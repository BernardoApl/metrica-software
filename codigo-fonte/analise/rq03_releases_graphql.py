"""RQ03 - Sistemas populares lancam releases com frequencia?

Metrica: total de releases, a partir de ``releases.totalCount`` na consulta
GraphQL (fragmento ``CAMPOS_RQ07`` de ``consulta.py``, reaproveitado aqui
porque a RQ07 tambem precisa desse mesmo dado agrupado por linguagem).

Versao GraphQL da RQ03, usada pelo script unico do grupo. Ja existe uma versao
independente em REST (``rq03_total_de_releases.py``); este modulo tem nome
proprio para nao sobrescreve-la e fornece o resumo geral (media, mediana,
minimo, maximo sobre os 100 repositorios), que a RQ07 nao calcula -- ela so
agrupa por linguagem.

Segue o mesmo padrao da RQ06/RQ02: distingue repositorio que nao teve o campo
solicitado na consulta (status ``dados_ausentes``) de repositorio que de fato
nao tem releases (status ``ok``, valor ``0``).

ATENCAO -- limitacao observada no ``releases.totalCount`` do GraphQL: para
repositorios com muitos releases ele nao e confiavel. Numa coleta real de 100
repositorios, 3 vieram travados em exatamente 1000 (quando o valor real, via
REST paginado, era 6843, 3799 e 1979) e 1 veio zerado (valor real 1636). Por
isso este valor deve ser tratado como comparativo, nunca como fonte principal
-- ``rq03_total_de_releases.py`` (REST, paginando ``/repos/{owner}/{repo}/releases``
por completo) e a fonte confiavel, e e ela que o script unificado usa.
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
    """Calcula a RQ03 para um repositorio."""
    total = _total(no, "releases")

    if total is None:
        return {
            "rq03_total_releases_graphql": None,
            "rq03_status_graphql": "dados_ausentes",
        }

    return {
        "rq03_total_releases_graphql": total,
        "rq03_status_graphql": "ok",
    }


def definicao() -> dict:
    """Definicao da metrica, gravada nos metadados da coleta."""
    return {
        "questao": "RQ03 - Sistemas populares lancam releases com frequencia?",
        "metrica": "Total de releases",
        "campo_utilizado": "releases.totalCount",
        "tratamento_de_ausentes": (
            "Quando o campo nao foi solicitado na consulta, o status fica 'dados_ausentes' "
            "e a metrica None; nunca zero por omissao."
        ),
    }


def resumir(registros: Iterable[dict]) -> dict:
    """Agrega a RQ03 sobre a coleta inteira."""
    registros = list(registros)
    valores = [
        r["rq03_total_releases_graphql"]
        for r in registros
        if isinstance(r.get("rq03_total_releases_graphql"), int)
    ]

    contagem_status = {}
    for r in registros:
        chave = r.get("rq03_status_graphql", "desconhecido")
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
