import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from solucao import detectar_conflitos


class TestEscalonadorTurnos(unittest.TestCase):
    def test_lista_vazia(self):
        self.assertEqual(detectar_conflitos([]), [])

    def test_conflito_mesmo_funcionario(self):
        turnos = [
            {"funcionario": "Ana", "inicio": "08:00", "fim": "12:00"},
            {"funcionario": "Ana", "inicio": "11:00", "fim": "15:00"},
        ]
        self.assertEqual(detectar_conflitos(turnos), [(0, 1)])

    def test_sem_conflito_bordas_tocando(self):
        turnos = [
            {"funcionario": "Ana", "inicio": "08:00", "fim": "12:00"},
            {"funcionario": "Ana", "inicio": "12:00", "fim": "15:00"},
        ]
        self.assertEqual(detectar_conflitos(turnos), [])

    def test_sem_conflito_funcionarios_diferentes(self):
        turnos = [
            {"funcionario": "Ana", "inicio": "08:00", "fim": "12:00"},
            {"funcionario": "Bruno", "inicio": "09:00", "fim": "11:00"},
        ]
        self.assertEqual(detectar_conflitos(turnos), [])

    def test_multiplos_conflitos(self):
        turnos = [
            {"funcionario": "Ana", "inicio": "08:00", "fim": "12:00"},
            {"funcionario": "Ana", "inicio": "09:00", "fim": "10:00"},
            {"funcionario": "Ana", "inicio": "11:00", "fim": "13:00"},
        ]
        self.assertEqual(detectar_conflitos(turnos), [(0, 1), (0, 2)])

    def test_horario_invalido(self):
        turnos = [{"funcionario": "Ana", "inicio": "25:00", "fim": "26:00"}]
        with self.assertRaises(ValueError):
            detectar_conflitos(turnos)


if __name__ == "__main__":
    unittest.main()
