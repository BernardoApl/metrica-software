import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from solucao import deduplicar_contatos


class TestDeduplicadorContatos(unittest.TestCase):
    def test_lista_vazia(self):
        self.assertEqual(deduplicar_contatos([]), [])

    def test_sem_duplicados(self):
        contatos = [
            {"nome": "Ana", "telefone": "11911111111", "email": "a@x.com"},
            {"nome": "Bruno", "telefone": "11922222222", "email": "b@x.com"},
        ]
        self.assertEqual(deduplicar_contatos(contatos), contatos)

    def test_duplicado_formatos_diferentes(self):
        contatos = [
            {"nome": "Ana", "telefone": "(11) 91111-1111", "email": "a@x.com"},
            {"nome": "Ana Paula Silva", "telefone": "+55 11 91111-1111", "email": "a2@x.com"},
        ]
        resultado = deduplicar_contatos(contatos)
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["nome"], "Ana Paula Silva")

    def test_empate_mantem_primeiro(self):
        contatos = [
            {"nome": "Ana", "telefone": "11911111111", "email": "a@x.com"},
            {"nome": "Bob", "telefone": "11911111111", "email": "b@x.com"},
        ]
        resultado = deduplicar_contatos(contatos)
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["nome"], "Ana")

    def test_preserva_ordem_primeira_ocorrencia(self):
        contatos = [
            {"nome": "Carlos", "telefone": "11933333333", "email": "c@x.com"},
            {"nome": "Ana", "telefone": "11911111111", "email": "a@x.com"},
            {"nome": "Carlos Eduardo", "telefone": "11933333333", "email": "c2@x.com"},
        ]
        resultado = deduplicar_contatos(contatos)
        self.assertEqual([c["telefone"] for c in resultado], ["11933333333", "11911111111"])
        self.assertEqual(resultado[0]["nome"], "Carlos Eduardo")


if __name__ == "__main__":
    unittest.main()
