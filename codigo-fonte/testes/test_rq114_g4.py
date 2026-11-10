import copy
import json

import pytest

from frontend import rq114_g4 as rq


@pytest.fixture(scope='module')
def m():
    return rq.carregar(rq.ENTRADA)


def test_quatro_paineis_com_cores_fixas_e_eixos(m):
    html = rq.fragmento(m)
    assert html.count('<svg class="g4-svg"') == len(m['cenarios']) == 4
    assert html.count('stroke="#2a78d6"') == html.count('stroke="#eb6834"') == 2 * 4  # α 0,05 e 0,01 por painel
    assert 'Rejeições de H0 (%)' in html and 'Tamanho do efeito d' in html
    assert html.count('class="g4-ponto"') == 4 * 2 * len(m['efeitos_dz'])
    assert '80%' in html and '5%' in html


def test_texto_e_tabela_vem_dos_numeros(m):
    html = rq.fragmento(m)
    r = m['resumo']['assimetria']['erro_tipo_i']['wilcoxon_pareado']
    assert rq.pct(r) in html
    m2 = copy.deepcopy(m)
    m2['resumo']['base']['mais_poderoso'] = 't_pareado'
    assert 'o t pareado detecta melhor' in rq.texto(m2) and 'inflam o desvio' not in rq.texto(m2)


def test_proporcao_inconsistente_bloqueia_grafico(m, tmp_path):
    ruim = copy.deepcopy(m)
    ruim['cenarios']['base']['pontos'][1]['testes']['t_pareado']['0.05']['proporcao'] = .99
    p = tmp_path / 'r.json'
    p.write_text(json.dumps(ruim), encoding='utf-8')
    with pytest.raises(ValueError, match='inconsistente'):
        rq.carregar(p)


def test_executar_so_troca_o_bloco(tmp_path):
    pagina = tmp_path / 'index.html'
    pagina.write_text(f'antes {rq.INICIO}\nvelho\n{rq.FIM} depois', encoding='utf-8')
    rq.executar(pagina=pagina)
    texto = pagina.read_text(encoding='utf-8')
    assert texto.startswith('antes ') and texto.endswith(' depois') and 'velho' not in texto
    pagina.write_text('sem marcadores', encoding='utf-8')
    with pytest.raises(ValueError):
        rq.executar(pagina=pagina)
