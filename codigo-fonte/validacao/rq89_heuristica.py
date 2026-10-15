"""RQ89: precisao, recall e F1 da heuristica de release corretiva (secao 6, passo 5).

    python codigo-fonte/validacao/rq89_heuristica.py avaliar \\
        --consenso dados/lab03_final/amostra_ouro/consenso_releases.csv

Compara cada versao de ``metricas.corretiva.HEURISTICAS`` com o **rotulo de
consenso** das releases sorteadas na RQ86 (a classe positiva e "corretiva").
Se o F1 da melhor versao ficar abaixo de 0,70, o enunciado manda refinar a
heuristica e reavaliar; o historico de versoes e F1 vai para o artigo.

Entradas:

- ``<amostra>/sorteio_releases.csv`` (RQ86): releases sorteadas, com a anterior;
- ``<entrada>/commits_releases.csv.gz`` (RQ76/RQ82): mensagens dos commits do ``compare``;
- ``--consenso``: CSV com ``id_release`` e ``corretiva`` (sim/nao), produzido
  pela consolidacao da RQ88, **ou** uma planilha ``.xlsx`` de um avaliador (util
  para uma checagem preliminar com os proprios rotulos, nunca como o resultado final).
  Releases sem rotulo valido ficam fora e sao contadas no relatorio.

Saidas em ``--saida`` (padrao: a pasta da amostra-ouro): ``avaliacao_heuristica.csv``
(uma linha por versao), ``erros_heuristica.csv`` (falsos positivos e negativos de
cada versao, com os links para ler a release) e ``avaliacao_heuristica.json``.
Retorna 0 se alguma versao atinge o limiar, 2 se nao atinge, 1 em erro de entrada.

A heuristica **nao** e usada para rotular nada: os rotulos humanos vieram antes,
sem ela (cegueira exigida na RQ86). Este script so confronta os dois.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

RAIZ_CODIGO = Path(__file__).resolve().parents[1]
RAIZ_PROJETO = RAIZ_CODIGO.parent
sys.path.insert(0, str(RAIZ_CODIGO))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from metricas import corretiva  # noqa: E402
import rq86_amostra_ouro as ouro  # noqa: E402

LIMIAR_F1 = 0.70
ENTRADA_PADRAO = ouro.ENTRADA_PADRAO
AMOSTRA_PADRAO = ouro.SAIDA_PADRAO
CONSENSO_PADRAO = AMOSTRA_PADRAO / "consenso_releases.csv"
#: ``corretiva_consenso`` e a coluna do ``consenso_releases.csv`` gerado pela RQ88.
COLUNAS_ROTULO = ("corretiva_consenso", "corretiva", "consenso", "consenso_corretiva")


# ----------------------------------------------------------------------- entradas
def ler_rotulos(caminho: Path) -> tuple[dict, list]:
    """``({id_release: True|False}, [ids sem rotulo valido])`` de um CSV ou ``.xlsx``."""
    caminho = Path(caminho)
    if caminho.suffix.lower() == ".xlsx":
        tabela = ouro.ler_planilha(caminho)["releases"]
        codigos = zip(tabela["id_release"], tabela["corretiva"])
    else:
        tabela = pd.read_csv(caminho, dtype=str, keep_default_na=False)
        coluna = next((c for c in COLUNAS_ROTULO if c in tabela), None)
        if "id_release" not in tabela or coluna is None:
            raise ValueError("%s: precisa das colunas id_release e uma entre %s."
                             % (caminho, ", ".join(COLUNAS_ROTULO)))
        codigos = zip(tabela["id_release"],
                      (ouro.codigo_do_rotulo(v, ouro.CORRETIVA) for v in tabela[coluna]))
    rotulos, invalidos = {}, []
    for id_release, codigo in codigos:
        if id_release in rotulos or id_release in invalidos:
            raise ValueError("%s: id_release repetido: %s" % (caminho, id_release))
        if codigo is None:
            invalidos.append(id_release)
        else:
            rotulos[id_release] = codigo == "sim"
    return rotulos, invalidos


def montar_tabela(sorteio: pd.DataFrame, commits: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por release sorteada, com a lista de mensagens do ``compare``.

    ``mensagens`` e ``None`` quando o ``compare`` nao tem commits registrados
    (a heuristica so enxerga a tag nesse caso).
    """
    por_par = {}
    for chave, grupo in commits.groupby(["nome_completo", "anterior", "tag_name"], sort=False):
        por_par[chave] = [m if isinstance(m, str) else "" for m in grupo["mensagem"]]
    tabela = sorteio.copy()
    tabela["mensagens"] = [por_par.get((n, a, t)) for n, a, t in
                           zip(tabela["nome_completo"], tabela["release_anterior"],
                               tabela["tag_name"])]
    return tabela


def ler_entradas(entrada: Path, amostra: Path) -> pd.DataFrame:
    arquivos = (amostra / "sorteio_releases.csv", entrada / "commits_releases.csv.gz")
    faltam = [str(a) for a in arquivos if not a.exists()]
    if faltam:
        raise FileNotFoundError("Faltam: %s. Gere o sorteio (RQ86) e a coleta final (RQ82)."
                                % ", ".join(faltam))
    sorteio = pd.read_csv(arquivos[0], dtype=str, keep_default_na=False)
    commits = pd.read_csv(arquivos[1], dtype=str, keep_default_na=False)
    if "mensagem" not in commits:
        raise ValueError("%s sem a coluna 'mensagem'; refaca a coleta (RQ76)." % arquivos[1])
    return montar_tabela(sorteio, commits)


# ------------------------------------------------------------------------ metricas
def prever(tabela: pd.DataFrame, nome: str) -> list[bool]:
    return [corretiva.classificar(nome, anterior, tag, mensagens)
            for anterior, tag, mensagens in zip(tabela["release_anterior"], tabela["tag_name"],
                                                tabela["mensagens"])]


def avaliar(tabela: pd.DataFrame, rotulos: dict, versoes=None) -> list[dict]:
    """Precisao, recall e F1 (classe positiva = corretiva) de cada versao.

    Usa ``sklearn.metrics.precision_recall_fscore_support``. Quando a heuristica
    nao marca nenhuma release, a precisao e 0 por convencao (``zero_division=0``).
    """
    from sklearn.metrics import precision_recall_fscore_support

    rotulada = tabela[tabela["id_release"].isin(rotulos)].reset_index(drop=True)
    if rotulada.empty:
        raise ValueError("Nenhuma release sorteada tem rotulo de consenso.")
    reais = [rotulos[i] for i in rotulada["id_release"]]
    resultados = []
    for nome in versoes or corretiva.HEURISTICAS:
        previstas = prever(rotulada, nome)
        p, r, f1, _ = precision_recall_fscore_support(
            reais, previstas, average="binary", pos_label=True, zero_division=0)
        pares = list(zip(reais, previstas))
        resultados.append({
            "versao": nome, "n": len(pares),
            "corretivas_consenso": sum(reais), "corretivas_heuristica": sum(previstas),
            "vp": sum(a and b for a, b in pares), "fp": sum(not a and b for a, b in pares),
            "fn": sum(a and not b for a, b in pares), "vn": sum(not a and not b for a, b in pares),
            "precisao": float(p), "recall": float(r), "f1": float(f1),
            "sem_mensagens": int(sum(m is None for m in rotulada["mensagens"])),
        })
    return resultados


def listar_erros(tabela: pd.DataFrame, rotulos: dict, versoes=None) -> pd.DataFrame:
    """Falsos positivos e negativos, com as evidencias, para ler e refinar a heuristica."""
    linhas = []
    rotulada = tabela[tabela["id_release"].isin(rotulos)].reset_index(drop=True)
    for nome in versoes or corretiva.HEURISTICAS:
        for i, prevista in enumerate(prever(rotulada, nome)):
            linha = rotulada.iloc[i]
            real = rotulos[linha["id_release"]]
            if prevista == real:
                continue
            ev = corretiva.evidencias(linha["release_anterior"], linha["tag_name"],
                                      linha["mensagens"])
            linhas.append({"versao": nome, "erro": "falso_positivo" if prevista else "falso_negativo",
                           "id_release": linha["id_release"], "nome_completo": linha["nome_completo"],
                           "tag_name": linha["tag_name"], "release_anterior": linha["release_anterior"],
                           **{"ev_" + k: v for k, v in ev.items()},
                           "link_release": linha.get("link_release", ""),
                           "link_commits": linha.get("link_commits", "")})
    return pd.DataFrame(linhas)


def melhor(resultados: list[dict]) -> dict:
    """Maior F1; empate vai para a versao mais recente (a ultima da lista)."""
    return max(reversed(resultados), key=lambda r: r["f1"])


def executar(consenso: Path, entrada: Path, amostra: Path, saida: Path,
             limiar: float = LIMIAR_F1) -> dict:
    tabela = ler_entradas(entrada, amostra)
    rotulos, invalidos = ler_rotulos(consenso)
    desconhecidos = sorted(set(rotulos) - set(tabela["id_release"]))
    if desconhecidos:
        raise ValueError("Rotulos de releases fora do sorteio: %s" % ", ".join(desconhecidos[:5]))
    resultados = avaliar(tabela, rotulos)
    erros = listar_erros(tabela, rotulos)
    melhor_versao = melhor(resultados)
    resumo = {"issue": 89, "limiar_f1": limiar, "consenso": str(consenso),
              "releases_sorteadas": len(tabela), "releases_rotuladas": len(rotulos),
              "releases_sem_rotulo": invalidos + sorted(set(tabela["id_release"]) - set(rotulos)
                                                         - set(invalidos)),
              "versoes": resultados, "melhor_versao": melhor_versao["versao"],
              "atinge_limiar": melhor_versao["f1"] >= limiar,
              "versao_padrao_atual": corretiva.HEURISTICA_PADRAO}
    saida.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(resultados).to_csv(saida / "avaliacao_heuristica.csv", index=False)
    erros.to_csv(saida / "erros_heuristica.csv", index=False)
    (saida / "avaliacao_heuristica.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    return resumo


# ---------------------------------------------------------------------------- CLI
def principal(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="RQ89: P/R/F1 da heuristica de release corretiva.")
    sub = parser.add_subparsers(dest="comando", required=True)
    p = sub.add_parser("avaliar", help="compara as versoes da heuristica com o consenso")
    p.add_argument("--consenso", type=Path, default=CONSENSO_PADRAO,
                   help="CSV (id_release, corretiva) do consenso da RQ88, ou .xlsx de um avaliador")
    p.add_argument("--entrada", type=Path, default=ENTRADA_PADRAO,
                   help="pasta com commits_releases.csv.gz (RQ82)")
    p.add_argument("--amostra", type=Path, default=AMOSTRA_PADRAO,
                   help="pasta com sorteio_releases.csv (RQ86)")
    p.add_argument("--saida", type=Path, default=None)
    p.add_argument("--limiar", type=float, default=LIMIAR_F1)
    args = parser.parse_args(argv)
    try:
        resumo = executar(args.consenso, args.entrada, args.amostra,
                          args.saida or args.amostra, args.limiar)
    except (OSError, ValueError) as erro:
        print("Erro: %s" % erro, file=sys.stderr)
        return 1
    for r in resumo["versoes"]:
        print("%-26s P=%.3f R=%.3f F1=%.3f (VP=%d FP=%d FN=%d VN=%d)" % (
            r["versao"], r["precisao"], r["recall"], r["f1"], r["vp"], r["fp"], r["fn"], r["vn"]))
    if resumo["releases_sem_rotulo"]:
        print("Aviso: %d releases sem rotulo valido ficaram fora." % len(resumo["releases_sem_rotulo"]))
    if resumo["atinge_limiar"]:
        print("Melhor: %s (F1 >= %.2f)." % (resumo["melhor_versao"], args.limiar))
        return 0
    print("Nenhuma versao atinge F1 %.2f: refine a heuristica (veja erros_heuristica.csv) e "
          "reavalie." % args.limiar)
    return 2


if __name__ == "__main__":
    raise SystemExit(principal())
