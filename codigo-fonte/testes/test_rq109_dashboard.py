import shutil

import pytest

from frontend import rq109_dashboard as rq


@pytest.fixture
def pagina(tmp_path):
    destino = tmp_path / 'index.html'
    shutil.copy(rq.PAGINA, destino)
    return destino


def construir(pagina):
    pasta = pagina.parent
    return rq.construir(pagina, pasta / 'dados.json', pasta / 'graficos/g1.svg',
                        caminho_rq104=pasta / 'nao_existe.csv')


def test_links_do_repositorio_e_projects_ficam_antes_do_conteudo():
    html = rq.PAGINA.read_text(encoding='utf-8')
    conteudo = html.index('<main')
    for link in ('https://github.com/BernardoApl/metrica-software"',
                 'https://github.com/BernardoApl/metrica-software/projects"',
                 'Como abrir o dashboard'):
        assert html.index(link) < conteudo


def test_secoes_seguem_a_ordem_do_enunciado():
    html = rq.PAGINA.read_text(encoding='utf-8')
    ids = ['id="cenario"', 'id="protocolo"', 'id="pergunta"', 'id="hipoteses"', 'id="dados"', 'id="testes"']
    posicoes = [html.index(i) for i in ids]
    assert posicoes == sorted(posicoes)


def test_construir_preenche_g1_e_gera_grafico(pagina):
    assert construir(pagina) == 'contrato_rq103_provisorio'
    html = pagina.read_text(encoding='utf-8')
    assert (pagina.parent / 'graficos/g1.svg').exists()
    assert 'src="graficos/g1.svg"' in html and 'mediana de 5,62 ms' in html
    assert html.index('id="dados"') < html.index('graficos/g1.svg') < html.index('id="testes"')


def test_construir_e_idempotente(pagina):
    construir(pagina)
    primeira = pagina.read_bytes()
    svg = (pagina.parent / 'graficos/g1.svg').read_bytes()
    construir(pagina)
    assert pagina.read_bytes() == primeira
    assert (pagina.parent / 'graficos/g1.svg').read_bytes() == svg


def test_inserir_preserva_o_que_esta_fora_dos_marcadores():
    html = f'antes {rq.INICIO_G1}\nvelho\n{rq.FIM_G1} depois'
    novo = rq.inserir_g1(html, 'novo')
    assert novo == f'antes {rq.INICIO_G1}\nnovo\n{rq.FIM_G1} depois'


@pytest.mark.parametrize('html', ['sem marcadores', f'{rq.FIM_G1} {rq.INICIO_G1}'])
def test_marcadores_ausentes_ou_invertidos_falham(html):
    with pytest.raises(ValueError):
        rq.inserir_g1(html, 'x')


def test_pagina_versionada_esta_atualizada(tmp_path):
    """O index.html do repositório deve corresponder ao que o comando único gera."""
    copia = tmp_path / 'index.html'
    shutil.copy(rq.PAGINA, copia)
    rq.construir(copia, tmp_path / 'd.json', tmp_path / 'g1.svg', caminho_rq104=rq.rq107.SIMULADOS_RQ104)
    assert copia.read_text(encoding='utf-8') == rq.PAGINA.read_text(encoding='utf-8')
