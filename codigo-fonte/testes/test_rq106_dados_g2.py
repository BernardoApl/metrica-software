import json

import numpy as np
import pytest

from analise import rq106_dados_g2 as rq


@pytest.fixture(scope='module')
def dados(tmp_path_factory):
    saida = tmp_path_factory.mktemp('g2') / 'g2.js'
    rq.executar(saida)
    texto = saida.read_text(encoding='utf-8')
    assert texto.splitlines()[1].startswith('window.G2_DADOS = ')
    return json.loads(texto.split('window.G2_DADOS = ', 1)[1].rstrip().rstrip(';'))


def test_tres_amostras(dados):
    assert list(dados['amostras']) == ['simulada_h0', 'simulada_observado', 'reais']
    assert dados['alfa'] == 0.05


def test_area_do_p_valor_bate_com_rq105(dados):
    for a in dados['amostras'].values():
        w = a['wilcoxon']
        v, p = np.array(w['valores']), np.array(w['probabilidade'])
        assert p.sum() == pytest.approx(1, abs=1e-4)
        baixo, alto = sorted((w['observado'], w['espelho']))
        area = p[(v <= baixo + 1e-9) | (v >= alto - 1e-9)].sum()
        assert area == pytest.approx(min(1, w['p_valor']), rel=1e-3, abs=1e-8)
        assert p[(v <= w['limite_inferior']) | (v >= w['limite_superior'])].sum() <= 0.05 + 1e-6


def test_curva_t(dados):
    t = dados['amostras']['simulada_h0']['t']
    x, y = np.array(t['x']), np.array(t['densidade'])
    assert t['gl'] == 29 and t['critico'] == pytest.approx(2.0452, abs=1e-4)
    assert np.trapezoid(y, x) == pytest.approx(1, abs=1e-3)
    assert not t['rejeita_h0'] and abs(t['observado']) < t['critico']
    assert dados['amostras']['reais']['t']['observado'] > x.max()  # fora do eixo, indicado na borda
