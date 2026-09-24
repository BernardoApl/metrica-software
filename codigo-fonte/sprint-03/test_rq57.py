import csv
import tempfile
import unittest
from pathlib import Path

import rq57_pipeline_dashboard as rq57


def linha_rq28(**alteracoes):
    registro = {
        "trial_id": "t1", "participante": "a", "kata": "kata01", "tratamento": "com_ia", "issue": "34",
        "duracao_segundos": "100.0", "limite_segundos": "2100.0", "status": "sucesso",
        "sucesso": "True", "censurado": "False",
    }
    registro.update(alteracoes)
    return registro


def linha_rq30(**alteracoes):
    registro = {
        "trial_id": "t1", "loc": "20", "sloc": "15", "lloc": "10", "funcoes_analisadas": "2",
        "complexidade_media": "3.0", "complexidade_maxima": "4", "indice_manutenibilidade": "70.0",
        "duplicacao_disponivel": "True", "duplicacao_percentual": "5.0",
    }
    registro.update(alteracoes)
    return registro


def escrever_csv(caminho: Path, linhas: list[dict]):
    with caminho.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(linhas[0].keys()))
        escritor.writeheader()
        escritor.writerows(linhas)


class TestCarregarRq28(unittest.TestCase):
    def test_arquivo_inexistente_retorna_dataframe_vazio(self):
        df = rq57.carregar_rq28(Path("nao_existe.csv"))
        self.assertTrue(df.empty)

    def test_sucesso_usa_duracao_real(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "rq28.csv"
            escrever_csv(caminho, [linha_rq28()])
            df = rq57.carregar_rq28(caminho)
        self.assertEqual(df.loc[0, "duracao_efetiva_segundos"], 100.0)
        self.assertEqual(df.loc[0, "sucesso_binario"], 1.0)

    def test_censurado_usa_limite_e_interrompido_fica_nan(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "rq28.csv"
            escrever_csv(caminho, [
                linha_rq28(trial_id="t2", sucesso="False", censurado="True", status="limite_atingido",
                           duracao_segundos="2100.0"),
                linha_rq28(trial_id="t3", sucesso="False", censurado="False", status="interrompido"),
            ])
            df = rq57.carregar_rq28(caminho)
        self.assertEqual(df.loc[0, "duracao_efetiva_segundos"], 2100.0)
        self.assertTrue(df.loc[1, "duracao_efetiva_segundos"] != df.loc[1, "duracao_efetiva_segundos"])  # NaN
        self.assertTrue(df.loc[1, "sucesso_binario"] != df.loc[1, "sucesso_binario"])  # NaN


class TestCarregarRq30(unittest.TestCase):
    def test_calcula_complexidade_por_loc(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "rq30.csv"
            escrever_csv(caminho, [linha_rq30()])
            df = rq57.carregar_rq30(caminho)
        self.assertAlmostEqual(df.loc[0, "complexidade_por_loc"], (3.0 * 2) / 20)


class TestExecutar(unittest.TestCase):
    def test_dataset_unificado_junta_rq28_e_rq30_por_trial_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho_rq28 = Path(tmp) / "rq28.csv"
            caminho_rq30 = Path(tmp) / "rq30.csv"
            escrever_csv(caminho_rq28, [linha_rq28()])
            escrever_csv(caminho_rq30, [linha_rq30()])
            unificado, resumo = rq57.executar(caminho_rq28, caminho_rq30)

        self.assertEqual(len(unificado), 1)
        self.assertEqual(unificado.loc[0, "loc"], 20)
        self.assertEqual(len(resumo), 1)
        self.assertEqual(resumo.loc[0, "participante"], "a")
        self.assertEqual(resumo.loc[0, "mediana_tempo_segundos"], 100.0)
        self.assertEqual(resumo.loc[0, "taxa_sucesso"], 1.0)

    def test_sem_arquivos_nao_quebra(self):
        with tempfile.TemporaryDirectory() as tmp:
            unificado, resumo = rq57.executar(Path(tmp) / "a.csv", Path(tmp) / "b.csv")
        self.assertTrue(unificado.empty)
        self.assertTrue(resumo.empty)


if __name__ == "__main__":
    unittest.main()
