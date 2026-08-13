
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

def requisicao(url, params=None):
    while True:
        response = requests.get(
            url,
            headers=HEADERS,
            params=params
        )

        if response.status_code == 403:
            remaining = response.headers.get("X-RateLimit-Remaining")

            if remaining == "0":
                reset = int(response.headers["X-RateLimit-Reset"])
                agora = time.time()
                espera = max(reset - agora, 0) + 2

                print(f"Rate limit atingido. Aguardando {espera:.0f}s...")
                time.sleep(espera)
                continue

        response.raise_for_status()

        return response.json()

def buscar_top_100_repositorios():
    repositorios = []

    for page in range(1, 11):

        print(f"Buscando repositórios - página {page}/10")

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

        repositorios.extend(dados["items"])
        time.sleep(0.2)

    return repositorios[:100]

def calcular_idade(created_at):
    data_criacao = datetime.fromisoformat(
        created_at.replace("Z", "+00:00")
    )

    data_coleta = datetime.now(timezone.utc)

    idade_dias = (data_coleta - data_criacao).days
    idade_anos = idade_dias / 365.25

    return data_coleta, idade_dias, idade_anos

def executar():

    repositorios = buscar_top_100_repositorios()

    print(f"\nTotal encontrado: {len(repositorios)}")

    data = []

    for indice, repo in enumerate(repositorios, start=1):

        data_coleta, idade_dias, idade_anos = calcular_idade(
            repo["created_at"]
        )

        resultado = {
            "rank": indice,
            "repository": repo["full_name"],
            "stars": repo["stargazers_count"],
            "created_at": repo["created_at"],
            "collected_at": data_coleta.isoformat(),
            "idade_dias": idade_dias,
            "idade_anos": round(idade_anos, 2),
        }

        data.append(resultado)

        print(
            f"[{indice}/100] "
            f"{repo['full_name']} -> "
            f"{idade_anos:.2f} anos"
        )

    os.makedirs("../coleta/data", exist_ok=True)

    with open(
        "data/rq01_idade.csv",
        "w",
        newline="",
        encoding="utf-8"
    ) as arquivo:

        writer = csv.DictWriter(
            arquivo,
            fieldnames=data[0].keys()
        )

        writer.writeheader()
        writer.writerows(data)

    print("\nRQ01 concluída.")
    print("Arquivo: data/rq01_idade.csv")


if __name__ == "__main__":
    executar()