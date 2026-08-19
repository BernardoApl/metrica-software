"""Confere a RQ16 em uma amostra real de 5 a 10 repositorios."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap import configurar_caminhos  # noqa: E402

configurar_caminhos()

import rq16_prs_releases  # noqa: E402
from cliente_github import ClienteGitHub, ErroGitHub, obter_token  # noqa: E402
from executar_coleta_rq16 import coletar_rq16  # noqa: E402


def validar(resultado: dict, quantidade: int) -> None:
    repositorios = resultado["repositorios"]
    assert len(repositorios) == quantidade, "quantidade retornada diferente da solicitada"

    nomes = [r["nome_completo"] for r in repositorios]
    assert all(nomes), "repositorio sem nome"
    assert len(set(nomes)) == quantidade, "repositorios duplicados"

    for registro in repositorios:
        bruto = registro["bruto"]
        prs_esperadas = (bruto.get("pullRequestsAceitos") or {}).get("totalCount", 0)
        releases_esperados = (bruto.get("releases") or {}).get("totalCount", 0)
        assert registro["rq02_pull_requests_aceitos"] == prs_esperadas
        assert registro["rq03_total_releases"] == releases_esperados

    pares_esperados = rq16_prs_releases.extrair_pares(repositorios)
    resumo = resultado["resumo"]["rq16"]
    assert resumo["pares_utilizados"] == len(pares_esperados)
    assert resumo["total_repositorios"] == quantidade
    assert resumo["pares_utilizados"] + resumo["descartados_sem_par_completo"] == quantidade

    coeficiente_esperado = rq16_prs_releases.calcular_correlacao_pearson(pares_esperados)
    assert resumo["coeficiente_correlacao_pearson"] == coeficiente_esperado
    assert resumo["interpretacao"] == rq16_prs_releases.classificar_forca(coeficiente_esperado)

    faixas_esperadas = rq16_prs_releases.agrupar_por_faixa_de_releases(pares_esperados)
    assert resumo["por_faixa_de_releases"] == faixas_esperadas
    soma_faixas = sum(g["quantidade_repositorios"] for g in resumo["por_faixa_de_releases"].values())
    assert soma_faixas == resumo["pares_utilizados"]


def principal(argv=None) -> int:
    analisador = argparse.ArgumentParser(description="Valida a RQ16 na API real do GitHub.")
    analisador.add_argument("--quantidade", type=int, default=8)
    analisador.add_argument("--token", default=None)
    argumentos = analisador.parse_args(argv)
    if not 5 <= argumentos.quantidade <= 10:
        analisador.error("--quantidade deve estar entre 5 e 10")

    try:
        resultado = coletar_rq16(
            ClienteGitHub(obter_token(argumentos.token)),
            quantidade=argumentos.quantidade,
        )
        validar(resultado, argumentos.quantidade)
    except (AssertionError, ErroGitHub) as erro:
        print("[falha] %s" % erro, file=sys.stderr)
        return 1

    print("RQ16 validada em %d repositorios." % argumentos.quantidade)
    print(resultado["resumo"]["rq16"])
    return 0


if __name__ == "__main__":
    sys.exit(principal())
