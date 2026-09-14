"""Testes offline da RQ30. A duplicacao (jscpd) e sempre mockada, sem depender de Node.js."""

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import rq30_metricas_estaticas as rq30


CODIGO_COM_RAMIFICACOES = """
def classificar(valor):
    if valor < 0:
        return "negativo"
    elif valor == 0:
        return "zero"
    else:
        return "positivo"
"""


class TestAnalisarComplexidadeELoc(unittest.TestCase):
    def test_conta_funcoes_e_complexidade_media(self):
        resultado = rq30.analisar_complexidade_e_loc(CODIGO_COM_RAMIFICACOES)
        self.assertEqual(resultado["funcoes_analisadas"], 1)
        self.assertGreaterEqual(resultado["complexidade_media"], 3)
        self.assertEqual(resultado["complexidade_media"], resultado["complexidade_maxima"])
        self.assertGreater(resultado["loc"], 0)
        self.assertTrue(0 <= resultado["indice_manutenibilidade"] <= 100)

    def test_arquivo_sem_funcao_tem_complexidade_zero(self):
        resultado = rq30.analisar_complexidade_e_loc("x = 1\n")
        self.assertEqual(resultado["funcoes_analisadas"], 0)
        self.assertEqual(resultado["complexidade_media"], 0.0)
        self.assertEqual(resultado["complexidade_maxima"], 0)

    def test_codigo_invalido_marca_metricas_indisponiveis(self):
        resultado = rq30.analisar_complexidade_e_loc("def f(:\n    pass")
        self.assertEqual(resultado, rq30.METRICAS_INDISPONIVEIS)


class TestAnalisarDuplicacao(unittest.TestCase):
    def test_sem_npx_marca_indisponivel(self):
        with patch.object(rq30.shutil, "which", return_value=None):
            resultado = rq30.analisar_duplicacao(Path("arquivo.py"), 3, 20)
        self.assertEqual(resultado, rq30.DUPLICACAO_INDISPONIVEL)

    def test_falha_ao_executar_jscpd_marca_indisponivel(self):
        with patch.object(rq30.shutil, "which", return_value="npx-fake"), \
             patch.object(rq30.subprocess, "run", side_effect=OSError("sem node")):
            resultado = rq30.analisar_duplicacao(Path("arquivo.py"), 3, 20)
        self.assertEqual(resultado, rq30.DUPLICACAO_INDISPONIVEL)

    def test_le_percentual_do_relatorio_jscpd(self):
        relatorio_falso = {"statistics": {"total": {"percentage": 12.5, "duplicatedLines": 3, "lines": 24}}}

        def executar_falso(comando, **kwargs):
            destino = Path(comando[comando.index("--output") + 1]) / "jscpd-report.json"
            destino.write_text(json.dumps(relatorio_falso), encoding="utf-8")
            return Mock(returncode=0)

        with patch.object(rq30.shutil, "which", return_value="npx-fake"), \
             patch.object(rq30.subprocess, "run", side_effect=executar_falso):
            resultado = rq30.analisar_duplicacao(Path("arquivo.py"), 3, 20)

        self.assertTrue(resultado["duplicacao_disponivel"])
        self.assertEqual(resultado["duplicacao_percentual"], 12.5)
        self.assertEqual(resultado["linhas_duplicadas"], 3)
        self.assertEqual(resultado["linhas_analisadas_duplicacao"], 24)


class TestMedir(unittest.TestCase):
    def test_medir_sem_duplicacao_nao_chama_jscpd(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "solucao.py"
            caminho.write_text(CODIGO_COM_RAMIFICACOES, encoding="utf-8")
            with patch.object(rq30, "analisar_duplicacao") as duplicacao_mock:
                resultado = rq30.medir(caminho, sem_duplicacao=True)
        duplicacao_mock.assert_not_called()
        self.assertFalse(resultado["duplicacao_disponivel"])
        self.assertEqual(resultado["funcoes_analisadas"], 1)


class TestRegistrarCsv(unittest.TestCase):
    def test_csv_preserva_medicoes_e_um_unico_cabecalho(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "metricas.csv"
            for kata in ("kata01", "kata02"):
                registro = dict.fromkeys(rq30.COLUNAS, "")
                registro.update(participante="integrante1", kata=kata)
                rq30.registrar_csv(caminho, registro)
            with caminho.open(encoding="utf-8", newline="") as arquivo:
                linhas = list(csv.DictReader(arquivo))
            self.assertEqual([linha["kata"] for linha in linhas], ["kata01", "kata02"])

    def test_csv_incompativel_nao_e_modificado(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "metricas.csv"
            caminho.write_text("outras,colunas\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                rq30.registrar_csv(caminho, {})
            self.assertEqual(caminho.read_text(encoding="utf-8"), "outras,colunas\n")


if __name__ == "__main__":
    unittest.main()
