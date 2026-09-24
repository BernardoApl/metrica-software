"""RQ52: RQ2 - Teste de Wilcoxon pareado sobre taxa de sucesso / defeitos (com_ia vs sem_ia).

H0: a taxa de sucesso (% de trials que passam em todos os testes de aceitacao dentro do time-box)
e igual com e sem IA.
H1: a taxa de sucesso difere entre com e sem IA.

O RQ28 so registra sucesso/fracasso por trial (nao a fracao de testes individuais que passaram),
entao a "taxa de sucesso" aqui e a proporcao de trials bem-sucedidos por participante/tratamento
(cada participante tem 2 katas por tratamento -> taxa em {0, 0.5, 1}). Documentado como limitacao:
para uma taxa por-teste seria preciso o RQ28 registrar quantos testes individuais passaram, nao so
o resultado agregado do `unittest discover`.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

import estatistica_utils as util

RAIZ = Path(__file__).resolve().parents[2]
RQ28_PADRAO = RAIZ / "dados" / "lab02_rq28_tempos.csv"
SAIDA_PADRAO = RAIZ / "dados" / "lab02_rq52_wilcoxon_sucesso.json"

STATUS_VALIDOS_PARA_TENTATIVA = {"sucesso", "limite_atingido"}


def sucesso_binario(registro: dict):
    status = util.texto(registro.get("status")).lower()
    if status not in STATUS_VALIDOS_PARA_TENTATIVA:
        return None  # interrupcao/erro de execucao nao e uma tentativa valida
    return 1.0 if util.texto(registro.get("sucesso")).lower() == "true" else 0.0


def trials_ignorados(registros: list[dict]) -> list[dict]:
    return [
        {"trial_id": util.texto(r.get("trial_id")), "participante": util.texto(r.get("participante")),
         "kata": util.texto(r.get("kata")), "status": util.texto(r.get("status"))}
        for r in registros if sucesso_binario(r) is None
    ]


def analisar(caminho_rq28: Path = RQ28_PADRAO) -> dict:
    registros = util.ler_csv(caminho_rq28)
    agregados = util.agregar_por_participante_tratamento(
        registros, extrair_valor=sucesso_binario, agregador=statistics.mean,
    )
    pares, incompletos = util.construir_pares(agregados)
    resultado = util.testar_wilcoxon_pareado(pares)
    return {
        "rq": "RQ2 - taxa de sucesso / defeitos",
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

    print("RQ2 - Taxa de sucesso / defeitos (com_ia vs sem_ia)")
    print("Pares completos: %d" % len(relatorio["pares_utilizados"]))
    if relatorio["participantes_incompletos"]:
        print("Participantes incompletos:")
        for item in relatorio["participantes_incompletos"]:
            print("- %s: falta %s" % (item["participante"], ", ".join(item["tratamentos_faltando"])))
    print(relatorio["interpretacao"])
    print("Relatorio salvo em %s" % args.saida)
    return 0 if relatorio["wilcoxon"]["suficiente"] else 1


if __name__ == "__main__":
    sys.exit(principal())
