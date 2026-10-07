"""Testes de particionamento, deduplicacao e cache da coleta RQ73."""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "coleta"))
from rq73_coletar_candidatos import BuscaGitHub, ErroGitHub, coletar, exportar


def repo(i, estrelas=None):
    return dict(id=i, full_name=f"org/repo{i}", stargazers_count=estrelas or 1001+i,
                private=False, html_url=f"https://github.com/org/repo{i}")


class BuscaSimulada:
    def __init__(self, registros):
        self.registros = registros
        self.chamadas = []

    def buscar(self, consulta, pagina=1):
        self.chamadas.append((consulta, pagina))
        faixa = re.search(r"stars:(\d+)\.\.(\d+)", consulta)
        registros = self.registros
        if faixa:
            menor, maior = map(int, faixa.groups())
            registros = [r for r in registros if menor <= r['stargazers_count'] <= maior]
        registros = sorted(registros, key=lambda r: -r['stargazers_count'])
        return dict(coletado_em="2026-10-06T00:00:00+00:00", resposta=dict(
            total_count=len(registros), items=registros[(pagina-1)*100:pagina*100]))


class TestColeta(unittest.TestCase):
    def test_particiona_e_pagina_sem_perder_repositorios(self):
        busca = BuscaSimulada([repo(i) for i in range(1205)])
        resultado = coletar(busca, limite=1205)
        itens = resultado['repositorios']
        self.assertEqual(len(itens), 1205)
        self.assertEqual(len({r['id_github'] for r in itens}), 1205)
        self.assertTrue(all(p <= 10 for _, p in busca.chamadas))
        self.assertTrue(all(p['total_informado'] <= 1000 for p in resultado['metadados']['particoes']))
        self.assertEqual([r['estrelas'] for r in itens], sorted([r['estrelas'] for r in itens], reverse=True))

    def test_respeita_limite(self):
        resultado = coletar(BuscaSimulada([repo(i) for i in range(500)]), limite=123)
        self.assertEqual(len(resultado['repositorios']), 123)
        self.assertTrue(resultado['metadados']['meta_atingida'])

    def test_remove_duplicados_e_privados(self):
        privado = dict(repo(2), private=True)
        resultado = coletar(BuscaSimulada([repo(1), repo(1), privado]))
        self.assertEqual(len(resultado['repositorios']), 1)
        self.assertEqual(resultado['metadados']['duplicados'], 1)
        self.assertEqual(resultado['metadados']['rejeitados'], 1)

    def test_nao_trunca_empate_acima_de_mil(self):
        with self.assertRaises(ErroGitHub):
            coletar(BuscaSimulada([repo(i, 1001) for i in range(1001)]))

    def test_busca_vazia_nao_atinge_meta(self):
        resultado = coletar(BuscaSimulada([]))
        self.assertTrue(resultado['metadados']['concluido'])
        self.assertFalse(resultado['metadados']['meta_atingida'])

    def test_exportacao(self):
        resultado = coletar(BuscaSimulada([repo(1)]))
        with tempfile.TemporaryDirectory() as tmp:
            saida = Path(tmp) / 'candidatos.json'
            exportar(resultado, saida)
            self.assertEqual(json.loads(saida.read_text(encoding='utf-8')), resultado)
            self.assertTrue(saida.with_suffix('.csv').exists())
            self.assertTrue(saida.with_name('candidatos_funil.csv').exists())

    def test_cache_evita_requisicao(self):
        resposta = MagicMock()
        resposta.__enter__.return_value = resposta
        resposta.read.return_value = json.dumps(dict(items=[], total_count=0, incomplete_results=False)).encode()
        resposta.headers = {}
        with tempfile.TemporaryDirectory() as tmp, patch('urllib.request.urlopen', return_value=resposta) as abrir:
            cliente = BuscaGitHub('token-teste', Path(tmp), dormir=lambda _: None)
            primeiro = cliente.buscar('is:public stars:>1000')
            self.assertEqual(cliente.buscar('is:public stars:>1000'), primeiro)
            self.assertEqual(abrir.call_count, 1)

    def test_busca_incompleta_nao_e_salva(self):
        resposta = MagicMock()
        resposta.__enter__.return_value = resposta
        resposta.read.return_value = b'{"items": [], "total_count": 1, "incomplete_results": true}'
        resposta.headers = {}
        with tempfile.TemporaryDirectory() as tmp, patch('urllib.request.urlopen', return_value=resposta):
            cliente = BuscaGitHub('token-teste', Path(tmp), tentativas=1)
            with self.assertRaises(ErroGitHub):
                cliente.buscar('is:public stars:>1000')
            self.assertEqual(list(Path(tmp).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
