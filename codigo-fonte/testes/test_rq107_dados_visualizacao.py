import json
from collections import Counter

import numpy as np
import pytest

from analise import rq107_dados_visualizacao as rq


@pytest.fixture(scope='module')
def parametros():
    return json.loads(rq.PARAMETROS.read_text(encoding='utf-8'))


@pytest.fixture
def sem_rq104(tmp_path):
    return tmp_path / 'nao_existe.csv'


def test_reamostragem_e_reprodutivel_e_muda_com_a_semente(parametros):
    assert rq.reamostrar_contrato_rq103(parametros) == rq.reamostrar_contrato_rq103(parametros)
    assert rq.reamostrar_contrato_rq103(parametros) != rq.reamostrar_contrato_rq103(parametros, semente=1)


def test_reamostragem_mantem_pares_completos_e_estratos(parametros):
    origem = {(p['tempo_sem_cache_ms'], p['tempo_com_cache_ms']): e['ordem_primeiro']
              for e in parametros['estratos'] for p in e['pares']}
    simulados = rq.reamostrar_contrato_rq103(parametros)
    assert len(simulados) == 30
    assert all(par in origem for par in simulados)
    assert Counter(origem[par] for par in simulados) == {'sem_cache': 15, 'com_cache': 15}


def test_processar_usa_coleta_real_e_declara_simulado_provisorio(sem_rq104):
    dados = rq.processar(caminho_rq104=sem_rq104)
    assert dados['origem_simulados'] == 'contrato_rq103_provisorio'
    assert (dados['pares_reais'], dados['pares_simulados']) == (30, 30)
    assert dados['series']['sem_cache']['real']['forma']['mediana'] == pytest.approx(5.6236475)
    assert dados['series']['com_cache']['real']['forma']['mediana'] == pytest.approx(0.495)
    assert dados['series']['diferenca']['real']['forma']['pares_fora_cercas_iqr'] == [1, 2, 3]


def test_simulados_da_rq104_tem_precedencia(tmp_path):
    csv = tmp_path / 'pares_simulados.csv'
    csv.write_text('par_id,tempo_sem_cache_ms,tempo_com_cache_ms\n1,5.0,0.0005\n2,7.0,0.0004\n3,6.0,0.0006\n', encoding='utf-8')
    dados = rq.processar(caminho_rq104=csv)
    assert dados['origem_simulados'] == 'rq104'
    assert dados['series']['sem_cache']['simulado']['valores'] == [5.0, 7.0, 6.0]
    assert dados['series']['com_cache']['simulado']['valores'] == pytest.approx([0.5, 0.4, 0.6])


@pytest.mark.parametrize('conteudo', [
    '',
    'a,b\n1,2\n',
    'tempo_sem_cache_ms,tempo_com_cache_ms\n-1,0.1\n',
    'tempo_sem_cache_ms,tempo_com_cache_ms\nnan,0.1\n',
])
def test_simulados_invalidos_sao_recusados(tmp_path, conteudo):
    csv = tmp_path / 'pares_simulados.csv'
    csv.write_text(conteudo, encoding='utf-8')
    with pytest.raises(ValueError):
        rq.ler_simulados(csv)


def test_parametros_de_outra_coleta_sao_recusados(parametros, sem_rq104):
    with pytest.raises(ValueError):
        rq.pares_simulados(parametros, 'outra_execucao', sem_rq104)


def test_histogramas_compartilham_classes_e_contam_todos_os_valores():
    real, simulado = np.array([1.0, 2.0, 3.0, 10.0]), np.array([0.0, 2.0, 12.0])
    h = rq.histogramas(real, simulado, classes=4)
    assert h['bordas'] == [0.0, 3.0, 6.0, 9.0, 12.0]
    assert sum(h['real']) == 4 and sum(h['simulado']) == 3


def test_forma_conta_extremos_e_assimetria_positiva():
    f = rq.forma(np.array([1.0, 2, 3, 4, 100]))
    assert f['pares_fora_cercas_iqr'] == [5]
    assert f['assimetria'] > 0
    assert (f['n'], f['mediana']) == (5, 3.0)


def test_saida_e_deterministica(tmp_path, sem_rq104):
    destino = tmp_path / 'sub' / 'dados.json'
    rq.executar(destino, caminho_rq104=sem_rq104)
    primeira = destino.read_bytes()
    rq.executar(destino, caminho_rq104=sem_rq104)
    assert destino.read_bytes() == primeira
