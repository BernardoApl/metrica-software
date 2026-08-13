"""Script unico do grupo: junta as sete RQs num dataset final, para 100 repositorios.

Nao modifica nenhum script individual dos integrantes. Reaproveita:

- as funcoes de coleta de ``analise/rq01_idade.py``, ``analise/rq02_total_pr_aceitos.py``
  e ``analise/rq03_total_de_releases.py`` (``buscar_top_100_repositorios``,
  ``calcular_idade``, ``contar_prs_aceitos``, ``contar_releases``) -- RQ01, RQ02
  e RQ03 continuam sendo coletadas via REST, exatamente como cada integrante
  escreveu;
- ``coleta_repositorios.coletar()``, que ja junta RQ04, RQ05, RQ06 e RQ07
  numa unica consulta GraphQL.

O merge final e feito pelo nome completo do repositorio (``owner/repo``). REST
e GraphQL fazem buscas independentes -- criterios ligeiramente diferentes
(``stars:>0`` vs. ``stars:>1 is:public``) e instantes diferentes, com a
contagem de estrelas mudando entre as duas chamadas --, entao um repositorio
pode aparecer numa lista e nao na outra. Esses casos ficam marcados nos campos
``presente_na_busca_rest``/``presente_na_busca_graphql`` em vez de descartados
ou de travar a coleta.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap import DIRETORIO_DADOS, configurar_caminhos  # noqa: E402

configurar_caminhos()

from cliente_github import ClienteGitHub, ErroGitHub, obter_token  # noqa: E402
from coleta_repositorios import coletar as coletar_graphql  # noqa: E402
from consulta import BUSCA_PADRAO  # noqa: E402

SAIDA_PADRAO = DIRETORIO_DADOS / "lab01s01_unificado.json"

#: Pausa entre repositorios no laco REST -- reproduzida aqui porque a coleta REST
#: chama diretamente as funcoes menores dos scripts individuais
#: (buscar_top_100_repositorios, contar_prs_aceitos, contar_releases), sem passar
#: pelos lacos originais. 1.5s porque a Search API do GitHub (usada por
#: contar_prs_aceitos) tem um limite secundario de ~30 requisicoes/min --
#: bem mais apertado que o limite principal de 5000/h.
PAUSA_ENTRE_CHAMADAS_REST = 1.5


def chamar_com_retentativa(func, *args, tentativas: int = 5, espera_em_limite: float = 65.0):
    """Repete uma chamada de um script individual apos um limite secundario.

    O ``requisicao()`` dos scripts REST individuais trata apenas o limite
    principal da API (``X-RateLimit-Remaining`` chegando a zero). A Search API
    (usada por ``contar_prs_aceitos``) tambem tem um limite secundario, mais
    apertado, que devolve HTTP 403 mesmo com o limite principal longe do fim;
    sem tratamento, esse 403 sobe como ``requests.exceptions.HTTPError`` e
    derruba a coleta. Em vez de alterar o script de cada integrante, o retry
    fica aqui, na orquestracao.
    """
    for tentativa in range(1, tentativas + 1):
        try:
            return func(*args)
        except requests.exceptions.HTTPError as erro:
            resposta = erro.response
            limite_secundario = resposta is not None and resposta.status_code in (403, 429)
            if limite_secundario and tentativa < tentativas:
                print("[aviso] limite secundario da API atingido, aguardando %.0fs (tentativa %d/%d)"
                      % (espera_em_limite, tentativa, tentativas))
                time.sleep(espera_em_limite)
                continue
            raise


def preparar_modulos_rest(token: str):
    """Importa os modulos REST individuais sem modifica-los.

    Os tres modulos leem ``GITHUB_TOKEN`` do ambiente no momento do import
    (``os.getenv``, sem o fallback de ``.env`` que ``obter_token`` tem) e levantam
    ``RuntimeError`` se a variavel nao estiver definida. Por isso o token ja
    resolvido e injetado no ambiente antes do import, para que o import nao
    falhe quando o token so existir no arquivo ``.env``.
    """
    os.environ.setdefault("GITHUB_TOKEN", token)
    import rq01_idade
    import rq02_total_pr_aceitos
    import rq03_total_de_releases
    return rq01_idade, rq02_total_pr_aceitos, rq03_total_de_releases


def coletar_rest(rq01_idade, rq02_total_pr_aceitos, rq03_total_de_releases) -> list:
    """Coleta RQ01, RQ02 e RQ03 reaproveitando as funcoes dos scripts individuais."""
    repositorios = rq01_idade.buscar_top_100_repositorios()

    registros = []
    for indice, repo in enumerate(repositorios, start=1):
        _, idade_dias, idade_anos = rq01_idade.calcular_idade(repo["created_at"])

        try:
            total_prs = chamar_com_retentativa(rq02_total_pr_aceitos.contar_prs_aceitos, repo["full_name"])
        except requests.exceptions.RequestException as erro:
            print("[aviso] RQ02 falhou para %s (%s); metrica fica ausente." % (repo["full_name"], erro))
            total_prs = None

        try:
            total_releases = chamar_com_retentativa(rq03_total_de_releases.contar_releases, repo["full_name"])
        except requests.exceptions.RequestException as erro:
            print("[aviso] RQ03 falhou para %s (%s); metrica fica ausente." % (repo["full_name"], erro))
            total_releases = None

        time.sleep(PAUSA_ENTRE_CHAMADAS_REST)

        registros.append({
            "nome_completo": repo["full_name"],
            "estrelas_rest": repo["stargazers_count"],
            "rq01_idade_dias": idade_dias,
            "rq01_idade_anos": round(idade_anos, 2),
            "rq02_pull_requests_aceitos": total_prs,
            "rq03_total_releases": total_releases,
        })
        print("[REST %d/100] %s -> %.2f anos, %s PRs aceitos, %s releases"
              % (indice, repo["full_name"], idade_anos, total_prs, total_releases))

    return registros


def _estatisticas(valores: list) -> dict:
    if not valores:
        return {"media": None, "mediana": None, "minimo": None, "maximo": None}
    return {
        "media": round(statistics.fmean(valores), 2),
        "mediana": round(statistics.median(valores), 2),
        "minimo": min(valores),
        "maximo": max(valores),
    }


def unificar(
    cliente: ClienteGitHub,
    rq01_idade,
    rq02_total_pr_aceitos,
    rq03_total_de_releases,
    quantidade: int = 100,
    busca: str = BUSCA_PADRAO,
) -> dict:
    """Roda os dois lados da coleta (REST e GraphQL) e junta por nome do repositorio."""
    print("Consultando a API GraphQL do GitHub (RQ04, RQ05, RQ06, RQ07)...")
    resultado_graphql = coletar_graphql(cliente, quantidade=quantidade, busca=busca)
    por_nome_graphql = {r["nome_completo"]: r for r in resultado_graphql["repositorios"]}

    print("Consultando a API REST do GitHub (RQ01, RQ02, RQ03)...")
    registros_rest = coletar_rest(rq01_idade, rq02_total_pr_aceitos, rq03_total_de_releases)
    por_nome_rest = {r["nome_completo"]: r for r in registros_rest}

    nomes = list(dict.fromkeys(list(por_nome_graphql) + list(por_nome_rest)))
    unificados = []
    for nome in nomes:
        graphql = por_nome_graphql.get(nome)
        rest = por_nome_rest.get(nome)
        registro = {
            "nome_completo": nome,
            "presente_na_busca_graphql": graphql is not None,
            "presente_na_busca_rest": rest is not None,
        }
        if graphql:
            registro.update({
                "url": graphql.get("url"),
                "estrelas": graphql.get("estrelas"),
                "rq04_dias_desde_ultima_atualizacao": graphql.get("rq04_dias_desde_ultima_atualizacao"),
                "rq04_status": graphql.get("rq04_status"),
                "rq05_linguagem_primaria": graphql.get("rq05_linguagem_primaria"),
                "rq05_categoria_linguagem": graphql.get("rq05_categoria_linguagem"),
                "rq06_issues_total": graphql.get("rq06_issues_total"),
                "rq06_razao_fechadas_total": graphql.get("rq06_razao_fechadas_total"),
                # Calculadas de novo via GraphQL (rq01_idade_graphql.py,
                # rq02_pull_requests_graphql.py, rq03_releases_graphql.py); mantidas
                # so como comparativo -- quem responde pela RQ01/RQ02/RQ03 e o REST.
                "rq01_idade_anos_graphql": graphql.get("rq01_idade_anos"),
                "rq02_pull_requests_aceitos_graphql": graphql.get("rq02_pull_requests_aceitos_graphql"),
                "rq03_total_releases_graphql": graphql.get("rq03_total_releases_graphql"),
            })
        if rest:
            registro.setdefault("estrelas", rest.get("estrelas_rest"))
            registro.update({
                "rq01_idade_dias": rest.get("rq01_idade_dias"),
                "rq01_idade_anos": rest.get("rq01_idade_anos"),
                "rq02_pull_requests_aceitos": rest.get("rq02_pull_requests_aceitos"),
                "rq03_total_releases": rest.get("rq03_total_releases"),
            })
        unificados.append(registro)

    idades_anos = [
        r["rq01_idade_anos"] for r in unificados if isinstance(r.get("rq01_idade_anos"), (int, float))
    ]
    prs_aceitos = [
        r["rq02_pull_requests_aceitos"] for r in unificados if isinstance(r.get("rq02_pull_requests_aceitos"), int)
    ]
    releases = [
        r["rq03_total_releases"] for r in unificados if isinstance(r.get("rq03_total_releases"), int)
    ]

    return {
        "metadados": {
            "quantidade_graphql": len(por_nome_graphql),
            "quantidade_rest": len(por_nome_rest),
            "quantidade_em_ambas_as_buscas": sum(
                1 for r in unificados if r["presente_na_busca_graphql"] and r["presente_na_busca_rest"]
            ),
            "quantidade_unificada": len(unificados),
            "criterio_busca_graphql": busca,
            "criterio_busca_rest": "stars:>0 sort:stars order:desc",
            "consulta_graphql": resultado_graphql["metadados"]["consulta_graphql"],
            "rate_limit_graphql": cliente.ultimo_rate_limit,
        },
        "repositorios": unificados,
        "resumo": {
            "rq01_idade_anos": _estatisticas(idades_anos),
            "rq02_pull_requests_aceitos": _estatisticas(prs_aceitos),
            "rq03_total_releases": _estatisticas(releases),
            "rq04": resultado_graphql["resumo"]["rq04"],
            "rq05": resultado_graphql["resumo"]["rq05"],
            "rq06": resultado_graphql["resumo"]["rq06"],
            "rq07": resultado_graphql["resumo"]["rq07"],
            # Resumos calculados via GraphQL, para comparar com o REST acima.
            "rq01_graphql": resultado_graphql["resumo"]["rq01"],
            "rq02_graphql": resultado_graphql["resumo"]["rq02"],
            "rq03_graphql": resultado_graphql["resumo"]["rq03"],
        },
    }


def montar_argumentos(argv=None) -> argparse.Namespace:
    analisador = argparse.ArgumentParser(
        description=(
            "Coleta os repositorios mais populares do GitHub e junta RQ01 a RQ07 "
            "num unico dataset, sem alterar os scripts individuais."
        )
    )
    analisador.add_argument(
        "--quantidade", type=int, default=100,
        help="Quantidade de repositorios no lado GraphQL (RQ04-RQ07). O lado REST "
             "(RQ01/RQ02/RQ03) sempre busca 100, conforme os scripts individuais.",
    )
    analisador.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    analisador.add_argument("--token", default=None)
    analisador.add_argument("--busca", default=BUSCA_PADRAO)
    return analisador.parse_args(argv)


def imprimir_resumo(resultado: dict) -> None:
    metadados = resultado["metadados"]
    resumo = resultado["resumo"]

    print("")
    print("=" * 72)
    print("COLETA UNIFICADA CONCLUIDA")
    print("=" * 72)
    print("Repositorios (GraphQL)      : %s" % metadados["quantidade_graphql"])
    print("Repositorios (REST)         : %s" % metadados["quantidade_rest"])
    print("Presentes nas duas buscas   : %s" % metadados["quantidade_em_ambas_as_buscas"])
    print("Total unificado             : %s" % metadados["quantidade_unificada"])

    print("")
    print("-- RQ01: idade do repositorio (REST | GraphQL, comparativo) --")
    print("  Mediana: %s anos | %s anos" % (
        resumo["rq01_idade_anos"]["mediana"], resumo["rq01_graphql"]["mediana_anos"]))
    print("  Media  : %s anos | %s anos" % (
        resumo["rq01_idade_anos"]["media"], resumo["rq01_graphql"]["media_anos"]))

    print("")
    print("-- RQ02: pull requests aceitos (REST | GraphQL, comparativo) --")
    print("  Mediana: %s | %s" % (resumo["rq02_pull_requests_aceitos"]["mediana"], resumo["rq02_graphql"]["mediana"]))
    print("  Media  : %s | %s" % (resumo["rq02_pull_requests_aceitos"]["media"], resumo["rq02_graphql"]["media"]))

    print("")
    print("-- RQ03: total de releases (REST | GraphQL, comparativo) --")
    print("  Mediana: %s | %s" % (resumo["rq03_total_releases"]["mediana"], resumo["rq03_graphql"]["mediana"]))
    print("  Media  : %s | %s" % (resumo["rq03_total_releases"]["media"], resumo["rq03_graphql"]["media"]))

    print("")
    print("-- RQ04: tempo ate a ultima atualizacao --")
    print("  Mediana: %s dias | Media: %s dias" % (resumo["rq04"]["mediana_dias"], resumo["rq04"]["media_dias"]))

    print("")
    print("-- RQ05: linguagem primaria --")
    print("  Linguagens distintas: %s | Sem linguagem: %s" % (
        resumo["rq05"]["linguagens_distintas"], resumo["rq05"]["sem_linguagem"]))

    print("")
    print("-- RQ06: razao de issues fechadas --")
    print("  Mediana: %s | Media: %s" % (resumo["rq06"]["mediana_razao"], resumo["rq06"]["media_razao"]))

    print("")
    print("-- RQ07: grupos de linguagem --")
    print("  Grupos: %s" % len(resumo["rq07"]))


def principal(argv=None) -> int:
    argumentos = montar_argumentos(argv)

    try:
        token = obter_token(argumentos.token)
        rq01_idade, rq02_total_pr_aceitos, rq03_total_de_releases = preparar_modulos_rest(token)
        cliente = ClienteGitHub(token)
        resultado = unificar(
            cliente, rq01_idade, rq02_total_pr_aceitos, rq03_total_de_releases,
            argumentos.quantidade, argumentos.busca,
        )
    except (ValueError, RuntimeError, ErroGitHub, requests.exceptions.RequestException) as erro:
        print("[erro] %s" % erro, file=sys.stderr)
        return 1

    argumentos.saida.parent.mkdir(parents=True, exist_ok=True)
    with open(argumentos.saida, "w", encoding="utf-8") as arquivo:
        json.dump(resultado, arquivo, ensure_ascii=False, indent=2)

    imprimir_resumo(resultado)
    print("")
    print("Saida gravada em: %s" % argumentos.saida)
    return 0


if __name__ == "__main__":
    sys.exit(principal())
