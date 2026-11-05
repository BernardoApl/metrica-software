import math

import numpy as np
import pytest
from scipy import stats

from analise import rq105_testes_pareados as rq


@pytest.fixture(scope='module')
def resultados(tmp_path_factory):
    return rq.executar(saida=tmp_path_factory.mktemp('rq105'))


def test_t_pareado_confere_com_formula():
    sem = np.array([10., 12, 9, 14, 11, 13])
    com = np.array([9., 10, 9.5, 11, 10, 12])
    d = sem - com
    r = rq.teste_t_pareado(sem, com)
    t = d.mean() / (d.std(ddof=1) / math.sqrt(len(d)))
    assert r['estatistica'] == pytest.approx(t)
    assert r['p_valor'] == pytest.approx(2 * stats.t.sf(abs(t), 5))
    assert r['efeito_d_cohen_dz'] == pytest.approx(d.mean() / d.std(ddof=1))
    lo, hi = r['ic95_media_ms']
    assert lo < d.mean() < hi


def test_wilcoxon_sem_empates_igual_scipy_exato():
    rng = np.random.default_rng(7)
    sem = rng.lognormal(1, .5, 20)
    com = sem - rng.normal(.3, 1, 20)
    r = rq.teste_wilcoxon_pareado(sem, com)
    ref = stats.wilcoxon(sem, com, method='exact')
    assert r['p_valor'] == pytest.approx(ref.pvalue)
    assert r['w_scipy_min'] == pytest.approx(ref.statistic)
    assert r['estatistica'] + r['w_menos'] == 20 * 21 / 2


def test_distribuicao_nula_simetrica_e_tabela_n30():
    valores, prob = rq.distribuicao_nula_wplus(np.arange(1, 31))
    assert prob.sum() == pytest.approx(1)
    assert np.allclose(prob, prob[::-1])
    inferior, superior, nivel = rq.regiao_rejeicao_wplus(valores, prob)
    assert (inferior, superior) == (137, 328)  # valor crítico tabelado, n = 30, bilateral 5%
    assert nivel <= .05


def test_postos_medios_com_empates_e_zeros():
    r = rq.teste_wilcoxon_pareado([3, 3, 5, 2, 7, 1], [1, 1, 2, 2, 1, 2])
    assert r['zeros_descartados'] == 1 and r['n_efetivo'] == 5 and r['empates_em_abs_d']
    assert 'postos médios' in r['metodo']
    valores, prob = rq.distribuicao_nula_wplus([1.5, 1.5, 3, 4, 5])
    assert prob.sum() == pytest.approx(1)
    assert 6.5 in valores and 7.5 not in valores  # 1,5 + 5 é possível; 7,5 não


def test_hodges_lehmann():
    assert rq.hodges_lehmann([1, 2, 3]) == 2
    assert rq.hodges_lehmann([0, 0, 10]) == pytest.approx(2.5)


def test_entradas_invalidas():
    with pytest.raises(ValueError):
        rq.teste_t_pareado([1, 2], [1, 2])
    with pytest.raises(ValueError):
        rq.teste_t_pareado([1, 2, 3], [0, 1, 2])  # desvio das diferenças zero
    with pytest.raises(ValueError):
        rq.teste_wilcoxon_pareado([1, 2, 3], [1, 2, 3])


def test_resultados_das_tres_amostras(resultados):
    obs, h0, reais = resultados['simulada_observado'], resultados['simulada_h0'], resultados['reais']
    for r in (obs, reais):
        assert r['t_pareado']['rejeita_h0'] and r['wilcoxon_pareado']['rejeita_h0']
        assert r['wilcoxon_pareado']['estatistica'] == 465  # todas as diferenças positivas
        assert r['t_pareado']['media_diferenca_ms'] > 0
    assert reais['t_pareado']['estatistica'] == pytest.approx(24.93, abs=.01)
    assert not h0['t_pareado']['rejeita_h0'] and not h0['wilcoxon_pareado']['rejeita_h0']
    assert any('mesma conclusão' in f for f in reais['interpretacao'])
