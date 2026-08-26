"""Testes offline da RQ18."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap import configurar_caminhos  # noqa: E402

configurar_caminhos()

import rq18_visualizacao_idade_issues as rq18  # noqa: E402


class TestRQ18(unittest.TestCase):
    def _resultado_rq17(self):
        return {
            "resumo": {
                "repositorios_analisados": 3,
                "registros_descartados_ou_ausentes": 1,
                "correlacao": {"pearson": 0.5, "spearman": 0.5},
                "regressao_linear": {"inclinacao_por_ano": 5.0, "intercepto": 10.0},
                "outliers": {
                    "limites_idade_anos": {"inferior": -1.0, "superior": 20.0},
                    "limites_percentual_issues_fechadas": {"inferior": 15.0, "superior": 100.0},
                },
            },
            "registros_analisados": [
                {
                    "nome_repositorio": "a/a",
                    "idade_anos": 1.0,
                    "percentual_issues_fechadas": 20.0,
                    "total_issues": 10,
                },
                {
                    "nome_repositorio": "b/b",
                    "idade_anos": 5.0,
                    "percentual_issues_fechadas": 80.0,
                    "total_issues": 20,
                },
                {
                    "nome_repositorio": "c/c",
                    "idade_anos": 10.0,
                    "percentual_issues_fechadas": 10.0,
                    "total_issues": 30,
                },
            ],
        }

    def test_gera_svg_com_titulo_e_eixos(self):
        svg = rq18.gerar_svg(self._resultado_rq17())

        self.assertIn("<svg", svg)
        self.assertIn("RQ18 - Idade do repositorio x percentual de issues fechadas", svg)
        self.assertIn("Idade do repositorio (anos)", svg)
        self.assertIn("Issues fechadas (%)", svg)
        self.assertIn("<circle", svg)

    def test_identifica_outlier_por_limite_da_rq17(self):
        resultado = self._resultado_rq17()

        self.assertTrue(rq18.eh_outlier(resultado["registros_analisados"][2], resultado["resumo"]))
        self.assertFalse(rq18.eh_outlier(resultado["registros_analisados"][0], resultado["resumo"]))

    def test_salva_svg(self):
        caminho = Path(__file__).resolve().parents[2] / "dados" / "_tmp_rq18_teste.svg"
        try:
            rq18.salvar_svg(self._resultado_rq17(), caminho)

            self.assertTrue(caminho.exists())
            self.assertIn("<svg", caminho.read_text(encoding="utf-8"))
        finally:
            if caminho.exists():
                caminho.unlink()

    def test_sem_registros_validos_falha_com_mensagem_clara(self):
        with self.assertRaises(ValueError):
            rq18.gerar_svg({"resumo": {}, "registros_analisados": []})


if __name__ == "__main__":
    unittest.main()
