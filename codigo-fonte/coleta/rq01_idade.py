
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

def buscar_top_1000_repositorios():
    repositorios = []

    for page in range(1, 11):

        print(f"Buscando repositórios - página {page}/10")

        dados = requisicao(
            f"{GITHUB_API}/search/repositories",
            params={
                "q": "stars:>0",
                "sort": "stars",
                "order": "desc",
                "per_page": 100,
                "page": page,
            }
        )

        repositorios.extend(dados["items"])
        time.sleep(0.2)

    return repositorios[:1000]