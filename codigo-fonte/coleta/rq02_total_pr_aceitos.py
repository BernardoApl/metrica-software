# scripts/rq02_pull_requests.py

import csv
import os
import time

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


def requisicao(url, params=None):

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


def buscar_top_100_repositorios():

    repositorios = []

    for page in range(1, 11):

        print(
            f"Buscando repositórios - "
            f"página {page}/10"
        )

        dados = requisicao(
            f"{GITHUB_API}/search/repositories",
            params={
                "q": "stars:>0",
                "sort": "stars",
                "order": "desc",
                "per_page": 10,
                "page": page,
            }
        )

        repositorios.extend(
            dados["items"]
        )

        time.sleep(0.2)

    return repositorios[:100]


def contar_prs_aceitos(full_name):

    dados = requisicao(
        f"{GITHUB_API}/search/issues",
        params={
            "q": f"repo:{full_name} is:pr is:merged",
            "per_page": 1,
        }
    )

    return dados["total_count"]


def executar():

    repositorios = buscar_top_100_repositorios()

    print(
        f"\nTotal de repositórios: "
        f"{len(repositorios)}"
    )

    resultados = []

    for indice, repo in enumerate(
        repositorios,
        start=1
    ):

        full_name = repo["full_name"]

        total = contar_prs_aceitos(
            full_name
        )

        resultado = {
            "rank": indice,
            "repository": full_name,
            "stars": repo["stargazers_count"],
            "total_prs_aceitos": total,
        }

        resultados.append(resultado)

        print(
            f"[{indice}/100] "
            f"{full_name} -> "
            f"{total} PRs aceitos"
        )

        # Evita bombardear a API
        time.sleep(0.2)

    os.makedirs("data", exist_ok=True)

    with open(
        "data/rq02_pull_requests.csv",
        "w",
        newline="",
        encoding="utf-8"
    ) as arquivo:

        writer = csv.DictWriter(
            arquivo,
            fieldnames=resultados[0].keys()
        )

        writer.writeheader()
        writer.writerows(resultados)

    print("\nRQ02 concluída.")
    print(
        "Arquivo: data/rq02_pull_requests.csv"
    )


if __name__ == "__main__":
    executar()