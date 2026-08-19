"""RQ16 - Sistemas que aceitam mais pull requests lancam mais releases?

Metrica: correlacao entre pull requests aceitas (RQ02, ``rq02_pull_requests_aceitos``)
e quantidade de releases (RQ03, ``rq03_total_releases``).

Nao ha campo GraphQL novo a coletar: RQ02 e RQ03 ja fazem parte do fragmento
``CAMPOS_RQ07`` de ``consulta.py``, o mesmo que alimenta o agrupamento por
linguagem da RQ07. Este modulo so combina os dois resultados ja calculados.

- **Coeficiente:** correlacao de Pearson, calculada com a biblioteca padrao
  (``statistics``), sem numpy/pandas.
- **Faixas de releases:** alem do coeficiente global, os repositorios sao
  agrupados por quantidade de releases para inspecionar a tendencia sem
  depender de um grafico de dispersao.
- **Valores ausentes:** repositorios sem uma das duas metricas (por exemplo,
  campo nao solicitado na consulta) sao excluidos do calculo da correlacao e
  do agrupamento por faixa, mas continuam contados em
  ``descartados_sem_par_completo``.

ATENCAO -- ``rq03_total_releases`` via GraphQL (``releases.totalCount``) e
pouco confiavel para repositorios com muitos releases (ver o aviso em
``rq03_releases_graphql.py``). Como este modulo le o campo ``rq03_total_releases``
generico (nao o sufixado ``_graphql``), quando a coleta unificada substitui esse
campo pelo valor da API REST (paginado, confiavel), a RQ16 se beneficia
automaticamente.
"""

from __future__ import annotations

import statistics
from typing import Iterable, Optional

#: Campos ja calculados pela RQ02 e pela RQ03, combinados aqui.
CAMPO_PRS_ACEITAS = "rq02_pull_requests_aceitos"
CAMPO_TOTAL_RELEASES = "rq03_total_releases"

#: Faixas de quantidade de releases usadas para agrupar a tendencia. O limite
#: superior e exclusivo; ``None`` marca a ultima faixa, sem teto.
FAIXAS_RELEASES = (
    (0, 1, "Sem releases"),
    (1, 11, "1 a 10 releases"),
    (11, 51, "11 a 50 releases"),
    (51, None, "Mais de 50 releases"),
)


def extrair_pares(registros: Iterable[dict]) -> list:
    """Extrai os pares (prs_aceitas, total_releases) dos registros com as duas metricas presentes."""
    pares = []
    for registro in registros:
        prs = (registro or {}).get(CAMPO_PRS_ACEITAS)
        releases = (registro or {}).get(CAMPO_TOTAL_RELEASES)
        if isinstance(prs, (int, float)) and isinstance(releases, (int, float)):
            pares.append((float(prs), float(releases)))
    return pares


def calcular_correlacao_pearson(pares: list) -> Optional[float]:
    """Calcula o coeficiente de correlacao de Pearson entre os pares.

    :return: ``None`` quando ha menos de dois pares ou quando um dos dois
        conjuntos de valores nao tem variancia (correlacao indefinida nesses
        casos, nao zero).
    """
    if len(pares) < 2:
        return None

    xs = [par[0] for par in pares]
    ys = [par[1] for par in pares]
    desvio_x = statistics.pstdev(xs)
    desvio_y = statistics.pstdev(ys)
    if desvio_x == 0 or desvio_y == 0:
        return None

    media_x = statistics.fmean(xs)
    media_y = statistics.fmean(ys)
    covariancia = sum((x - media_x) * (y - media_y) for x, y in pares) / len(pares)
    return round(covariancia / (desvio_x * desvio_y), 4)


def classificar_forca(coeficiente: Optional[float]) -> str:
    """Traduz o coeficiente em uma leitura textual (forca + sinal)."""
    if coeficiente is None:
        return "indeterminada (pares insuficientes ou sem variancia)"
    if coeficiente == 0:
        return "nula"

    magnitude = abs(coeficiente)
    if magnitude < 0.2:
        forca = "muito fraca"
    elif magnitude < 0.4:
        forca = "fraca"
    elif magnitude < 0.6:
        forca = "moderada"
    elif magnitude < 0.8:
        forca = "forte"
    else:
        forca = "muito forte"

    sinal = "positiva" if coeficiente > 0 else "negativa"
    return "%s %s" % (forca, sinal)


def _faixa_de(total_releases: float) -> str:
    for minimo, maximo, rotulo in FAIXAS_RELEASES:
        if total_releases >= minimo and (maximo is None or total_releases < maximo):
            return rotulo
    return FAIXAS_RELEASES[-1][2]


def agrupar_por_faixa_de_releases(pares: list) -> dict:
    """Agrupa as pull requests aceitas por faixa de quantidade de releases."""
    grupos = {rotulo: [] for _, _, rotulo in FAIXAS_RELEASES}
    for prs, releases in pares:
        grupos[_faixa_de(releases)].append(prs)

    resultado = {}
    for _, _, rotulo in FAIXAS_RELEASES:
        valores = grupos[rotulo]
        resultado[rotulo] = {
            "quantidade_repositorios": len(valores),
            "media_prs_aceitas": round(statistics.fmean(valores), 4) if valores else None,
            "mediana_prs_aceitas": round(statistics.median(valores), 4) if valores else None,
        }
    return resultado


def definicao() -> dict:
    """Definicao da metrica, gravada nos metadados da coleta."""
    return {
        "questao": "RQ16 - Sistemas que aceitam mais pull requests lancam mais releases?",
        "metrica": "Correlacao entre pull requests aceitas (RQ02) e quantidade de releases (RQ03)",
        "campos_utilizados": [CAMPO_PRS_ACEITAS, CAMPO_TOTAL_RELEASES],
        "formula": "Coeficiente de correlacao de Pearson entre rq02_pull_requests_aceitos e rq03_total_releases",
        "faixas_de_releases": [rotulo for _, _, rotulo in FAIXAS_RELEASES],
        "tratamento_de_ausentes": (
            "Repositorios sem uma das duas metricas sao excluidos do calculo da correlacao "
            "e do agrupamento por faixa, mas continuam contados em 'descartados_sem_par_completo'."
        ),
    }


def resumir(registros: Iterable[dict]) -> dict:
    """Calcula a RQ16 sobre a coleta inteira."""
    registros = list(registros)
    pares = extrair_pares(registros)
    coeficiente = calcular_correlacao_pearson(pares)

    return {
        "total_repositorios": len(registros),
        "pares_utilizados": len(pares),
        "descartados_sem_par_completo": len(registros) - len(pares),
        "coeficiente_correlacao_pearson": coeficiente,
        "interpretacao": classificar_forca(coeficiente),
        "por_faixa_de_releases": agrupar_por_faixa_de_releases(pares),
    }
