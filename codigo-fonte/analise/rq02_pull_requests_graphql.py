"""RQ02 - Sistemas populares recebem muita contribuicao externa?

Metrica: total de pull requests aceitas (mergeadas), a partir de
``pullRequestsAceitos.totalCount`` -- ``pullRequests(states: MERGED)`` na
consulta GraphQL (fragmento ``CAMPOS_RQ07`` de ``consulta.py``, reaproveitado
aqui porque a RQ07 tambem precisa desse mesmo dado agrupado por linguagem).

Versao GraphQL da RQ02, usada pelo script unico do grupo. Ja existe uma versao
independente em REST (``rq02_total_pr_aceitos.py``); este modulo tem nome
proprio para nao sobrescreve-la e fornece o resumo geral (media, mediana,
minimo, maximo sobre os 100 repositorios), que a RQ07 nao calcula -- ela so
agrupa por linguagem.

Segue o mesmo padrao da RQ06 (``rq06_issues.py``): distingue repositorio que
nao teve o campo solicitado na consulta (status ``dados_ausentes``) de
repositorio que de fato tem zero pull requests aceitas (status ``ok``, valor
``0``).
"""

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
    """Calcula a RQ02 para um repositorio."""
    total = _total(no, "pullRequestsAceitos")

    if total is None:
        return {
            "rq02_pull_requests_aceitos_graphql": None,
            "rq02_status_graphql": "dados_ausentes",
        }

    return {
        "rq02_pull_requests_aceitos_graphql": total,
        "rq02_status_graphql": "ok",
    }


def definicao() -> dict:
    """Definicao da metrica, gravada nos metadados da coleta."""
    return {
        "questao": "RQ02 - Sistemas populares recebem muita contribuicao externa?",
        "metrica": "Total de pull requests aceitas (mergeadas)",
        "campo_utilizado": "pullRequestsAceitos.totalCount (pullRequests com states: MERGED)",
        "tratamento_de_ausentes": (
            "Quando o campo nao foi solicitado na consulta, o status fica 'dados_ausentes' "
            "e a metrica None; nunca zero por omissao."
        ),
    }


def resumir(registros: Iterable[dict]) -> dict:
    """Agrega a RQ02 sobre a coleta inteira."""
    registros = list(registros)
    valores = [
        r["rq02_pull_requests_aceitos_graphql"]
        for r in registros
        if isinstance(r.get("rq02_pull_requests_aceitos_graphql"), int)
    ]

    contagem_status = {}
    for r in registros:
        chave = r.get("rq02_status_graphql", "desconhecido")
        contagem_status[chave] = contagem_status.get(chave, 0) + 1

    return {
        "total_repositorios": len(registros),
        "com_metrica": len(valores),
        "sem_metrica": len(registros) - len(valores),
        "por_status": contagem_status,
        "media": round(statistics.fmean(valores), 4) if valores else None,
        "mediana": round(statistics.median(valores), 4) if valores else None,
        "minimo": min(valores) if valores else None,
        "maximo": max(valores) if valores else None,
    }
