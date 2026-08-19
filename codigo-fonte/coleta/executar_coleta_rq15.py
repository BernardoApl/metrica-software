"""Coleta e calcula a RQ15: idade do repositorio x percentual de issues fechadas.

Reaproveita os campos ja definidos para RQ01 (``CAMPOS_RQ01``) e RQ06
(``CAMPOS_RQ06``) -- nao ha campo GraphQL novo para esta RQ, so a combinacao
dos dois resultados.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap import DIRETORIO_DADOS, configurar_caminhos  # noqa: E402

configurar_caminhos()

import rq01_idade_graphql  # noqa: E402
import rq06_issues  # noqa: E402
import rq15_idade_issues_fechadas  # noqa: E402
from cliente_github import ClienteGitHub, ErroGitHub, obter_token  # noqa: E402
from consulta import (  # noqa: E402
    BUSCA_PADRAO,
    CAMPOS_IDENTIFICACAO,
    CAMPOS_RQ01,
    CAMPOS_RQ06,
    montar_consulta,
    montar_variaveis,
)
from rq04_atualizacao import agora_utc  # noqa: E402

SAIDA_PADRAO = DIRETORIO_DADOS / "lab01s01_rq15.json"


def coletar_rq15(cliente: ClienteGitHub, quantidade: int = 100, busca: str = BUSCA_PADRAO) -> dict:
    referencia_data = agora_utc()
    consulta = montar_consulta((CAMPOS_IDENTIFICACAO, CAMPOS_RQ01, CAMPOS_RQ06))
    dados = cliente.executar(consulta, montar_variaveis(quantidade, busca=busca))
    busca_resultado = dados.get("search") or {}
    nos = [no for no in (busca_resultado.get("nodes") or []) if no]

    repositorios = []
    for no in nos:
        registro = {
            "nome_completo": no.get("nameWithOwner"),
            "url": no.get("url"),
            "estrelas": no.get("stargazerCount"),
        }
        registro.update(rq01_idade_graphql.calcular(no, referencia_data))
        registro.update(rq06_issues.calcular(no))
        registro["bruto"] = no
        repositorios.append(registro)

    return {
        "metadados": {
            "coletado_em": referencia_data.isoformat(),
            "criterio_busca": busca,
            "quantidade_solicitada": quantidade,
            "quantidade_retornada": len(repositorios),
            "total_disponivel_na_busca": busca_resultado.get("repositoryCount"),
            "rate_limit": cliente.ultimo_rate_limit,
            "consulta_graphql": consulta,
            "definicao_rq01": rq01_idade_graphql.definicao(),
            "definicao_rq06": rq06_issues.definicao(),
            "definicao_rq15": rq15_idade_issues_fechadas.definicao(),
        },
        "repositorios": repositorios,
        "resumo": {
            "rq01": rq01_idade_graphql.resumir(repositorios),
            "rq06": rq06_issues.resumir(repositorios),
            "rq15": rq15_idade_issues_fechadas.resumir(repositorios),
        },
    }


def montar_argumentos(argv=None) -> argparse.Namespace:
    analisador = argparse.ArgumentParser(description="Coleta e calcula a RQ15.")
    analisador.add_argument("--quantidade", type=int, default=100)
    analisador.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    analisador.add_argument("--token", default=None)
    analisador.add_argument("--busca", default=BUSCA_PADRAO)
    return analisador.parse_args(argv)


def principal(argv=None) -> int:
    argumentos = montar_argumentos(argv)
    try:
        cliente = ClienteGitHub(obter_token(argumentos.token))
        resultado = coletar_rq15(cliente, argumentos.quantidade, argumentos.busca)
    except (ValueError, ErroGitHub) as erro:
        print("[erro] %s" % erro, file=sys.stderr)
        return 1

    argumentos.saida.parent.mkdir(parents=True, exist_ok=True)
    with open(argumentos.saida, "w", encoding="utf-8") as arquivo:
        json.dump(resultado, arquivo, ensure_ascii=False, indent=2)

    resumo = resultado["resumo"]["rq15"]
    print("Repositorios coletados: %d" % resultado["metadados"]["quantidade_retornada"])
    print("Pares utilizados: %d | Descartados: %d" % (
        resumo["pares_utilizados"], resumo["descartados_sem_par_completo"]))
    print("Coeficiente de Pearson: %s (%s)" % (
        resumo["coeficiente_correlacao_pearson"], resumo["interpretacao"]))
    for faixa, grupo in resumo["por_faixa_de_idade"].items():
        print("  %s: %d repositorios, media %s" % (
            faixa, grupo["quantidade_repositorios"], grupo["media_razao_fechadas"]))
    print("Saida: %s" % argumentos.saida)

    return 0 if resultado["metadados"]["quantidade_retornada"] == argumentos.quantidade else 1


if __name__ == "__main__":
    sys.exit(principal())
