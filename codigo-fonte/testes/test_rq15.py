"""Testa a correlacao e o agrupamento da RQ15 sem acessar a API."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap import configurar_caminhos  # noqa: E402

configurar_caminhos()

import rq15_idade_issues_fechadas as rq15  # noqa: E402


class TestRQ15(unittest.TestCase):
    def test_extrai_pares_ignora_registros_incompletos(self):
        registros = [
            {"rq01_idade_anos": 5.0, "rq06_razao_fechadas_total": 0.8},
            {"rq01_idade_anos": None, "rq06_razao_fechadas_total": 0.5},
            {"rq01_idade_anos": 3.0, "rq06_razao_fechadas_total": None},
            {"rq01_idade_anos": 3.0},
        ]

        pares = rq15.extrair_pares(registros)

        self.assertEqual(pares, [(5.0, 0.8)])

    def test_correlacao_positiva_perfeita(self):
        pares = [(1.0, 0.1), (2.0, 0.2), (3.0, 0.3), (4.0, 0.4)]

        coeficiente = rq15.calcular_correlacao_pearson(pares)

        self.assertEqual(coeficiente, 1.0)

    def test_correlacao_negativa_perfeita(self):
        pares = [(1.0, 0.8), (2.0, 0.6), (3.0, 0.4), (4.0, 0.2)]

        coeficiente = rq15.calcular_correlacao_pearson(pares)

        self.assertEqual(coeficiente, -1.0)

    def test_correlacao_indeterminada_sem_variancia_em_x(self):
        pares = [(5.0, 0.1), (5.0, 0.9)]

        self.assertIsNone(rq15.calcular_correlacao_pearson(pares))

    def test_correlacao_indeterminada_com_menos_de_dois_pares(self):
        self.assertIsNone(rq15.calcular_correlacao_pearson([]))
        self.assertIsNone(rq15.calcular_correlacao_pearson([(1.0, 0.5)]))

    def test_classifica_forca_e_sinal(self):
        self.assertEqual(rq15.classificar_forca(None), "indeterminada (pares insuficientes ou sem variancia)")
        self.assertEqual(rq15.classificar_forca(0.0), "nula")
        self.assertEqual(rq15.classificar_forca(0.1), "muito fraca positiva")
        self.assertEqual(rq15.classificar_forca(-0.3), "fraca negativa")
        self.assertEqual(rq15.classificar_forca(0.5), "moderada positiva")
        self.assertEqual(rq15.classificar_forca(-0.7), "forte negativa")
        self.assertEqual(rq15.classificar_forca(0.9), "muito forte positiva")

    def test_agrupa_por_faixa_de_idade(self):
        pares = [
            (1.0, 0.2),   # Ate 2 anos
            (1.5, 0.4),   # Ate 2 anos
            (3.0, 0.6),   # 2 a 5 anos
            (7.0, 0.8),   # 5 a 10 anos
            (15.0, 1.0),  # Mais de 10 anos
        ]

        grupos = rq15.agrupar_por_faixa_de_idade(pares)

        self.assertEqual(list(grupos), ["Ate 2 anos", "2 a 5 anos", "5 a 10 anos", "Mais de 10 anos"])
        self.assertEqual(grupos["Ate 2 anos"]["quantidade_repositorios"], 2)
        self.assertEqual(grupos["Ate 2 anos"]["media_razao_fechadas"], 0.3)
        self.assertEqual(grupos["2 a 5 anos"]["quantidade_repositorios"], 1)
        self.assertEqual(grupos["5 a 10 anos"]["mediana_razao_fechadas"], 0.8)
        self.assertEqual(grupos["Mais de 10 anos"]["quantidade_repositorios"], 1)

    def test_faixa_sem_repositorios_fica_com_estatisticas_nulas(self):
        grupos = rq15.agrupar_por_faixa_de_idade([(1.0, 0.5)])

        self.assertEqual(grupos["2 a 5 anos"]["quantidade_repositorios"], 0)
        self.assertIsNone(grupos["2 a 5 anos"]["media_razao_fechadas"])
        self.assertIsNone(grupos["2 a 5 anos"]["mediana_razao_fechadas"])

    def test_resumo_conta_descartados_sem_par_completo(self):
        registros = [
            {"rq01_idade_anos": 1.0, "rq06_razao_fechadas_total": 0.5},
            {"rq01_idade_anos": 2.0, "rq06_razao_fechadas_total": 1.0},
            {"rq01_idade_anos": None, "rq06_razao_fechadas_total": 0.5, "rq01_status": "sem_data_criacao"},
            {"rq01_idade_anos": 4.0, "rq06_razao_fechadas_total": None, "rq06_status": "sem_issues"},
        ]

        resumo = rq15.resumir(registros)

        self.assertEqual(resumo["total_repositorios"], 4)
        self.assertEqual(resumo["pares_utilizados"], 2)
        self.assertEqual(resumo["descartados_sem_par_completo"], 2)
        self.assertIsNotNone(resumo["coeficiente_correlacao_pearson"])
        self.assertIn("por_faixa_de_idade", resumo)


if __name__ == "__main__":
    unittest.main()
