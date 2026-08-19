"""Testes offline da exportacao do snapshot semanal em CSV (RQ14)."""

from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "coleta"))
from exportar_csv import achatar_repositorio, escrever_csv, nome_arquivo_semanal  # noqa: E402


class TestNomeArquivoSemanal(unittest.TestCase):
    def test_usa_ano_e_semana_iso(self):
        referencia = datetime(2026, 8, 19, tzinfo=timezone.utc)  # semana ISO 34 de 2026
        caminho = nome_arquivo_semanal(referencia, Path("dados"))
        self.assertEqual(caminho, Path("dados/rq14_snapshot_semanal_2026-W34.csv"))

    def test_mesma_semana_gera_mesmo_arquivo(self):
        segunda = datetime(2026, 8, 17, tzinfo=timezone.utc)
        domingo = datetime(2026, 8, 23, tzinfo=timezone.utc)
        self.assertEqual(
            nome_arquivo_semanal(segunda, Path("dados")),
            nome_arquivo_semanal(domingo, Path("dados")),
        )


class TestAchatarRepositorio(unittest.TestCase):
    def test_remove_apenas_o_no_bruto(self):
        registro = {"nome_completo": "a/b", "estrelas": 10, "bruto": {"id": "xyz"}}
        self.assertEqual(achatar_repositorio(registro), {"nome_completo": "a/b", "estrelas": 10})


class TestEscreverCsv(unittest.TestCase):
    def test_grava_cabecalho_uniao_e_linhas(self):
        repositorios = [
            {"nome_completo": "a/b", "estrelas": 10, "rq04_dias": 1.0, "bruto": {}},
            {"nome_completo": "c/d", "estrelas": 20, "rq05_linguagem_primaria": "Python", "bruto": {}},
        ]
        with tempfile.TemporaryDirectory() as diretorio:
            caminho = Path(diretorio) / "snapshot.csv"
            escrever_csv(repositorios, caminho)

            with open(caminho, newline="", encoding="utf-8") as arquivo:
                linhas = list(csv.DictReader(arquivo))

        self.assertEqual(linhas[0]["nome_completo"], "a/b")
        self.assertEqual(linhas[0]["rq05_linguagem_primaria"], "")
        self.assertEqual(linhas[1]["rq04_dias"], "")
        self.assertNotIn("bruto", linhas[0])

    def test_lista_vazia_levanta_value_error(self):
        with tempfile.TemporaryDirectory() as diretorio:
            with self.assertRaises(ValueError):
                escrever_csv([], Path(diretorio) / "snapshot.csv")


if __name__ == "__main__":
    unittest.main()
