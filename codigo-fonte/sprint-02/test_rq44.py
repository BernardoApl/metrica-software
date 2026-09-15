"""Testes offline da RQ44 (sem depender de matplotlib nem de dados reais da RQ30)."""

import csv
import tempfile
import unittest
from pathlib import Path

import rq44_comparar_metricas as rq44


def _registro(kata, tratamento, complexidade_media, loc, duplicacao_percentual):
    return {
        "kata": kata, "tratamento": tratamento,
        "complexidade_media": str(complexidade_media), "loc": str(loc),
        "duplicacao_percentual": str(duplicacao_percentual),
    }


class TestMedianaEIqr(unittest.TestCase):
    def test_lista_vazia(self):
        self.assertEqual(rq44._mediana_e_iqr([]), (None, None, 0))

    def test_um_valor_sem_iqr(self):
        mediana, iqr, n = rq44._mediana_e_iqr([5.0])
        self.assertEqual(mediana, 5.0)
        self.assertIsNone(iqr)
        self.assertEqual(n, 1)

    def test_iqr_com_multiplos_valores(self):
        mediana, iqr, n = rq44._mediana_e_iqr([1.0, 2.0, 3.0, 4.0])
        self.assertEqual(mediana, 2.5)
        self.assertEqual(iqr, 2.0)
        self.assertEqual(n, 4)


class TestCompararPorTratamento(unittest.TestCase):
    def test_agrupa_por_kata_e_tratamento(self):
        registros = [
            _registro("kata01_frete_progressivo", "com_ia", 2.0, 10, 0.0),
            _registro("kata01_frete_progressivo", "com_ia", 4.0, 20, 0.0),
            _registro("kata01_frete_progressivo", "sem_ia", 3.0, 15, 5.0),
        ]
        linhas = rq44.comparar_por_tratamento(registros)
        self.assertEqual(len(linhas), 2)

        com_ia = next(l for l in linhas if l["tratamento"] == "com_ia")
        self.assertEqual(com_ia["n_trials"], 2)
        self.assertEqual(com_ia["complexidade_media_mediana"], 3.0)
        self.assertEqual(com_ia["loc_mediana"], 15.0)

        sem_ia = next(l for l in linhas if l["tratamento"] == "sem_ia")
        self.assertEqual(sem_ia["n_trials"], 1)
        self.assertEqual(sem_ia["complexidade_media_mediana"], 3.0)

    def test_ignora_valores_ausentes_ou_invalidos(self):
        registros = [
            _registro("kata02_senha_corporativa", "com_ia", 1.0, 5, ""),
            {"kata": "kata02_senha_corporativa", "tratamento": "com_ia",
             "complexidade_media": "", "loc": "5", "duplicacao_percentual": "0.0"},
        ]
        linhas = rq44.comparar_por_tratamento(registros)
        self.assertEqual(len(linhas), 1)
        self.assertEqual(linhas[0]["complexidade_media_n"], 1)
        self.assertEqual(linhas[0]["duplicacao_percentual_n"], 1)
        self.assertEqual(linhas[0]["loc_n"], 2)


class TestSalvarCsv(unittest.TestCase):
    def test_grava_cabecalho_e_linhas(self):
        linhas = rq44.comparar_por_tratamento([
            _registro("kata01_frete_progressivo", "com_ia", 2.0, 10, 0.0),
        ])
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "comparacao.csv"
            rq44.salvar_csv(linhas, caminho)
            with caminho.open(encoding="utf-8", newline="") as arquivo:
                gravado = list(csv.DictReader(arquivo))
        self.assertEqual(len(gravado), 1)
        self.assertEqual(gravado[0]["kata"], "kata01_frete_progressivo")

    def test_lista_vazia_nao_cria_arquivo(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "comparacao.csv"
            rq44.salvar_csv([], caminho)
            self.assertFalse(caminho.exists())


if __name__ == "__main__":
    unittest.main()
