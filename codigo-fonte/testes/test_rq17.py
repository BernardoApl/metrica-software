"""Testes offline da RQ17."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap import configurar_caminhos  # noqa: E402

configurar_caminhos()

import rq17_idade_issues_fechadas as rq17  # noqa: E402


class TestRQ17(unittest.TestCase):
    def test_monta_registro_valido_estimando_issues_fechadas(self):
        registro = {
            "nome_completo": "org/projeto",
            "rq01_idade_anos": 4.5,
            "rq06_issues_total": 10,
            "rq06_razao_fechadas_total": 0.6,
        }

        linha = rq17.montar_registro(registro)

        self.assertTrue(linha["analisado"])
        self.assertEqual(linha["issues_fechadas"], 6)
        self.assertEqual(linha["origem_issues_fechadas"], rq17.ORIGEM_ESTIMADA)
        self.assertEqual(linha["percentual_issues_fechadas"], 60.0)

    def test_preserva_issues_fechadas_quando_campo_existe(self):
        registro = {
            "nome_completo": "org/projeto",
            "rq01_idade_anos": 4.5,
            "rq06_issues_total": 10,
            "rq06_issues_fechadas": 7,
            "rq06_razao_fechadas_total": 0.7,
        }

        linha = rq17.montar_registro(registro)

        self.assertEqual(linha["issues_fechadas"], 7)
        self.assertEqual(linha["origem_issues_fechadas"], rq17.ORIGEM_COLETADA)

    def test_repositorio_sem_issues_e_descartado_sem_divisao_por_zero(self):
        linha = rq17.montar_registro({
            "nome_completo": "org/vazio",
            "rq01_idade_anos": 3.0,
            "rq06_issues_total": 0,
            "rq06_razao_fechadas_total": None,
        })

        self.assertFalse(linha["analisado"])
        self.assertEqual(linha["status_rq17"], rq17.STATUS_SEM_ISSUES)
        self.assertIsNone(linha["percentual_issues_fechadas"])

    def test_correlacoes_perfeitas(self):
        xs = [1.0, 2.0, 3.0, 4.0]
        ys = [10.0, 20.0, 30.0, 40.0]

        self.assertEqual(rq17.calcular_correlacao_pearson(xs, ys), 1.0)
        self.assertEqual(rq17.calcular_correlacao_spearman(xs, ys), 1.0)

    def test_analisar_conta_descartados_e_classifica(self):
        resultado = rq17.analisar([
            {"nome_completo": "a/a", "rq01_idade_anos": 1.0, "rq06_issues_total": 10, "rq06_razao_fechadas_total": 0.2},
            {"nome_completo": "b/b", "rq01_idade_anos": 2.0, "rq06_issues_total": 10, "rq06_razao_fechadas_total": 0.4},
            {"nome_completo": "c/c", "rq01_idade_anos": 3.0, "rq06_issues_total": 10, "rq06_razao_fechadas_total": 0.6},
            {"nome_completo": "d/d", "rq01_idade_anos": 4.0, "rq06_issues_total": 0, "rq06_razao_fechadas_total": None},
        ])

        resumo = resultado["resumo"]
        self.assertEqual(resumo["total_repositorios"], 4)
        self.assertEqual(resumo["repositorios_analisados"], 3)
        self.assertEqual(resumo["registros_descartados_ou_ausentes"], 1)
        self.assertEqual(resumo["por_status"][rq17.STATUS_SEM_ISSUES], 1)
        self.assertEqual(resumo["correlacao"]["spearman"], 1.0)
        self.assertEqual(resumo["hipotese"], "confirmada")


if __name__ == "__main__":
    unittest.main()
