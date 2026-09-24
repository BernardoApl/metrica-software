import unittest

import rq51_wilcoxon_tempo as rq51


def trial(**alteracoes):
    registro = {
        "trial_id": "t1", "participante": "a", "kata": "kata01", "tratamento": "com_ia",
        "duracao_segundos": "100.0", "limite_segundos": "2100.0", "sucesso": "True", "censurado": "False",
        "status": "sucesso",
    }
    registro.update(alteracoes)
    return registro


class TestDuracaoEfetiva(unittest.TestCase):
    def test_sucesso_usa_duracao_real(self):
        self.assertEqual(rq51.duracao_efetiva(trial()), 100.0)

    def test_censurado_usa_limite(self):
        registro = trial(sucesso="False", censurado="True", duracao_segundos="2100.0")
        self.assertEqual(rq51.duracao_efetiva(registro), 2100.0)

    def test_erro_execucao_e_ignorado(self):
        registro = trial(sucesso="False", censurado="False", status="erro de execucao")
        self.assertIsNone(rq51.duracao_efetiva(registro))


class TestAnalisar(unittest.TestCase):
    def test_sem_trials_e_insuficiente(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            relatorio = rq51.analisar(Path(tmp) / "vazio.csv")
        self.assertFalse(relatorio["wilcoxon"]["suficiente"])
        self.assertEqual(relatorio["total_trials_lidos"], 0)

    def test_participantes_completos_geram_par_e_estatistica(self):
        import csv
        import tempfile
        from pathlib import Path

        linhas = []
        for participante in ("a", "b", "c"):
            for tratamento, duracao in (("com_ia", "100"), ("com_ia", "110"),
                                          ("sem_ia", "200"), ("sem_ia", "210")):
                linhas.append(trial(participante=participante, tratamento=tratamento, duracao_segundos=duracao))

        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "rq28.csv"
            with caminho.open("w", newline="", encoding="utf-8") as arquivo:
                escritor = csv.DictWriter(arquivo, fieldnames=list(linhas[0].keys()))
                escritor.writeheader()
                escritor.writerows(linhas)
            relatorio = rq51.analisar(caminho)

        self.assertEqual(len(relatorio["pares_utilizados"]), 3)
        self.assertTrue(relatorio["wilcoxon"]["suficiente"])
        self.assertEqual(relatorio["participantes_incompletos"], [])


if __name__ == "__main__":
    unittest.main()
