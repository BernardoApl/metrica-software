"""Valida a RQ06 em uma amostra real de 5 a 10 repositorios."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap import configurar_caminhos  # noqa: E402

configurar_caminhos()

from cliente_github import ClienteGitHub, ErroGitHub, obter_token  # noqa: E402
from executar_coleta_rq06 import coletar_rq06  # noqa: E402


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
        total = (bruto.get("issues") or {}).get("totalCount", 0)
        fechadas = (bruto.get("issuesFechadas") or {}).get("totalCount", 0)
        esperado = round(fechadas / total, 4) if total else None
        assert registro["rq06_issues_total"] == total
        assert registro["rq06_issues_fechadas"] == fechadas
        assert registro["rq06_razao_fechadas_total"] == esperado


def principal(argv=None) -> int:
    analisador = argparse.ArgumentParser(description="Valida a RQ06 na API real do GitHub.")
    analisador.add_argument("--quantidade", type=int, default=8)
    analisador.add_argument("--token", default=None)
    argumentos = analisador.parse_args(argv)
    if not 5 <= argumentos.quantidade <= 10:
        analisador.error("--quantidade deve estar entre 5 e 10")

    try:
        resultado = coletar_rq06(
            ClienteGitHub(obter_token(argumentos.token)),
            quantidade=argumentos.quantidade,
        )
        validar(resultado, argumentos.quantidade)
    except (AssertionError, ErroGitHub) as erro:
        print("[falha] %s" % erro, file=sys.stderr)
        return 1

    print("RQ06 validada em %d repositorios." % argumentos.quantidade)
    print(resultado["resumo"]["rq06"])
    return 0


if __name__ == "__main__":
    sys.exit(principal())
