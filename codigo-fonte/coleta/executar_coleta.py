"""Ponto de entrada da coleta automatica do Lab01S01 (RQ04 e RQ05).

Uso::

    set GITHUB_TOKEN=ghp_xxx          # Windows (cmd)
    $env:GITHUB_TOKEN = "ghp_xxx"     # Windows (PowerShell)
    export GITHUB_TOKEN=ghp_xxx       # Linux/macOS

    python codigo-fonte/coleta/executar_coleta.py
    python codigo-fonte/coleta/executar_coleta.py --quantidade 100 --saida dados/coleta.json

O token tambem pode vir de um arquivo ``.env`` na raiz do projeto
(``GITHUB_TOKEN=...``) ou da opcao ``--token``. O ``.env`` esta no ``.gitignore``.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap import DIRETORIO_DADOS, configurar_caminhos  # noqa: E402

configurar_caminhos()

import rq04_atualizacao  # noqa: E402
from cliente_github import ClienteGitHub, ErroGitHub, obter_token  # noqa: E402
from coleta_repositorios import coletar  # noqa: E402
from consulta import BUSCA_PADRAO  # noqa: E402
from exportar_csv import escrever_csv, nome_arquivo_semanal  # noqa: E402

SAIDA_PADRAO = DIRETORIO_DADOS / "lab01s01_rq04_rq05.json"


def montar_argumentos(argv=None) -> argparse.Namespace:
    analisador = argparse.ArgumentParser(
        description="Coleta os repositorios mais populares do GitHub e calcula RQ04 e RQ05."
    )
    analisador.add_argument(
        "--quantidade", type=int, default=100,
        help="Quantidade de repositorios a coletar (maximo 100 nesta sprint). Padrao: 100.",
    )
    analisador.add_argument(
        "--saida", type=Path, default=SAIDA_PADRAO,
        help="Arquivo JSON de saida. Padrao: dados/lab01s01_rq04_rq05.json",
    )
    analisador.add_argument(
        "--token", default=None,
        help="Token do GitHub. Se omitido, usa GITHUB_TOKEN/GH_TOKEN ou o arquivo .env.",
    )
    analisador.add_argument(
        "--busca", default=BUSCA_PADRAO,
        help="Criterio de busca do GitHub. Padrao: %s" % BUSCA_PADRAO,
    )
    analisador.add_argument(
        "--csv", action="store_true",
        help="Tambem exporta o snapshot semanal dos repositorios em CSV (RQ14).",
    )
    analisador.add_argument(
        "--csv-saida", type=Path, default=None,
        help="Arquivo CSV de saida. Padrao: dados/rq14_snapshot_semanal_<ano>-W<semana>.csv",
    )
    return analisador.parse_args(argv)


def imprimir_resumo(resultado: dict) -> None:
    metadados = resultado["metadados"]
    rq04 = resultado["resumo"]["rq04"]
    rq05 = resultado["resumo"]["rq05"]

    print("")
    print("=" * 72)
    print("COLETA CONCLUIDA")
    print("=" * 72)
    print("Repositorios coletados : %s de %s solicitados"
          % (metadados["quantidade_retornada"], metadados["quantidade_solicitada"]))
    print("Data de referencia     : %s (UTC)" % metadados["coletado_em"])
    print("Disponiveis na busca   : %s" % metadados["total_disponivel_na_busca"])
    if metadados.get("rate_limit"):
        limite = metadados["rate_limit"]
        print("Rate limit             : custo %s, restam %s de %s (reinicia em %s)"
              % (limite.get("cost"), limite.get("remaining"),
                 limite.get("limit"), limite.get("resetAt")))

    print("")
    print("-- RQ04: tempo ate a ultima atualizacao (campo %s) --" % rq04_atualizacao.CAMPO_OFICIAL)
    print("  Mediana : %s dias" % rq04["mediana_dias"])
    print("  Media   : %s dias" % rq04["media_dias"])
    print("  Faixa   : de %s a %s dias" % (rq04["minimo_dias"], rq04["maximo_dias"]))
    print("  Sem metrica (ausentes): %s" % rq04["sem_metrica"])
    print("  Status  : %s" % rq04["por_status"])

    print("")
    print("-- RQ05: linguagem primaria --")
    print("  Linguagens distintas    : %s" % rq05["linguagens_distintas"])
    print("  Sem linguagem definida  : %s" % rq05["sem_linguagem"])
    print("  Entre as mais populares : %s (%s%%)"
          % (rq05["entre_linguagens_populares"], rq05["percentual_entre_populares"]))
    print("  Top 10 por contagem:")
    for posicao, (linguagem, total) in enumerate(list(rq05["contagem_por_linguagem"].items())[:10], 1):
        print("    %2d. %-24s %3d" % (posicao, linguagem, total))


def principal(argv=None) -> int:
    argumentos = montar_argumentos(argv)

    try:
        token = obter_token(argumentos.token)
    except ErroGitHub as erro:
        print("[erro] %s" % erro, file=sys.stderr)
        return 2

    cliente = ClienteGitHub(token)

    print("Consultando a API GraphQL do GitHub (%d repositorios)..." % argumentos.quantidade)
    try:
        resultado = coletar(cliente, quantidade=argumentos.quantidade, busca=argumentos.busca)
    except ValueError as erro:
        print("[erro] %s" % erro, file=sys.stderr)
        return 2
    except ErroGitHub as erro:
        print("[erro] Falha na coleta: %s" % erro, file=sys.stderr)
        return 1

    saida = Path(argumentos.saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    with open(saida, "w", encoding="utf-8") as arquivo:
        json.dump(resultado, arquivo, ensure_ascii=False, indent=2)

    imprimir_resumo(resultado)
    print("")
    print("Saida gravada em: %s" % saida)

    if argumentos.csv:
        caminho_csv = argumentos.csv_saida
        if caminho_csv is None:
            referencia_data = datetime.fromisoformat(resultado["metadados"]["coletado_em"])
            caminho_csv = nome_arquivo_semanal(referencia_data, DIRETORIO_DADOS)
        escrever_csv(resultado["repositorios"], caminho_csv)
        print("Snapshot semanal (CSV) gravado em: %s" % caminho_csv)

    if resultado["metadados"]["quantidade_retornada"] < argumentos.quantidade:
        print("[aviso] A API devolveu menos repositorios do que o solicitado.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(principal())
