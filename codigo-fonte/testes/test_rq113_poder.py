import json

import numpy as np
import pytest
from scipy import stats

from analise import rq104_gerador_simulacao as rq104
from analise import rq105_testes_pareados as rq105
from analise import rq113_poder as rq


@pytest.fixture(scope='module')
def parametros():
    return rq104.carregar_parametros()


def test_p_valores_vetorizados_iguais_aos_da_rq105():
    rng = np.random.default_rng(3)
    d = np.round(rng.normal(.3, 1, (5, 30)), 1)  # arredondar força empates
    p_t = rq.p_t_pareado(d)
    for i, linha in enumerate(d):
        assert p_t[i] == pytest.approx(stats.ttest_1samp(linha, 0).pvalue)
        r = rq105.teste_wilcoxon_pareado(linha, np.zeros(30))
        assert rq.p_wilcoxon(linha) == pytest.approx(r['p_valor'])


@pytest.mark.parametrize('cenario,n', [('base', 30), ('amostra_pequena', 10), ('outliers', 30), ('assimetria', 30)])
def test_cenarios_sob_h0(parametros, cenario, n):
    d, sigma = rq.amostras_h0(cenario, parametros, np.random.default_rng(1), 4000)
    assert d.shape == (4000, n)
    assert abs(d.mean()) < .05 * sigma  # média zero: H0 do t vale em todos os cenários
    assert d.std() == pytest.approx(sigma, rel=.08)
    if cenario == 'assimetria':
        assert stats.skew(d.ravel()) > 1 and np.median(d) < 0  # simetria violada
    else:
        assert abs(stats.skew(d.ravel())) < .3 and abs((d > 0).mean() - .5) < .02


def test_reprodutivel_e_independente_da_ordem(parametros):
    a = rq.simular_cenario('outliers', parametros, 200, efeitos=(0, .5))
    b = rq.simular_cenario('outliers', parametros, 200, efeitos=(0, .5))
    assert a == b


def test_poder_cresce_com_efeito(parametros):
    c = rq.simular_cenario('base', parametros, 400)
    for teste in rq.TESTES:
        poder = [p['testes'][teste]['0.05']['proporcao'] for p in c['pontos']]
        assert poder[0] < .1 and poder[-1] > .95
        assert all(b >= a - .05 for a, b in zip(poder, poder[1:]))
        assert all(p['testes'][teste]['0.01']['proporcao'] <= p['testes'][teste]['0.05']['proporcao']
                   for p in c['pontos'])
    assert c['pontos'][3]['delta_ms'] == pytest.approx(.3 * c['sigma_d_ms'])


def test_tamanho_para_poder_e_classificacao():
    assert rq.tamanho_para_poder([(0, .05), (.5, .6), (1, 1)]) == pytest.approx(.5 + .2 / .4 * .5)
    assert rq.tamanho_para_poder([(0, .05), (1, .5)]) is None
    assert rq.classificar_tipo_i([.06, .07]) == 'liberal'
    assert rq.classificar_tipo_i([.03, .045]) == 'conservador'
    assert rq.classificar_tipo_i([.045, .055]) == 'perto do nominal'


def test_executar_grava_saidas(tmp_path):
    m = rq.executar(tmp_path, repeticoes=60, cenarios=('base',))
    dados = json.loads((tmp_path / 'resultados.json').read_text(encoding='utf-8'))
    assert dados['cenarios']['base']['n_pares'] == 30 and 'base' in dados['leituras']
    linhas = (tmp_path / 'poder.csv').read_text(encoding='utf-8').splitlines()
    assert len(linhas) == 1 + len(rq.EFEITOS_DZ) * 2 * len(rq.ALFAS)
    assert m['resumo']['base']['mais_poderoso'] in ('t_pareado', 'wilcoxon_pareado', 'empate')
