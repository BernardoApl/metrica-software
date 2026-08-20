"""RQ10 - validacao dos  RQ03, RQ04 e RQ05 nos 1.000 repositorios."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap import DIRETORIO_DADOS, configurar_caminhos  # noqa: E402

configurar_caminhos()

import rq04_atualizacao  # noqa: E402
import rq05_linguagem  # noqa: E402
from linguagens_populares import ReferenciaLinguagens  # noqa: E402


ENTRADA_PADRAO = DIRETORIO_DADOS / "lab01s01_unificado.json"
STATUS_RQ04 = {
    rq04_atualizacao.STATUS_OK,
    rq04_atualizacao.STATUS_SEM_PUSH,
    rq04_atualizacao.STATUS_DATA_INVALIDA,
    rq04_atualizacao.STATUS_DATA_FUTURA,
}


def carregar(caminho: Path) -> dict:
    with open(caminho, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def _numero_nao_negativo(valor) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and valor >= 0


def _inteiro_nao_negativo(valor) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool) and valor >= 0


def _estatisticas(valores: list[int]) -> dict:
    return {
        "media": round(statistics.fmean(valores), 2),
        "mediana": round(statistics.median(valores), 2),
        "minimo": min(valores),
        "maximo": max(valores),
    }


def validar(resultado: dict, quantidade: int = 1000) -> dict:
    metadados = resultado["metadados"]
    repositorios = resultado["repositorios"]
    resumo = resultado["resumo"]

    for campo in (
        "quantidade_graphql",
        "quantidade_rest",
        "quantidade_em_ambas_as_buscas",
        "quantidade_unificada",
    ):
        assert metadados.get(campo) == quantidade, "%s deve ser %d" % (campo, quantidade)
    assert len(repositorios) == quantidade, "snapshot nao possui 1.000 repositorios"

    nomes = [registro.get("nome_completo") for registro in repositorios]
    assert all(isinstance(nome, str) and nome.strip() for nome in nomes), "repositorio sem nome"
    assert len(set(nomes)) == quantidade, "repositorios duplicados"

    estrelas = [registro.get("estrelas") for registro in repositorios]
    assert all(_inteiro_nao_negativo(valor) for valor in estrelas), "estrelas invalidas"
    assert estrelas == sorted(estrelas, reverse=True), "repositorios fora da ordem de estrelas"

    releases = []
    divergencias_rq03 = 0
    ausentes_rq03_rest = 0
    registros_rq05 = []

    for registro in repositorios:
        nome = registro["nome_completo"]
        assert registro.get("presente_na_busca_graphql") is True, "%s ausente na busca GraphQL" % nome
        assert registro.get("presente_na_busca_rest") is True, "%s ausente na busca REST" % nome

        total_releases = registro.get("rq03_total_releases")
        total_graphql = registro.get("rq03_total_releases_graphql")
        assert _inteiro_nao_negativo(total_graphql), "%s com RQ03 GraphQL invalida" % nome
        if total_releases is None:
            ausentes_rq03_rest += 1
        else:
            assert _inteiro_nao_negativo(total_releases), "%s com RQ03 REST invalida" % nome
            releases.append(total_releases)
            divergencias_rq03 += total_releases != total_graphql

        status = registro.get("rq04_status")
        dias = registro.get("rq04_dias_desde_ultima_atualizacao")
        assert status in STATUS_RQ04, "%s com status RQ04 invalido" % nome
        if status in (rq04_atualizacao.STATUS_SEM_PUSH, rq04_atualizacao.STATUS_DATA_INVALIDA):
            assert dias is None, "%s deveria estar sem metrica RQ04" % nome
        else:
            assert _numero_nao_negativo(dias), "%s com dias da RQ04 invalidos" % nome
        if status == rq04_atualizacao.STATUS_DATA_FUTURA:
            assert dias == 0.0, "%s com data futura nao limitada a zero" % nome

        linguagem = registro.get("rq05_linguagem_primaria")
        categoria = registro.get("rq05_categoria_linguagem")
        if linguagem is None:
            assert categoria == rq05_linguagem.SEM_LINGUAGEM, "%s com categoria RQ05 invalida" % nome
            no_linguagem = {"primaryLanguage": None}
        else:
            assert isinstance(linguagem, str) and linguagem.strip(), "%s com linguagem RQ05 invalida" % nome
            assert categoria == linguagem, "%s com linguagem e categoria RQ05 divergentes" % nome
            no_linguagem = {"primaryLanguage": {"name": linguagem}}

        validado_rq05 = dict(registro)
        validado_rq05.update(rq05_linguagem.calcular(no_linguagem, REFERENCIA_LINGUAGENS))
        registros_rq05.append(validado_rq05)

    assert resumo.get("rq03_total_releases") == _estatisticas(releases), "resumo da RQ03 divergente"
    assert resumo.get("rq04") == rq04_atualizacao.resumir(repositorios), "resumo da RQ04 divergente"
    assert resumo.get("rq05") == rq05_linguagem.resumir(registros_rq05), "resumo da RQ05 divergente"

    return {
        "repositorios_validados": len(repositorios),
        "ausentes_rq03_rest": ausentes_rq03_rest,
        "divergencias_rest_graphql_rq03": divergencias_rq03,
    }


REFERENCIA_LINGUAGENS = ReferenciaLinguagens.carregar()


def principal(argv=None) -> int:
    analisador = argparse.ArgumentParser(
        description="Valida RQ03, RQ04 e RQ05 nos 1.000 repositorios da coleta unificada."
    )
    analisador.add_argument("--entrada", type=Path, default=ENTRADA_PADRAO)
    argumentos = analisador.parse_args(argv)

    try:
        resultado = carregar(argumentos.entrada)
        diagnostico = validar(resultado)
    except (AssertionError, OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as erro:
        print("[falha] %s" % erro, file=sys.stderr)
        return 1

    print("RQ03, RQ04 e RQ05 validadas em %d repositorios." % diagnostico["repositorios_validados"])
    print(
        "RQ03: %d valor(es) REST ausente(s) e %d divergencia(s) informativa(s) entre REST e GraphQL."
        % (
            diagnostico["ausentes_rq03_rest"],
            diagnostico["divergencias_rest_graphql_rq03"],
        )
    )
    print("RQ04: campos, status e resumo validados.")
    print("RQ05: linguagens, categorias, referencia e resumo validados.")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
