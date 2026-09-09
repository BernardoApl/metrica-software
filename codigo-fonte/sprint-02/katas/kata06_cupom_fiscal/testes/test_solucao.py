import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from solucao import validar_cupom


class TestCupomFiscal(unittest.TestCase):
    def test_codigo_valido(self):
        self.assertTrue(validar_cupom("123456780"))

    def test_verificador_incorreto(self):
        self.assertFalse(validar_cupom("123456781"))

    def test_tamanho_incorreto(self):
        self.assertFalse(validar_cupom("12345678"))

    def test_contem_letra(self):
        self.assertFalse(validar_cupom("12345678A"))

    def test_base_zero_valida(self):
        self.assertTrue(validar_cupom("000000000"))

    def test_base_repetida_valida(self):
        self.assertTrue(validar_cupom("111111114"))

    def test_base_repetida_invalida(self):
        self.assertFalse(validar_cupom("111111115"))


if __name__ == "__main__":
    unittest.main()
