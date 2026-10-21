"""Casos sintéticos independentes da coleta real da RQ91."""
import pandas as pd
import pytest

from analise.rq91_deployment_frequency import analisar, complementar


def fixture_janela():
    metricas = pd.DataFrame({
        'nome_completo': ['org/a', 'org/b'], 'linguagem': ['Python', 'Go'],
        'releases_janela': [2, 0], 'frequencia_deploy_semana': [2., 0.],
        'classe_frequencia': ['High', 'Low'],
    })
    releases = pd.DataFrame([
        ['org/a', 1, False, False, '2026-01-01T00:00:00Z'],
        ['org/a', 2, False, False, '2026-01-07T23:59:59.999Z'],
        ['org/a', 3, False, False, '2026-01-08T00:00:00Z'],
        ['org/a', 4, False, True, '2026-01-04T00:00:00Z'],
        ['org/a', 5, True, False, None],
        ['org/a', 6, False, False, '2025-12-31T23:59:59Z'],
    ], columns=['nome_completo', 'id', 'draft', 'prerelease', 'published_at'])
    return metricas, releases


def test_filtros_fronteiras_quartis_e_classe_ausente():
    m, r = fixture_janela()
    df, classes, resumo = analisar(m, r, '2026-01-01', '2026-01-07')
    assert df.releases_janela.tolist() == [2, 0]
    assert resumo['semanas'] == 1
    assert resumo['mediana'] == 1
    assert resumo['q1'] == .5 and resumo['q3'] == 1.5 and resumo['iqr'] == 1
    assert classes.repositorios.tolist() == [0, 1, 0, 1]
    assert classes.percentual.sum() == 100
    assert resumo['auditoria'] == {
        'linhas_releases': 6, 'drafts_excluidos': 1, 'prereleases_excluidas': 1,
        'fora_janela_excluidas': 2, 'releases_incluidas': 2,
        'contagens_frequencias_classes_reconciliadas': True,
    }


@pytest.mark.parametrize('erro', ['duplicata', 'data', 'booleano', 'contagem', 'frequencia', 'classe'])
def test_rejeita_dados_inconsistentes(erro):
    m, r = fixture_janela()
    if erro == 'duplicata':
        r = pd.concat([r, r.iloc[[0]]], ignore_index=True)
    elif erro == 'data':
        r.loc[0, 'published_at'] = None
    elif erro == 'booleano':
        r['draft'] = r.draft.astype(object)
        r.loc[0, 'draft'] = 'talvez'
    elif erro == 'contagem':
        m.loc[0, 'releases_janela'] = 3
    elif erro == 'frequencia':
        m.loc[0, 'frequencia_deploy_semana'] = float('nan')
    else:
        m.loc[0, 'classe_frequencia'] = 'Elite'
    with pytest.raises(ValueError):
        analisar(m, r, '2026-01-01', '2026-01-07')


def test_mes_medio_e_arredondamento_nao_mudam_categoria():
    m, r = fixture_janela()
    # 12 releases/365 dias ultrapassam 1 por mês médio (365,25/12).
    m = m.iloc[[0]].copy()
    r = pd.concat([r.iloc[[0]]]*12, ignore_index=True)
    r['id'] = range(12)
    m['releases_janela'] = 12
    m['frequencia_deploy_semana'] = .230137
    m['classe_frequencia'] = 'Medium'
    df, _, _ = analisar(m, r, '2026-01-01', '2026-12-31')
    assert df.classe_frequencia.iloc[0] == 'Medium'
    assert df.frequencia_deploy_semana.iloc[0] == pytest.approx(12*7/365)


def test_painel_inclui_zeros_e_normaliza_mes_parcial():
    df = pd.DataFrame({'nome_completo': ['org/a','org/b','org/c'],
                       'releases_janela': [6,1,0], 'frequencia_deploy_semana': [6*7/33,7/33,0]})
    r = pd.DataFrame([
        ['org/a', False, False, '2026-01-15T12:00:00Z']
    ]*4 + [
        ['org/a', False, False, '2026-02-02T23:59:59Z']
    ]*2 + [
        ['org/b', False, False, '2026-01-31T12:00:00Z'],
        ['org/a', False, True, '2026-02-02T12:00:00Z'],
        ['org/a', False, False, '2026-02-03T00:00:00Z'],
    ], columns=['nome_completo','draft','prerelease','published_at'])
    ranking, painel, meses, c = complementar(df, r, '2026-01-01','2026-02-02')
    assert len(painel) == 6 and painel.releases.sum() == 7
    assert meses.releases.tolist() == [5,2]
    assert meses.dias_observados.tolist() == [31,2]
    assert meses.repositorios_sem_release.tolist() == [1,2]
    assert meses.mediana.tolist() == pytest.approx([7/31,0])
    fevereiro = painel.query("nome_completo == 'org/a' and mes == '2026-02'").iloc[0]
    assert fevereiro.frequencia_semana == 7
    assert c['top_10pct_quantidade'] == 1
    assert c['top_10pct_participacao_percentual'] == pytest.approx(600/7)
    assert ranking.participacao_releases_percentual.sum() == pytest.approx(100)


def test_concentracao_empates_e_amostra_sem_releases():
    df = pd.DataFrame({'nome_completo':['z/a','a/b'], 'releases_janela':[0,0],
                       'frequencia_deploy_semana':[0.,0.]})
    r = pd.DataFrame(columns=['nome_completo','draft','prerelease','published_at'])
    ranking, painel, meses, c = complementar(df, r, '2026-02-01','2026-02-28')
    assert ranking.nome_completo.tolist() == ['a/b','z/a']
    assert c['top_10pct_participacao_percentual'] == 0
    assert c['extremos_superiores'] == 0
    assert painel.releases.tolist() == [0,0]
    assert meses.percentual_sem_release.iloc[0] == 100


def test_schema_incompleto_e_repositorio_desconhecido():
    m,r = fixture_janela()
    with pytest.raises(ValueError, match='Colunas obrigatórias'):
        analisar(m, r.drop(columns='draft'), '2026-01-01','2026-01-07')
    r.loc[0,'nome_completo'] = 'fora/amostra'
    with pytest.raises(ValueError, match='fora da amostra'):
        analisar(m,r,'2026-01-01','2026-01-07')
