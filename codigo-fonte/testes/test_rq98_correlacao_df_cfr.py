import json

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from analise import rq98_correlacao_df_cfr as rq98
from analise.rq97_cfr import preparar_entregas
from coleta.coleta_dora import limites_da_janela
from metricas import dora

INICIO, FIM = limites_da_janela('2026-01-01', '2026-12-31')


def rel(nome, tag, publicada, i):
    return dict(nome_completo=nome, id=str(i), tag_name=tag, draft='False', prerelease='False',
                published_at=publicada)


# ------------------------------------------------------------- correlações
def test_interpretacao_do_rho_usa_os_limites_da_convencao():
    assert rq98.interpretar(None) == 'não estimável'
    assert rq98.interpretar(.099) == 'desprezível' and rq98.interpretar(-.05) == 'desprezível'
    assert rq98.interpretar(.1) == 'fraca positiva' and rq98.interpretar(-.299) == 'fraca negativa'
    assert rq98.interpretar(.3) == 'moderada positiva' and rq98.interpretar(-.499) == 'moderada negativa'
    assert rq98.interpretar(.5) == 'forte positiva' and rq98.interpretar(-1) == 'forte negativa'


def test_correlacao_perfeita_ignora_ausentes_e_e_indefinida_sem_variacao():
    x = pd.Series(range(1, 11), dtype=float)
    r = rq98.correlacao(x, x * 3)
    assert r['n'] == 10 and r['rho'] == pytest.approx(1.0) and r['interpretacao'] == 'forte positiva'
    assert r['ic95_inf'] == pytest.approx(1.0) and r['ic95_sup'] == pytest.approx(1.0)
    inversa = rq98.correlacao(x, -x)
    assert inversa['rho'] == pytest.approx(-1.0)
    com_nan = rq98.correlacao(pd.concat([x, pd.Series([99.])]), pd.concat([x, pd.Series([np.nan])]))
    assert com_nan['n'] == 10
    for y in (pd.Series([1.] * 10), pd.Series([1., 2.])):
        sem_variacao = rq98.correlacao(x if len(y) == 10 else x[:2], y)
        assert sem_variacao['rho'] is None and sem_variacao['interpretacao'] == 'não estimável'


def test_ic_bootstrap_do_rho_e_deterministico_e_contem_o_rho():
    rng = np.random.default_rng(1)
    x = rng.normal(size=80)
    y = x + rng.normal(size=80)
    inf, sup = rq98.ic_bootstrap_spearman(x, y, replicas=500)
    assert (inf, sup) == rq98.ic_bootstrap_spearman(x, y, replicas=500)
    rho = stats.spearmanr(x, y).statistic
    assert inf < rho < sup
    assert rq98.ic_bootstrap_spearman([1, 2, 3], [1, 2, 3]) == (None, None)


def test_spearman_parcial_bate_com_a_formula_de_um_controle():
    rng = np.random.default_rng(7)
    z = rng.normal(size=120)
    d = pd.DataFrame({'z': z, 'x': z + rng.normal(size=120), 'y': z + rng.normal(size=120)})
    rxy, rxz, ryz = (stats.spearmanr(d[a], d[b]).statistic for a, b in [('x', 'y'), ('x', 'z'), ('y', 'z')])
    esperado = (rxy - rxz * ryz) / np.sqrt((1 - rxz ** 2) * (1 - ryz ** 2))
    r = rq98.spearman_parcial(d, 'x', 'y', ['z'])
    assert r['rho'] == pytest.approx(esperado) and r['n'] == 120
    assert abs(r['rho']) < abs(rxy)  # o controle explica boa parte da correlação bruta
    assert 0 <= r['p'] <= 1
    assert rq98.spearman_parcial(d.head(3), 'x', 'y', ['z'])['rho'] is None
    constante = d.assign(y=1.)
    assert rq98.spearman_parcial(constante, 'x', 'y', ['z'])['rho'] is None


# ------------------------------------------------------------ linha de base mecânica
def test_linha_de_base_media_dos_embaralhamentos_calculada_a_mao():
    # flags da v1: [F, F, T]. Observado: v1.0.0 e v1.1.0 falham, v1.1.1 não -> 2/3.
    # Embaralhando as posições 1 e 2: [F, F, T] (2/3) ou [F, T, F] (1/3) -> esperado 1/2.
    entregas = preparar_entregas(pd.DataFrame([rel('org/a', 'v1.0.0', '2026-03-01T00:00:00Z', 1),
                                               rel('org/a', 'v1.1.0', '2026-03-02T00:00:00Z', 2),
                                               rel('org/a', 'v1.1.1', '2026-03-03T00:00:00Z', 3)]), FIM)
    r = rq98.linha_de_base(entregas, INICIO, FIM, replicas=2000).iloc[0]
    assert r.cfr_nulo == pytest.approx(.5, abs=.03)
    assert r.cfr_nulo_desvio == pytest.approx(1 / 6, abs=.02)
    assert r.oportunidade_7d == pytest.approx(2 / 3)  # v1.1.1 não tem sucessora
    repetido = rq98.linha_de_base(entregas, INICIO, FIM, replicas=2000).iloc[0]
    assert r.cfr_nulo == repetido.cfr_nulo  # semente fixa


def test_linha_de_base_sem_oportunidade_de_falha_e_sem_release_avaliavel():
    espalhadas = preparar_entregas(pd.DataFrame([rel('org/a', 'v1.0.0', '2026-03-01T00:00:00Z', 1),
                                                 rel('org/a', 'v1.0.1', '2026-04-01T00:00:00Z', 2),
                                                 rel('org/b', 'v1.0.0', '2026-12-30T00:00:00Z', 3),
                                                 rel('org/c', 'v1.0.0', '2026-05-01T00:00:00Z', 4)]), FIM)
    r = rq98.linha_de_base(espalhadas, INICIO, FIM, replicas=50).set_index('nome_completo')
    assert r.loc['org/a', 'cfr_nulo'] == 0 and r.loc['org/a', 'oportunidade_7d'] == 0  # nenhuma sucessora em 7 dias
    assert pd.isna(r.loc['org/b', 'cfr_nulo']) and pd.isna(r.loc['org/b', 'oportunidade_7d'])  # só censurada
    assert r.loc['org/c', 'cfr_nulo'] == 0  # uma única release


# -------------------------------------------------------- faixas e cruzamento das classes
def tabela_classes():
    return pd.DataFrame({
        'frequencia_deploy_semana': [.1, .2, .3, .4, 1., 2., 7., 8.],
        'classe_frequencia': ['Low', 'Low', 'Medium', 'Medium', 'High', 'High', 'Elite', 'Elite'],
        'cfr_ci': [.05, .1, .2, .5, .05, .1, .6, .4], 'cfr_entrega': [0., 0., .1, .2, .3, .5, .9, np.nan],
        'cfr_nulo': [.01, .02, .05, .1, .3, .4, .8, .9], 'oportunidade_7d': [.1, .1, .2, .3, .6, .7, .9, .95],
        'classe_cfr_a': ['Elite', 'Elite', 'High', 'Low', 'Elite', 'Elite', 'Low', 'Medium'],
        'classe_cfr_b': ['Elite', 'Elite', 'Elite', 'High', 'High', 'Low', 'Low', None]})


def test_cruzamento_das_classes_dora_com_fisher():
    d = tabela_classes()
    c = rq98.cruzamento_dora(d, 'classe_cfr_a')
    # frequência alta (Elite/High): 4 repositórios, CFR (a) alto em 2; baixa: 4, CFR (a) alto em 3
    assert (c['frequencia_alta_cfr_alto'], c['frequencia_alta_cfr_baixo']) == (2, 2)
    assert (c['frequencia_baixa_cfr_alto'], c['frequencia_baixa_cfr_baixo']) == (3, 1)
    assert c['proporcao_cfr_alto_na_frequencia_alta'] == .5 and c['proporcao_cfr_alto_na_frequencia_baixa'] == .75
    assert c['razao_de_chances'] == pytest.approx((2 * 1) / (2 * 3))
    assert c['fisher_p'] == pytest.approx(stats.fisher_exact([[2, 2], [3, 1]])[1])
    b = rq98.cruzamento_dora(d, 'classe_cfr_b')
    assert b['n'] == 7  # o repositório sem CFR (b) fica fora
    infinito = rq98.cruzamento_dora(pd.DataFrame({'classe_frequencia': ['High', 'Low'],
                                                  'classe_cfr_a': ['Elite', 'Low']}), 'classe_cfr_a')
    assert infinito['razao_de_chances'] is None  # divisão por zero vira ausente, não infinito


def test_faixas_de_frequencia_por_quartil():
    f = rq98.faixas_de_frequencia(tabela_classes())
    assert f.faixa.tolist() == ['Q1', 'Q2', 'Q3', 'Q4'] and f.n.tolist() == [2, 2, 2, 2]
    assert f.cfr_a_mediana.tolist() == pytest.approx([.075, .35, .075, .5])
    assert f.cfr_b_elite_ou_high.tolist() == [2, 2, 1, 0]
    assert f.frequencia_max.iloc[0] == .2 and f.frequencia_min.iloc[-1] == 7.


# -------------------------------------------------------------------- integração
def monta_entrada(tmp_path, dias=150):
    entrada = tmp_path / 'entrada'
    entrada.mkdir()
    metricas, releases = [], []
    for k in range(12):
        nome, total = f'org/r{k:02d}', 5 + 3 * k
        cfr = .02 * (k + 1)
        metricas.append(dict(nome_completo=nome, linguagem='Python', frequencia_deploy_semana=total / (365 / 7),
                             releases_janela=total, cfr_ci=cfr, classe_frequencia=dora.classificar_frequencia(
                                 total / (365 / 7)), classe_cfr=dora.classificar_cfr(cfr), runs_validos=100 + k,
                             idade_anos=1 + k % 5, contribuidores_total=10 + 7 * k))
        for i in range(total):
            dia = pd.Timestamp('2026-01-05', tz='UTC') + pd.Timedelta(days=i * dias / total)
            releases.append(rel(nome, f'v1.{i // 2}.{i % 2}', dia.strftime('%Y-%m-%dT%H:%M:%SZ'), 1000 * k + i + 1))
    pd.DataFrame(metricas).to_csv(entrada / 'metricas_repositorios.csv', index=False)
    pd.DataFrame(releases).to_csv(entrada / 'releases.csv', index=False)
    (entrada / 'resumo_execucao.json').write_text(json.dumps(
        {'config': {'janela': {'inicio': '2026-01-01', 'fim': '2026-12-31'}, 'janela_confirmada': False}}))
    return entrada


def test_executar_gera_saidas_e_numeros_conferiveis(tmp_path):
    entrada = monta_entrada(tmp_path)
    saida = tmp_path / 'saida'
    resumo = rq98.executar(entrada, saida, replicas_nulo=50, replicas_bootstrap=100)
    for nome in ['repositorios.csv', 'correlacoes.csv', 'robustez.csv', 'faixas_frequencia.csv', 'resumo.json',
                 'RELATORIO.md', 'dispersao_df_cfr.png', 'dispersao_df_cfr.svg', 'robustez_rho.png']:
        assert (saida / nome).is_file(), nome
    c = pd.read_csv(saida / 'correlacoes.csv').set_index('variante')
    # frequência e CFR (a) crescem juntos em todos os repositórios -> ρ = 1
    assert c.loc['a', 'rho'] == pytest.approx(1.0) and c.loc['a', 'n'] == 12
    assert c.loc['a', 'p_holm'] >= c.loc['a', 'p']
    assert c.loc['b', 'n'] == 12 and -1 <= c.loc['b', 'rho'] <= 1
    assert c.loc['b', 'p_holm'] >= c.loc['b', 'p']
    r = pd.read_csv(saida / 'repositorios.csv')
    assert set(r.nome_completo) == {f'org/r{k:02d}' for k in range(12)}
    assert r.cfr_entrega.between(0, 1).all() and r.cfr_nulo.between(0, 1).all()
    rob = pd.read_csv(saida / 'robustez.csv')
    assert {'todos os repositórios'} <= set(rob.subconjunto)
    assert rob.subconjunto.str.contains('linha de base').any()
    assert resumo['principais'][0]['variante'] == 'a' and resumo['mecanica']['replicas'] == 50
    assert set(resumo['fontes_sha256']) == {'entrada/metricas_repositorios.csv', 'entrada/releases.csv',
                                            'entrada/resumo_execucao.json'}
    json.loads((saida / 'resumo.json').read_text(encoding='utf-8'))
    texto = (saida / 'RELATORIO.md').read_text(encoding='utf-8')
    assert 'Confronto com H5' in texto and 'acoplamento mecânico' in texto


def test_executar_com_cfr_b_constante_gera_relatorio_sem_correlacao_do_b(tmp_path):
    # Releases espaçadas demais: nenhuma sucessora em 7 dias, CFR (b) = 0 em todos e ρ indefinido.
    entrada = monta_entrada(tmp_path, dias=300)
    resumo = rq98.executar(entrada, tmp_path / 'saida', replicas_nulo=20, replicas_bootstrap=50)
    b = [r for r in resumo['principais'] if r['variante'] == 'b'][0]
    assert b['rho'] is None and b['p_holm'] is None and b['interpretacao'] == 'não estimável'
    a = [r for r in resumo['principais'] if r['variante'] == 'a'][0]
    assert a['p_holm'] == a['p']  # Holm com um único teste estimável não altera o p
    assert 'não estimável' in (tmp_path / 'saida' / 'RELATORIO.md').read_text(encoding='utf-8')


def test_analisar_rejeita_entradas_inconsistentes(tmp_path):
    entrada = monta_entrada(tmp_path)
    metricas = pd.read_csv(entrada / 'metricas_repositorios.csv')
    entregas = preparar_entregas(pd.read_csv(entrada / 'releases.csv', dtype=str, keep_default_na=False), FIM)
    rq98.analisar(metricas, entregas, INICIO, FIM, 20, 50)
    with pytest.raises(ValueError, match='ausentes'):
        rq98.analisar(metricas.drop(columns='classe_cfr'), entregas, INICIO, FIM, 20, 50)
    with pytest.raises(ValueError, match='duplicados'):
        rq98.analisar(pd.concat([metricas, metricas.iloc[[0]]]), entregas, INICIO, FIM, 20, 50)
    with pytest.raises(ValueError, match='fora da amostra'):
        rq98.analisar(metricas.iloc[1:], entregas, INICIO, FIM, 20, 50)
    with pytest.raises(ValueError, match='fora do intervalo'):
        rq98.analisar(metricas.assign(cfr_ci=1.5), entregas, INICIO, FIM, 20, 50)
    with pytest.raises(ValueError, match='diverge'):
        rq98.analisar(metricas.assign(classe_cfr='Elite'), entregas, INICIO, FIM, 20, 50)
