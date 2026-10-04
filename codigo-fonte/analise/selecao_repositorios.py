"""Seleciona repositorios analisaveis e gera um funil auditavel da selecao.

O script parte do snapshot unificado do LAB01. Um repositorio so entra na
amostra final quando foi encontrado nas coletas REST e GraphQL, possui
identificacao valida e tem as metricas centrais necessarias para as analises
(idade, PRs aceitos, releases e dias desde o ultimo push) em valores validos.

Campos que podem ser naturalmente ausentes, como linguagem primaria e a razao
de issues fechadas para repositorios sem issues, permanecem na amostra.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[2]
ENTRADA_PADRAO = RAIZ / "dados" / "lab01s01_unificado.json"
SAIDA_SELECIONADOS_PADRAO = RAIZ / "dados" / "repositorios_selecionados.csv"
SAIDA_FUNIL_PADRAO = RAIZ / "dados" / "funil_selecao_repositorios.csv"

METRICAS_NUCLEARES = (
    "rq01_idade_anos",
    "rq02_pull_requests_aceitos",
    "rq03_total_releases",
    "rq04_dias_desde_ultima_atualizacao",
)
COLUNAS_SELECIONADOS = (
    "nome_completo", "url", "estrelas", "rq01_idade_anos",
    "rq02_pull_requests_aceitos", "rq03_total_releases",
    "rq04_dias_desde_ultima_atualizacao", "rq05_linguagem_primaria",
    "rq06_razao_fechadas_total",
)
COLUNAS_FUNIL = ("etapa", "criterio", "entrada", "removidos_na_etapa", "aprovados")


def numero_valido(valor: object) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and valor >= 0


def presente_nas_duas_fontes(repositorio: dict) -> bool:
    return bool(repositorio.get("presente_na_busca_graphql")) and bool(
        repositorio.get("presente_na_busca_rest")
    )


def identificacao_valida(repositorio: dict) -> bool:
    return (
        isinstance(repositorio.get("nome_completo"), str)
        and bool(repositorio["nome_completo"].strip())
        and isinstance(repositorio.get("url"), str)
        and bool(repositorio["url"].strip())
        and numero_valido(repositorio.get("estrelas"))
    )


def metricas_nucleares_validas(repositorio: dict) -> bool:
    return (
        repositorio.get("rq04_status") == "ok"
        and all(numero_valido(repositorio.get(campo)) for campo in METRICAS_NUCLEARES)
    )


def aplicar_etapa(repositorios: list[dict], nome: str, criterio: str, predicado) -> tuple[list[dict], dict]:
    aprovados = [repositorio for repositorio in repositorios if predicado(repositorio)]
    return aprovados, {
        "etapa": nome,
        "criterio": criterio,
        "entrada": len(repositorios),
        "removidos_na_etapa": len(repositorios) - len(aprovados),
        "aprovados": len(aprovados),
    }


def selecionar(repositorios: list[dict], limite: int | None = None) -> tuple[list[dict], list[dict]]:
    """Aplica os criterios em sequencia e devolve amostra e funil."""
    if limite is not None and limite < 1:
        raise ValueError("O limite precisa ser maior que zero.")

    funil = [{
        "etapa": "candidatos_iniciais",
        "criterio": "repositorios presentes no snapshot unificado",
        "entrada": len(repositorios),
        "removidos_na_etapa": 0,
        "aprovados": len(repositorios),
    }]
    atuais, etapa = aplicar_etapa(
        repositorios, "presentes_nas_duas_coletas",
        "presente na GraphQL e na REST", presente_nas_duas_fontes,
    )
    funil.append(etapa)
    atuais, etapa = aplicar_etapa(
        atuais, "identificacao_valida",
        "nome, URL e estrelas validos", identificacao_valida,
    )
    funil.append(etapa)
    atuais, etapa = aplicar_etapa(
        atuais, "metricas_nucleares_validas",
        "idade, PRs, releases e ultimo push validos; status RQ04 igual a ok",
        metricas_nucleares_validas,
    )
    funil.append(etapa)

    selecionados = sorted(
        atuais,
        key=lambda repositorio: (-repositorio["estrelas"], repositorio["nome_completo"].casefold()),
    )
    if limite is not None:
        antes_do_limite = len(selecionados)
        selecionados = selecionados[:limite]
        funil.append({
            "etapa": "limite_da_amostra",
            "criterio": "primeiros %d por numero de estrelas" % limite,
            "entrada": antes_do_limite,
            "removidos_na_etapa": antes_do_limite - len(selecionados),
            "aprovados": len(selecionados),
        })
    return selecionados, funil


def carregar_repositorios(caminho: Path) -> list[dict]:
    with caminho.open(encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    repositorios = dados.get("repositorios")
    if not isinstance(repositorios, list):
        raise ValueError("O JSON precisa conter uma lista no campo 'repositorios'.")
    return repositorios


def salvar_csv(caminho: Path, linhas: list[dict], colunas: tuple[str, ...]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=colunas, extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(linhas)


def principal(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entrada", type=Path, default=ENTRADA_PADRAO)
    parser.add_argument("--saida-selecionados", type=Path, default=SAIDA_SELECIONADOS_PADRAO)
    parser.add_argument("--saida-funil", type=Path, default=SAIDA_FUNIL_PADRAO)
    parser.add_argument("--limite", type=int, default=None,
                        help="Limita a amostra aos repositorios com mais estrelas.")
    args = parser.parse_args(argv)

    try:
        selecionados, funil = selecionar(carregar_repositorios(args.entrada), args.limite)
    except (OSError, ValueError, json.JSONDecodeError) as erro:
        parser.error(str(erro))

    salvar_csv(args.saida_selecionados, selecionados, COLUNAS_SELECIONADOS)
    salvar_csv(args.saida_funil, funil, COLUNAS_FUNIL)
    print("Repositorios selecionados: %d" % len(selecionados))
    for etapa in funil:
        print("- %s: %d aprovados" % (etapa["etapa"], etapa["aprovados"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
