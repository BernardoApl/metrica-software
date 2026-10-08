"""RQ75: fixtures sinteticas, sem acesso a rede."""
import gzip
import csv
import json
import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'coleta'))
import rq75_releases_tags_commits as rq75
import coleta_dora
from test_coleta_dora import ClienteFalso, release, commit_api


def test_release_recente_apos_pagina_antiga_e_fim_com_fracao():
    antigas = [dict(release(f'v{i}', '2024-01-01T00:00:00Z'), id=i) for i in range(200)]
    nova = dict(release('nova', '2026-09-30T23:59:59.500Z'), id=201)
    cliente = ClienteFalso(releases=antigas + [nova])
    resultado = coleta_dora.coletar_releases(cliente, 'o/r', '2025-10-01', '2026-09-30')
    assert len(cliente.chamadas) == 3
    assert [r['tag_name'] for r in resultado['releases'] if r['dentro_janela']] == ['nova']


def test_release_sem_publicacao_nao_usa_created_at():
    item = dict(release('draft', '2026-01-01T00:00:00Z'), published_at=None)
    r = coleta_dora.coletar_releases(ClienteFalso(releases=[item]), 'o/r', '2025-10-01', '2026-09-30')
    assert not r['releases'][0]['dentro_janela']


def test_tags_paginadas_datadas_por_sha_com_reuso_e_falha():
    cliente = Mock()
    cliente.paginar.return_value = iter([
        {'status': 200, 'corpo': [{'tag_name': 'v1', 'sha': 'a'}, {'tag_name': 'sem-release', 'sha': 'a'}]},
        {'status': 200, 'corpo': [{'tag_name': 'v1', 'sha': 'a'}, {'tag_name': 'apagada', 'sha': 'b'}]},
    ])
    cliente.get.side_effect = [
        {'status': 200, 'corpo': {'sha': 'a', 'data_autor': '2026-09-30T23:59:59.900Z'}},
        {'status': 404, 'corpo': None},
    ]
    resultado = rq75.coletar_tags(cliente, 'o/r', '2025-10-01', '2026-09-30', [{'tag_name': 'v1'}])
    assert cliente.get.call_count == 2
    assert len(resultado['tags']) == 3
    assert resultado['tags'][0]['tem_release'] and resultado['tags'][0]['dentro_janela']
    assert not resultado['tags'][1]['tem_release']
    assert resultado['tags'][2]['status'] == 'indisponivel'
    assert not resultado['tags'][2]['dentro_janela']


class ClienteComTags(ClienteFalso):
    def paginar(self, caminho, *args, **kwargs):
        if caminho.endswith('/tags'):
            yield {'status': 200, 'corpo': []}
        else:
            yield from super().paginar(caminho, *args, **kwargs)


def test_commits_acima_de_250_com_base_fora_janela_e_exportacao(tmp_path):
    commits = [commit_api(f'sha{i}', '2026-01-01T00:00:00Z') for i in range(301)]
    cliente = ClienteComTags(releases=[release('v2', '2026-02-01T00:00:00Z'),
                                      release('v1', '2025-09-01T00:00:00Z')],
                            compares={('v1', 'v2'): commits})
    resultado = rq75.coletar_repositorio(cliente, 'o/r', '2025-10-01', '2026-09-30')
    assert resultado['concluido']
    assert len(resultado['commits']) == 301
    assert resultado['comparacoes'][0]['anterior'] == 'v1'
    rq75.exportar([resultado], tmp_path, {'janela': resultado['janela']})
    with gzip.open(tmp_path / 'commits.csv.gz', 'rt', encoding='utf-8', newline='') as f:
        linhas = list(csv.DictReader(f))
    assert len(linhas) == 301 and linhas[0]['nome_completo'] == 'o/r'
    assert json.loads((tmp_path / 'resumo.json').read_text())['completos'] == 1


def test_compare_inacessivel_nao_e_sucesso():
    cliente = ClienteComTags(releases=[release('v2', '2026-02-01T00:00:00Z'),
                                      release('v1', '2025-09-01T00:00:00Z')], compares={('v1', 'v2'): 404})
    resultado = rq75.coletar_repositorio(cliente, 'o/r', '2025-10-01', '2026-09-30')
    assert not resultado['concluido']
    assert resultado['comparacoes'][0]['motivo'] == 'compare_indisponivel'


def test_primeira_release_nao_inventa_commits():
    resultado = rq75.coletar_repositorio(ClienteComTags(releases=[release('v1', '2026-01-01T00:00:00Z')]),
                                       'o/r', '2025-10-01', '2026-09-30')
    assert resultado['concluido']
    assert resultado['comparacoes'][0]['motivo'] == 'sem_release_anterior'
    assert resultado['commits'] == []


def test_autenticacao_nao_e_transformada_em_tag_ausente():
    import pytest
    cliente = Mock()
    cliente.paginar.return_value = iter([{'status': 200, 'corpo': [{'tag_name': 'v1', 'sha': 'a'}]}])
    cliente.get.side_effect = rq75.ErroAutenticacaoREST('401')
    with pytest.raises(rq75.ErroAutenticacaoREST):
        rq75.coletar_tags(cliente, 'o/r', '2025-10-01', '2026-09-30', [])


def test_compare_truncado_fica_incompleto():
    cliente = ClienteComTags(releases=[release('v2', '2026-02-01T00:00:00Z'),
                                      release('v1', '2025-09-01T00:00:00Z')],
                            compares={('v1', 'v2'): [commit_api(str(i), '2026-01-01T00:00:00Z') for i in range(150)]})
    resultado = rq75.coletar_repositorio(cliente, 'o/r', '2025-10-01', '2026-09-30', max_paginas=1)
    assert not resultado['concluido']
    assert resultado['comparacoes'][0]['motivo'] == 'compare_truncado'
    assert len(resultado['commits']) == 100


def test_cli_retoma_checkpoint_e_rejeita_outra_entrada(tmp_path, monkeypatch):
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({'janela': {'inicio': '2025-10-01', 'fim': '2026-09-30'}}))
    entrada = tmp_path / 'entrada.csv'
    entrada.write_text('nome_completo\no/r\n')
    saida = tmp_path / 'saida'
    monkeypatch.setattr(rq75, 'obter_token', lambda: 'teste')
    monkeypatch.setattr(rq75, 'ClienteREST', lambda *a: ClienteComTags())
    args = ['--config', str(config), '--entrada', str(entrada), '--saida', str(saida)]
    assert rq75.principal(args) == 0
    coleta = Mock(side_effect=AssertionError('nao deve repetir checkpoint completo'))
    monkeypatch.setattr(rq75, 'coletar_repositorio', coleta)
    assert rq75.principal(args) == 0
    coleta.assert_not_called()
    anterior = (saida / 'resumo.json').read_bytes()
    entrada.write_text('nome_completo\no/outro\n')
    assert rq75.principal(args) == 1
    assert (saida / 'resumo.json').read_bytes() == anterior
