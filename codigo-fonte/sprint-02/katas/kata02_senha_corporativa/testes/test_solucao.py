import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from solucao import validar_senha


class TestSenhaCorporativa(unittest.TestCase):
    def test_senha_valida(self):
        self.assertTrue(validar_senha("Abcde123!", "joao"))

    def test_muito_curta(self):
        self.assertFalse(validar_senha("Ab1!", "joao"))

    def test_sem_minuscula(self):
        self.assertFalse(validar_senha("ABCDEFG1!", "joao"))

    def test_sem_caractere_especial(self):
        self.assertFalse(validar_senha("Abcdefgh1", "joao"))

    def test_tres_caracteres_repetidos(self):
        self.assertFalse(validar_senha("Aaa11111!", "joao"))

    def test_contem_nome_usuario(self):
        self.assertFalse(validar_senha("Joao1234!", "joao"))

    def test_outra_senha_valida(self):
        self.assertTrue(validar_senha("Passw0rd!", "joao"))


if __name__ == "__main__":
    unittest.main()
