"""RQ15 - Sistemas mais antigos tem maior percentual de issues fechadas?

Metrica: correlacao entre a idade do repositorio (RQ01, ``rq01_idade_anos``) e a
razao de issues fechadas (RQ06, ``rq06_razao_fechadas_total``).

Nao ha campos GraphQL novos a coletar: RQ01 e RQ06 ja fazem parte da consulta
unificada do grupo (``CAMPOS_RQ01`` e ``CAMPOS_RQ06_RQ07`` em ``consulta.py``).
Este modulo so combina os dois resultados ja calculados.

- **Coeficiente:** correlacao de Pearson, calculada com a biblioteca padrao
  (``statistics``), sem numpy/pandas.
- **Faixas de idade:** alem do coeficiente global, os repositorios sao
  agrupados em faixas de idade para inspecionar a tendencia sem depender de um
  grafico de dispersao.
- **Valores ausentes:** repositorios sem idade (``sem_data_criacao``) ou sem
  razao de issues fechadas (por exemplo, ``sem_issues``) sao excluidos do
  calculo -- correlacao nao aceita valor nulo -- mas continuam contados em
  ``descartados_sem_par_completo``, para que a exclusao fique auditavel.
"""

from __future__ import annotations

import statistics
from typing import Iterable, Optional, Tuple

#: Campos ja calculados pela RQ01 e pela RQ06, combinados aqui.
CAMPO_IDADE = "rq01_idade_anos"
CAMPO_RAZAO_FECHADAS = "rq06_razao_fechadas_total"

#: Faixas de idade usadas para agrupar a tendencia. O limite superior e exclusivo;
#: ``None`` marca a ultima faixa, sem teto.
FAIXAS_IDADE = (
    (0.0, 2.0, "Ate 2 anos"),
    (2.0, 5.0, "2 a 5 anos"),
    (5.0, 10.0, "5 a 10 anos"),
    (10.0, None, "Mais de 10 anos"),
)


def extrair_pares(registros: Iterable[dict]) -> list:
    """Extrai os pares (idade_anos, razao_fechadas) dos registros com as duas metricas presentes."""
    pares = []
    for registro in registros:
        idade = (registro or {}).get(CAMPO_IDADE)
        razao = (registro or {}).get(CAMPO_RAZAO_FECHADAS)
        if isinstance(idade, (int, float)) and isinstance(razao, (int, float)):
            pares.append((float(idade), float(razao)))
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


def _faixa_de(idade: float) -> str:
    for minimo, maximo, rotulo in FAIXAS_IDADE:
        if idade >= minimo and (maximo is None or idade < maximo):
            return rotulo
    return FAIXAS_IDADE[-1][2]


def agrupar_por_faixa_de_idade(pares: list) -> dict:
    """Agrupa a razao de issues fechadas por faixa de idade do repositorio."""
    grupos = {rotulo: [] for _, _, rotulo in FAIXAS_IDADE}
    for idade, razao in pares:
        grupos[_faixa_de(idade)].append(razao)

    resultado = {}
    for _, _, rotulo in FAIXAS_IDADE:
        valores = grupos[rotulo]
        resultado[rotulo] = {
            "quantidade_repositorios": len(valores),
            "media_razao_fechadas": round(statistics.fmean(valores), 4) if valores else None,
            "mediana_razao_fechadas": round(statistics.median(valores), 4) if valores else None,
        }
    return resultado


def definicao() -> dict:
    """Definicao da metrica, gravada nos metadados da coleta."""
    return {
        "questao": "RQ15 - Sistemas mais antigos tem maior percentual de issues fechadas?",
        "metrica": "Correlacao entre a idade do repositorio (RQ01) e a razao de issues fechadas (RQ06)",
        "campos_utilizados": [CAMPO_IDADE, CAMPO_RAZAO_FECHADAS],
        "formula": "Coeficiente de correlacao de Pearson entre rq01_idade_anos e rq06_razao_fechadas_total",
        "faixas_de_idade": [rotulo for _, _, rotulo in FAIXAS_IDADE],
        "tratamento_de_ausentes": (
            "Repositorios sem idade (sem_data_criacao) ou sem razao de issues fechadas "
            "(por exemplo, sem_issues) sao excluidos do calculo da correlacao e do "
            "agrupamento por faixa, mas continuam contados em 'descartados_sem_par_completo'."
        ),
    }


def resumir(registros: Iterable[dict]) -> dict:
    """Calcula a RQ15 sobre a coleta inteira."""
    registros = list(registros)
    pares = extrair_pares(registros)
    coeficiente = calcular_correlacao_pearson(pares)

    return {
        "total_repositorios": len(registros),
        "pares_utilizados": len(pares),
        "descartados_sem_par_completo": len(registros) - len(pares),
        "coeficiente_correlacao_pearson": coeficiente,
        "interpretacao": classificar_forca(coeficiente),
        "por_faixa_de_idade": agrupar_por_faixa_de_idade(pares),
    }
