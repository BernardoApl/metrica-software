import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from solucao import calcular_estacionamento


class TestCalculoEstacionamento(unittest.TestCase):
    def test_carro_uma_hora(self):
        self.assertEqual(calcular_estacionamento(1, "carro"), 8.0)

    def test_carro_fracao_arredonda_para_cima(self):
        self.assertEqual(calcular_estacionamento(1.2, "carro"), 12.0)

    def test_carro_atinge_diaria(self):
        self.assertEqual(calcular_estacionamento(10, "carro"), 40.0)

    def test_moto_horas_intermediarias(self):
        self.assertEqual(calcular_estacionamento(3, "moto"), 9.0)

    def test_caminhao_menos_de_uma_hora(self):
        self.assertEqual(calcular_estacionamento(0.5, "caminhao"), 15.0)

    def test_horas_invalidas(self):
        with self.assertRaises(ValueError):
            calcular_estacionamento(0, "carro")

    def test_veiculo_invalido(self):
        with self.assertRaises(ValueError):
            calcular_estacionamento(2, "onibus")


if __name__ == "__main__":
    unittest.main()
