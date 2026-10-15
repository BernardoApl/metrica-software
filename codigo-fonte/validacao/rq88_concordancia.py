"""RQ88: kappa de Fleiss entre os tres avaliadores e rotulo de consenso (secao 6, passos 3 e 4).

    python codigo-fonte/validacao/rq88_concordancia.py

Le as tres planilhas da RQ86 (``amostra_ouro/rotulos/rotulos_<avaliador>.xlsx``)
e, para cada dimensao rotulada (tipo do projeto, entregas reais, release
corretiva):

1. **concordancia:** kappa de Fleiss com ``aggregate_raters`` + ``fleiss_kappa``
   do statsmodels, a % de itens em que os tres concordam e a interpretacao de
   Landis & Koch (1977);
2. **consenso**, pelo protocolo de desempate do grupo:
   - 3-0 -> rotulo unanime (``origem = unanime``);
   - 2-1 -> maioria simples (``origem = maioria``);
   - 1-1-1 -> decidido em reuniao dos tres e registrado em
     ``decisoes_reuniao.csv`` (``origem = reuniao``). A reuniao tambem pode
     rever um 2-1, desde que registre a justificativa.

Enquanto houver empate 1-1-1 sem decisao, o consenso fica incompleto: o
comando grava ``pendencias_reuniao.csv`` (pauta da reuniao) e termina com
codigo 2. O kappa e sempre calculado sobre os rotulos **independentes**, antes
de qualquer decisao de reuniao.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

RAIZ_CODIGO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import rq86_amostra_ouro as ouro  # noqa: E402

PASTA_PADRAO = ouro.SAIDA_PADRAO

UNANIME, MAIORIA, REUNIAO, EMPATE = "unanime", "maioria", "reuniao", "empate_pendente"
COLUNAS_DECISOES = ("dimensao", "id_item", "rotulo", "justificativa")

#: Faixas de Landis & Koch (1977), como no enunciado: (limite superior inclusivo, rotulo).
FAIXAS_LANDIS_KOCH = ((0.20, "leve"), (0.40, "razoavel"), (0.60, "moderada"),
                      (0.80, "substancial"), (1.00, "quase perfeita"))


class PlanilhaIncompleta(ValueError):
    """Alguma planilha tem celulas vazias, valores invalidos ou linhas alteradas."""


# ------------------------------------------------------------------- kappa
def interpretar_kappa(kappa: Optional[float]) -> Optional[str]:
    if kappa is None:
        return None
    if kappa < 0:
        return "pobre"
    for limite, rotulo in FAIXAS_LANDIS_KOCH:
        if kappa <= limite:
            return rotulo
    return FAIXAS_LANDIS_KOCH[-1][1]


def kappa_fleiss(matriz: pd.DataFrame, categorias) -> Optional[float]:
    """Kappa de Fleiss de uma matriz itens x avaliadores com codigos de ``categorias``.

    Todas as categorias possiveis entram na tabela, inclusive as que ninguem
    usou. Devolve ``None`` quando o kappa e indefinido (todos os itens na
    mesma categoria: concordancia esperada = 1).
    """
    from statsmodels.stats.inter_rater import aggregate_raters, fleiss_kappa

    categorias = list(categorias)
    indices = matriz.apply(lambda coluna: coluna.map(categorias.index)).to_numpy()
    tabela, _ = aggregate_raters(indices, n_cat=len(categorias))
    with np.errstate(divide="ignore", invalid="ignore"):
        kappa = fleiss_kappa(tabela, method="fleiss")
    return None if math.isnan(kappa) else float(kappa)


def resumo_concordancia(dimensao: str, matriz: pd.DataFrame, categorias) -> dict:
    kappa = kappa_fleiss(matriz, categorias)
    unanimes = int((matriz.nunique(axis=1) == 1).sum())
    contagem = pd.Series(matriz.to_numpy().ravel()).value_counts()
    return {
        "dimensao": dimensao,
        "itens": len(matriz),
        "avaliadores": matriz.shape[1],
        "kappa_fleiss": kappa,
        "interpretacao": interpretar_kappa(kappa),
        "concordancia_total": unanimes / len(matriz) if len(matriz) else None,
        "itens_unanimes": unanimes,
        "itens_2_1": int((matriz.nunique(axis=1) == 2).sum()),
        "itens_1_1_1": int((matriz.nunique(axis=1) == 3).sum()),
        "distribuicao": {c: int(contagem.get(c, 0)) for c in categorias},
    }


# --------------------------------------------------------------- consenso
def consenso_do_item(rotulos: list) -> tuple[Optional[str], str]:
    """``(rotulo, origem)`` pela maioria; empate 1-1-1 -> ``(None, empate_pendente)``."""
    contagem = pd.Series(rotulos).value_counts()
    if contagem.iloc[0] == len(rotulos):
        return contagem.index[0], UNANIME
    if contagem.iloc[0] > len(rotulos) / 2:
        return contagem.index[0], MAIORIA
    return None, EMPATE


def aplicar_consenso(matriz: pd.DataFrame, dimensao: str, permitidos: dict,
                     decisoes: pd.DataFrame) -> pd.DataFrame:
    """Coluna ``consenso`` + ``origem`` (+ ``justificativa``) para cada item da matriz."""
    resultado = matriz.copy()
    pares = [consenso_do_item(list(linha)) for linha in matriz.itertuples(index=False)]
    resultado["consenso"] = [rotulo for rotulo, _ in pares]
    resultado["origem"] = [origem for _, origem in pares]
    resultado["justificativa"] = ""
    da_dimensao = decisoes[decisoes["dimensao"] == dimensao]
    for _, decisao in da_dimensao.iterrows():
        item = decisao["id_item"]
        if item not in resultado.index:
            raise ValueError("decisoes_reuniao.csv: %s nao e um item de %s." % (item, dimensao))
        rotulo = ouro.codigo_do_rotulo(decisao["rotulo"], permitidos)
        if rotulo is None:
            raise ValueError("decisoes_reuniao.csv: rotulo %r invalido para %s (%s)."
                             % (decisao["rotulo"], dimensao, item))
        if not str(decisao.get("justificativa") or "").strip():
            raise ValueError("decisoes_reuniao.csv: %s/%s sem justificativa." % (dimensao, item))
        resultado.loc[item, ["consenso", "origem", "justificativa"]] = [
            rotulo, REUNIAO, decisao["justificativa"]]
    return resultado


def ler_decisoes(caminho: Path) -> pd.DataFrame:
    if not caminho.exists():
        return pd.DataFrame(columns=COLUNAS_DECISOES)
    decisoes = pd.read_csv(caminho, dtype=str, keep_default_na=False)
    faltando = set(COLUNAS_DECISOES) - set(decisoes.columns)
    if faltando:
        raise ValueError("decisoes_reuniao.csv sem as colunas %s." % sorted(faltando))
    repetidas = decisoes.duplicated(["dimensao", "id_item"])
    if repetidas.any():
        raise ValueError("decisoes_reuniao.csv repete itens: %s."
                         % decisoes.loc[repetidas, "id_item"].tolist())
    return decisoes


# ---------------------------------------------------------------- leitura
def carregar_rotulos(pasta: Path, avaliadores=ouro.AVALIADORES) -> dict:
    """``{dimensao: matriz itens x avaliadores}`` a partir das planilhas validadas.

    :raises PlanilhaIncompleta: se alguma planilha nao passar no ``validar`` da RQ86.
    """
    problemas, lidas = [], {}
    for avaliador in avaliadores:
        planilha = pasta / "rotulos" / ("rotulos_%s.xlsx" % avaliador)
        if not planilha.exists():
            problemas.append("%s: planilha ausente (%s)" % (avaliador, planilha))
            continue
        abas = ouro.ler_planilha(planilha)
        validacao = ouro.validar_planilha(planilha, pasta, abas=abas)
        if not validacao["completa"]:
            problemas.append("%s: %d problema(s), ex.: %s" % (
                avaliador, len(validacao["problemas"]), validacao["problemas"][0]))
            continue
        lidas[avaliador] = abas
    if problemas:
        raise PlanilhaIncompleta("; ".join(problemas))

    matrizes = {}
    for aba, coluna, _ in ouro.DIMENSOES:
        chave = ouro.CHAVES[aba][0]
        matrizes[coluna] = pd.DataFrame({
            avaliador: abas[aba].set_index(chave)[coluna] for avaliador, abas in lidas.items()})
    return matrizes


# -------------------------------------------------------------- execucao
def executar(pasta: Path, avaliadores=ouro.AVALIADORES) -> dict:
    """Calcula kappa e consenso e grava os arquivos em ``pasta``."""
    matrizes = carregar_rotulos(pasta, avaliadores)
    decisoes = ler_decisoes(pasta / "decisoes_reuniao.csv")
    resumos, consensos, pendencias = [], {}, []
    for aba, dimensao, permitidos in ouro.DIMENSOES:
        matriz = matrizes[dimensao]
        resumos.append(resumo_concordancia(dimensao, matriz, permitidos))
        consenso = aplicar_consenso(matriz, dimensao, permitidos, decisoes)
        consensos[dimensao] = consenso
        for item, linha in consenso.iterrows():
            # Pauta: empates (obrigatorios) e divergencias 2-1 (para revisar, se o grupo quiser).
            if linha["origem"] in (EMPATE, MAIORIA):
                pendencias.append({"dimensao": dimensao, "id_item": item,
                                   "obrigatoria": linha["origem"] == EMPATE,
                                   **{a: linha[a] for a in matriz.columns},
                                   "maioria": linha["consenso"] if linha["origem"] == MAIORIA else ""})

    sorteio_repos = pd.read_csv(pasta / "sorteio_repositorios.csv", dtype=str)
    sorteio_releases = pd.read_csv(pasta / "sorteio_releases.csv", dtype=str)
    repositorios = sorteio_repos[["id_repositorio", "nome_completo"]].set_index("id_repositorio")
    for dimensao in ("tipo_projeto", "entregas_reais"):
        consenso = consensos[dimensao]
        repositorios = repositorios.join(
            consenso[list(avaliadores)].add_prefix(dimensao + "_"))
        repositorios = repositorios.join(consenso[["consenso", "origem", "justificativa"]]
                                         .add_prefix(dimensao + "_"))
    releases = sorteio_releases[["id_release", "id_repositorio", "nome_completo", "tag_name",
                                 "release_anterior", "published_at"]].set_index("id_release")
    corretiva = consensos["corretiva"]
    releases = releases.join(corretiva[list(avaliadores)].add_prefix("corretiva_"))
    releases = releases.join(corretiva[["consenso", "origem", "justificativa"]]
                             .add_prefix("corretiva_"))

    repositorios.reset_index().to_csv(pasta / "consenso_repositorios.csv", index=False)
    releases.reset_index().to_csv(pasta / "consenso_releases.csv", index=False)
    pd.DataFrame([{k: v for k, v in r.items() if k != "distribuicao"}
                  | {"distribuicao": json.dumps(r["distribuicao"])} for r in resumos]
                 ).to_csv(pasta / "concordancia_fleiss.csv", index=False)
    colunas_pauta = ["dimensao", "id_item", "obrigatoria", *avaliadores, "maioria"]
    pd.DataFrame(pendencias, columns=colunas_pauta).to_csv(pasta / "pendencias_reuniao.csv",
                                                           index=False)
    empates = sum(1 for p in pendencias if p["obrigatoria"])
    resumo = {
        "avaliadores": list(avaliadores),
        "protocolo": "3-0 unanime; 2-1 maioria simples; 1-1-1 decidido em reuniao "
                     "(decisoes_reuniao.csv), que tambem pode rever 2-1 com justificativa",
        "concordancia": resumos,
        "empates_sem_decisao": empates,
        "consenso_completo": empates == 0,
        "origem_do_consenso": {d: c["origem"].value_counts().to_dict()
                               for d, c in consensos.items()},
    }
    (pasta / "concordancia_fleiss.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    return resumo


def principal(argv=None) -> int:
    parser = argparse.ArgumentParser(description="RQ88: kappa de Fleiss e consenso.")
    parser.add_argument("--pasta", type=Path, default=PASTA_PADRAO,
                        help="pasta da amostra-ouro gerada pela RQ86")
    args = parser.parse_args(argv)
    try:
        resumo = executar(args.pasta)
    except PlanilhaIncompleta as erro:
        print("Planilhas ainda incompletas (rode o validar da RQ86): %s" % erro, file=sys.stderr)
        return 1
    except (OSError, ValueError) as erro:
        print("Erro: %s" % erro, file=sys.stderr)
        return 1
    for r in resumo["concordancia"]:
        kappa = "indefinido" if r["kappa_fleiss"] is None else "%.3f" % r["kappa_fleiss"]
        print("%-15s kappa = %-10s (%s) | %3.0f%% unanimes | 2-1: %d | 1-1-1: %d"
              % (r["dimensao"], kappa, r["interpretacao"] or "-",
                 100 * r["concordancia_total"], r["itens_2_1"], r["itens_1_1_1"]))
    if not resumo["consenso_completo"]:
        print("\n%d empate(s) 1-1-1 sem decisao. Pauta em %s; registre as decisoes em %s."
              % (resumo["empates_sem_decisao"], args.pasta / "pendencias_reuniao.csv",
                 args.pasta / "decisoes_reuniao.csv"))
        return 2
    print("\nConsenso completo: consenso_repositorios.csv e consenso_releases.csv.")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
