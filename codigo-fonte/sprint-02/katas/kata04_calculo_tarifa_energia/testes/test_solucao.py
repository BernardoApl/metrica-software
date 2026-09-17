import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from solucao import calcular_tarifa_energia


class TestCalculoTarifaEnergia(unittest.TestCase):
    def test_residencial_faixa_inicial(self):
        self.assertEqual(calcular_tarifa_energia(50, "residencial", "verde"), 25.0)

    def test_residencial_duas_faixas(self):
        self.assertEqual(calcular_tarifa_energia(150, "residencial", "verde"), 85.0)

    def test_residencial_tres_faixas_bandeira_amarela(self):
        self.assertEqual(calcular_tarifa_energia(400, "residencial", "amarela"), 288.0)

    def test_comercial_aplica_tarifa_minima(self):
        self.assertEqual(calcular_tarifa_energia(50, "comercial", "verde"), 50.0)

    def test_bandeira_vermelha_soma_sobretaxa(self):
        self.assertEqual(calcular_tarifa_energia(50, "residencial", "vermelha"), 27.0)

    def test_consumo_invalido(self):
        with self.assertRaises(ValueError):
            calcular_tarifa_energia(0, "residencial", "verde")

    def test_tipo_ligacao_invalido(self):
        with self.assertRaises(ValueError):
            calcular_tarifa_energia(100, "industrial", "verde")

    def test_bandeira_invalida(self):
        with self.assertRaises(ValueError):
            calcular_tarifa_energia(100, "residencial", "azul")


if __name__ == "__main__":
    unittest.main()
