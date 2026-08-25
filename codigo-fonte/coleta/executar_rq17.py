"""Executa a RQ17 usando o snapshot consolidado existente.

Nao faz nova coleta. A entrada padrao e ``dados/lab01s01_unificado.json``, que
ja contem os 1.000 repositorios com RQ01 e RQ06 calculadas.

Saidas padrao:

- ``dados/rq17_resultados.json``: resumo e registros auditaveis;
- ``dados/rq17_idade_issues_fechadas.csv``: tabela usada na analise;
- ``entregas/laboratorio-01/sprint-02/RQ17.md``: texto interpretativo.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap import DIRETORIO_DADOS, RAIZ_PROJETO, configurar_caminhos  # noqa: E402

configurar_caminhos()

import rq17_idade_issues_fechadas as rq17  # noqa: E402


ENTRADA_PADRAO = DIRETORIO_DADOS / "lab01s01_unificado.json"
SAIDA_JSON_PADRAO = DIRETORIO_DADOS / "rq17_resultados.json"
SAIDA_CSV_PADRAO = DIRETORIO_DADOS / "rq17_idade_issues_fechadas.csv"
SAIDA_MARKDOWN_PADRAO = RAIZ_PROJETO / "entregas" / "laboratorio-01" / "sprint-02" / "RQ17.md"


def carregar_json(caminho: Path) -> dict:
    with open(caminho, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def escrever_json(resultado: dict, caminho: Path) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(resultado, arquivo, ensure_ascii=False, indent=2)
    return caminho


def escrever_csv(registros: list[dict], caminho: Path) -> Path:
    if not registros:
        raise ValueError("Nao ha registros da RQ17 para exportar.")
    caminho.parent.mkdir(parents=True, exist_ok=True)
    colunas = list(registros[0].keys())
    with open(caminho, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=colunas)
        escritor.writeheader()
        escritor.writerows(registros)
    return caminho


def _fmt(valor, sufixo: str = "") -> str:
    if valor is None:
        return "n/a"
    return "%s%s" % (valor, sufixo)


def montar_markdown(resultado: dict) -> str:
    resumo = resultado["resumo"]
    correlacao = resumo["correlacao"]
    idade = resumo["distribuicao_idade_anos"]
    percentual = resumo["distribuicao_percentual_issues_fechadas"]
    regressao = resumo["regressao_linear"]
    outliers = resumo["outliers"]
    grupos = resumo["por_faixa_de_idade"]

    linhas_outliers = []
    for item in outliers["amostra"][:5]:
        linhas_outliers.append(
            "- %s: %.2f anos, %.2f%% de issues fechadas, %s issues totais"
            % (
                item["nome_repositorio"],
                item["idade_anos"],
                item["percentual_issues_fechadas"],
                item["total_issues"],
            )
        )
    if not linhas_outliers:
        linhas_outliers.append("- Nenhum outlier identificado pelo metodo IQR.")

    linhas_faixas = []
    for faixa, dados in grupos.items():
        linhas_faixas.append(
            "| %s | %s | %s%% | %s%% |"
            % (
                faixa,
                dados["quantidade_repositorios"],
                _fmt(dados["media_percentual"]),
                _fmt(dados["mediana_percentual"]),
            )
        )

    return """# RQ17 - Idade do repositorio x percentual de issues fechadas

## Analise

Pergunta: repositorios mais antigos tendem a apresentar maior percentual de issues fechadas?

Fonte: `dados/lab01s01_unificado.json`, sem nova coleta. A idade vem da RQ01 (`rq01_idade_anos`) e o percentual de issues fechadas reutiliza a RQ06 (`rq06_razao_fechadas_total`), com a mesma formula: `issues_fechadas / total_de_issues`.

- Total de repositorios no snapshot: {total}
- Repositorios analisados: {analisados}
- Registros descartados ou ausentes: {descartados}
- Motivos de descarte/status: `{status}`
- Quantidades de issues fechadas estimadas a partir da razao consolidada: {estimadas}

Observacao: o snapshot unificado atual nao preserva o campo exato `rq06_issues_fechadas`. Por isso, a tabela da RQ17 estima esse inteiro com `round(total_issues * rq06_razao_fechadas_total)` apenas para auditoria. A analise estatistica usa diretamente a razao ja calculada pela RQ06.

## Distribuicao

- Idade: media {idade_media} anos, mediana {idade_mediana} anos, minimo {idade_min} e maximo {idade_max}.
- Percentual de issues fechadas: media {perc_media}%, mediana {perc_mediana}%, minimo {perc_min}% e maximo {perc_max}%.

| Faixa de idade | Repositorios | Media de issues fechadas | Mediana de issues fechadas |
|---|---:|---:|---:|
{linhas_faixas}

## Correlacao e tendencia

- Pearson: {pearson} ({pearson_texto})
- Spearman: {spearman} ({spearman_texto})
- Tendencia linear simples: {inclinacao} ponto(s) percentual(is) por ano

O Pearson foi usado para medir relacao linear. O Spearman foi usado como apoio para tendencia monotonica, pois o percentual e limitado entre 0% e 100% e ha concentracao de valores altos.

## Outliers

Metodo: {metodo_outlier}. Foram identificados {qtd_outliers} outlier(s), principalmente percentuais baixos de fechamento em relacao a distribuicao.

{linhas_outliers}

## Conclusao

Hipotese: **{hipotese}**.

{conclusao}
""".format(
        total=resumo["total_repositorios"],
        analisados=resumo["repositorios_analisados"],
        descartados=resumo["registros_descartados_ou_ausentes"],
        status=resumo["por_status"],
        estimadas=resumo["issues_fechadas_estimadas"],
        idade_media=idade["media"],
        idade_mediana=idade["mediana"],
        idade_min=idade["minimo"],
        idade_max=idade["maximo"],
        perc_media=percentual["media"],
        perc_mediana=percentual["mediana"],
        perc_min=percentual["minimo"],
        perc_max=percentual["maximo"],
        linhas_faixas="\n".join(linhas_faixas),
        pearson=correlacao["pearson"],
        pearson_texto=correlacao["interpretacao_pearson"],
        spearman=correlacao["spearman"],
        spearman_texto=correlacao["interpretacao_spearman"],
        inclinacao=regressao["variacao_pontos_percentuais_por_ano"],
        metodo_outlier=outliers["metodo"],
        qtd_outliers=outliers["quantidade"],
        linhas_outliers="\n".join(linhas_outliers),
        hipotese=resumo["hipotese"],
        conclusao=resumo["conclusao"],
    )


def escrever_markdown(resultado: dict, caminho_markdown: Path) -> Path:
    caminho_markdown.parent.mkdir(parents=True, exist_ok=True)
    caminho_markdown.write_text(montar_markdown(resultado), encoding="utf-8")
    return caminho_markdown


def montar_argumentos(argv=None) -> argparse.Namespace:
    analisador = argparse.ArgumentParser(
        description="Executa RQ17 usando os dados consolidados dos 1.000 repositorios."
    )
    analisador.add_argument("--entrada", type=Path, default=ENTRADA_PADRAO)
    analisador.add_argument("--saida-json", type=Path, default=SAIDA_JSON_PADRAO)
    analisador.add_argument("--saida-csv", type=Path, default=SAIDA_CSV_PADRAO)
    analisador.add_argument("--saida-md", type=Path, default=SAIDA_MARKDOWN_PADRAO)
    return analisador.parse_args(argv)


def principal(argv=None) -> int:
    argumentos = montar_argumentos(argv)

    try:
        snapshot = carregar_json(argumentos.entrada)
        repositorios = snapshot["repositorios"]
        resultado = rq17.analisar(repositorios)
        escrever_json(resultado, argumentos.saida_json)
        escrever_csv(resultado["registros"], argumentos.saida_csv)
        escrever_markdown(resultado, argumentos.saida_md)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as erro:
        print("[erro] %s" % erro, file=sys.stderr)
        return 1

    resumo = resultado["resumo"]
    print("RQ17 concluida usando: %s" % argumentos.entrada)
    print("Repositorios analisados: %s de %s" % (resumo["repositorios_analisados"], resumo["total_repositorios"]))
    print("Descartados/ausentes: %s" % resumo["registros_descartados_ou_ausentes"])
    print("Pearson: %s | Spearman: %s" % (
        resumo["correlacao"]["pearson"],
        resumo["correlacao"]["spearman"],
    ))
    print("Hipotese: %s" % resumo["hipotese"])
    print("Texto para relatorio: %s" % argumentos.saida_md)
    return 0


if __name__ == "__main__":
    sys.exit(principal())
