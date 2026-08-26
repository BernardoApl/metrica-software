"""Testes offline da RQ21."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap import configurar_caminhos  # noqa: E402

configurar_caminhos()

import rq21_idade_releases as rq21  # noqa: E402


class TestRQ21(unittest.TestCase):
    def test_monta_registro_valido(self):
        registro = {
            "nome_completo": "org/projeto",
            "rq01_idade_anos": 4.5,
            "rq03_total_releases": 12,
        }

        linha = rq21.montar_registro(registro)

        self.assertTrue(linha["analisado"])
        self.assertEqual(linha["status_rq21"], rq21.STATUS_OK)
        self.assertEqual(linha["idade_anos"], 4.5)
        self.assertEqual(linha["total_releases"], 12)

    def test_repositorio_sem_releases_e_descartado(self):
        linha = rq21.montar_registro({
            "nome_completo": "org/sem-releases",
            "rq01_idade_anos": 3.0,
            "rq03_total_releases": None,
        })

        self.assertFalse(linha["analisado"])
        self.assertEqual(linha["status_rq21"], rq21.STATUS_RELEASES_AUSENTE)
        self.assertIsNone(linha["total_releases"])

    def test_repositorio_sem_idade_e_descartado(self):
        linha = rq21.montar_registro({
            "nome_completo": "org/sem-idade",
            "rq01_idade_anos": None,
            "rq03_total_releases": 5,
        })

        self.assertFalse(linha["analisado"])
        self.assertEqual(linha["status_rq21"], rq21.STATUS_IDADE_AUSENTE)

    def test_repositorio_com_zero_releases_e_valido(self):
        linha = rq21.montar_registro({
            "nome_completo": "org/zero",
            "rq01_idade_anos": 1.0,
            "rq03_total_releases": 0,
        })

        self.assertTrue(linha["analisado"])
        self.assertEqual(linha["total_releases"], 0)

    def test_correlacoes_perfeitas(self):
        xs = [1.0, 2.0, 3.0, 4.0]
        ys = [10.0, 20.0, 30.0, 40.0]

        self.assertEqual(rq21.calcular_correlacao_pearson(xs, ys), 1.0)
        self.assertEqual(rq21.calcular_correlacao_spearman(xs, ys), 1.0)

    def test_agrupa_por_faixa_de_idade(self):
        validos = [
            {"idade_anos": 1.0, "total_releases": 2},
            {"idade_anos": 1.5, "total_releases": 4},
            {"idade_anos": 3.0, "total_releases": 6},
            {"idade_anos": 7.0, "total_releases": 8},
            {"idade_anos": 15.0, "total_releases": 10},
        ]

        grupos = rq21.agrupar_por_faixa_de_idade(validos)

        self.assertEqual(list(grupos), ["Ate 2 anos", "2 a 5 anos", "5 a 10 anos", "Mais de 10 anos"])
        self.assertEqual(grupos["Ate 2 anos"]["quantidade_repositorios"], 2)
        self.assertEqual(grupos["Ate 2 anos"]["media_releases"], 3.0)
        self.assertEqual(grupos["5 a 10 anos"]["mediana_releases"], 8.0)

    def test_analisar_conta_descartados_e_classifica(self):
        resultado = rq21.analisar([
            {"nome_completo": "a/a", "rq01_idade_anos": 1.0, "rq03_total_releases": 2},
            {"nome_completo": "b/b", "rq01_idade_anos": 2.0, "rq03_total_releases": 4},
            {"nome_completo": "c/c", "rq01_idade_anos": 3.0, "rq03_total_releases": 6},
            {"nome_completo": "d/d", "rq01_idade_anos": 4.0, "rq03_total_releases": None},
        ])

        resumo = resultado["resumo"]
        self.assertEqual(resumo["total_repositorios"], 4)
        self.assertEqual(resumo["repositorios_analisados"], 3)
        self.assertEqual(resumo["registros_descartados_ou_ausentes"], 1)
        self.assertEqual(resumo["por_status"][rq21.STATUS_RELEASES_AUSENTE], 1)
        self.assertEqual(resumo["correlacao"]["spearman"], 1.0)
        self.assertEqual(resumo["hipotese"], "confirmada")


if __name__ == "__main__":
    unittest.main()
