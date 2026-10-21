import json

import pandas as pd
import pytest

from analise.rq95_estatisticas_c1 import analisar, estatisticas, executar, nota_mediana


def repo(nome, freq, lead, cfr, rec, classes, geral, lead_b=1.):
    f, l, c, r = classes
    return dict(nome_completo=nome, linguagem='Python', frequencia_deploy_semana=freq,
                lead_time_release_mediana_dias=lead, lead_time_commit_mediana_dias=lead_b, cfr_ci=cfr,
                recuperacao_mediana_horas=rec, classe_frequencia=f, classe_lead_time=l, classe_cfr=c,
                classe_recuperacao=r, classe_geral=geral)


def metricas_exemplo():
    return pd.DataFrame([
        # notas 4, 4, 4, 3 -> mediana 4 -> Elite
        repo('org/a', 8., .5, .1, 2., ('Elite', 'Elite', 'Elite', 'High'), 'Elite'),
        # notas 2, 1, 4, 3 -> mediana 2,5 -> arredonda para Medium
        repo('org/b', .5, 40., .05, 3., ('Medium', 'Low', 'Elite', 'High'), 'Medium'),
        # recuperação indefinida -> geral vazia
        repo('org/c', .1, 10., .5, None, ('Low', 'Medium', 'Low', None), None),
    ])


def test_estatisticas_e_indefinidos():
    e = estatisticas([1., 2., 3., 4., None])
    assert (e['n'], e['indefinidos'], e['mediana'], e['q1'], e['q3'], e['iqr']) == (4, 1, 2.5, 1.75, 3.25, 1.5)
    assert estatisticas([None])['mediana'] is None
    assert nota_mediana([2, 1, 4, 3]) == 2.5


def test_classificacao_c1_arredondamento_e_indefinida():
    repos, est, classes, perfis, combinacoes, resumo = analisar(metricas_exemplo())
    r = repos.set_index('nome_completo')
    assert r.loc['org/b', 'mediana_notas'] == 2.5 and bool(r.loc['org/b', 'arredondado'])
    assert pd.isna(r.loc['org/c', 'classe_geral'])
    assert r.loc['org/c', 'classe_geral_metricas_definidas'] == 'Low'  # notas 1, 2, 1
    assert resumo['classe_geral_indefinida'] == 1 and resumo['arredondados_para_baixo'] == 1
    assert resumo['motivo_indefinida']['classe_recuperacao'] == 1
    assert (r.loc['org/a', 'perfil_velocidade'], r.loc['org/b', 'perfil_velocidade']) == ('alto', 'baixo')
    assert pd.isna(r.loc['org/c', 'perfil_estabilidade'])
    assert int(perfis.to_numpy().sum()) == 2
    geral = classes.loc[classes.metrica == 'classe_geral'].set_index('classe').repositorios
    assert geral['Indefinida'] == 1 and geral.sum() == 3
    assert est.set_index('metrica').loc['recuperacao_mediana_horas', 'indefinidos'] == 1
    assert set(combinacoes.combinacao) == {'E/E/E/H', 'M/L/E/H'}


def test_classe_exportada_divergente_e_rejeitada():
    m = metricas_exemplo()
    m.loc[1, 'classe_geral'] = 'High'
    with pytest.raises(ValueError, match='org/b: classe_geral'):
        analisar(m)


def test_entradas_invalidas():
    with pytest.raises(ValueError, match='ausentes'):
        analisar(metricas_exemplo().drop(columns='cfr_ci'))
    with pytest.raises(ValueError, match='duplicados'):
        analisar(pd.concat([metricas_exemplo(), metricas_exemplo().iloc[[0]]]))
    m = metricas_exemplo()
    m.loc[0, 'cfr_ci'] = 1.5
    with pytest.raises(ValueError, match='CFR'):
        analisar(m)


def test_sensibilidade_rq92():
    rq92 = pd.DataFrame({'nome_completo': ['org/a', 'org/b', 'org/c'],
                         'recuperacao_mediana_horas': [2., 30., None]})
    repos, *_, resumo = analisar(metricas_exemplo(), rq92)
    s = resumo['sensibilidade_corte_rq92']
    assert s == dict(recuperacao_alterada=1, classe_recuperacao_alterada=1, classe_geral_alterada=0)
    assert repos.set_index('nome_completo').loc['org/b', 'classe_recuperacao_rq92'] == 'Medium'
    with pytest.raises(ValueError, match='diferentes'):
        analisar(metricas_exemplo(), rq92.iloc[:2])


def test_executar_gera_saidas(tmp_path):
    entrada = tmp_path / 'entrada'
    entrada.mkdir()
    metricas_exemplo().to_csv(entrada / 'metricas_repositorios.csv', index=False)
    (entrada / 'resumo_execucao.json').write_text(json.dumps(
        {'config': {'janela': {'inicio': '2025-10-01', 'fim': '2026-09-30'}, 'janela_confirmada': False}}))
    saida = tmp_path / 'saida'
    resumo = executar(entrada, saida, tmp_path / 'nao_existe.csv')
    for nome in ['repositorios_c1.csv', 'estatisticas_descritivas.csv', 'classes_c1.csv', 'combinacoes_classes.csv',
                 'perfis_velocidade_estabilidade.csv', 'resumo.json', 'RELATORIO.md', 'distribuicoes_c1.png',
                 'classes_c1.svg']:
        assert (saida / nome).exists(), nome
    assert resumo['sensibilidade_corte_rq92'] is None
    texto = (saida / 'RELATORIO.md').read_text(encoding='utf-8')
    assert 'ainda não confirmada' in texto and 'não foi encontrada' in texto
    assert json.loads((saida / 'resumo.json').read_text(encoding='utf-8'))['repositorios'] == 3
