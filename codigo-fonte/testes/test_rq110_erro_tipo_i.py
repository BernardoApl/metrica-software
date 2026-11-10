import csv
import json

import numpy as np
import pytest
from scipy import stats

from analise import rq110_erro_tipo_i as rq


def test_denominador_decisao_estrita_e_intervalo():
    linhas = [{f'{t}_{k}': v for t in rq.TESTES for k, v in
               [('status', 'ok'), ('p', p)]} for p in [.001, .05, .9, .5]]
    r = rq.resumir(linhas, .05)['t_pareado']
    assert r['rejeicoes_h0'] == 1
    assert r['erro_tipo_i'] == .25
    ic = stats.binomtest(1, 4).proportion_ci(method='exact')
    assert r['ic95_clopper_pearson'] == [ic.low, ic.high]
    linhas[0]['t_pareado_status'] = 'erro'
    r = rq.resumir(linhas, .05)
    assert r['t_pareado']['falhas'] == 1
    assert r['t_pareado']['erro_tipo_i'] is None
    assert r['wilcoxon_pareado']['erro_tipo_i'] == .25


def test_reproduz_mesmas_amostras_h0_e_testes():
    p = rq.rq104.carregar_parametros()
    linhas, resumo = rq.simular(p, 12, 110)
    assert (linhas, resumo) == rq.simular(p, 12, 110)
    assert linhas != rq.simular(p, 12, 111)[0]
    lote = rq.rq104.gerar_lote(p, np.random.default_rng(110), 12, 'h0')
    for i, linha in enumerate(linhas):
        sem, com = lote['sem'][i], lote['com'][i]
        assert linha['t_pareado_p'] == pytest.approx(stats.ttest_rel(sem, com).pvalue)
        esperado = rq.rq105.teste_wilcoxon_pareado(sem, com)
        assert linha['wilcoxon_pareado_p'] == esperado['p_valor']
        assert linha['media_diferenca_ms'] == lote['diferenca'][i].mean()
    assert all(r['repeticoes_validas'] == 12 for r in resumo.values())


@pytest.mark.parametrize('kwargs', [dict(repeticoes=0), dict(repeticoes=1.5), dict(repeticoes=True),
    dict(semente=-1), dict(semente=True), dict(alfa=0), dict(alfa=1), dict(alfa=float('nan'))])
def test_argumentos_invalidos(kwargs):
    with pytest.raises(ValueError):
        rq.simular(rq.rq104.carregar_parametros(), **kwargs)


def test_falha_estatistica_nao_vira_nao_rejeicao(monkeypatch):
    def falhar(*args):
        raise ValueError('falha controlada')
    monkeypatch.setattr(rq.rq105, 'teste_t_pareado', falhar)
    linhas, r = rq.simular(rq.rq104.carregar_parametros(), 3)
    assert r['t_pareado']['falhas'] == 3
    assert r['t_pareado']['erro_tipo_i'] is None
    assert linhas[0]['t_pareado_rejeita_h0'] is None
    assert r['wilcoxon_pareado']['repeticoes_validas'] == 3


def test_exportacao_hashes_e_preservacao(tmp_path):
    m = rq.executar(saida=tmp_path, repeticoes=5)
    assert m['status'] == 'concluida'
    for nome, h in m['artefatos_sha256'].items():
        assert rq.hash_arquivo(tmp_path / nome) == h
    with (tmp_path / 'repeticoes.csv').open() as f:
        assert len(list(csv.DictReader(f))) == 5
    assert json.loads((tmp_path / 'resultados.json').read_text(encoding='utf-8')) == m
    with pytest.raises(ValueError, match='não vazia'):
        rq.executar(saida=tmp_path, repeticoes=5)
