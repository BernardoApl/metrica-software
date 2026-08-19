"""Valida RQ01 e RQ02, requisitos definidos na Sprint 1, nos 1.000 repositorios."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap import DIRETORIO_DADOS, configurar_caminhos  # noqa: E402

configurar_caminhos()

import rq01_idade_graphql  # noqa: E402
import rq02_pull_requests_graphql  # noqa: E402
from rq04_atualizacao import analisar_iso8601  # noqa: E402


ENTRADA_PADRAO = DIRETORIO_DADOS / "lab01s02_1000.local.json"


def carregar(caminho: Path) -> dict:
    with open(caminho, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def validar(resultado: dict, quantidade: int = 1000) -> None:
    metadados = resultado["metadados"]
    repositorios = resultado["repositorios"]

    assert metadados["quantidade_solicitada"] == quantidade, "quantidade solicitada incorreta"
    assert metadados["quantidade_retornada"] == quantidade, "quantidade retornada incorreta"
    assert len(repositorios) == quantidade, "snapshot nao possui 1.000 repositorios"

    nomes = [registro.get("nome_completo") for registro in repositorios]
    assert all(nomes), "repositorio sem nome"
    assert len(set(nomes)) == quantidade, "repositorios duplicados"

    estrelas = [registro.get("estrelas") for registro in repositorios]
    assert all(isinstance(valor, int) and valor >= 0 for valor in estrelas), "estrelas invalidas"
    assert estrelas == sorted(estrelas, reverse=True), "repositorios fora da ordem de estrelas"

    referencia = analisar_iso8601(metadados.get("coletado_em"))
    assert referencia is not None, "data de referencia da coleta invalida"

    for registro in repositorios:
        bruto = registro.get("bruto") or {}
        criada_em = analisar_iso8601(bruto.get("createdAt"))
        assert criada_em is not None, "%s sem createdAt valido" % registro["nome_completo"]

        idade_dias = (referencia - criada_em).total_seconds() / rq01_idade_graphql.SEGUNDOS_POR_DIA
        assert registro.get("rq01_campo_utilizado") == rq01_idade_graphql.CAMPO_OFICIAL
        assert registro.get("rq01_data_criacao") == bruto.get("createdAt")
        assert registro.get("rq01_idade_dias") == round(idade_dias, 2)
        assert registro.get("rq01_idade_anos") == round(
            idade_dias / rq01_idade_graphql.DIAS_POR_ANO,
            2,
        )
        assert registro.get("rq01_status") == rq01_idade_graphql.STATUS_OK

        conexao_prs = bruto.get("pullRequestsAceitos")
        assert isinstance(conexao_prs, dict), "%s sem dados de pull requests" % registro["nome_completo"]
        total_prs = conexao_prs.get("totalCount")
        assert isinstance(total_prs, int) and total_prs >= 0, "total de pull requests invalido"
        assert registro.get("rq02_pull_requests_aceitos_graphql") == total_prs
        assert registro.get("rq02_status_graphql") == "ok"

    assert resultado["resumo"]["rq01"] == rq01_idade_graphql.resumir(repositorios)
    assert resultado["resumo"]["rq02"] == rq02_pull_requests_graphql.resumir(repositorios)


def principal(argv=None) -> int:
    analisador = argparse.ArgumentParser(description="Valida os requisitos RQ01 e RQ02 da Sprint 1 nos 1.000 repositorios.")
    analisador.add_argument("--entrada", type=Path, default=ENTRADA_PADRAO)
    argumentos = analisador.parse_args(argv)

    try:
        resultado = carregar(argumentos.entrada)
        validar(resultado)
    except (AssertionError, OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as erro:
        print("[falha] %s" % erro, file=sys.stderr)
        return 1

    print("Requisitos da Sprint 1 validados: RQ01 e RQ02 em 1.000 repositorios.")
    print("RQ01: %s" % resultado["resumo"]["rq01"])
    print("RQ02: %s" % resultado["resumo"]["rq02"])
    return 0


if __name__ == "__main__":
    sys.exit(principal())
