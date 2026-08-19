"""Exportacao do snapshot semanal da coleta de repositorios para CSV.

RQ14 -- alem do JSON completo (que preserva o no bruto da API para auditoria),
o grupo tambem quer um snapshot tabular, mais facil de abrir em planilha e de
comparar semana a semana. Este modulo achata a lista de repositorios coletados
(descartando o campo ``bruto``, que nao e tabular) e grava em CSV, com um nome
de arquivo padrao que carrega o ano e a semana ISO da coleta.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Iterable


def nome_arquivo_semanal(referencia: datetime, diretorio: Path) -> Path:
    """Monta o caminho do snapshot semanal a partir da data de referencia.

    Usa o ano e a semana ISO (``isocalendar``) para que coletas repetidas na
    mesma semana caiam no mesmo arquivo, e coletas de semanas diferentes gerem
    arquivos distintos -- o proposito do snapshot semanal.
    """
    ano_iso, semana_iso, _ = referencia.isocalendar()
    return diretorio / ("rq14_snapshot_semanal_%d-W%02d.csv" % (ano_iso, semana_iso))


def achatar_repositorio(registro: dict) -> dict:
    """Remove o no bruto da API, mantendo apenas os campos tabulares (``rq04_*``, ``rq05_*`` etc.)."""
    return {chave: valor for chave, valor in registro.items() if chave != "bruto"}


def escrever_csv(repositorios: Iterable[dict], caminho: Path) -> Path:
    """Grava os repositorios achatados em CSV.

    As colunas sao a uniao das chaves de todos os registros, na ordem em que
    aparecem, para que um campo ausente em um repositorio (por exemplo, sem
    linguagem definida) nao derrube a exportacao dos demais.

    :raises ValueError: se ``repositorios`` estiver vazio -- nao ha cabecalho a inferir.
    """
    linhas = [achatar_repositorio(registro) for registro in repositorios]
    if not linhas:
        raise ValueError("Nao ha repositorios para exportar em CSV.")

    colunas = []
    vistas = set()
    for linha in linhas:
        for chave in linha:
            if chave not in vistas:
                vistas.add(chave)
                colunas.append(chave)

    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=colunas)
        escritor.writeheader()
        escritor.writerows(linhas)

    return caminho
