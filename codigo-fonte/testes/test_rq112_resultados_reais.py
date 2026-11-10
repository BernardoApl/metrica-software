import copy

from frontend import rq112_resultados_reais as rq


def test_resultados_reais_sem_arredondar_p_para_zero():
    d = rq.carregar()
    html = rq.fragmento(d)
    assert d['resultados']['n_pares'] == 30
    assert '3,89e-21' in html and '1,86e-09' in html
    assert '24,927' in html and '465,0' in html
    assert '4,551' in html and '1,000' in html
    assert '0,000491 ms' in html
    assert html.count('data-label="Decisão">Rejeita H0</td>') == 2


def test_decisao_e_origem_nao_sao_textos_fixos():
    d = copy.deepcopy(rq.carregar())
    d['resultados']['t_pareado'].update(p_valor=.6, rejeita_h0=False)
    d['origem'] = '<script>teste</script>'
    html = rq.fragmento(d)
    assert 'data-label="Decisão">Não rejeita H0</td>' in html
    assert '0,6000' in html
    assert '<script>' not in html
    assert '&lt;script&gt;' in html
