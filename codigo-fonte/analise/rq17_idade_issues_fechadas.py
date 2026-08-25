"""RQ17 - Relacao entre idade do repositorio e percentual de issues fechadas.

Esta RQ reutiliza dados ja consolidados:

- ``rq01_idade_anos`` da RQ01;
- ``rq06_issues_total`` e ``rq06_razao_fechadas_total`` da RQ06.

O snapshot unificado atual dos 1.000 repositorios nao preserva a quantidade
exata de issues fechadas no merge final, embora a RQ06 calcule esse campo antes
da unificacao. Quando ``rq06_issues_fechadas`` nao existe, este modulo registra
uma estimativa inteira por ``round(total_issues * razao)`` e marca a origem em
``origem_issues_fechadas``. A correlacao continua usando a razao ja consolidada
da RQ06, sem recoletar dados.
"""

from __future__ import annotations

import math
import statistics
from typing import Iterable, Optional


CAMPO_NOME = "nome_completo"
CAMPO_IDADE = "rq01_idade_anos"
CAMPO_TOTAL_ISSUES = "rq06_issues_total"
CAMPO_ISSUES_FECHADAS = "rq06_issues_fechadas"
CAMPO_RAZAO = "rq06_razao_fechadas_total"

STATUS_OK = "ok"
STATUS_SEM_ISSUES = "sem_issues"
STATUS_IDADE_AUSENTE = "idade_ausente"
STATUS_TOTAL_ISSUES_INVALIDO = "total_issues_invalido"
STATUS_PERCENTUAL_AUSENTE = "percentual_ausente"
STATUS_PERCENTUAL_INVALIDO = "percentual_invalido"

ORIGEM_COLETADA = "coletada"
ORIGEM_ESTIMADA = "estimada_a_partir_da_razao_rq06"
ORIGEM_NAO_APLICAVEL = "nao_aplicavel"

FAIXAS_IDADE = (
    (0.0, 2.0, "Ate 2 anos"),
    (2.0, 5.0, "2 a 5 anos"),
    (5.0, 10.0, "5 a 10 anos"),
    (10.0, None, "Mais de 10 anos"),
)


def _numero(valor) -> bool:
    return (
        isinstance(valor, (int, float))
        and not isinstance(valor, bool)
        and math.isfinite(float(valor))
    )


def _inteiro_nao_negativo(valor) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool) and valor >= 0


def estimar_issues_fechadas(total_issues, razao, valor_coletado=None) -> tuple[Optional[int], str]:
    """Obtem a quantidade de issues fechadas sem fazer nova coleta.

    Preferimos o valor coletado, quando existir. No snapshot unificado atual ele
    nao foi preservado; nesse caso, usamos a razao arredondada da RQ06 para obter
    uma estimativa inteira e deixamos a origem explicita.
    """
    if _inteiro_nao_negativo(valor_coletado):
        return int(valor_coletado), ORIGEM_COLETADA
    if _inteiro_nao_negativo(total_issues) and total_issues > 0 and _numero(razao):
        estimada = int(round(total_issues * float(razao)))
        estimada = max(0, min(int(total_issues), estimada))
        return estimada, ORIGEM_ESTIMADA
    return None, ORIGEM_NAO_APLICAVEL


def montar_registro(registro: dict) -> dict:
    """Normaliza um repositorio para a RQ17, mantendo o motivo de descarte."""
    registro = registro or {}
    nome = registro.get(CAMPO_NOME)
    idade = registro.get(CAMPO_IDADE)
    total_issues = registro.get(CAMPO_TOTAL_ISSUES)
    razao = registro.get(CAMPO_RAZAO)
    issues_fechadas, origem = estimar_issues_fechadas(
        total_issues,
        razao,
        registro.get(CAMPO_ISSUES_FECHADAS),
    )

    if not _numero(idade):
        status = STATUS_IDADE_AUSENTE
    elif not _inteiro_nao_negativo(total_issues):
        status = STATUS_TOTAL_ISSUES_INVALIDO
    elif total_issues == 0:
        status = STATUS_SEM_ISSUES
    elif razao is None:
        status = STATUS_PERCENTUAL_AUSENTE
    elif not _numero(razao) or not 0.0 <= float(razao) <= 1.0:
        status = STATUS_PERCENTUAL_INVALIDO
    else:
        status = STATUS_OK

    percentual = None
    if _numero(razao) and 0.0 <= float(razao) <= 1.0:
        percentual = round(float(razao) * 100.0, 2)

    return {
        "nome_repositorio": nome,
        "idade_anos": round(float(idade), 2) if _numero(idade) else None,
        "total_issues": int(total_issues) if _inteiro_nao_negativo(total_issues) else None,
        "issues_fechadas": issues_fechadas,
        "origem_issues_fechadas": origem,
        "percentual_issues_fechadas": percentual,
        "razao_issues_fechadas": round(float(razao), 4) if percentual is not None else None,
        "status_rq17": status,
        "analisado": status == STATUS_OK,
    }


def preparar_registros(registros: Iterable[dict]) -> list[dict]:
    """Converte todos os repositorios do snapshot para linhas auditaveis da RQ17."""
    return [montar_registro(registro) for registro in registros]


def registros_validos(registros_rq17: Iterable[dict]) -> list[dict]:
    return [registro for registro in registros_rq17 if registro.get("status_rq17") == STATUS_OK]


def _quartis(valores: list[float]) -> tuple[Optional[float], Optional[float], Optional[float]]:
    if not valores:
        return None, None, None
    if len(valores) == 1:
        return valores[0], valores[0], valores[0]
    q1, mediana, q3 = statistics.quantiles(valores, n=4, method="inclusive")
    return q1, mediana, q3


def resumir_distribuicao(valores: list[float], casas: int = 4) -> dict:
    """Resumo descritivo usado para idade e percentual."""
    if not valores:
        return {
            "quantidade": 0,
            "media": None,
            "mediana": None,
            "minimo": None,
            "q1": None,
            "q3": None,
            "maximo": None,
            "desvio_padrao_populacional": None,
        }
    q1, mediana, q3 = _quartis(valores)
    return {
        "quantidade": len(valores),
        "media": round(statistics.fmean(valores), casas),
        "mediana": round(mediana, casas),
        "minimo": round(min(valores), casas),
        "q1": round(q1, casas),
        "q3": round(q3, casas),
        "maximo": round(max(valores), casas),
        "desvio_padrao_populacional": round(statistics.pstdev(valores), casas) if len(valores) > 1 else 0.0,
    }


def calcular_correlacao_pearson(xs: list[float], ys: list[float]) -> Optional[float]:
    """Coeficiente de Pearson para relacao linear entre idade e percentual."""
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    desvio_x = statistics.pstdev(xs)
    desvio_y = statistics.pstdev(ys)
    if desvio_x == 0 or desvio_y == 0:
        return None
    media_x = statistics.fmean(xs)
    media_y = statistics.fmean(ys)
    covariancia = sum((x - media_x) * (y - media_y) for x, y in zip(xs, ys)) / len(xs)
    return round(covariancia / (desvio_x * desvio_y), 4)


def _ranks(valores: list[float]) -> list[float]:
    """Ranks com media para empates, suficientes para Spearman sem scipy."""
    ordenados = sorted(enumerate(valores), key=lambda item: item[1])
    ranks = [0.0] * len(valores)
    indice = 0
    while indice < len(ordenados):
        proximo = indice + 1
        while proximo < len(ordenados) and ordenados[proximo][1] == ordenados[indice][1]:
            proximo += 1
        rank_medio = (indice + 1 + proximo) / 2.0
        for posicao in range(indice, proximo):
            ranks[ordenados[posicao][0]] = rank_medio
        indice = proximo
    return ranks


def calcular_correlacao_spearman(xs: list[float], ys: list[float]) -> Optional[float]:
    """Correlacao de Spearman para tendencia monotonica, robusta a escala."""
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    return calcular_correlacao_pearson(_ranks(xs), _ranks(ys))


def regressao_linear(xs: list[float], ys: list[float]) -> dict:
    """Ajuste linear simples para resumir a tendencia da RQ17."""
    if len(xs) != len(ys) or len(xs) < 2:
        return {"inclinacao_por_ano": None, "intercepto": None}
    media_x = statistics.fmean(xs)
    media_y = statistics.fmean(ys)
    soma_x = sum((x - media_x) ** 2 for x in xs)
    if soma_x == 0:
        return {"inclinação_por_ano": None, "intercepto": None}
    inclinacao = sum((x - media_x) * (y - media_y) for x, y in zip(xs, ys)) / soma_x
    intercepto = media_y - inclinacao * media_x
    return {
        "inclinacao_por_ano": round(inclinacao, 6),
        "intercepto": round(intercepto, 6),
        "variacao_pontos_percentuais_por_ano": round(inclinacao, 4),
    }


def _limites_iqr(valores: list[float]) -> tuple[Optional[float], Optional[float]]:
    if len(valores) < 4:
        return None, None
    q1, _, q3 = _quartis(valores)
    iqr = q3 - q1
    return q1 - 1.5 * iqr, q3 + 1.5 * iqr


def detectar_outliers(validos: list[dict], limite_amostra: int = 10) -> dict:
    """Identifica outliers por IQR em idade e percentual."""
    idades = [registro["idade_anos"] for registro in validos]
    percentuais = [registro["percentual_issues_fechadas"] for registro in validos]
    idade_min, idade_max = _limites_iqr(idades)
    percentual_min, percentual_max = _limites_iqr(percentuais)

    outliers = []
    for registro in validos:
        motivos = []
        if idade_min is not None and (registro["idade_anos"] < idade_min or registro["idade_anos"] > idade_max):
            motivos.append("idade")
        if percentual_min is not None and (
            registro["percentual_issues_fechadas"] < percentual_min
            or registro["percentual_issues_fechadas"] > percentual_max
        ):
            motivos.append("percentual_issues_fechadas")
        if motivos:
            item = dict(registro)
            item["motivos_outlier"] = motivos
            outliers.append(item)

    outliers_ordenados = sorted(
        outliers,
        key=lambda item: (item["percentual_issues_fechadas"], -item["idade_anos"], item["nome_repositorio"] or ""),
    )
    return {
        "metodo": "IQR (1,5 vezes o intervalo interquartil)",
        "limites_idade_anos": {
            "inferior": round(idade_min, 4) if idade_min is not None else None,
            "superior": round(idade_max, 4) if idade_max is not None else None,
        },
        "limites_percentual_issues_fechadas": {
            "inferior": round(percentual_min, 4) if percentual_min is not None else None,
            "superior": round(percentual_max, 4) if percentual_max is not None else None,
        },
        "quantidade": len(outliers),
        "amostra": outliers_ordenados[:limite_amostra],
    }


def _faixa_de_idade(idade: float) -> str:
    for minimo, maximo, rotulo in FAIXAS_IDADE:
        if idade >= minimo and (maximo is None or idade < maximo):
            return rotulo
    return FAIXAS_IDADE[-1][2]


def agrupar_por_faixa_de_idade(validos: list[dict]) -> dict:
    grupos = {rotulo: [] for _, _, rotulo in FAIXAS_IDADE}
    for registro in validos:
        grupos[_faixa_de_idade(registro["idade_anos"])].append(registro["percentual_issues_fechadas"])

    resultado = {}
    for _, _, rotulo in FAIXAS_IDADE:
        valores = grupos[rotulo]
        resultado[rotulo] = {
            "quantidade_repositorios": len(valores),
            "media_percentual": round(statistics.fmean(valores), 2) if valores else None,
            "mediana_percentual": round(statistics.median(valores), 2) if valores else None,
        }
    return resultado


def contar_status(registros_rq17: Iterable[dict]) -> dict:
    contagem = {}
    for registro in registros_rq17:
        status = registro.get("status_rq17", "desconhecido")
        contagem[status] = contagem.get(status, 0) + 1
    return contagem


def classificar_forca(coeficiente: Optional[float]) -> str:
    if coeficiente is None:
        return "indeterminada"
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
    sinal = "positiva" if coeficiente > 0 else "negativa" if coeficiente < 0 else "nula"
    return "%s %s" % (forca, sinal)


def classificar_hipotese(coeficiente_spearman: Optional[float]) -> str:
    """Classifica a hipotese usando a tendencia monotonica como referencia."""
    if coeficiente_spearman is None:
        return "inconclusiva"
    if coeficiente_spearman >= 0.4:
        return "confirmada"
    if coeficiente_spearman >= 0.2:
        return "parcialmente confirmada"
    return "refutada"


def gerar_conclusao(resumo: dict) -> str:
    coeficiente = resumo["correlacao"]["spearman"]
    classificacao = resumo["hipotese"]
    forca = resumo["correlacao"]["interpretacao_spearman"]
    if classificacao == "confirmada":
        return (
            "Os dados indicam uma tendencia positiva clara: repositorios mais antigos "
            "tendem a apresentar maior percentual de issues fechadas."
        )
    if classificacao == "parcialmente confirmada":
        return (
            "Os dados indicam apenas uma tendencia positiva fraca: repositorios mais "
            "antigos tendem levemente a apresentar maior percentual de issues fechadas, "
            "mas a idade nao explica sozinha a variacao observada."
        )
    if classificacao == "refutada":
        return (
            "Os dados nao sustentam a hipotese de que repositorios mais antigos tenham "
            "maior percentual de issues fechadas."
        )
    return "A hipotese ficou inconclusiva por falta de pares validos ou variancia nas metricas (%s)." % coeficiente


def analisar(registros: Iterable[dict]) -> dict:
    """Executa a RQ17 completa sobre os repositorios consolidados."""
    linhas = preparar_registros(registros)
    validos = registros_validos(linhas)
    idades = [registro["idade_anos"] for registro in validos]
    percentuais = [registro["percentual_issues_fechadas"] for registro in validos]

    pearson = calcular_correlacao_pearson(idades, percentuais)
    spearman = calcular_correlacao_spearman(idades, percentuais)

    resumo = {
        "questao": "RQ17 - Repositorios mais antigos tendem a apresentar maior percentual de issues fechadas?",
        "fonte_dados": "dados/lab01s01_unificado.json",
        "metrica_percentual": "issues_fechadas / total_de_issues, reutilizando rq06_razao_fechadas_total",
        "total_repositorios": len(linhas),
        "repositorios_analisados": len(validos),
        "registros_descartados_ou_ausentes": len(linhas) - len(validos),
        "por_status": contar_status(linhas),
        "issues_fechadas_estimadas": sum(
            1 for registro in validos if registro.get("origem_issues_fechadas") == ORIGEM_ESTIMADA
        ),
        "observacao_issues_fechadas": (
            "O snapshot unificado atual nao preserva rq06_issues_fechadas; a quantidade "
            "foi estimada por round(total_issues * rq06_razao_fechadas_total). A analise "
            "usa a razao ja consolidada da RQ06."
        ),
        "distribuicao_idade_anos": resumir_distribuicao(idades, casas=2),
        "distribuicao_percentual_issues_fechadas": resumir_distribuicao(percentuais, casas=2),
        "correlacao": {
            "pearson": pearson,
            "metodo_pearson": "correlacao linear entre idade_anos e percentual_issues_fechadas",
            "interpretacao_pearson": classificar_forca(pearson),
            "spearman": spearman,
            "metodo_spearman": "correlacao de postos para tendencia monotonica, com rank medio em empates",
            "interpretacao_spearman": classificar_forca(spearman),
        },
        "regressao_linear": regressao_linear(idades, percentuais),
        "outliers": detectar_outliers(validos),
        "por_faixa_de_idade": agrupar_por_faixa_de_idade(validos),
        "hipotese": classificar_hipotese(spearman),
    }
    resumo["conclusao"] = gerar_conclusao(resumo)

    return {
        "resumo": resumo,
        "registros": linhas,
        "registros_analisados": validos,
    }
