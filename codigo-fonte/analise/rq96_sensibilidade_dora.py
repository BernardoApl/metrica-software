"""RQ96 / LAB03 RQ07: sensibilidade da classificação DORA à definição operacional, sem rede.

python codigo-fonte/analise/rq96_sensibilidade_dora.py

Monta combinações de definições (unidade de deploy, variante de lead time e de
CFR), classifica cada repositório em cada uma com ``metricas/dora.py`` e mede,
por par, a proporção que muda de classe geral e o kappa de Cohen ponderado
(pesos lineares). A C1 é a referência da RQ95.

Variantes calculadas aqui a partir dos CSVs da coleta final:

- frequência com pré-releases: releases publicadas (draft = false) na janela,
  com ou sem ``prerelease``;
- frequência por tag: tags cujo commit apontado tem ``commit.author.date`` na
  janela (``tags.csv``; a tag em si não tem data na API);
- CFR (b): ``metricas.variantes.cfr_entrega`` com a heurística padrão. Ela usa
  só as tags (``patch_semver_v1``), então não depende do CSV de commits.

Lead time (a) e (b) vêm de ``metricas_repositorios.csv`` e são sempre os da
unidade release: recalculá-los para pré-releases e tags exige os commits de
cada intervalo, que não estão versionados.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from itertools import combinations
from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score

CODIGO = Path(__file__).resolve().parents[1]
RAIZ = CODIGO.parent
sys.path.insert(0, str(CODIGO))
from coleta.coleta_dora import limites_da_janela, semanas_da_janela  # noqa: E402
from metricas import corretiva, dora, variantes  # noqa: E402

CLASSES = ['Elite', 'High', 'Medium', 'Low']
TOLERANCIA = 0.00000051

#: nome -> (unidade de deploy, lead time, CFR, descrição)
COMBINACOES = {
    'C1': ('release', 'a', 'a', 'Referência: release, lead time por release, CFR de CI'),
    'C2': ('release', 'b', 'a', 'Lead time por commit'),
    'C3': ('release', 'a', 'b', 'CFR de entrega (release corretiva)'),
    'C4': ('release', 'b', 'b', 'Lead time por commit e CFR de entrega'),
    'C5': ('release_prerelease', 'a', 'a', 'Pré-releases contam como deploy'),
    'C6': ('tag', 'a', 'a', 'Tags contam como deploy'),
    'C7': ('tag', 'b', 'b', 'Tags, lead time por commit e CFR de entrega'),
}
FREQUENCIA = {'release': 'frequencia_release', 'release_prerelease': 'frequencia_release_prerelease',
              'tag': 'frequencia_tag'}
LEAD = {'a': 'lead_time_release_mediana_dias', 'b': 'lead_time_commit_mediana_dias'}
CFR = {'a': 'cfr_ci', 'b': 'cfr_entrega'}


def booleanos(serie: pd.Series) -> pd.Series:
    valores = serie.astype(str).str.lower().map({'true': True, 'false': False})
    if valores.isna().any():
        raise ValueError(f'Booleano ausente/inválido: {serie.name}')
    return valores.astype(bool)


def _valor(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)


def variantes_por_repositorio(metricas, releases, tags, inicio, fim, heuristica=None):
    """Frequências por unidade de deploy e CFR (b), com conferência da coleta."""
    for tabela, colunas in [
            (metricas, {'nome_completo', 'releases_janela', 'prereleases_janela', 'frequencia_deploy_semana',
                        'lead_time_release_mediana_dias', 'lead_time_commit_mediana_dias', 'cfr_ci',
                        'recuperacao_mediana_horas', 'classe_geral'}),
            (releases, {'nome_completo', 'id', 'tag_name', 'draft', 'prerelease', 'published_at'}),
            (tags, {'nome_completo', 'tag_name', 'dentro_janela', 'status'})]:
        faltantes = colunas - set(tabela.columns)
        if faltantes:
            raise ValueError(f'Colunas obrigatórias ausentes: {sorted(faltantes)}')
    if metricas.empty or metricas.nome_completo.isna().any() or metricas.nome_completo.duplicated().any():
        raise ValueError('Amostra vazia, identificadores ausentes ou repositórios duplicados.')
    if releases.duplicated(['nome_completo', 'id']).any() or tags.duplicated(['nome_completo', 'tag_name']).any():
        raise ValueError('Releases ou tags duplicadas.')
    amostra = set(metricas.nome_completo)
    if not (set(releases.nome_completo) | set(tags.nome_completo)) <= amostra:
        raise ValueError('Releases ou tags de repositórios fora da amostra.')
    if (tags.status != 'ok').any():
        raise ValueError('Tags sem data do commit (status diferente de ok).')

    abertura, fechamento = limites_da_janela(inicio, fim)
    semanas = semanas_da_janela(inicio, fim)
    rel = releases.copy()
    rel['draft'], rel['prerelease'] = booleanos(rel.draft), booleanos(rel.prerelease)
    datas = pd.to_datetime(rel.published_at.replace('', None), utc=True, format='ISO8601')
    na_janela = ~rel.draft & datas.notna() & (datas >= abertura) & (datas <= fechamento)
    df = metricas.sort_values('nome_completo').reset_index(drop=True).copy()
    contar = lambda mascara: df.nome_completo.map(rel.loc[mascara].groupby('nome_completo').size()) \
        .fillna(0).astype(int)  # noqa: E731
    df['releases_contadas'] = contar(na_janela & ~rel.prerelease)
    df['prereleases_contadas'] = contar(na_janela & rel.prerelease)
    if not (df.releases_contadas == df.releases_janela).all() or \
            not (df.prereleases_contadas == df.prereleases_janela).all():
        raise ValueError('Contagem de releases/pré-releases diverge do CSV de métricas.')
    df['tags_janela'] = df.nome_completo.map(
        tags.loc[booleanos(tags.dentro_janela)].groupby('nome_completo').size()).fillna(0).astype(int)
    df['frequencia_release'] = df.releases_contadas / semanas
    if not ((df.frequencia_release - df.frequencia_deploy_semana).abs() <= TOLERANCIA).all():
        raise ValueError('Frequência exportada diverge da recontagem.')
    df['frequencia_release_prerelease'] = (df.releases_contadas + df.prereleases_contadas) / semanas
    df['frequencia_tag'] = df.tags_janela / semanas

    entregas = {}
    grupos = {nome: g for nome, g in rel.groupby('nome_completo')}
    for nome in df.nome_completo:
        registros = []
        for r in (grupos[nome].to_dict('records') if nome in grupos else []):
            if r['published_at']:
                registros.append(dict(r, id=int(r['id'])))
        e = variantes.cfr_entrega(registros, abertura, fechamento, heuristica or variantes.HEURISTICA, {})
        entregas[nome] = e
    df['cfr_entrega'] = df.nome_completo.map(lambda n: entregas[n]['cfr_entrega'])
    df['releases_avaliadas_cfr'] = df.nome_completo.map(lambda n: entregas[n]['releases_avaliadas_cfr'])
    df['releases_falha_cfr'] = df.nome_completo.map(lambda n: entregas[n]['releases_falha_cfr'])
    df['releases_sem_semver'] = df.nome_completo.map(lambda n: entregas[n]['releases_sem_semver'])
    return df


def classificar_combinacoes(df):
    """Uma coluna de classe por métrica variante e a classe geral por combinação."""
    saida = df[['nome_completo']].copy()
    for unidade, coluna in FREQUENCIA.items():
        saida[f'classe_freq_{unidade}'] = df[coluna].map(lambda v: dora.classificar_frequencia(_valor(v)))
    for variante, coluna in LEAD.items():
        saida[f'classe_lead_{variante}'] = df[coluna].map(lambda v: dora.classificar_lead_time(_valor(v)))
    for variante, coluna in CFR.items():
        saida[f'classe_cfr_{variante}'] = df[coluna].map(lambda v: dora.classificar_cfr(_valor(v)))
    saida['classe_recuperacao'] = df.recuperacao_mediana_horas.map(lambda v: dora.classificar_recuperacao(_valor(v)))
    for nome, (unidade, lead, cfr, _) in COMBINACOES.items():
        saida[nome] = [dora.classificacao_geral(c) for c in zip(
            saida[f'classe_freq_{unidade}'], saida[f'classe_lead_{lead}'], saida[f'classe_cfr_{cfr}'],
            saida.classe_recuperacao)]
    if not (saida.C1.fillna('') == df.classe_geral.fillna('')).all():
        raise ValueError('C1 diverge da classe geral exportada.')
    return saida


def comparar(x: pd.Series, y: pd.Series) -> dict:
    """Mudança de classe e kappa ponderado entre duas classificações."""
    juntos = pd.concat([x.rename('x'), y.rename('y')], axis=1).dropna()
    n = len(juntos)
    if not n:
        return dict(n=0, mudam=0, proporcao_mudam=None, melhoram=0, pioram=0, mudam_2_ou_mais=0,
                    kappa_linear=None, concordancia_exata=None)
    a, b = juntos.x.map(dora.NOTAS), juntos.y.map(dora.NOTAS)
    # Kappa indefinido quando só há uma classe nas duas classificações.
    kappa = (cohen_kappa_score(a, b, labels=[1, 2, 3, 4], weights='linear')
             if len(set(a) | set(b)) > 1 else float('nan'))
    mudam = int((a != b).sum())
    return dict(n=n, mudam=mudam, proporcao_mudam=mudam / n, melhoram=int((b > a).sum()),
                pioram=int((b < a).sum()), mudam_2_ou_mais=int(((a - b).abs() >= 2).sum()),
                kappa_linear=None if math.isnan(kappa) else float(kappa), concordancia_exata=1 - mudam / n)


def landis_koch(k) -> str:
    if k is None:
        return 'não estimável'
    for limite, rotulo in [(0, 'pobre'), (.2, 'leve'), (.4, 'razoável'), (.6, 'moderada'), (.8, 'substancial')]:
        if k <= limite:
            return rotulo
    return 'quase perfeita'


def analisar(metricas, releases, tags, inicio, fim, heuristica=None):
    df = variantes_por_repositorio(metricas, releases, tags, inicio, fim, heuristica)
    cls = classificar_combinacoes(df)
    nomes = list(COMBINACOES)

    pares = pd.DataFrame([dict(combinacao_1=p, combinacao_2=q, **comparar(cls[p], cls[q]))
                          for p, q in combinations(nomes, 2)])
    pares['interpretacao_kappa'] = pares.kappa_linear.map(landis_koch)

    metricas_var = pd.DataFrame([dict(metrica=m, referencia=r, alternativa=a, **comparar(cls[r], cls[a]))
                                 for m, r, a in [
        ('frequencia', 'classe_freq_release', 'classe_freq_release_prerelease'),
        ('frequencia', 'classe_freq_release', 'classe_freq_tag'),
        ('lead_time', 'classe_lead_a', 'classe_lead_b'),
        ('cfr', 'classe_cfr_a', 'classe_cfr_b')]])
    metricas_var['interpretacao_kappa'] = metricas_var.kappa_linear.map(landis_koch)

    distrib = []
    for nome in nomes:
        contagem = cls[nome].value_counts().reindex(CLASSES, fill_value=0)
        definidos = int(cls[nome].notna().sum())
        for classe, n in contagem.items():
            distrib.append(dict(combinacao=nome, classe=classe, repositorios=int(n),
                                percentual_definidos=n / definidos * 100 if definidos else None))
        distrib.append(dict(combinacao=nome, classe='Indefinida', repositorios=len(cls) - definidos,
                            percentual_definidos=None))
    distrib = pd.DataFrame(distrib)
    definicoes = pd.DataFrame([dict(combinacao=n, unidade_deploy=u, lead_time=l, cfr=c, descricao=d,
                                    repositorios_classificados=int(cls[n].notna().sum()))
                               for n, (u, l, c, d) in COMBINACOES.items()])

    todas = cls[nomes]
    completos = todas.dropna()
    cls['classes_distintas'] = todas.nunique(axis=1)
    cls['combinacoes_iguais_c1'] = todas.eq(todas.C1, axis=0).sum(axis=1) - 1
    notas = todas.apply(lambda c: c.map(dora.NOTAS))
    cls['amplitude_notas'] = notas.max(axis=1) - notas.min(axis=1)
    estaveis = int((completos.nunique(axis=1) == 1).sum())

    vs_c1 = pares.loc[pares.combinacao_1 == 'C1'].set_index('combinacao_2')
    alternativas = vs_c1.index.tolist()
    mudam_alguma = int((completos[alternativas].ne(completos.C1, axis=0)).any(axis=1).sum())
    tabela = df.merge(cls, on='nome_completo')
    colunas = ['nome_completo', 'linguagem', 'releases_contadas', 'prereleases_contadas', 'tags_janela',
               'frequencia_release', 'frequencia_release_prerelease', 'frequencia_tag',
               'lead_time_release_mediana_dias', 'lead_time_commit_mediana_dias', 'cfr_ci', 'cfr_entrega',
               'releases_avaliadas_cfr', 'releases_falha_cfr', 'releases_sem_semver', 'recuperacao_mediana_horas'] + \
        [c for c in cls.columns if c != 'nome_completo']
    tabela = tabela[[c for c in colunas if c in tabela.columns]]

    def razao(num, den):
        r = (df[num] / df[den]).replace([float('inf')], float('nan'))
        return float(r.median()) if r.notna().any() else None

    resumo = dict(
        repositorios=len(df), heuristica_cfr_entrega=heuristica or variantes.HEURISTICA,
        heuristica_validada_manualmente=False,
        combinacoes={n: dict(unidade_deploy=u, lead_time=l, cfr=c, descricao=d)
                     for n, (u, l, c, d) in COMBINACOES.items()},
        classificados=definicoes.set_index('combinacao').repositorios_classificados.astype(int).to_dict(),
        distribuicao={n: cls[n].value_counts().reindex(CLASSES, fill_value=0).astype(int).to_dict() for n in nomes},
        pares_c1=json.loads(vs_c1.reset_index().to_json(orient='records', force_ascii=False)),
        metricas_variantes=json.loads(metricas_var.to_json(orient='records', force_ascii=False)),
        repositorios_classificados_em_todas=len(completos),
        repositorios_mesma_classe_em_todas=estaveis,
        repositorios_mudam_em_alguma_alternativa=mudam_alguma,
        alternativas_com_mudanca_ge_30pct=[c for c in alternativas if vs_c1.loc[c, 'proporcao_mudam'] >= .30],
        kappa_vs_c1_min=_valor(vs_c1.kappa_linear.min()), kappa_vs_c1_max=_valor(vs_c1.kappa_linear.max()),
        kappa_todos_pares_min=_valor(pares.kappa_linear.min()), kappa_todos_pares_max=_valor(pares.kappa_linear.max()),
        mediana_frequencia=dict(release=float(df.frequencia_release.median()),
                                release_prerelease=float(df.frequencia_release_prerelease.median()),
                                tag=float(df.frequencia_tag.median())),
        mediana_razao_tag_sobre_release=razao('frequencia_tag', 'frequencia_release'),
        repositorios_com_prerelease=int((df.prereleases_contadas > 0).sum()),
        repositorios_mais_tags_que_releases=int((df.tags_janela > df.releases_contadas).sum()),
        repositorios_menos_tags_que_releases=int((df.tags_janela < df.releases_contadas).sum()),
        cfr_entrega=dict(mediana=_valor(df.cfr_entrega.median()), indefinidos=int(df.cfr_entrega.isna().sum()),
                         releases_avaliadas=int(df.releases_avaliadas_cfr.sum()),
                         releases_falha=int(df.releases_falha_cfr.sum()),
                         releases_sem_semver=int(df.releases_sem_semver.sum())),
        cfr_ci_mediana=float(df.cfr_ci.median()))
    return tabela, definicoes, distrib, pares, metricas_var, resumo


def graficos(pares, distrib, destino):
    cache = RAIZ / 'dados/.cache/matplotlib'
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR', str(cache))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    matplotlib.rcParams['svg.hashsalt'] = 'rq96'
    nomes = list(COMBINACOES)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.4), constrained_layout=True)
    for ax, coluna, titulo, mapa, formato, limites in [
            (axes[0], 'proporcao_mudam', 'Repositórios que mudam de classe geral (%)', 'Oranges', '{:.0f}', (0, 100)),
            (axes[1], 'kappa_linear', 'Kappa de Cohen ponderado (linear)', 'Blues', '{:.2f}', (0, 1))]:
        matriz = pd.DataFrame(float('nan'), index=nomes, columns=nomes)
        for r in pares.itertuples():
            v = getattr(r, coluna)
            v = None if v is None or pd.isna(v) else v * (100 if coluna == 'proporcao_mudam' else 1)
            matriz.loc[r.combinacao_2, r.combinacao_1] = v
        imagem = ax.imshow(matriz.to_numpy(dtype=float), cmap=mapa, vmin=limites[0], vmax=limites[1])
        for i, linha in enumerate(nomes):
            for j, coluna_nome in enumerate(nomes):
                v = matriz.loc[linha, coluna_nome]
                if not pd.isna(v):
                    escuro = (v - limites[0]) / (limites[1] - limites[0]) > .6
                    ax.text(j, i, formato.format(v), ha='center', va='center', fontsize=9,
                            color='white' if escuro else 'black')
        ax.set_xticks(range(len(nomes)), nomes)
        ax.set_yticks(range(len(nomes)), nomes)
        ax.set_title(titulo)
        fig.colorbar(imagem, ax=ax, shrink=.8)
    fig.suptitle('RQ96 · Concordância da classificação DORA geral entre combinações')
    for ext in ['png', 'svg']:
        fig.savefig(destino / f'concordancia_pares.{ext}', dpi=180, metadata={'Date': None} if ext == 'svg' else None)
    plt.close(fig)

    cores = {'Elite': '#1C6855', 'High': '#377EB8', 'Medium': '#B58A27', 'Low': '#8D5959', 'Indefinida': '#BBBBBB'}
    fig, ax = plt.subplots(figsize=(10, 4.8), constrained_layout=True)
    base = [0] * len(nomes)
    total = distrib.groupby('combinacao').repositorios.sum().reindex(nomes)
    for categoria in CLASSES + ['Indefinida']:
        g = distrib.loc[distrib.classe == categoria].set_index('combinacao').reindex(nomes)
        valores = (g.repositorios / total * 100).tolist()
        barras = ax.barh(nomes, valores, left=base, color=cores[categoria], label=categoria)
        ax.bar_label(barras, labels=[f'{v:.0f}%' if v >= 4 else '' for v in valores], label_type='center',
                     color='white', fontsize=8)
        base = [b + v for b, v in zip(base, valores)]
    ax.invert_yaxis()
    ax.set(xlim=(0, 100), xlabel='Repositórios (%)', title='RQ96 · Classe geral em cada combinação')
    ax.legend(ncol=5, loc='upper center', bbox_to_anchor=(.5, -.15), fontsize=9)
    for ext in ['png', 'svg']:
        fig.savefig(destino / f'classes_combinacoes.{ext}', dpi=180, metadata={'Date': None} if ext == 'svg' else None)
    plt.close(fig)


def _n(x, casas=2):
    return 'não estimável' if x is None or (isinstance(x, float) and math.isnan(x)) else f'{x:.{casas}f}'


def relatorio(tabela, definicoes, distrib, pares, metricas_var, resumo, config):
    n = resumo['repositorios']
    tabela_def = '\n'.join(f'| {r.combinacao} | {r.unidade_deploy} | ({r.lead_time}) | ({r.cfr}) | {r.descricao} | '
                           f'{r.repositorios_classificados} |' for r in definicoes.itertuples())
    piv = distrib.pivot(index='combinacao', columns='classe', values='repositorios').reindex(list(COMBINACOES))
    tabela_dist = '\n'.join(f'| {c} | ' + ' | '.join(str(int(piv.loc[c, k])) for k in CLASSES + ['Indefinida']) + ' |'
                            for c in piv.index)
    vs = pares.loc[pares.combinacao_1 == 'C1']
    tabela_c1 = '\n'.join(
        f'| C1 × {r.combinacao_2} | {r.n} | {r.mudam} ({r.proporcao_mudam * 100:.1f}%) | {r.melhoram} | {r.pioram} | '
        f'{r.mudam_2_ou_mais} | {_n(r.kappa_linear, 3)} | {r.interpretacao_kappa} |' for r in vs.itertuples())
    outros = pares.loc[pares.combinacao_1 != 'C1']
    tabela_outros = '\n'.join(
        f'| {r.combinacao_1} × {r.combinacao_2} | {r.n} | {r.proporcao_mudam * 100:.1f}% | {_n(r.kappa_linear, 3)} |'
        for r in outros.itertuples())
    rotulo_var = {('frequencia', 'classe_freq_release_prerelease'): 'Frequência: release → release + pré-release',
                  ('frequencia', 'classe_freq_tag'): 'Frequência: release → tag',
                  ('lead_time', 'classe_lead_b'): 'Lead time: (a) → (b)', ('cfr', 'classe_cfr_b'): 'CFR: (a) → (b)'}
    tabela_var = '\n'.join(
        f'| {rotulo_var[(r.metrica, r.alternativa)]} | {r.n} | {r.mudam} ({r.proporcao_mudam * 100:.1f}%) | '
        f'{r.melhoram} | {r.pioram} | {_n(r.kappa_linear, 3)} |' for r in metricas_var.itertuples())
    mf = resumo['mediana_frequencia']
    ce = resumo['cfr_entrega']
    k_min, k_max = resumo['kappa_vs_c1_min'], resumo['kappa_vs_c1_max']
    acima = resumo['alternativas_com_mudanca_ge_30pct']
    alternativas = vs.combinacao_2.tolist()
    h7_mudanca = ('confirmada em todas as alternativas' if len(acima) == len(alternativas) else
                  f'confirmada em {len(acima)} de {len(alternativas)} alternativas ({", ".join(acima) or "nenhuma"})')
    h7_kappa = ('não avaliável' if k_min is None else 'dentro da faixa prevista' if .2 <= k_min and k_max <= .6 else
                f'parcialmente fora da faixa prevista (de {_n(k_min, 3)} a {_n(k_max, 3)})')
    var = metricas_var.set_index('alternativa')
    lt = var.loc['classe_lead_b']
    pre, tag = var.loc['classe_freq_release_prerelease'], var.loc['classe_freq_tag']
    cfr = var.loc['classe_cfr_b']
    aviso = 'confirmada na configuração' if config.get('janela_confirmada') is True else \
        '**ainda não confirmada pelo professor na configuração**'
    estaveis, completos = resumo['repositorios_mesma_classe_em_todas'], resumo['repositorios_classificados_em_todas']
    so_unidade = vs.loc[vs.combinacao_2.isin(['C5', 'C6'])]
    com_cfr_b = vs.loc[vs.combinacao_2.isin(['C3', 'C4', 'C7'])]
    if len(acima) == len(alternativas) and k_min is not None and .2 <= k_min and k_max <= .6:
        veredito = ('**H7 confirmada.** A classificação muda com qualquer alternativa; '
                    'as conclusões das RQ01 a RQ06 devem ser lidas como condicionais à C1.')
    elif not acima:
        veredito = ('**H7 não confirmada.** Nenhuma alternativa muda 30% ou mais das classes gerais; '
                    'a classificação da C1 é robusta às definições testadas.')
    else:
        veredito = (f'**H7 parcialmente confirmada.** A fragilidade depende de qual definição muda. Trocar só a '
                    f'unidade de deploy (C5, C6) muda de {so_unidade.proporcao_mudam.min() * 100:.1f}% a '
                    f'{so_unidade.proporcao_mudam.max() * 100:.1f}% das classes'
                    f'{", sempre para melhor" if so_unidade.pioram.sum() == 0 else ""}, com kappa de '
                    f'{_n(so_unidade.kappa_linear.min(), 3)} a {_n(so_unidade.kappa_linear.max(), 3)}. As '
                    f'combinações com CFR (b) mudam de {com_cfr_b.proporcao_mudam.min() * 100:.1f}% a '
                    f'{com_cfr_b.proporcao_mudam.max() * 100:.1f}%, e '
                    f'{com_cfr_b.pioram.sum() / max(com_cfr_b.mudam.sum(), 1) * 100:.0f}% dessas mudanças são para '
                    f'pior, porque o CFR (a) '
                    f'concentra os repositórios em Elite e o CFR (b) não. Como a heurística do CFR (b) ainda não foi '
                    f'validada, parte desse efeito pode ser do proxy, e não da definição. Conclusões das RQ01 a RQ06 '
                    f'sobre a classe geral valem para a C1 e são sensíveis, sobretudo, à escolha do CFR.')
    return f'''# RQ96 — RQ07: Sensibilidade das classificações DORA

## Pergunta e método

O quanto a classificação DORA de um repositório depende da definição operacional escolhida? Análise local de **{n} repositórios**, janela UTC inclusiva {config['janela']['inicio']} a {config['janela']['fim']}, {aviso}.

Cada repositório é classificado em {len(COMBINACOES)} combinações de definições. Em todas, a recuperação é a mesma (mediana dos episódios completos por workflow) e a classe geral é a mediana das quatro notas, arredondada para baixo, indefinida se alguma métrica for indefinida (regra da RQ95). A **C1 é a referência** e reproduz a `classe_geral` exportada em todos os repositórios.

| Combinação | Unidade de deploy | Lead time | CFR | Descrição | Classificados |
|---|---|---|---|---|---:|
{tabela_def}

- **Pré-releases:** releases publicadas na janela com `prerelease = true` entram no numerador da frequência. Contagens conferidas com a coleta.
- **Tags:** tags cujo commit apontado tem `commit.author.date` na janela. A API não data a tag; a data do commit é uma aproximação que pode antecipar a tag.
- **CFR (b):** release seguida de corretiva em até 7 dias (inclusive), últimos 7 dias censurados, heurística `{resumo['heuristica_cfr_entrega']}` (só a tag; **ainda sem F1 medido contra a amostra-ouro**). Mediana {_n(ce['mediana'] * 100 if ce['mediana'] is not None else None, 1)}%, contra {resumo['cfr_ci_mediana'] * 100:.1f}% do CFR (a); {ce['indefinidos']} repositório(s) sem release avaliável; {ce['releases_sem_semver']} releases com tag fora do SemVer estrito, que nunca são corretivas na v1.
- **Lead time** é sempre o da unidade release: recalculá-lo para pré-releases e tags exige os commits de cada intervalo (`commits_releases.csv.gz`, não versionado). Nas combinações C5 a C7, só a frequência muda com a unidade de deploy.

Por par de combinações: n de repositórios classificados nas duas, proporção que muda de classe geral, direção da mudança e kappa de Cohen ponderado com pesos lineares (`sklearn`), interpretado pela escala de Landis e Koch.

## Resultados

### Classe geral em cada combinação

| Combinação | Elite | High | Medium | Low | Indefinida |
|---|---:|---:|---:|---:|---:|
{tabela_dist}

![Classes por combinação](classes_combinacoes.png)

### C1 contra cada alternativa

| Par | n | Mudam | Melhoram | Pioram | Mudam ≥ 2 classes | Kappa linear | Landis e Koch |
|---|---:|---:|---:|---:|---:|---:|---|
{tabela_c1}

Entre os {completos} repositórios classificados em todas as combinações, **{estaveis} ({estaveis / completos * 100:.1f}%) têm a mesma classe em todas** e **{resumo['repositorios_mudam_em_alguma_alternativa']} ({resumo['repositorios_mudam_em_alguma_alternativa'] / completos * 100:.1f}%) mudam em pelo menos uma alternativa** à C1.

![Concordância entre pares](concordancia_pares.png)

### Demais pares

| Par | n | Mudam | Kappa linear |
|---|---:|---:|---:|
{tabela_outros}

### Efeito de cada troca sobre a classe da própria métrica

| Troca | n | Mudam | Melhoram | Pioram | Kappa linear |
|---|---:|---:|---:|---:|---:|
{tabela_var}

- Frequência mediana (releases/semana): release {_n(mf['release'], 3)}; com pré-releases {_n(mf['release_prerelease'], 3)}; por tag {_n(mf['tag'], 3)}. {resumo['repositorios_com_prerelease']} repositórios têm pré-releases na janela. {resumo['repositorios_mais_tags_que_releases']} têm mais tags que releases e {resumo['repositorios_menos_tags_que_releases']}, menos (tags datadas pelo commit podem cair fora da janela mesmo com a release dentro).
- A classe de uma métrica muda bem mais que a classe geral: a mediana de quatro notas absorve parte das trocas.

## Confronto com H7

A H7 previa classificação frágil: pelo menos 30% dos repositórios mudando de categoria geral entre a C1 e as alternativas, kappa ponderado entre 0,2 e 0,6, pré-releases e tags inflando a frequência e a troca do lead time (a) pelo (b) melhorando a classe de muitos repositórios.

- **≥ 30% mudam de classe geral:** {h7_mudanca}.
- **Kappa entre 0,2 e 0,6:** {h7_kappa}.
- **Pré-releases inflam a frequência:** {'sim' if pre.melhoram > 0 and pre.pioram == 0 else 'não'}; a classe de frequência melhora em {pre.melhoram} repositórios e nunca piora (pré-releases só somam).
- **Tags inflam a frequência:** {'sim' if tag.melhoram > tag.pioram else 'não'}; a classe melhora em {tag.melhoram} e piora em {tag.pioram} repositórios.
- **Lead time (b) melhora a classe de muitos:** {'confirmada' if lt.melhoram > lt.pioram else 'não confirmada'}; melhora em {lt.melhoram} e piora em {lt.pioram} repositórios (ver RQ94: a (b) não é sistematicamente menor que a (a)).
- **CFR (b):** a classe de CFR muda em {cfr.mudam} repositórios ({cfr.proporcao_mudam * 100:.1f}%), melhorando em {cfr.melhoram} e piorando em {cfr.pioram}. Não havia previsão na H7; é a troca de maior efeito por métrica.

{veredito}

## Limitações

As combinações não esgotam as definições possíveis; foram escolhidas as obrigatórias do enunciado que os dados versionados permitem calcular. Lead time não acompanha a unidade de deploy nas C5 a C7. O CFR (b) depende de uma heurística ainda não validada (F1 pendente na RQ89); se a versão padrão mudar, a RQ96 deve ser reexecutada. Tags datadas pelo commit, não pela criação. O kappa ponderado assume classes ordinais e equidistantes. Repositórios sem classe geral numa combinação ficam fora do par, então os n variam. A amostra não é probabilística.

## Reprodução e dicionário das saídas

`python codigo-fonte/analise/rq96_sensibilidade_dora.py` (opções `--entrada`, `--saida` e `--heuristica`). Não exige token nem rede.

- repositorios_combinacoes.csv: nome_completo, linguagem; releases_contadas, prereleases_contadas, tags_janela (contagens na janela); frequencia_release, frequencia_release_prerelease, frequencia_tag (releases/semana); lead_time_release_mediana_dias e lead_time_commit_mediana_dias (dias); cfr_ci e cfr_entrega (fração); releases_avaliadas_cfr, releases_falha_cfr, releases_sem_semver (contagens); recuperacao_mediana_horas (horas); classe_freq_*, classe_lead_*, classe_cfr_*, classe_recuperacao (classe de cada variante de métrica); C1 a C7 (classe geral); classes_distintas (nº de classes gerais diferentes entre as combinações), combinacoes_iguais_c1 (nº de alternativas com a mesma classe da C1), amplitude_notas (maior − menor nota geral).
- combinacoes.csv: combinacao, unidade_deploy, lead_time, cfr, descricao e repositorios_classificados.
- classes_combinacoes.csv: combinacao, classe (inclui Indefinida), repositórios e percentual entre os classificados.
- pares.csv: combinacao_1, combinacao_2, n, mudam, proporcao_mudam (fração), melhoram e pioram (na direção 1 → 2), mudam_2_ou_mais, kappa_linear, concordancia_exata (fração) e interpretacao_kappa.
- metricas_variantes.csv: as mesmas medidas para a classe de cada métrica isolada (referencia → alternativa).
- resumo.json: definições, distribuições, comparações com a C1, estabilidade, frequências, CFR (b) e SHA-256 das entradas. Campos sem estimativa são null.
- concordancia_pares.png/.svg e classes_combinacoes.png/.svg.

Referências locais: metricas/dora.py; metricas/variantes.py; metricas/corretiva.py; RQ94 e RQ95 em entregas/laboratorio-03/sprint-03; H7 em entregas/laboratorio-03/artigo/introducao.tex.
'''


def executar(entrada: Path, saida: Path, heuristica=None):
    fontes = [entrada / n for n in ['metricas_repositorios.csv', 'releases.csv', 'tags.csv', 'resumo_execucao.json']]
    config = json.loads(fontes[3].read_text(encoding='utf-8'))['config']
    metricas = pd.read_csv(fontes[0])
    releases = pd.read_csv(fontes[1], keep_default_na=False, dtype={'tag_name': str})
    tags = pd.read_csv(fontes[2], keep_default_na=False, dtype={'tag_name': str})
    tabela, definicoes, distrib, pares, metricas_var, resumo = analisar(
        metricas, releases, tags, config['janela']['inicio'], config['janela']['fim'], heuristica)
    resumo['janela'] = config['janela']
    resumo['janela_confirmada'] = config.get('janela_confirmada', False) is True
    resumo['fontes_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in fontes}
    saida.mkdir(parents=True, exist_ok=True)
    for nome, t in [('repositorios_combinacoes', tabela), ('combinacoes', definicoes),
                    ('classes_combinacoes', distrib), ('pares', pares), ('metricas_variantes', metricas_var)]:
        t.to_csv(saida / f'{nome}.csv', index=False, float_format='%.12g')
    (saida / 'resumo.json').write_text(json.dumps(resumo, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
                                       encoding='utf-8')
    graficos(pares, distrib, saida)
    (saida / 'RELATORIO.md').write_text(relatorio(tabela, definicoes, distrib, pares, metricas_var, resumo, config),
                                        encoding='utf-8')
    return resumo


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--entrada', type=Path, default=RAIZ / 'dados/lab03_final')
    p.add_argument('--saida', type=Path, default=RAIZ / 'entregas/laboratorio-03/sprint-03/RQ96')
    p.add_argument('--heuristica', choices=sorted(corretiva.HEURISTICAS), default=variantes.HEURISTICA)
    args = p.parse_args()
    r = executar(args.entrada, args.saida, args.heuristica)
    print(json.dumps({k: r[k] for k in ['pares_c1', 'repositorios_mesma_classe_em_todas',
                                        'alternativas_com_mudanca_ge_30pct']}, ensure_ascii=False, indent=2))
