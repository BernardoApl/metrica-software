"""RQ18 - Grafico da relacao entre idade e percentual de issues fechadas.

Usa diretamente ``dados/rq17_resultados.json``. Nao faz nova coleta e nao
duplica os 1.000 registros em outro JSON.

Saida principal: um SVG estatico com scatter plot, pronto para o relatorio.
"""

from __future__ import annotations

import html
import math
from pathlib import Path


LARGURA = 1120
ALTURA = 760
MARGEM_ESQUERDA = 88
MARGEM_DIREITA = 46
MARGEM_SUPERIOR = 116
MARGEM_INFERIOR = 94

COR_FUNDO = "#ffffff"
COR_TEXTO = "#18181b"
COR_TEXTO_SECUNDARIO = "#52525b"
COR_GRADE = "#e4e4e7"
COR_EIXO = "#27272a"
COR_PONTO = "#2563eb"
COR_OUTLIER = "#d97706"
COR_TENDENCIA = "#3f3f46"


def _escapar(valor) -> str:
    return html.escape("" if valor is None else str(valor), quote=True)


def _numero(valor) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(float(valor))


def _escala(valor: float, minimo: float, maximo: float, inicio: float, fim: float) -> float:
    if maximo == minimo:
        return (inicio + fim) / 2.0
    return inicio + ((valor - minimo) / (maximo - minimo)) * (fim - inicio)


def _ticks(maximo: float, passo: float) -> list[float]:
    valores = []
    atual = 0.0
    while atual <= maximo + passo / 2.0:
        valores.append(round(atual, 6))
        atual += passo
    return valores


def eh_outlier(registro: dict, resumo: dict) -> bool:
    """Reaplica os limites IQR calculados na RQ17 para destacar outliers."""
    outliers = resumo.get("outliers") or {}
    limites_idade = outliers.get("limites_idade_anos") or {}
    limites_percentual = outliers.get("limites_percentual_issues_fechadas") or {}
    idade = registro.get("idade_anos")
    percentual = registro.get("percentual_issues_fechadas")

    if not _numero(idade) or not _numero(percentual):
        return False

    idade_inferior = limites_idade.get("inferior")
    idade_superior = limites_idade.get("superior")
    percentual_inferior = limites_percentual.get("inferior")
    percentual_superior = limites_percentual.get("superior")

    idade_fora = (
        _numero(idade_inferior)
        and _numero(idade_superior)
        and (idade < idade_inferior or idade > idade_superior)
    )
    percentual_fora = (
        _numero(percentual_inferior)
        and _numero(percentual_superior)
        and (percentual < percentual_inferior or percentual > percentual_superior)
    )
    return bool(idade_fora or percentual_fora)


def gerar_svg(resultado_rq17: dict) -> str:
    """Gera o scatter plot em SVG."""
    resumo = resultado_rq17.get("resumo") or {}
    registros = resultado_rq17.get("registros_analisados") or []
    if not registros:
        raise ValueError("Nao ha registros analisados na RQ17 para gerar a RQ18.")

    idades = [float(registro["idade_anos"]) for registro in registros]
    max_x = max(20.0, float(math.ceil(max(idades))))
    min_x = 0.0
    min_y = 0.0
    max_y = 100.0

    x0 = MARGEM_ESQUERDA
    x1 = LARGURA - MARGEM_DIREITA
    y0 = ALTURA - MARGEM_INFERIOR
    y1 = MARGEM_SUPERIOR

    def sx(valor: float) -> float:
        return _escala(valor, min_x, max_x, x0, x1)

    def sy(valor: float) -> float:
        return _escala(valor, min_y, max_y, y0, y1)

    correlacao = resumo.get("correlacao") or {}
    subtitulo = (
        "n=%s repositorios analisados; %s descartados; Pearson=%s; Spearman=%s"
        % (
            resumo.get("repositorios_analisados", len(registros)),
            resumo.get("registros_descartados_ou_ausentes", 0),
            correlacao.get("pearson"),
            correlacao.get("spearman"),
        )
    )

    partes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{LARGURA}" height="{ALTURA}" viewBox="0 0 {LARGURA} {ALTURA}" role="img" aria-labelledby="titulo descricao">',
        f'<rect width="{LARGURA}" height="{ALTURA}" fill="{COR_FUNDO}"/>',
        '<title id="titulo">RQ18 - Idade do repositorio x percentual de issues fechadas</title>',
        '<desc id="descricao">Grafico de dispersao gerado a partir do resultado da RQ17.</desc>',
        f'<text x="{MARGEM_ESQUERDA}" y="42" font-family="Arial, sans-serif" font-size="24" font-weight="700" fill="{COR_TEXTO}">RQ18 - Idade do repositorio x percentual de issues fechadas</text>',
        f'<text x="{MARGEM_ESQUERDA}" y="72" font-family="Arial, sans-serif" font-size="15" fill="{COR_TEXTO_SECUNDARIO}">{_escapar(subtitulo)}</text>',
    ]

    for valor in _ticks(100.0, 20.0):
        y = sy(valor)
        partes.append(f'<line x1="{x0}" y1="{y:.2f}" x2="{x1}" y2="{y:.2f}" stroke="{COR_GRADE}" stroke-width="1"/>')
        partes.append(
            f'<text x="{x0 - 12}" y="{y + 5:.2f}" text-anchor="end" font-family="Arial, sans-serif" font-size="12" fill="{COR_TEXTO_SECUNDARIO}">{int(valor)}%</text>'
        )

    for valor in _ticks(max_x, 5.0):
        x = sx(valor)
        partes.append(f'<line x1="{x:.2f}" y1="{y0}" x2="{x:.2f}" y2="{y1}" stroke="{COR_GRADE}" stroke-width="1"/>')
        partes.append(
            f'<text x="{x:.2f}" y="{y0 + 26}" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="{COR_TEXTO_SECUNDARIO}">{int(valor)}</text>'
        )

    partes.append(f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y0}" stroke="{COR_EIXO}" stroke-width="1.4"/>')
    partes.append(f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="{COR_EIXO}" stroke-width="1.4"/>')
    partes.append(
        f'<text x="{(x0 + x1) / 2:.2f}" y="{ALTURA - 30}" text-anchor="middle" font-family="Arial, sans-serif" font-size="15" font-weight="700" fill="{COR_TEXTO}">Idade do repositorio (anos)</text>'
    )
    partes.append(
        f'<text x="24" y="{(y0 + y1) / 2:.2f}" transform="rotate(-90 24 {(y0 + y1) / 2:.2f})" text-anchor="middle" font-family="Arial, sans-serif" font-size="15" font-weight="700" fill="{COR_TEXTO}">Issues fechadas (%)</text>'
    )

    for registro in registros:
        x = sx(float(registro["idade_anos"]))
        y = sy(float(registro["percentual_issues_fechadas"]))
        destacado = eh_outlier(registro, resumo)
        cor = COR_OUTLIER if destacado else COR_PONTO
        raio = 4.8 if destacado else 3.1
        opacidade = 0.86 if destacado else 0.42
        partes.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{raio}" fill="{cor}" fill-opacity="{opacidade}">'
            f'<title>{_escapar(registro.get("nome_repositorio"))}: {registro["idade_anos"]} anos, {registro["percentual_issues_fechadas"]}% fechadas, {registro["total_issues"]} issues</title>'
            '</circle>'
        )

    regressao = resumo.get("regressao_linear") or {}
    inclinacao = regressao.get("inclinacao_por_ano")
    intercepto = regressao.get("intercepto")
    if _numero(inclinacao) and _numero(intercepto):
        y_inicio = max(0.0, min(100.0, float(intercepto)))
        y_fim = max(0.0, min(100.0, float(intercepto) + float(inclinacao) * max_x))
        partes.append(
            f'<line x1="{sx(0.0):.2f}" y1="{sy(y_inicio):.2f}" x2="{sx(max_x):.2f}" y2="{sy(y_fim):.2f}" stroke="{COR_TENDENCIA}" stroke-width="2.4" stroke-dasharray="8 6"/>'
        )

    legenda_x = x1 - 272
    legenda_y = y1 + 18
    partes.extend(
        [
            f'<circle cx="{legenda_x}" cy="{legenda_y}" r="4" fill="{COR_PONTO}" fill-opacity="0.55"/>',
            f'<text x="{legenda_x + 14}" y="{legenda_y + 5}" font-family="Arial, sans-serif" font-size="12" fill="{COR_TEXTO_SECUNDARIO}">Repositorios analisados</text>',
            f'<circle cx="{legenda_x}" cy="{legenda_y + 24}" r="5" fill="{COR_OUTLIER}" fill-opacity="0.86"/>',
            f'<text x="{legenda_x + 14}" y="{legenda_y + 29}" font-family="Arial, sans-serif" font-size="12" fill="{COR_TEXTO_SECUNDARIO}">Outliers por IQR</text>',
            f'<line x1="{legenda_x - 4}" y1="{legenda_y + 48}" x2="{legenda_x + 12}" y2="{legenda_y + 48}" stroke="{COR_TENDENCIA}" stroke-width="2.4" stroke-dasharray="8 6"/>',
            f'<text x="{legenda_x + 14}" y="{legenda_y + 53}" font-family="Arial, sans-serif" font-size="12" fill="{COR_TEXTO_SECUNDARIO}">Regressao linear simples</text>',
        ]
    )

    nota = "Fonte: dados/rq17_resultados.json; percentual reutiliza a razao da RQ06."
    partes.append(
        f'<text x="{MARGEM_ESQUERDA}" y="{ALTURA - 10}" font-family="Arial, sans-serif" font-size="11" fill="{COR_TEXTO_SECUNDARIO}">{_escapar(nota)}</text>'
    )
    partes.append("</svg>")
    return "\n".join(partes)


def salvar_svg(resultado_rq17: dict, caminho: Path) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(gerar_svg(resultado_rq17), encoding="utf-8")
    return caminho
