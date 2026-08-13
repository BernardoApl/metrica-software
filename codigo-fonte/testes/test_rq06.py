"""Testa o calculo e o resumo da RQ06 sem acessar a API."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap import configurar_caminhos  # noqa: E402

configurar_caminhos()

import rq06_issues  # noqa: E402


class TestRQ06(unittest.TestCase):
    def test_calcula_razao_de_issues_fechadas(self):
        no = {
            "issues": {"totalCount": 20},
            "issuesFechadas": {"totalCount": 15},
        }

        resultado = rq06_issues.calcular(no)

        self.assertEqual(resultado["rq06_issues_total"], 20)
        self.assertEqual(resultado["rq06_issues_fechadas"], 15)
        self.assertEqual(resultado["rq06_razao_fechadas_total"], 0.75)
        self.assertEqual(resultado["rq06_status"], "ok")

    def test_repositorio_sem_issues_nao_divide_por_zero(self):
        resultado = rq06_issues.calcular({
            "issues": {"totalCount": 0},
            "issuesFechadas": {"totalCount": 0},
        })

        self.assertEqual(resultado["rq06_issues_total"], 0)
        self.assertEqual(resultado["rq06_issues_fechadas"], 0)
        self.assertIsNone(resultado["rq06_razao_fechadas_total"])
        self.assertEqual(resultado["rq06_status"], "sem_issues")

    def test_campos_nao_coletados_nao_sao_tratados_como_zero(self):
        resultado = rq06_issues.calcular({})

        self.assertIsNone(resultado["rq06_issues_total"])
        self.assertIsNone(resultado["rq06_issues_fechadas"])
        self.assertIsNone(resultado["rq06_razao_fechadas_total"])
        self.assertEqual(resultado["rq06_status"], "dados_ausentes")

    def test_resumo_ignora_repositorios_sem_issues(self):
        registros = [
            {"rq06_razao_fechadas_total": 0.25, "rq06_status": "ok"},
            {"rq06_razao_fechadas_total": 0.75, "rq06_status": "ok"},
            {"rq06_razao_fechadas_total": None, "rq06_status": "sem_issues"},
        ]

        resumo = rq06_issues.resumir(registros)

        self.assertEqual(resumo["total_repositorios"], 3)
        self.assertEqual(resumo["com_issues"], 2)
        self.assertEqual(resumo["sem_issues"], 1)
        self.assertEqual(resumo["dados_ausentes"], 0)
        self.assertEqual(resumo["media_razao"], 0.5)
        self.assertEqual(resumo["mediana_razao"], 0.5)

    def test_resumo_corrige_zero_falso_de_coleta_sem_campos(self):
        registros = [{
            "rq06_razao_fechadas_total": None,
            "rq06_status": "sem_issues",
            "bruto": {"nameWithOwner": "owner/repo"},
        }]

        resumo = rq06_issues.resumir(registros)

        self.assertEqual(resumo["sem_issues"], 0)
        self.assertEqual(resumo["dados_ausentes"], 1)


if __name__ == "__main__":
    unittest.main()
