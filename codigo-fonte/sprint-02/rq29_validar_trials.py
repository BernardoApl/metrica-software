"""RQ29: validacao dos registros de trials e piloto da coleta.

Este modulo valida o CSV produzido pela RQ28 e executa um piloto sintetico da
coleta de tempo. O piloto nao usa um kata real, para nao misturar evidencia de
instrumentacao com dados do experimento.
"""

from __future__ import annotations

import argparse
import csv
import json
import queue
import sys
import uuid
from datetime import datetime
from pathlib import Path

import rq28_cronometragem as rq28


STATUS_VALIDOS = {"sucesso", "limite_atingido", "interrompido", "erro_execucao"}
TRATAMENTOS_VALIDOS = {"com_ia", "sem_ia"}
SAIDA_PILOTO_PADRAO = Path(__file__).resolve().parents[2] / "dados" / "lab02_rq29_piloto.csv"


def _texto(valor) -> str:
    return "" if valor is None else str(valor).strip()


def _booleano(valor: str):
    normalizado = _texto(valor).lower()
    if normalizado in {"true", "1", "sim"}:
        return True
    if normalizado in {"false", "0", "nao", "não"}:
        return False
    return None


def _datetime_iso(valor: str):
    texto = _texto(valor)
    if texto.endswith("Z"):
        texto = texto[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(texto)
    except ValueError:
        return None


def validar_registro(registro: dict, linha: int, exigir_diretorio_existente: bool = False) -> list[str]:
    erros: list[str] = []

    for coluna in rq28.COLUNAS:
        if coluna not in registro:
            erros.append("linha %d: coluna ausente: %s" % (linha, coluna))
        elif coluna != "ultimo_codigo_testes" and _texto(registro[coluna]) == "":
            erros.append("linha %d: campo obrigatorio vazio: %s" % (linha, coluna))

    trial_id = _texto(registro.get("trial_id"))
    try:
        uuid.UUID(trial_id)
    except ValueError:
        erros.append("linha %d: trial_id invalido" % linha)

    tratamento = _texto(registro.get("tratamento"))
    if tratamento not in TRATAMENTOS_VALIDOS:
        erros.append("linha %d: tratamento invalido: %s" % (linha, tratamento))

    status = _texto(registro.get("status"))
    if status not in STATUS_VALIDOS:
        erros.append("linha %d: status invalido: %s" % (linha, status))

    sucesso = _booleano(registro.get("sucesso"))
    censurado = _booleano(registro.get("censurado"))
    if sucesso is None:
        erros.append("linha %d: sucesso deve ser booleano" % linha)
    if censurado is None:
        erros.append("linha %d: censurado deve ser booleano" % linha)
    if sucesso is not None and sucesso != (status == "sucesso"):
        erros.append("linha %d: sucesso incoerente com status" % linha)
    if censurado is not None and censurado != (status == "limite_atingido"):
        erros.append("linha %d: censurado incoerente com status" % linha)

    inicio = _datetime_iso(registro.get("inicio_utc"))
    fim = _datetime_iso(registro.get("fim_utc"))
    if inicio is None:
        erros.append("linha %d: inicio_utc invalido" % linha)
    if fim is None:
        erros.append("linha %d: fim_utc invalido" % linha)
    if inicio is not None and fim is not None and fim < inicio:
        erros.append("linha %d: fim_utc anterior ao inicio_utc" % linha)

    try:
        duracao = float(_texto(registro.get("duracao_segundos")))
    except ValueError:
        duracao = None
        erros.append("linha %d: duracao_segundos invalida" % linha)

    try:
        limite = float(_texto(registro.get("limite_segundos")))
    except ValueError:
        limite = None
        erros.append("linha %d: limite_segundos invalido" % linha)

    if duracao is not None and duracao < 0:
        erros.append("linha %d: duracao_segundos negativa" % linha)
    if limite is not None and not 0 < limite <= 2100:
        erros.append("linha %d: limite_segundos fora do intervalo (0, 2100]" % linha)
    if duracao is not None and limite is not None and duracao > limite + 0.001:
        erros.append("linha %d: duracao_segundos maior que limite_segundos" % linha)
    if status == "limite_atingido" and duracao is not None and limite is not None:
        if abs(duracao - limite) > 0.001:
            erros.append("linha %d: trial censurado deve ter duracao igual ao limite" % linha)

    try:
        verificacoes = int(_texto(registro.get("verificacoes")))
    except ValueError:
        verificacoes = None
        erros.append("linha %d: verificacoes invalido" % linha)
    if verificacoes is not None and verificacoes < 0:
        erros.append("linha %d: verificacoes negativo" % linha)
    if status == "sucesso" and verificacoes == 0:
        erros.append("linha %d: sucesso sem nenhuma verificacao" % linha)

    ultimo_codigo = _texto(registro.get("ultimo_codigo_testes"))
    if ultimo_codigo:
        try:
            int(ultimo_codigo)
        except ValueError:
            erros.append("linha %d: ultimo_codigo_testes deve ser inteiro ou vazio" % linha)
    if (status == "sucesso" or sucesso is True) and ultimo_codigo != "0":
        erros.append("linha %d: sucesso exige ultimo_codigo_testes igual a 0" % linha)

    try:
        comando = json.loads(_texto(registro.get("comando_testes")))
    except json.JSONDecodeError:
        comando = None
        erros.append("linha %d: comando_testes nao e JSON valido" % linha)
    if not isinstance(comando, list) or not comando or not all(isinstance(item, str) for item in comando):
        erros.append("linha %d: comando_testes deve ser lista JSON nao vazia de strings" % linha)

    diretorio = Path(_texto(registro.get("diretorio")))
    if exigir_diretorio_existente and not diretorio.is_dir():
        erros.append("linha %d: diretorio nao existe: %s" % (linha, diretorio))

    return erros


def validar_csv(caminho: Path, exigir_diretorio_existente: bool = False) -> dict:
    if not caminho.exists():
        return {
            "arquivo": str(caminho),
            "valido": False,
            "total_registros": 0,
            "erros": ["arquivo nao encontrado: %s" % caminho],
            "resumo_status": {},
            "resumo_tratamento": {},
        }

    erros: list[str] = []
    resumo_status: dict[str, int] = {}
    resumo_tratamento: dict[str, int] = {}
    vistos: set[str] = set()

    with caminho.open(newline="", encoding="utf-8") as arquivo:
        leitor = csv.DictReader(arquivo)
        if leitor.fieldnames != list(rq28.COLUNAS):
            erros.append("cabecalho incompativel com a RQ28")
        registros = list(leitor)

    for indice, registro in enumerate(registros, start=2):
        erros.extend(validar_registro(registro, indice, exigir_diretorio_existente))
        trial_id = _texto(registro.get("trial_id"))
        if trial_id in vistos:
            erros.append("linha %d: trial_id duplicado: %s" % (indice, trial_id))
        vistos.add(trial_id)
        status = _texto(registro.get("status"))
        tratamento = _texto(registro.get("tratamento"))
        resumo_status[status] = resumo_status.get(status, 0) + 1
        resumo_tratamento[tratamento] = resumo_tratamento.get(tratamento, 0) + 1

    if not registros:
        erros.append("arquivo sem registros de trial")

    return {
        "arquivo": str(caminho),
        "valido": not erros,
        "total_registros": len(registros),
        "erros": erros,
        "resumo_status": resumo_status,
        "resumo_tratamento": resumo_tratamento,
    }


def executar_piloto(saida: Path) -> dict:
    fila = queue.Queue()
    fila.put("testar")
    saida.parent.mkdir(parents=True, exist_ok=True)
    diretorio = saida.parent.resolve()
    comando = [sys.executable, "-c", "raise SystemExit(0)"]
    medicao = rq28.medir(comando, diretorio, limite=60, fila=fila)
    registro = {
        "trial_id": str(uuid.uuid4()),
        "participante": "piloto_rq29",
        "kata": "piloto_instrumentacao",
        "tratamento": "sem_ia",
        "issue": "29",
        "comando_testes": json.dumps(comando, ensure_ascii=False),
        "diretorio": str(diretorio),
    }
    registro.update(medicao)
    rq28.registrar_csv(saida, registro)
    return validar_csv(saida)


def principal(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=rq28.SAIDA_PADRAO,
                        help="CSV da RQ28 a validar. Padrao: dados/lab02_rq28_tempos.csv.")
    parser.add_argument("--exigir-diretorio-existente", action="store_true",
                        help="Tambem valida se o diretorio registrado ainda existe.")
    parser.add_argument("--piloto", action="store_true",
                        help="Executa um trial sintetico e valida o CSV gerado.")
    parser.add_argument("--saida-piloto", type=Path, default=SAIDA_PILOTO_PADRAO,
                        help="CSV de saida do piloto sintetico.")
    parser.add_argument("--json", action="store_true",
                        help="Imprime o relatorio em JSON.")
    args = parser.parse_args(argv)

    relatorio = executar_piloto(args.saida_piloto) if args.piloto else validar_csv(
        args.csv, args.exigir_diretorio_existente,
    )

    if args.json:
        print(json.dumps(relatorio, ensure_ascii=False, indent=2))
    else:
        print("Arquivo: %s" % relatorio["arquivo"])
        print("Registros: %d" % relatorio["total_registros"])
        print("Status: %s" % relatorio["resumo_status"])
        print("Tratamentos: %s" % relatorio["resumo_tratamento"])
        if relatorio["valido"]:
            print("Validacao OK.")
        else:
            print("Validacao falhou:")
            for erro in relatorio["erros"]:
                print("- %s" % erro)
    return 0 if relatorio["valido"] else 1


if __name__ == "__main__":
    sys.exit(principal())
