"""RQ05 - Sistemas populares sao escritos nas linguagens mais populares?

Metrica: linguagem primaria de cada repositorio.

Definicao operacional
---------------------
- **Campo:** ``primaryLanguage.name``, a linguagem primaria que o proprio GitHub
  determina (a linguagem com mais bytes de codigo no repositorio, segundo o
  Linguist).
- **Preservacao do nome:** o valor e guardado exatamente como a API devolve --
  ``C++``, ``C#``, ``Jupyter Notebook``, ``Objective-C`` -- sem normalizar
  maiusculas nem traduzir nomes. Essa string e a chave de agrupamento da RQ07
  ("divida os resultados das RQs 02, 03 e 04 por linguagem"), entao qualquer
  normalizacao aqui se propagaria para a analise dos outros integrantes.
- **Valores ausentes:** ``primaryLanguage`` e nulo em repositorios sem codigo
  detectavel, algo comum entre os mais estrelados do GitHub (listas "awesome",
  colecoes de livros, roadmaps). Esses repositorios recebem
  ``rq05_linguagem_primaria = None`` e a categoria explicita
  ``"Sem linguagem definida"``. Nunca sao descartados: some-los eliminaria uma
  parcela relevante da amostra e distorceria a distribuicao da RQ05.
- **Linguagens mais populares:** ver ``linguagens_populares.py`` -- a fonte e o
  GitHub Octoverse, fixada no Lab01S01 e mantida ate o fim do laboratorio.
"""

from __future__ import annotations

from typing import Iterable, Optional

from linguagens_populares import ReferenciaLinguagens

#: Categoria usada na contagem para repositorios sem linguagem primaria.
SEM_LINGUAGEM = "Sem linguagem definida"


def extrair_linguagem(no: dict) -> Optional[str]:
    """Le ``primaryLanguage.name`` do no cru, tolerando nulos no caminho.

    Nomes vazios ou so com espacos sao tratados como ausencia.
    """
    principal = (no or {}).get("primaryLanguage") or {}
    nome = principal.get("name")
    if not isinstance(nome, str) or not nome.strip():
        return None
    return nome


def calcular(no: dict, referencia: ReferenciaLinguagens) -> dict:
    """Calcula a RQ05 para um repositorio.

    :param no: no ``Repository`` cru, como devolvido pela consulta GraphQL.
    :param referencia: ranking de linguagens populares carregado do arquivo.
    :return: dicionario com as chaves ``rq05_*``.
    """
    linguagem = extrair_linguagem(no)
    rank = referencia.rank(linguagem) if linguagem else None

    return {
        # Nome exatamente como o GitHub devolveu; None quando ausente.
        "rq05_linguagem_primaria": linguagem,
        # Versao sempre preenchida, propria para contagem e agrupamento.
        "rq05_categoria_linguagem": linguagem if linguagem else SEM_LINGUAGEM,
        "rq05_possui_linguagem": linguagem is not None,
        "rq05_esta_entre_populares": rank is not None,
        "rq05_rank_popularidade": rank,
        "rq05_fonte_populares": "%s %s" % (referencia.fonte, referencia.edicao),
    }


def definicao(referencia: ReferenciaLinguagens) -> dict:
    """Definicao da metrica, gravada nos metadados da coleta."""
    return {
        "questao": "RQ05 - Sistemas populares sao escritos nas linguagens mais populares?",
        "metrica": "Linguagem primaria de cada repositorio",
        "campo_utilizado": "primaryLanguage.name",
        "preservacao_do_nome": (
            "O nome e guardado exatamente como a API devolve, sem normalizacao, porque e a "
            "chave de agrupamento da RQ07."
        ),
        "tratamento_de_ausentes": (
            "primaryLanguage nulo -> rq05_linguagem_primaria None e categoria "
            "'%s'. O repositorio permanece no conjunto de dados e e contado como categoria "
            "propria, nunca descartado." % SEM_LINGUAGEM
        ),
        "criterio_de_comparacao": (
            "A comparacao com a lista de referencia ignora maiusculas e minusculas, mas o "
            "valor guardado e sempre o nome devolvido pela API."
        ),
        "referencia_linguagens_populares": referencia.descrever(),
    }


def resumir(registros: Iterable[dict]) -> dict:
    """Agrega a RQ05 sobre a coleta inteira.

    Devolve a contagem por linguagem em ordem decrescente e a fatia de
    repositorios escritos em alguma das linguagens da lista de referencia --
    que e a resposta direta a pergunta da RQ05.
    """
    registros = list(registros)

    contagem = {}
    for r in registros:
        chave = r.get("rq05_categoria_linguagem", SEM_LINGUAGEM)
        contagem[chave] = contagem.get(chave, 0) + 1

    ordenada = dict(sorted(contagem.items(), key=lambda par: (-par[1], par[0].casefold())))

    total = len(registros)
    com_linguagem = sum(1 for r in registros if r.get("rq05_possui_linguagem"))
    entre_populares = sum(1 for r in registros if r.get("rq05_esta_entre_populares"))

    return {
        "total_repositorios": total,
        "com_linguagem": com_linguagem,
        "sem_linguagem": total - com_linguagem,
        "linguagens_distintas": len([c for c in contagem if c != SEM_LINGUAGEM]),
        "entre_linguagens_populares": entre_populares,
        "percentual_entre_populares": round(100.0 * entre_populares / total, 2) if total else None,
        "contagem_por_linguagem": ordenada,
    }
