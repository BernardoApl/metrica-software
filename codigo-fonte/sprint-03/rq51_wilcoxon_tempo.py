"""RQ51: RQ1 - Teste de Wilcoxon pareado sobre tempo de resolucao (com_ia vs sem_ia).

H0: a mediana do tempo de resolucao e igual com e sem IA.
H1: a mediana do tempo de resolucao difere entre com e sem IA.

Trial censurado (time-box de 35 min atingido sem sucesso) entra com duracao = limite_segundos,
conforme decidido na RQ33 - nao e descartado. Trials com erro de execucao ou interrompidos ficam
de fora (nao representam nem sucesso nem censura valida) e sao listados como alerta.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import estatistica_utils as util

RAIZ = Path(__file__).resolve().parents[2]
RQ28_PADRAO = RAIZ / "dados" / "lab02_rq28_tempos.csv"
SAIDA_PADRAO = RAIZ / "dados" / "lab02_rq51_wilcoxon_tempo.json"


def duracao_efetiva(registro: dict):
    if util.texto(registro.get("sucesso")).lower() == "true":
        return util.numero(registro.get("duracao_segundos"))
    if util.texto(registro.get("censurado")).lower() == "true":
        return util.numero(registro.get("limite_segundos"))
    return None


def trials_ignorados(registros: list[dict]) -> list[dict]:
    return [
        {"trial_id": util.texto(r.get("trial_id")), "participante": util.texto(r.get("participante")),
         "kata": util.texto(r.get("kata")), "status": util.texto(r.get("status"))}
        for r in registros if duracao_efetiva(r) is None
    ]


def analisar(caminho_rq28: Path = RQ28_PADRAO) -> dict:
    registros = util.ler_csv(caminho_rq28)
    agregados = util.agregar_por_participante_tratamento(registros, extrair_valor=duracao_efetiva)
    pares, incompletos = util.construir_pares(agregados)
    resultado = util.testar_wilcoxon_pareado(pares)
    return {
        "rq": "RQ1 - tempo de resolucao",
        "csv_rq28": str(caminho_rq28),
        "total_trials_lidos": len(registros),
        "trials_ignorados": trials_ignorados(registros),
        "agregados_por_participante": agregados,
        "pares_utilizados": [{"participante": p, "com_ia": a, "sem_ia": b} for a, b, p in pares],
        "participantes_incompletos": incompletos,
        "wilcoxon": resultado,
        "interpretacao": util.interpretar(resultado),
    }


def principal(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rq28", type=Path, default=RQ28_PADRAO)
    parser.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    args = parser.parse_args(argv)

    relatorio = analisar(args.rq28)
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")

    print("RQ1 - Tempo de resolucao (com_ia vs sem_ia)")
    print("Pares completos: %d" % len(relatorio["pares_utilizados"]))
    if relatorio["participantes_incompletos"]:
        print("Participantes incompletos:")
        for item in relatorio["participantes_incompletos"]:
            print("- %s: falta %s" % (item["participante"], ", ".join(item["tratamentos_faltando"])))
    if relatorio["trials_ignorados"]:
        print("Trials ignorados (nem sucesso nem censura valida): %d" % len(relatorio["trials_ignorados"]))
    print(relatorio["interpretacao"])
    print("Relatorio salvo em %s" % args.saida)
    return 0 if relatorio["wilcoxon"]["suficiente"] else 1


if __name__ == "__main__":
    sys.exit(principal())
