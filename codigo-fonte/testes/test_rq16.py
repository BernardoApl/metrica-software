"""Testa a correlacao e o agrupamento da RQ16 sem acessar a API."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap import configurar_caminhos  # noqa: E402

configurar_caminhos()

import rq16_prs_releases as rq16  # noqa: E402


class TestRQ16(unittest.TestCase):
    def test_extrai_pares_ignora_registros_incompletos(self):
        registros = [
            {"rq02_pull_requests_aceitos": 40, "rq03_total_releases": 8},
            {"rq02_pull_requests_aceitos": None, "rq03_total_releases": 5},
            {"rq02_pull_requests_aceitos": 10, "rq03_total_releases": None},
            {"rq02_pull_requests_aceitos": 10},
        ]

        pares = rq16.extrair_pares(registros)

        self.assertEqual(pares, [(40.0, 8.0)])

    def test_correlacao_positiva_perfeita(self):
        pares = [(10.0, 1.0), (20.0, 2.0), (30.0, 3.0), (40.0, 4.0)]

        self.assertEqual(rq16.calcular_correlacao_pearson(pares), 1.0)

    def test_correlacao_negativa_perfeita(self):
        pares = [(10.0, 4.0), (20.0, 3.0), (30.0, 2.0), (40.0, 1.0)]

        self.assertEqual(rq16.calcular_correlacao_pearson(pares), -1.0)

    def test_correlacao_indeterminada_sem_variancia(self):
        self.assertIsNone(rq16.calcular_correlacao_pearson([(5.0, 1.0), (5.0, 9.0)]))

    def test_correlacao_indeterminada_com_menos_de_dois_pares(self):
        self.assertIsNone(rq16.calcular_correlacao_pearson([]))
        self.assertIsNone(rq16.calcular_correlacao_pearson([(1.0, 1.0)]))

    def test_classifica_forca_e_sinal(self):
        self.assertEqual(rq16.classificar_forca(None), "indeterminada (pares insuficientes ou sem variancia)")
        self.assertEqual(rq16.classificar_forca(0.0), "nula")
        self.assertEqual(rq16.classificar_forca(0.1), "muito fraca positiva")
        self.assertEqual(rq16.classificar_forca(-0.3), "fraca negativa")
        self.assertEqual(rq16.classificar_forca(0.5), "moderada positiva")
        self.assertEqual(rq16.classificar_forca(-0.7), "forte negativa")
        self.assertEqual(rq16.classificar_forca(0.9), "muito forte positiva")

    def test_agrupa_por_faixa_de_releases(self):
        pares = [
            (5.0, 0.0),     # Sem releases
            (10.0, 3.0),    # 1 a 10 releases
            (20.0, 10.0),   # 1 a 10 releases
            (50.0, 30.0),   # 11 a 50 releases
            (100.0, 80.0),  # Mais de 50 releases
        ]

        grupos = rq16.agrupar_por_faixa_de_releases(pares)

        self.assertEqual(
            list(grupos),
            ["Sem releases", "1 a 10 releases", "11 a 50 releases", "Mais de 50 releases"],
        )
        self.assertEqual(grupos["Sem releases"]["quantidade_repositorios"], 1)
        self.assertEqual(grupos["1 a 10 releases"]["quantidade_repositorios"], 2)
        self.assertEqual(grupos["1 a 10 releases"]["media_prs_aceitas"], 15.0)
        self.assertEqual(grupos["11 a 50 releases"]["quantidade_repositorios"], 1)
        self.assertEqual(grupos["Mais de 50 releases"]["quantidade_repositorios"], 1)

    def test_faixa_sem_repositorios_fica_com_estatisticas_nulas(self):
        grupos = rq16.agrupar_por_faixa_de_releases([(5.0, 0.0)])

        self.assertEqual(grupos["1 a 10 releases"]["quantidade_repositorios"], 0)
        self.assertIsNone(grupos["1 a 10 releases"]["media_prs_aceitas"])
        self.assertIsNone(grupos["1 a 10 releases"]["mediana_prs_aceitas"])

    def test_resumo_conta_descartados_sem_par_completo(self):
        registros = [
            {"rq02_pull_requests_aceitos": 10, "rq03_total_releases": 1},
            {"rq02_pull_requests_aceitos": 20, "rq03_total_releases": 2},
            {"rq02_pull_requests_aceitos": None, "rq03_total_releases": 3, "rq02_status_graphql": "dados_ausentes"},
            {"rq02_pull_requests_aceitos": 30, "rq03_total_releases": None, "rq03_status_graphql": "dados_ausentes"},
        ]

        resumo = rq16.resumir(registros)

        self.assertEqual(resumo["total_repositorios"], 4)
        self.assertEqual(resumo["pares_utilizados"], 2)
        self.assertEqual(resumo["descartados_sem_par_completo"], 2)
        self.assertIsNotNone(resumo["coeficiente_correlacao_pearson"])
        self.assertIn("por_faixa_de_releases", resumo)


if __name__ == "__main__":
    unittest.main()
