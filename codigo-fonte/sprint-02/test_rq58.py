"""Testes offline da RQ58 sem depender de pandas/matplotlib/seaborn."""

import csv
import tempfile
import unittest
from pathlib import Path

import rq58_dashboard as rq58


class TestRQ58Resumo(unittest.TestCase):
    def test_resumo_calcula_trials_sucesso_e_mediana(self):
        tempos = [
            {"tratamento": "com_ia", "duracao_segundos": "10", "sucesso": "True"},
            {"tratamento": "com_ia", "duracao_segundos": "30", "sucesso": "False"},
            {"tratamento": "sem_ia", "duracao_segundos": "20", "sucesso": "True"},
        ]
        metricas = [
            {"tratamento": "com_ia", "complexidade_media": "2", "loc": "10", "duplicacao_percentual": ""},
            {"tratamento": "com_ia", "complexidade_media": "4", "loc": "20", "duplicacao_percentual": ""},
        ]

        linhas = rq58.resumir(tempos, metricas)
        por_chave = {(l["tratamento"], l["metrica"]): l for l in linhas}

        self.assertEqual(por_chave[("com_ia", "trials")]["valor"], 2)
        self.assertEqual(por_chave[("com_ia", "taxa_sucesso")]["valor"], 0.5)
        self.assertEqual(por_chave[("com_ia", "duracao_mediana_segundos")]["valor"], 20.0)
        self.assertEqual(por_chave[("com_ia", "complexidade_media_mediana")]["valor"], 3.0)
        self.assertEqual(por_chave[("sem_ia", "loc_mediana")]["valor"], "")

    def test_salvar_resumo_grava_csv(self):
        linhas = [{
            "categoria": "tempo", "tratamento": "sem_ia",
            "metrica": "trials", "valor": 1, "observacao": "ok",
        }]
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "resumo.csv"
            rq58.salvar_resumo(linhas, caminho)
            with caminho.open(encoding="utf-8", newline="") as arquivo:
                registros = list(csv.DictReader(arquivo))
        self.assertEqual(registros[0]["metrica"], "trials")


if __name__ == "__main__":
    unittest.main()
