"""RQ30: ambiente e script de metricas estaticas (complexidade, LOC e duplicacao) do LAB02."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from radon.complexity import cc_visit
from radon.metrics import mi_visit
from radon.raw import analyze as radon_analyze


COLUNAS = (
    "participante", "kata", "tratamento", "issue", "trial_id", "arquivo",
    "medido_em_utc", "loc", "sloc", "lloc", "comentarios", "linhas_em_branco",
    "funcoes_analisadas", "complexidade_media", "complexidade_maxima",
    "indice_manutenibilidade", "duplicacao_disponivel", "duplicacao_percentual",
    "linhas_duplicadas", "linhas_analisadas_duplicacao",
)
SAIDA_PADRAO = Path(__file__).resolve().parents[2] / "dados" / "lab02_rq30_metricas_estaticas.csv"
MIN_LINHAS_PADRAO = 3
MIN_TOKENS_PADRAO = 20
METRICAS_INDISPONIVEIS = {
    "loc": "", "sloc": "", "lloc": "", "comentarios": "", "linhas_em_branco": "",
    "funcoes_analisadas": "", "complexidade_media": "", "complexidade_maxima": "",
    "indice_manutenibilidade": "",
}
DUPLICACAO_INDISPONIVEL = {
    "duplicacao_disponivel": False, "duplicacao_percentual": "",
    "linhas_duplicadas": "", "linhas_analisadas_duplicacao": "",
}


def analisar_complexidade_e_loc(codigo: str) -> dict:
    """Complexidade ciclomatica media (Radon `cc`), LOC (Radon `raw`) e MI (Radon `mi`)."""
    try:
        blocos = cc_visit(codigo)
        bruto = radon_analyze(codigo)
        indice = mi_visit(codigo, True)
    except SyntaxError as erro:
        print("Aviso: nao foi possivel analisar o codigo (%s); complexidade/LOC indisponiveis." % erro,
              file=sys.stderr)
        return dict(METRICAS_INDISPONIVEIS)
    complexidades = [bloco.complexity for bloco in blocos]
    return {
        "loc": bruto.loc,
        "sloc": bruto.sloc,
        "lloc": bruto.lloc,
        "comentarios": bruto.comments,
        "linhas_em_branco": bruto.blank,
        "funcoes_analisadas": len(blocos),
        "complexidade_media": round(sum(complexidades) / len(complexidades), 4) if complexidades else 0.0,
        "complexidade_maxima": max(complexidades) if complexidades else 0,
        "indice_manutenibilidade": round(indice, 4),
    }


def analisar_duplicacao(caminho: Path, min_linhas: int, min_tokens: int) -> dict:
    """Percentual de linhas duplicadas via `jscpd`, executado sob demanda com `npx`.

    O jscpd e uma ferramenta Node.js, nao uma dependencia Python do projeto. Se
    `npx` nao estiver disponivel no ambiente, a duplicacao fica marcada como
    indisponivel em vez de interromper a coleta das demais metricas.
    """
    npx = shutil.which("npx")
    if npx is None:
        print("Aviso: 'npx' nao encontrado; duplicacao (jscpd) nao sera medida.", file=sys.stderr)
        return dict(DUPLICACAO_INDISPONIVEL)
    with tempfile.TemporaryDirectory() as diretorio_saida:
        comando = [
            npx, "--yes", "jscpd", str(caminho),
            "--reporters", "json", "--output", diretorio_saida, "--silent",
            "--min-lines", str(min_linhas), "--min-tokens", str(min_tokens),
        ]
        try:
            subprocess.run(comando, capture_output=True, text=True, timeout=120, check=False)
        except (OSError, subprocess.TimeoutExpired) as erro:
            print("Aviso: falha ao executar jscpd (%s); duplicacao nao sera medida." % erro, file=sys.stderr)
            return dict(DUPLICACAO_INDISPONIVEL)
        relatorio = Path(diretorio_saida) / "jscpd-report.json"
        if not relatorio.exists():
            print("Aviso: jscpd nao gerou relatorio; duplicacao nao sera medida.", file=sys.stderr)
            return dict(DUPLICACAO_INDISPONIVEL)
        total = json.loads(relatorio.read_text(encoding="utf-8"))["statistics"]["total"]
    return {
        "duplicacao_disponivel": True,
        "duplicacao_percentual": round(total["percentage"], 4),
        "linhas_duplicadas": total["duplicatedLines"],
        "linhas_analisadas_duplicacao": total["lines"],
    }


def medir(caminho_arquivo: Path, min_linhas: int = MIN_LINHAS_PADRAO,
          min_tokens: int = MIN_TOKENS_PADRAO, sem_duplicacao: bool = False) -> dict:
    """Mede complexidade, LOC, MI e duplicacao do arquivo final de um trial."""
    codigo = caminho_arquivo.read_text(encoding="utf-8")
    registro = {"medido_em_utc": datetime.now(timezone.utc).isoformat()}
    registro.update(analisar_complexidade_e_loc(codigo))
    if sem_duplicacao:
        registro.update(DUPLICACAO_INDISPONIVEL)
    else:
        registro.update(analisar_duplicacao(caminho_arquivo, min_linhas, min_tokens))
    return registro


def registrar_csv(caminho: Path, registro: dict) -> None:
    """Acrescenta uma medicao sem sobrescrever as anteriores."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    existente = caminho.exists() and caminho.stat().st_size > 0
    if existente:
        with caminho.open(newline="", encoding="utf-8") as arquivo:
            if next(csv.reader(arquivo), None) != list(COLUNAS):
                raise ValueError("O CSV existente tem colunas incompativeis com a RQ30.")
    with caminho.open("a", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS)
        if not existente:
            escritor.writeheader()
        escritor.writerow(registro)


def principal(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--participante", required=True)
    parser.add_argument("--kata", required=True)
    parser.add_argument("--tratamento", choices=("com_ia", "sem_ia"), required=True)
    parser.add_argument("--issue", required=True, help="Numero ou URL da Issue do trial.")
    parser.add_argument("--arquivo", type=Path, required=True,
                        help="Caminho do solucao.py final do trial.")
    parser.add_argument("--trial-id", default="", help="trial_id da RQ28, se houver, para cruzar os dados.")
    parser.add_argument("--min-linhas", type=int, default=MIN_LINHAS_PADRAO,
                        help="min-lines repassado ao jscpd (padrao: %(default)s).")
    parser.add_argument("--min-tokens", type=int, default=MIN_TOKENS_PADRAO,
                        help="min-tokens repassado ao jscpd (padrao: %(default)s).")
    parser.add_argument("--sem-duplicacao", action="store_true",
                        help="Pula a medicao de duplicacao (util sem Node.js/jscpd disponivel).")
    parser.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    parser.add_argument("--json", action="store_true", help="Imprime o registro em JSON.")
    args = parser.parse_args(argv)

    if not args.arquivo.is_file():
        parser.error("Arquivo nao encontrado: %s" % args.arquivo)
    if any(not getattr(args, campo).strip() for campo in ("participante", "kata", "issue")):
        parser.error("Participante, kata e Issue nao podem estar vazios.")

    medicao = medir(args.arquivo.resolve(), args.min_linhas, args.min_tokens, args.sem_duplicacao)
    registro = {
        "participante": args.participante, "kata": args.kata, "tratamento": args.tratamento,
        "issue": args.issue, "trial_id": args.trial_id, "arquivo": str(args.arquivo.resolve()),
    }
    registro.update(medicao)

    try:
        registrar_csv(args.saida, registro)
    except (OSError, ValueError) as erro:
        print("Nao foi possivel salvar o CSV: %s" % erro, file=sys.stderr)
        print(json.dumps(registro, ensure_ascii=False, default=str), file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(registro, ensure_ascii=False, default=str, indent=2))
    else:
        print("LOC: %s | Complexidade media: %s | MI: %s" % (
            registro["loc"], registro["complexidade_media"], registro["indice_manutenibilidade"]))
        if registro["duplicacao_disponivel"]:
            print("Duplicacao: %s%% (%s/%s linhas)" % (
                registro["duplicacao_percentual"], registro["linhas_duplicadas"],
                registro["linhas_analisadas_duplicacao"]))
        else:
            print("Duplicacao: indisponivel")
    print("Registro salvo em: %s" % args.saida.resolve())
    return 0


if __name__ == "__main__":
    sys.exit(principal())
