"""RQ53: RQ3 - Teste de Wilcoxon pareado sobre metricas estaticas normalizadas por LOC.

H0: a complexidade/duplicacao normalizada por LOC e igual com e sem IA.
H1: a complexidade/duplicacao normalizada por LOC difere entre com e sem IA.

Duas metricas, cada uma com seu proprio teste pareado (mesmo participante nos dois tratamentos):

- complexidade_por_loc = (complexidade_media * funcoes_analisadas) / loc - complexidade ciclomatica
  total normalizada pelo tamanho do arquivo, para nao confundir "mais complexo" com "so mais longo"
  (codigo gerado por IA pode ser mais verboso - RQ44 na Sprint 2 ja mostrou isso).
- duplicacao_percentual - ja e normalizada (percentual sobre linhas analisadas), reportada aqui
  junto do LOC como metrica de controle, conforme recomendado no enunciado.

LOC entra no relatorio como controle mas nao e testado sozinho (nao e uma pergunta de pesquisa).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import estatistica_utils as util

RAIZ = Path(__file__).resolve().parents[2]
RQ30_PADRAO = RAIZ / "dados" / "lab02_rq30_metricas_estaticas.csv"
SAIDA_PADRAO = RAIZ / "dados" / "lab02_rq53_wilcoxon_metricas_estaticas.json"


def complexidade_por_loc(registro: dict):
    loc = util.numero(registro.get("loc"))
    complexidade_media = util.numero(registro.get("complexidade_media"))
    funcoes = util.numero(registro.get("funcoes_analisadas"))
    if not loc or complexidade_media is None or funcoes is None:
        return None
    return (complexidade_media * funcoes) / loc


def duplicacao_percentual(registro: dict):
    if util.texto(registro.get("duplicacao_disponivel")).lower() != "true":
        return None
    return util.numero(registro.get("duplicacao_percentual"))


METRICAS = {
    "complexidade_por_loc": complexidade_por_loc,
    "duplicacao_percentual": duplicacao_percentual,
}


def loc_por_tratamento(registros: list[dict]) -> dict:
    agregados = util.agregar_por_participante_tratamento(
        registros, extrair_valor=lambda r: util.numero(r.get("loc")),
    )
    por_tratamento: dict[str, list[float]] = {}
    for por_trat in agregados.values():
        for tratamento, valor in por_trat.items():
            por_tratamento.setdefault(tratamento, []).append(valor)
    import statistics
    return {tratamento: statistics.median(valores) for tratamento, valores in por_tratamento.items()}


def analisar(caminho_rq30: Path = RQ30_PADRAO) -> dict:
    registros = util.ler_csv(caminho_rq30)
    resultado_metricas = {}
    for nome_metrica, extrair in METRICAS.items():
        agregados = util.agregar_por_participante_tratamento(registros, extrair_valor=extrair)
        pares, incompletos = util.construir_pares(agregados)
        wilcoxon = util.testar_wilcoxon_pareado(pares)
        resultado_metricas[nome_metrica] = {
            "agregados_por_participante": agregados,
            "pares_utilizados": [{"participante": p, "com_ia": a, "sem_ia": b} for a, b, p in pares],
            "participantes_incompletos": incompletos,
            "wilcoxon": wilcoxon,
            "interpretacao": util.interpretar(wilcoxon),
        }

    return {
        "rq": "RQ3 - metricas estaticas normalizadas por LOC",
        "csv_rq30": str(caminho_rq30),
        "total_trials_lidos": len(registros),
        "loc_mediano_por_tratamento_controle": loc_por_tratamento(registros),
        "metricas": resultado_metricas,
    }


def principal(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rq30", type=Path, default=RQ30_PADRAO)
    parser.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    args = parser.parse_args(argv)

    relatorio = analisar(args.rq30)
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")

    print("RQ3 - Metricas estaticas normalizadas por LOC (com_ia vs sem_ia)")
    print("LOC mediano por tratamento (controle): %s" % relatorio["loc_mediano_por_tratamento_controle"])
    todas_suficientes = True
    for nome_metrica, resultado in relatorio["metricas"].items():
        print("- %s: %d pares -> %s" % (nome_metrica, len(resultado["pares_utilizados"]), resultado["interpretacao"]))
        todas_suficientes = todas_suficientes and resultado["wilcoxon"]["suficiente"]
    print("Relatorio salvo em %s" % args.saida)
    return 0 if todas_suficientes else 1


if __name__ == "__main__":
    sys.exit(principal())
