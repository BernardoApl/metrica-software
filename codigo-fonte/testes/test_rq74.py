"""Testes offline da coleta RQ74; respostas sinteticas nao sao dados de pesquisa."""

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from email.message import Message

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "coleta"))
import rq74_metadados_repositorios as rq74


def no_valido():
    return dict(id="R_1", nameWithOwner="org/novo", url="https://github.com/org/novo",
                description=None, homepageUrl=None, createdAt="2020-01-01T00:00:00Z",
                updatedAt="2026-01-01T00:00:00Z", pushedAt=None, stargazerCount=0,
                forkCount=0, diskUsage=0, isFork=False, isArchived=False,
                isDisabled=False, isEmpty=True, visibility="PUBLIC", hasIssuesEnabled=False,
                owner={"login": "org"}, primaryLanguage=None, licenseInfo=None,
                defaultBranchRef=None, issues={"totalCount": 0}, issuesFechadas={"totalCount": 0},
                pullRequests={"totalCount": 0}, prsAceitos={"totalCount": 0},
                releases={"totalCount": 0})


class TestRQ74(unittest.TestCase):
    def test_contribuidores_paralelos_salvam_lotes_e_preservam_falhas(self):
        with tempfile.TemporaryDirectory() as pasta:
            entrada = Path(pasta) / 'entrada.csv'
            nomes = [f'org/repo{i}' for i in range(26)]
            entrada.write_text('nome_completo\n' + '\n'.join(nomes), encoding='utf-8')
            saida = Path(pasta) / 'saida.json'
            estado = rq74.preparar_estado(nomes, entrada, saida)
            estado['repositorios'] = [rq74.normalizar(n, dict(no_valido(), nameWithOwner=n)) for n in nomes]
            cliente = Mock()
            def consultar(nome):
                if nome == 'org/repo12':
                    raise rq74.ErroGitHub('HTTP 403')
                return dict(total=int(nome.split('repo')[1]), coletado_em=rq74.agora())
            cliente.contribuidores.side_effect = consultar
            with patch.object(rq74, 'salvar', wraps=rq74.salvar) as gravar:
                rq74.complementar_contribuidores(cliente, estado, saida, trabalhadores=4)
            self.assertEqual(gravar.call_count, 2)
            self.assertEqual(estado['metadados']['coletados_ok'], 25)
            self.assertIsNone(estado['repositorios'][12]['contribuidores_total'])
            for i, registro in enumerate(estado['repositorios']):
                if i != 12:
                    self.assertEqual(registro['contribuidores_total'], i)
            cliente.contribuidores.reset_mock()
            cliente.contribuidores.side_effect = lambda _: dict(total=12, coletado_em=rq74.agora())
            rq74.complementar_contribuidores(cliente, estado, saida, trabalhadores=4)
            cliente.contribuidores.assert_called_once_with('org/repo12')
            self.assertTrue(estado['metadados']['concluido'])

    def test_gravacao_repete_bloqueio_temporario(self):
        temporario = Mock()
        temporario.replace.side_effect = [PermissionError('arquivo em uso'), None]
        with patch.object(rq74.time, 'sleep') as dormir:
            rq74.substituir_com_retentativa(temporario, Path('destino.json'))
        self.assertEqual(temporario.replace.call_count, 2)
        dormir.assert_called_once_with(0.2)

    def test_gravacao_nao_oculta_bloqueio_permanente(self):
        temporario = Mock()
        temporario.replace.side_effect = PermissionError('arquivo em uso')
        with patch.object(rq74.time, 'sleep'), self.assertRaises(PermissionError):
            rq74.substituir_com_retentativa(temporario, Path('destino.json'))
        self.assertEqual(temporario.replace.call_count, 6)

    def test_preserva_renomeacao_nulos_e_zeros(self):
        registro = rq74.normalizar("org/antigo", no_valido())
        self.assertEqual(registro["status"], "ok")
        self.assertEqual(registro["nome_solicitado"], "org/antigo")
        self.assertEqual(registro["nome_completo"], "org/novo")
        self.assertIsNone(registro["linguagem"])
        self.assertEqual(registro["issues_total"], 0)

    def test_ausencia_e_erro_parcial_nao_sao_sucesso(self):
        self.assertEqual(rq74.normalizar("org/a", None)["status"], "indisponivel")
        no = no_valido()
        no["releases"] = {"totalCount": None}
        self.assertEqual(rq74.normalizar("org/a", no)["status"], "incompleto")
        self.assertEqual(rq74.normalizar("org/a", no_valido(),
                         [{"message": "falha em campo opcional"}])["status"], "erro_graphql")

    def test_consulta_usa_nomes_selecionados_com_variaveis(self):
        consulta, variaveis = rq74.montar_consulta(["org/a", "outro/b"])
        self.assertIn("r1: repository", consulta)
        self.assertNotIn("search(", consulta)
        self.assertEqual(variaveis, {"o0": "org", "n0": "a", "o1": "outro", "n1": "b"})

    def test_checkpoint_retoma_apenas_falhas_e_exporta_todos(self):
        with tempfile.TemporaryDirectory() as pasta:
            entrada = Path(pasta) / "selecao.csv"
            entrada.write_text("nome_completo\norg/a\norg/b\nORG/A\n", encoding="utf-8")
            saida = Path(pasta) / "metadados.json"
            nomes = rq74.ler_selecao(entrada)
            self.assertEqual(nomes, ["org/a", "org/b"])
            estado = rq74.preparar_estado(nomes, entrada, saida)
            cliente = Mock(ultimo_rate_limit={"remaining": 99})
            cliente.executar.side_effect = [{"r0": no_valido()}, rq74.ErroGitHub("offline")]
            with self.assertRaises(rq74.ErroGitHub):
                rq74.coletar(cliente, estado, saida, tamanho_lote=1)
            estado = rq74.preparar_estado(nomes, entrada, saida)
            self.assertFalse(estado["metadados"]["concluido"])
            self.assertEqual(estado["repositorios"][0]["status_metadados"], "ok")
            cliente.executar.reset_mock(side_effect=True)
            cliente.executar.return_value = {"r0": no_valido()}
            rq74.coletar(cliente, estado, saida, tamanho_lote=1)
            self.assertEqual(cliente.executar.call_count, 1)
            self.assertEqual(cliente.executar.call_args.args[1]["n0"], "b")
            cliente.contribuidores.return_value = dict(total=5, coletado_em=rq74.agora())
            rq74.complementar_contribuidores(cliente, estado, saida)
            self.assertTrue(json.loads(saida.read_text(encoding="utf-8"))["metadados"]["concluido"])
            cliente.contribuidores.reset_mock()
            rq74.complementar_contribuidores(cliente, estado, saida)
            cliente.contribuidores.assert_not_called()
            with saida.with_suffix(".csv").open(encoding="utf-8", newline="") as arquivo:
                self.assertEqual(len(list(csv.DictReader(arquivo))), 2)
            entrada.write_text("nome_completo\norg/c\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                rq74.preparar_estado(["org/c"], entrada, saida)

    def test_erro_graphql_afeta_apenas_alias_correspondente(self):
        with tempfile.TemporaryDirectory() as pasta:
            estado = {"metadados": {}, "repositorios": [
                dict(nome_solicitado="org/a", status="pendente"),
                dict(nome_solicitado="org/b", status="pendente")]}
            cliente = Mock(ultimo_rate_limit=None)
            def resposta(*args):
                cliente.erros_graphql = [{"path": ["r1", "description"], "message": "indisponivel"}]
                return {"r0": no_valido(), "r1": no_valido()}
            cliente.executar.side_effect = resposta
            rq74.coletar(cliente, estado, Path(pasta) / "saida.json")
            self.assertEqual([r["status_metadados"] for r in estado["repositorios"]], ["ok", "erro_graphql"])

    def test_idade_reproduzivel_com_fuso(self):
        self.assertEqual(rq74.calcular_idade("2020-01-01T00:00:00Z", "2021-01-01T00:00:00Z")[0], 366)
        self.assertEqual(rq74.calcular_idade("2020-01-01T00:00:00Z", "2019-12-31T21:00:00-03:00"), (0, 0))
        with self.assertRaises(ValueError):
            rq74.calcular_idade("2021-01-01T00:00:00Z", "2020-01-01T00:00:00Z")
        with self.assertRaises(ValueError):
            rq74.data_utc("2020-01-01")

    def test_contagem_contribuidores_sem_baixar_todas_paginas(self):
        link = '<https://api.github.com/repos/o/r/contributors?per_page=1&page=731&anon=true>; rel="last"'
        self.assertEqual(rq74.contar_contribuidores(200, [{}], link), 731)
        self.assertEqual(rq74.contar_contribuidores(204, [], ""), 0)
        self.assertEqual(rq74.contar_contribuidores(200, [], ""), 0)
        self.assertEqual(rq74.contar_contribuidores(200, [{}], ""), 1)
        with self.assertRaises(ValueError):
            rq74.contar_contribuidores(200, [{}], '<https://api.github.com/x?page=2>; rel="next"')

    def test_contribuidores_rate_limit_aguarda_e_retenta(self):
        dormir = Mock()
        cliente = rq74.ClienteMetadados("token-teste", dormir=dormir)
        headers = Message()
        headers["Retry-After"] = "120"
        erro = HTTPError("https://api.github.com", 429, "limite", headers, None)
        resposta = Mock(status=204, headers={})
        resposta.__enter__ = Mock(return_value=resposta)
        resposta.__exit__ = Mock(return_value=False)
        with patch.object(rq74.urllib.request, "urlopen", side_effect=[erro, resposta]):
            self.assertEqual(cliente.contribuidores("org/r")["total"], 0)
        dormir.assert_called_once_with(120)

    def test_migra_checkpoint_antigo_sem_reconsultar_graphql(self):
        with tempfile.TemporaryDirectory() as pasta:
            entrada = Path(pasta) / "entrada.csv"
            entrada.write_text("nome_completo\norg/a\n", encoding="utf-8")
            saida = Path(pasta) / "saida.json"
            estado = rq74.preparar_estado(["org/a"], entrada, saida)
            antigo = rq74.normalizar("org/a", no_valido())
            for campo in ("status_metadados", "status_contribuidores"):
                antigo.pop(campo)
            estado["repositorios"] = [antigo]
            saida.write_text(json.dumps(estado), encoding="utf-8")
            novo = rq74.preparar_estado(["org/a"], entrada, saida)
            self.assertEqual(novo["repositorios"][0]["status_metadados"], "ok")
            self.assertEqual(novo["repositorios"][0]["status"], "incompleto")
            self.assertIsNotNone(novo["repositorios"][0]["idade_anos"])
            cliente = Mock()
            rq74.coletar(cliente, novo, saida)
            cliente.executar.assert_not_called()

    def test_falha_contribuidores_preserva_metadados_e_nao_vira_zero(self):
        with tempfile.TemporaryDirectory() as pasta:
            saida = Path(pasta) / "saida.json"
            estado = {"metadados": {"referencia_idade": "2026-01-01T00:00:00Z"},
                      "repositorios": [rq74.normalizar("org/a", no_valido())]}
            cliente = Mock()
            cliente.contribuidores.side_effect = rq74.ErroGitHub("HTTP 403")
            rq74.complementar_contribuidores(cliente, estado, saida)
            r = estado["repositorios"][0]
            self.assertEqual(r["status_metadados"], "ok")
            self.assertEqual(r["status_contribuidores"], "erro")
            self.assertIsNone(r["contribuidores_total"])
            self.assertEqual(r["status"], "incompleto")
            self.assertEqual(r["bruto"], no_valido())
            self.assertFalse(estado["metadados"]["concluido"])

    def test_retomada_rejeita_mudanca_referencia_idade(self):
        with tempfile.TemporaryDirectory() as pasta:
            entrada = Path(pasta) / "entrada.csv"
            entrada.write_text("nome_completo\norg/a\n", encoding="utf-8")
            saida = Path(pasta) / "saida.json"
            estado = rq74.preparar_estado(["org/a"], entrada, saida, "2026-01-01T00:00:00Z")
            rq74.salvar(estado, saida)
            with self.assertRaises(ValueError):
                rq74.preparar_estado(["org/a"], entrada, saida, "2026-02-01T00:00:00Z")

    def test_rejeita_csv_sem_identidade_e_nome_invalido(self):
        with tempfile.TemporaryDirectory() as pasta:
            entrada = Path(pasta) / "entrada.csv"
            for conteudo in ("url\nx\n", "nome_completo\n../a/b\n", "nome_completo\n"):
                entrada.write_text(conteudo, encoding="utf-8")
                with self.assertRaises(ValueError):
                    rq74.ler_selecao(entrada)


if __name__ == "__main__":
    unittest.main()
