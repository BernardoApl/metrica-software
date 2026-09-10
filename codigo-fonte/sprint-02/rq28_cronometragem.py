"""RQ28: tempo por trial do LAB02, com limite e censura explícitos."""

from __future__ import annotations

import argparse
import csv
import json
import queue
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


COLUNAS = (
    "trial_id", "participante", "kata", "tratamento", "issue", "inicio_utc",
    "fim_utc", "duracao_segundos", "limite_segundos", "status", "sucesso",
    "censurado", "verificacoes", "ultimo_codigo_testes", "comando_testes", "diretorio",
)
SAIDA_PADRAO = Path(__file__).resolve().parents[2] / "dados" / "lab02_rq28_tempos.csv"


def limite_valido(texto: str) -> float:
    valor = float(texto)
    if not 0 < valor <= 35:
        raise argparse.ArgumentTypeError("O limite deve ser maior que zero e no máximo 35 minutos.")
    return valor


def registrar_csv(caminho: Path, registro: dict) -> None:
    """Acrescenta uma tentativa sem sobrescrever as anteriores."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    existente = caminho.exists() and caminho.stat().st_size > 0
    if existente:
        with caminho.open(newline="", encoding="utf-8") as arquivo:
            if next(csv.reader(arquivo), None) != list(COLUNAS):
                raise ValueError("O CSV existente tem colunas incompatíveis com a RQ28.")
    with caminho.open("a", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS)
        if not existente:
            escritor.writeheader()
        escritor.writerow(registro)


def ler_comandos(fila: queue.Queue) -> None:
    while True:
        try:
            fila.put(input().strip().lower())
        except EOFError:
            fila.put("sair")
            return


def encerrar_testes(processo: subprocess.Popen) -> None:
    if processo.poll() is not None:
        return
    # O grupo de processos impede que filhos do executor continuem após o limite.
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(processo.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
    else:
        import os
        import signal
        try:
            os.killpg(processo.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    processo.wait()


def medir(comando: list[str], diretorio: Path, limite: float, fila: queue.Queue) -> dict:
    """Cronometra inclusive edição, interação com IA e execução dos testes.

    A aprovação é observada quando o comando de aceitação termina com código 0
    antes do prazo. A interface não permite pausar nem declarar sucesso manual.
    """
    inicio_utc = datetime.now(timezone.utc).isoformat()
    inicio = time.monotonic()
    prazo = inicio + limite
    processo = None
    verificacoes = 0
    ultimo_codigo = ""
    status = "interrompido"
    fim = inicio
    try:
        while True:
            fim = time.monotonic()
            if fim >= prazo:
                status = "limite_atingido"
                break
            if processo is not None:
                codigo = processo.poll()
                if codigo is not None:
                    processo.wait()
                    ultimo_codigo = codigo
                    processo = None
                    fim = time.monotonic()
                    if fim >= prazo:
                        status = "limite_atingido"
                        break
                    if codigo == 0:
                        status = "sucesso"
                        break
                    print("Testes não passaram (código %s). O cronômetro continua." % codigo)
            try:
                acao = fila.get(timeout=min(0.05, max(0, prazo - time.monotonic())))
            except queue.Empty:
                continue
            if acao == "sair":
                fim = time.monotonic()
                status = "limite_atingido" if fim >= prazo else "interrompido"
                break
            if acao == "testar" and processo is None:
                if time.monotonic() >= prazo:
                    continue
                opcoes = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if sys.platform == "win32" else {"start_new_session": True}
                processo = subprocess.Popen(
                    comando, cwd=diretorio, stdin=subprocess.DEVNULL, **opcoes,
                )
                verificacoes += 1
            elif acao == "tempo":
                print("Restam %.1f segundos." % max(0, prazo - time.monotonic()))
            elif acao == "testar":
                print("Já existe uma verificação em andamento.")
            else:
                print("Comandos: testar | tempo | sair")
    except KeyboardInterrupt:
        fim = time.monotonic()
        status = "limite_atingido" if fim >= prazo else "interrompido"
    except OSError as erro:
        fim = time.monotonic()
        status = "erro_execucao"
        print("Falha ao executar testes: %s" % erro, file=sys.stderr)
    finally:
        fim_utc = datetime.now(timezone.utc).isoformat()
        if processo is not None:
            encerrar_testes(processo)
    return {
        "inicio_utc": inicio_utc,
        "fim_utc": fim_utc,
        "duracao_segundos": limite if status == "limite_atingido" else round(max(0, fim - inicio), 6),
        "limite_segundos": limite,
        "status": status,
        "sucesso": status == "sucesso",
        "censurado": status == "limite_atingido",
        "verificacoes": verificacoes,
        "ultimo_codigo_testes": ultimo_codigo,
    }


def principal(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--participante", required=True)
    parser.add_argument("--kata", required=True)
    parser.add_argument("--tratamento", choices=("com_ia", "sem_ia"), required=True)
    parser.add_argument("--issue", required=True, help="Número ou URL da Issue do trial.")
    parser.add_argument("--limite-minutos", type=limite_valido, default=35.0)
    parser.add_argument("--diretorio", type=Path, default=Path.cwd())
    parser.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    parser.add_argument("--testes", nargs=argparse.REMAINDER, required=True,
                        help="Última opção: executável e argumentos dos testes de aceitação.")
    args = parser.parse_args(argv)
    if not args.testes:
        parser.error("Informe o comando após --testes.")
    if not args.diretorio.is_dir():
        parser.error("O diretório dos testes não existe.")
    if any(not getattr(args, campo).strip() for campo in ("participante", "kata", "issue")):
        parser.error("Participante, kata e Issue não podem estar vazios.")
    print("Limite: %g minutos. Prepare o ambiente antes de iniciar." % args.limite_minutos)
    try:
        input("Pressione Enter ao iniciar a resolução do kata: ")
    except (EOFError, KeyboardInterrupt):
        print("\nTentativa não iniciada.")
        return 1
    print("Cronômetro iniciado. Comandos: testar | tempo | sair. Sem pausa.")
    fila = queue.Queue()
    threading.Thread(target=ler_comandos, args=(fila,), daemon=True).start()
    registro = medir(args.testes, args.diretorio.resolve(), args.limite_minutos * 60, fila)
    registro.update({
        "trial_id": str(uuid.uuid4()), "participante": args.participante,
        "kata": args.kata, "tratamento": args.tratamento, "issue": args.issue,
        "comando_testes": json.dumps(args.testes, ensure_ascii=False),
        "diretorio": str(args.diretorio.resolve()),
    })
    try:
        registrar_csv(args.saida, registro)
    except (OSError, ValueError) as erro:
        print("Não foi possível salvar o CSV: %s" % erro, file=sys.stderr)
        print(json.dumps(registro, ensure_ascii=False), file=sys.stderr)
        return 2
    print("Trial encerrado: %s | %.3f segundos" % (registro["status"], registro["duracao_segundos"]))
    print("Registro salvo em: %s" % args.saida.resolve())
    return 0 if registro["sucesso"] else 1


if __name__ == "__main__":
    sys.exit(principal())
