"""RQ06 - Razao entre issues fechadas e total de issues."""

from __future__ import annotations

import statistics
from typing import Iterable


def _total(no: dict, campo: str) -> int:
    conexao = (no or {}).get(campo) or {}
    valor = conexao.get("totalCount", 0)
    return valor if isinstance(valor, int) else 0


def calcular(no: dict) -> dict:
    """Calcula a RQ06 para um repositorio."""
    total_issues = _total(no, "issues")
    issues_fechadas = _total(no, "issuesFechadas")

    razao = None
    if total_issues > 0:
        razao = round(issues_fechadas / total_issues, 4)

    return {
        "rq06_issues_total": total_issues,
        "rq06_issues_fechadas": issues_fechadas,
        "rq06_razao_fechadas_total": razao,
        "rq06_status": "sem_issues" if total_issues == 0 else "ok",
    }


def definicao() -> dict:
    return {
        "questao": "RQ06 - Qual a razao entre issues fechadas e total de issues?",
        "metrica": "Razao entre issues fechadas e total de issues",
        "campos_utilizados": ["issues.totalCount", "issuesFechadas.totalCount"],
        "formula": "issuesFechadas.totalCount / issues.totalCount",
        "tratamento_de_ausentes": "Quando issues.totalCount = 0, a razao fica None.",
    }


def resumir(registros: Iterable[dict]) -> dict:
    registros = list(registros)
    valores = [
        r["rq06_razao_fechadas_total"]
        for r in registros
        if r.get("rq06_razao_fechadas_total") is not None
    ]

    return {
        "total_repositorios": len(registros),
        "com_issues": len(valores),
        "sem_issues": len(registros) - len(valores),
        "media_razao": round(statistics.fmean(valores), 4) if valores else None,
        "mediana_razao": round(statistics.median(valores), 4) if valores else None,
        "minimo_razao": min(valores) if valores else None,
        "maximo_razao": max(valores) if valores else None,
    }
