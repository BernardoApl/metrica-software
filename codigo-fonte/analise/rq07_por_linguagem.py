"""RQ07 - Divisao de RQ02, RQ03 e RQ04 por linguagem primaria.

Modulo inicial, preparado para usar os campos ja produzidos pelos colegas:

- ``rq02_pull_requests_aceitos``
- ``rq03_total_releases``
- ``rq04_dias_desde_ultima_atualizacao``
- ``rq05_categoria_linguagem`` ou ``rq05_linguagem_primaria``
"""

from __future__ import annotations

import statistics
from typing import Iterable


SEM_LINGUAGEM = "Sem linguagem definida"


def _linguagem(registro: dict) -> str:
    return (
        registro.get("rq05_categoria_linguagem")
        or registro.get("rq05_linguagem_primaria")
        or SEM_LINGUAGEM
    )


def _valores(registros: list[dict], campo: str) -> list[float]:
    return [
        r[campo]
        for r in registros
        if isinstance(r.get(campo), (int, float))
    ]


def _estatisticas(registros: list[dict], campo: str) -> dict:
    valores = _valores(registros, campo)
    if not valores:
        return {"media": None, "mediana": None, "minimo": None, "maximo": None}

    return {
        "media": round(statistics.fmean(valores), 4),
        "mediana": round(statistics.median(valores), 4),
        "minimo": min(valores),
        "maximo": max(valores),
    }


def resumir(registros: Iterable[dict]) -> dict:
    """Agrupa os resultados de RQ02, RQ03 e RQ04 por linguagem primaria."""
    grupos = {}
    for registro in registros:
        grupos.setdefault(_linguagem(registro), []).append(registro)

    resultado = {}
    for linguagem, itens in sorted(grupos.items(), key=lambda item: item[0].casefold()):
        resultado[linguagem] = {
            "quantidade_repositorios": len(itens),
            "rq02_pull_requests_aceitos": _estatisticas(itens, "rq02_pull_requests_aceitos"),
            "rq03_total_releases": _estatisticas(itens, "rq03_total_releases"),
            "rq04_dias_desde_ultima_atualizacao": _estatisticas(
                itens,
                "rq04_dias_desde_ultima_atualizacao",
            ),
        }

    return resultado


def definicao() -> dict:
    return {
        "questao": "RQ07 - Dividir os resultados de RQ02, RQ03 e RQ04 por linguagem.",
        "chave_de_agrupamento": "rq05_categoria_linguagem",
        "metricas_agrupadas": [
            "rq02_pull_requests_aceitos",
            "rq03_total_releases",
            "rq04_dias_desde_ultima_atualizacao",
        ],
        "observacao": (
            "Este modulo depende dos campos calculados pelas RQs 02, 03, 04 e 05. "
            "A integracao final deve ocorrer depois que esses commits estiverem no projeto."
        ),
    }
