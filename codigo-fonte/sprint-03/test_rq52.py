import csv
import tempfile
import unittest
from pathlib import Path

import rq52_wilcoxon_sucesso as rq52


def trial(**alteracoes):
    registro = {
        "trial_id": "t1", "participante": "a", "kata": "kata01", "tratamento": "com_ia",
        "sucesso": "True", "status": "sucesso",
    }
    registro.update(alteracoes)
    return registro


class TestSucessoBinario(unittest.TestCase):
    def test_sucesso_vira_um(self):
        self.assertEqual(rq52.sucesso_binario(trial()), 1.0)

    def test_limite_atingido_sem_sucesso_vira_zero(self):
        registro = trial(sucesso="False", status="limite_atingido")
        self.assertEqual(rq52.sucesso_binario(registro), 0.0)

    def test_interrompido_e_ignorado(self):
        registro = trial(sucesso="False", status="interrompido")
        self.assertIsNone(rq52.sucesso_binario(registro))

    def test_erro_execucao_e_ignorado(self):
        registro = trial(sucesso="False", status="erro_execucao")
        self.assertIsNone(rq52.sucesso_binario(registro))


class TestAnalisar(unittest.TestCase):
    def test_taxa_de_sucesso_por_participante(self):
        linhas = [
            trial(participante="a", tratamento="com_ia", sucesso="True", status="sucesso"),
            trial(participante="a", tratamento="com_ia", sucesso="False", status="limite_atingido"),
            trial(participante="a", tratamento="sem_ia", sucesso="False", status="limite_atingido"),
            trial(participante="a", tratamento="sem_ia", sucesso="False", status="limite_atingido"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "rq28.csv"
            with caminho.open("w", newline="", encoding="utf-8") as arquivo:
                escritor = csv.DictWriter(arquivo, fieldnames=list(linhas[0].keys()))
                escritor.writeheader()
                escritor.writerows(linhas)
            relatorio = rq52.analisar(caminho)

        self.assertEqual(relatorio["agregados_por_participante"]["a"]["com_ia"], 0.5)
        self.assertEqual(relatorio["agregados_por_participante"]["a"]["sem_ia"], 0.0)

    def test_sem_trials_e_insuficiente(self):
        with tempfile.TemporaryDirectory() as tmp:
            relatorio = rq52.analisar(Path(tmp) / "vazio.csv")
        self.assertFalse(relatorio["wilcoxon"]["suficiente"])


if __name__ == "__main__":
    unittest.main()
