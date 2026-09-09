import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from solucao import converter


class TestConversorEstoque(unittest.TestCase):
    def setUp(self):
        self.tabela = {("caixa", "pacote"): 10, ("pacote", "unidade"): 12}

    def test_mesma_unidade(self):
        self.assertEqual(converter(3, "caixa", "caixa", self.tabela), 3)

    def test_conversao_direta(self):
        self.assertEqual(converter(1, "caixa", "pacote", self.tabela), 10)

    def test_conversao_indireta(self):
        self.assertEqual(converter(2, "caixa", "unidade", self.tabela), 240)

    def test_conversao_a_partir_intermediaria(self):
        self.assertEqual(converter(5, "pacote", "unidade", self.tabela), 60)

    def test_sem_caminho_inverso(self):
        with self.assertRaises(ValueError):
            converter(1, "unidade", "caixa", self.tabela)

    def test_sem_caminho_unidades_desconhecidas(self):
        with self.assertRaises(ValueError):
            converter(1, "caixa", "tonelada", self.tabela)


if __name__ == "__main__":
    unittest.main()
