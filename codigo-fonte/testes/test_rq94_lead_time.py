import json

import pandas as pd
import pytest

from analise.rq94_lead_time import (REGRESSAO, SEM_VERSAO, SERIE_DIFERENTE, AVANCO, analisar, executar,
                                    relacao_com_anterior, versao_tag)


def release(nome, tag, anterior, lead, commits, negativos=0, motivo=None):
    return dict(nome_completo=nome, tag_name=tag, anterior=anterior, published_at='2026-01-10T00:00:00Z',
                commits=commits, commits_negativos=negativos, truncado='False', lead_time_dias=lead, motivo=motivo)


def releases_exemplo():
    return pd.DataFrame([
        release('org/a', 'v1.0.0', None, None, 0, motivo='sem_release_anterior'),
        release('org/a', 'v1.1.0', 'v1.0.0', 2., 3),
        release('org/a', 'v1.2.0', 'v1.1.0', 10., 5, negativos=1),
        release('org/a', 'v1.0.1', 'v1.2.0', 40., 2),
        release('org/b', 'v2.0.0', 'v1.9.0', 0.5, 1),
        release('org/b', 'v2.0.0', 'v2.0.0', None, 0, motivo='sem_commits_novos'),
    ])


def metricas_exemplo(**ajustes):
    linhas = [dict(nome_completo='org/a', linguagem='Python', releases_janela=4, lead_time_release_mediana_dias=10.,
                   lead_time_commit_mediana_dias=3., releases_com_lead_time=3, commits_com_lead_time=9,
                   releases_sem_anterior=1, releases_sem_commits=0, releases_compare_indisponivel=0,
                   releases_compare_truncado=0, commits_negativos=1, classe_lead_time='Medium'),
              dict(nome_completo='org/b', linguagem='Go', releases_janela=2, lead_time_release_mediana_dias=.5,
                   lead_time_commit_mediana_dias=.5, releases_com_lead_time=1, commits_com_lead_time=1,
                   releases_sem_anterior=0, releases_sem_commits=1, releases_compare_indisponivel=0,
                   releases_compare_truncado=0, commits_negativos=0, classe_lead_time='Elite')]
    for chave, valor in ajustes.items():
        linhas[0][chave] = valor
    return pd.DataFrame(linhas)


@pytest.mark.parametrize('anterior, atual, esperado', [
    ('v1.2.0', 'v1.3.0', AVANCO),
    ('v26.8.1.2041-lts', 'v26.7.5.10-stable', REGRESSAO),
    ('@tanstack/vue-query@5.1.0', '@tanstack/react-query@5.1.0', SERIE_DIFERENTE),
    ('nightly', 'v1.0.0', SEM_VERSAO),
    ('v2.0.0', 'v2.0.0', AVANCO),
])
def test_relacao_com_anterior(anterior, atual, esperado):
    assert relacao_com_anterior(anterior, atual) == esperado


def test_versao_tag_tolerante():
    assert versao_tag('4.6-stable') == ('', (4, 6))
    assert versao_tag('pkg==1.2.3') == ('pkg==', (1, 2, 3))
    assert versao_tag(None) is None


def test_variantes_classes_e_robustez():
    df, detalhes, est, classes, transicoes, resumo = analisar(metricas_exemplo(), releases_exemplo())
    a = df.set_index('nome_completo').loc['org/a']
    assert a.lead_time_a_dias == 10 and a.lead_time_b_dias == 3
    assert (a.classe_lead_time_a, a.classe_lead_time_b) == ('Medium', 'High')
    assert a.passos_classe_b_menos_a == 1 and bool(a.mudou_classe) and bool(a.b_menor_que_a)
    # v1.0.1 depois de v1.2.0 é backport: fora da robustez, a mediana de (2, 10) é 6.
    assert a.releases_linha_intercalada == 1
    assert a.lead_time_a_sem_intercaladas_dias == 6
    assert resumo['repositorios_b_igual_a'] == 1 and resumo['repositorios_mudam_de_classe'] == 1
    assert transicoes.loc['Medium', 'High'] == 1 and int(transicoes.to_numpy().sum()) == 2
    assert classes.groupby('variante').repositorios.sum().eq(2).all()
    assert len(detalhes) == 6 and resumo['commits_negativos'] == 1


def test_divergencia_da_variante_a_e_rejeitada():
    with pytest.raises(ValueError, match='lead_time_release_mediana_dias'):
        analisar(metricas_exemplo(lead_time_release_mediana_dias=11.), releases_exemplo())


def test_contagem_de_commits_divergente_e_rejeitada():
    with pytest.raises(ValueError, match='commits_com_lead_time'):
        analisar(metricas_exemplo(commits_com_lead_time=10), releases_exemplo())


def test_variante_b_acima_do_maximo_e_rejeitada():
    with pytest.raises(ValueError, match=r'\(b\)'):
        analisar(metricas_exemplo(lead_time_commit_mediana_dias=41.), releases_exemplo())


def test_entradas_invalidas():
    with pytest.raises(ValueError, match='ausentes'):
        analisar(metricas_exemplo().drop(columns='classe_lead_time'), releases_exemplo())
    duplicadas = pd.concat([releases_exemplo(), releases_exemplo().iloc[[1]]])
    with pytest.raises(ValueError, match='duplicados'):
        analisar(metricas_exemplo(), duplicadas)
    fora = pd.concat([releases_exemplo(), pd.DataFrame([release('org/z', 'v1', 'v0', 1., 1)])])
    with pytest.raises(ValueError, match='fora da amostra'):
        analisar(metricas_exemplo(), fora)


def test_executar_gera_saidas(tmp_path):
    entrada = tmp_path / 'entrada'
    entrada.mkdir()
    metricas_exemplo().to_csv(entrada / 'metricas_repositorios.csv', index=False)
    releases_exemplo().to_csv(entrada / 'lead_time_releases.csv', index=False)
    (entrada / 'resumo_execucao.json').write_text(json.dumps(
        {'config': {'janela': {'inicio': '2025-10-01', 'fim': '2026-09-30'}, 'janela_confirmada': False}}))
    saida = tmp_path / 'saida'
    resumo = executar(entrada, saida)
    for nome in ['repositorios.csv', 'releases.csv', 'estatisticas.csv', 'classes_dora.csv',
                 'transicoes_classes.csv', 'resumo.json', 'RELATORIO.md', 'lead_time_variantes.png',
                 'tamanho_release.svg']:
        assert (saida / nome).exists(), nome
    assert json.loads((saida / 'resumo.json').read_text(encoding='utf-8'))['repositorios'] == 2
    assert resumo['janela_confirmada'] is False
    assert 'ainda não confirmada' in (saida / 'RELATORIO.md').read_text(encoding='utf-8')
