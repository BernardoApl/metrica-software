"""Orquestracao da coleta dos repositorios mais populares do GitHub.

Fluxo: monta a consulta a partir dos fragmentos de campos -> envia pelo cliente
proprio -> normaliza cada no cru em um registro com as metricas calculadas.

Escopo desta sprint (Lab01S01): 100 repositorios em uma unica requisicao, sem
paginacao. Os metadados da saida ja carregam ``possui_proxima_pagina`` e
``cursor_final``, de modo que a paginacao de 1000 repositorios (Lab01S02) seja
apenas iterar sobre o cursor.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

import rq04_atualizacao
import rq05_linguagem
import rq06_issues
import rq07_por_linguagem
from cliente_github import ClienteGitHub
from consulta import (
    BUSCA_PADRAO,
    CAMPOS_IDENTIFICACAO,
    CAMPOS_RQ04_RQ05,
    CAMPOS_RQ06_RQ07,
    LIMITE_POR_PAGINA,
    montar_consulta,
    montar_variaveis,
)
from linguagens_populares import ReferenciaLinguagens

#: Fragmentos usados quando a coleta roda isolada, no escopo deste integrante.
#: Na integracao com o grupo, basta acrescentar os fragmentos dos demais.
FRAGMENTOS_PADRAO = (CAMPOS_IDENTIFICACAO, CAMPOS_RQ04_RQ05, CAMPOS_RQ06_RQ07)


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
    registro.update(rq04_atualizacao.calcular(no, referencia_data))
    registro.update(rq05_linguagem.calcular(no, referencia_linguagens))
    registro.update(rq06_issues.calcular(no))
    registro.update(rq07_por_linguagem.extrair_metricas_base(no))
    registro["bruto"] = no
    return registro


def coletar(
    cliente: ClienteGitHub,
    quantidade: int = 100,
    busca: str = BUSCA_PADRAO,
    fragmentos: Iterable[str] = FRAGMENTOS_PADRAO,
    referencia_data: Optional[datetime] = None,
    referencia_linguagens: Optional[ReferenciaLinguagens] = None,
) -> dict:
    """Coleta os ``quantidade`` repositorios com mais estrelas e calcula as metricas.

    :param cliente: cliente GraphQL ja autenticado.
    :param quantidade: quantos repositorios coletar (maximo de 100 nesta sprint).
    :param busca: criterio de busca do GitHub.
    :param fragmentos: fragmentos de campos que compoem a consulta.
    :param referencia_data: data de referencia da RQ04. Se omitida, usa o instante
        atual em UTC. Fixe-a para tornar a coleta reproduzivel.
    :param referencia_linguagens: ranking de linguagens populares da RQ05.
    :raises ValueError: se ``quantidade`` exceder o limite da API.
    :return: dicionario com ``metadados``, ``repositorios`` e ``resumo``.
    """
    if referencia_data is None:
        referencia_data = rq04_atualizacao.agora_utc()
    if referencia_linguagens is None:
        referencia_linguagens = ReferenciaLinguagens.carregar()

    consulta = montar_consulta(fragmentos)
    variaveis = montar_variaveis(quantidade, busca=busca)

    dados = cliente.executar(consulta, variaveis)
    busca_resultado = dados.get("search") or {}
    nos = [no for no in (busca_resultado.get("nodes") or []) if no]

    repositorios = [normalizar(no, referencia_data, referencia_linguagens) for no in nos]
    pagina = busca_resultado.get("pageInfo") or {}

    return {
        "metadados": {
            "coletado_em": referencia_data.isoformat(),
            "criterio_busca": busca,
            "limite_por_pagina_da_api": LIMITE_POR_PAGINA,
            "quantidade_solicitada": quantidade,
            "quantidade_retornada": len(repositorios),
            "total_disponivel_na_busca": busca_resultado.get("repositoryCount"),
            "possui_proxima_pagina": pagina.get("hasNextPage"),
            "cursor_final": pagina.get("endCursor"),
            "rate_limit": cliente.ultimo_rate_limit,
            "consulta_graphql": consulta,
            "definicao_rq04": rq04_atualizacao.definicao(),
            "definicao_rq05": rq05_linguagem.definicao(referencia_linguagens),
            "definicao_rq06": rq06_issues.definicao(),
            "definicao_rq07": rq07_por_linguagem.definicao(),
        },
        "repositorios": repositorios,
        "resumo": {
            "rq04": rq04_atualizacao.resumir(repositorios),
            "rq05": rq05_linguagem.resumir(repositorios),
            "rq06": rq06_issues.resumir(repositorios),
            "rq07": rq07_por_linguagem.resumir(repositorios),
        },
    }
