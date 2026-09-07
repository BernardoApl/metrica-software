"""Testes offline da RQ28, sem coleta de dados reais do experimento."""

import argparse
import csv
import queue
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import rq28_cronometragem as rq28


class TestRQ28(unittest.TestCase):
    def medir(self, acoes, limite=2100):
        fila = queue.Queue()
        for acao in acoes:
            fila.put(acao)
        return rq28.medir(["executor", "testes"], Path.cwd(), limite, fila)

    def test_limite_nao_pode_exceder_35(self):
        self.assertEqual(rq28.limite_valido("35"), 35)
        self.assertEqual(rq28.limite_valido("20"), 20)
        for valor in ("0", "-1", "36", "nan", "inf"):
            with self.subTest(valor=valor):
                with self.assertRaises(argparse.ArgumentTypeError):
                    rq28.limite_valido(valor)

    def test_sucesso_exige_codigo_zero_antes_do_prazo(self):
        processo = Mock()
        processo.poll.return_value = 0
        with patch.object(rq28.subprocess, "Popen", return_value=processo):
            resultado = self.medir(["testar"])
        self.assertTrue(resultado["sucesso"])
        self.assertFalse(resultado["censurado"])
        self.assertEqual(resultado["verificacoes"], 1)
        self.assertLess(resultado["duracao_segundos"], 2100)

    def test_falha_nao_encerra_cronometro(self):
        processo = Mock()
        processo.poll.return_value = 1
        with patch.object(rq28.subprocess, "Popen", return_value=processo):
            resultado = self.medir(["testar", "sair"])
        self.assertEqual(resultado["ultimo_codigo_testes"], 1)
        self.assertEqual(resultado["status"], "interrompido")
        self.assertFalse(resultado["sucesso"])

    def test_limite_censura_exatamente_em_35_minutos(self):
        with patch.object(rq28.time, "monotonic", side_effect=[100, 2201]):
            resultado = self.medir([])
        self.assertEqual(resultado["duracao_segundos"], 2100)
        self.assertTrue(resultado["censurado"])
        self.assertFalse(resultado["sucesso"])

    def test_teste_ativo_e_encerrado_no_prazo(self):
        processo = Mock()
        processo.poll.return_value = None
        with patch.object(rq28.time, "monotonic", side_effect=[0, 0, 0, 0, 2100]), \
             patch.object(rq28.subprocess, "Popen", return_value=processo), \
             patch.object(rq28, "encerrar_testes") as encerrar:
            resultado = self.medir(["testar"])
        encerrar.assert_called_once_with(processo)
        self.assertTrue(resultado["censurado"])

    def test_interrupcao_nao_e_sucesso_nem_censura(self):
        resultado = self.medir(["sair"])
        self.assertEqual(resultado["status"], "interrompido")
        self.assertFalse(resultado["censurado"])
        self.assertFalse(resultado["sucesso"])

    def test_comando_invalido_registra_erro(self):
        with patch.object(rq28.subprocess, "Popen", side_effect=FileNotFoundError("executor")):
            resultado = self.medir(["testar"])
        self.assertEqual(resultado["status"], "erro_execucao")
        self.assertFalse(resultado["sucesso"])

    def test_csv_preserva_tentativas_e_um_unico_cabecalho(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "tempos.csv"
            for identificador in ("a", "b"):
                registro = dict.fromkeys(rq28.COLUNAS, "")
                registro.update(trial_id=identificador, participante="José", kata="kata,1")
                rq28.registrar_csv(caminho, registro)
            with caminho.open(encoding="utf-8", newline="") as arquivo:
                linhas = list(csv.DictReader(arquivo))
            self.assertEqual([r["trial_id"] for r in linhas], ["a", "b"])
            self.assertEqual(linhas[0]["participante"], "José")
            self.assertEqual(linhas[0]["kata"], "kata,1")

    def test_csv_incompativel_nao_e_modificado(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "tempos.csv"
            caminho.write_text("outras,colunas\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                rq28.registrar_csv(caminho, {})
            self.assertEqual(caminho.read_text(encoding="utf-8"), "outras,colunas\n")


if __name__ == "__main__":
    unittest.main()
