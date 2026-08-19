"""Confere a RQ07 em uma amostra real de 5 a 10 repositorios."""

from __future__ import annotations

import argparse
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap import configurar_caminhos  # noqa: E402

configurar_caminhos()

from cliente_github import ClienteGitHub, ErroGitHub, obter_token  # noqa: E402
from executar_coleta_rq07 import coletar_rq07  # noqa: E402


def _estatisticas(valores: list[float]) -> dict:
    if not valores:
        return {"media": None, "mediana": None, "minimo": None, "maximo": None}
    return {
        "media": round(statistics.fmean(valores), 4),
        "mediana": round(statistics.median(valores), 4),
        "minimo": min(valores),
        "maximo": max(valores),
    }


def validar(resultado: dict, quantidade: int) -> None:
    repositorios = resultado["repositorios"]
    assert len(repositorios) == quantidade, "quantidade retornada diferente da solicitada"

    nomes = [r["nome_completo"] for r in repositorios]
    assert all(nomes), "repositorio sem nome"
    assert len(set(nomes)) == quantidade, "repositorios duplicados"

    estrelas = [r["estrelas"] for r in repositorios]
    assert estrelas == sorted(estrelas, reverse=True), "resultado fora da ordem de estrelas"

    for registro in repositorios:
        bruto = registro["bruto"]
        linguagem = (bruto.get("primaryLanguage") or {}).get("name")
        assert registro["rq05_linguagem_primaria"] == linguagem
        assert registro["rq02_pull_requests_aceitos"] == (
            (bruto.get("pullRequestsAceitos") or {}).get("totalCount", 0)
        )
        assert registro["rq03_total_releases"] == (
            (bruto.get("releases") or {}).get("totalCount", 0)
        )

    resumo = resultado["resumo"]["rq07"]
    contagem = Counter(r["rq05_categoria_linguagem"] for r in repositorios)
    assert sum(grupo["quantidade_repositorios"] for grupo in resumo.values()) == quantidade

    campos = (
        "rq02_pull_requests_aceitos",
        "rq03_total_releases",
        "rq04_dias_desde_ultima_atualizacao",
    )
    for linguagem, total in contagem.items():
        grupo = resumo[linguagem]
        assert grupo["quantidade_repositorios"] == total
        itens = [r for r in repositorios if r["rq05_categoria_linguagem"] == linguagem]
        for campo in campos:
            valores = [r[campo] for r in itens if isinstance(r.get(campo), (int, float))]
            assert grupo[campo] == _estatisticas(valores)


def principal(argv=None) -> int:
    analisador = argparse.ArgumentParser(description="Valida a RQ07 na API real do GitHub.")
    analisador.add_argument("--quantidade", type=int, default=8)
    analisador.add_argument("--token", default=None)
    argumentos = analisador.parse_args(argv)
    if not 5 <= argumentos.quantidade <= 10:
        analisador.error("--quantidade deve estar entre 5 e 10")

    try:
        resultado = coletar_rq07(
            ClienteGitHub(obter_token(argumentos.token)),
            quantidade=argumentos.quantidade,
        )
        validar(resultado, argumentos.quantidade)
    except (AssertionError, ErroGitHub) as erro:
        print("[falha] %s" % erro, file=sys.stderr)
        return 1

    print("RQ07 validada em %d repositorios." % argumentos.quantidade)
    print("Grupos de linguagem: %d" % len(resultado["resumo"]["rq07"]))
    return 0


if __name__ == "__main__":
    sys.exit(principal())
