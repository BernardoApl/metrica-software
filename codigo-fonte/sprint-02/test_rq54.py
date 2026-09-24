"""Testes offline da RQ54 (sem depender de matplotlib nem de dados reais da RQ30)."""

import csv
import tempfile
import unittest
from pathlib import Path

import rq54_consolidar_metricas_tratamento as rq54


def _registro(kata, tratamento, complexidade_media, loc, duplicacao_percentual):
    return {
        "kata": kata, "tratamento": tratamento,
        "complexidade_media": str(complexidade_media), "loc": str(loc),
        "duplicacao_percentual": str(duplicacao_percentual),
    }


class TestConsolidarPorTratamento(unittest.TestCase):
    def test_agrupa_somente_por_tratamento(self):
        registros = [
            _registro("kata01_frete_progressivo", "com_ia", 2.0, 10, 0.0),
            _registro("kata02_senha_corporativa", "com_ia", 4.0, 20, 0.0),
            _registro("kata03_deduplicador_contatos", "sem_ia", 3.0, 15, 5.0),
        ]
        linhas = rq54.consolidar_por_tratamento(registros)
        self.assertEqual(len(linhas), 2)

        com_ia = next(l for l in linhas if l["tratamento"] == "com_ia")
        self.assertEqual(com_ia["n_trials"], 2)
        self.assertEqual(com_ia["n_katas"], 2)
        self.assertEqual(com_ia["complexidade_media_mediana"], 3.0)
        self.assertEqual(com_ia["loc_mediana"], 15.0)

        sem_ia = next(l for l in linhas if l["tratamento"] == "sem_ia")
        self.assertEqual(sem_ia["n_trials"], 1)
        self.assertEqual(sem_ia["n_katas"], 1)
        self.assertEqual(sem_ia["complexidade_media_mediana"], 3.0)

    def test_agrega_multiplos_katas_no_mesmo_tratamento(self):
        registros = [
            _registro("kata01_frete_progressivo", "sem_ia", 1.0, 10, 0.0),
            _registro("kata02_senha_corporativa", "sem_ia", 3.0, 30, 10.0),
        ]
        linhas = rq54.consolidar_por_tratamento(registros)
        self.assertEqual(len(linhas), 1)
        self.assertEqual(linhas[0]["n_trials"], 2)
        self.assertEqual(linhas[0]["n_katas"], 2)
        self.assertEqual(linhas[0]["complexidade_media_mediana"], 2.0)
        self.assertEqual(linhas[0]["loc_mediana"], 20.0)

    def test_ignora_valores_ausentes_ou_invalidos(self):
        registros = [
            _registro("kata02_senha_corporativa", "com_ia", 1.0, 5, ""),
            {"kata": "kata02_senha_corporativa", "tratamento": "com_ia",
             "complexidade_media": "", "loc": "5", "duplicacao_percentual": "0.0"},
        ]
        linhas = rq54.consolidar_por_tratamento(registros)
        self.assertEqual(len(linhas), 1)
        self.assertEqual(linhas[0]["complexidade_media_n"], 1)
        self.assertEqual(linhas[0]["duplicacao_percentual_n"], 1)
        self.assertEqual(linhas[0]["loc_n"], 2)


class TestSalvarCsv(unittest.TestCase):
    def test_grava_cabecalho_e_linhas(self):
        linhas = rq54.consolidar_por_tratamento([
            _registro("kata01_frete_progressivo", "com_ia", 2.0, 10, 0.0),
        ])
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "consolidacao.csv"
            rq54.salvar_csv(linhas, caminho)
            with caminho.open(encoding="utf-8", newline="") as arquivo:
                gravado = list(csv.DictReader(arquivo))
        self.assertEqual(len(gravado), 1)
        self.assertEqual(gravado[0]["tratamento"], "com_ia")

    def test_lista_vazia_nao_cria_arquivo(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "consolidacao.csv"
            rq54.salvar_csv([], caminho)
            self.assertFalse(caminho.exists())


if __name__ == "__main__":
    unittest.main()
