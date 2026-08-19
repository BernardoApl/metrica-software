"""Orquestracao da coleta dos repositorios mais populares do GitHub.

Fluxo: monta a consulta a partir dos fragmentos de campos -> envia pelo cliente
proprio -> normaliza cada no cru em um registro com as metricas calculadas.

A consulta combinada e pesada demais para buscar muitos repositorios de uma
vez. Por isso a coleta percorre o cursor GraphQL em paginas menores ate atingir
a quantidade solicitada, limitada aos 1000 resultados da Search API.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

import rq01_idade_graphql
import rq02_pull_requests_graphql
import rq03_releases_graphql
import rq04_atualizacao
import rq05_linguagem
import rq06_issues
import rq07_por_linguagem
import rq15_idade_issues_fechadas
from cliente_github import ClienteGitHub
from consulta import (
    BUSCA_PADRAO,
    CAMPOS_IDENTIFICACAO,
    CAMPOS_RQ01,
    CAMPOS_RQ04_RQ05,
    CAMPOS_RQ06_RQ07,
    LIMITE_POR_PAGINA,
    LIMITE_RESULTADOS_BUSCA,
    montar_consulta,
    montar_variaveis,
)
from linguagens_populares import ReferenciaLinguagens

#: Fragmentos que cobrem as sete RQs do grupo numa unica consulta GraphQL.
FRAGMENTOS_PADRAO = (CAMPOS_IDENTIFICACAO, CAMPOS_RQ01, CAMPOS_RQ04_RQ05, CAMPOS_RQ06_RQ07)

#: Tamanho de pagina seguro para a consulta combinada -- o mesmo que a RQ07
#: isolada ja usa (ver ``executar_coleta_rq07.py``), que e pelo menos tao pesada
#: quanto qualquer subconjunto de RQ04-RQ07.
TAMANHO_PAGINA_PADRAO = 10


def normalizar(no: dict, referencia_data: datetime, referencia_linguagens: ReferenciaLinguagens) -> dict:
    """Converte um no ``Repository`` cru no registro final de um repositorio.

    A estrutura e plana de proposito: cada integrante contribui com um conjunto
    de chaves prefixadas pela sua RQ (``rq04_*``, ``rq05_*``), e a fusao no
    script unico do grupo e uma simples atualizacao de dicionario, sem colisao.
    O no cru fica preservado em ``bruto`` para permitir auditoria e recalculo.
    """
    no = no or {}
    registro = {
        "nome_completo": no.get("nameWithOwner"),
        "url": no.get("url"),
        "estrelas": no.get("stargazerCount"),
    }
    registro.update(rq01_idade_graphql.calcular(no, referencia_data))
    registro.update(rq04_atualizacao.calcular(no, referencia_data))
    registro.update(rq05_linguagem.calcular(no, referencia_linguagens))
    registro.update(rq06_issues.calcular(no))
    registro.update(rq07_por_linguagem.extrair_metricas_base(no))
    registro.update(rq02_pull_requests_graphql.calcular(no))
    registro.update(rq03_releases_graphql.calcular(no))
    registro["bruto"] = no
    return registro


def coletar(
    cliente: ClienteGitHub,
    quantidade: int = 100,
    busca: str = BUSCA_PADRAO,
    fragmentos: Iterable[str] = FRAGMENTOS_PADRAO,
    referencia_data: Optional[datetime] = None,
    referencia_linguagens: Optional[ReferenciaLinguagens] = None,
    tamanho_pagina: int = TAMANHO_PAGINA_PADRAO,
) -> dict:
    """Coleta os ``quantidade`` repositorios com mais estrelas e calcula as metricas.

    :param cliente: cliente GraphQL ja autenticado.
    :param quantidade: quantos repositorios coletar (maximo de 1000).
    :param busca: criterio de busca do GitHub.
    :param fragmentos: fragmentos de campos que compoem a consulta.
    :param referencia_data: data de referencia da RQ04. Se omitida, usa o instante
        atual em UTC. Fixe-a para tornar a coleta reproduzivel.
    :param referencia_linguagens: ranking de linguagens populares da RQ05.
    :param tamanho_pagina: repositorios por requisicao GraphQL. A consulta com
        os campos de RQ04 a RQ07 e pesada demais para vir toda de uma vez em
        100 repositorios (a API devolve HTTP 502); paginar evita isso.
    :raises ValueError: se os limites de quantidade ou pagina forem invalidos.
    :return: dicionario com ``metadados``, ``repositorios`` e ``resumo``.
    """
    if not isinstance(quantidade, int) or not 1 <= quantidade <= LIMITE_RESULTADOS_BUSCA:
        raise ValueError("A quantidade deve estar entre 1 e %d." % LIMITE_RESULTADOS_BUSCA)
    if not isinstance(tamanho_pagina, int) or not 1 <= tamanho_pagina <= LIMITE_POR_PAGINA:
        raise ValueError("O tamanho da pagina deve estar entre 1 e %d." % LIMITE_POR_PAGINA)

    if referencia_data is None:
        referencia_data = rq04_atualizacao.agora_utc()
    if referencia_linguagens is None:
        referencia_linguagens = ReferenciaLinguagens.carregar()

    consulta = montar_consulta(fragmentos)
    nos = []
    cursor = None
    total_disponivel = None
    requisicoes = 0

    while len(nos) < quantidade:
        por_pagina = min(tamanho_pagina, quantidade - len(nos))
        variaveis = montar_variaveis(por_pagina, busca=busca, cursor=cursor)
        dados = cliente.executar(consulta, variaveis)
        busca_resultado = dados.get("search") or {}
        recebidos = [no for no in (busca_resultado.get("nodes") or []) if no]
        pagina = busca_resultado.get("pageInfo") or {}
        nos.extend(recebidos)
        requisicoes += 1

        if total_disponivel is None:
            total_disponivel = busca_resultado.get("repositoryCount")
        if not recebidos or not pagina.get("hasNextPage"):
            break
        proximo_cursor = pagina.get("endCursor")
        if not proximo_cursor or proximo_cursor == cursor:
            break
        cursor = proximo_cursor

    repositorios = [normalizar(no, referencia_data, referencia_linguagens) for no in nos]

    return {
        "metadados": {
            "coletado_em": referencia_data.isoformat(),
            "criterio_busca": busca,
            "limite_por_pagina_da_api": LIMITE_POR_PAGINA,
            "tamanho_pagina": tamanho_pagina,
            "quantidade_requisicoes": requisicoes,
            "quantidade_solicitada": quantidade,
            "quantidade_retornada": len(repositorios),
            "total_disponivel_na_busca": total_disponivel,
            "rate_limit": cliente.ultimo_rate_limit,
            "consulta_graphql": consulta,
            "definicao_rq01": rq01_idade_graphql.definicao(),
            "definicao_rq02": rq02_pull_requests_graphql.definicao(),
            "definicao_rq03": rq03_releases_graphql.definicao(),
            "definicao_rq04": rq04_atualizacao.definicao(),
            "definicao_rq05": rq05_linguagem.definicao(referencia_linguagens),
            "definicao_rq06": rq06_issues.definicao(),
            "definicao_rq07": rq07_por_linguagem.definicao(),
            "definicao_rq15": rq15_idade_issues_fechadas.definicao(),
        },
        "repositorios": repositorios,
        "resumo": {
            "rq01": rq01_idade_graphql.resumir(repositorios),
            "rq02": rq02_pull_requests_graphql.resumir(repositorios),
            "rq03": rq03_releases_graphql.resumir(repositorios),
            "rq04": rq04_atualizacao.resumir(repositorios),
            "rq05": rq05_linguagem.resumir(repositorios),
            "rq06": rq06_issues.resumir(repositorios),
            "rq07": rq07_por_linguagem.resumir(repositorios),
            "rq15": rq15_idade_issues_fechadas.resumir(repositorios),
        },
    }
