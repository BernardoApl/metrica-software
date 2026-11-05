import json

import numpy as np
import pytest

from analise import rq104_gerador_simulacao as rq


@pytest.fixture(scope='module')
def parametros():
    return rq.carregar_parametros()


def pares_reais(parametros):
    return {(int(i), s, c) for e in parametros['estratos']
            for i, s, c in zip(e['par_id'], e['sem'], e['com'])}


def test_contrato_rq103_carregado(parametros):
    assert parametros['n'] == 30
    assert [e['quantidade'] for e in parametros['estratos']] == [15, 15]
    assert parametros['semente_sugerida'] == 104


def test_mesma_semente_reproduz_e_semente_diferente_muda(parametros):
    a = rq.gerar_amostra(parametros, 104)
    assert a == rq.gerar_amostra(parametros, 104)
    assert a != rq.gerar_amostra(parametros, 105)


def test_pares_completos_e_estratos_preservados(parametros):
    reais = pares_reais(parametros)
    linhas = rq.gerar_amostra(parametros, 104)
    assert len(linhas) == 30
    for r in linhas:
        assert (r['par_id_origem'], r['tempo_sem_cache_ms'], r['tempo_com_cache_ms']) in reais
        assert r['diferenca_ms'] == pytest.approx(r['tempo_sem_cache_ms'] - r['tempo_com_cache_ms'])
        assert not r['rotulos_trocados']
    assert sum(r['ordem_primeiro'] == 'sem_cache' for r in linhas) == 15


def test_lote_vetorizado(parametros):
    d = rq.gerar_lote(parametros, np.random.default_rng(1), 500)
    assert d['sem'].shape == (500, 30)
    assert np.all(d['diferenca'] > 0)  # na coleta real o cache sempre foi mais rápido
    assert np.all((d['estrato'] == 0).sum(axis=1) == 15)


def test_cenario_h0_troca_rotulos_e_centra_em_zero(parametros):
    d = rq.gerar_lote(parametros, np.random.default_rng(2), 4000, 'h0')
    assert 0.48 < d['trocado'].mean() < 0.52
    assert np.all(d['diferenca'][d['trocado']] < 0)
    assert np.all(d['sem'] > 0) and np.all(d['com'] > 0)
    # Simetria em torno de zero: média das diferenças próxima de 0 e metade negativas.
    assert abs(d['diferenca'].mean()) < 0.05
    assert 0.48 < (d['diferenca'] < 0).mean() < 0.52


def test_cenario_invalido(parametros):
    with pytest.raises(ValueError):
        rq.gerar_lote(parametros, np.random.default_rng(0), 1, 'outro')


def test_contrato_incompativel(tmp_path):
    p = json.loads(rq.PARAMETROS.read_text(encoding='utf-8'))
    p['metodo'] = 'normal'
    arq = tmp_path / 'p.json'
    arq.write_text(json.dumps(p), encoding='utf-8')
    with pytest.raises(ValueError):
        rq.carregar_parametros(arq)


def test_executar_grava_csv_e_manifesto(tmp_path):
    m = rq.executar(saida=tmp_path)
    assert set(m['cenarios']) == {'observado', 'h0'}
    sem, com = rq.ler_amostra(tmp_path / 'amostra_simulada_observado.csv')
    assert len(sem) == 30 and np.all(sem > com)
    assert rq.executar(saida=tmp_path) == m  # reexecução idêntica
