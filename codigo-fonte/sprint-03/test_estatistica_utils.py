import unittest

import estatistica_utils as util


class TestAgregarPorParticipanteTratamento(unittest.TestCase):
    def test_agrega_mediana_por_participante_e_tratamento(self):
        registros = [
            {"participante": "a", "tratamento": "com_ia", "valor": "10"},
            {"participante": "a", "tratamento": "com_ia", "valor": "20"},
            {"participante": "a", "tratamento": "sem_ia", "valor": "30"},
        ]
        agregados = util.agregar_por_participante_tratamento(
            registros, extrair_valor=lambda r: util.numero(r.get("valor")),
        )
        self.assertEqual(agregados["a"]["com_ia"], 15.0)
        self.assertEqual(agregados["a"]["sem_ia"], 30.0)

    def test_ignora_registros_com_valor_none(self):
        registros = [{"participante": "a", "tratamento": "com_ia", "valor": ""}]
        agregados = util.agregar_por_participante_tratamento(
            registros, extrair_valor=lambda r: util.numero(r.get("valor")),
        )
        self.assertEqual(agregados, {})


class TestConstruirPares(unittest.TestCase):
    def test_participante_com_os_dois_tratamentos_vira_par(self):
        agregados = {"a": {"com_ia": 10.0, "sem_ia": 20.0}, "b": {"com_ia": 5.0}}
        pares, incompletos = util.construir_pares(agregados)
        self.assertEqual(pares, [(10.0, 20.0, "a")])
        self.assertEqual(len(incompletos), 1)
        self.assertEqual(incompletos[0]["participante"], "b")
        self.assertEqual(incompletos[0]["tratamentos_faltando"], ["sem_ia"])


class TestWilcoxonPareado(unittest.TestCase):
    def test_sem_pares_e_insuficiente(self):
        resultado = util.testar_wilcoxon_pareado([])
        self.assertFalse(resultado["suficiente"])
        self.assertEqual(resultado["n_pares"], 0)

    def test_todas_diferencas_zero_e_insuficiente(self):
        resultado = util.testar_wilcoxon_pareado([(5.0, 5.0, "a"), (3.0, 3.0, "b")])
        self.assertFalse(resultado["suficiente"])

    def test_diferenca_consistente_favorece_tratamento_a_no_effect_size(self):
        pares = [(10.0, 20.0, "a"), (12.0, 25.0, "b"), (9.0, 19.0, "c"), (11.0, 22.0, "d"), (8.0, 18.0, "e")]
        resultado = util.testar_wilcoxon_pareado(pares)
        self.assertTrue(resultado["suficiente"])
        self.assertEqual(resultado["n_pares"], 5)
        self.assertLess(resultado["effect_size_rank_biserial"], 0)
        self.assertIsNotNone(resultado["p_valor"])
        self.assertLess(resultado["p_valor"], 0.10)

    def test_amostra_pequena_gera_aviso(self):
        resultado = util.testar_wilcoxon_pareado([(1.0, 2.0, "a")])
        self.assertTrue(resultado["suficiente"])
        self.assertTrue(resultado["aviso_amostra_pequena"])


class TestInterpretar(unittest.TestCase):
    def test_interpreta_dados_insuficientes(self):
        texto = util.interpretar({"suficiente": False, "motivo": "sem pares"})
        self.assertIn("Dados insuficientes", texto)

    def test_interpreta_p_valor_significativo(self):
        texto = util.interpretar({"suficiente": True, "p_valor": 0.01})
        self.assertIn("rejeita H0", texto)

    def test_interpreta_p_valor_nao_significativo(self):
        texto = util.interpretar({"suficiente": True, "p_valor": 0.5})
        self.assertIn("nao rejeita H0", texto)


if __name__ == "__main__":
    unittest.main()
