import json

import pandas as pd
import pytest

from analise.rq96_sensibilidade_dora import analisar, comparar, executar, landis_koch

INICIO, FIM = '2026-01-01', '2026-01-28'  # 4 semanas


def metrica(nome, releases, pre, lead_a, lead_b, cfr, rec, geral):
    return dict(nome_completo=nome, linguagem='Go', releases_janela=releases, prereleases_janela=pre,
                frequencia_deploy_semana=releases / 4, lead_time_release_mediana_dias=lead_a,
                lead_time_commit_mediana_dias=lead_b, cfr_ci=cfr, recuperacao_mediana_horas=rec, classe_geral=geral)


def release(nome, i, tag, data, pre=False):
    return dict(nome_completo=nome, id=i, tag_name=tag, draft='False', prerelease=str(pre), published_at=data)


def tag(nome, nome_tag, dentro):
    return dict(nome_completo=nome, tag_name=nome_tag, dentro_janela=str(dentro), status='ok')


def dados():
    # org/a: 4 releases (1/sem, High); 1.0.0 -> 1.0.1 em 2 dias é corretiva.
    rel = [release('org/a', 1, 'v1.0.0', '2026-01-02T00:00:00Z'),
           release('org/a', 2, 'v1.0.1', '2026-01-04T00:00:00Z'),
           release('org/a', 3, 'v1.1.0', '2026-01-10T00:00:00Z'),
           release('org/a', 4, 'v1.2.0', '2026-01-15T00:00:00Z'),
           release('org/a', 5, 'v2.0.0-rc1', '2026-01-16T00:00:00Z', pre=True),
           release('org/b', 6, 'v0.1.0', '2026-01-05T00:00:00Z')]
    tags = [tag('org/a', f't{i}', True) for i in range(30)] + [tag('org/b', 'v0.1.0', True), tag('org/b', 'x', False)]
    m = pd.DataFrame([
        # notas: freq High(3), lead High(3), cfr Elite(4), rec Elite(4) -> 3,5 -> High.
        # Com tags (freq Elite) ou lead (b) Elite, a mediana vira 4 -> Elite.
        metrica('org/a', 4, 1, 2., 0.5, .05, .5, 'High'),
        # freq 0,25/sem -> Medium(2), lead Low(1), cfr Elite(4), rec indefinida -> geral vazia
        metrica('org/b', 1, 0, 40., 40., .05, None, None)])
    return m, pd.DataFrame(rel), pd.DataFrame(tags)


def test_comparar_e_landis_koch():
    x = pd.Series(['Elite', 'High', 'Medium', None])
    y = pd.Series(['Elite', 'Medium', 'Medium', 'Low'])
    r = comparar(x, y)
    assert (r['n'], r['mudam'], r['pioram'], r['melhoram']) == (3, 1, 1, 0)
    assert r['proporcao_mudam'] == pytest.approx(1 / 3)
    assert comparar(pd.Series([None]), pd.Series(['Low']))['n'] == 0
    assert [landis_koch(k) for k in [None, -.1, .1, .3, .5, .7, .9]] == [
        'não estimável', 'pobre', 'leve', 'razoável', 'moderada', 'substancial', 'quase perfeita']
    assert comparar(pd.Series(['High']), pd.Series(['High']))['kappa_linear'] is None


def test_variantes_e_combinacoes():
    tabela, definicoes, distrib, pares, metricas_var, resumo = analisar(*dados(), INICIO, FIM)
    a = tabela.set_index('nome_completo').loc['org/a']
    assert a.frequencia_release == 1 and a.frequencia_release_prerelease == 1.25 and a.frequencia_tag == 7.5
    assert (a.classe_freq_tag, a.classe_lead_b) == ('Elite', 'Elite')
    # Releases avaliadas: até 21/01 (as de 7 dias antes do fim). v1.0.0 falha por causa de v1.0.1.
    assert (a.releases_avaliadas_cfr, a.releases_falha_cfr) == (4, 1) and a.cfr_entrega == .25
    assert a.classe_cfr_b == 'High'
    assert a.C1 == 'High' and a.C6 == 'Elite' and a.C2 == 'Elite'
    assert pd.isna(tabela.set_index('nome_completo').loc['org/b', 'C1'])
    c1c6 = pares.set_index(['combinacao_1', 'combinacao_2']).loc[('C1', 'C6')]
    assert (c1c6.n, c1c6.mudam, c1c6.melhoram) == (1, 1, 1)
    assert len(pares) == 21 and resumo['repositorios_classificados_em_todas'] == 1
    assert distrib.groupby('combinacao').repositorios.sum().eq(2).all()


def test_contagem_divergente_e_rejeitada():
    m, rel, tags = dados()
    m.loc[0, 'prereleases_janela'] = 0
    with pytest.raises(ValueError, match='pré-releases'):
        analisar(m, rel, tags, INICIO, FIM)


def test_c1_divergente_e_rejeitada():
    m, rel, tags = dados()
    m.loc[0, 'classe_geral'] = 'Elite'
    with pytest.raises(ValueError, match='C1'):
        analisar(m, rel, tags, INICIO, FIM)


def test_entradas_invalidas():
    m, rel, tags = dados()
    with pytest.raises(ValueError, match='ausentes'):
        analisar(m.drop(columns='cfr_ci'), rel, tags, INICIO, FIM)
    with pytest.raises(ValueError, match='duplicadas'):
        analisar(m, pd.concat([rel, rel.iloc[[0]]]), tags, INICIO, FIM)
    sem_data = tags.copy()
    sem_data.loc[0, 'status'] = 'erro'
    with pytest.raises(ValueError, match='status'):
        analisar(m, rel, sem_data, INICIO, FIM)
    fora = pd.concat([tags, pd.DataFrame([tag('org/z', 'v1', True)])])
    with pytest.raises(ValueError, match='fora da amostra'):
        analisar(m, rel, fora, INICIO, FIM)


def test_executar_gera_saidas(tmp_path):
    entrada = tmp_path / 'entrada'
    entrada.mkdir()
    m, rel, tags = dados()
    m.to_csv(entrada / 'metricas_repositorios.csv', index=False)
    rel.to_csv(entrada / 'releases.csv', index=False)
    tags.to_csv(entrada / 'tags.csv', index=False)
    (entrada / 'resumo_execucao.json').write_text(json.dumps(
        {'config': {'janela': {'inicio': INICIO, 'fim': FIM}, 'janela_confirmada': False}}))
    saida = tmp_path / 'saida'
    resumo = executar(entrada, saida)
    for nome in ['repositorios_combinacoes.csv', 'combinacoes.csv', 'classes_combinacoes.csv', 'pares.csv',
                 'metricas_variantes.csv', 'resumo.json', 'RELATORIO.md', 'concordancia_pares.png',
                 'classes_combinacoes.svg']:
        assert (saida / nome).exists(), nome
    assert resumo['heuristica_validada_manualmente'] is False
    assert 'H7' in (saida / 'RELATORIO.md').read_text(encoding='utf-8')
