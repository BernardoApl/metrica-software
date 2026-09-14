"""RQ31: validacao das metricas estaticas (RQ30) e piloto sobre os katas reais.

Este modulo valida o CSV produzido pela RQ30 e executa um piloto que roda a
RQ30 sobre o `solucao.py` atual de cada um dos 6 katas do LAB02. O piloto usa
os arquivos reais dos katas (antes de qualquer trial) apenas para validar o
script de metricas de ponta a ponta, sem misturar com dados reais do
experimento.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import rq30_metricas_estaticas as rq30


TRATAMENTOS_VALIDOS = {"com_ia", "sem_ia"}
DIRETORIO_KATAS_PADRAO = Path(__file__).resolve().parent / "katas"
SAIDA_PILOTO_PADRAO = Path(__file__).resolve().parents[2] / "dados" / "lab02_rq31_piloto.csv"


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


def _booleano(valor):
    normalizado = _texto(valor).lower()
    if normalizado in {"true", "1", "sim"}:
        return True
    if normalizado in {"false", "0", "nao", "não"}:
        return False
    return None


def validar_registro(registro: dict, linha: int) -> list[str]:
    erros: list[str] = []

    for coluna in rq30.COLUNAS:
        if coluna not in registro:
            erros.append("linha %d: coluna ausente: %s" % (linha, coluna))
    for campo in ("participante", "kata", "tratamento", "issue", "arquivo", "medido_em_utc"):
        if _texto(registro.get(campo)) == "":
            erros.append("linha %d: campo obrigatorio vazio: %s" % (linha, campo))

    tratamento = _texto(registro.get("tratamento"))
    if tratamento not in TRATAMENTOS_VALIDOS:
        erros.append("linha %d: tratamento invalido: %s" % (linha, tratamento))

    loc = _numero(registro.get("loc"))
    if loc is not None and loc < 0:
        erros.append("linha %d: loc negativo" % linha)

    funcoes = _numero(registro.get("funcoes_analisadas"))
    complexidade_media = _numero(registro.get("complexidade_media"))
    if funcoes is not None and funcoes > 0 and (complexidade_media is None or complexidade_media < 1):
        erros.append("linha %d: complexidade_media invalida para arquivo com funcoes" % linha)

    mi = _numero(registro.get("indice_manutenibilidade"))
    if mi is not None and not 0 <= mi <= 100:
        erros.append("linha %d: indice_manutenibilidade fora do intervalo [0, 100]" % linha)

    disponivel = _booleano(registro.get("duplicacao_disponivel"))
    if disponivel is None:
        erros.append("linha %d: duplicacao_disponivel deve ser booleano" % linha)

    percentual = _numero(registro.get("duplicacao_percentual"))
    if disponivel:
        if percentual is None or not 0 <= percentual <= 100:
            erros.append("linha %d: duplicacao_percentual invalida" % linha)
    elif disponivel is False and percentual is not None:
        erros.append("linha %d: duplicacao_percentual deveria estar vazia quando indisponivel" % linha)

    arquivo = _texto(registro.get("arquivo"))
    if arquivo and not arquivo.endswith(".py"):
        erros.append("linha %d: arquivo analisado nao e .py: %s" % (linha, arquivo))

    return erros


def validar_csv(caminho: Path) -> dict:
    if not caminho.exists():
        return {
            "arquivo": str(caminho),
            "valido": False,
            "total_registros": 0,
            "erros": ["arquivo nao encontrado: %s" % caminho],
            "resumo_tratamento": {},
        }

    erros: list[str] = []
    resumo_tratamento: dict[str, int] = {}
    vistos: set[tuple] = set()

    with caminho.open(newline="", encoding="utf-8") as arquivo:
        leitor = csv.DictReader(arquivo)
        if leitor.fieldnames != list(rq30.COLUNAS):
            erros.append("cabecalho incompativel com a RQ30")
        registros = list(leitor)

    for indice, registro in enumerate(registros, start=2):
        erros.extend(validar_registro(registro, indice))
        chave = (
            _texto(registro.get("participante")),
            _texto(registro.get("kata")),
            _texto(registro.get("tratamento")),
        )
        if chave in vistos:
            erros.append("linha %d: combinacao participante/kata/tratamento duplicada: %s" % (indice, chave))
        vistos.add(chave)
        tratamento = _texto(registro.get("tratamento"))
        resumo_tratamento[tratamento] = resumo_tratamento.get(tratamento, 0) + 1

    if not registros:
        erros.append("arquivo sem registros de medicao")

    return {
        "arquivo": str(caminho),
        "valido": not erros,
        "total_registros": len(registros),
        "erros": erros,
        "resumo_tratamento": resumo_tratamento,
    }


def listar_katas(diretorio: Path = DIRETORIO_KATAS_PADRAO) -> list[Path]:
    return sorted(diretorio.glob("kata*/solucao.py"))


def executar_piloto(saida: Path, diretorio_katas: Path = DIRETORIO_KATAS_PADRAO,
                     sem_duplicacao: bool = False) -> dict:
    katas = listar_katas(diretorio_katas)
    if not katas:
        raise FileNotFoundError("nenhum solucao.py encontrado em %s" % diretorio_katas)
    saida.parent.mkdir(parents=True, exist_ok=True)
    for indice, caminho in enumerate(katas):
        medicao = rq30.medir(caminho.resolve(), sem_duplicacao=sem_duplicacao)
        registro = {
            "participante": "piloto_rq31",
            "kata": caminho.parent.name,
            "tratamento": "com_ia" if indice % 2 == 0 else "sem_ia",
            "issue": "31",
            "trial_id": "",
            "arquivo": str(caminho.resolve()),
        }
        registro.update(medicao)
        rq30.registrar_csv(saida, registro)
    return validar_csv(saida)


def principal(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=rq30.SAIDA_PADRAO,
                        help="CSV da RQ30 a validar. Padrao: dados/lab02_rq30_metricas_estaticas.csv.")
    parser.add_argument("--piloto", action="store_true",
                        help="Roda a RQ30 sobre o solucao.py atual dos 6 katas e valida o CSV gerado.")
    parser.add_argument("--saida-piloto", type=Path, default=SAIDA_PILOTO_PADRAO)
    parser.add_argument("--diretorio-katas", type=Path, default=DIRETORIO_KATAS_PADRAO)
    parser.add_argument("--sem-duplicacao", action="store_true",
                        help="Pula o jscpd no piloto (ambiente sem Node.js disponivel).")
    parser.add_argument("--json", action="store_true", help="Imprime o relatorio em JSON.")
    args = parser.parse_args(argv)

    relatorio = executar_piloto(args.saida_piloto, args.diretorio_katas, args.sem_duplicacao) if args.piloto \
        else validar_csv(args.csv)

    if args.json:
        print(json.dumps(relatorio, ensure_ascii=False, indent=2))
    else:
        print("Arquivo: %s" % relatorio["arquivo"])
        print("Registros: %d" % relatorio["total_registros"])
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
