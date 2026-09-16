"""RQ43.2 (Inovacao): valida integridade e rastreabilidade dos dados reais dos trials.

Cruza os registros reais da RQ28 com evidencias complementares do LAB02:
diretorio do kata, arquivo `solucao.py`, prompt/interacao dos trials com IA e,
quando disponivel, medicoes estaticas da RQ30. A validacao reaproveita a RQ29
para o schema do CSV de tempos e a RQ31 para o schema do CSV de metricas.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import rq28_cronometragem as rq28
import rq29_validar_trials as rq29


RAIZ_PROJETO = Path(__file__).resolve().parents[2]
DADOS_PADRAO = RAIZ_PROJETO / "dados"
CSV_RQ28_PADRAO = rq28.SAIDA_PADRAO
CSV_RQ30_PADRAO = DADOS_PADRAO / "lab02_rq30_metricas_estaticas.csv"
SAIDA_CSV_PADRAO = DADOS_PADRAO / "lab02_rq43_integridade_trials.csv"
SAIDA_JSON_PADRAO = DADOS_PADRAO / "lab02_rq43_integridade_trials.json"

RQ30_COLUNAS = (
    "participante", "kata", "tratamento", "issue", "trial_id", "arquivo",
    "medido_em_utc", "loc", "sloc", "lloc", "comentarios", "linhas_em_branco",
    "funcoes_analisadas", "complexidade_media", "complexidade_maxima",
    "indice_manutenibilidade", "duplicacao_disponivel", "duplicacao_percentual",
    "linhas_duplicadas", "linhas_analisadas_duplicacao",
)

COLUNAS_SAIDA = (
    "trial_id", "participante", "kata", "tratamento", "issue", "status",
    "sucesso", "censurado", "diretorio_existe", "solucao_existe",
    "prompt_ia_existe", "metricas_rq30_existe", "rastreabilidade_ok", "alertas",
)


def _texto(valor) -> str:
    return "" if valor is None else str(valor).strip()


def _booleano(valor) -> bool:
    return _texto(valor).lower() in {"true", "1", "sim"}


def carregar_csv(caminho: Path) -> list[dict]:
    if not caminho.exists():
        return []
    with caminho.open(newline="", encoding="utf-8") as arquivo:
        return list(csv.DictReader(arquivo))


def validar_csv_metricas_basico(caminho: Path) -> dict:
    if not caminho.exists():
        return {
            "arquivo": str(caminho),
            "valido": False,
            "total_registros": 0,
            "erros": ["arquivo de metricas RQ30 nao encontrado: %s" % caminho],
        }

    erros = []
    with caminho.open(newline="", encoding="utf-8") as arquivo:
        leitor = csv.DictReader(arquivo)
        if leitor.fieldnames != list(RQ30_COLUNAS):
            erros.append("cabecalho incompativel com a RQ30")
        registros = list(leitor)

    for indice, registro in enumerate(registros, start=2):
        for campo in ("participante", "kata", "tratamento", "issue", "arquivo", "medido_em_utc"):
            if _texto(registro.get(campo)) == "":
                erros.append("linha %d: campo obrigatorio vazio: %s" % (indice, campo))
        arquivo = _texto(registro.get("arquivo"))
        if arquivo and not arquivo.endswith(".py"):
            erros.append("linha %d: arquivo analisado nao e .py: %s" % (indice, arquivo))

    if not registros:
        erros.append("arquivo sem registros de medicao")

    return {
        "arquivo": str(caminho),
        "valido": not erros,
        "total_registros": len(registros),
        "erros": erros,
    }


def _numero_kata(nome_kata: str) -> str:
    partes = _texto(nome_kata).split("_", 1)
    if partes and partes[0].startswith("kata"):
        return partes[0].replace("kata", "")
    return ""


def localizar_prompt_ia(kata: str, diretorio_dados: Path) -> Path | None:
    numero = _numero_kata(kata)
    candidatos = []
    if numero:
        candidatos.extend(diretorio_dados.glob(f"lab02_kata{numero}_com_ia_prompts.*"))
        if numero.isdigit():
            candidatos.extend(diretorio_dados.glob(f"lab02_kata{int(numero):02d}_com_ia_prompts.*"))
    candidatos.extend(diretorio_dados.glob(f"*{kata}*com_ia*prompt*"))
    arquivos = sorted(caminho for caminho in candidatos if caminho.is_file())
    return arquivos[0] if arquivos else None


def indexar_metricas(registros_metricas: list[dict]) -> dict[str, list[dict]]:
    por_trial: dict[str, list[dict]] = {}
    for registro in registros_metricas:
        trial_id = _texto(registro.get("trial_id"))
        if trial_id:
            por_trial.setdefault(trial_id, []).append(registro)
    return por_trial


def validar_rastreabilidade(
    registros_trials: list[dict],
    registros_metricas: list[dict],
    diretorio_dados: Path = DADOS_PADRAO,
) -> list[dict]:
    metricas_por_trial = indexar_metricas(registros_metricas)
    linhas = []

    for registro in registros_trials:
        alertas = []
        trial_id = _texto(registro.get("trial_id"))
        tratamento = _texto(registro.get("tratamento"))
        status = _texto(registro.get("status"))
        sucesso = _booleano(registro.get("sucesso"))
        censurado = _booleano(registro.get("censurado"))

        diretorio = Path(_texto(registro.get("diretorio")))
        diretorio_existe = diretorio.is_dir()
        if not diretorio_existe:
            alertas.append("diretorio_do_trial_nao_encontrado")

        solucao = diretorio / "solucao.py"
        solucao_existe = solucao.is_file()
        if not solucao_existe:
            alertas.append("solucao_py_nao_encontrado")

        prompt_ia = localizar_prompt_ia(_texto(registro.get("kata")), diretorio_dados) if tratamento == "com_ia" else None
        prompt_ia_existe = tratamento != "com_ia" or prompt_ia is not None
        if tratamento == "com_ia" and prompt_ia is None:
            alertas.append("prompt_interacao_ia_nao_encontrado")

        metricas = metricas_por_trial.get(trial_id, [])
        metricas_existe = bool(metricas)
        if sucesso and not metricas_existe:
            alertas.append("metricas_rq30_nao_encontradas_para_trial")
        if len(metricas) > 1:
            alertas.append("metricas_rq30_duplicadas_para_trial")

        rastreabilidade_ok = diretorio_existe and solucao_existe and prompt_ia_existe and (not sucesso or metricas_existe)

        linhas.append({
            "trial_id": trial_id,
            "participante": _texto(registro.get("participante")),
            "kata": _texto(registro.get("kata")),
            "tratamento": tratamento,
            "issue": _texto(registro.get("issue")),
            "status": status,
            "sucesso": sucesso,
            "censurado": censurado,
            "diretorio_existe": diretorio_existe,
            "solucao_existe": solucao_existe,
            "prompt_ia_existe": prompt_ia_existe,
            "metricas_rq30_existe": metricas_existe,
            "rastreabilidade_ok": rastreabilidade_ok,
            "alertas": ";".join(alertas),
        })

    return linhas


def validar_metricas_referenciam_trials(registros_trials: list[dict], registros_metricas: list[dict]) -> list[str]:
    trials = {_texto(registro.get("trial_id")) for registro in registros_trials if _texto(registro.get("trial_id"))}
    erros = []
    for indice, registro in enumerate(registros_metricas, start=2):
        trial_id = _texto(registro.get("trial_id"))
        if trial_id and trial_id not in trials:
            erros.append("linha %d da RQ30: trial_id sem correspondente na RQ28: %s" % (indice, trial_id))
    return erros


def salvar_csv(linhas: list[dict], caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS_SAIDA)
        escritor.writeheader()
        escritor.writerows(linhas)


def gerar_relatorio(csv_rq28: Path, csv_rq30: Path, diretorio_dados: Path = DADOS_PADRAO) -> dict:
    relatorio_rq29 = rq29.validar_csv(csv_rq28, exigir_diretorio_existente=True)
    registros_trials = carregar_csv(csv_rq28)

    metricas_disponiveis = csv_rq30.exists()
    registros_metricas = carregar_csv(csv_rq30) if metricas_disponiveis else []
    relatorio_rq30 = validar_csv_metricas_basico(csv_rq30)

    linhas = validar_rastreabilidade(registros_trials, registros_metricas, diretorio_dados)
    erros_metricas = validar_metricas_referenciam_trials(registros_trials, registros_metricas)

    alertas = []
    if not metricas_disponiveis:
        alertas.append("CSV da RQ30 ausente; colete metricas estaticas para rastreabilidade completa.")
    alertas.extend(erros_metricas)

    registros_ok = sum(1 for linha in linhas if linha["rastreabilidade_ok"])
    registros_com_alerta = sum(1 for linha in linhas if linha["alertas"])
    valido = relatorio_rq29["valido"] and metricas_disponiveis and relatorio_rq30["valido"] \
        and not erros_metricas and registros_ok == len(linhas)

    return {
        "valido": valido,
        "csv_rq28": str(csv_rq28),
        "csv_rq30": str(csv_rq30),
        "total_trials": len(linhas),
        "trials_rastreaveis": registros_ok,
        "trials_com_alerta": registros_com_alerta,
        "rq28_valido": relatorio_rq29["valido"],
        "rq30_valido": relatorio_rq30["valido"] if metricas_disponiveis else False,
        "erros_rq28": relatorio_rq29["erros"],
        "erros_rq30": relatorio_rq30["erros"],
        "alertas": alertas,
        "linhas": linhas,
    }


def salvar_json(relatorio: dict, caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")


def principal(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-rq28", type=Path, default=CSV_RQ28_PADRAO)
    parser.add_argument("--csv-rq30", type=Path, default=CSV_RQ30_PADRAO)
    parser.add_argument("--diretorio-dados", type=Path, default=DADOS_PADRAO)
    parser.add_argument("--saida-csv", type=Path, default=SAIDA_CSV_PADRAO)
    parser.add_argument("--saida-json", type=Path, default=SAIDA_JSON_PADRAO)
    parser.add_argument("--json", action="store_true", help="Imprime o relatorio completo em JSON.")
    args = parser.parse_args(argv)

    relatorio = gerar_relatorio(args.csv_rq28, args.csv_rq30, args.diretorio_dados)
    salvar_csv(relatorio["linhas"], args.saida_csv)
    salvar_json(relatorio, args.saida_json)

    if args.json:
        print(json.dumps(relatorio, ensure_ascii=False, indent=2))
    else:
        print("Trials reais: %d" % relatorio["total_trials"])
        print("Trials rastreaveis: %d" % relatorio["trials_rastreaveis"])
        print("Trials com alerta: %d" % relatorio["trials_com_alerta"])
        print("RQ28 valido: %s" % relatorio["rq28_valido"])
        print("RQ30 valido: %s" % relatorio["rq30_valido"])
        if relatorio["alertas"]:
            print("Alertas:")
            for alerta in relatorio["alertas"]:
                print("- %s" % alerta)
        if relatorio["valido"]:
            print("Integridade e rastreabilidade OK.")
        else:
            print("Integridade/rastreabilidade incompleta; veja os arquivos de saida.")
        print("CSV salvo em: %s" % args.saida_csv.resolve())
        print("JSON salvo em: %s" % args.saida_json.resolve())
    return 0 if relatorio["valido"] else 1


if __name__ == "__main__":
    sys.exit(principal())
