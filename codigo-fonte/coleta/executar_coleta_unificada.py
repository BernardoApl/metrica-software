"""Script unico do grupo: junta as sete RQs num dataset final, para 1000 repositorios.

Nao modifica nenhum script individual dos integrantes. Reaproveita:

- as funcoes de coleta de ``analise/rq01_idade.py``, ``analise/rq02_total_pr_aceitos.py``
  e ``analise/rq03_total_de_releases.py`` (``calcular_idade``, ``contar_prs_aceitos``,
  ``contar_releases``) -- RQ01, RQ02 e RQ03 continuam sendo coletadas via REST,
  exatamente como cada integrante escreveu;
- ``coleta_repositorios.coletar()``, que ja junta RQ04, RQ05, RQ06 e RQ07
  numa unica consulta GraphQL.

O merge final e feito pelo nome completo do repositorio (``owner/repo``). REST
e GraphQL fazem buscas independentes.
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

PAUSA_ENTRE_CHAMADAS_REST = 1.5

def chamar_com_retentativa(func, *args, tentativas: int = 5, espera_em_limite: float = 65.0):
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
    os.environ.setdefault("GITHUB_TOKEN", token)
    import rq01_idade
    import rq02_total_pr_aceitos
    import rq03_total_de_releases
    return rq01_idade, rq02_total_pr_aceitos, rq03_total_de_releases

def buscar_repositorios_rest_paginado(quantidade: int, token: str) -> list:
    """Faz a busca paginada na API REST para trazer a quantidade desejada de repositorios,
    substituindo a funcao hardcoded de 100."""
    repositorios = []
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"}
    paginas = (quantidade // 100) + (1 if quantidade % 100 != 0 else 0)

    print(f"Buscando a lista base de {quantidade} repositorios via REST...")
    for pagina in range(1, paginas + 1):
        url = f"https://api.github.com/search/repositories?q=stars:>0&sort=stars&order=desc&per_page=100&page={pagina}"
        resposta = requests.get(url, headers=headers)
        resposta.raise_for_status()

        itens = resposta.json().get("items", [])
        repositorios.extend(itens)

        if len(itens) < 100:
            break

        time.sleep(PAUSA_ENTRE_CHAMADAS_REST)

    return repositorios[:quantidade]

def coletar_rest(rq01_idade, rq02_total_pr_aceitos, rq03_total_de_releases, quantidade: int, token: str) -> list:
    """Coleta RQ01, RQ02 e RQ03 reaproveitando as funcoes dos scripts individuais."""

    # Substituimos a chamada de 100 pela funcao paginada customizada acima
    repositorios = buscar_repositorios_rest_paginado(quantidade, token)

    registros = []
    total = len(repositorios)

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
        print(f"[REST {indice}/{total}] {repo['full_name']} -> {idade_anos:.2f} anos, {total_prs} PRs aceitos, {total_releases} releases")

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
    token: str,
    quantidade: int = 1000,
    busca: str = BUSCA_PADRAO,
) -> dict:
    print(f"Consultando a API GraphQL do GitHub (RQ04, RQ05, RQ06, RQ07) para {quantidade} repositorios...")
    resultado_graphql = coletar_graphql(cliente, quantidade=quantidade, busca=busca)
    por_nome_graphql = {r["nome_completo"]: r for r in resultado_graphql["repositorios"]}

    print(f"Consultando a API REST do GitHub (RQ01, RQ02, RQ03) para {quantidade} repositorios...")
    registros_rest = coletar_rest(rq01_idade, rq02_total_pr_aceitos, rq03_total_de_releases, quantidade, token)
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

    idades_anos = [r["rq01_idade_anos"] for r in unificados if isinstance(r.get("rq01_idade_anos"), (int, float))]
    prs_aceitos = [r["rq02_pull_requests_aceitos"] for r in unificados if isinstance(r.get("rq02_pull_requests_aceitos"), int)]
    releases = [r["rq03_total_releases"] for r in unificados if isinstance(r.get("rq03_total_releases"), int)]

    return {
        "metadados": {
            "quantidade_graphql": len(por_nome_graphql),
            "quantidade_rest": len(por_nome_rest),
            "quantidade_em_ambas_as_buscas": sum(1 for r in unificados if r["presente_na_busca_graphql"] and r["presente_na_busca_rest"]),
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
            "rq15": resultado_graphql["resumo"].get("rq15", {}),
            "rq16": resultado_graphql["resumo"].get("rq16", {}),
            "rq01_graphql": resultado_graphql["resumo"].get("rq01", {}),
            "rq02_graphql": resultado_graphql["resumo"].get("rq02", {}),
            "rq03_graphql": resultado_graphql["resumo"].get("rq03", {}),
        },
    }

def montar_argumentos(argv=None) -> argparse.Namespace:
    analisador = argparse.ArgumentParser(
        description="Coleta os repositorios mais populares do GitHub e junta RQ01 a RQ07 num unico dataset."
    )
    analisador.add_argument(
        "--quantidade", type=int, default=1000,
        help="Quantidade de repositorios a serem buscados em ambas as APIs (GraphQL e REST). Padrao: 1000.",
    )
    analisador.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    analisador.add_argument("--token", default=None)
    analisador.add_argument("--busca", default=BUSCA_PADRAO)
    return analisador.parse_args(argv)

def imprimir_resumo(resultado: dict) -> None:
    metadados = resultado["metadados"]
    resumo = resultado["resumo"]

    print("\n" + "=" * 72)
    print("COLETA UNIFICADA CONCLUIDA")
    print("=" * 72)
    print(f"Repositorios (GraphQL)      : {metadados['quantidade_graphql']}")
    print(f"Repositorios (REST)         : {metadados['quantidade_rest']}")
    print(f"Presentes nas duas buscas   : {metadados['quantidade_em_ambas_as_buscas']}")
    print(f"Total unificado             : {metadados['quantidade_unificada']}\n")

def principal(argv=None) -> int:
    argumentos = montar_argumentos(argv)

    try:
        token = obter_token(argumentos.token)
        rq01_idade, rq02_total_pr_aceitos, rq03_total_de_releases = preparar_modulos_rest(token)
        cliente = ClienteGitHub(token)
        resultado = unificar(
            cliente, rq01_idade, rq02_total_pr_aceitos, rq03_total_de_releases, token,
            argumentos.quantidade, argumentos.busca,
        )
    except (ValueError, RuntimeError, ErroGitHub, requests.exceptions.RequestException) as erro:
        print("[erro] %s" % erro, file=sys.stderr)
        return 1

    argumentos.saida.parent.mkdir(parents=True, exist_ok=True)
    with open(argumentos.saida, "w", encoding="utf-8") as arquivo:
        json.dump(resultado, arquivo, ensure_ascii=False, indent=2)

    imprimir_resumo(resultado)
    print(f"\nSaida gravada em: {argumentos.saida}")
    return 0

if __name__ == "__main__":
    sys.exit(principal())