"""RQ98 / LAB03 RQ05: correlação entre frequência de deploy e CFR, sem rede.

python codigo-fonte/analise/rq98_correlacao_df_cfr.py

Correlação de Spearman (ρ, p-valor e n) entre a frequência de deploy (RQ01) e o
CFR, separadamente para a variante (a), de CI, e para a variante (b), de entrega
(heurística padrão ``patch_semver_v1``). Complementa com:

- intervalo de confiança de 95% do ρ por *bootstrap* de pares e correção de Holm
  para os dois testes principais;
- leitura por faixas (quartis) de frequência e o cruzamento das classes DORA;
- **linha de base mecânica do CFR (b)**: quanto mais releases, maior a chance de
  uma release de *patch* sair em até 7 dias da anterior, mesmo que os *patches*
  caiam em datas aleatórias. A linha de base embaralha, dentro de cada
  repositório, quais releases são corretivas (preservando as datas e o número de
  corretivas) e dá o CFR (b) esperado sem relação entre uma release e a seguinte;
- robustez: sem extremos de frequência, com mais releases/runs, só repositórios
  SemVer, e correlação parcial controlando idade, contribuidores e a linha de base.

As funções de nível de release vêm de ``rq97_cfr`` e a recontagem de
``variantes.cfr_entrega`` é conferida por ela.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests

CODIGO = Path(__file__).resolve().parents[1]
RAIZ = CODIGO.parent
sys.path.insert(0, str(CODIGO))
from analise import rq97_cfr as rq97  # noqa: E402
from coleta.coleta_dora import limites_da_janela  # noqa: E402
from metricas import ci, corretiva, dora  # noqa: E402

SEMENTE = 42
REPLICAS_BOOTSTRAP = 2000
REPLICAS_NULO = 1000
CLASSES_ALTAS = ('Elite', 'High')
VARIANTES = {'a': ('cfr_ci', 'CFR (a) · CI'), 'b': ('cfr_entrega', 'CFR (b) · entrega (v1)')}


def _valor(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else v


def _n(x, casas=2):
    return 'não estimável' if x is None or (isinstance(x, float) and math.isnan(x)) else f'{x:.{casas}f}'


def _p(x, casas=1):
    return 'não estimável' if x is None or (isinstance(x, float) and math.isnan(x)) else f'{x * 100:.{casas}f}%'


def _e(x):
    return 'não estimável' if x is None or (isinstance(x, float) and math.isnan(x)) else f'{x:.2e}'


def _g(x):
    """p-valor: notação científica só quando muito pequeno."""
    return 'não estimável' if x is None or (isinstance(x, float) and math.isnan(x)) else \
        (f'{x:.3f}' if x >= .001 else f'{x:.1e}')


def _ausente(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


def _maior(a, b) -> bool:
    return not _ausente(a) and not _ausente(b) and a > b


def interpretar(rho) -> str:
    """Convenção usual para |ρ|: < 0,1 desprezível; < 0,3 fraca; < 0,5 moderada; ≥ 0,5 forte."""
    if _ausente(rho):
        return 'não estimável'
    r = abs(rho)
    forca = 'desprezível' if r < .1 else 'fraca' if r < .3 else 'moderada' if r < .5 else 'forte'
    return forca if forca == 'desprezível' else f'{forca} {"positiva" if rho > 0 else "negativa"}'


# ------------------------------------------------------------------ correlações
def ic_bootstrap_spearman(x, y, replicas: int = REPLICAS_BOOTSTRAP, semente: int = SEMENTE):
    """Intervalo percentil de 95% para o ρ, reamostrando pares (semente fixa)."""
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if len(x) < 4:
        return None, None
    rng = np.random.default_rng(semente)
    idx = rng.integers(0, len(x), size=(replicas, len(x)))
    rx, ry = stats.rankdata(x[idx], axis=1), stats.rankdata(y[idx], axis=1)
    rx, ry = rx - rx.mean(axis=1, keepdims=True), ry - ry.mean(axis=1, keepdims=True)
    with np.errstate(invalid='ignore', divide='ignore'):
        rhos = (rx * ry).sum(axis=1) / np.sqrt((rx ** 2).sum(axis=1) * (ry ** 2).sum(axis=1))
    rhos = rhos[~np.isnan(rhos)]
    if rhos.size < replicas // 2:
        return None, None
    return float(np.percentile(rhos, 2.5)), float(np.percentile(rhos, 97.5))


def correlacao(x, y, replicas: int = REPLICAS_BOOTSTRAP) -> dict:
    """Spearman com p-valor, n e IC por bootstrap; usa só os pares completos."""
    d = pd.DataFrame({'x': x, 'y': y}).dropna()
    if len(d) < 3 or d.x.nunique() < 2 or d.y.nunique() < 2:
        return dict(n=len(d), rho=None, p=None, ic95_inf=None, ic95_sup=None, interpretacao='não estimável')
    r = stats.spearmanr(d.x, d.y)
    inf, sup = ic_bootstrap_spearman(d.x, d.y, replicas)
    rho = _valor(float(r.statistic))
    return dict(n=len(d), rho=rho, p=_valor(float(r.pvalue)), ic95_inf=inf, ic95_sup=sup,
                interpretacao=interpretar(rho))


def spearman_parcial(df: pd.DataFrame, x: str, y: str, controles: list) -> dict:
    """Spearman parcial: correlação de Pearson entre os resíduos dos *postos* de x e y
    após regredir cada um nos postos dos controles. O p-valor usa n − 2 − k graus de liberdade."""
    d = df[[x, y] + controles].dropna()
    n, k = len(d), len(controles)
    if n - 2 - k < 1:
        return dict(n=n, rho=None, p=None)
    postos = d.rank()
    base = np.column_stack([np.ones(n)] + [postos[c].to_numpy() for c in controles])

    def residuo(v):
        coef, *_ = np.linalg.lstsq(base, postos[v].to_numpy(), rcond=None)
        return postos[v].to_numpy() - base @ coef
    rx, ry = residuo(x), residuo(y)
    if np.allclose(rx, 0) or np.allclose(ry, 0):
        return dict(n=n, rho=None, p=None)
    rho = float(np.corrcoef(rx, ry)[0, 1])
    t = rho * math.sqrt((n - 2 - k) / max(1e-15, 1 - rho ** 2))
    return dict(n=n, rho=rho, p=float(2 * stats.t.sf(abs(t), n - 2 - k)))


# --------------------------------------------------------- linha de base mecânica
def linha_de_base(entregas: dict, inicio, fim, replicas: int = REPLICAS_NULO, semente: int = SEMENTE) -> pd.DataFrame:
    """CFR (b) esperado se as corretivas caíssem em releases aleatórias do mesmo repositório.

    Para cada repositório, embaralha entre as releases (da segunda em diante, pois a
    primeira nunca é corretiva) quais são corretivas segundo a v1, preservando datas
    e quantidade, e devolve a média e o desvio do CFR (b) em ``replicas`` embaralhamentos.
    ``oportunidade_7d`` é a fração das releases avaliadas seguidas por qualquer release
    em até 7 dias: o teto de falhas possível, que cresce com a frequência.
    """
    inicio_s, fim_s = int(ci.data_utc(inicio).timestamp()), int(ci.data_utc(fim).timestamp())
    rng = np.random.default_rng(semente)
    linhas = []
    for nome in sorted(entregas):
        e = entregas[nome]
        flags = rq97.sinalizar_corretivas(e)
        t = e.t
        avaliada = (t >= inicio_s) & (t + rq97.SETE_DIAS <= fim_s)
        a = np.searchsorted(t, t, side='right')[avaliada]
        b = np.searchsorted(t, t + rq97.SETE_DIAS, side='right')[avaliada]
        if not avaliada.any():
            linhas.append(dict(nome_completo=nome, cfr_nulo=None, cfr_nulo_desvio=None, oportunidade_7d=None))
            continue
        embaralhado = rng.permuted(np.tile(flags[1:], (replicas, 1)), axis=1)
        # A primeira release nunca é corretiva; cum[:, k] = corretivas entre as k primeiras releases.
        todas = np.concatenate([np.zeros((replicas, 1), dtype=bool), embaralhado], axis=1)
        cum = np.concatenate([np.zeros((replicas, 1), dtype=np.int64), np.cumsum(todas, axis=1, dtype=np.int64)],
                             axis=1)
        cfr = (cum[:, b] > cum[:, a]).mean(axis=1)
        linhas.append(dict(nome_completo=nome, cfr_nulo=float(cfr.mean()), cfr_nulo_desvio=float(cfr.std()),
                           oportunidade_7d=float((b > a).mean())))
    return pd.DataFrame(linhas)


# ------------------------------------------------------------------------ análise
def faixas_de_frequencia(df: pd.DataFrame) -> pd.DataFrame:
    """Quartis de frequência: CFR (a), CFR (b) e linha de base (b) em cada faixa."""
    d = df.copy()
    d['faixa'] = pd.qcut(d.frequencia_deploy_semana, 4, labels=['Q1', 'Q2', 'Q3', 'Q4'], duplicates='drop')
    linhas = []
    for faixa, g in d.groupby('faixa', observed=True):
        linhas.append(dict(faixa=str(faixa), n=len(g), frequencia_min=g.frequencia_deploy_semana.min(),
                           frequencia_max=g.frequencia_deploy_semana.max(),
                           cfr_a_mediana=g.cfr_ci.median(), cfr_b_mediana=g.cfr_entrega.median(),
                           cfr_b_nulo_mediana=g.cfr_nulo.median(), oportunidade_7d_mediana=g.oportunidade_7d.median(),
                           cfr_a_elite_ou_high=int(g.classe_cfr_a.isin(CLASSES_ALTAS).sum()),
                           cfr_b_elite_ou_high=int(g.classe_cfr_b.isin(CLASSES_ALTAS).sum())))
    return pd.DataFrame(linhas)


def cruzamento_dora(df: pd.DataFrame, classe_cfr: str) -> dict:
    """Frequência alta (Elite/High) × CFR alto (Elite/High), com Fisher exato."""
    d = df.dropna(subset=[classe_cfr])
    freq_alta = d.classe_frequencia.isin(CLASSES_ALTAS)
    cfr_alto = d[classe_cfr].isin(CLASSES_ALTAS)
    tabela = [[int((freq_alta & cfr_alto).sum()), int((freq_alta & ~cfr_alto).sum())],
              [int((~freq_alta & cfr_alto).sum()), int((~freq_alta & ~cfr_alto).sum())]]
    odds, p = stats.fisher_exact(tabela)
    n_alta, n_baixa = sum(tabela[0]), sum(tabela[1])
    return dict(n=len(d), frequencia_alta_cfr_alto=tabela[0][0], frequencia_alta_cfr_baixo=tabela[0][1],
                frequencia_baixa_cfr_alto=tabela[1][0], frequencia_baixa_cfr_baixo=tabela[1][1],
                proporcao_cfr_alto_na_frequencia_alta=tabela[0][0] / n_alta if n_alta else None,
                proporcao_cfr_alto_na_frequencia_baixa=tabela[1][0] / n_baixa if n_baixa else None,
                razao_de_chances=_valor(float(odds)) if not math.isinf(odds) else None, fisher_p=float(p))


def analisar(metricas: pd.DataFrame, entregas: dict, inicio, fim, replicas_nulo: int = REPLICAS_NULO,
             replicas_bootstrap: int = REPLICAS_BOOTSTRAP):
    colunas = {'nome_completo', 'frequencia_deploy_semana', 'cfr_ci', 'classe_frequencia', 'classe_cfr',
               'runs_validos', 'idade_anos', 'contribuidores_total', 'releases_janela'}
    faltantes = colunas - set(metricas.columns)
    if faltantes:
        raise ValueError(f'Colunas obrigatórias ausentes: {sorted(faltantes)}')
    if metricas.empty or metricas.nome_completo.isna().any() or metricas.nome_completo.duplicated().any():
        raise ValueError('Amostra vazia, identificadores ausentes ou repositórios duplicados.')
    if not set(entregas) <= set(metricas.nome_completo):
        raise ValueError('Releases de repositórios fora da amostra.')
    df = metricas.sort_values('nome_completo').reset_index(drop=True).copy()
    if ((df.cfr_ci < 0) | (df.cfr_ci > 1)).any() or (df.frequencia_deploy_semana < 0).any():
        raise ValueError('Frequência negativa ou CFR (a) fora do intervalo [0, 1].')

    v1 = rq97.cfr_por_heuristica(entregas, corretiva.HEURISTICA_PADRAO, inicio, fim)
    rq97.conferir_com_oficial(entregas, v1, inicio, fim)
    df = df.merge(v1[['nome_completo', 'cfr_entrega', 'releases_avaliadas_cfr', 'releases_corretivas',
                      'releases_na_janela', 'releases_sem_semver']], on='nome_completo', how='left')
    df['cfr_entrega'] = pd.to_numeric(df.cfr_entrega)
    for coluna in ['releases_avaliadas_cfr', 'releases_corretivas', 'releases_na_janela', 'releases_sem_semver']:
        df[coluna] = df[coluna].fillna(0).astype(int)
    df['proporcao_semver'] = (1 - df.releases_sem_semver / df.releases_na_janela).where(df.releases_na_janela > 0)
    df['classe_cfr_a'] = df.cfr_ci.map(lambda v: dora.classificar_cfr(_valor(v)))
    df['classe_cfr_b'] = df.cfr_entrega.map(lambda v: dora.classificar_cfr(_valor(v)))
    if not (df.classe_cfr_a.fillna('') == df.classe_cfr.fillna('')).all():
        raise ValueError('Classe de CFR (a) exportada diverge da reclassificação.')
    df = df.merge(linha_de_base(entregas, inicio, fim, replicas_nulo), on='nome_completo', how='left')
    for coluna in ['cfr_nulo', 'cfr_nulo_desvio', 'oportunidade_7d']:
        df[coluna] = pd.to_numeric(df[coluna])
    df['cfr_b_menos_nulo'] = df.cfr_entrega - df.cfr_nulo
    df['log10_frequencia'] = np.log10(df.frequencia_deploy_semana.where(df.frequencia_deploy_semana > 0))
    df['log_contribuidores'] = np.log1p(df.contribuidores_total)

    # Testes principais, Holm entre os dois.
    principais = {}
    for chave, (coluna, rotulo) in VARIANTES.items():
        principais[chave] = dict(variante=chave, rotulo=rotulo,
                                 **correlacao(df.frequencia_deploy_semana, df[coluna], replicas_bootstrap))
    estimaveis = [k for k in principais if principais[k]['p'] is not None]
    for k in principais:
        principais[k]['p_holm'] = None
    if estimaveis:  # Holm entre os testes que existem
        ajustados = multipletests([principais[k]['p'] for k in estimaveis], method='holm')[1]
        for k, aj in zip(estimaveis, ajustados):
            principais[k]['p_holm'] = float(aj)
    correlacoes = pd.DataFrame(list(principais.values()))

    # Linha de base e oportunidade (explicação mecânica).
    mecanica = dict(
        frequencia_x_nulo=correlacao(df.frequencia_deploy_semana, df.cfr_nulo, replicas_bootstrap),
        frequencia_x_oportunidade=correlacao(df.frequencia_deploy_semana, df.oportunidade_7d, replicas_bootstrap),
        frequencia_x_proporcao_corretivas=correlacao(
            df.frequencia_deploy_semana, df.releases_corretivas / df.releases_na_janela.where(df.releases_na_janela > 0),
            replicas_bootstrap),
        observado_x_nulo=correlacao(df.cfr_entrega, df.cfr_nulo, replicas_bootstrap),
        frequencia_x_nulo_semver=correlacao(df.loc[df.proporcao_semver >= .8, 'frequencia_deploy_semana'],
                                            df.loc[df.proporcao_semver >= .8, 'cfr_nulo'], replicas_bootstrap),
        nulo_mediana=_valor(float(df.cfr_nulo.median())), observado_mediana=_valor(float(df.cfr_entrega.median())),
        observado_abaixo_do_nulo=int((df.cfr_b_menos_nulo < 0).sum()),
        observado_acima_do_nulo=int((df.cfr_b_menos_nulo > 0).sum()),
        replicas=replicas_nulo)

    # Robustez.
    q1, q3 = df.frequencia_deploy_semana.quantile([.25, .75])
    limite = float(q3 + 1.5 * (q3 - q1))
    sem_extremos = df.frequencia_deploy_semana <= limite
    linhas = []

    def sub(variante, nome, mascara):
        coluna = VARIANTES[variante][0]
        s = df.loc[mascara]
        linhas.append(dict(variante=variante, subconjunto=nome, **correlacao(s.frequencia_deploy_semana, s[coluna],
                                                                              replicas_bootstrap)))
    for v in VARIANTES:
        sub(v, 'todos os repositórios', df.index == df.index)
        sub(v, 'sem extremos de frequência (acima de Q3 + 1,5·IQR)', sem_extremos)
    sub('a', 'com pelo menos 500 runs válidos', df.runs_validos >= 500)
    sub('b', 'com pelo menos 20 releases avaliadas', df.releases_avaliadas_cfr >= 20)
    sub('b', 'com pelo menos 80% das releases em SemVer', df.proporcao_semver >= .8)
    sub('b', 'SemVer (≥ 80%) e sem extremos de frequência', (df.proporcao_semver >= .8) & sem_extremos)
    for v in VARIANTES:
        coluna = VARIANTES[v][0]
        parcial = spearman_parcial(df, 'frequencia_deploy_semana', coluna, ['idade_anos', 'log_contribuidores'])
        linhas.append(dict(variante=v, subconjunto='parcial: controlando idade e contribuidores', **parcial,
                           ic95_inf=None, ic95_sup=None, interpretacao=interpretar(parcial['rho'])))
    parcial = spearman_parcial(df, 'frequencia_deploy_semana', 'cfr_entrega', ['cfr_nulo'])
    linhas.append(dict(variante='b', subconjunto='parcial: controlando o CFR (b) esperado pela linha de base',
                       **parcial, ic95_inf=None, ic95_sup=None, interpretacao=interpretar(parcial['rho'])))
    robustez = pd.DataFrame(linhas)

    faixas = faixas_de_frequencia(df)
    cruzamento = {chave: cruzamento_dora(df, f'classe_cfr_{chave}') for chave in VARIANTES}
    classes_freq = df.classe_frequencia.value_counts().reindex(rq97.CLASSES, fill_value=0).astype(int).to_dict()

    resumo = dict(
        repositorios=len(df), principais=json.loads(correlacoes.to_json(orient='records', force_ascii=False, double_precision=15)),
        mecanica=mecanica, robustez=json.loads(robustez.to_json(orient='records', force_ascii=False, double_precision=15)),
        faixas=json.loads(faixas.to_json(orient='records', force_ascii=False, double_precision=15)),
        cruzamento_dora=cruzamento, classes_frequencia=classes_freq,
        extremos_de_frequencia=dict(limite_tukey=limite, repositorios_acima=int((~sem_extremos).sum())),
        heuristica=corretiva.HEURISTICA_PADRAO, heuristica_validada_manualmente=False,
        cfr_b_indefinido=int(df.cfr_entrega.isna().sum()),
        mediana_frequencia=float(df.frequencia_deploy_semana.median()))
    return df, correlacoes, robustez, faixas, resumo


# ------------------------------------------------------------------------- saídas
def graficos(df, correlacoes, robustez, resumo, destino):
    cache = RAIZ / 'dados/.cache/matplotlib'
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR', str(cache))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    matplotlib.rcParams['svg.hashsalt'] = 'rq98'
    meta = {'metadata': {'Date': None}}
    principal = correlacoes.set_index('variante')

    fig, eixos = plt.subplots(1, 2, figsize=(12, 4.8), constrained_layout=True, sharex=True)
    d = df.loc[df.frequencia_deploy_semana > 0]
    faixas = pd.qcut(d.frequencia_deploy_semana, 8, duplicates='drop')
    centro = d.groupby(faixas, observed=True).frequencia_deploy_semana.median()
    for ax, (chave, (coluna, rotulo)), cor in zip(eixos, VARIANTES.items(), ['#377EB8', '#B58A27']):
        ax.scatter(d.frequencia_deploy_semana, d[coluna], s=14, alpha=.5, color=cor, edgecolor='none',
                   label='repositório')
        ax.plot(centro.to_numpy(), d.groupby(faixas, observed=True)[coluna].median().to_numpy(), color='black',
                linewidth=1.6, marker='o', markersize=4, label='mediana por octil de frequência')
        if chave == 'b':
            ax.plot(centro.to_numpy(), d.groupby(faixas, observed=True).cfr_nulo.median().to_numpy(),
                    color='#8D5959', linewidth=1.6, linestyle='--', marker='s', markersize=4,
                    label='esperado ao acaso (linha de base)')
        r = principal.loc[chave]
        ax.set(xscale='log', xlabel='Frequência de deploy (releases/semana, escala log)', ylabel=rotulo,
               title=f'ρ = {_n(r.rho)} · p = {_g(r.p)} · n = {int(r.n)}', ylim=(-.03, 1.03))
        ax.legend(loc='upper left', fontsize=8)
    fig.suptitle('RQ98 · Frequência de deploy × CFR')
    for ext in ['png', 'svg']:
        fig.savefig(destino / f'dispersao_df_cfr.{ext}', dpi=180, **(meta if ext == 'svg' else {}))
    plt.close(fig)

    r = robustez.dropna(subset=['rho']).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(10, .42 * len(r) + 1.4), constrained_layout=True)
    y = np.arange(len(r))[::-1]
    for i, linha in r.iterrows():
        cor = '#377EB8' if linha.variante == 'a' else '#B58A27'
        if _valor(linha.ic95_inf) is not None:
            ax.hlines(y[i], linha.ic95_inf, linha.ic95_sup, color=cor, linewidth=2)
        ax.plot(linha.rho, y[i], 'o', color=cor)
    ax.axvline(0, color='gray', linewidth=1)
    ax.set_yticks(y, [f'({v}) {s} (n = {int(n)})' for v, s, n in zip(r.variante, r.subconjunto, r.n)], fontsize=8)
    ax.set(xlabel='ρ de Spearman (barras: IC de 95% por bootstrap, quando há)', xlim=(-.6, 1),
           title='RQ98 · Robustez da correlação (azul: CFR (a); amarelo: CFR (b))')
    for ext in ['png', 'svg']:
        fig.savefig(destino / f'robustez_rho.{ext}', dpi=180, **(meta if ext == 'svg' else {}))
    plt.close(fig)


def relatorio(df, correlacoes, robustez, faixas, resumo, config) -> str:
    n = len(df)
    aviso = 'confirmada na configuração' if config.get('janela_confirmada') is True else \
        '**ainda não confirmada pelo professor na configuração**'
    pr = correlacoes.set_index('variante')
    ra, rb = pr.loc['a'], pr.loc['b']
    mec = resumo['mecanica']
    cru = resumo['cruzamento_dora']

    tabela_principal = '\n'.join(
        f'| {r.rotulo} | {int(r.n)} | {_n(r.rho, 3)} | {_g(r.p)} | {_g(r.p_holm)} | '
        f'{_n(r.ic95_inf, 2)} a {_n(r.ic95_sup, 2)} | {r.interpretacao} |' for r in correlacoes.itertuples())
    tabela_faixas = '\n'.join(
        f'| {r.faixa} | {int(r.n)} | {_n(r.frequencia_min, 3)}–{_n(r.frequencia_max, 3)} | {_p(r.cfr_a_mediana)} | '
        f'{_p(r.cfr_b_mediana)} | {_p(r.cfr_b_nulo_mediana)} | {_p(r.oportunidade_7d_mediana, 0)} |'
        for r in faixas.itertuples())

    def linha_cruzamento(chave, rotulo):
        c = cru[chave]
        return (f'| {rotulo} | {c["n"]} | {c["frequencia_alta_cfr_alto"]} de '
                f'{c["frequencia_alta_cfr_alto"] + c["frequencia_alta_cfr_baixo"]} '
                f'({_p(c["proporcao_cfr_alto_na_frequencia_alta"], 0)}) | {c["frequencia_baixa_cfr_alto"]} de '
                f'{c["frequencia_baixa_cfr_alto"] + c["frequencia_baixa_cfr_baixo"]} '
                f'({_p(c["proporcao_cfr_alto_na_frequencia_baixa"], 0)}) | {_n(c["razao_de_chances"], 2)} | '
                f'{_g(c["fisher_p"])} |')
    tabela_cruzamento = '\n'.join([linha_cruzamento('a', 'CFR (a) · CI'), linha_cruzamento('b', 'CFR (b) · entrega (v1)')])
    tabela_robustez = '\n'.join(
        f'| ({r.variante}) {r.subconjunto} | {int(r.n)} | {_n(r.rho, 3)} | {_g(r.p)} | '
        f'{"—" if _valor(r.ic95_inf) is None else _n(r.ic95_inf, 2) + " a " + _n(r.ic95_sup, 2)} |'
        for r in robustez.itertuples())
    parcial_nulo = robustez.loc[robustez.subconjunto.str.contains('linha de base')].iloc[0]
    semver = robustez.loc[(robustez.variante == 'b') & (robustez.subconjunto == 'com pelo menos 80% das releases em SemVer')].iloc[0]
    parcial_idade = robustez.loc[robustez.subconjunto.str.startswith('parcial: controlando idade')].set_index('variante')

    h5_b = not _ausente(rb.rho) and rb.rho <= 0.1  # previsão: próxima de zero ou levemente negativa
    h5_a = not _ausente(ra.rho) and abs(ra.rho) < .1
    h5_a_fraca = not _ausente(ra.rho) and abs(ra.rho) < .3
    pontos = h5_b + (1 if h5_a else .5 if h5_a_fraca else 0)
    veredito = 'confirmada' if pontos == 2 else 'não confirmada' if pontos == 0 else 'parcialmente confirmada'

    return f'''# RQ98 — RQ05: Correlação entre Deployment Frequency e Change Failure Rate

## Pergunta e método

Repositórios com maior frequência de deploy apresentam maior ou menor taxa de falha? Análise local de **{n} repositórios**, janela UTC inclusiva {config['janela']['inicio']} a {config['janela']['fim']}, {aviso}.

- **Frequência de deploy** (RQ01): releases publicadas (não draft, não pré-release) na janela / semanas da janela.
- **CFR (a)** de CI e **CFR (b)** de entrega (heurística padrão `{resumo['heuristica']}`, **sem validação manual concluída**), como na RQ97. O CFR (b) é recalculado aqui e conferido com `metricas.variantes.cfr_entrega`; o CFR (a) vem da coleta e a classe é reclassificada.
- **Correlação de Spearman** (ρ, p-valor, n) entre a frequência e cada variante, calculada **separadamente**; só entram os repositórios com as duas medidas ({rb.n:.0f} no (b), porque {resumo['cfr_b_indefinido']} repositório não tem release avaliável). IC de 95% por *bootstrap* de pares ({REPLICAS_BOOTSTRAP} réplicas, semente {SEMENTE}); correção de Holm para os dois testes principais. Convenção para |ρ|: < 0,1 desprezível, < 0,3 fraca, < 0,5 moderada, ≥ 0,5 forte.

## Resultados

| Variante | n | ρ de Spearman | p | p (Holm) | IC 95% do ρ | Leitura |
|---|---:|---:|---:|---:|---|---|
{tabela_principal}

![Dispersão](dispersao_df_cfr.png)

A figura usa escala logarítmica na frequência, que varia de {_n(df.frequencia_deploy_semana.min(), 3)} a {_n(df.frequencia_deploy_semana.max(), 1)} releases/semana (mediana {_n(resumo['mediana_frequencia'], 3)}). A linha preta é a mediana do CFR em oito faixas de frequência com o mesmo número de repositórios.

- **CFR (a):** ρ = **{_n(ra.rho, 3)}** (p = {_g(ra.p)}; Holm {_g(ra.p_holm)}), correlação **{ra.interpretacao}**.
- **CFR (b):** ρ = **{_n(rb.rho, 3)}** (p = {_g(rb.p)}), correlação **{rb.interpretacao}**: os repositórios que mais publicam releases são os que mais têm uma release corretiva logo em seguida.

### Por faixas de frequência (quartis)

| Faixa | n | Frequência (releases/semana) | Mediana CFR (a) | Mediana CFR (b) | CFR (b) esperado ao acaso | Releases com sucessora em 7 dias |
|---|---:|---|---:|---:|---:|---:|
{tabela_faixas}

### As classes DORA caminham juntas?

Proporção de repositórios com CFR **Elite ou High** (≤ 30%) entre os de frequência **alta** (Elite ou High, ≥ 1 release/semana; {resumo['classes_frequencia']['Elite'] + resumo['classes_frequencia']['High']} repositórios) e entre os de frequência baixa (Medium ou Low):

| CFR | n | Frequência alta | Frequência baixa | Razão de chances | Fisher (p) |
|---|---:|---|---|---:|---:|
{tabela_cruzamento}

## Por que o CFR (b) sobe com a frequência: acoplamento mecânico

O CFR (b) conta uma falha quando **qualquer** release corretiva sai em até 7 dias depois. Quanto mais frequentes as releases, mais provável que **alguma** release caia nessa janela, e mais provável que seja um *patch*, mesmo que os *patches* estejam espalhados ao acaso. Isso cria uma relação aritmética entre a frequência e o CFR (b) que **não depende de o repositório ser mais ou menos estável**.

- **Oportunidade de falha.** A fração das releases avaliadas com alguma sucessora em até 7 dias tem ρ = **{_n(mec['frequencia_x_oportunidade']['rho'], 2)}** com a frequência (mediana de {_p(faixas.oportunidade_7d_mediana.iloc[0], 0)} na faixa Q1 e {_p(faixas.oportunidade_7d_mediana.iloc[-1], 0)} na Q4). Já a proporção de releases que são *patch* quase não varia com a frequência (ρ = {_n(mec['frequencia_x_proporcao_corretivas']['rho'], 2)}).
- **Linha de base.** Embaralhando, em cada repositório, quais releases são corretivas ({mec['replicas']} permutações, semente {SEMENTE}; datas e número de corretivas preservados), o CFR (b) esperado ao acaso tem ρ = **{_n(mec['frequencia_x_nulo']['rho'], 3)}** com a frequência, {'maior' if _maior(mec['frequencia_x_nulo']['rho'], rb.rho) else 'menor ou igual'} que o observado ({_n(rb.rho, 3)}). A mediana do esperado é {_p(mec['nulo_mediana'])}, contra {_p(mec['observado_mediana'])} observada; o CFR (b) observado fica abaixo do esperado em {mec['observado_abaixo_do_nulo']} repositórios e acima em {mec['observado_acima_do_nulo']}.
- **Faixa a faixa.** Na faixa de maior frequência, a mediana observada é {_p(faixas.cfr_b_mediana.iloc[-1])} e a esperada ao acaso, {_p(faixas.cfr_b_nulo_mediana.iloc[-1])}; na de menor frequência, {_p(faixas.cfr_b_mediana.iloc[0])} e {_p(faixas.cfr_b_nulo_mediana.iloc[0])}.
- **Correlação parcial.** Controlando pelo CFR (b) esperado ao acaso, o ρ entre frequência e CFR (b) é **{_n(parcial_nulo.rho, 3)}** (p = {_g(parcial_nulo.p)}, n = {int(parcial_nulo.n)}): {'negativo' if _maior(0, parcial_nulo.rho) else 'positivo ou nulo'}, e bem menor em módulo que o ρ bruto.

![Robustez](robustez_rho.png)

A leitura é cautelosa: a linha de base supõe que as corretivas poderiam cair em qualquer release do repositório; ela absorve o efeito aritmético, mas não prova que a relação restante seja causal, e perto de CFR = 0 ou 1 há efeito de piso e teto. O que ela mostra é que o ρ positivo do CFR (b) **não** é evidência de um *trade-off* entre velocidade e estabilidade.

## Robustez

| Subconjunto | n | ρ | p | IC 95% |
|---|---:|---:|---:|---|
{tabela_robustez}

- **Extremos de frequência.** Há {resumo['extremos_de_frequencia']['repositorios_acima']} repositórios acima de Q3 + 1,5·IQR = {_n(resumo['extremos_de_frequencia']['limite_tukey'], 2)} releases/semana; retirá-los não muda a conclusão.
- **Cobertura SemVer.** Restringindo o CFR (b) aos repositórios com pelo menos 80% das releases em SemVer, onde a heurística enxerga os *patches*, o ρ sobe para {_n(semver.rho, 3)} (n = {int(semver.n)}); nesse subconjunto o esperado ao acaso tem ρ = {_n(mec['frequencia_x_nulo_semver']['rho'], 3)}, de novo acima do observado. O acoplamento mecânico é ainda mais forte onde o proxy funciona melhor.
- **Fatores de confusão.** Controlando idade e contribuidores, o ρ é {_n(parcial_idade.loc['a', 'rho'], 3)} para o CFR (a) (p = {_g(parcial_idade.loc['a', 'p'])}) e {_n(parcial_idade.loc['b', 'rho'], 3)} para o CFR (b) (p = {_g(parcial_idade.loc['b', 'p'])}).

## Confronto com H5

A H5 previa ausência de *trade-off*: ρ próximo de zero ou levemente negativo entre frequência e CFR (b), em linha com o DORA, e próximo de zero para o CFR (a).

- **CFR (b) próximo de zero ou levemente negativo:** **{'confirmada' if h5_b else 'não confirmada'}**. O ρ bruto é {_n(rb.rho, 3)} ({rb.interpretacao}). A previsão falha no número, mas o mecanismo acima mostra que o resultado bruto é em grande parte aritmético; depois de descontar a linha de base, o ρ parcial é {_n(parcial_nulo.rho, 3)}.
- **CFR (a) próximo de zero:** **{'confirmada' if h5_a else 'parcialmente confirmada' if h5_a_fraca else 'não confirmada'}**. ρ = {_n(ra.rho, 3)} ({ra.interpretacao}; p = {_g(ra.p)}): estatisticamente distinguível de zero com n = {int(ra.n)}, mas de magnitude {'desprezível' if h5_a else 'pequena'} e, controlando idade e contribuidores, {_n(parcial_idade.loc['a', 'rho'], 3)} (p = {_g(parcial_idade.loc['a', 'p'])}).

**H5 {veredito}**: vale, de forma fraca, para o CFR (a); não vale no valor bruto do CFR (b). Sobre a afirmação do DORA, os dados *open source* **não a confirmam nem a contradizem de forma conclusiva**: no CFR (a), a relação é fraca; no CFR (b), a relação positiva observada é compatível com o efeito aritmético da frequência. Em termos de classes, {_p(cru['a']['proporcao_cfr_alto_na_frequencia_alta'], 0)} dos repositórios de frequência alta têm CFR (a) Elite ou High, contra {_p(cru['a']['proporcao_cfr_alto_na_frequencia_baixa'], 0)} nos de frequência baixa (Fisher p = {_g(cru['a']['fisher_p'])}); no CFR (b), {_p(cru['b']['proporcao_cfr_alto_na_frequencia_alta'], 0)} contra {_p(cru['b']['proporcao_cfr_alto_na_frequencia_baixa'], 0)} (Fisher p = {_g(cru['b']['fisher_p'])}). Correlação não implica causalidade: tamanho da equipe, maturidade e automação de releases podem afetar as duas medidas.

## Limitações

Release é proxy de deploy e CFR é proxy de falha; o CFR (b) depende de uma heurística **sem F1 medido** e, na v1, só lê a tag (ver RQ97). A correlação é calculada sobre as medianas/taxas por repositório, uma por projeto, sem considerar que repositórios muito ativos têm muito mais observações. A linha de base é um diagnóstico, não uma estimativa causal: supõe que as corretivas são permutáveis entre as releases de um repositório. O ρ bruto do (b) não deve ser lido como evidência de *trade-off*. A janela ainda não foi confirmada pelo professor; a amostra de repositórios populares com GitHub Actions não é probabilística; IC por *bootstrap* não é intervalo populacional.

## Reprodução e dicionário das saídas

`python codigo-fonte/analise/rq98_correlacao_df_cfr.py` (opções `--entrada` e `--saida`). Não exige token, rede nem `commits_releases.csv.gz`.

- repositorios.csv: nome_completo, linguagem; frequencia_deploy_semana (releases/semana); cfr_ci e cfr_entrega (fração); classe_frequencia, classe_cfr_a, classe_cfr_b; releases_avaliadas_cfr, releases_corretivas, releases_na_janela, releases_sem_semver (contagens); proporcao_semver (fração das releases da janela); cfr_nulo e cfr_nulo_desvio (CFR (b) esperado ao acaso e desvio, fração); oportunidade_7d (fração das releases avaliadas com sucessora em até 7 dias); cfr_b_menos_nulo (pontos de fração); runs_validos, idade_anos e contribuidores_total.
- correlacoes.csv: variante, rotulo, n, rho, p, ic95_inf, ic95_sup, interpretacao e p_holm.
- robustez.csv: variante, subconjunto, n, rho, p, ic95_inf, ic95_sup e interpretacao (as linhas "parcial" não têm IC).
- faixas_frequencia.csv: quartis de frequência com n, frequencia_min/max (releases/semana), medianas de CFR (a), CFR (b), CFR (b) esperado e oportunidade_7d, e contagens de Elite/High.
- resumo.json: correlações, linha de base, robustez, cruzamento das classes e SHA-256 das entradas. Campos sem estimativa são null.
- dispersao_df_cfr.png/.svg e robustez_rho.png/.svg.

Referências locais: RQ91, RQ95, RQ96 e RQ97 em entregas/laboratorio-03/sprint-03; metricas/variantes.py; H5 em entregas/laboratorio-03/artigo/introducao.tex.
'''


def executar(entrada: Path, saida: Path, replicas_nulo: int = REPLICAS_NULO,
             replicas_bootstrap: int = REPLICAS_BOOTSTRAP):
    fontes = [entrada / n for n in ('metricas_repositorios.csv', 'releases.csv', 'resumo_execucao.json')]
    config = json.loads(fontes[-1].read_text(encoding='utf-8'))['config']
    inicio, fim = limites_da_janela(config['janela']['inicio'], config['janela']['fim'])
    metricas = pd.read_csv(fontes[0])
    releases = pd.read_csv(fontes[1], dtype=str, keep_default_na=False)
    entregas = rq97.preparar_entregas(releases, fim)
    df, correlacoes, robustez, faixas, resumo = analisar(metricas, entregas, inicio, fim, replicas_nulo,
                                                         replicas_bootstrap)
    resumo['janela'] = config['janela']
    resumo['janela_confirmada'] = config.get('janela_confirmada', False) is True
    resumo['fontes_sha256'] = {f'{p.parent.name}/{p.name}': hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in fontes}
    saida.mkdir(parents=True, exist_ok=True)
    colunas = ['nome_completo', 'linguagem', 'frequencia_deploy_semana', 'cfr_ci', 'cfr_entrega', 'classe_frequencia',
               'classe_cfr_a', 'classe_cfr_b', 'releases_avaliadas_cfr', 'releases_corretivas', 'releases_na_janela',
               'releases_sem_semver', 'proporcao_semver', 'cfr_nulo', 'cfr_nulo_desvio', 'oportunidade_7d',
               'cfr_b_menos_nulo', 'runs_validos', 'idade_anos', 'contribuidores_total']
    df[[c for c in colunas if c in df]].to_csv(saida / 'repositorios.csv', index=False, float_format='%.12g')
    correlacoes.to_csv(saida / 'correlacoes.csv', index=False, float_format='%.12g')
    robustez.to_csv(saida / 'robustez.csv', index=False, float_format='%.12g')
    faixas.to_csv(saida / 'faixas_frequencia.csv', index=False, float_format='%.12g')
    (saida / 'resumo.json').write_text(json.dumps(resumo, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
                                       encoding='utf-8')
    graficos(df, correlacoes, robustez, resumo, saida)
    (saida / 'RELATORIO.md').write_text(relatorio(df, correlacoes, robustez, faixas, resumo, config),
                                        encoding='utf-8')
    return resumo


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--entrada', type=Path, default=RAIZ / 'dados/lab03_final')
    p.add_argument('--saida', type=Path, default=RAIZ / 'entregas/laboratorio-03/sprint-03/RQ98')
    args = p.parse_args()
    r = executar(args.entrada, args.saida)
    print(json.dumps({k: r[k] for k in ['principais', 'mecanica']}, ensure_ascii=False, indent=2))
