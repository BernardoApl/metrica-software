"""Testa a extracao e o agrupamento da RQ07 sem acessar a API."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap import configurar_caminhos  # noqa: E402

configurar_caminhos()

import rq07_por_linguagem  # noqa: E402


class TestRQ07(unittest.TestCase):
    def test_extrai_resultados_de_rq02_e_rq03(self):
        no = {
            "pullRequestsAceitos": {"totalCount": 42},
            "releases": {"totalCount": 7},
        }

        resultado = rq07_por_linguagem.extrair_metricas_base(no)

        self.assertEqual(resultado["rq02_pull_requests_aceitos"], 42)
        self.assertEqual(resultado["rq03_total_releases"], 7)

    def test_campos_ausentes_recebem_zero(self):
        resultado = rq07_por_linguagem.extrair_metricas_base({})

        self.assertEqual(resultado["rq02_pull_requests_aceitos"], 0)
        self.assertEqual(resultado["rq03_total_releases"], 0)

    def test_agrupa_metricas_por_linguagem(self):
        registros = [
            {
                "rq05_categoria_linguagem": "Python",
                "rq02_pull_requests_aceitos": 10,
                "rq03_total_releases": 2,
                "rq04_dias_desde_ultima_atualizacao": 4.0,
            },
            {
                "rq05_categoria_linguagem": "Python",
                "rq02_pull_requests_aceitos": 30,
                "rq03_total_releases": 6,
                "rq04_dias_desde_ultima_atualizacao": 8.0,
            },
            {
                "rq05_categoria_linguagem": "Go",
                "rq02_pull_requests_aceitos": 5,
                "rq03_total_releases": 1,
                "rq04_dias_desde_ultima_atualizacao": 3.0,
            },
        ]

        resumo = rq07_por_linguagem.resumir(registros)

        self.assertEqual(list(resumo), ["Python", "Go"])
        self.assertEqual(resumo["Python"]["quantidade_repositorios"], 2)
        self.assertEqual(resumo["Python"]["rq02_pull_requests_aceitos"]["media"], 20.0)
        self.assertEqual(resumo["Python"]["rq03_total_releases"]["mediana"], 4.0)
        self.assertEqual(resumo["Python"]["rq04_dias_desde_ultima_atualizacao"]["maximo"], 8.0)

    def test_mantem_sem_linguagem_e_ignora_rq04_ausente(self):
        registros = [{
            "rq05_linguagem_primaria": None,
            "rq02_pull_requests_aceitos": 0,
            "rq03_total_releases": 0,
            "rq04_dias_desde_ultima_atualizacao": None,
        }]

        resumo = rq07_por_linguagem.resumir(registros)
        grupo = resumo[rq07_por_linguagem.SEM_LINGUAGEM]

        self.assertEqual(grupo["quantidade_repositorios"], 1)
        self.assertIsNone(grupo["rq04_dias_desde_ultima_atualizacao"]["media"])


if __name__ == "__main__":
    unittest.main()
