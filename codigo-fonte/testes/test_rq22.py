"""Testes offline da RQ22."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap import configurar_caminhos  # noqa: E402

configurar_caminhos()

import rq22_visualizacao_idade_releases as rq22  # noqa: E402


class TestRQ22(unittest.TestCase):
    def _resultado_rq21(self):
        return {
            "resumo": {
                "repositorios_analisados": 3,
                "registros_descartados_ou_ausentes": 1,
                "correlacao": {"pearson": 0.5, "spearman": 0.5},
                "regressao_linear": {"inclinacao_por_ano": 5.0, "intercepto": 10.0},
                "outliers": {
                    "limites_idade_anos": {"inferior": -1.0, "superior": 20.0},
                    "limites_total_releases": {"inferior": -5.0, "superior": 60.0},
                },
            },
            "registros_analisados": [
                {"nome_repositorio": "a/a", "idade_anos": 1.0, "total_releases": 2},
                {"nome_repositorio": "b/b", "idade_anos": 5.0, "total_releases": 40},
                {"nome_repositorio": "c/c", "idade_anos": 10.0, "total_releases": 5000},
            ],
        }

    def test_gera_svg_com_titulo_e_eixos(self):
        svg = rq22.gerar_svg(self._resultado_rq21())

        self.assertIn("<svg", svg)
        self.assertIn("RQ22 - Idade do repositorio x quantidade de releases", svg)
        self.assertIn("Idade do repositorio (anos)", svg)
        self.assertIn("Total de releases (escala log)", svg)
        self.assertIn("<circle", svg)

    def test_identifica_outlier_por_limite_da_rq21(self):
        resultado = self._resultado_rq21()

        self.assertTrue(rq22.eh_outlier(resultado["registros_analisados"][2], resultado["resumo"]))
        self.assertFalse(rq22.eh_outlier(resultado["registros_analisados"][0], resultado["resumo"]))

    def test_salva_svg(self):
        caminho = Path(__file__).resolve().parents[2] / "dados" / "_tmp_rq22_teste.svg"
        try:
            rq22.salvar_svg(self._resultado_rq21(), caminho)

            self.assertTrue(caminho.exists())
            self.assertIn("<svg", caminho.read_text(encoding="utf-8"))
        finally:
            if caminho.exists():
                caminho.unlink()

    def test_sem_registros_validos_falha_com_mensagem_clara(self):
        with self.assertRaises(ValueError):
            rq22.gerar_svg({"resumo": {}, "registros_analisados": []})

    def test_ticks_y_inclui_o_maximo_quando_nao_bate_com_candidato(self):
        ticks = rq22._ticks_y(6888)

        self.assertEqual(ticks[-1], 6888)
        self.assertIn(0, ticks)
        self.assertIn(1000, ticks)


if __name__ == "__main__":
    unittest.main()
