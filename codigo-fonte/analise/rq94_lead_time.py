"""RQ94 / LAB03 RQ02: lead time for changes nas variantes (a) e (b), sem rede.

python codigo-fonte/analise/rq94_lead_time.py

Lê ``metricas_repositorios.csv`` e ``lead_time_releases.csv`` da coleta final.
A variante (a) é recalculada release a release e conferida com o CSV de
métricas. A (b) depende de ``commits_releases.csv.gz``, que não é versionado
(acima de 100 MB): o valor exportado é usado e conferido pela contagem de
commits e pelos limites que a definição impõe.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path

import pandas as pd
from scipy import stats

CODIGO = Path(__file__).resolve().parents[1]
RAIZ = CODIGO.parent
sys.path.insert(0, str(CODIGO))
from metricas.dora import classificar_lead_time  # noqa: E402
from metricas.lead_time import SEM_ANTERIOR, SEM_COMMITS  # noqa: E402

CLASSES = ['Elite', 'High', 'Medium', 'Low']
#: Tolerância da exportação com seis casas decimais.
TOLERANCIA = 0.00000051
#: Prefixo textual, números da versão (separados por ., _ ou -) e o resto da tag.
_TAG = re.compile(r'^(\D*)(\d+(?:[._-]\d+)*)(.*)$')

AVANCO, REGRESSAO, SERIE_DIFERENTE, SEM_VERSAO = 'avanco', 'regressao', 'serie_diferente', 'sem_versao'


def versao_tag(tag) -> tuple | None:
    """``(prefixo, números)`` de uma tag com versão numérica, ou ``None``.

    Mais tolerante que o SemVer estrito da RQ89: aceita ``v26.7.16.2-stable``,
    ``pkg@1.2.3`` e ``4.6-stable``. Serve só para diagnosticar a ordem das
    linhas de release, não para classificar releases corretivas.
    """
    m = _TAG.match(str(tag or '').strip())
    if not m:
        return None
    return m.group(1).lower(), tuple(int(n) for n in re.split(r'[._-]', m.group(2)))


def relacao_com_anterior(anterior, atual) -> str:
    """Como a tag de R se relaciona com a da release anterior por data.

    ``regressao``: mesma série e versão menor (backport numa linha de
    manutenção mais antiga). ``serie_diferente``: prefixos distintos (pacotes de
    um monorepo, por exemplo). Nos dois casos o ``compare`` mistura linhas de
    release e o lead time de R não mede só o trabalho novo de R.
    """
    a, b = versao_tag(anterior), versao_tag(atual)
    if a is None or b is None:
        return SEM_VERSAO
    if a[0] != b[0]:
        return SERIE_DIFERENTE
    return REGRESSAO if b[1] < a[1] else AVANCO


def estatisticas(serie) -> dict:
    s = pd.Series(serie, dtype=float).dropna()
    if s.empty:
        return dict(n=0, mediana=None, q1=None, q3=None, iqr=None, minimo=None, maximo=None)
    q1, mediana, q3 = (float(s.quantile(q, interpolation='linear')) for q in [.25, .5, .75])
    return dict(n=len(s), mediana=mediana, q1=q1, q3=q3, iqr=q3 - q1,
                minimo=float(s.min()), maximo=float(s.max()))


def booleanos(serie: pd.Series) -> pd.Series:
    valores = serie.astype(str).str.lower().map({'true': True, 'false': False})
    if valores.isna().any():
        raise ValueError(f'Booleano ausente/inválido: {serie.name}')
    return valores.astype(bool)


def _validar(metricas, releases):
    for tabela, colunas in [
            (metricas, {'nome_completo', 'linguagem', 'releases_janela', 'lead_time_release_mediana_dias',
                        'lead_time_commit_mediana_dias', 'releases_com_lead_time', 'commits_com_lead_time',
                        'releases_sem_anterior', 'releases_sem_commits', 'releases_compare_indisponivel',
                        'releases_compare_truncado', 'commits_negativos', 'classe_lead_time'}),
            (releases, {'nome_completo', 'tag_name', 'anterior', 'published_at', 'commits',
                        'commits_negativos', 'truncado', 'lead_time_dias', 'motivo'})]:
        faltantes = colunas - set(tabela.columns)
        if faltantes:
            raise ValueError(f'Colunas obrigatórias ausentes: {sorted(faltantes)}')
    if metricas.empty or metricas.nome_completo.isna().any() or metricas.nome_completo.duplicated().any():
        raise ValueError('Amostra vazia, identificadores ausentes ou repositórios duplicados.')
    # A mesma tag pode ser republicada (duas releases); a anterior as distingue.
    if releases.nome_completo.isna().any() or releases.duplicated(['nome_completo', 'tag_name', 'anterior']).any():
        raise ValueError('Releases com identificadores ausentes ou duplicados.')
    if not set(releases.nome_completo).issubset(set(metricas.nome_completo)):
        raise ValueError('Releases de repositórios fora da amostra.')
    if (releases.lead_time_dias.dropna() < 0).any():
        raise ValueError('Lead time negativo no CSV de releases.')


def _reconciliar(df, metricas):
    """Confere a (a) recalculada e as contagens; diverge = erro, não omissão."""
    salvo = metricas.set_index('nome_completo').loc[df.nome_completo]
    pares = [('lead_time_a_dias', 'lead_time_release_mediana_dias'),
             ('releases_com_lead_time', 'releases_com_lead_time'),
             ('commits_com_lead_time', 'commits_com_lead_time'),
             ('releases_sem_anterior', 'releases_sem_anterior'),
             ('releases_sem_commits', 'releases_sem_commits'),
             ('commits_negativos', 'commits_negativos'),
             ('releases_janela', 'releases_janela')]
    for calculado, exportado in pares:
        a = df[calculado].to_numpy(dtype=float)
        b = pd.to_numeric(salvo[exportado], errors='raise').to_numpy(dtype=float)
        ausentes = pd.isna(a) != pd.isna(b)
        diferentes = ~pd.isna(a) & ~pd.isna(b) & (abs(a - b) > TOLERANCIA)
        if ausentes.any() or diferentes.any():
            nome = df.nome_completo[ausentes | diferentes].iloc[0]
            raise ValueError(f'Métrica não reconciliada em {nome}: {exportado}')
    if not (df.classe_lead_time_a.fillna('') == salvo.classe_lead_time.fillna('').to_numpy()).all():
        raise ValueError('Classe de lead time diverge do CSV de métricas.')


def analisar(metricas: pd.DataFrame, releases: pd.DataFrame):
    _validar(metricas, releases)
    rel = releases.copy()
    rel['truncado'] = booleanos(rel.truncado)
    rel['lead_time_dias'] = pd.to_numeric(rel.lead_time_dias, errors='raise')
    rel['commits_validos'] = rel.commits - rel.commits_negativos
    rel['relacao_anterior'] = [relacao_com_anterior(a, b) if not pd.isna(a) else SEM_VERSAO
                               for a, b in zip(rel.anterior, rel.tag_name)]
    rel['linha_intercalada'] = rel.relacao_anterior.isin([REGRESSAO, SERIE_DIFERENTE])
    com_lt = rel.loc[rel.lead_time_dias.notna()]
    grupos = com_lt.groupby('nome_completo')

    df = metricas[['nome_completo', 'linguagem']].copy().sort_values('nome_completo').reset_index(drop=True)
    contar = rel.groupby('nome_completo')
    df['releases_janela'] = df.nome_completo.map(contar.size()).fillna(0).astype(int)
    df['releases_com_lead_time'] = df.nome_completo.map(grupos.size()).fillna(0).astype(int)
    for motivo, coluna in [(SEM_ANTERIOR, 'releases_sem_anterior'), (SEM_COMMITS, 'releases_sem_commits')]:
        df[coluna] = df.nome_completo.map(rel.loc[rel.motivo == motivo].groupby('nome_completo').size()) \
            .fillna(0).astype(int)
    df['commits_com_lead_time'] = df.nome_completo.map(grupos.commits_validos.sum()).fillna(0).astype(int)
    df['commits_negativos'] = df.nome_completo.map(contar.commits_negativos.sum()).fillna(0).astype(int)
    df['commits_por_release_mediana'] = df.nome_completo.map(grupos.commits_validos.median())

    df['lead_time_a_dias'] = df.nome_completo.map(grupos.lead_time_dias.median())
    df['lead_time_a_q1_dias'] = df.nome_completo.map(grupos.lead_time_dias.quantile(.25))
    df['lead_time_a_q3_dias'] = df.nome_completo.map(grupos.lead_time_dias.quantile(.75))
    df['lead_time_a_max_dias'] = df.nome_completo.map(grupos.lead_time_dias.max())
    df['lead_time_b_dias'] = df.nome_completo.map(
        pd.to_numeric(metricas.set_index('nome_completo').lead_time_commit_mediana_dias, errors='raise'))
    df['classe_lead_time_a'] = df.lead_time_a_dias.map(lambda v: None if pd.isna(v) else classificar_lead_time(v))
    df['classe_lead_time_b'] = df.lead_time_b_dias.map(lambda v: None if pd.isna(v) else classificar_lead_time(v))
    _reconciliar(df, metricas)

    # A (b) não é recalculável sem o CSV de commits; a definição impõe limites.
    sem_b = df.lead_time_b_dias.isna() != df.lead_time_a_dias.isna()
    fora = df.lead_time_b_dias > df.lead_time_a_max_dias + TOLERANCIA
    if sem_b.any() or fora.any() or (df.lead_time_b_dias < 0).any():
        raise ValueError('Lead time (b) incompatível com as releases: ausente, negativo ou acima do máximo da (a).')

    df['diferenca_a_menos_b_dias'] = df.lead_time_a_dias - df.lead_time_b_dias
    df['razao_b_sobre_a'] = df.lead_time_b_dias / df.lead_time_a_dias
    df['b_menor_que_a'] = df.lead_time_b_dias < df.lead_time_a_dias
    notas = {c: 4 - i for i, c in enumerate(CLASSES)}
    df['passos_classe_b_menos_a'] = df.classe_lead_time_b.map(notas) - df.classe_lead_time_a.map(notas)
    df['mudou_classe'] = df.classe_lead_time_a != df.classe_lead_time_b

    # Robustez da (a) sem releases cujo compare mistura linhas de release.
    limpas = com_lt.loc[~com_lt.linha_intercalada].groupby('nome_completo').lead_time_dias
    df['releases_linha_intercalada'] = df.nome_completo.map(
        com_lt.loc[com_lt.linha_intercalada].groupby('nome_completo').size()).fillna(0).astype(int)
    df['lead_time_a_sem_intercaladas_dias'] = df.nome_completo.map(limpas.median())
    df['classe_lead_time_a_sem_intercaladas'] = df.lead_time_a_sem_intercaladas_dias.map(
        lambda v: None if pd.isna(v) else classificar_lead_time(v))

    est = pd.DataFrame([dict(variante=nome, **estatisticas(df[coluna])) for nome, coluna in [
        ('a_por_release', 'lead_time_a_dias'), ('b_por_commit', 'lead_time_b_dias'),
        ('a_sem_linhas_intercaladas', 'lead_time_a_sem_intercaladas_dias'),
        ('diferenca_a_menos_b', 'diferenca_a_menos_b_dias'), ('razao_b_sobre_a', 'razao_b_sobre_a')]])

    linhas = []
    for variante, coluna in [('a', 'classe_lead_time_a'), ('b', 'classe_lead_time_b'),
                             ('a_sem_intercaladas', 'classe_lead_time_a_sem_intercaladas')]:
        contagem = df[coluna].value_counts().reindex(CLASSES, fill_value=0)
        validos = int(df[coluna].notna().sum())
        for classe, n in contagem.items():
            linhas.append(dict(variante=variante, classe=classe, repositorios=int(n),
                               percentual=n / validos * 100 if validos else None))
    classes = pd.DataFrame(linhas)
    transicoes = pd.crosstab(pd.Categorical(df.classe_lead_time_a, CLASSES),
                             pd.Categorical(df.classe_lead_time_b, CLASSES), dropna=False)
    transicoes.index.name, transicoes.columns.name = 'classe_a', 'classe_b'

    pareados = df.dropna(subset=['lead_time_a_dias', 'lead_time_b_dias'])
    diferencas = pareados.diferenca_a_menos_b_dias
    wilcoxon = None
    if (diferencas != 0).any():
        teste = stats.wilcoxon(pareados.lead_time_a_dias, pareados.lead_time_b_dias, zero_method='wilcox')
        nz = diferencas[diferencas != 0]
        postos = nz.abs().rank()
        # Correlação rank-bisserial pareada: positiva = (a) maior que (b).
        rbc = float((postos[nz > 0].sum() - postos[nz < 0].sum()) / postos.sum())
        wilcoxon = dict(n=len(pareados), estatistica=float(teste.statistic), p_valor=float(teste.pvalue),
                        rank_bisserial=rbc)

    def spearman(x, y):
        juntos = pd.concat([x, y], axis=1).dropna()
        if len(juntos) < 3 or juntos.iloc[:, 0].nunique() < 2 or juntos.iloc[:, 1].nunique() < 2:
            return dict(n=len(juntos), rho=None, p_valor=None)
        r = stats.spearmanr(juntos.iloc[:, 0], juntos.iloc[:, 1])
        return dict(n=len(juntos), rho=float(r.statistic), p_valor=float(r.pvalue))

    tamanho = dict(
        repositorio_commits_por_release_vs_razao_b_sobre_a=spearman(
            df.commits_por_release_mediana, df.razao_b_sobre_a),
        repositorio_commits_por_release_vs_diferenca_a_menos_b=spearman(
            df.commits_por_release_mediana, df.diferenca_a_menos_b_dias),
        release_commits_vs_lead_time_a=spearman(com_lt.commits_validos, com_lt.lead_time_dias))

    total_commits = int(df.commits_com_lead_time.sum())
    top10 = int(df.commits_com_lead_time.nlargest(10).sum())
    resumo = dict(
        repositorios=len(df), releases_janela=int(df.releases_janela.sum()),
        releases_com_lead_time=int(df.releases_com_lead_time.sum()),
        releases_sem_anterior=int(df.releases_sem_anterior.sum()),
        releases_sem_commits=int(df.releases_sem_commits.sum()),
        releases_compare_indisponivel=int(pd.to_numeric(metricas.releases_compare_indisponivel).sum()),
        releases_compare_truncado=int(rel.truncado.sum()),
        commits_com_lead_time=total_commits, commits_negativos=int(df.commits_negativos.sum()),
        participacao_commits_top10_repositorios=top10 / total_commits if total_commits else None,
        estatisticas=json.loads(est.to_json(orient='records', force_ascii=False)),
        repositorios_b_menor_que_a=int(pareados.b_menor_que_a.sum()),
        repositorios_b_igual_a=int((diferencas == 0).sum()),
        repositorios_b_maior_que_a=int((diferencas < 0).sum()),
        repositorios_mudam_de_classe=int(pareados.mudou_classe.sum()),
        passos_classe_b_menos_a=df.passos_classe_b_menos_a.value_counts().sort_index()
            .rename(lambda k: str(int(k))).astype(int).to_dict(),
        wilcoxon_a_vs_b=wilcoxon, tamanho_da_release=tamanho,
        relacao_com_anterior=com_lt.relacao_anterior.value_counts().astype(int).to_dict(),
        releases_linha_intercalada=int(com_lt.linha_intercalada.sum()),
        repositorios_com_linha_intercalada=int((df.releases_linha_intercalada > 0).sum()),
        commits_em_releases_intercaladas=int(com_lt.loc[com_lt.linha_intercalada].commits_validos.sum()),
        repositorios_mudam_classe_sem_intercaladas=int(
            (df.classe_lead_time_a_sem_intercaladas.notna()
             & (df.classe_lead_time_a_sem_intercaladas != df.classe_lead_time_a)).sum()),
        repositorios_sem_release_apos_filtro=int(df.lead_time_a_sem_intercaladas_dias.isna().sum()))
    detalhes = rel[['nome_completo', 'tag_name', 'anterior', 'published_at', 'commits', 'commits_negativos',
                    'commits_validos', 'lead_time_dias', 'motivo', 'relacao_anterior', 'linha_intercalada']]
    return df, detalhes, est, classes, transicoes, resumo


def graficos(df, classes, destino):
    cache = RAIZ / 'dados/.cache/matplotlib'
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR', str(cache))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    matplotlib.rcParams['svg.hashsalt'] = 'rq94'
    cores = {'a': '#377EB8', 'b': '#B58A27'}
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.8), constrained_layout=True)
    for variante, coluna, rotulo in [('a', 'lead_time_a_dias', '(a) por release'),
                                     ('b', 'lead_time_b_dias', '(b) por commit')]:
        v = df[coluna].dropna().sort_values().to_numpy()
        axes[0].step(v, [(i + 1) / len(v) * 100 for i in range(len(v))], where='post',
                     color=cores[variante], label=f'{rotulo} · n = {len(v)}')
    axes[0].set_xscale('log')
    axes[0].set(xlabel='Mediana do repositório (dias, log)', ylabel='Repositórios (%)',
                title='Distribuição acumulada', ylim=(0, 101))
    axes[0].legend(loc='upper left', fontsize=9)
    pares = df.dropna(subset=['lead_time_a_dias', 'lead_time_b_dias'])
    axes[1].scatter(pares.lead_time_a_dias, pares.lead_time_b_dias, s=14, alpha=.6, color='#555555')
    limite = (min(pares.lead_time_a_dias.min(), pares.lead_time_b_dias.min()) / 2,
              max(pares.lead_time_a_dias.max(), pares.lead_time_b_dias.max()) * 2)
    axes[1].plot(limite, limite, color='#8D5959', linewidth=1, label='(a) = (b)')
    axes[1].set(xscale='log', yscale='log', xlim=limite, ylim=limite, xlabel='(a) por release (dias)',
                ylabel='(b) por commit (dias)', title='Variantes pareadas por repositório')
    for ax in axes[:2]:
        for corte in [1, 7, 30]:
            ax.axvline(corte, color='gray', linestyle=':', linewidth=1)
    for corte in [1, 7, 30]:
        axes[1].axhline(corte, color='gray', linestyle=':', linewidth=1)
    axes[1].legend(loc='upper left', fontsize=9)
    x = range(len(CLASSES))
    for deslocamento, variante, rotulo in [(-.2, 'a', '(a)'), (.2, 'b', '(b)')]:
        g = classes.loc[classes.variante == variante].set_index('classe').reindex(CLASSES)
        barras = axes[2].bar([i + deslocamento for i in x], g.repositorios, width=.4,
                             color=cores[variante], label=rotulo)
        axes[2].bar_label(barras, padding=2, fontsize=8)
    axes[2].set_xticks(list(x), CLASSES)
    axes[2].set(title='Classes DORA de lead time', ylabel='Repositórios',
                ylim=(0, classes.repositorios.max() * 1.2))
    axes[2].legend(fontsize=9)
    fig.suptitle('RQ94 · Lead time for changes nas variantes (a) e (b)')
    for ext in ['png', 'svg']:
        fig.savefig(destino / f'lead_time_variantes.{ext}', dpi=180, metadata={'Date': None} if ext == 'svg' else None)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.8), constrained_layout=True)
    cor = df.releases_linha_intercalada > 0
    for mascara, rotulo, c in [(~cor, 'sem linha intercalada', '#377EB8'),
                               (cor, 'com linha intercalada', '#B58A27')]:
        ax.scatter(df.loc[mascara, 'commits_por_release_mediana'], df.loc[mascara, 'razao_b_sobre_a'],
                   s=14, alpha=.7, color=c, label=rotulo)
    ax.axhline(1, color='#8D5959', linewidth=1)
    ax.set(xscale='log', yscale='log', xlabel='Commits por release (mediana do repositório, log)',
           ylabel='(b) / (a) (log)', title='Tamanho da release e razão entre as variantes')
    ax.legend(fontsize=9)
    for ext in ['png', 'svg']:
        fig.savefig(destino / f'tamanho_release.{ext}', dpi=180, metadata={'Date': None} if ext == 'svg' else None)
    plt.close(fig)


def _n(x, casas=2):
    return 'não estimável' if x is None or (isinstance(x, float) and math.isnan(x)) else f'{x:.{casas}f}'


def relatorio(df, est, classes, transicoes, resumo, config):
    e = {r['variante']: r for r in resumo['estatisticas']}
    a, b, s = e['a_por_release'], e['b_por_commit'], e['a_sem_linhas_intercaladas']
    w = resumo['wilcoxon_a_vs_b']
    t = resumo['tamanho_da_release']
    tabela_est = '\n'.join(
        f"| {nome} | {r['n']} | {_n(r['mediana'])} | {_n(r['q1'])}–{_n(r['q3'])} | {_n(r['iqr'])} | "
        f"{_n(r['minimo'], 4)}–{_n(r['maximo'])} |"
        for nome, r in [('(a) por release', a), ('(b) por commit', b), ('(a) sem linhas intercaladas', s)])
    pivot = classes.pivot(index='classe', columns='variante', values='repositorios').reindex(CLASSES)
    pct = classes.pivot(index='classe', columns='variante', values='percentual').reindex(CLASSES)
    tabela_cls = '\n'.join(f'| {c} | {int(pivot.a[c])} ({pct.a[c]:.1f}%) | {int(pivot.b[c])} ({pct.b[c]:.1f}%) | '
                           f'{int(pivot.a_sem_intercaladas[c])} ({pct.a_sem_intercaladas[c]:.1f}%) |'
                           for c in CLASSES)
    tabela_tr = '\n'.join(f'| **{c}** | ' + ' | '.join(str(int(transicoes.loc[c, d])) for d in CLASSES) + ' |'
                          for c in CLASSES)
    passos = resumo['passos_classe_b_menos_a']
    melhora = sum(v for k, v in passos.items() if int(k) > 0)
    piora = sum(v for k, v in passos.items() if int(k) < 0)
    rel = resumo['relacao_com_anterior']
    h2a = ('compatível' if a['mediana'] is not None and 7 <= a['mediana'] else 'fora da faixa prevista')
    h2b = ('confirmada' if b['mediana'] < a['mediana'] and resumo['repositorios_b_menor_que_a'] > len(df) / 2
           else 'não confirmada')
    r_rep = t['repositorio_commits_por_release_vs_razao_b_sobre_a']
    r_dif = t['repositorio_commits_por_release_vs_diferenca_a_menos_b']
    r_rel = t['release_commits_vs_lead_time_a']
    if r_rep['rho'] is None or r_rep['p_valor'] >= .05:
        leitura_tamanho = 'sem associação detectável entre tamanho da release e razão (b)/(a); parte não avaliável'
    elif r_rep['rho'] < 0:
        leitura_tamanho = ('compatível: quanto maiores as releases, menor a (b) em relação à (a), '
                           'isto é, a distância entre as variantes cresce com o tamanho')
    else:
        leitura_tamanho = 'contrária: quanto maiores as releases, mais a (b) se aproxima ou supera a (a)'
    maioria = resumo['repositorios_b_menor_que_a'] > len(df) / 2
    classe_b = classificar_lead_time(b['mediana']) if b['mediana'] is not None else 'não estimável'
    aviso = 'confirmada na configuração' if config.get('janela_confirmada') is True else \
        '**ainda não confirmada pelo professor na configuração**'
    maiores = df.nlargest(5, 'commits_com_lead_time')
    tabela_maiores = '\n'.join(
        f'| {r.nome_completo} | {r.commits_com_lead_time} | {int(r.releases_linha_intercalada)} | '
        f'{_n(r.lead_time_a_dias)} | {_n(r.lead_time_b_dias)} |' for r in maiores.itertuples())
    return f'''# RQ94 — RQ02: Lead time for changes nas duas variantes

## Pergunta e método

Qual o tempo entre um commit e seu respectivo deploy, por release e por commit? Análise local de **{len(df)} repositórios**, janela UTC inclusiva {config['janela']['inicio']} a {config['janela']['fim']}, {aviso}.

Para cada release R da janela (publicada, não draft, não pré-release), os commits são os do intervalo entre a release publicada imediatamente anterior e R (clone git parcial; `fonte_commits = git` em todos os repositórios). Data do commit = `commit.author.date`; data de R = `published_at`.

- **(a) por release:** lead time de R = data de R − commit mais antigo de R; valor do repositório = mediana entre as releases.
- **(b) por commit:** cada commit de R contribui com data de R − data dele; valor do repositório = mediana de **todos** os commits de todas as releases (não é mediana de medianas).

Estatística da amostra: mediana das medianas dos repositórios, Q1/Q3 por interpolação linear e IQR. Classes pelos cortes da disciplina: Elite < 1 dia; High 1 a < 7; Medium 7 a < 30; Low ≥ 30 dias.

## Cobertura e auditoria

- Releases na janela: **{resumo['releases_janela']}**; com lead time: **{resumo['releases_com_lead_time']}**.
- Ignoradas: **{resumo['releases_sem_anterior']}** primeira release da história (sem anterior) e **{resumo['releases_sem_commits']}** sem commits novos. Compare indisponível: {resumo['releases_compare_indisponivel']}; truncado: {resumo['releases_compare_truncado']}.
- Commits com lead time: **{resumo['commits_com_lead_time']}**; descartados por data de autoria posterior à release: **{resumo['commits_negativos']}**.
- A variante (a) foi **recalculada** a partir de `lead_time_releases.csv` e bate com `metricas_repositorios.csv` em todos os repositórios (tolerância de seis casas), assim como as contagens de releases e commits e a classe de lead time.
- A variante (b) **não pode ser recalculada** aqui: o arquivo por commit (`commits_releases.csv.gz`) passa de 100 MB e não foi versionado. O valor exportado foi conferido pela soma dos commits por release e pelos limites da definição (0 ≤ (b) ≤ maior lead time (a) do repositório).

## Resultados

| Variante | n | Mediana (dias) | Q1–Q3 | IQR | Mín.–máx. |
|---|---:|---:|---:|---:|---:|
{tabela_est}

| Classe | (a) por release | (b) por commit | (a) sem linhas intercaladas |
|---|---:|---:|---:|
{tabela_cls}

![Lead time nas variantes](lead_time_variantes.png)

### Comparação pareada

Em **{resumo['repositorios_b_menor_que_a']} repositórios** a (b) é menor que a (a), em **{resumo['repositorios_b_maior_que_a']}** é maior e em **{resumo['repositorios_b_igual_a']}** é igual. A razão (b)/(a) tem mediana **{_n(e['razao_b_sobre_a']['mediana'])}** (Q1–Q3 {_n(e['razao_b_sobre_a']['q1'])}–{_n(e['razao_b_sobre_a']['q3'])}). Wilcoxon pareado (a vs. b): W = {_n(w['estatistica'], 1) if w else 'não estimável'}, p = {_n(w['p_valor'], 4) if w else 'não estimável'}, correlação rank-bisserial = {_n(w['rank_bisserial'], 3) if w else 'não estimável'} (positiva = (a) maior).

**{resumo['repositorios_mudam_de_classe']} repositórios ({resumo['repositorios_mudam_de_classe'] / len(df) * 100:.1f}%) mudam de classe** ao trocar (a) por (b): {melhora} melhoram e {piora} pioram. Matriz de transição (linhas: (a); colunas: (b)):

| (a) \\ (b) | ''' + ' | '.join(CLASSES) + f''' |
|---|---:|---:|---:|---:|
{tabela_tr}

Por que a (b) pode ser **maior** que a (a)? Em cada release, o lead time de cada commit é no máximo o da (a). Mas a (b) do repositório pondera as releases pelo número de commits, e a (a) dá peso igual a cada release. Quando poucas releases grandes concentram commits antigos e muitas releases pequenas são rápidas, a mediana por commit cai dentro das releases grandes e supera a mediana por release.

### Tamanho da release

- Por release: Spearman entre commits e lead time (a): ρ = {_n(r_rel['rho'], 3)} (p = {_n(r_rel['p_valor'], 4)}, n = {r_rel['n']}). Quanto mais commits, mais distante tende a estar o commit mais antigo, o que é quase mecânico na definição (a).
- Por repositório: Spearman entre a mediana de commits por release e a razão (b)/(a): ρ = {_n(r_rep['rho'], 3)} (p = {_n(r_rep['p_valor'], 4)}, n = {r_rep['n']}); e a diferença (a) − (b) em dias: ρ = {_n(r_dif['rho'], 3)} (p = {_n(r_dif['p_valor'], 4)}).

![Tamanho da release e razão entre as variantes](tamanho_release.png)

### Linhas de release intercaladas

A "release anterior" é a anterior **por data**. Em projetos com várias linhas de manutenção (backports) ou monorepos, ela pode ser de outra linha, e o intervalo de commits passa a misturar trabalho que não pertence a R. Diagnosticamos isso pela tag (prefixo e números da versão): das releases com lead time, {rel.get(AVANCO, 0)} avançam a versão da anterior, **{rel.get(REGRESSAO, 0)} regridem** (backport numa linha mais antiga), **{rel.get(SERIE_DIFERENTE, 0)} são de outra série** (prefixo diferente) e {rel.get(SEM_VERSAO, 0)} não têm versão numérica.

As {resumo['releases_linha_intercalada']} releases intercaladas estão em **{resumo['repositorios_com_linha_intercalada']} repositórios** e somam **{resumo['commits_em_releases_intercaladas']} commits**. Os 10 repositórios com mais commits concentram **{resumo['participacao_commits_top10_repositorios'] * 100:.1f}%** de todos os commits:

| Repositório | Commits | Releases intercaladas | (a) dias | (b) dias |
|---|---:|---:|---:|---:|
{tabela_maiores}

Como análise de robustez (não substitui a definição comum da turma), recalculamos a (a) sem as releases intercaladas: mediana **{_n(s['mediana'])} dias** (n = {s['n']}); **{resumo['repositorios_mudam_classe_sem_intercaladas']} repositórios** mudam de classe e {resumo['repositorios_sem_release_apos_filtro']} ficam sem release. A (b) não pode ser refeita sem o arquivo por commit.

## Confronto com H2

A H2 previa (a) com mediana na faixa de semanas (Medium, muitas vezes Low) e (b) sistematicamente menor, na faixa de dias, com diferença crescente com o tamanho das releases.

- **(a):** mediana de {_n(a['mediana'])} dias, classe {classificar_lead_time(a['mediana'])}; Medium e Low somam {int(pivot.a['Medium'] + pivot.a['Low'])} repositórios. Faixa prevista: **{h2a}**.
- **(b) sistematicamente menor que (a):** **{h2b}**. A mediana da amostra na (b) é {_n(b['mediana'])} dias (classe {classe_b}), {'acima' if b['mediana'] > a['mediana'] else 'abaixo'} da (a). A (b) é menor em {resumo['repositorios_b_menor_que_a']} repositórios ({'maioria' if maioria else 'minoria'}), mas maior em {resumo['repositorios_b_maior_que_a']}, e o Wilcoxon pareado {'não ' if not w or w['p_valor'] >= .05 else ''}rejeita a igualdade a 5% (rank-bisserial {_n(w['rank_bisserial'], 3) if w else 'não estimável'}). Não há deslocamento para a faixa de dias.
- **Diferença cresce com o tamanho das releases:** {leitura_tamanho} (ρ = {_n(r_rep['rho'], 3)} entre commits por release e (b)/(a)). O mecanismo da H2 (um commit antigo "explode" a (a) e a (b) o dilui) aparece nos repositórios de releases grandes; nos de releases pequenas, a ponderação por commit faz a (b) superar a (a) (ver explicação acima).

A troca de variante muda a classe de {resumo['repositorios_mudam_de_classe']} repositórios. Esse dado alimenta a RQ07 (sensibilidade): o lead time sozinho já desloca a classificação de uma parte relevante da amostra.

## Limitações

Release publicada é proxy de deploy; numa biblioteca, quem faz deploy é o usuário. `commit.author.date` é preservada em rebase e cherry-pick, o que alonga o lead time de commits reaproveitados. A ordem por data mistura linhas de release (seção acima); a definição comum da turma foi mantida e o efeito é reportado à parte. A heurística de linha intercalada lê só a tag e pode errar em esquemas de versão sem número ou com datas. A (b) foi verificada, mas não recalculada. Seleção de repositórios populares, não probabilística. IQR é dispersão, não intervalo de confiança.

## Reprodução e dicionário das saídas

`python codigo-fonte/analise/rq94_lead_time.py` (opções `--entrada` e `--saida`). Não exige token nem rede.

- repositorios.csv: nome_completo, linguagem; releases_janela, releases_com_lead_time, releases_sem_anterior, releases_sem_commits (contagens); commits_com_lead_time, commits_negativos (contagens); commits_por_release_mediana (commits); lead_time_a_dias, lead_time_a_q1_dias, lead_time_a_q3_dias, lead_time_a_max_dias e lead_time_b_dias (dias); classe_lead_time_a/b; diferenca_a_menos_b_dias (dias); razao_b_sobre_a (adimensional); b_menor_que_a, mudou_classe (booleanos); passos_classe_b_menos_a (−3 a 3, positivo = (b) melhora); releases_linha_intercalada (contagem); lead_time_a_sem_intercaladas_dias (dias) e classe_lead_time_a_sem_intercaladas.
- releases.csv: uma linha por release da janela; commits, commits_negativos, commits_validos (contagens), lead_time_dias (a, dias; vazio sem lead time), motivo, relacao_anterior (avanco, regressao, serie_diferente, sem_versao) e linha_intercalada.
- estatisticas.csv: variante, n, mediana, q1, q3, iqr, minimo, maximo (dias; a razão é adimensional).
- classes_dora.csv: variante (a, b, a_sem_intercaladas), classe, repositórios e percentual sobre os classificados.
- transicoes_classes.csv: matriz classe (a) × classe (b), em repositórios.
- resumo.json: cobertura, estatísticas, comparação pareada, correlações, linhas intercaladas e SHA-256 das entradas. Campos sem estimativa são null.
- lead_time_variantes.png/.svg e tamanho_release.png/.svg.

Referências locais: enunciado LAB03, seções 3 e 5 (RQ02); metricas/lead_time.py; metricas/dora.py; H2 em entregas/laboratorio-03/artigo/introducao.tex.
'''


def executar(entrada: Path, saida: Path):
    fontes = [entrada / n for n in ['metricas_repositorios.csv', 'lead_time_releases.csv', 'resumo_execucao.json']]
    config = json.loads(fontes[2].read_text(encoding='utf-8'))['config']
    metricas = pd.read_csv(fontes[0])
    releases = pd.read_csv(fontes[1])
    df, detalhes, est, classes, transicoes, resumo = analisar(metricas, releases)
    resumo['janela'] = config['janela']
    resumo['janela_confirmada'] = config.get('janela_confirmada', False) is True
    resumo['fontes_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in fontes}
    saida.mkdir(parents=True, exist_ok=True)
    for nome, tabela in [('repositorios', df), ('releases', detalhes), ('estatisticas', est),
                         ('classes_dora', classes)]:
        tabela.to_csv(saida / f'{nome}.csv', index=False, float_format='%.12g')
    transicoes.to_csv(saida / 'transicoes_classes.csv')
    (saida / 'resumo.json').write_text(json.dumps(resumo, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
                                       encoding='utf-8')
    graficos(df, classes, saida)
    (saida / 'RELATORIO.md').write_text(relatorio(df, est, classes, transicoes, resumo, config), encoding='utf-8')
    return resumo


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--entrada', type=Path, default=RAIZ / 'dados/lab03_final')
    p.add_argument('--saida', type=Path, default=RAIZ / 'entregas/laboratorio-03/sprint-03/RQ94')
    args = p.parse_args()
    r = executar(args.entrada, args.saida)
    print(json.dumps({k: r[k] for k in ['estatisticas', 'repositorios_b_menor_que_a', 'repositorios_mudam_de_classe',
                                        'wilcoxon_a_vs_b']}, ensure_ascii=False, indent=2))
