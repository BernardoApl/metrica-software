"""Testes offline da RQ58 sem depender de pandas/matplotlib/seaborn."""

import csv
import tempfile
import unittest
from pathlib import Path

import rq58_dashboard as rq58


def linha_unificado(**alteracoes):
    registro = {
        "trial_id": "t1",
        "participante": "bblop",
        "kata": "kata01",
        "tratamento": "com_ia",
        "issue": "32",
        "issue_informada": "True",
        "duracao_efetiva_segundos": "10",
        "sucesso_binario": "1.0",
        "complexidade_por_loc": "0.3",
        "metricas_rq30_disponiveis": "True",
        "duplicacao_percentual_disponivel": "False",
    }
    registro.update(alteracoes)
    return registro


def linha_resumo(**alteracoes):
    registro = {
        "participante": "bblop",
        "tratamento": "com_ia",
        "n_trials": "1",
        "n_issues_informadas": "1",
        "n_metricas_estaticas": "1",
        "mediana_tempo_segundos": "10",
        "taxa_sucesso": "1.0",
        "mediana_complexidade_por_loc": "0.3",
        "mediana_duplicacao_percentual": "",
        "mediana_indice_manutenibilidade": "50",
    }
    registro.update(alteracoes)
    return registro


class TestRQ58Resumo(unittest.TestCase):
    def test_resumo_usa_dataset_unificado_da_rq57(self):
        unificado = [
            linha_unificado(trial_id="t1", tratamento="com_ia", duracao_efetiva_segundos="10"),
            linha_unificado(
                trial_id="t2", tratamento="com_ia", duracao_efetiva_segundos="30",
                issue_informada="False", metricas_rq30_disponiveis="False",
                complexidade_por_loc="",
            ),
            linha_unificado(
                trial_id="t3", tratamento="sem_ia", duracao_efetiva_segundos="20",
                issue_informada="True", metricas_rq30_disponiveis="False",
                complexidade_por_loc="",
            ),
        ]
        resumo_tratamento = [
            linha_resumo(tratamento="com_ia", n_trials="2"),
            linha_resumo(tratamento="sem_ia", n_trials="1", n_metricas_estaticas="0"),
        ]

        linhas = rq58.resumir(unificado, resumo_tratamento)
        por_chave = {(l["tratamento"], l["metrica"]): l for l in linhas}

        self.assertEqual(por_chave[("com_ia", "trials_unicos")]["valor"], 2)
        self.assertEqual(por_chave[("com_ia", "issues_informadas")]["valor"], 1)
        self.assertEqual(por_chave[("com_ia", "metricas_rq30_disponiveis")]["valor"], 1)
        self.assertEqual(por_chave[("com_ia", "duracao_mediana_segundos")]["valor"], 20.0)
        self.assertEqual(por_chave[("com_ia", "taxa_sucesso")]["valor"], 1.0)
        self.assertEqual(por_chave[("sem_ia", "complexidade_por_loc_mediana")]["valor"], "")

    def test_salvar_resumo_grava_csv(self):
        linhas = [{
            "categoria": "cobertura", "tratamento": "sem_ia",
            "metrica": "trials_unicos", "valor": 1, "observacao": "ok",
        }]
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "resumo.csv"
            rq58.salvar_resumo(linhas, caminho)
            with caminho.open(encoding="utf-8", newline="") as arquivo:
                registros = list(csv.DictReader(arquivo))
        self.assertEqual(registros[0]["metrica"], "trials_unicos")


if __name__ == "__main__":
    unittest.main()
