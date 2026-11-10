import copy

import pytest

from frontend import rq115_conclusao as rq


@pytest.fixture(scope='module')
def dados():
    return rq.carregar()


def resumo(t_poder, w_poder, t_i, w_i):
    return dict(mais_poderoso='t_pareado' if t_poder > w_poder else 'wilcoxon_pareado',
                erro_tipo_i=dict(t_pareado=t_i, wilcoxon_pareado=w_i))


def test_regra_de_recomendacao():
    assert rq.recomendar('x', {'x': resumo(.9, .7, .08, .22)}) == 't_pareado'
    assert rq.recomendar('x', {'x': resumo(.7, .9, .05, .05)}) == 'wilcoxon_pareado'
    # o mais poderoso é descartado se for liberal demais
    assert rq.recomendar('x', {'x': resumo(.7, .9, .05, .20)}) == 't_pareado'
    # os dois liberais: fica o de menor erro tipo I
    assert rq.recomendar('x', {'x': resumo(.9, .7, .30, .15)}) == 'wilcoxon_pareado'


def test_cenario_dos_dados():
    r = {'base': {}, 'outliers': {}, 'assimetria': {}}
    assert rq.cenario_dos_dados(1.94, r) == 'assimetria'
    assert rq.cenario_dos_dados(-1.2, r) == 'assimetria'
    assert rq.cenario_dos_dados(.3, r) == 'outliers'
    assert rq.cenario_dos_dados(.3, {'base': {}}) == 'base'


def test_secao_com_dados_reais_e_simulados(dados):
    c = rq.montar(dados)
    assert c['cenario'] == 'assimetria' and c['recomendado'] == 't_pareado' and not c['acertou']
    html = rq.fragmento(dados)
    for trecho in ('Antes de simular', 'O que encontramos', 'Quando a escolha mudaria', 'Principal limitação',
                   't(29) = 24,93', 'W+ = 465;', '5,44%', '5,26%', 'Usar o t pareado neste cenário', '12.000 vezes'):
        assert trecho in html
    assert 'confirmou a expectativa só em parte' in html


def test_texto_muda_com_os_numeros(dados):
    d = copy.deepcopy(dados)
    d['q2']['resumo']['assimetria'].update(mais_poderoso='wilcoxon_pareado',
                                           erro_tipo_i=dict(t_pareado=.05, wilcoxon_pareado=.05))
    c = rq.montar(d)
    assert c['recomendado'] == 'wilcoxon_pareado' and c['acertou']
    assert 'A simulação <strong>confirmou</strong>' in rq.fragmento(d)


def test_executar_so_troca_o_bloco(tmp_path):
    pagina = tmp_path / 'index.html'
    pagina.write_text(f'antes {rq.INICIO}\nvelho\n{rq.FIM} depois', encoding='utf-8')
    rq.executar(pagina)
    texto = pagina.read_text(encoding='utf-8')
    assert texto.startswith('antes ') and texto.endswith(' depois') and 'velho' not in texto
    pagina.write_text('sem marcadores', encoding='utf-8')
    with pytest.raises(ValueError):
        rq.executar(pagina)
