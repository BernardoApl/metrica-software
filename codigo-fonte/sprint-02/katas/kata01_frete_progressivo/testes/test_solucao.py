import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from solucao import calcular_frete


class TestFreteProgressivo(unittest.TestCase):
    def test_frete_gratuito_acima_do_limite(self):
        self.assertEqual(calcular_frete(3, 30, 300), 0.0)

    def test_frete_minimo(self):
        self.assertEqual(calcular_frete(1, 10, 10), 5.0)

    def test_faixa_ate_5kg(self):
        self.assertEqual(calcular_frete(3, 30, 50), 6.0)

    def test_faixa_intermediaria(self):
        self.assertEqual(calcular_frete(10, 100, 50), 22.75)

    def test_faixa_acima_de_20kg(self):
        self.assertEqual(calcular_frete(25, 300, 50), 60.0)

    def test_peso_invalido(self):
        with self.assertRaises(ValueError):
            calcular_frete(0, 10, 10)

    def test_distancia_invalida(self):
        with self.assertRaises(ValueError):
            calcular_frete(5, -1, 10)


if __name__ == "__main__":
    unittest.main()
