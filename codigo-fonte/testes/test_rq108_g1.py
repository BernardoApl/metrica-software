import json

import pytest
from matplotlib.colors import to_hex

from analise import rq107_dados_visualizacao as rq107
from frontend import rq108_g1 as rq


@pytest.fixture(scope='module')
def dados_json(tmp_path_factory):
    caminho = tmp_path_factory.mktemp('rq108') / 'dados.json'
    rq107.executar(caminho, caminho_rq104=caminho.parent / 'nao_existe.csv')
    return caminho


def test_svg_tem_titulo_eixos_com_unidade_e_legenda(dados_json, tmp_path):
    svg = rq.executar(dados_json, tmp_path / 'g1.svg').read_text(encoding='utf-8')
    for texto in ('G1. Tempos reais e simulados', 'Frequência (nº de pares)',
                  'Tempo por operação sem cache (ms)', 'Tempo por operação com cache (µs)',
                  'Dados reais (30 pares)', 'Dados simulados (30 pares)',
                  'pares 1, 2, 3'):
        assert texto in svg


def test_seis_paineis_com_uma_cor_por_origem(dados_json):
    fig = rq.desenhar_g1(json.loads(dados_json.read_text(encoding='utf-8')))
    assert len(fig.axes) == 6
    assert all(len(eixo.patches) == 12 for eixo in fig.axes)
    for eixo, cor in zip(fig.axes, (rq.COR_REAL, rq.COR_SIMULADO) * 3):
        assert all(to_hex(barra.get_facecolor()) == cor for barra in eixo.patches)
    # Mesma linha, mesma escala: real e simulado são comparáveis barra a barra.
    for real, simulado in zip(fig.axes[::2], fig.axes[1::2]):
        assert real.get_xlim() == simulado.get_xlim()
        assert real.get_ylim() == simulado.get_ylim()


def test_barras_desenham_as_contagens_do_backend(dados_json):
    dados = json.loads(dados_json.read_text(encoding='utf-8'))
    fig = rq.desenhar_g1(dados)
    h = dados['series']['sem_cache']['histograma']
    assert [p.get_height() for p in fig.axes[0].patches] == h['real']
    assert [p.get_height() for p in fig.axes[1].patches] == h['simulado']


def test_svg_e_reprodutivel(dados_json, tmp_path):
    a = rq.executar(dados_json, tmp_path / 'a.svg').read_bytes()
    b = rq.executar(dados_json, tmp_path / 'b.svg').read_bytes()
    assert a == b


def test_dados_ausentes_falham(tmp_path):
    with pytest.raises(OSError):
        rq.executar(tmp_path / 'nao_existe.json', tmp_path / 'g1.svg')


def test_fragmento_traz_numeros_do_json_e_tabela(dados_json):
    dados = json.loads(dados_json.read_text(encoding='utf-8'))
    html = rq.fragmento_html(dados)
    assert 'mediana de 5,62 ms' in html and 'pares 1, 2, 3' in html
    assert '11.000 vezes' in html
    assert html.count('<tr>') == 7  # cabeçalho + real e simulado das três séries
    assert 'provisórios' in html


def test_fragmento_sem_aviso_quando_simulados_sao_da_rq104(dados_json):
    dados = json.loads(dados_json.read_text(encoding='utf-8'))
    dados['origem_simulados'] = 'rq104'
    assert 'provisórios' not in rq.fragmento_html(dados)
