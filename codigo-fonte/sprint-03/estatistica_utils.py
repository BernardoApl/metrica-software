"""Utilitarios compartilhados pelos testes de Wilcoxon da Sprint 3 (RQ51/RQ52/RQ53).

Desenho within-subject: cada participante e seu proprio controle. Os pares do
Wilcoxon sao por participante (mediana dos katas com_ia vs mediana dos katas
sem_ia do mesmo participante), nao por kata - cada integrante resolve cada
kata uma unica vez, sob um so tratamento (ver RQ50).
"""

from __future__ import annotations

import csv
import statistics
from pathlib import Path

try:
    from scipy import stats as scipy_stats
except ImportError:  # scipy pode nao estar instalado em todo ambiente
    scipy_stats = None


def ler_csv(caminho: Path) -> list[dict]:
    caminho = Path(caminho)
    if not caminho.exists():
        return []
    with caminho.open(newline="", encoding="utf-8") as arquivo:
        return list(csv.DictReader(arquivo))


def texto(valor) -> str:
    return "" if valor is None else str(valor).strip()


def numero(valor):
    bruto = texto(valor)
    if bruto == "":
        return None
    try:
        return float(bruto)
    except ValueError:
        return None


def agregar_por_participante_tratamento(registros, campo_participante="participante",
                                          campo_tratamento="tratamento", extrair_valor=None,
                                          agregador=statistics.median):
    """Agrupa `registros` por (participante, tratamento) e agrega os valores extraidos.

    `extrair_valor(registro) -> float | None`; registros com valor None sao ignorados.
    Retorna dict: participante -> {tratamento: valor_agregado}.
    """
    brutos: dict[str, dict[str, list[float]]] = {}
    for registro in registros:
        participante = texto(registro.get(campo_participante))
        tratamento = texto(registro.get(campo_tratamento))
        valor = extrair_valor(registro)
        if not participante or not tratamento or valor is None:
            continue
        brutos.setdefault(participante, {}).setdefault(tratamento, []).append(valor)

    return {
        participante: {tratamento: agregador(lista) for tratamento, lista in por_tratamento.items()}
        for participante, por_tratamento in brutos.items()
    }


def construir_pares(agregados: dict, tratamento_a: str = "com_ia", tratamento_b: str = "sem_ia"):
    """Retorna (pares, incompletos).

    pares: list[(valor_tratamento_a, valor_tratamento_b, participante)] - so participantes com os dois
    tratamentos medidos.
    incompletos: list[dict] com o participante e o(s) tratamento(s) que faltam, para reportar no audit.
    """
    pares = []
    incompletos = []
    for participante, por_tratamento in agregados.items():
        if tratamento_a in por_tratamento and tratamento_b in por_tratamento:
            pares.append((por_tratamento[tratamento_a], por_tratamento[tratamento_b], participante))
        else:
            faltando = [t for t in (tratamento_a, tratamento_b) if t not in por_tratamento]
            incompletos.append({"participante": participante, "tratamentos_faltando": faltando})
    return pares, incompletos


def _ranks_por_diferenca_absoluta(diferencas: list[float]) -> list[float]:
    """Ranks medios (empates dividem o rank) das diferencas != 0, na ordem original."""
    indices_nao_zero = [i for i, d in enumerate(diferencas) if d != 0]
    ordenados = sorted(indices_nao_zero, key=lambda i: abs(diferencas[i]))
    ranks = [0.0] * len(diferencas)
    posicao = 0
    while posicao < len(ordenados):
        fim = posicao
        valor_absoluto = abs(diferencas[ordenados[posicao]])
        while fim + 1 < len(ordenados) and abs(diferencas[ordenados[fim + 1]]) == valor_absoluto:
            fim += 1
        rank_medio = (posicao + fim) / 2 + 1
        for k in range(posicao, fim + 1):
            ranks[ordenados[k]] = rank_medio
        posicao = fim + 1
    return ranks


def testar_wilcoxon_pareado(pares, minimo_pares_recomendado: int = 3) -> dict:
    """Wilcoxon signed-rank pareado (tratamento_a vs tratamento_b) + effect size rank-biserial.

    `pares`: list[(valor_a, valor_b, participante)], como retornado por `construir_pares`.
    Nao inventa resultado quando os dados nao permitem: com menos de 1 par completo, ou com todas
    as diferencas zero, marca `suficiente=False` em vez de forcar um p-valor.
    """
    if len(pares) < 1:
        return {"suficiente": False, "motivo": "nenhum par completo (mesmo participante nos dois tratamentos)",
                "n_pares": 0}

    diferencas = [a - b for a, b, _ in pares]
    if all(d == 0 for d in diferencas):
        return {"suficiente": False, "motivo": "todas as diferencas entre tratamentos sao zero",
                "n_pares": len(pares)}

    ranks = _ranks_por_diferenca_absoluta(diferencas)
    w_mais = sum(r for r, d in zip(ranks, diferencas) if d > 0)
    w_menos = sum(r for r, d in zip(ranks, diferencas) if d < 0)
    effect_size = (w_mais - w_menos) / (w_mais + w_menos) if (w_mais + w_menos) else 0.0

    resultado = {
        "suficiente": True,
        "n_pares": len(pares),
        "aviso_amostra_pequena": len(pares) < minimo_pares_recomendado,
        "mediana_a": statistics.median(a for a, _, _ in pares),
        "mediana_b": statistics.median(b for _, b, _ in pares),
        "w_mais": w_mais,
        "w_menos": w_menos,
        "effect_size_rank_biserial": effect_size,
        "estatistica": None,
        "p_valor": None,
    }

    if scipy_stats is None:
        resultado["aviso"] = "scipy nao instalado: p-valor nao calculado, so estatistica descritiva"
        return resultado

    try:
        estatistica, p_valor = scipy_stats.wilcoxon(
            [a for a, _, _ in pares], [b for _, b, _ in pares], zero_method="wilcox",
        )
        resultado["estatistica"] = float(estatistica)
        resultado["p_valor"] = float(p_valor)
    except ValueError as erro:
        resultado["aviso"] = "scipy nao conseguiu calcular p-valor: %s" % erro

    return resultado


def interpretar(resultado: dict, alfa: float = 0.05) -> str:
    if not resultado.get("suficiente"):
        return "Dados insuficientes: %s." % resultado.get("motivo", "motivo desconhecido")
    if resultado.get("p_valor") is None:
        return "Estatistica descritiva calculada, mas sem p-valor (%s)." % resultado.get("aviso", "scipy indisponivel")
    if resultado["p_valor"] < alfa:
        return "p-valor=%.4f < %.2f: rejeita H0 (ha diferenca entre os tratamentos)." % (resultado["p_valor"], alfa)
    return "p-valor=%.4f >= %.2f: nao rejeita H0 (sem evidencia de diferenca)." % (resultado["p_valor"], alfa)
