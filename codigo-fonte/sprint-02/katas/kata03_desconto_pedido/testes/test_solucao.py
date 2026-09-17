import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from solucao import calcular_pedido


class TestDescontoPedido(unittest.TestCase):
    def test_valor_invalido(self):
        with self.assertRaises(ValueError):
            calcular_pedido(0, "comum")

    def test_sem_desconto_valor_baixo(self):
        self.assertEqual(calcular_pedido(50, "comum"), 50.0)

    def test_desconto_base_5_porcento(self):
        self.assertEqual(calcular_pedido(150, "comum"), 142.5)

    def test_desconto_base_10_porcento(self):
        self.assertEqual(calcular_pedido(300, "comum"), 270.0)

    def test_cliente_premium_soma_desconto(self):
        self.assertEqual(calcular_pedido(150, "premium"), 135.0)

    def test_cupom_soma_desconto(self):
        self.assertEqual(calcular_pedido(150, "comum", cupom=True), 135.0)

    def test_desconto_maximo_limitado_a_20_porcento(self):
        self.assertEqual(calcular_pedido(300, "premium", cupom=True), 240.0)


if __name__ == "__main__":
    unittest.main()
