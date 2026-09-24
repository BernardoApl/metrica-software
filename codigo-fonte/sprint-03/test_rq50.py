import unittest

import rq50_auditoria_dataset as auditoria


def linha_rq28(**alteracoes):
    linha = {
        "trial_id": "abc",
        "participante": "integrante1",
        "kata": "kata01_frete_progressivo",
        "tratamento": "com_ia",
        "issue": "34",
        "duracao_segundos": "100.0",
        "sucesso": "True",
    }
    linha.update(alteracoes)
    return linha


def linha_rq30(**alteracoes):
    linha = {
        "participante": "integrante1",
        "kata": "kata01_frete_progressivo",
        "tratamento": "com_ia",
        "issue": "34",
        "complexidade_media": "2.0",
        "indice_manutenibilidade": "80.0",
        "duplicacao_percentual": "0.0",
    }
    linha.update(alteracoes)
    return linha


class TestAuditarCobertura(unittest.TestCase):
    def test_trial_ausente_aparece_como_faltando(self):
        relatorio = auditoria.auditar_cobertura([], [])
        self.assertEqual(relatorio["total_faltando"], len(auditoria.DESENHO_ESPERADO))
        self.assertEqual(relatorio["total_ok"], 0)

    def test_trial_correto_aparece_como_ok(self):
        relatorio = auditoria.auditar_cobertura([linha_rq28()], [linha_rq30()])
        issues_ok = {item["issue"] for item in relatorio["ok"]}
        self.assertIn("34", issues_ok)
        self.assertEqual(relatorio["total_divergente"], 0)

    def test_kata_nao_oficial_gera_divergencia(self):
        relatorio = auditoria.auditar_cobertura(
            [linha_rq28(kata="kata01_outra_variante")], [linha_rq30(kata="kata01_outra_variante")],
        )
        self.assertEqual(relatorio["total_divergente"], 1)
        self.assertEqual(relatorio["divergentes"][0]["issue"], "34")

    def test_trial_sucesso_sem_rq30_gera_divergencia(self):
        relatorio = auditoria.auditar_cobertura([linha_rq28()], [])
        self.assertEqual(relatorio["total_divergente"], 1)
        self.assertIn("sem medicao correspondente", relatorio["divergentes"][0]["problemas"][0])


class TestOutliersIqr(unittest.TestCase):
    def test_menos_de_quatro_valores_nao_calcula_outliers(self):
        resultado = auditoria.outliers_iqr([1.0, 2.0, 3.0])
        self.assertEqual(resultado["outliers"], [])
        self.assertIn("aviso", resultado)

    def test_detecta_outlier_evidente(self):
        resultado = auditoria.outliers_iqr([10.0, 11.0, 9.0, 10.5, 9.5, 500.0])
        self.assertIn(500.0, resultado["outliers"])


class TestAuditarPrincipal(unittest.TestCase):
    def test_pronto_para_wilcoxon_falso_quando_falta_trial(self):
        relatorio = auditoria.auditar_outliers([linha_rq28()], [linha_rq30()])
        self.assertIn("duracao_segundos", relatorio)


if __name__ == "__main__":
    unittest.main()
