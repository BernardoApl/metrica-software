import json
import re
import shutil

import pytest

from frontend import rq111_g3 as rq111
from frontend import rq117_g3_q3 as rq


@pytest.fixture(scope='module')
def dados():
    return rq111.carregar(rq111.ENTRADA), rq.carregar_q3()


def test_grafico_tem_q1_e_as_tres_situacoes_da_q3(dados):
    q1, q3 = dados
    grupos = rq.situacoes(q1, q3)
    assert [g['rotulo'][0] for g in grupos] == ['Q1 · troca de rótulos', 'Q3 · amostra pequena',
                                                'Q3 · outliers 10% × 5', 'Q3 · assimetria']
    assert grupos[0]['testes']['t_pareado']['proporcao'] == q1['resultados']['t_pareado']['erro_tipo_i']
    assert grupos[1]['testes']['wilcoxon_pareado'] == rq.taxa(q3, 'base', 10, 'wilcoxon_pareado')


def test_svg_tem_titulo_eixos_referencia_e_cores_dos_testes(dados):
    svg = rq.grafico_situacoes(rq.situacoes(*dados))
    for trecho in ('Erro tipo I dos dois testes em cada situação simulada', 'Erro tipo I (% de amostras com p &lt; 0,05)',
                   'Situação simulada', '5% (α)', 'fill="#2a78d6"', 'fill="#eb6834"'):
        assert trecho in svg
    assert svg.count('<rect') == 8  # 4 situações × 2 testes


def test_altura_da_barra_corresponde_a_taxa(dados):
    svg = rq.grafico_situacoes(rq.situacoes(*dados))
    alturas = [float(h) for h in re.findall(r'<rect [^>]*height="([\d.]+)"', svg)]
    maior = max(rq.situacoes(*dados), key=lambda g: g['testes']['wilcoxon_pareado']['proporcao'])
    assert maior['rotulo'][0] == 'Q3 · assimetria'
    assert max(alturas) == alturas[-1]  # a última barra (Wilcoxon na assimetria) é a mais alta


def test_texto_cita_os_numeros_da_q3(dados):
    _, q3 = dados
    frase = rq.texto(q3)
    for situacao, n, teste in (('outliers', 30, 't_pareado'), ('assimetria', 10, 't_pareado'),
                               ('assimetria', 50, 'wilcoxon_pareado')):
        assert rq.pct(rq.taxa(q3, situacao, n, teste)['proporcao']) in frase
    assert 2 <= frase.count('. ') + 1 <= 5


def test_tabela_tem_uma_linha_por_ponto(dados):
    q1, q3 = dados
    html = rq.tabela(q1, q3)
    assert html.count('<tr>') == 1 + 3 * len(q3['n_pares'])


def test_executar_preenche_so_o_bloco_marcado(tmp_path):
    pagina = tmp_path / 'index.html'
    shutil.copy(rq.PAGINA, pagina)
    antes = pagina.read_text(encoding='utf-8')
    rq.executar(pagina=pagina)
    depois = pagina.read_text(encoding='utf-8')
    assert depois[:depois.index(rq.INICIO)] == antes[:antes.index(rq.INICIO)]
    assert depois[depois.index(rq.FIM):] == antes[antes.index(rq.FIM):]
    rq.executar(pagina=pagina)
    assert pagina.read_text(encoding='utf-8') == depois


def test_bloco_fica_na_secao_de_erro_tipo_i_depois_do_g3_da_q1():
    html = rq.PAGINA.read_text(encoding='utf-8')
    assert html.index('id="erro-tipo-i"') < html.index('<!-- G3:FIM -->') < html.index(rq.INICIO) < html.index('id="poder"')


def test_pagina_versionada_esta_atualizada(tmp_path):
    copia = tmp_path / 'index.html'
    shutil.copy(rq.PAGINA, copia)
    rq.executar(pagina=copia)
    assert copia.read_text(encoding='utf-8') == rq.PAGINA.read_text(encoding='utf-8')


@pytest.mark.parametrize('campo,valor', [('questao', 'Q1'), ('medida', 'poder')])
def test_entrada_errada_e_recusada(tmp_path, campo, valor):
    m = json.loads(rq.ENTRADA_Q3.read_text(encoding='utf-8'))
    m[campo] = valor
    caminho = tmp_path / 'r.json'
    caminho.write_text(json.dumps(m), encoding='utf-8')
    with pytest.raises(ValueError):
        rq.carregar_q3(caminho)


def test_marcadores_ausentes_falham():
    with pytest.raises(ValueError):
        rq.inserir('sem marcadores', 'x')
