"""Executa a RQ22 a partir do resultado ja produzido pela RQ21.

Nao faz nova coleta e nao duplica o JSON grande da RQ21. O script le
``dados/rq21_resultados.json`` e gera:

- ``dados/rq22_idade_releases.svg``;
- ``entregas/laboratorio-01/sprint-02/RQ22.md``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap import DIRETORIO_DADOS, RAIZ_PROJETO, configurar_caminhos  # noqa: E402

configurar_caminhos()

import rq22_visualizacao_idade_releases as rq22  # noqa: E402


ENTRADA_PADRAO = DIRETORIO_DADOS / "rq21_resultados.json"
SAIDA_SVG_PADRAO = DIRETORIO_DADOS / "rq22_idade_releases.svg"
SAIDA_MARKDOWN_PADRAO = RAIZ_PROJETO / "entregas" / "laboratorio-01" / "sprint-02" / "RQ22.md"


def carregar_json(caminho: Path) -> dict:
    with open(caminho, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def _fmt(valor, sufixo: str = "") -> str:
    if valor is None:
        return "n/a"
    return "%s%s" % (valor, sufixo)


def montar_markdown(resultado_rq21: dict, caminho_svg: Path) -> str:
    resumo = resultado_rq21["resumo"]
    correlacao = resumo["correlacao"]
    idade = resumo["distribuicao_idade_anos"]
    releases = resumo["distribuicao_total_releases"]
    regressao = resumo["regressao_linear"]
    outliers = resumo["outliers"]

    exemplos_outliers = []
    for item in outliers.get("amostra", [])[:5]:
        exemplos_outliers.append(
            "- %s: %.2f anos, %s releases"
            % (
                item["nome_repositorio"],
                item["idade_anos"],
                item["total_releases"],
            )
        )
    if not exemplos_outliers:
        exemplos_outliers.append("- Nenhum outlier relevante identificado pelo metodo IQR.")

    try:
        svg_relativo = caminho_svg.relative_to(RAIZ_PROJETO).as_posix()
    except ValueError:
        svg_relativo = caminho_svg.as_posix()

    return """# RQ22 - Grafico da relacao entre idade e quantidade de releases

## Visualizacao

Arquivo gerado: `{svg}`

O grafico de dispersao utiliza diretamente o resultado da RQ21 (`dados/rq21_resultados.json`). Cada ponto representa um repositorio analisado. O eixo X mostra a idade do repositorio em anos e o eixo Y mostra a quantidade de releases, em escala log10(releases + 1) -- a distribuicao de releases e fortemente assimetrica (mediana de dezenas, mas ate {rel_max} releases em um unico repositorio), e um eixo linear esmagaria quase todos os pontos perto de zero. Os rotulos do eixo Y mostram a quantidade real de releases, nao o valor transformado.

## Registros usados

- Repositorios no snapshot original: {total}
- Repositorios plotados: {analisados}
- Registros descartados ou ausentes: {descartados}
- Motivos de descarte/status: `{status}`

## Principais valores observados

- Idade: minimo {idade_min} anos, mediana {idade_mediana} anos, media {idade_media} anos e maximo {idade_max} anos.
- Total de releases: minimo {rel_min}, mediana {rel_mediana}, media {rel_media} e maximo {rel_max}.

## Tendencia e correlacao

- Pearson: {pearson} ({pearson_texto})
- Spearman: {spearman} ({spearman_texto})
- Linha de tendencia: {inclinacao} release(s) adicionais por ano

A linha de tendencia foi incluida como referencia visual, mas a correlacao e praticamente nula. Portanto, ela nao deve ser lida como explicacao do comportamento dos repositorios -- a quantidade de releases varia por outros fatores (cadencia de versionamento do projeto, maturidade do processo de release) que nao a idade.

## Outliers

Metodo: {metodo_outlier}. Foram identificados {qtd_outliers} outlier(s), principalmente repositorios com quantidade de releases muito acima do restante do conjunto.

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
        rel_min=releases["minimo"],
        rel_mediana=releases["mediana"],
        rel_media=releases["media"],
        rel_max=releases["maximo"],
        pearson=correlacao["pearson"],
        pearson_texto=correlacao["interpretacao_pearson"],
        spearman=correlacao["spearman"],
        spearman_texto=correlacao["interpretacao_spearman"],
        inclinacao=_fmt(regressao.get("releases_adicionais_por_ano")),
        metodo_outlier=outliers["metodo"],
        qtd_outliers=outliers["quantidade"],
        outliers="\n".join(exemplos_outliers),
        hipotese=resumo["hipotese"],
        conclusao=resumo["conclusao"],
    )


def escrever_markdown(resultado_rq21: dict, caminho_svg: Path, caminho_markdown: Path) -> Path:
    caminho_markdown.parent.mkdir(parents=True, exist_ok=True)
    caminho_markdown.write_text(montar_markdown(resultado_rq21, caminho_svg), encoding="utf-8")
    return caminho_markdown


def montar_argumentos(argv=None) -> argparse.Namespace:
    analisador = argparse.ArgumentParser(
        description="Gera o grafico e a interpretacao da RQ22 a partir da RQ21."
    )
    analisador.add_argument("--entrada", type=Path, default=ENTRADA_PADRAO)
    analisador.add_argument("--saida-svg", type=Path, default=SAIDA_SVG_PADRAO)
    analisador.add_argument("--saida-md", type=Path, default=SAIDA_MARKDOWN_PADRAO)
    return analisador.parse_args(argv)


def principal(argv=None) -> int:
    argumentos = montar_argumentos(argv)

    try:
        resultado_rq21 = carregar_json(argumentos.entrada)
        rq22.salvar_svg(resultado_rq21, argumentos.saida_svg)
        escrever_markdown(resultado_rq21, argumentos.saida_svg, argumentos.saida_md)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as erro:
        print("[erro] %s" % erro, file=sys.stderr)
        return 1

    resumo = resultado_rq21["resumo"]
    print("RQ22 concluida usando: %s" % argumentos.entrada)
    print("Repositorios plotados: %s" % resumo["repositorios_analisados"])
    print("Descartados/ausentes: %s" % resumo["registros_descartados_ou_ausentes"])
    print("Grafico: %s" % argumentos.saida_svg)
    print("Texto para relatorio: %s" % argumentos.saida_md)
    return 0


if __name__ == "__main__":
    sys.exit(principal())
