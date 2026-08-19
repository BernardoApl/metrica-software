"""Coleta e salva os dados agrupados por linguagem para a RQ07."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap import DIRETORIO_DADOS, configurar_caminhos  # noqa: E402

configurar_caminhos()

import rq04_atualizacao  # noqa: E402
import rq05_linguagem  # noqa: E402
import rq07_por_linguagem  # noqa: E402
from cliente_github import ClienteGitHub, ErroGitHub, obter_token  # noqa: E402
from consulta import (  # noqa: E402
    BUSCA_PADRAO,
    CAMPOS_IDENTIFICACAO,
    CAMPOS_RQ04_RQ05,
    CAMPOS_RQ07,
    montar_consulta,
    montar_variaveis,
)
from linguagens_populares import ReferenciaLinguagens  # noqa: E402

SAIDA_PADRAO = DIRETORIO_DADOS / "lab01s01_rq07.json"
TAMANHO_PAGINA_PADRAO = 10


def coletar_rq07(
    cliente: ClienteGitHub,
    quantidade: int = 100,
    busca: str = BUSCA_PADRAO,
    tamanho_pagina: int = TAMANHO_PAGINA_PADRAO,
) -> dict:
    if not isinstance(quantidade, int) or quantidade < 1 or quantidade > 100:
        raise ValueError("A quantidade deve estar entre 1 e 100 nesta sprint.")
    if not isinstance(tamanho_pagina, int) or tamanho_pagina < 1 or tamanho_pagina > 100:
        raise ValueError("O tamanho da pagina deve estar entre 1 e 100.")

    referencia_data = rq04_atualizacao.agora_utc()
    referencia_linguagens = ReferenciaLinguagens.carregar()
    consulta = montar_consulta((CAMPOS_IDENTIFICACAO, CAMPOS_RQ04_RQ05, CAMPOS_RQ07))
    nos = []
    cursor = None
    total_disponivel = None
    requisicoes = 0

    while len(nos) < quantidade:
        por_pagina = min(tamanho_pagina, quantidade - len(nos))
        variaveis = montar_variaveis(por_pagina, busca=busca, cursor=cursor)
        dados = cliente.executar(consulta, variaveis)
        busca_resultado = dados.get("search") or {}
        recebidos = [no for no in (busca_resultado.get("nodes") or []) if no]
        pagina = busca_resultado.get("pageInfo") or {}
        nos.extend(recebidos)
        requisicoes += 1

        if total_disponivel is None:
            total_disponivel = busca_resultado.get("repositoryCount")
        if not recebidos or not pagina.get("hasNextPage"):
            break
        cursor = pagina.get("endCursor")

    repositorios = []
    for no in nos:
        registro = {
            "nome_completo": no.get("nameWithOwner"),
            "url": no.get("url"),
            "estrelas": no.get("stargazerCount"),
        }
        registro.update(rq04_atualizacao.calcular(no, referencia_data))
        registro.update(rq05_linguagem.calcular(no, referencia_linguagens))
        registro.update(rq07_por_linguagem.extrair_metricas_base(no))
        registro["bruto"] = no
        repositorios.append(registro)

    return {
        "metadados": {
            "coletado_em": referencia_data.isoformat(),
            "criterio_busca": busca,
            "quantidade_solicitada": quantidade,
            "quantidade_retornada": len(repositorios),
            "tamanho_pagina": tamanho_pagina,
            "quantidade_requisicoes": requisicoes,
            "total_disponivel_na_busca": total_disponivel,
            "rate_limit": cliente.ultimo_rate_limit,
            "consulta_graphql": consulta,
            "definicao_rq07": rq07_por_linguagem.definicao(),
        },
        "repositorios": repositorios,
        "resumo": {"rq07": rq07_por_linguagem.resumir(repositorios)},
    }


def montar_argumentos(argv=None) -> argparse.Namespace:
    analisador = argparse.ArgumentParser(description="Coleta e calcula a RQ07.")
    analisador.add_argument("--quantidade", type=int, default=100)
    analisador.add_argument("--tamanho-pagina", type=int, default=TAMANHO_PAGINA_PADRAO)
    analisador.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    analisador.add_argument("--token", default=None)
    analisador.add_argument("--busca", default=BUSCA_PADRAO)
    return analisador.parse_args(argv)


def principal(argv=None) -> int:
    argumentos = montar_argumentos(argv)
    try:
        cliente = ClienteGitHub(obter_token(argumentos.token))
        resultado = coletar_rq07(
            cliente,
            argumentos.quantidade,
            argumentos.busca,
            argumentos.tamanho_pagina,
        )
    except (ValueError, ErroGitHub) as erro:
        print("[erro] %s" % erro, file=sys.stderr)
        return 1

    argumentos.saida.parent.mkdir(parents=True, exist_ok=True)
    with open(argumentos.saida, "w", encoding="utf-8") as arquivo:
        json.dump(resultado, arquivo, ensure_ascii=False, indent=2)

    grupos = resultado["resumo"]["rq07"]
    print("Repositorios coletados: %d" % resultado["metadados"]["quantidade_retornada"])
    print("Grupos de linguagem: %d" % len(grupos))
    for linguagem, grupo in list(grupos.items())[:10]:
        print("%s: %d repositorios" % (linguagem, grupo["quantidade_repositorios"]))
    print("Saida: %s" % argumentos.saida)

    return 0 if resultado["metadados"]["quantidade_retornada"] == argumentos.quantidade else 1


if __name__ == "__main__":
    sys.exit(principal())
