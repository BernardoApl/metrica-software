"""RQ04 - Sistemas populares sao atualizados com frequencia?

Metrica: tempo ate a ultima atualizacao.

Definicao operacional
---------------------
O enunciado nao diz qual campo da API representa "a ultima atualizacao", e a API
do GitHub oferece tres candidatos com semanticas diferentes:

===============================================  ========================================
Campo                                            O que realmente marca
===============================================  ========================================
``updatedAt``                                    Qualquer alteracao no registro do
                                                 repositorio, inclusive metadados
                                                 (descricao, topics, settings).
``pushedAt``                                     Ultimo push de codigo, em qualquer branch.
``defaultBranchRef.target.committedDate``        Data do ultimo commit no branch padrao.
===============================================  ========================================

**Campo oficial adotado: ``pushedAt``.** A RQ04 pergunta se o sistema e
*atualizado com frequencia*, ou seja, se ha atividade de desenvolvimento.
``updatedAt`` e inflado por eventos que nao sao desenvolvimento (editar a
descricao ja o atualiza), o que faria repositorios inativos parecerem ativos.
``committedDate`` do branch padrao ignora atividade em branches de trabalho e e
nulo em repositorios sem branch padrao. ``pushedAt`` e o campo que captura
atividade de codigo sem depender de um unico branch.

Os outros dois campos sao coletados assim mesmo e devolvidos como comparativos,
para que a escolha possa ser justificada com dados no relatorio final. Eles nao
entram no calculo.

- **Data de referencia:** o instante da coleta (``coletado_em``), em UTC,
  capturado uma unica vez no inicio da execucao e aplicado a todos os
  repositorios. E gravado na saida, de modo que o resultado seja reproduzivel e
  auditavel depois. Nos testes a referencia e injetada para dar determinismo.
- **Formula:** ``(referencia - pushedAt) / 86400``
- **Unidade:** dias (numero real, 2 casas decimais). Como os repositorios do topo
  costumam ter push nas ultimas horas, o resultado tambem e exposto em horas.
- **Valores ausentes:** ``pushedAt`` nulo (repositorio vazio, nunca recebeu push)
  produz metrica ``None`` com status ``sem_push``; o repositorio permanece no
  conjunto de dados, mas fica de fora das agregacoes. Data no futuro (defasagem
  de relogio) e limitada a ``0.0`` com status ``data_futura``.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Iterable, Optional

#: Campo da API do GitHub adotado como definicao oficial da metrica.
CAMPO_OFICIAL = "pushedAt"

#: Campos coletados apenas para comparacao no relatorio; fora do calculo.
CAMPOS_COMPARATIVOS = ("updatedAt", "defaultBranchRef.target.committedDate")

SEGUNDOS_POR_DIA = 86400.0

STATUS_OK = "ok"
STATUS_SEM_PUSH = "sem_push"
STATUS_DATA_INVALIDA = "data_invalida"
STATUS_DATA_FUTURA = "data_futura"


def agora_utc() -> datetime:
    """Instante atual em UTC, usado como data de referencia padrao."""
    return datetime.now(timezone.utc)


def analisar_iso8601(valor: Optional[str]) -> Optional[datetime]:
    """Converte um timestamp ISO 8601 da API do GitHub em ``datetime`` com fuso.

    A API devolve o formato ``2026-08-11T14:03:52Z``. O sufixo ``Z`` e traduzido
    para ``+00:00`` explicitamente, para funcionar tambem em versoes de Python
    anteriores a 3.11.

    :return: ``None`` se o valor for nulo, vazio ou nao interpretavel.
    """
    if not valor or not isinstance(valor, str):
        return None
    texto = valor.strip()
    if texto.endswith("Z"):
        texto = texto[:-1] + "+00:00"
    try:
        momento = datetime.fromisoformat(texto)
    except ValueError:
        return None
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(timezone.utc)


def _committed_date(no: dict) -> Optional[str]:
    """Extrai ``defaultBranchRef.target.committedDate`` tolerando nulos no caminho."""
    ref = (no or {}).get("defaultBranchRef") or {}
    alvo = ref.get("target") or {}
    return alvo.get("committedDate")


def calcular(no: dict, referencia: datetime) -> dict:
    """Calcula a RQ04 para um repositorio.

    :param no: no ``Repository`` cru, como devolvido pela consulta GraphQL.
    :param referencia: data de referencia em UTC, a mesma para toda a coleta.
    :return: dicionario com as chaves ``rq04_*``, pronto para ser fundido com as
        metricas dos demais integrantes.
    """
    if referencia.tzinfo is None:
        referencia = referencia.replace(tzinfo=timezone.utc)
    referencia = referencia.astimezone(timezone.utc)

    no = no or {}
    bruto = no.get(CAMPO_OFICIAL)
    momento = analisar_iso8601(bruto)

    if bruto is None:
        status, dias, horas = STATUS_SEM_PUSH, None, None
    elif momento is None:
        status, dias, horas = STATUS_DATA_INVALIDA, None, None
    else:
        segundos = (referencia - momento).total_seconds()
        if segundos < 0:
            # Defasagem de relogio entre o GitHub e a maquina da coleta.
            status, dias, horas = STATUS_DATA_FUTURA, 0.0, 0.0
        else:
            status = STATUS_OK
            dias = round(segundos / SEGUNDOS_POR_DIA, 2)
            horas = round(segundos / 3600.0, 2)

    return {
        "rq04_campo_utilizado": CAMPO_OFICIAL,
        "rq04_data_referencia": referencia.isoformat(),
        "rq04_data_ultima_atualizacao": bruto,
        "rq04_dias_desde_ultima_atualizacao": dias,
        "rq04_horas_desde_ultima_atualizacao": horas,
        "rq04_status": status,
        # Comparativos: nao entram no calculo, existem para justificar a escolha
        # do campo oficial no relatorio final.
        "rq04_comparativo_updated_at": no.get("updatedAt"),
        "rq04_comparativo_ultimo_commit_branch_padrao": _committed_date(no),
    }


def definicao() -> dict:
    """Definicao da metrica, gravada nos metadados da coleta."""
    return {
        "questao": "RQ04 - Sistemas populares sao atualizados com frequencia?",
        "metrica": "Tempo ate a ultima atualizacao",
        "campo_utilizado": CAMPO_OFICIAL,
        "campos_comparativos": list(CAMPOS_COMPARATIVOS),
        "justificativa_do_campo": (
            "pushedAt marca o ultimo push de codigo em qualquer branch. updatedAt tambem "
            "muda por alteracoes de metadados (descricao, topics, settings), o que faria "
            "repositorios inativos parecerem ativos; committedDate do branch padrao ignora "
            "atividade em outros branches e e nulo quando nao ha branch padrao."
        ),
        "data_referencia": "Instante da coleta em UTC, unico para todos os repositorios.",
        "formula": "(data_referencia - pushedAt) / 86400",
        "unidade": "dias (numero real, 2 casas decimais)",
        "tratamento_de_ausentes": (
            "pushedAt nulo -> metrica None, status 'sem_push', repositorio mantido no "
            "conjunto de dados mas excluido das agregacoes. Data nao interpretavel -> "
            "status 'data_invalida'. Data no futuro -> limitada a 0.0, status 'data_futura'."
        ),
    }


def resumir(registros: Iterable[dict]) -> dict:
    """Agrega a RQ04 sobre a coleta inteira.

    Valores ausentes sao contados a parte e nao entram nas estatisticas, para nao
    contaminar a mediana usada no relatorio.
    """
    registros = list(registros)
    valores = [
        r["rq04_dias_desde_ultima_atualizacao"]
        for r in registros
        if r.get("rq04_dias_desde_ultima_atualizacao") is not None
    ]

    contagem_status = {}
    for r in registros:
        chave = r.get("rq04_status", "desconhecido")
        contagem_status[chave] = contagem_status.get(chave, 0) + 1

    resumo = {
        "total_repositorios": len(registros),
        "com_metrica": len(valores),
        "sem_metrica": len(registros) - len(valores),
        "por_status": contagem_status,
        "mediana_dias": None,
        "media_dias": None,
        "minimo_dias": None,
        "maximo_dias": None,
    }
    if valores:
        resumo["mediana_dias"] = round(statistics.median(valores), 2)
        resumo["media_dias"] = round(statistics.fmean(valores), 2)
        resumo["minimo_dias"] = min(valores)
        resumo["maximo_dias"] = max(valores)
    return resumo
