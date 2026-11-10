import copy

from frontend import rq111_g3 as rq


def test_grafico_reflete_resultados_e_intervalos():
    m = rq.carregar(rq.ENTRADA)
    html = rq.fragmento(m)
    assert '5,44%' in html and '5,26%' in html
    assert '544 / 10000' in html and '526 / 10000' in html
    assert '5,0035%' in html
    assert 'stroke-dasharray="6 4"' in html
    assert 'aria-labelledby="g3-svg-titulo g3-svg-desc"' in html


def test_interpretacao_atualiza_com_os_dados():
    m = copy.deepcopy(rq.carregar(rq.ENTRADA))
    m['resultados']['t_pareado'].update(erro_tipo_i=.04, rejeicoes_h0=400, ic95_clopper_pearson=[.03, .05])
    html = rq.fragmento(m)
    assert '4,00%' in html
    assert 't pareado: o IC 95% contém' in html
    assert 't pareado: o IC 95% não contém' not in html
