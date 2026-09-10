"""Testes offline da RQ29."""

import csv
import json
import tempfile
import unittest
import uuid
from pathlib import Path

import rq28_cronometragem as rq28
import rq29_validar_trials as rq29


def registro_valido(**alteracoes):
    registro = {
        "trial_id": str(uuid.uuid4()),
        "participante": "integrante1",
        "kata": "kata01",
        "tratamento": "com_ia",
        "issue": "29",
        "inicio_utc": "2026-09-10T12:00:00+00:00",
        "fim_utc": "2026-09-10T12:03:00+00:00",
        "duracao_segundos": "180.0",
        "limite_segundos": "2100.0",
        "status": "sucesso",
        "sucesso": "True",
        "censurado": "False",
        "verificacoes": "1",
        "ultimo_codigo_testes": "0",
        "comando_testes": json.dumps(["python", "-m", "unittest", "discover", "-s", "testes"]),
        "diretorio": str(Path.cwd()),
    }
    registro.update(alteracoes)
    return registro


class TestRQ29(unittest.TestCase):
    def test_registro_valido_nao_gera_erros(self):
        self.assertEqual(rq29.validar_registro(registro_valido(), 2), [])

    def test_sucesso_precisa_ser_coerente_com_status_e_codigo_zero(self):
        erros = rq29.validar_registro(
            registro_valido(status="interrompido", sucesso="True", ultimo_codigo_testes="1"), 2,
        )
        self.assertIn("linha 2: sucesso incoerente com status", erros)
        self.assertIn("linha 2: sucesso exige ultimo_codigo_testes igual a 0", erros)

    def test_trial_censurado_usa_limite_como_duracao(self):
        erros = rq29.validar_registro(
            registro_valido(
                status="limite_atingido",
                sucesso="False",
                censurado="True",
                duracao_segundos="2000",
                limite_segundos="2100",
                ultimo_codigo_testes="1",
            ),
            2,
        )
        self.assertIn("linha 2: trial censurado deve ter duracao igual ao limite", erros)

    def test_valida_csv_com_duplicidade(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "tempos.csv"
            mesmo_id = str(uuid.uuid4())
            registros = [
                registro_valido(trial_id=mesmo_id),
                registro_valido(trial_id=mesmo_id, kata="kata02"),
            ]
            with caminho.open("w", newline="", encoding="utf-8") as arquivo:
                escritor = csv.DictWriter(arquivo, fieldnames=rq28.COLUNAS)
                escritor.writeheader()
                escritor.writerows(registros)

            relatorio = rq29.validar_csv(caminho)

        self.assertFalse(relatorio["valido"])
        self.assertEqual(relatorio["total_registros"], 2)
        self.assertTrue(any("trial_id duplicado" in erro for erro in relatorio["erros"]))

    def test_piloto_gera_csv_valido(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "piloto.csv"
            relatorio = rq29.executar_piloto(caminho)

        self.assertTrue(relatorio["valido"], relatorio["erros"])
        self.assertEqual(relatorio["total_registros"], 1)
        self.assertEqual(relatorio["resumo_status"], {"sucesso": 1})


if __name__ == "__main__":
    unittest.main()
