"""Testes offline da RQ31. O piloto roda com --sem-duplicacao, sem depender de Node.js."""

import csv
import tempfile
import unittest
from pathlib import Path

import rq30_metricas_estaticas as rq30
import rq31_validar_metricas as rq31


def registro_valido(**alteracoes):
    registro = {
        "participante": "integrante1",
        "kata": "kata01",
        "tratamento": "com_ia",
        "issue": "30",
        "trial_id": "",
        "arquivo": "caminho/solucao.py",
        "medido_em_utc": "2026-09-10T12:00:00+00:00",
        "loc": "5",
        "sloc": "3",
        "lloc": "2",
        "comentarios": "0",
        "linhas_em_branco": "1",
        "funcoes_analisadas": "1",
        "complexidade_media": "1.0",
        "complexidade_maxima": "1",
        "indice_manutenibilidade": "100.0",
        "duplicacao_disponivel": "True",
        "duplicacao_percentual": "0.0",
        "linhas_duplicadas": "0",
        "linhas_analisadas_duplicacao": "5",
    }
    registro.update(alteracoes)
    return registro


class TestValidarRegistro(unittest.TestCase):
    def test_registro_valido_nao_gera_erros(self):
        self.assertEqual(rq31.validar_registro(registro_valido(), 2), [])

    def test_tratamento_invalido(self):
        erros = rq31.validar_registro(registro_valido(tratamento="com_ajuda"), 2)
        self.assertIn("linha 2: tratamento invalido: com_ajuda", erros)

    def test_complexidade_incoerente_com_funcoes(self):
        erros = rq31.validar_registro(
            registro_valido(funcoes_analisadas="1", complexidade_media="0"), 2,
        )
        self.assertIn("linha 2: complexidade_media invalida para arquivo com funcoes", erros)

    def test_duplicacao_percentual_exige_disponibilidade(self):
        erros = rq31.validar_registro(
            registro_valido(duplicacao_disponivel="False", duplicacao_percentual="10"), 2,
        )
        self.assertIn("linha 2: duplicacao_percentual deveria estar vazia quando indisponivel", erros)

    def test_duplicacao_disponivel_exige_percentual_valido(self):
        erros = rq31.validar_registro(
            registro_valido(duplicacao_disponivel="True", duplicacao_percentual=""), 2,
        )
        self.assertIn("linha 2: duplicacao_percentual invalida", erros)

    def test_arquivo_deve_ser_py(self):
        erros = rq31.validar_registro(registro_valido(arquivo="solucao.txt"), 2)
        self.assertIn("linha 2: arquivo analisado nao e .py: solucao.txt", erros)


class TestValidarCsv(unittest.TestCase):
    def test_valida_csv_com_combinacao_duplicada(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "metricas.csv"
            with caminho.open("w", newline="", encoding="utf-8") as arquivo:
                escritor = csv.DictWriter(arquivo, fieldnames=rq30.COLUNAS)
                escritor.writeheader()
                escritor.writerow(registro_valido())
                escritor.writerow(registro_valido())

            relatorio = rq31.validar_csv(caminho)

        self.assertFalse(relatorio["valido"])
        self.assertEqual(relatorio["total_registros"], 2)
        self.assertTrue(any("combinacao participante/kata/tratamento duplicada" in erro
                             for erro in relatorio["erros"]))

    def test_arquivo_inexistente(self):
        relatorio = rq31.validar_csv(Path("nao_existe.csv"))
        self.assertFalse(relatorio["valido"])
        self.assertEqual(relatorio["total_registros"], 0)


class TestExecutarPiloto(unittest.TestCase):
    def test_piloto_roda_sobre_katas_reais_e_gera_csv_valido(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "piloto.csv"
            relatorio = rq31.executar_piloto(caminho, sem_duplicacao=True)

        katas = rq31.listar_katas()
        self.assertTrue(relatorio["valido"], relatorio["erros"])
        self.assertEqual(relatorio["total_registros"], len(katas))
        self.assertEqual(sum(relatorio["resumo_tratamento"].values()), len(katas))

    def test_piloto_sem_katas_gera_erro(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                rq31.executar_piloto(Path(tmp) / "piloto.csv", diretorio_katas=Path(tmp), sem_duplicacao=True)


if __name__ == "__main__":
    unittest.main()
