"""RQ01 - Sistemas populares sao maduros/antigos?

Metrica: idade do repositorio, calculada a partir de ``createdAt``.

Versao GraphQL da RQ01, usada pelo script unico do grupo (``coleta_repositorios.py``).
Ja existe uma versao independente em REST (``rq01_idade.py``, do integrante
responsavel pela RQ01); este modulo tem nome proprio para nao sobrescreve-la e
serve como fonte de comparacao dentro da mesma consulta que ja traz RQ04-RQ07.

Segue o mesmo padrao operacional da RQ04 (``rq04_atualizacao.py``): uma unica
data de referencia em UTC, capturada no inicio da coleta e aplicada a todos os
repositorios, para que o resultado seja reproduzivel e auditavel depois.

- **Formula:** ``(referencia - createdAt) / 86400`` (dias); tambem exposta em
  anos, dividindo por 365.25.
- **Valores ausentes:** ``createdAt`` nulo produz metrica ``None`` com status
  ``sem_data_criacao``; o repositorio permanece no conjunto de dados, mas fica
  de fora das agregacoes.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Iterable

from rq04_atualizacao import analisar_iso8601

#: Campo da API do GitHub adotado como definicao oficial da metrica.
CAMPO_OFICIAL = "createdAt"

DIAS_POR_ANO = 365.25
SEGUNDOS_POR_DIA = 86400.0

STATUS_OK = "ok"
STATUS_SEM_DATA = "sem_data_criacao"
STATUS_DATA_INVALIDA = "data_invalida"


def calcular(no: dict, referencia: datetime) -> dict:
    """Calcula a RQ01 para um repositorio.

    :param no: no ``Repository`` cru, como devolvido pela consulta GraphQL.
    :param referencia: data de referencia em UTC, a mesma para toda a coleta.
    :return: dicionario com as chaves ``rq01_*``, pronto para ser fundido com as
        metricas dos demais integrantes.
    """
    if referencia.tzinfo is None:
        referencia = referencia.replace(tzinfo=timezone.utc)
    referencia = referencia.astimezone(timezone.utc)

    no = no or {}
    bruto = no.get(CAMPO_OFICIAL)
    momento = analisar_iso8601(bruto)

    if bruto is None:
        status, dias, anos = STATUS_SEM_DATA, None, None
    elif momento is None:
        status, dias, anos = STATUS_DATA_INVALIDA, None, None
    else:
        dias_totais = (referencia - momento).total_seconds() / SEGUNDOS_POR_DIA
        status = STATUS_OK
        dias = round(dias_totais, 2)
        anos = round(dias_totais / DIAS_POR_ANO, 2)

    return {
        "rq01_campo_utilizado": CAMPO_OFICIAL,
        "rq01_data_criacao": bruto,
        "rq01_idade_dias": dias,
        "rq01_idade_anos": anos,
        "rq01_status": status,
    }


def definicao() -> dict:
    """Definicao da metrica, gravada nos metadados da coleta."""
    return {
        "questao": "RQ01 - Sistemas populares sao maduros/antigos?",
        "metrica": "Idade do repositorio (calculada a partir da data de criacao)",
        "campo_utilizado": CAMPO_OFICIAL,
        "data_referencia": "Instante da coleta em UTC, unico para todos os repositorios.",
        "formula": "(data_referencia - createdAt) / 86400, tambem exposta em anos (/365.25)",
        "unidade": "dias e anos (numero real, 2 casas decimais)",
        "tratamento_de_ausentes": (
            "createdAt nulo -> metrica None, status 'sem_data_criacao', repositorio mantido "
            "no conjunto de dados mas excluido das agregacoes. Data nao interpretavel -> "
            "status 'data_invalida'."
        ),
    }


def resumir(registros: Iterable[dict]) -> dict:
    """Agrega a RQ01 sobre a coleta inteira.

    Valores ausentes sao contados a parte e nao entram nas estatisticas, para nao
    contaminar a mediana usada no relatorio.
    """
    registros = list(registros)
    dias = [r["rq01_idade_dias"] for r in registros if r.get("rq01_idade_dias") is not None]
    anos = [r["rq01_idade_anos"] for r in registros if r.get("rq01_idade_anos") is not None]

    contagem_status = {}
    for r in registros:
        chave = r.get("rq01_status", "desconhecido")
        contagem_status[chave] = contagem_status.get(chave, 0) + 1

    resumo = {
        "total_repositorios": len(registros),
        "com_metrica": len(dias),
        "sem_metrica": len(registros) - len(dias),
        "por_status": contagem_status,
        "mediana_dias": None,
        "media_dias": None,
        "minimo_dias": None,
        "maximo_dias": None,
        "mediana_anos": None,
        "media_anos": None,
    }
    if dias:
        resumo["mediana_dias"] = round(statistics.median(dias), 2)
        resumo["media_dias"] = round(statistics.fmean(dias), 2)
        resumo["minimo_dias"] = min(dias)
        resumo["maximo_dias"] = max(dias)
    if anos:
        resumo["mediana_anos"] = round(statistics.median(anos), 2)
        resumo["media_anos"] = round(statistics.fmean(anos), 2)
    return resumo
