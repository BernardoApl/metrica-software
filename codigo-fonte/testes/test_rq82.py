"""RQ82: consolidacao e retomada com dados sinteticos isolados."""
import copy
import json
from unittest.mock import Mock

import pytest
import pipeline_dora as pipeline
import rq82_amostra_final as rq82
from test_pipeline_dora import candidato


def config_final(tmp_path):
    return pipeline._mesclar(pipeline.CONFIG_PADRAO, {
        'meta_repositorios': 300, 'janela_confirmada': True,
        'limite_runs_por_repositorio': None, 'limite_paginas_compare': None,
        'diretorio_checkpoints': str(tmp_path / 'checkpoints')})


def avaliacao(nome):
    return dict(nome_completo=nome, motivo='incluido',
                metricas=dict(nome_completo=nome, releases_janela=5, runs_validos=50,
                              contribuidores_total=0, idade_anos=2),
                releases=[], runs=[], commits=[], tags=[], status_tags=200)


def resultado_com(n):
    a = [avaliacao(f'o/r{i}') for i in range(n)]
    return dict(amostra=[x['metricas'] for x in a], avaliacoes=a,
                funil=[{'aprovados': n}])


def test_meta_300_e_299_nao_e_final(tmp_path):
    config = config_final(tmp_path)
    assert rq82.validar_amostra(resultado_com(300), config)['amostra_final_validada']
    assert not rq82.validar_amostra(resultado_com(299), config)['amostra_final_validada']


def test_provisorio_truncado_duplicado_e_metadados_ausentes(tmp_path):
    config = dict(config_final(tmp_path), janela_confirmada=False)
    resultado = resultado_com(300)
    resultado['amostra'][1]['nome_completo'] = 'o/r0'
    resultado['amostra'][0]['contribuidores_total'] = None
    resultado['avaliacoes'][0]['metricas']['releases_compare_truncado'] = 1
    motivos = {p['motivo'] for p in rq82.validar_amostra(resultado, config)['pendencias']}
    assert {'janela_nao_confirmada', 'repositorios_duplicados', 'contribuidores_ausentes',
            'releases_compare_truncado'} <= motivos


def test_config_nao_relaxa_criterios_nem_trunca(tmp_path):
    config = config_final(tmp_path)
    rq82.validar_config(config)
    rq82.validar_config(dict(config, limite_runs_por_repositorio=20000))
    for mudanca in ({'meta_repositorios': 100}, {'limite_paginas_compare': 20},
                    {'limite_runs_por_repositorio': 49}, {'limite_runs_por_repositorio': True},
                    {'criterios': {'minimo_releases': 4, 'minimo_runs_validos': 50}},
                    {'janela': {'inicio': '2026-01-01', 'fim': '2026-01-02'}}):
        with pytest.raises(ValueError):
            rq82.validar_config(dict(config, **mudanca))


def test_checkpoint_reutiliza_e_isola_mudanca_de_contexto(tmp_path, monkeypatch):
    config = config_final(tmp_path)
    candidatos = [candidato('o/r0', 10000)]
    coleta = Mock(side_effect=lambda *a: copy.deepcopy(avaliacao('o/r0')))
    monkeypatch.setattr(pipeline, 'avaliar_repositorio', coleta)
    monkeypatch.setattr(rq82, 'coletar_tags', lambda *a: {'status': 200, 'tags': []})
    avaliar = rq82.criar_avaliador(config, candidatos)
    avaliar(None, candidatos[0], config)
    avaliar(None, candidatos[0], config)
    assert coleta.call_count == 1
    alterado = dict(config, janela_confirmada=False)
    rq82.criar_avaliador(alterado, candidatos)(None, candidatos[0], alterado)
    assert coleta.call_count == 2


def test_checkpoint_incompleto_e_retentado(tmp_path, monkeypatch):
    config = config_final(tmp_path)
    candidatos = [candidato('o/r0', 10000)]
    # Sem tags vindas do clone git, a RQ82 as busca pela API; aqui a API falha (403).
    sem_tags = lambda *a: {k: v for k, v in copy.deepcopy(avaliacao('o/r0')).items()
                           if k not in ('tags', 'status_tags')}
    coleta = Mock(side_effect=sem_tags)
    monkeypatch.setattr(pipeline, 'avaliar_repositorio', coleta)
    monkeypatch.setattr(rq82, 'coletar_tags', lambda *a: {'status': 403, 'tags': []})
    avaliar = rq82.criar_avaliador(config, candidatos)
    avaliar(None, candidatos[0], config)
    avaliar(None, candidatos[0], config)
    assert coleta.call_count == 2


def test_tags_do_clone_dispensam_a_consulta_pela_api(tmp_path, monkeypatch):
    config = config_final(tmp_path)
    candidatos = [candidato('o/r0', 10000)]
    monkeypatch.setattr(pipeline, 'avaliar_repositorio',
                        Mock(side_effect=lambda *a: copy.deepcopy(avaliacao('o/r0'))))
    api = Mock(side_effect=AssertionError('nao deveria consultar tags pela API'))
    monkeypatch.setattr(rq82, 'coletar_tags', api)
    rq82.criar_avaliador(config, candidatos)(None, candidatos[0], config)
    api.assert_not_called()


def test_execucao_consolida_300_e_exporta_sem_rede(tmp_path, monkeypatch):
    config = config_final(tmp_path)
    entrada = tmp_path / 'entrada.csv'
    entrada.write_text('nome_completo\no/r0\n')
    config['candidatos']['metadados'] = str(entrada)
    config['diretorio_saida'] = str(tmp_path / 'final')
    caminho = tmp_path / 'config.json'
    caminho.write_text(json.dumps(config))
    resultado = resultado_com(300)
    resultado.update(tags=[], releases=[], runs=[], commits=[], pre_filtrados=[])
    resultado['funil'] = [{'aprovados': 300, 'etapa': 'inicial'}, {'aprovados': 300, 'etapa': 'final'}]
    monkeypatch.setattr(rq82, 'obter_token', lambda: 'teste')
    monkeypatch.setattr(pipeline, 'criar_cliente', lambda *a: None)
    monkeypatch.setattr(pipeline, 'executar', lambda *a, **kw: resultado)
    assert rq82.principal(['--config', str(caminho)]) == 0
    auditoria = json.loads((tmp_path / 'final/validacao_rq82.json').read_text())
    assert auditoria['repositorios'] == 300
    assert auditoria['amostra_final_validada']
    assert (tmp_path / 'final/tags.csv').exists()


def test_auth_compare_interrompe_em_vez_de_ocultar(monkeypatch):
    from test_coleta_dora import release
    releases = [dict(release('v1', '2026-01-01T00:00:00Z'), dentro_janela=True),
                dict(release('v2', '2026-02-01T00:00:00Z'), dentro_janela=True)]
    monkeypatch.setattr(pipeline.coleta_dora, 'coletar_compare', Mock(side_effect=rq82.ErroAutenticacaoREST('401')))
    with pytest.raises(rq82.ErroAutenticacaoREST):
        pipeline.calcular_lead_time(None, 'o/r', releases, {})
