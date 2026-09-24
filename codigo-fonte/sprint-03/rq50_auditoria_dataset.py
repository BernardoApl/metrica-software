"""RQ50: identificar outliers e consolidar o dataset real da Sprint 2 (RQ28/RQ30).

O desenho da Sprint 2 previa 12 trials reais (3 integrantes x 4 katas, cada
integrante com 2 katas com_ia e 2 sem_ia, contrabalanceados), um por issue do
GitHub (#34-42, #47-49). Este script cruza `dados/lab02_rq28_tempos.csv` e
`dados/lab02_rq30_metricas_estaticas.csv` com esse desenho esperado, aponta
quais trials ainda faltam (ou estao com kata/issue divergentes) e calcula
outliers (IQR) sobre os trials reais ja registrados.

Nao inventa nem descarta dados: so relata o que falta coletar antes de rodar
os testes de Wilcoxon (RQ51/RQ52/RQ53).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
RQ28_PADRAO = RAIZ / "dados" / "lab02_rq28_tempos.csv"
RQ30_PADRAO = RAIZ / "dados" / "lab02_rq30_metricas_estaticas.csv"
SAIDA_PADRAO = RAIZ / "dados" / "lab02_rq50_auditoria.json"

# Katas oficialmente selecionados (RQ32) para o LAB02.
KATAS_OFICIAIS = {
    "01": "kata01_frete_progressivo",
    "02": "kata02_calculo_estacionamento",
    "03": "kata03_desconto_pedido",
    "04": "kata04_calculo_tarifa_energia",
}

# Desenho esperado da Sprint 2: uma linha por issue de trial fechada no GitHub
# (#34-42, #47-49; exclui #43-46, que sao issues de inovacao/validacao, nao
# trials de kata). responsavel_esperado e o assignee da issue no GitHub.
DESENHO_ESPERADO = [
    {"issue": "34", "kata_numero": "01", "tratamento": "com_ia", "responsavel_esperado": "BernardoApl"},
    {"issue": "35", "kata_numero": "02", "tratamento": "sem_ia", "responsavel_esperado": "BernardoApl"},
    {"issue": "36", "kata_numero": "03", "tratamento": "com_ia", "responsavel_esperado": "BernardoApl"},
    {"issue": "47", "kata_numero": "04", "tratamento": "sem_ia", "responsavel_esperado": "BernardoApl"},
    {"issue": "37", "kata_numero": "01", "tratamento": "sem_ia", "responsavel_esperado": "bacelete"},
    {"issue": "38", "kata_numero": "02", "tratamento": "com_ia", "responsavel_esperado": "bacelete"},
    {"issue": "39", "kata_numero": "03", "tratamento": "sem_ia", "responsavel_esperado": "bacelete"},
    {"issue": "48", "kata_numero": "04", "tratamento": "com_ia", "responsavel_esperado": "bacelete"},
    {"issue": "40", "kata_numero": "01", "tratamento": "com_ia", "responsavel_esperado": "Joaopedrotavaress"},
    {"issue": "41", "kata_numero": "02", "tratamento": "com_ia", "responsavel_esperado": "Joaopedrotavaress"},
    {"issue": "42", "kata_numero": "03", "tratamento": "sem_ia", "responsavel_esperado": "Joaopedrotavaress"},
    {"issue": "49", "kata_numero": "04", "tratamento": "sem_ia", "responsavel_esperado": "Joaopedrotavaress"},
]


def _texto(valor) -> str:
    return "" if valor is None else str(valor).strip()


def _numero(valor):
    texto = _texto(valor)
    if texto == "":
        return None
    try:
        return float(texto)
    except ValueError:
        return None


def _numero_kata(kata: str) -> str:
    """Extrai o prefixo 'NN' de campos como 'kata03' ou 'kata03_desconto_pedido'."""
    kata = _texto(kata).lower()
    if kata.startswith("kata") and len(kata) >= 6 and kata[4:6].isdigit():
        return kata[4:6]
    return ""


def ler_csv(caminho: Path) -> list[dict]:
    if not caminho.exists():
        return []
    with caminho.open(newline="", encoding="utf-8") as arquivo:
        return list(csv.DictReader(arquivo))


def auditar_cobertura(linhas_rq28: list[dict], linhas_rq30: list[dict]) -> dict:
    por_issue_rq28: dict[str, list[dict]] = {}
    for linha in linhas_rq28:
        por_issue_rq28.setdefault(_texto(linha.get("issue")), []).append(linha)

    issues_rq30 = {_texto(linha.get("issue")) for linha in linhas_rq30}

    faltando: list[dict] = []
    divergentes: list[dict] = []
    ok: list[dict] = []

    for esperado in DESENHO_ESPERADO:
        issue = esperado["issue"]
        candidatos = por_issue_rq28.get(issue, [])
        if not candidatos:
            faltando.append(esperado)
            continue
        for linha in candidatos:
            numero_kata = _numero_kata(linha.get("kata"))
            kata_oficial = KATAS_OFICIAIS.get(esperado["kata_numero"])
            problemas = []
            if numero_kata != esperado["kata_numero"]:
                problemas.append(
                    "kata da linha (%s) nao bate com o numero esperado (kata%s)"
                    % (_texto(linha.get("kata")), esperado["kata_numero"])
                )
            elif _texto(linha.get("kata")) != kata_oficial:
                problemas.append(
                    "kata '%s' nao e o nome oficial selecionado na RQ32 (%s)"
                    % (_texto(linha.get("kata")), kata_oficial)
                )
            if _texto(linha.get("tratamento")) != esperado["tratamento"]:
                problemas.append(
                    "tratamento da linha (%s) nao bate com o esperado (%s)"
                    % (_texto(linha.get("tratamento")), esperado["tratamento"])
                )
            if issue not in issues_rq30 and _texto(linha.get("sucesso")).lower() == "true":
                problemas.append("trial com sucesso mas sem medicao correspondente na RQ30")
            registro = {**esperado, "trial_id": _texto(linha.get("trial_id")),
                        "participante_csv": _texto(linha.get("participante")),
                        "kata_csv": _texto(linha.get("kata")), "problemas": problemas}
            (divergentes if problemas else ok).append(registro)

    return {
        "total_esperado": len(DESENHO_ESPERADO),
        "total_ok": len(ok),
        "total_divergente": len(divergentes),
        "total_faltando": len(faltando),
        "ok": ok,
        "divergentes": divergentes,
        "faltando": faltando,
    }


def outliers_iqr(valores: list[float]) -> dict:
    n = len(valores)
    if n < 4:
        return {"n": n, "aviso": "menos de 4 valores: deteccao de outliers por IQR nao e confiavel", "outliers": []}
    ordenados = sorted(valores)

    def quartil(p: float) -> float:
        posicao = p * (n - 1)
        base = int(posicao)
        fracao = posicao - base
        if base + 1 < n:
            return ordenados[base] + fracao * (ordenados[base + 1] - ordenados[base])
        return ordenados[base]

    q1, q3 = quartil(0.25), quartil(0.75)
    iqr = q3 - q1
    limite_inferior, limite_superior = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    outliers = [v for v in valores if v < limite_inferior or v > limite_superior]
    return {
        "n": n, "q1": q1, "q3": q3, "iqr": iqr,
        "limite_inferior": limite_inferior, "limite_superior": limite_superior,
        "outliers": outliers,
    }


def auditar_outliers(linhas_rq28: list[dict], linhas_rq30: list[dict]) -> dict:
    duracoes = [_numero(l.get("duracao_segundos")) for l in linhas_rq28
                if _texto(l.get("sucesso")).lower() == "true"]
    duracoes = [d for d in duracoes if d is not None]

    resultado = {"duracao_segundos": outliers_iqr(duracoes)}
    for campo in ("complexidade_media", "indice_manutenibilidade", "duplicacao_percentual"):
        valores = [_numero(l.get(campo)) for l in linhas_rq30]
        valores = [v for v in valores if v is not None]
        resultado[campo] = outliers_iqr(valores)
    return resultado


def auditar(rq28: Path = RQ28_PADRAO, rq30: Path = RQ30_PADRAO) -> dict:
    linhas_rq28 = ler_csv(rq28)
    linhas_rq30 = ler_csv(rq30)
    cobertura = auditar_cobertura(linhas_rq28, linhas_rq30)
    return {
        "csv_rq28": str(rq28),
        "csv_rq30": str(rq30),
        "total_trials_rq28": len(linhas_rq28),
        "total_trials_rq30": len(linhas_rq30),
        "cobertura": cobertura,
        "outliers": auditar_outliers(linhas_rq28, linhas_rq30),
        "pronto_para_wilcoxon": cobertura["total_faltando"] == 0 and cobertura["total_divergente"] == 0,
    }


def principal(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rq28", type=Path, default=RQ28_PADRAO)
    parser.add_argument("--rq30", type=Path, default=RQ30_PADRAO)
    parser.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    args = parser.parse_args(argv)

    relatorio = auditar(args.rq28, args.rq30)
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")

    cobertura = relatorio["cobertura"]
    print("Trials esperados: %d | OK: %d | divergentes: %d | faltando: %d"
          % (cobertura["total_esperado"], cobertura["total_ok"],
             cobertura["total_divergente"], cobertura["total_faltando"]))
    if cobertura["faltando"]:
        print("Faltando:")
        for item in cobertura["faltando"]:
            print("- #%s: kata%s / %s (esperado: %s)"
                  % (item["issue"], item["kata_numero"], item["tratamento"], item["responsavel_esperado"]))
    if cobertura["divergentes"]:
        print("Divergentes:")
        for item in cobertura["divergentes"]:
            print("- #%s (trial_id=%s): %s" % (item["issue"], item["trial_id"], "; ".join(item["problemas"])))
    print("Relatorio salvo em %s" % args.saida)
    return 0 if relatorio["pronto_para_wilcoxon"] else 1


if __name__ == "__main__":
    sys.exit(principal())
