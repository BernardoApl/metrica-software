import re
import shutil

import pytest

from frontend import rq117_quadro as rq

JS = rq.PAGINA.with_name('quadro.js')


@pytest.fixture(scope='module')
def blocos():
    d = rq.carregar()
    return rq.destaques(d['g1'], d['conclusao'], d['q1'], d['q3'], d['q2'])


def test_uma_pergunta_e_dois_ou_tres_numeros_por_secao(blocos):
    assert list(blocos) == list(rq.SECOES)
    for html in blocos.values():
        assert html.count('class="quadro-pergunta"') == 1
        assert 2 <= html.count('class="quadro-numero"') <= 3


def test_numeros_vem_dos_resultados_salvos(blocos):
    assert '5,62 ms' in blocos['dados'] and '0,49 µs' in blocos['dados']
    assert '8,3%' in blocos['erro-tipo-i'] and '21,6%' in blocos['erro-tipo-i']
    assert '3,9 × 10⁻²¹' in blocos['resultados-reais']
    assert 't pareado' in re.search(r'quadro-valor">([^<]+)', blocos['conclusao']).group(1)


@pytest.mark.parametrize('p,texto', [(3.893e-21, '3,9 × 10⁻²¹'), (1.86e-09, '1,9 × 10⁻⁹'), (0.0123, '1,2 × 10⁻²')])
def test_potencia_dez(p, texto):
    assert rq.potencia_dez(p) == texto


def test_cor_de_cada_teste_e_a_mesma_dos_graficos(blocos):
    for html in blocos.values():
        for teste, cor in rq.COR.items():
            if f'background:{cor}' in html:
                assert cor in ('var(--cor-t)', 'var(--cor-w)')
    assert 'var(--cor-t)' in blocos['erro-tipo-i'] and 'var(--cor-w)' in blocos['erro-tipo-i']


def test_executar_e_idempotente_e_nao_mexe_fora_dos_marcadores(tmp_path):
    pagina = tmp_path / 'index.html'
    shutil.copy(rq.PAGINA, pagina)
    rq.executar(pagina)
    primeira = pagina.read_text(encoding='utf-8')
    rq.executar(pagina)
    assert pagina.read_text(encoding='utf-8') == primeira
    sem_blocos = lambda h: re.sub(r'(<!-- QUADRO:[^:]+:INICIO[^>]*-->).*?(<!-- QUADRO:)', r'\1\2', h, flags=re.S)
    assert sem_blocos(primeira) == sem_blocos(rq.PAGINA.read_text(encoding='utf-8'))


def test_pagina_versionada_esta_atualizada(tmp_path):
    copia = tmp_path / 'index.html'
    shutil.copy(rq.PAGINA, copia)
    rq.executar(copia)
    assert copia.read_text(encoding='utf-8') == rq.PAGINA.read_text(encoding='utf-8')


def test_destaque_fica_logo_no_inicio_de_cada_secao():
    html = rq.PAGINA.read_text(encoding='utf-8')
    for secao in rq.SECOES:
        inicio, _ = rq.marcadores(secao)
        abertura = html.index(f'<section id="{secao}"')
        proxima = html.find('<section', abertura + 1)
        assert abertura < html.index(inicio) < (proxima if proxima > 0 else len(html))


def test_pagina_carrega_o_script_e_o_script_cobre_as_15_perguntas():
    assert '<script src="quadro.js"></script>' in rq.PAGINA.read_text(encoding='utf-8')
    js = JS.read_text(encoding='utf-8')
    perguntas = re.search(r'const PERGUNTAS = \[(.*?)\n  \];', js, re.S).group(1)
    assert len(re.findall(r"^\s*\['", perguntas, re.M)) == 15
    for secao in rq.SECOES:
        assert f"'{secao}'" in js


def test_marcadores_ausentes_falham():
    with pytest.raises(ValueError):
        rq.inserir('sem marcadores', 'dados', 'x')
