import csv
import tempfile
import unittest
from pathlib import Path

import rq53_wilcoxon_metricas_estaticas as rq53


def linha(**alteracoes):
    registro = {
        "participante": "a", "kata": "kata01", "tratamento": "com_ia",
        "loc": "20", "funcoes_analisadas": "2", "complexidade_media": "3.0",
        "duplicacao_disponivel": "True", "duplicacao_percentual": "5.0",
    }
    registro.update(alteracoes)
    return registro


class TestComplexidadePorLoc(unittest.TestCase):
    def test_calcula_complexidade_total_normalizada(self):
        self.assertAlmostEqual(rq53.complexidade_por_loc(linha()), (3.0 * 2) / 20)

    def test_loc_zero_retorna_none(self):
        self.assertIsNone(rq53.complexidade_por_loc(linha(loc="0")))


class TestDuplicacaoPercentual(unittest.TestCase):
    def test_indisponivel_retorna_none(self):
        self.assertIsNone(rq53.duplicacao_percentual(linha(duplicacao_disponivel="False", duplicacao_percentual="")))

    def test_disponivel_retorna_valor(self):
        self.assertEqual(rq53.duplicacao_percentual(linha()), 5.0)


class TestAnalisar(unittest.TestCase):
    def test_sem_trials_e_insuficiente_nas_duas_metricas(self):
        with tempfile.TemporaryDirectory() as tmp:
            relatorio = rq53.analisar(Path(tmp) / "vazio.csv")
        for resultado in relatorio["metricas"].values():
            self.assertFalse(resultado["wilcoxon"]["suficiente"])

    def test_participantes_completos_geram_pares(self):
        linhas = []
        for participante in ("a", "b", "c"):
            linhas.append(linha(participante=participante, tratamento="com_ia",
                                 complexidade_media="4.0", duplicacao_percentual="10.0"))
            linhas.append(linha(participante=participante, tratamento="sem_ia",
                                 complexidade_media="2.0", duplicacao_percentual="2.0"))

        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "rq30.csv"
            with caminho.open("w", newline="", encoding="utf-8") as arquivo:
                escritor = csv.DictWriter(arquivo, fieldnames=list(linhas[0].keys()))
                escritor.writeheader()
                escritor.writerows(linhas)
            relatorio = rq53.analisar(caminho)

        for resultado in relatorio["metricas"].values():
            self.assertEqual(len(resultado["pares_utilizados"]), 3)
            self.assertTrue(resultado["wilcoxon"]["suficiente"])


if __name__ == "__main__":
    unittest.main()
