"""Calcula a razao entre issues fechadas e total de issues da RQ06."""

from __future__ import annotations

import statistics
from typing import Iterable, Optional


def _total(no: dict, campo: str) -> Optional[int]:
    no = no or {}
    if campo not in no:
        return None
    conexao = no.get(campo) or {}
    valor = conexao.get("totalCount", 0)
    return valor if isinstance(valor, int) else 0


def calcular(no: dict) -> dict:
    """Calcula a RQ06 para um repositorio."""
    total_issues = _total(no, "issues")
    issues_fechadas = _total(no, "issuesFechadas")

    if total_issues is None or issues_fechadas is None:
        return {
            "rq06_issues_total": None,
            "rq06_issues_fechadas": None,
            "rq06_razao_fechadas_total": None,
            "rq06_status": "dados_ausentes",
        }

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
        "tratamento_de_ausentes": (
            "Quando issues.totalCount = 0, a razao fica None. Quando os campos nao "
            "foram coletados, o status fica dados_ausentes."
        ),
    }


def resumir(registros: Iterable[dict]) -> dict:
    registros = list(registros)
    valores = [
        r["rq06_razao_fechadas_total"]
        for r in registros
        if r.get("rq06_razao_fechadas_total") is not None
        and not (
            isinstance(r.get("bruto"), dict)
            and ("issues" not in r["bruto"] or "issuesFechadas" not in r["bruto"])
        )
    ]

    por_status = {}
    for registro in registros:
        bruto = registro.get("bruto")
        if isinstance(bruto, dict) and ("issues" not in bruto or "issuesFechadas" not in bruto):
            status = "dados_ausentes"
        else:
            status = registro.get("rq06_status", "desconhecido")
        por_status[status] = por_status.get(status, 0) + 1

    return {
        "total_repositorios": len(registros),
        "com_issues": len(valores),
        "sem_issues": por_status.get("sem_issues", 0),
        "dados_ausentes": por_status.get("dados_ausentes", 0),
        "por_status": por_status,
        "media_razao": round(statistics.fmean(valores), 4) if valores else None,
        "mediana_razao": round(statistics.median(valores), 4) if valores else None,
        "minimo_razao": min(valores) if valores else None,
        "maximo_razao": max(valores) if valores else None,
    }
