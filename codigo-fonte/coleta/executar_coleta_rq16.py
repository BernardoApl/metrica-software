"""Coleta e calcula a RQ16: pull requests aceitas x quantidade de releases.

Reaproveita o fragmento ``CAMPOS_RQ07`` de ``consulta.py`` -- nao ha campo
GraphQL novo para esta RQ, so a combinacao dos dois resultados que a RQ07 ja
usa para agrupar por linguagem.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap import DIRETORIO_DADOS, configurar_caminhos  # noqa: E402

configurar_caminhos()

import rq07_por_linguagem  # noqa: E402
import rq16_prs_releases  # noqa: E402
from cliente_github import ClienteGitHub, ErroGitHub, obter_token  # noqa: E402
from consulta import (  # noqa: E402
    BUSCA_PADRAO,
    CAMPOS_IDENTIFICACAO,
    CAMPOS_RQ07,
    montar_consulta,
    montar_variaveis,
)

SAIDA_PADRAO = DIRETORIO_DADOS / "lab01s01_rq16.json"


def coletar_rq16(cliente: ClienteGitHub, quantidade: int = 100, busca: str = BUSCA_PADRAO) -> dict:
    consulta = montar_consulta((CAMPOS_IDENTIFICACAO, CAMPOS_RQ07))
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
        registro.update(rq07_por_linguagem.extrair_metricas_base(no))
        registro["bruto"] = no
        repositorios.append(registro)

    return {
        "metadados": {
            "coletado_em": datetime.now(timezone.utc).isoformat(),
            "criterio_busca": busca,
            "quantidade_solicitada": quantidade,
            "quantidade_retornada": len(repositorios),
            "total_disponivel_na_busca": busca_resultado.get("repositoryCount"),
            "rate_limit": cliente.ultimo_rate_limit,
            "consulta_graphql": consulta,
            "definicao_rq16": rq16_prs_releases.definicao(),
        },
        "repositorios": repositorios,
        "resumo": {"rq16": rq16_prs_releases.resumir(repositorios)},
    }


def montar_argumentos(argv=None) -> argparse.Namespace:
    analisador = argparse.ArgumentParser(description="Coleta e calcula a RQ16.")
    analisador.add_argument("--quantidade", type=int, default=100)
    analisador.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    analisador.add_argument("--token", default=None)
    analisador.add_argument("--busca", default=BUSCA_PADRAO)
    return analisador.parse_args(argv)


def principal(argv=None) -> int:
    argumentos = montar_argumentos(argv)
    try:
        cliente = ClienteGitHub(obter_token(argumentos.token))
        resultado = coletar_rq16(cliente, argumentos.quantidade, argumentos.busca)
    except (ValueError, ErroGitHub) as erro:
        print("[erro] %s" % erro, file=sys.stderr)
        return 1

    argumentos.saida.parent.mkdir(parents=True, exist_ok=True)
    with open(argumentos.saida, "w", encoding="utf-8") as arquivo:
        json.dump(resultado, arquivo, ensure_ascii=False, indent=2)

    resumo = resultado["resumo"]["rq16"]
    print("Repositorios coletados: %d" % resultado["metadados"]["quantidade_retornada"])
    print("Pares utilizados: %d | Descartados: %d" % (
        resumo["pares_utilizados"], resumo["descartados_sem_par_completo"]))
    print("Coeficiente de Pearson: %s (%s)" % (
        resumo["coeficiente_correlacao_pearson"], resumo["interpretacao"]))
    for faixa, grupo in resumo["por_faixa_de_releases"].items():
        print("  %s: %d repositorios, media %s PRs" % (
            faixa, grupo["quantidade_repositorios"], grupo["media_prs_aceitas"]))
    print("Saida: %s" % argumentos.saida)

    return 0 if resultado["metadados"]["quantidade_retornada"] == argumentos.quantidade else 1


if __name__ == "__main__":
    sys.exit(principal())
