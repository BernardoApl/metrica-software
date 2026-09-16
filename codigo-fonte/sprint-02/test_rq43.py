"""Testes offline da RQ43."""

import csv
import tempfile
import unittest
import uuid
from pathlib import Path

import rq28_cronometragem as rq28
import rq43_validar_rastreabilidade_trials as rq43


def registro_trial(**alteracoes):
    registro = {
        "trial_id": str(uuid.uuid4()),
        "participante": "integrante1",
        "kata": "kata03_deduplicador_contatos",
        "tratamento": "com_ia",
        "issue": "36",
        "inicio_utc": "2026-09-16T12:00:00+00:00",
        "fim_utc": "2026-09-16T12:01:00+00:00",
        "duracao_segundos": "60.0",
        "limite_segundos": "2100.0",
        "status": "sucesso",
        "sucesso": "True",
        "censurado": "False",
        "verificacoes": "1",
        "ultimo_codigo_testes": "0",
        "comando_testes": '["python", "-m", "unittest", "discover", "-s", "testes"]',
        "diretorio": str(Path.cwd()),
    }
    registro.update(alteracoes)
    return registro


def registro_metrica(trial_id, **alteracoes):
    registro = {
        "participante": "integrante1",
        "kata": "kata03_deduplicador_contatos",
        "tratamento": "com_ia",
        "issue": "36",
        "trial_id": trial_id,
        "arquivo": "solucao.py",
        "medido_em_utc": "2026-09-16T12:02:00+00:00",
        "loc": "20",
        "sloc": "15",
        "lloc": "10",
        "comentarios": "0",
        "linhas_em_branco": "4",
        "funcoes_analisadas": "1",
        "complexidade_media": "2.0",
        "complexidade_maxima": "2",
        "indice_manutenibilidade": "90.0",
        "duplicacao_disponivel": "False",
        "duplicacao_percentual": "",
        "linhas_duplicadas": "",
        "linhas_analisadas_duplicacao": "",
    }
    registro.update(alteracoes)
    return registro


def gravar_csv(caminho, colunas, registros):
    with caminho.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=colunas)
        escritor.writeheader()
        escritor.writerows(registros)


class TestRQ43(unittest.TestCase):
    def test_trial_completo_fica_rastreavel(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            kata = raiz / "kata03"
            kata.mkdir()
            (kata / "solucao.py").write_text("def f():\n    return True\n", encoding="utf-8")
            (raiz / "lab02_kata03_com_ia_prompts.md").write_text("prompt", encoding="utf-8")

            trial = registro_trial(diretorio=str(kata))
            linha = rq43.validar_rastreabilidade(
                [trial],
                [registro_metrica(trial["trial_id"])],
                raiz,
            )[0]

        self.assertTrue(linha["rastreabilidade_ok"])
        self.assertEqual(linha["alertas"], "")

    def test_trial_com_ia_sem_prompt_e_sem_metrica_gera_alertas(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            kata = raiz / "kata03"
            kata.mkdir()
            (kata / "solucao.py").write_text("def f():\n    return True\n", encoding="utf-8")

            trial = registro_trial(diretorio=str(kata))
            linha = rq43.validar_rastreabilidade([trial], [], raiz)[0]

        self.assertFalse(linha["rastreabilidade_ok"])
        self.assertIn("prompt_interacao_ia_nao_encontrado", linha["alertas"])
        self.assertIn("metricas_rq30_nao_encontradas_para_trial", linha["alertas"])

    def test_metricas_com_trial_id_orfao_sao_reportadas(self):
        erros = rq43.validar_metricas_referenciam_trials(
            [registro_trial(trial_id="11111111-1111-1111-1111-111111111111")],
            [registro_metrica("22222222-2222-2222-2222-222222222222")],
        )
        self.assertEqual(len(erros), 1)
        self.assertIn("trial_id sem correspondente", erros[0])

    def test_gerar_relatorio_salva_estado_incompleto_quando_rq30_ausente(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            kata = raiz / "kata03"
            kata.mkdir()
            (kata / "solucao.py").write_text("def f():\n    return True\n", encoding="utf-8")
            (raiz / "lab02_kata03_com_ia_prompts.md").write_text("prompt", encoding="utf-8")

            csv_rq28 = raiz / "tempos.csv"
            csv_rq30 = raiz / "metricas.csv"
            gravar_csv(csv_rq28, rq28.COLUNAS, [registro_trial(diretorio=str(kata))])

            relatorio = rq43.gerar_relatorio(csv_rq28, csv_rq30, raiz)

        self.assertFalse(relatorio["valido"])
        self.assertTrue(relatorio["rq28_valido"])
        self.assertFalse(relatorio["rq30_valido"])
        self.assertIn("CSV da RQ30 ausente", relatorio["alertas"][0])

    def test_gerar_relatorio_valido_com_rq28_e_rq30(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            kata = raiz / "kata03"
            kata.mkdir()
            solucao = kata / "solucao.py"
            solucao.write_text("def f():\n    return True\n", encoding="utf-8")
            (raiz / "lab02_kata03_com_ia_prompts.md").write_text("prompt", encoding="utf-8")

            trial = registro_trial(diretorio=str(kata))
            csv_rq28 = raiz / "tempos.csv"
            csv_rq30 = raiz / "metricas.csv"
            gravar_csv(csv_rq28, rq28.COLUNAS, [trial])
            gravar_csv(csv_rq30, rq43.RQ30_COLUNAS, [
                registro_metrica(trial["trial_id"], arquivo=str(solucao)),
            ])

            relatorio = rq43.gerar_relatorio(csv_rq28, csv_rq30, raiz)

        self.assertTrue(relatorio["valido"], relatorio)
        self.assertEqual(relatorio["trials_rastreaveis"], 1)


if __name__ == "__main__":
    unittest.main()
