"""Confere a RQ15 em uma amostra real de 5 a 10 repositorios."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap import configurar_caminhos  # noqa: E402

configurar_caminhos()

import rq15_idade_issues_fechadas  # noqa: E402
from cliente_github import ClienteGitHub, ErroGitHub, obter_token  # noqa: E402
from executar_coleta_rq15 import coletar_rq15  # noqa: E402


def validar(resultado: dict, quantidade: int) -> None:
    repositorios = resultado["repositorios"]
    assert len(repositorios) == quantidade, "quantidade retornada diferente da solicitada"

    nomes = [r["nome_completo"] for r in repositorios]
    assert all(nomes), "repositorio sem nome"
    assert len(set(nomes)) == quantidade, "repositorios duplicados"

    for registro in repositorios:
        bruto = registro["bruto"]

        criado_em = bruto.get("createdAt")
        if criado_em is None:
            assert registro["rq01_idade_anos"] is None
        else:
            assert registro["rq01_status"] == "ok"
            assert registro["rq01_idade_anos"] is not None

        total = (bruto.get("issues") or {}).get("totalCount", 0)
        fechadas = (bruto.get("issuesFechadas") or {}).get("totalCount", 0)
        esperado = round(fechadas / total, 4) if total else None
        assert registro["rq06_razao_fechadas_total"] == esperado

    pares_esperados = rq15_idade_issues_fechadas.extrair_pares(repositorios)
    resumo = resultado["resumo"]["rq15"]
    assert resumo["pares_utilizados"] == len(pares_esperados)
    assert resumo["total_repositorios"] == quantidade
    assert resumo["pares_utilizados"] + resumo["descartados_sem_par_completo"] == quantidade

    coeficiente_esperado = rq15_idade_issues_fechadas.calcular_correlacao_pearson(pares_esperados)
    assert resumo["coeficiente_correlacao_pearson"] == coeficiente_esperado
    assert resumo["interpretacao"] == rq15_idade_issues_fechadas.classificar_forca(coeficiente_esperado)

    faixas_esperadas = rq15_idade_issues_fechadas.agrupar_por_faixa_de_idade(pares_esperados)
    assert resumo["por_faixa_de_idade"] == faixas_esperadas
    soma_faixas = sum(g["quantidade_repositorios"] for g in resumo["por_faixa_de_idade"].values())
    assert soma_faixas == resumo["pares_utilizados"]


def principal(argv=None) -> int:
    analisador = argparse.ArgumentParser(description="Valida a RQ15 na API real do GitHub.")
    analisador.add_argument("--quantidade", type=int, default=8)
    analisador.add_argument("--token", default=None)
    argumentos = analisador.parse_args(argv)
    if not 5 <= argumentos.quantidade <= 10:
        analisador.error("--quantidade deve estar entre 5 e 10")

    try:
        resultado = coletar_rq15(
            ClienteGitHub(obter_token(argumentos.token)),
            quantidade=argumentos.quantidade,
        )
        validar(resultado, argumentos.quantidade)
    except (AssertionError, ErroGitHub) as erro:
        print("[falha] %s" % erro, file=sys.stderr)
        return 1

    print("RQ15 validada em %d repositorios." % argumentos.quantidade)
    print(resultado["resumo"]["rq15"])
    return 0


if __name__ == "__main__":
    sys.exit(principal())
