"""
RQ12 - Gerar e Validar CSV Consolidado dos 1.000 Repositórios.

Consolida as métricas necessárias das RQs 01 a 06 em um único CSV:

RQ01 - Idade do repositório
RQ02 - Total de pull requests aceitas
RQ03 - Total de releases
RQ04 - Tempo até a última atualização
RQ05 - Linguagem primária
RQ06 - Razão entre issues fechadas e total de issues

Também realiza validações sobre os 1.000 repositórios coletados.
"""

import csv
import os
import time
from datetime import datetime, timezone

import requests


GITHUB_API = "https://api.github.com"

TOKEN = os.getenv("GITHUB_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "A variável de ambiente GITHUB_TOKEN não foi configurada."
    )

HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28",
}

TOTAL_REPOSITORIOS = 1000
REPOSITORIOS_POR_PAGINA = 100


def requisicao(url, params=None):
    """
    Realiza uma requisição para a API do GitHub.

    Quando o rate limit é atingido, aguarda até o momento
    informado pelo GitHub para tentar novamente.
    """

    while True:

        response = requests.get(
            url,
            headers=HEADERS,
            params=params
        )

        if response.status_code in (403, 429):

            remaining = response.headers.get(
                "X-RateLimit-Remaining"
            )

            if remaining == "0":

                reset = int(
                    response.headers["X-RateLimit-Reset"]
                )

                espera = max(
                    reset - time.time(),
                    0
                ) + 2

                print(
                    f"Rate limit atingido. "
                    f"Aguardando {espera:.0f}s..."
                )

                time.sleep(espera)

                continue

        response.raise_for_status()

        return response.json()


def buscar_top_1000_repositorios():
    """
    Busca os 1.000 repositórios com maior número de estrelas.

    A API do GitHub permite no máximo 1.000 resultados
    para uma busca. Por isso são utilizadas 10 páginas
    de 100 registros.
    """

    repositorios = []

    total_paginas = (
        TOTAL_REPOSITORIOS // REPOSITORIOS_POR_PAGINA
    )

    for page in range(1, total_paginas + 1):

        print(
            f"Buscando repositórios - "
            f"página {page}/{total_paginas}"
        )

        dados = requisicao(
            f"{GITHUB_API}/search/repositories",
            params={
                "q": "stars:>0",
                "sort": "stars",
                "order": "desc",
                "per_page": REPOSITORIOS_POR_PAGINA,
                "page": page,
            }
        )

        repositorios.extend(
            dados["items"]
        )

        time.sleep(0.2)

    return repositorios[:TOTAL_REPOSITORIOS]


def calcular_idade(created_at, data_coleta):
    """
    Calcula a idade do repositório em dias e anos.

    Fórmula:
        data_coleta - data_criacao
    """

    data_criacao = datetime.fromisoformat(
        created_at.replace("Z", "+00:00")
    )

    idade_dias = (
        data_coleta - data_criacao
    ).days

    idade_anos = idade_dias / 365.25

    return idade_dias, idade_anos


def contar_prs_aceitos(full_name):
    """
    RQ02.

    Conta pull requests aceitos/merged utilizando
    a busca de issues do GitHub.
    """

    dados = requisicao(
        f"{GITHUB_API}/search/issues",
        params={
            "q": f"repo:{full_name} is:pr is:merged",
            "per_page": 1,
        }
    )

    return dados["total_count"]


def contar_releases(full_name):
    """
    RQ03.

    Conta todas as releases do repositório utilizando
    paginação.
    """

    pagina = 1
    total = 0

    while True:

        releases = requisicao(
            f"{GITHUB_API}/repos/{full_name}/releases",
            params={
                "per_page": 100,
                "page": pagina,
            }
        )

        if not releases:
            break

        total += len(releases)

        pagina += 1

    return total


def calcular_tempo_atualizacao(
    pushed_at,
    data_coleta
):
    """
    RQ04.

    Campo oficial adotado:
        pushed_at

    Fórmula:
        (data_coleta - pushed_at) / 86400

    Retorna:
        dias
        horas
        status
    """

    if not pushed_at:

        return None, None, "sem_push"

    try:

        data_push = datetime.fromisoformat(
            pushed_at.replace("Z", "+00:00")
        )

    except ValueError:

        return None, None, "data_invalida"

    segundos = (
        data_coleta - data_push
    ).total_seconds()

    if segundos < 0:

        return 0.0, 0.0, "data_futura"

    dias = round(
        segundos / 86400.0,
        2
    )

    horas = round(
        segundos / 3600.0,
        2
    )

    return dias, horas, "ok"


def contar_issues(full_name):
    """
    RQ06.

    Obtém:
        - total de issues
        - issues fechadas

    A razão é calculada posteriormente.
    """

    abertas_e_fechadas = requisicao(
        f"{GITHUB_API}/search/issues",
        params={
            "q": f"repo:{full_name} is:issue",
            "per_page": 1,
        }
    )

    fechadas = requisicao(
        f"{GITHUB_API}/search/issues",
        params={
            "q": f"repo:{full_name} is:issue is:closed",
            "per_page": 1,
        }
    )

    total_issues = (
        abertas_e_fechadas["total_count"]
    )

    issues_fechadas = (
        fechadas["total_count"]
    )

    if total_issues == 0:

        razao = None
        status = "sem_issues"

    else:

        razao = round(
            issues_fechadas / total_issues,
            4
        )

        status = "ok"

    return (
        total_issues,
        issues_fechadas,
        razao,
        status
    )


def coletar_metricas(
    repositorios,
    data_coleta
):
    """
    Coleta todas as métricas necessárias
    para as RQs 01 a 06.
    """

    resultados = []

    for indice, repo in enumerate(
        repositorios,
        start=1
    ):

        full_name = repo["full_name"]

        print(
            f"\n[{indice}/{TOTAL_REPOSITORIOS}] "
            f"{full_name}"
        )

        # ==================================================
        # RQ01 - IDADE
        # ==================================================

        idade_dias, idade_anos = calcular_idade(
            repo["created_at"],
            data_coleta
        )

        # ==================================================
        # RQ02 - PULL REQUESTS ACEITOS
        # ==================================================

        total_prs_aceitos = contar_prs_aceitos(
            full_name
        )

        # ==================================================
        # RQ03 - RELEASES
        # ==================================================

        total_releases = contar_releases(
            full_name
        )

        # ==================================================
        # RQ04 - ATUALIZAÇÃO
        # ==================================================

        (
            dias_desde_atualizacao,
            horas_desde_atualizacao,
            rq04_status
        ) = calcular_tempo_atualizacao(
            repo.get("pushed_at"),
            data_coleta
        )

        # ==================================================
        # RQ05 - LINGUAGEM
        # ==================================================

        linguagem = repo.get("language")

        if linguagem:

            rq05_categoria = linguagem
            possui_linguagem = True

        else:

            rq05_categoria = (
                "Sem linguagem definida"
            )

            possui_linguagem = False

        # ==================================================
        # RQ06 - ISSUES
        # ==================================================

        (
            issues_total,
            issues_fechadas,
            razao_issues,
            rq06_status
        ) = contar_issues(
            full_name
        )

        # ==================================================
        # CONSOLIDAÇÃO
        # ==================================================

        resultado = {

            # Identificação
            "rank": indice,
            "repository": full_name,
            "stars": repo["stargazers_count"],

            # RQ01
            "created_at": repo["created_at"],
            "idade_dias": idade_dias,
            "idade_anos": round(
                idade_anos,
                2
            ),

            # RQ02
            "total_prs_aceitos": total_prs_aceitos,

            # RQ03
            "total_releases": total_releases,

            # RQ04
            "pushed_at": repo.get("pushed_at"),
            "updated_at": repo.get("updated_at"),
            "data_coleta": data_coleta.isoformat(),
            "dias_desde_ultima_atualizacao":
                dias_desde_atualizacao,
            "horas_desde_ultima_atualizacao":
                horas_desde_atualizacao,
            "rq04_status": rq04_status,

            # RQ05
            "linguagem_primaria": linguagem,
            "categoria_linguagem": rq05_categoria,
            "possui_linguagem": possui_linguagem,

            # RQ06
            "issues_total": issues_total,
            "issues_fechadas": issues_fechadas,
            "razao_issues_fechadas_total":
                razao_issues,
            "rq06_status": rq06_status,
        }

        resultados.append(
            resultado
        )

        print(
            f"    Stars: "
            f"{repo['stargazers_count']}"
        )

        print(
            f"    RQ01 - Idade: "
            f"{idade_anos:.2f} anos"
        )

        print(
            f"    RQ02 - PRs aceitos: "
            f"{total_prs_aceitos}"
        )

        print(
            f"    RQ03 - Releases: "
            f"{total_releases}"
        )

        if dias_desde_atualizacao is not None:

            print(
                f"    RQ04 - Última atualização: "
                f"{dias_desde_atualizacao:.2f} dias"
            )

        else:

            print(
                f"    RQ04 - Última atualização: "
                f"{rq04_status}"
            )

        print(
            f"    RQ05 - Linguagem: "
            f"{rq05_categoria}"
        )

        print(
            f"    RQ06 - Issues: "
            f"{issues_fechadas}/"
            f"{issues_total}"
        )

        time.sleep(0.2)

    return resultados


def validar_quantidade(resultados):

    erros = []

    quantidade = len(resultados)

    if quantidade != TOTAL_REPOSITORIOS:

        erros.append(
            f"Quantidade incorreta: "
            f"{quantidade} registros. "
            f"Esperado: {TOTAL_REPOSITORIOS}."
        )

    return erros


def validar_duplicidades(resultados):

    erros = []

    repositorios = [
        resultado["repository"]
        for resultado in resultados
    ]

    duplicados = (
        len(repositorios)
        - len(set(repositorios))
    )

    if duplicados > 0:

        erros.append(
            f"Foram encontrados "
            f"{duplicados} repositórios duplicados."
        )

    return erros


def validar_campos(resultados):

    erros = []

    campos_obrigatorios = [

        "rank",
        "repository",
        "stars",

        # RQ01
        "created_at",
        "idade_dias",
        "idade_anos",

        # RQ02
        "total_prs_aceitos",

        # RQ03
        "total_releases",

        # RQ04
        "pushed_at",
        "data_coleta",
        "dias_desde_ultima_atualizacao",
        "horas_desde_ultima_atualizacao",
        "rq04_status",

        # RQ05
        "linguagem_primaria",
        "categoria_linguagem",
        "possui_linguagem",

        # RQ06
        "issues_total",
        "issues_fechadas",
        "razao_issues_fechadas_total",
        "rq06_status",
    ]

    for campo in campos_obrigatorios:

        if not all(
            campo in resultado
            for resultado in resultados
        ):

            erros.append(
                f"Campo obrigatório ausente: "
                f"{campo}"
            )

    return erros


def validar_valores(resultados):

    erros = []

    campos_nao_negativos = [

        "stars",
        "idade_dias",
        "idade_anos",
        "total_prs_aceitos",
        "total_releases",
        "issues_total",
        "issues_fechadas",
    ]

    for resultado in resultados:

        for campo in campos_nao_negativos:

            valor = resultado.get(campo)

            if valor is not None and valor < 0:

                erros.append(
                    f"{resultado['repository']}: "
                    f"valor negativo em {campo}: "
                    f"{valor}"
                )

    return erros


def validar_issues(resultados):

    erros = []

    for resultado in resultados:

        total = resultado[
            "issues_total"
        ]

        fechadas = resultado[
            "issues_fechadas"
        ]

        if fechadas > total:

            erros.append(
                f"{resultado['repository']}: "
                f"issues fechadas ({fechadas}) "
                f"maior que issues totais ({total})."
            )

    return erros


def validar_razao_issues(resultados):

    erros = []

    for resultado in resultados:

        total = resultado[
            "issues_total"
        ]

        fechadas = resultado[
            "issues_fechadas"
        ]

        razao = resultado[
            "razao_issues_fechadas_total"
        ]

        if total == 0:

            if razao is not None:

                erros.append(
                    f"{resultado['repository']}: "
                    f"razão deveria ser None quando "
                    f"não existem issues."
                )

        else:

            razao_esperada = round(
                fechadas / total,
                4
            )

            if razao != razao_esperada:

                erros.append(
                    f"{resultado['repository']}: "
                    f"razão incorreta."
                )

    return erros


def validar_ranks(resultados):

    erros = []

    ranks = [
        resultado["rank"]
        for resultado in resultados
    ]

    ranks_esperados = list(
        range(
            1,
            TOTAL_REPOSITORIOS + 1
        )
    )

    if sorted(ranks) != ranks_esperados:

        erros.append(
            "Os ranks não correspondem "
            "à sequência de 1 até 1000."
        )

    return erros


def validar_resultados(resultados):

    print(
        "\n========================================"
    )

    print(
        "VALIDAÇÃO DO CSV CONSOLIDADO"
    )

    print(
        "========================================"
    )

    erros = []

    erros.extend(
        validar_quantidade(
            resultados
        )
    )

    erros.extend(
        validar_duplicidades(
            resultados
        )
    )

    erros.extend(
        validar_campos(
            resultados
        )
    )

    erros.extend(
        validar_valores(
            resultados
        )
    )

    erros.extend(
        validar_issues(
            resultados
        )
    )

    erros.extend(
        validar_razao_issues(
            resultados
        )
    )

    erros.extend(
        validar_ranks(
            resultados
        )
    )

    if erros:

        print(
            "\nCSV INVALIDADO."
        )

        print(
            f"\nTotal de erros: "
            f"{len(erros)}"
        )

        for erro in erros:

            print(
                f"- {erro}"
            )

        raise RuntimeError(
            "A validação do CSV consolidado falhou."
        )

    print(
        "\nCSV VALIDADO COM SUCESSO."
    )

    print(
        f"Total de repositórios: "
        f"{len(resultados)}"
    )

    repositorios_unicos = len(
        set(
            resultado["repository"]
            for resultado in resultados
        )
    )

    print(
        f"Repositórios únicos: "
        f"{repositorios_unicos}"
    )

    print(
        "Ranks válidos: 1-1000"
    )

    print(
        "Campos obrigatórios: OK"
    )

    print(
        "Valores numéricos: OK"
    )

    print(
        "Consistência das issues: OK"
    )


def salvar_csv(resultados):

    os.makedirs(
        "../coleta/data",
        exist_ok=True
    )

    caminho = (
        "../coleta/data/"
        "rq12_repositorios_1000_consolidado.csv"
    )

    fieldnames = [

        "rank",
        "repository",
        "stars",

        # RQ01
        "created_at",
        "idade_dias",
        "idade_anos",

        # RQ02
        "total_prs_aceitos",

        # RQ03
        "total_releases",

        # RQ04
        "pushed_at",
        "updated_at",
        "data_coleta",
        "dias_desde_ultima_atualizacao",
        "horas_desde_ultima_atualizacao",
        "rq04_status",

        # RQ05
        "linguagem_primaria",
        "categoria_linguagem",
        "possui_linguagem",

        # RQ06
        "issues_total",
        "issues_fechadas",
        "razao_issues_fechadas_total",
        "rq06_status",
    ]

    with open(
        caminho,
        "w",
        newline="",
        encoding="utf-8"
    ) as arquivo:

        writer = csv.DictWriter(
            arquivo,
            fieldnames=fieldnames
        )

        writer.writeheader()

        writer.writerows(
            resultados
        )

    return caminho


def executar():

    print(
        "========================================"
    )

    print(
        "RQ12 - CSV CONSOLIDADO"
    )

    print(
        "========================================"
    )

    # Uma única referência temporal para toda a coleta.
    data_coleta = datetime.now(
        timezone.utc
    )

    print(
        f"\nData da coleta: "
        f"{data_coleta.isoformat()}"
    )

    # ==================================================
    # BUSCA DOS 1.000 REPOSITÓRIOS
    # ==================================================

    repositorios = (
        buscar_top_1000_repositorios()
    )

    print(
        f"\nTotal encontrado: "
        f"{len(repositorios)}"
    )

    if len(repositorios) != TOTAL_REPOSITORIOS:

        raise RuntimeError(
            f"Não foi possível obter os "
            f"{TOTAL_REPOSITORIOS} repositórios. "
            f"Encontrados: {len(repositorios)}."
        )

    # ==================================================
    # COLETA DAS MÉTRICAS
    # ==================================================

    resultados = coletar_metricas(
        repositorios,
        data_coleta
    )

    # ==================================================
    # VALIDAÇÃO
    # ==================================================

    validar_resultados(
        resultados
    )

    # ==================================================
    # CSV
    # ==================================================

    caminho = salvar_csv(
        resultados
    )

    print(
        "\n========================================"
    )

    print(
        "RQ12 CONCLUÍDA"
    )

    print(
        "========================================"
    )

    print(
        f"Arquivo: {caminho}"
    )


if __name__ == "__main__":
    executar()