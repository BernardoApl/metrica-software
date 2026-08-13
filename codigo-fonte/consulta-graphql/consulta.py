"""Montagem da consulta GraphQL enviada a API do GitHub.

Ponto de integracao do grupo
----------------------------
Cada integrante declara aqui (ou em modulo proprio) o *fragmento* de campos de
que suas RQs precisam. A consulta final e a concatenacao dos fragmentos, de
modo que a integracao no script unico do grupo nao exija que ninguem reescreva
a consulta de outro integrante.

Campos repetidos entre fragmentos nao sao problema: o GraphQL funde selecoes
identicas do mesmo campo, entao dois integrantes podem pedir ``stargazerCount``
sem conflito.

Escopo desta sprint (Lab01S01)
-----------------------------
Sem paginacao. ``first`` da Search API tem teto de 100 itens por pagina, o que
cobre exatamente os 100 repositorios exigidos em S01. A consulta ja devolve
``pageInfo``, de modo que a paginacao de 1000 repositorios (Lab01S02) se resuma
a iterar sobre ``endCursor``.
"""

from __future__ import annotations

from typing import Iterable

#: Teto de itens por pagina imposto pela API do GitHub.
LIMITE_POR_PAGINA = 100

#: Criterio de busca: repositorios publicos ordenados por numero de estrelas.
#: A Search API devolve no maximo 1000 resultados, o que e exatamente o alvo do
#: Lab01S02 -- por isso o mesmo criterio serve para as duas sprints.
BUSCA_PADRAO = "is:public stars:>1 sort:stars-desc"

#: Identificacao do repositorio. Necessaria para todos os integrantes, serve de
#: chave de juncao entre as metricas de cada um.
CAMPOS_IDENTIFICACAO = """
        nameWithOwner
        url
        stargazerCount
"""

#: Campo da RQ01: data de criacao, usada para calcular a idade do repositorio.
CAMPOS_RQ01 = """
        createdAt
"""

#: Campos das RQ04 e RQ05 (responsabilidade deste integrante).
#:
#: - ``pushedAt``: campo oficial da RQ04 (ver ``analise/rq04_atualizacao.py``).
#: - ``updatedAt`` e ``defaultBranchRef.target.committedDate``: coletados como
#:   comparativos auditaveis, para justificar no relatorio a escolha do campo
#:   oficial. Nao entram no calculo da metrica.
#: - ``primaryLanguage.name``: campo da RQ05.
CAMPOS_RQ04_RQ05 = """
        pushedAt
        updatedAt
        defaultBranchRef {
          name
          target {
            ... on Commit {
              committedDate
            }
          }
        }
        primaryLanguage {
          name
        }
"""

CAMPOS_RQ06 = """
        issues(first: 1) {
          totalCount
        }
        issuesFechadas: issues(first: 1, states: CLOSED) {
          totalCount
        }
"""

CAMPOS_RQ07 = """
        pullRequestsAceitos: pullRequests(first: 1, states: MERGED) {
          totalCount
        }
        releases(first: 1) {
          totalCount
        }
"""

CAMPOS_RQ06_RQ07 = CAMPOS_RQ06 + CAMPOS_RQ07

_MODELO_CONSULTA = """query RepositoriosPopulares($primeiros: Int!, $cursor: String, $busca: String!) {
  rateLimit {
    limit
    cost
    remaining
    resetAt
  }
  search(query: $busca, type: REPOSITORY, first: $primeiros, after: $cursor) {
    repositoryCount
    pageInfo {
      hasNextPage
      endCursor
    }
    nodes {
      ... on Repository {
%(campos)s
      }
    }
  }
}
"""


def montar_consulta(fragmentos: Iterable[str] = None) -> str:
    """Monta a consulta GraphQL a partir dos fragmentos de campos informados.

    :param fragmentos: fragmentos de selecao de campos aplicados dentro de
        ``... on Repository``. Se omitido, usa identificacao + RQ04 a RQ07.
    :return: a consulta GraphQL como texto.
    """
    if fragmentos is None:
        fragmentos = (CAMPOS_IDENTIFICACAO, CAMPOS_RQ01, CAMPOS_RQ04_RQ05, CAMPOS_RQ06_RQ07)

    blocos = [fragmento.strip("\n") for fragmento in fragmentos if fragmento and fragmento.strip()]
    if not blocos:
        raise ValueError("E preciso informar ao menos um fragmento de campos.")

    return _MODELO_CONSULTA % {"campos": "\n".join(blocos)}


def montar_variaveis(quantidade: int, busca: str = BUSCA_PADRAO, cursor: str = None) -> dict:
    """Monta o dicionario de variaveis da consulta.

    :param quantidade: quantos repositorios pedir nesta pagina (1..100).
    :param busca: criterio de busca do GitHub.
    :param cursor: cursor de paginacao (``endCursor`` da pagina anterior).
    :raises ValueError: se ``quantidade`` estiver fora do intervalo aceito.
    """
    if not isinstance(quantidade, int) or quantidade < 1:
        raise ValueError("A quantidade deve ser um inteiro positivo.")
    if quantidade > LIMITE_POR_PAGINA:
        raise ValueError(
            "A API do GitHub limita a busca a %d itens por pagina; foram pedidos %d. "
            "Coletar mais que isso exige paginacao, que pertence ao escopo do Lab01S02."
            % (LIMITE_POR_PAGINA, quantidade)
        )

    return {"primeiros": quantidade, "busca": busca, "cursor": cursor}
