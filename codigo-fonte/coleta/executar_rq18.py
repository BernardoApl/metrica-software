"""Executa a RQ18 a partir do resultado ja produzido pela RQ17.

Nao faz nova coleta e nao duplica o JSON grande da RQ17. O script le
``dados/rq17_resultados.json`` e gera:

- ``dados/rq18_idade_issues_fechadas.svg``;
- ``entregas/laboratorio-01/sprint-02/RQ18.md``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap import DIRETORIO_DADOS, RAIZ_PROJETO, configurar_caminhos  # noqa: E402

configurar_caminhos()

import rq18_visualizacao_idade_issues as rq18  # noqa: E402


ENTRADA_PADRAO = DIRETORIO_DADOS / "rq17_resultados.json"
SAIDA_SVG_PADRAO = DIRETORIO_DADOS / "rq18_idade_issues_fechadas.svg"
SAIDA_MARKDOWN_PADRAO = RAIZ_PROJETO / "entregas" / "laboratorio-01" / "sprint-02" / "RQ18.md"


def carregar_json(caminho: Path) -> dict:
    with open(caminho, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def _fmt(valor, sufixo: str = "") -> str:
    if valor is None:
        return "n/a"
    return "%s%s" % (valor, sufixo)


def montar_markdown(resultado_rq17: dict, caminho_svg: Path) -> str:
    resumo = resultado_rq17["resumo"]
    correlacao = resumo["correlacao"]
    idade = resumo["distribuicao_idade_anos"]
    percentual = resumo["distribuicao_percentual_issues_fechadas"]
    regressao = resumo["regressao_linear"]
    outliers = resumo["outliers"]

    exemplos_outliers = []
    for item in outliers.get("amostra", [])[:5]:
        exemplos_outliers.append(
            "- %s: %.2f anos, %.2f%% de issues fechadas, %s issues totais"
            % (
                item["nome_repositorio"],
                item["idade_anos"],
                item["percentual_issues_fechadas"],
                item["total_issues"],
            )
        )
    if not exemplos_outliers:
        exemplos_outliers.append("- Nenhum outlier relevante identificado pelo metodo IQR.")

    try:
        svg_relativo = caminho_svg.relative_to(RAIZ_PROJETO).as_posix()
    except ValueError:
        svg_relativo = caminho_svg.as_posix()

    return """# RQ18 - Grafico da relacao entre idade e percentual de issues fechadas

## Visualizacao

Arquivo gerado: `{svg}`

O grafico de dispersao utiliza diretamente o resultado da RQ17 (`dados/rq17_resultados.json`). Cada ponto representa um repositorio analisado. O eixo X mostra a idade do repositorio em anos e o eixo Y mostra o percentual de issues fechadas.

## Registros usados

- Repositorios no snapshot original: {total}
- Repositorios plotados: {analisados}
- Registros descartados ou ausentes: {descartados}
- Motivos de descarte/status: `{status}`

Os 43 registros descartados sao repositorios sem issues, para os quais a RQ06 manteve a razao como nula e evitou divisao por zero.

## Principais valores observados

- Idade: minimo {idade_min} anos, mediana {idade_mediana} anos, media {idade_media} anos e maximo {idade_max} anos.
- Percentual de issues fechadas: minimo {perc_min}%, mediana {perc_mediana}%, media {perc_media}% e maximo {perc_max}%.

## Tendencia e correlacao

- Pearson: {pearson} ({pearson_texto})
- Spearman: {spearman} ({spearman_texto})
- Linha de tendencia: {inclinacao} ponto(s) percentual(is) por ano

A linha de tendencia foi incluida como referencia visual, mas a correlacao e fraca positiva. Portanto, ela nao deve ser lida como explicacao forte do comportamento dos repositorios.

## Outliers

Metodo: {metodo_outlier}. Foram identificados {qtd_outliers} outlier(s), principalmente repositorios com percentual de fechamento baixo em relacao ao conjunto.

{outliers}

## Conclusao

Hipotese: **{hipotese}**.

{conclusao}
""".format(
        svg=svg_relativo,
        total=resumo["total_repositorios"],
        analisados=resumo["repositorios_analisados"],
        descartados=resumo["registros_descartados_ou_ausentes"],
        status=resumo["por_status"],
        idade_min=idade["minimo"],
        idade_mediana=idade["mediana"],
        idade_media=idade["media"],
        idade_max=idade["maximo"],
        perc_min=percentual["minimo"],
        perc_mediana=percentual["mediana"],
        perc_media=percentual["media"],
        perc_max=percentual["maximo"],
        pearson=correlacao["pearson"],
        pearson_texto=correlacao["interpretacao_pearson"],
        spearman=correlacao["spearman"],
        spearman_texto=correlacao["interpretacao_spearman"],
        inclinacao=_fmt(regressao.get("variacao_pontos_percentuais_por_ano")),
        metodo_outlier=outliers["metodo"],
        qtd_outliers=outliers["quantidade"],
        outliers="\n".join(exemplos_outliers),
        hipotese=resumo["hipotese"],
        conclusao=resumo["conclusao"],
    )


def escrever_markdown(resultado_rq17: dict, caminho_svg: Path, caminho_markdown: Path) -> Path:
    caminho_markdown.parent.mkdir(parents=True, exist_ok=True)
    caminho_markdown.write_text(montar_markdown(resultado_rq17, caminho_svg), encoding="utf-8")
    return caminho_markdown


def montar_argumentos(argv=None) -> argparse.Namespace:
    analisador = argparse.ArgumentParser(
        description="Gera o grafico e a interpretacao da RQ18 a partir da RQ17."
    )
    analisador.add_argument("--entrada", type=Path, default=ENTRADA_PADRAO)
    analisador.add_argument("--saida-svg", type=Path, default=SAIDA_SVG_PADRAO)
    analisador.add_argument("--saida-md", type=Path, default=SAIDA_MARKDOWN_PADRAO)
    return analisador.parse_args(argv)


def principal(argv=None) -> int:
    argumentos = montar_argumentos(argv)

    try:
        resultado_rq17 = carregar_json(argumentos.entrada)
        rq18.salvar_svg(resultado_rq17, argumentos.saida_svg)
        escrever_markdown(resultado_rq17, argumentos.saida_svg, argumentos.saida_md)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as erro:
        print("[erro] %s" % erro, file=sys.stderr)
        return 1

    resumo = resultado_rq17["resumo"]
    print("RQ18 concluida usando: %s" % argumentos.entrada)
    print("Repositorios plotados: %s" % resumo["repositorios_analisados"])
    print("Descartados/ausentes: %s" % resumo["registros_descartados_ou_ausentes"])
    print("Grafico: %s" % argumentos.saida_svg)
    print("Texto para relatorio: %s" % argumentos.saida_md)
    return 0


if __name__ == "__main__":
    sys.exit(principal())
