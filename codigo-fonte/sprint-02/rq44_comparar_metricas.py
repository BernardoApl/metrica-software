"""RQ44 (Inovacao): coleta e comparacao de complexidade, LOC e duplicacao das solucoes.

Le o CSV consolidado da RQ30 (dados/lab02_rq30_metricas_estaticas.csv) e produz,
por kata e por tratamento (com_ia vs sem_ia), a mediana e o IQR de complexidade
ciclomatica media, LOC e percentual de duplicacao. Usa mediana/IQR em vez de
media/desvio-padrao, conforme a recomendacao de robustez estatistica do LAB02
para o N pequeno do desenho within-subject (ver RQ33 - Hipoteses).
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ENTRADA_PADRAO = Path(__file__).resolve().parents[2] / "dados" / "lab02_rq30_metricas_estaticas.csv"
SAIDA_CSV_PADRAO = Path(__file__).resolve().parents[2] / "dados" / "lab02_rq44_comparacao_metricas.csv"
SAIDA_GRAFICO_PADRAO = Path(__file__).resolve().parents[2] / "dados" / "rq44_comparacao_metricas.png"

METRICAS = ("complexidade_media", "loc", "duplicacao_percentual")


def _float_ou_none(valor):
    if valor is None or valor == "":
        return None
    try:
        return float(valor)
    except ValueError:
        return None


def carregar_registros(caminho: Path) -> list[dict]:
    with caminho.open(newline="", encoding="utf-8") as arquivo:
        return list(csv.DictReader(arquivo))


def agrupar(registros: list[dict], chave) -> dict:
    grupos = defaultdict(list)
    for registro in registros:
        grupos[chave(registro)].append(registro)
    return grupos


def _mediana_e_iqr(valores: list[float]):
    """Mediana e IQR (hinges de Tukey) de uma lista de valores validos."""
    if not valores:
        return None, None, 0
    valores_ordenados = sorted(valores)
    mediana = statistics.median(valores_ordenados)
    if len(valores_ordenados) < 2:
        return mediana, None, len(valores_ordenados)
    metade = len(valores_ordenados) // 2
    metade_inferior = valores_ordenados[:metade]
    metade_superior = valores_ordenados[-metade:]
    q1 = statistics.median(metade_inferior)
    q3 = statistics.median(metade_superior)
    return mediana, q3 - q1, len(valores_ordenados)


def comparar_por_tratamento(registros: list[dict]) -> list[dict]:
    """Uma linha por (kata, tratamento) com mediana/IQR/N de cada metrica."""
    linhas = []
    por_kata_tratamento = agrupar(registros, lambda r: (r["kata"], r["tratamento"]))
    for (kata, tratamento), grupo in sorted(por_kata_tratamento.items()):
        linha = {"kata": kata, "tratamento": tratamento, "n_trials": len(grupo)}
        for metrica in METRICAS:
            valores = [v for v in (_float_ou_none(r.get(metrica)) for r in grupo) if v is not None]
            mediana, iqr, n_validos = _mediana_e_iqr(valores)
            linha[f"{metrica}_mediana"] = mediana
            linha[f"{metrica}_iqr"] = iqr
            linha[f"{metrica}_n"] = n_validos
        linhas.append(linha)
    return linhas


def salvar_csv(linhas: list[dict], caminho: Path) -> None:
    if not linhas:
        return
    caminho.parent.mkdir(parents=True, exist_ok=True)
    colunas = list(linhas[0].keys())
    with caminho.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=colunas)
        escritor.writeheader()
        escritor.writerows(linhas)


def gerar_grafico(linhas: list[dict], caminho: Path) -> None:
    import matplotlib.pyplot as plt

    tratamentos = sorted({linha["tratamento"] for linha in linhas})
    katas = sorted({linha["kata"] for linha in linhas})
    if not tratamentos or not katas:
        return

    largura = 0.8 / len(tratamentos)
    figura, eixos = plt.subplots(1, len(METRICAS), figsize=(6 * len(METRICAS), 5))
    if len(METRICAS) == 1:
        eixos = [eixos]

    for eixo, metrica in zip(eixos, METRICAS):
        for indice, tratamento in enumerate(tratamentos):
            valores = []
            for kata in katas:
                correspondentes = [l for l in linhas if l["kata"] == kata and l["tratamento"] == tratamento]
                valor = correspondentes[0][f"{metrica}_mediana"] if correspondentes else None
                valores.append(valor if valor is not None else 0)
            posicoes = [indice_kata + indice * largura for indice_kata in range(len(katas))]
            eixo.bar(posicoes, valores, width=largura, label=tratamento)
        eixo.set_xticks([indice_kata + largura * (len(tratamentos) - 1) / 2 for indice_kata in range(len(katas))])
        eixo.set_xticklabels(katas, rotation=45, ha="right")
        eixo.set_title(f"{metrica} (mediana)")
        eixo.legend()
        eixo.grid(True, axis="y", ls="--", alpha=0.3)

    figura.tight_layout()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    figura.savefig(caminho, dpi=300, bbox_inches="tight")
    print("Grafico gerado em: %s" % caminho)


def principal(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entrada", type=Path, default=ENTRADA_PADRAO,
                        help="CSV consolidado da RQ30 (padrao: %(default)s).")
    parser.add_argument("--saida-csv", type=Path, default=SAIDA_CSV_PADRAO)
    parser.add_argument("--saida-grafico", type=Path, default=SAIDA_GRAFICO_PADRAO)
    parser.add_argument("--sem-grafico", action="store_true",
                        help="Pula a geracao do grafico (dispensa matplotlib).")
    args = parser.parse_args(argv)

    if not args.entrada.is_file():
        parser.error("CSV de entrada nao encontrado: %s (rode a RQ30 antes)." % args.entrada)

    registros = carregar_registros(args.entrada)
    if not registros:
        parser.error("CSV de entrada esta vazio.")

    linhas = comparar_por_tratamento(registros)
    salvar_csv(linhas, args.saida_csv)

    for linha in linhas:
        print("%s | %s | n=%d | CC mediana=%s (IQR=%s) | LOC mediana=%s (IQR=%s) | Duplicacao mediana=%s%% (IQR=%s)" % (
            linha["kata"], linha["tratamento"], linha["n_trials"],
            linha["complexidade_media_mediana"], linha["complexidade_media_iqr"],
            linha["loc_mediana"], linha["loc_iqr"],
            linha["duplicacao_percentual_mediana"], linha["duplicacao_percentual_iqr"]))

    if not args.sem_grafico:
        try:
            gerar_grafico(linhas, args.saida_grafico)
        except ImportError:
            print("Aviso: matplotlib nao instalado; grafico nao gerado.", file=sys.stderr)

    print("Comparacao salva em: %s" % args.saida_csv.resolve())
    return 0


if __name__ == "__main__":
    sys.exit(principal())
