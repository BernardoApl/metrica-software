"""RQ97 / LAB03 RQ03: change failure rate (CFR) nas duas variantes, sem rede.

python codigo-fonte/analise/rq97_cfr.py

- **CFR (a), proxy de CI:** falhas / (falhas + sucessos) dos workflow runs de
  ``push`` no default branch, na janela. Recontado a partir de
  ``workflow_runs.csv.gz`` e conferido com ``metricas_repositorios.csv``.
- **CFR (b), proxy de entrega:** release seguida, em até 7 dias, de uma release
  corretiva; releases dos últimos 7 dias da janela ficam fora (censura). A
  versão principal usa a heurística padrão do projeto (``patch_semver_v1``, só
  a tag), calculada por ``metricas.variantes.cfr_entrega`` a partir de
  ``releases.csv``. As versões v2 e v3, que leem as mensagens dos commits, só
  são calculadas se ``commits_releases.csv.gz`` (não versionado, acima de
  100 MB) existir, e entram como sensibilidade: elas **não** foram validadas
  contra a amostra-ouro.

As funções de nível de release (``preparar_entregas``, ``sinalizar_corretivas``,
``cfr_entrega_de``) são reaproveitadas pela RQ98.
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import json
import math
import os
import sys
from pathlib import Path
from typing import NamedTuple

import numpy as np
import pandas as pd
from scipy import stats

CODIGO = Path(__file__).resolve().parents[1]
RAIZ = CODIGO.parent
sys.path.insert(0, str(CODIGO))
from analise.rq95_estatisticas_c1 import estatisticas  # noqa: E402
from analise.rq96_sensibilidade_dora import booleanos, comparar, landis_koch  # noqa: E402
from coleta.coleta_dora import limites_da_janela  # noqa: E402
from metricas import ci, corretiva, dora, lead_time, variantes  # noqa: E402

CLASSES = ['Elite', 'High', 'Medium', 'Low']
SETE_DIAS = 7 * 86400
TOLERANCIA = 0.00000051
SEMENTE = 42
REPLICAS_BOOTSTRAP = 5000
FALHAS_CI = sorted(ci.CONCLUSOES_FALHA)
#: Heurísticas que leem as mensagens dos commits (só v1 usa apenas a tag).
ALTERNATIVAS = ['patch_ou_mensagem_v2', 'correcao_de_defeito_v3']
CAMPOS_EVIDENCIA = ('uteis', 'revert_hotfix', 'fix', 'fix_defeito', 'feat')
#: Cortes de CFR da disciplina (Elite ≤ 15%, High ≤ 30%, Medium ≤ 45%).
CORTES_CFR = [.15, .30, .45]


def _valor(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else v


def _faltantes(tabela: pd.DataFrame, colunas, nome: str):
    faltantes = set(colunas) - set(tabela.columns)
    if faltantes:
        raise ValueError(f'{nome}: colunas obrigatórias ausentes: {sorted(faltantes)}')


def segundos(datas: pd.Series) -> pd.Series:
    """Instantes ISO 8601 (UTC) em segundos desde 1970-01-01."""
    ts = pd.to_datetime(datas, utc=True, format='ISO8601')
    return (ts - pd.Timestamp('1970-01-01', tz='UTC')) // pd.Timedelta(seconds=1)


# ------------------------------------------------------------------ CFR (a), CI
def cfr_ci_por_repositorio(runs: pd.DataFrame, metricas: pd.DataFrame, inicio, fim) -> pd.DataFrame:
    """Recontagem do CFR (a) e das conclusões, com o filtro da seção 3 do enunciado.

    Entram os runs de ``push`` no default branch criados em ``[inicio, fim]``;
    ``success`` é sucesso, ``failure``/``timed_out``/``startup_failure`` são falha e
    o resto (``cancelled``, ``skipped``...) é ignorado. Também mede quanto das
    falhas vem do workflow que mais falha em cada repositório.
    """
    _faltantes(runs, {'nome_completo', 'workflow_id', 'event', 'head_branch', 'conclusion', 'created_at'},
               'workflow_runs')
    inicio, fim = ci.data_utc(inicio), ci.data_utc(fim)
    branch = runs.nome_completo.astype(str).map(dict(zip(metricas.nome_completo, metricas.branch_padrao)))
    criado = pd.to_datetime(runs.created_at, utc=True, format='ISO8601')
    contexto = runs.loc[(runs.event == 'push') & (runs.head_branch.astype(str) == branch)
                        & (criado >= inicio) & (criado <= fim)]
    conclusao = contexto.conclusion.astype(str)
    sucesso = conclusao.isin(ci.CONCLUSOES_SUCESSO)
    falha = conclusao.isin(ci.CONCLUSOES_FALHA)
    contexto = contexto.assign(_conclusao=conclusao, _sucesso=sucesso, _falha=falha)

    repos = pd.Index(metricas.nome_completo)
    nome = contexto.nome_completo.astype(str)
    saida = pd.DataFrame(index=repos)
    saida['runs_push_branch'] = nome.value_counts().reindex(repos, fill_value=0)
    saida['runs_sucesso_recontado'] = nome[sucesso].value_counts().reindex(repos, fill_value=0)
    for tipo in FALHAS_CI:
        saida[f'falhas_{tipo}'] = nome[conclusao == tipo].value_counts().reindex(repos, fill_value=0)
    saida['runs_falha_recontado'] = saida[[f'falhas_{t}' for t in FALHAS_CI]].sum(axis=1)
    saida['runs_ignorados'] = (saida.runs_push_branch - saida.runs_sucesso_recontado
                               - saida.runs_falha_recontado)
    validos = saida.runs_sucesso_recontado + saida.runs_falha_recontado
    saida['cfr_ci_recontado'] = (saida.runs_falha_recontado / validos).where(validos > 0)

    por_workflow = (contexto.loc[falha].assign(_nome=nome[falha])
                    .groupby(['_nome', contexto.loc[falha].workflow_id.astype(str)], observed=True).size())
    totais = por_workflow.groupby(level=0).sum()
    saida['workflows_com_falha'] = por_workflow.groupby(level=0).size().reindex(repos, fill_value=0)
    saida['participacao_workflow_mais_falho'] = (por_workflow.groupby(level=0).max() / totais).reindex(repos)
    ativos = contexto.loc[sucesso | falha]
    saida['workflows_com_runs'] = (ativos.assign(_nome=nome[sucesso | falha])
                                   .groupby('_nome', observed=True).workflow_id.nunique()
                                   .reindex(repos, fill_value=0))
    saida.index.name = 'nome_completo'
    return saida.reset_index()


def conferir_cfr_ci(recontado: pd.DataFrame, metricas: pd.DataFrame) -> None:
    """A recontagem tem de reproduzir o que a coleta exportou, repositório a repositório."""
    juntos = metricas[['nome_completo', 'runs_falha', 'runs_sucesso', 'cfr_ci']].merge(recontado, on='nome_completo')
    for r in juntos.itertuples():
        if r.runs_falha != r.runs_falha_recontado or r.runs_sucesso != r.runs_sucesso_recontado:
            raise ValueError(f'CFR (a) recontado diverge da coleta em {r.nome_completo}: '
                             f'falhas {r.runs_falha_recontado} vs {r.runs_falha}, '
                             f'sucessos {r.runs_sucesso_recontado} vs {r.runs_sucesso}')
        exportado, recontagem = _valor(r.cfr_ci), _valor(r.cfr_ci_recontado)
        if (exportado is None) != (recontagem is None) or \
                (exportado is not None and abs(exportado - recontagem) > TOLERANCIA):
            raise ValueError(f'CFR (a) recontado diverge da coleta em {r.nome_completo}')


# ------------------------------------------------------------ CFR (b), entrega
class Entregas(NamedTuple):
    """Deploys principais de um repositório, em ordem cronológica (data, id)."""
    nome: str
    tags: list
    datas: list   # published_at, como veio da coleta
    ids: list
    t: np.ndarray  # published_at em segundos desde 1970


def preparar_entregas(releases: pd.DataFrame, fim) -> dict:
    """Deploys da definição principal (não draft, não pré-release) publicados até ``fim``."""
    _faltantes(releases, {'nome_completo', 'id', 'tag_name', 'draft', 'prerelease', 'published_at'}, 'releases')
    if releases.duplicated(['nome_completo', 'id']).any():
        raise ValueError('releases duplicadas.')
    fim_s = int(ci.data_utc(fim).timestamp())
    df = releases.assign(draft=booleanos(releases.draft), prerelease=booleanos(releases.prerelease))
    df = df.loc[~df.draft & ~df.prerelease & df.published_at.notna() & (df.published_at != '')].copy()
    df['t'] = segundos(df.published_at)
    df['id'] = pd.to_numeric(df.id)
    df = df.loc[df.t <= fim_s].sort_values(['nome_completo', 't', 'id'], kind='stable')
    return {nome: Entregas(nome, g.tag_name.tolist(), g.published_at.tolist(), g.id.tolist(),
                           g.t.to_numpy(dtype='int64'))
            for nome, g in df.groupby('nome_completo', sort=False)}


def sinalizar_corretivas(e: Entregas, heuristica: str = corretiva.HEURISTICA_PADRAO,
                         contagens: dict | None = None, disponiveis: set | None = None) -> np.ndarray:
    """``True`` nas releases que a heurística considera corretivas.

    A comparação é sempre com a release publicada imediatamente anterior; a primeira
    nunca é corretiva. ``contagens`` mapeia ``(repositório, tag)`` às evidências das
    mensagens (``CAMPOS_EVIDENCIA``) e ``disponiveis`` diz em quais releases o
    ``compare`` está completo; sem isso, só a tag vale (como na v1).
    """
    if heuristica not in corretiva.HEURISTICAS:
        raise ValueError(f'Heurística desconhecida: {heuristica!r}')
    funcao = corretiva.HEURISTICAS[heuristica]
    flags = np.zeros(len(e.tags), dtype=bool)
    for i in range(1, len(e.tags)):
        ev = corretiva.evidencias(e.tags[i - 1], e.tags[i], None)
        chave = (e.nome, e.tags[i])
        if contagens is not None and disponiveis is not None and chave in disponiveis:
            ev.update(zip(CAMPOS_EVIDENCIA, (int(v) for v in contagens.get(chave, [0] * len(CAMPOS_EVIDENCIA)))),
                      mensagens_disponiveis=True)
        flags[i] = bool(funcao(ev))
    return flags


def falhas_por_release(t: np.ndarray, corretivas: np.ndarray) -> np.ndarray:
    """Release i falha se alguma corretiva sai em ``(t_i, t_i + 7 dias]``."""
    acumulado = np.concatenate(([0], np.cumsum(corretivas, dtype=np.int64)))
    inicio = np.searchsorted(t, t, side='right')
    fim = np.searchsorted(t, t + SETE_DIAS, side='right')
    return acumulado[fim] > acumulado[inicio]


def cfr_entrega_de(t: np.ndarray, corretivas: np.ndarray, inicio, fim) -> dict:
    """CFR (b) com as regras da seção 5 do enunciado.

    Só releases publicadas na janela contam; as dos últimos 7 dias
    (``t + 7 dias > fim``) são censuradas e ficam fora do denominador.
    """
    inicio_s, fim_s = int(ci.data_utc(inicio).timestamp()), int(ci.data_utc(fim).timestamp())
    na_janela = t >= inicio_s
    censurada = t + SETE_DIAS > fim_s
    avaliada = na_janela & ~censurada
    falha = falhas_por_release(t, corretivas)
    avaliadas, falhas = int(avaliada.sum()), int((falha & avaliada).sum())
    return dict(cfr_entrega=falhas / avaliadas if avaliadas else None, releases_avaliadas_cfr=avaliadas,
                releases_falha_cfr=falhas, releases_censuradas_cfr=int((na_janela & censurada).sum()))


def conferir_com_oficial(entregas: dict, tabela: pd.DataFrame, inicio, fim) -> None:
    """A versão vetorizada (v1) tem de coincidir com ``variantes.cfr_entrega``."""
    por_repo = tabela.set_index('nome_completo')
    for nome, e in entregas.items():
        registros = [dict(tag_name=tag, published_at=data, draft=False, prerelease=False, id=i)
                     for tag, data, i in zip(e.tags, e.datas, e.ids)]
        oficial = variantes.cfr_entrega(registros, inicio, fim, corretiva.HEURISTICA_PADRAO, {})
        linha = por_repo.loc[nome]
        if (oficial['releases_avaliadas_cfr'], oficial['releases_falha_cfr'], oficial['releases_censuradas_cfr']) != \
                (linha.releases_avaliadas_cfr, linha.releases_falha_cfr, linha.releases_censuradas_cfr):
            raise ValueError(f'CFR (b) vetorizado diverge de variantes.cfr_entrega em {nome}')


# ----------------------------------------------- mensagens dos commits (v2, v3)
@functools.lru_cache(maxsize=200_000)
def _evidencias_mensagem(mensagem: str) -> tuple:
    ev = corretiva.evidencias(None, None, [mensagem])
    return tuple(ev[c] for c in CAMPOS_EVIDENCIA)


def agregar_commits(caminho: Path, tamanho_bloco: int = 500_000):
    """Soma as evidências das mensagens por ``(repositório, tag)``, sem carregar o arquivo inteiro.

    As contagens são aditivas (``corretiva.evidencias`` soma por mensagem), então a
    leitura em blocos dá o mesmo resultado que uma chamada com a lista completa.
    Devolve também quantas linhas cada release tem, para conferir com o ``compare``.
    """
    contagens, linhas = {}, {}
    leitor = pd.read_csv(caminho, usecols=['nome_completo', 'tag_name', 'mensagem'], dtype=str,
                         keep_default_na=False, chunksize=tamanho_bloco)
    for bloco in leitor:
        ev = pd.DataFrame([_evidencias_mensagem(m) for m in bloco.mensagem], columns=list(CAMPOS_EVIDENCIA),
                          dtype='int64')
        ev['_repo'], ev['_tag'] = bloco.nome_completo.to_numpy(), bloco.tag_name.to_numpy()
        soma = ev.groupby(['_repo', '_tag']).agg(**{c: (c, 'sum') for c in CAMPOS_EVIDENCIA}, _n=('uteis', 'size'))
        for (repo, tag), linha in zip(soma.index, soma.itertuples(index=False)):
            antigo = contagens.get((repo, tag))
            vetor = np.array(linha[:len(CAMPOS_EVIDENCIA)], dtype=np.int64)
            contagens[(repo, tag)] = vetor if antigo is None else antigo + vetor
            linhas[(repo, tag)] = linhas.get((repo, tag), 0) + int(linha[-1])
    return contagens, linhas


def releases_com_mensagens(lead: pd.DataFrame, linhas: dict, entregas: dict) -> set:
    """Releases cujo ``compare`` está completo, como em ``rq83_metricas_variantes``.

    Vale a release com ``compare`` disponível, não truncado, cuja ``anterior`` é a
    release que a heurística usa e cujo número de commits lidos bate com o do
    ``compare``. Uma release sem commits novos conta como disponível (com zero commits).
    """
    _faltantes(lead, {'nome_completo', 'tag_name', 'anterior', 'motivo', 'commits', 'truncado'}, 'lead_time_releases')
    anterior = {(e.nome, e.tags[i]): e.tags[i - 1] for e in entregas.values() for i in range(1, len(e.tags))}
    sem_compare = {lead_time.COMPARE_INDISPONIVEL, lead_time.SEM_ANTERIOR}
    truncado = booleanos(lead.truncado)
    ok = set()
    for r, cortado in zip(lead.itertuples(index=False), truncado):
        chave = (r.nome_completo, r.tag_name)
        if r.motivo in sem_compare or cortado or anterior.get(chave) != r.anterior:
            continue
        if linhas.get(chave, 0) != int(r.commits or 0):
            continue
        ok.add(chave)
    return ok


def cfr_por_heuristica(entregas: dict, heuristica: str, inicio, fim, contagens=None, disponiveis=None) -> pd.DataFrame:
    linhas = []
    for nome, e in entregas.items():
        flags = sinalizar_corretivas(e, heuristica, contagens, disponiveis)
        na_janela = e.t >= int(ci.data_utc(inicio).timestamp())
        linhas.append(dict(nome_completo=nome, **cfr_entrega_de(e.t, flags, inicio, fim),
                           releases_corretivas=int(flags[na_janela].sum()),
                           releases_na_janela=int(na_janela.sum()),
                           releases_sem_semver=int(sum(corretiva.versao(t) is None
                                                       for t, n in zip(e.tags, na_janela) if n))))
    return pd.DataFrame(linhas)


# ------------------------------------------------------------------ estatísticas
def ic_bootstrap_mediana(valores, replicas: int = REPLICAS_BOOTSTRAP, semente: int = SEMENTE):
    """Intervalo percentil de 95% para a mediana; semente fixa."""
    v = np.asarray([x for x in valores if x is not None and not np.isnan(x)], dtype=float)
    if v.size < 2:
        return None, None
    rng = np.random.default_rng(semente)
    medianas = np.median(v[rng.integers(0, v.size, size=(replicas, v.size))], axis=1)
    return float(np.percentile(medianas, 2.5)), float(np.percentile(medianas, 97.5))


def wilcoxon_pareado(a: pd.Series, b: pd.Series):
    """Wilcoxon pareado e correlação rank-bisserial (positiva = (a) maior), como na RQ94."""
    d = (a - b).dropna()
    if d.empty or (d == 0).all():
        return None
    teste = stats.wilcoxon(a.loc[d.index], b.loc[d.index], zero_method='wilcox')
    nz = d[d != 0]
    postos = nz.abs().rank()
    rbc = float((postos[nz > 0].sum() - postos[nz < 0].sum()) / postos.sum())
    return dict(n=len(d), estatistica=float(teste.statistic), p_valor=float(teste.pvalue), rank_bisserial=rbc)


def classes_de(serie: pd.Series) -> pd.Series:
    return serie.map(lambda v: dora.classificar_cfr(_valor(v)))


def distribuicao(classes: pd.Series) -> dict:
    return {**classes.value_counts().reindex(CLASSES, fill_value=0).astype(int).to_dict(),
            'Indefinida': int(classes.isna().sum())}


def analisar(metricas: pd.DataFrame, recontado: pd.DataFrame, entregas: dict, inicio, fim,
             lead: pd.DataFrame | None = None, commits: tuple | None = None):
    _faltantes(metricas, {'nome_completo', 'linguagem', 'branch_padrao', 'cfr_ci', 'runs_falha', 'runs_sucesso',
                          'frequencia_deploy_semana', 'releases_janela'}, 'metricas_repositorios')
    if metricas.empty or metricas.nome_completo.isna().any() or metricas.nome_completo.duplicated().any():
        raise ValueError('Amostra vazia, identificadores ausentes ou repositórios duplicados.')
    if not set(entregas) <= set(metricas.nome_completo):
        raise ValueError('Releases de repositórios fora da amostra.')
    conferir_cfr_ci(recontado, metricas)
    df = metricas.sort_values('nome_completo').reset_index(drop=True)
    if ((df.cfr_ci < 0) | (df.cfr_ci > 1)).any():
        raise ValueError('CFR (a) fora do intervalo [0, 1].')

    # CFR (b), versão principal (v1), conferida com a função oficial do projeto.
    v1 = cfr_por_heuristica(entregas, corretiva.HEURISTICA_PADRAO, inicio, fim)
    conferir_com_oficial(entregas, v1, inicio, fim)
    contexto = [c for c in ('nome_completo', 'linguagem', 'estrelas', 'idade_anos', 'contribuidores_total',
                            'frequencia_deploy_semana', 'releases_janela', 'cfr_ci') if c in df]
    tabela = df[contexto]
    tabela = tabela.merge(recontado.drop(columns=['cfr_ci_recontado', 'runs_sucesso_recontado',
                                                  'runs_falha_recontado']), on='nome_completo')
    tabela = tabela.merge(df[['nome_completo', 'runs_falha', 'runs_sucesso']], on='nome_completo')
    tabela = tabela.merge(v1, on='nome_completo', how='left')
    for coluna in ['releases_avaliadas_cfr', 'releases_falha_cfr', 'releases_censuradas_cfr',
                   'releases_corretivas', 'releases_na_janela', 'releases_sem_semver']:
        tabela[coluna] = tabela[coluna].fillna(0).astype(int)
    tabela['cfr_entrega'] = pd.to_numeric(tabela.cfr_entrega)
    tabela['proporcao_semver'] = (1 - tabela.releases_sem_semver / tabela.releases_na_janela).where(
        tabela.releases_na_janela > 0)
    tabela['proporcao_corretivas'] = (tabela.releases_corretivas / tabela.releases_na_janela).where(
        tabela.releases_na_janela > 0)
    tabela['classe_cfr_a'] = classes_de(tabela.cfr_ci)
    tabela['classe_cfr_b'] = classes_de(tabela.cfr_entrega)

    # Heurísticas que leem as mensagens (sensibilidade; não validadas).
    heuristicas = {corretiva.HEURISTICA_PADRAO: tabela.cfr_entrega}
    disponiveis_n = None
    if lead is not None and commits is not None:
        contagens, linhas = commits
        disponiveis = releases_com_mensagens(lead, linhas, entregas)
        disponiveis_n = len(disponiveis)
        for nome in ALTERNATIVAS:
            r = cfr_por_heuristica(entregas, nome, inicio, fim, contagens, disponiveis)
            tabela[f'cfr_entrega_{nome}'] = tabela[['nome_completo']].merge(
                r[['nome_completo', 'cfr_entrega']], on='nome_completo', how='left').cfr_entrega.astype(float)
            tabela[f'corretivas_{nome}'] = tabela[['nome_completo']].merge(
                r[['nome_completo', 'releases_corretivas']], on='nome_completo', how='left').releases_corretivas
            tabela[f'classe_cfr_{nome}'] = classes_de(tabela[f'cfr_entrega_{nome}'])
            heuristicas[nome] = tabela[f'cfr_entrega_{nome}']

    # Estatísticas descritivas por variante.
    metricas_resumo = {'cfr_ci': 'CFR (a), proxy de CI', 'cfr_entrega': 'CFR (b), proxy de entrega (v1)'}
    for nome in ALTERNATIVAS:
        if f'cfr_entrega_{nome}' in tabela:
            metricas_resumo[f'cfr_entrega_{nome}'] = f'CFR (b) com {nome}'
    est = []
    for coluna, rotulo in metricas_resumo.items():
        e = estatisticas(tabela[coluna])
        e['ic95_mediana_inf'], e['ic95_mediana_sup'] = ic_bootstrap_mediana(tabela[coluna].dropna())
        e['classe_da_mediana'] = dora.classificar_cfr(_valor(e['mediana']))
        est.append(dict(variante=coluna, rotulo=rotulo, **e))
    est = pd.DataFrame(est)

    # Distribuição das classes DORA por variante.
    colunas_classe = {'cfr_ci': 'classe_cfr_a', 'cfr_entrega': 'classe_cfr_b',
                      **{f'cfr_entrega_{n}': f'classe_cfr_{n}' for n in ALTERNATIVAS
                         if f'cfr_entrega_{n}' in tabela}}
    linhas_classe = []
    for variante, coluna in colunas_classe.items():
        dist = distribuicao(tabela[coluna])
        definidos = int(tabela[coluna].notna().sum())
        for classe, n in dist.items():
            linhas_classe.append(dict(variante=variante, classe=classe, repositorios=n,
                                      percentual_definidos=n / definidos * 100 if classe != 'Indefinida' and definidos
                                      else None))
    classes = pd.DataFrame(linhas_classe)

    # Comparação (a) × (b), pareada pelos repositórios com as duas.
    par = tabela.dropna(subset=['cfr_ci', 'cfr_entrega'])
    rho = stats.spearmanr(par.cfr_ci, par.cfr_entrega)
    transicao = pd.crosstab(par.classe_cfr_a, par.classe_cfr_b).reindex(index=CLASSES, columns=CLASSES, fill_value=0)
    transicao.index.name, transicao.columns.name = 'classe_a', 'classe_b'
    comparacao = comparar(par.classe_cfr_a, par.classe_cfr_b)
    comparacao['interpretacao_kappa'] = landis_koch(comparacao['kappa_linear'])
    diferenca = par.cfr_entrega - par.cfr_ci
    comparacao_valores = dict(
        n=len(par), spearman_rho=_valor(float(rho.statistic)), spearman_p=_valor(float(rho.pvalue)),
        b_maior_que_a=int((diferenca > 0).sum()), b_menor_que_a=int((diferenca < 0).sum()),
        b_igual_a=int((diferenca == 0).sum()), diferenca_mediana_b_menos_a=float(diferenca.median()),
        wilcoxon=wilcoxon_pareado(par.cfr_entrega, par.cfr_ci))

    # CFR (a) bruto: concentração e composição das falhas.
    falhas_total = int(tabela.runs_falha.sum())
    validos_total = falhas_total + int(tabela.runs_sucesso.sum())
    ci_resumo = dict(
        cfr_agregado=falhas_total / validos_total if validos_total else None,
        runs_validos=validos_total, runs_falha=falhas_total,
        runs_ignorados=int(tabela.runs_ignorados.sum()), runs_push_branch=int(tabela.runs_push_branch.sum()),
        falhas_por_conclusao={t: int(tabela[f'falhas_{t}'].sum()) for t in FALHAS_CI},
        repositorios_com_timed_out_ou_startup=int(((tabela.falhas_timed_out + tabela.falhas_startup_failure) > 0).sum()),
        repositorios_sem_falha=int((tabela.runs_falha == 0).sum()),
        repositorios_cfr_ci_acima_45=int((tabela.cfr_ci > .45).sum()),
        participacao_workflow_mais_falho=estatisticas(tabela.participacao_workflow_mais_falho.dropna()),
        workflows_com_runs=estatisticas(tabela.workflows_com_runs),
        mediana_proporcao_ignorados=float((tabela.runs_ignorados / tabela.runs_push_branch)
                                          .where(tabela.runs_push_branch > 0).median()))

    # CFR (b): estrutura e limites do proxy.
    avaliados = tabela.releases_avaliadas_cfr
    sem_avaliacao = tabela.loc[avaliados == 0, 'nome_completo'].tolist()
    estrito = tabela.dropna(subset=['cfr_entrega'])
    semver80 = estrito.loc[estrito.proporcao_semver >= .8]
    zero = estrito.cfr_entrega == 0
    entrega_resumo = dict(
        releases_avaliadas=int(avaliados.sum()), releases_falha=int(tabela.releases_falha_cfr.sum()),
        releases_censuradas=int(tabela.releases_censuradas_cfr.sum()),
        cfr_agregado=float(tabela.releases_falha_cfr.sum() / avaliados.sum()) if avaliados.sum() else None,
        repositorios_sem_release_avaliavel=sem_avaliacao,
        repositorios_cfr_zero=int(zero.sum()),
        repositorios_cfr_zero_sem_nenhum_semver=int((zero & (estrito.proporcao_semver == 0)).sum()),
        repositorios_sem_nenhum_semver=int((tabela.proporcao_semver == 0).sum()),
        repositorios_semver_ge_80=int(len(semver80)),
        releases_sem_semver=int(tabela.releases_sem_semver.sum()), releases_na_janela=int(tabela.releases_na_janela.sum()),
        proporcao_corretivas=estatisticas(tabela.proporcao_corretivas.dropna()),
        avaliadas_por_repositorio=estatisticas(avaliados[avaliados > 0]),
        repositorios_menos_de_10_avaliadas=int(((avaliados > 0) & (avaliados < 10)).sum()),
        estatisticas_semver_ge_80=dict(estatisticas(semver80.cfr_entrega),
                                       classe_da_mediana=dora.classificar_cfr(_valor(semver80.cfr_entrega.median()))
                                       if len(semver80) else None),
        disponiveis_para_mensagens=disponiveis_n)

    # Comparações entre versões da heurística (sensibilidade).
    versoes = []
    base = [n for n in heuristicas if n != corretiva.HEURISTICA_PADRAO]
    for nome in base:
        p = tabela.dropna(subset=['cfr_entrega', f'cfr_entrega_{nome}'])
        rho_h = stats.spearmanr(p.cfr_entrega, p[f'cfr_entrega_{nome}'])
        versoes.append(dict(heuristica=nome, n=len(p), spearman_com_v1=_valor(float(rho_h.statistic)),
                            spearman_p=_valor(float(rho_h.pvalue)),
                            proporcao_corretivas_mediana=float((tabela[f'corretivas_{nome}'] /
                                                                tabela.releases_na_janela)
                                                               .where(tabela.releases_na_janela > 0).median()),
                            **{k: v for k, v in comparar(p.classe_cfr_b, p[f'classe_cfr_{nome}']).items()
                               if k in ('mudam', 'proporcao_mudam', 'melhoram', 'pioram', 'kappa_linear')}))
    versoes = pd.DataFrame(versoes)

    resumo = dict(
        repositorios=len(tabela), estatisticas=json.loads(est.to_json(orient='records', force_ascii=False)),
        classes={v: distribuicao(tabela[c]) for v, c in colunas_classe.items()},
        comparacao_a_b=dict(**comparacao_valores, classes={k: v for k, v in comparacao.items()},
                            transicao=json.loads(transicao.to_json(orient='index'))),
        ci=ci_resumo, entrega=entrega_resumo,
        heuristicas=json.loads(versoes.to_json(orient='records', force_ascii=False)) if len(versoes) else [],
        heuristicas_com_mensagens=bool(len(versoes)))
    return tabela, est, classes, transicao, versoes, resumo


# ------------------------------------------------------------------- saídas
def _n(x, casas=2):
    return 'não estimável' if x is None or (isinstance(x, float) and math.isnan(x)) else f'{x:.{casas}f}'


def _e(x):
    return 'não estimável' if x is None or (isinstance(x, float) and math.isnan(x)) else f'{x:.2e}'


def _p(x, casas=1):
    """Fração -> percentual com o símbolo."""
    return 'não estimável' if x is None or (isinstance(x, float) and math.isnan(x)) else f'{x * 100:.{casas}f}%'


ROTULOS_VARIANTE = {'cfr_ci': 'CFR (a) · CI', 'cfr_entrega': 'CFR (b) · v1 (tag)',
                    'cfr_entrega_patch_ou_mensagem_v2': 'CFR (b) · v2 (tag ou mensagem)',
                    'cfr_entrega_correcao_de_defeito_v3': 'CFR (b) · v3 (correção de defeito)'}


def graficos(tabela, classes, resumo, destino):
    cache = RAIZ / 'dados/.cache/matplotlib'
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR', str(cache))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    matplotlib.rcParams['svg.hashsalt'] = 'rq97'
    meta = {'metadata': {'Date': None}}

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.8), constrained_layout=True)
    for coluna, cor in [('cfr_ci', '#377EB8'), ('cfr_entrega', '#B58A27')]:
        v = np.sort(tabela[coluna].dropna().to_numpy())
        ax1.step(v, np.arange(1, len(v) + 1) / len(v) * 100, where='post', color=cor,
                 label=f'{ROTULOS_VARIANTE[coluna]} · mediana {np.median(v) * 100:.1f}%')
    for corte in CORTES_CFR:
        ax1.axvline(corte, color='gray', linestyle=':', linewidth=1)
    ax1.set(title='Distribuição acumulada (linhas pontilhadas: cortes DORA)', xlabel='CFR (fração)',
            ylabel='Repositórios (%)', xlim=(0, 1), ylim=(0, 101))
    ax1.legend(loc='lower right', fontsize=9)
    par = tabela.dropna(subset=['cfr_ci', 'cfr_entrega'])
    ax2.scatter(par.cfr_ci, par.cfr_entrega, s=14, alpha=.55, color='#1C6855', edgecolor='none')
    ax2.plot([0, 1], [0, 1], color='gray', linestyle='--', linewidth=1)
    rho = resumo['comparacao_a_b']
    ax2.set(title=f'(a) × (b) · ρ = {_n(rho["spearman_rho"])}, n = {rho["n"]}', xlabel='CFR (a) · CI',
            ylabel='CFR (b) · entrega (v1)', xlim=(-.02, 1.02), ylim=(-.02, 1.02))
    fig.suptitle('RQ97 · Change failure rate nas duas variantes')
    for ext in ['png', 'svg']:
        fig.savefig(destino / f'cfr_variantes.{ext}', dpi=180, **(meta if ext == 'svg' else {}))
    plt.close(fig)

    cores = {'Elite': '#1C6855', 'High': '#377EB8', 'Medium': '#B58A27', 'Low': '#8D5959', 'Indefinida': '#BBBBBB'}
    presentes = [v for v in ROTULOS_VARIANTE if v in set(classes.variante)]
    fig, ax = plt.subplots(figsize=(10, 1.6 + .6 * len(presentes)), constrained_layout=True)
    base = [0] * len(presentes)
    total = len(tabela)
    for categoria in CLASSES + ['Indefinida']:
        valores = [classes.loc[(classes.variante == v) & (classes.classe == categoria), 'repositorios'].iloc[0]
                   / total * 100 for v in presentes]
        barras = ax.barh([ROTULOS_VARIANTE[v] for v in presentes], valores, left=base,
                         color=cores[categoria], label=categoria)
        ax.bar_label(barras, labels=[f'{v:.0f}%' if v >= 4 else '' for v in valores], label_type='center',
                     color='white', fontsize=8)
        base = [b + v for b, v in zip(base, valores)]
    ax.invert_yaxis()
    ax.set(xlabel=f'Repositórios (% de {total})', xlim=(0, 100), title='RQ97 · Classes DORA de CFR por variante')
    ax.legend(ncol=5, loc='upper center', bbox_to_anchor=(.5, -.25), fontsize=9)
    for ext in ['png', 'svg']:
        fig.savefig(destino / f'cfr_classes.{ext}', dpi=180, **(meta if ext == 'svg' else {}))
    plt.close(fig)


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, 'rb') as arquivo:
        for bloco in iter(lambda: arquivo.read(1 << 20), b''):
            h.update(bloco)
    return h.hexdigest()


def ler_entrada(entrada: Path):
    metricas = pd.read_csv(entrada / 'metricas_repositorios.csv')
    releases = pd.read_csv(entrada / 'releases.csv', dtype=str, keep_default_na=False)
    runs = pd.read_csv(entrada / 'workflow_runs.csv.gz', keep_default_na=False,
                       usecols=['nome_completo', 'workflow_id', 'event', 'head_branch', 'conclusion', 'created_at'],
                       dtype={'nome_completo': 'category', 'workflow_id': 'category', 'event': 'category',
                              'head_branch': 'category', 'conclusion': 'category', 'created_at': str})
    lead = pd.read_csv(entrada / 'lead_time_releases.csv', dtype=str, keep_default_na=False)
    return metricas, releases, runs, lead


def executar(entrada: Path, saida: Path, commits: Path | None = None, usar_commits: bool = True):
    fontes = [entrada / n for n in ('metricas_repositorios.csv', 'releases.csv', 'workflow_runs.csv.gz',
                                    'lead_time_releases.csv', 'resumo_execucao.json')]
    config = json.loads(fontes[-1].read_text(encoding='utf-8'))['config']
    inicio, fim = limites_da_janela(config['janela']['inicio'], config['janela']['fim'])
    metricas, releases, runs, lead = ler_entrada(entrada)
    metricas = metricas.sort_values('nome_completo').reset_index(drop=True)
    recontado = cfr_ci_por_repositorio(runs, metricas, inicio, fim)
    del runs
    entregas = preparar_entregas(releases, fim)
    caminho_commits = commits or entrada / 'commits_releases.csv.gz'
    agregado = None
    if usar_commits and caminho_commits.is_file():
        agregado = agregar_commits(caminho_commits)
        fontes.append(caminho_commits)
    tabela, est, classes, transicao, versoes, resumo = analisar(metricas, recontado, entregas, inicio, fim,
                                                               lead if agregado else None, agregado)
    resumo['janela'] = config['janela']
    resumo['janela_confirmada'] = config.get('janela_confirmada', False) is True
    resumo['heuristica_padrao'] = corretiva.HEURISTICA_PADRAO
    resumo['heuristica_validada_manualmente'] = False
    resumo['fontes_sha256'] = {f'{p.parent.name}/{p.name}': sha256(p) for p in fontes}
    saida.mkdir(parents=True, exist_ok=True)
    tabela.to_csv(saida / 'repositorios.csv', index=False, float_format='%.12g')
    est.to_csv(saida / 'estatisticas.csv', index=False, float_format='%.12g')
    classes.to_csv(saida / 'classes_dora.csv', index=False, float_format='%.12g')
    transicao.to_csv(saida / 'transicoes_classes.csv')
    if len(versoes):
        versoes.to_csv(saida / 'sensibilidade_heuristica.csv', index=False, float_format='%.12g')
    (saida / 'resumo.json').write_text(json.dumps(resumo, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
                                       encoding='utf-8')
    graficos(tabela, classes, resumo, saida)
    (saida / 'RELATORIO.md').write_text(relatorio(tabela, est, classes, transicao, versoes, resumo, config),
                                        encoding='utf-8')
    return resumo


def relatorio(tabela, est, classes, transicao, versoes, resumo, config) -> str:
    n = len(tabela)
    aviso = 'confirmada na configuração' if config.get('janela_confirmada') is True else \
        '**ainda não confirmada pelo professor na configuração**'
    e = est.set_index('variante')
    a, b = e.loc['cfr_ci'], e.loc['cfr_entrega']
    ci_, en, cmp_ = resumo['ci'], resumo['entrega'], resumo['comparacao_a_b']
    w, cl = cmp_['wilcoxon'] or dict(estatistica=None, p_valor=None, rank_bisserial=None), cmp_['classes']
    com_mensagens = resumo['heuristicas_com_mensagens']

    tabela_est = '\n'.join(
        f'| {r.rotulo} | {r.n} | {_p(r.mediana)} | {_p(r.ic95_mediana_inf)}–{_p(r.ic95_mediana_sup)} | '
        f'{_p(r.q1)}–{_p(r.q3)} | {_p(r.iqr)} | {_p(r.p10)}–{_p(r.p90)} | {_p(r.minimo)}–{_p(r.maximo)} | '
        f'{_p(r.media)} | {r.classe_da_mediana} |' for r in est.itertuples())
    rotulos = {'cfr_ci': 'CFR (a) · CI', 'cfr_entrega': 'CFR (b) · v1 (tag)',
               'cfr_entrega_patch_ou_mensagem_v2': 'CFR (b) · v2 (tag ou mensagem)',
               'cfr_entrega_correcao_de_defeito_v3': 'CFR (b) · v3 (correção de defeito)'}

    def linha_classes(variante):
        c = resumo['classes'][variante]
        return (f'| {rotulos[variante]} | ' + ' | '.join(f'{c[k]} ({c[k] / n * 100:.1f}%)' for k in CLASSES) +
                f' | {c["Indefinida"]} |')
    tabela_classes = '\n'.join(linha_classes(v) for v in resumo['classes'])
    tabela_transicao = '\n'.join(
        f'| **{c}** | ' + ' | '.join(str(int(transicao.loc[c, d])) for d in CLASSES) + ' |' for c in CLASSES)

    falhas = ci_['falhas_por_conclusao']
    w_ci = ci_['participacao_workflow_mais_falho']
    sem_semver = en['releases_sem_semver'] / en['releases_na_janela']
    s80 = en['estatisticas_semver_ge_80']
    prop = en['proporcao_corretivas']

    if com_mensagens:
        tabela_h = '\n'.join(
            [f'| v1 (tag; padrão) | {_p(b.mediana)} | {_p(b.q1)}–{_p(b.q3)} | {_p(prop["mediana"])} | — | — | — |'] +
            [f'| {h["heuristica"]} | {_p(e.loc["cfr_entrega_" + h["heuristica"], "mediana"])} | '
             f'{_p(e.loc["cfr_entrega_" + h["heuristica"], "q1"])}–{_p(e.loc["cfr_entrega_" + h["heuristica"], "q3"])} | '
             f'{_p(h["proporcao_corretivas_mediana"])} | {_n(h["spearman_com_v1"], 3)} | '
             f'{h["mudam"]} ({_p(h["proporcao_mudam"])}) | {_n(h["kappa_linear"], 3)} |' for h in resumo['heuristicas']])
        bloco_heuristica = f'''## Sensibilidade à heurística de release corretiva

O CFR (b) depende de uma heurística automática que, segundo o enunciado, precisa ser validada contra a amostra-ouro (precisão, recall e F1 ≥ 0,70). **Nenhum F1 foi medido até esta análise** (o consenso da amostra-ouro, RQ88, não está no repositório); por isso a versão padrão do projeto continua a v1, e as versões v2 e v3 (RQ89) entram aqui só para medir o quanto o CFR (b) depende da escolha. Nenhuma delas tem F1 medido.

| Versão | Mediana do CFR (b) | Q1–Q3 | Mediana da proporção de releases marcadas corretivas | ρ com a v1 | Mudam de classe vs v1 | κ ponderado vs v1 |
|---|---:|---:|---:|---:|---:|---:|
{tabela_h}

![Classes por variante](cfr_classes.png)

- A v2 (patch **ou** qualquer commit com `fix`, `revert` ou `hotfix`) marca quase todas as releases como corretivas (mediana de {_p(resumo['heuristicas'][0]['proporcao_corretivas_mediana'])} por repositório): releases com muitos commits quase sempre carregam algum `fix`. Em relação à v1, {resumo['heuristicas'][0]['pioram']} repositórios mudam para classe pior e {resumo['heuristicas'][0]['melhoram']} para melhor.
- A v3 é mais seletiva, mas ainda marca {_p(resumo['heuristicas'][1]['proporcao_corretivas_mediana'])} das releases na mediana: um único `revert` ou `hotfix` em qualquer commit do intervalo basta, e em releases grandes isso é comum.
- As três versões ordenam os repositórios de forma só parcialmente parecida (ρ entre {_n(min(h['spearman_com_v1'] for h in resumo['heuristicas']), 2)} e {_n(max(h['spearman_com_v1'] for h in resumo['heuristicas']), 2)} com a v1), mas o **nível** do CFR (b) muda muito: a mediana vai de {_p(b.mediana)} (v1) a {_p(e.loc['cfr_entrega_patch_ou_mensagem_v2', 'mediana'])} (v2). Sem a validação, o valor absoluto do CFR (b) não deve ser tomado como taxa de falha em produção.
- As mensagens vêm de `commits_releases.csv.gz`, que não é versionado (acima de 100 MB); o SHA-256 do arquivo usado está em `resumo.json`. Para {en['disponiveis_para_mensagens']} releases o `compare` estava completo e as mensagens foram usadas; nas demais, só a tag vale.
'''
    else:
        bloco_heuristica = '''## Sensibilidade à heurística de release corretiva

`commits_releases.csv.gz` (não versionado, acima de 100 MB) não estava disponível; as versões v2 e v3 da heurística, que leem as mensagens dos commits, não foram calculadas. O CFR (b) acima usa só a v1 (tag). A validação da heurística contra a amostra-ouro (F1 ≥ 0,70) continua pendente.
'''

    h3a = 0.10 <= a.mediana <= 0.25
    h3b = 0.05 <= b.mediana <= 0.15 and b.mediana < a.mediana
    h3_var = b.iqr > a.iqr
    h3_rho = cmp_['spearman_rho'] is not None and abs(cmp_['spearman_rho']) < 0.3
    confirmadas = sum([h3a, h3b, h3_var, h3_rho])
    veredito = 'confirmada' if confirmadas == 4 else 'não confirmada' if confirmadas == 0 else 'parcialmente confirmada'

    return f'''# RQ97 — RQ03: Change Failure Rate nas duas variantes

## Pergunta e método

Qual a taxa de falha das mudanças entregues por esses repositórios? Análise local de **{n} repositórios**, janela UTC inclusiva {config['janela']['inicio']} a {config['janela']['fim']}, {aviso}.

- **(a) Proxy de CI:** falhas / (falhas + sucessos) dos workflow runs de `push` no default branch criados na janela, todos os workflows juntos. `success` é sucesso; `failure`, `timed_out` e `startup_failure` são falha; `cancelled`, `skipped`, `neutral`, `action_required`, `stale` e vazio são ignorados. Mede **falha de pipeline**.
- **(b) Proxy de entrega:** uma release (publicada, não draft, não pré-release) falha se for seguida, em até 7 dias (inclusive), por uma release corretiva; CFR = releases que falharam / releases avaliadas. As releases dos últimos 7 dias da janela são **censuradas** e ficam fora do denominador. Heurística padrão do projeto: `{resumo['heuristica_padrao']}` (só o número de *patch* mudou em relação à release anterior), **sem validação manual concluída**.

Cada repositório tem o mesmo peso; quartis por interpolação linear. O IC de 95% é um intervalo percentil por *bootstrap* da mediana ({REPLICAS_BOOTSTRAP} réplicas, semente {SEMENTE}). Classes DORA: Elite ≤ 15%, High ≤ 30%, Medium ≤ 45%, Low > 45%.

## Cobertura e auditoria

- Runs lidos de `push` no default branch: **{ci_['runs_push_branch']}**; válidos (sucesso ou falha): **{ci_['runs_validos']}**; ignorados: **{ci_['runs_ignorados']}** ({_p(ci_['runs_ignorados'] / ci_['runs_push_branch'])} dos lidos; mediana por repositório {_p(ci_['mediana_proporcao_ignorados'])}).
- A recontagem do CFR (a) a partir de `workflow_runs.csv.gz` **reproduz** falhas, sucessos e CFR de `metricas_repositorios.csv` em todos os repositórios.
- O CFR (b) da v1 foi calculado de forma vetorizada e **conferido** com `metricas.variantes.cfr_entrega` em todos os repositórios (avaliadas, falhas e censuradas); também coincide com o CFR (b) usado na RQ96.
- Releases na janela: **{en['releases_na_janela']}**; avaliadas no CFR (b): **{en['releases_avaliadas']}**; censuradas pela regra dos 7 dias: **{en['releases_censuradas']}**.
- {len(en['repositorios_sem_release_avaliavel'])} repositório sem release avaliável (todas censuradas ou sem avaliação): {', '.join('`' + r + '`' for r in en['repositorios_sem_release_avaliavel'])}. Ele fica com CFR (b) indefinido (n = {b.n}), não zero.

## Resultados

Frações em percentual; n = repositórios com a variante definida.

| Variante | n | Mediana | IC 95% da mediana | Q1–Q3 | IQR | P10–P90 | Mín.–máx. | Média | Classe da mediana |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
{tabela_est}

- **CFR (a):** mediana **{_p(a.mediana)}** (Q1–Q3 {_p(a.q1)}–{_p(a.q3)}), classe **{a.classe_da_mediana}**. Somando todos os runs da amostra, o CFR é {_p(ci_['cfr_agregado'])} ({ci_['runs_falha']} falhas em {ci_['runs_validos']} runs), pois os repositórios com muitos runs falham mais. {ci_['repositorios_sem_falha']} repositórios não têm nenhuma falha e {ci_['repositorios_cfr_ci_acima_45']} passam de 45%.
- **CFR (b), v1:** mediana **{_p(b.mediana)}** (Q1–Q3 {_p(b.q1)}–{_p(b.q3)}), classe **{b.classe_da_mediana}**, com dispersão muito maior que a do (a): IQR de {_p(b.iqr)} contra {_p(a.iqr)}. Somando todas as releases avaliadas, o CFR (b) é {_p(en['cfr_agregado'])} ({en['releases_falha']} de {en['releases_avaliadas']}).

![Distribuições e dispersão](cfr_variantes.png)

### Classes DORA de CFR

| Variante | Elite | High | Medium | Low | Indefinida |
|---|---:|---:|---:|---:|---:|
{tabela_classes}

O CFR (a) concentra **{resumo['classes']['cfr_ci']['Elite']} repositórios em Elite** ({resumo['classes']['cfr_ci']['Elite'] / n * 100:.1f}%): com mediana de {_p(a.mediana)}, o corte de 15% discrimina pouco. O CFR (b) espalha os repositórios pelas quatro classes, com {resumo['classes']['cfr_entrega']['Low']} em Low.

## Comparação entre as variantes

Em **{cmp_['b_maior_que_a']} repositórios** o CFR (b) é maior que o (a), em **{cmp_['b_menor_que_a']}** é menor e em **{cmp_['b_igual_a']}** é igual (n = {cmp_['n']}); a diferença mediana (b) − (a) é de {_n(cmp_['diferenca_mediana_b_menos_a'] * 100, 1)} pontos percentuais. Wilcoxon pareado: W = {_n(w['estatistica'], 1)}, p = {_e(w['p_valor'])}, rank-bisserial = {_n(w['rank_bisserial'], 3)} (positiva = (b) maior). **Correlação de Spearman entre (a) e (b): ρ = {_n(cmp_['spearman_rho'], 3)} (p = {_n(cmp_['spearman_p'], 3)}, n = {cmp_['n']}).**

**{cl['mudam']} repositórios ({_p(cl['proporcao_mudam'])}) mudam de classe** ao trocar (a) por (b): {cl['melhoram']} melhoram e {cl['pioram']} pioram; {cl['mudam_2_ou_mais']} mudam duas classes ou mais. Kappa de Cohen ponderado (linear) = {_n(cl['kappa_linear'], 3)} ({cl['interpretacao_kappa']}). Matriz de transição (linhas: (a); colunas: (b)):

| (a) \\ (b) | Elite | High | Medium | Low |
|---|---:|---:|---:|---:|
{tabela_transicao}

As duas variantes quase não concordam sobre **quem** falha mais: o ρ é próximo de zero e a maioria dos repositórios muda de classe. Elas medem coisas diferentes, como previsto na H3.

### Falha de pipeline não é falha em produção

- **O que o (a) captura.** {_p(falhas['failure'] / ci_['runs_falha'])} das falhas são `failure` e {_p(falhas['startup_failure'] / ci_['runs_falha'])} são `startup_failure` (workflow que nem chegou a iniciar; {ci_['repositorios_com_timed_out_ou_startup']} repositórios têm algum), e nenhuma é `timed_out`. Em cada repositório, o workflow mais falho responde por **{_p(w_ci['mediana'])}** das falhas na mediana (Q1–Q3 {_p(w_ci['q1'])}–{_p(w_ci['q3'])}), e a mediana de workflows com runs válidos é {_n(ci_['workflows_com_runs']['mediana'], 0)}. Ou seja, o CFR (a) costuma refletir sobretudo um ou dois workflows, e não o conjunto das mudanças entregues; os dados não dizem por que eles falham.
- **O que o (a) não vê.** Um defeito que passa na CI e chega ao usuário não aparece; uma quebra corrigida no *commit* seguinte conta como falha, ainda que nunca tenha saído do `main`. Por isso o (a) é um indicador de **fragilidade do pipeline**, e sua classe Elite quase universal não implica entregas estáveis.
- **O que o (b) captura.** Releases seguidas, em até 7 dias, de uma versão de *patch*. Isso inclui correções de defeito, mas pode incluir também *patches* planejados, releases automáticas e *backports*; e o que o (b) não vê, porque a v1 só lê a tag, são correções publicadas como *minor* ou fora do SemVer.

## Limites do CFR (b)

- **Cobertura da heurística.** {en['releases_sem_semver']} das {en['releases_na_janela']} releases ({_p(sem_semver)}) têm tag fora do SemVer estrito e **nunca** são corretivas na v1. **{en['repositorios_sem_nenhum_semver']} repositórios** não têm nenhuma tag SemVer: o CFR (b) deles é zero **por construção**. Dos {en['repositorios_cfr_zero']} repositórios com CFR (b) igual a zero, {en['repositorios_cfr_zero_sem_nenhum_semver']} estão nesse caso.
- **Releases de *patch* são frequentes.** Na mediana, {_p(prop['mediana'])} das releases de um repositório mudam só o *patch* (Q1–Q3 {_p(prop['q1'])}–{_p(prop['q3'])}). Esse percentual é alto para correções de defeito; é compatível com releases automatizadas e incrementos rotineiros de *patch*, mas os dados não permitem separar as causas.
- **Restrição aos repositórios SemVer.** Nos {en['repositorios_semver_ge_80']} repositórios com pelo menos 80% das releases em SemVer, a mediana do CFR (b) é **{_p(s80['mediana'])}** (Q1–Q3 {_p(s80['q1'])}–{_p(s80['q3'])}; classe {s80['classe_da_mediana']}), {'acima' if s80['mediana'] > b.mediana else 'abaixo'} dos {_p(b.mediana)} da amostra inteira; os repositórios fora do SemVer, onde a v1 não enxerga correções, puxam a mediana da amostra para baixo.
- **Denominador pequeno.** A mediana de releases avaliadas por repositório é {_n(en['avaliadas_por_repositorio']['mediana'], 0)} (Q1–Q3 {_n(en['avaliadas_por_repositorio']['q1'], 0)}–{_n(en['avaliadas_por_repositorio']['q3'], 0)}); {en['repositorios_menos_de_10_avaliadas']} repositórios têm menos de 10, e uma única release muda o CFR em mais de 10 pontos percentuais.

{bloco_heuristica}
## Confronto com H3

A H3 previa CFR de CI (a) com mediana entre 10% e 25% (Elite/High); CFR de entrega (b) menor, entre 5% e 15%, porém mais variável; e correlação fraca entre (a) e (b) (|ρ| < 0,3).

- **(a) entre 10% e 25%:** **{'confirmada' if h3a else 'não confirmada'}**. A mediana é {_p(a.mediana)}, {'dentro' if h3a else 'abaixo'} da faixa; a classe é Elite, como previsto, mas por uma margem maior que a esperada.
- **(b) entre 5% e 15% e menor que o (a):** **{'confirmada' if h3b else 'não confirmada'}**. A mediana da v1 é {_p(b.mediana)}, {'dentro' if 0.05 <= b.mediana <= 0.15 else 'acima'} da faixa e {'abaixo' if b.mediana < a.mediana else 'acima'} da mediana do (a). A previsão de que a entrega falharia menos que o pipeline não se sustenta com o proxy atual.
- **(b) mais variável:** **{'confirmada' if h3_var else 'não confirmada'}** (IQR de {_p(b.iqr)} contra {_p(a.iqr)}).
- **Correlação fraca entre (a) e (b):** **{'confirmada' if h3_rho else 'não confirmada'}** (ρ = {_n(cmp_['spearman_rho'], 3)}, p = {_n(cmp_['spearman_p'], 3)}).

**H3 {veredito}** ({confirmadas} de 4 previsões). A previsão de que os dois proxies medem fenômenos diferentes se confirma; os níveis previstos, não. O nível do (b) depende da heurística, ainda sem validação, e o do (a) depende do corte DORA de 15%.

## Limitações

Release é proxy de deploy; falha de CI é proxy de falha. A heurística do CFR (b) não foi validada (F1 pendente) e só olha a tag na v1; a janela ainda não foi confirmada pelo professor; os cortes DORA vêm de questionários com empresas e não foram calibrados para *open source*; as classes tratam Elite…Low como equidistantes no κ ponderado; a amostra é de repositórios populares com GitHub Actions, não probabilística. IC por *bootstrap* da mediana não é intervalo populacional.

## Reprodução e dicionário das saídas

`python codigo-fonte/analise/rq97_cfr.py` (opções `--entrada`, `--saida`, `--commits` e `--sem-commits`). Não exige token nem rede.

- repositorios.csv: nome_completo, linguagem, estrelas, idade_anos, contribuidores_total, frequencia_deploy_semana (releases/semana), releases_janela (contagem); cfr_ci (fração) e runs_validos, runs_falha, runs_sucesso, runs_push_branch, runs_ignorados (contagens de runs); falhas_failure, falhas_startup_failure, falhas_timed_out (contagens); workflows_com_falha e workflows_com_runs (contagens); participacao_workflow_mais_falho (fração das falhas do repositório no workflow que mais falha); cfr_entrega (fração, v1), releases_avaliadas_cfr, releases_falha_cfr, releases_censuradas_cfr (contagens), releases_corretivas, releases_na_janela, releases_sem_semver (contagens); proporcao_semver e proporcao_corretivas (fração das releases da janela); classe_cfr_a e classe_cfr_b; e, quando há mensagens de commit, cfr_entrega_<heurística>, corretivas_<heurística> e classe_cfr_<heurística>.
- estatisticas.csv: variante, rotulo, n e indefinidos (contagens); mediana, q1, q3, iqr, p10, p90, minimo, maximo, media (fração); ic95_mediana_inf e _sup (fração); classe_da_mediana.
- classes_dora.csv: variante, classe (inclui Indefinida), repositorios (contagem) e percentual_definidos.
- transicoes_classes.csv: matriz classe do (a) × classe do (b), em repositórios.
- sensibilidade_heuristica.csv: por versão v2 e v3, n, spearman_com_v1, proporcao_corretivas_mediana, mudam, proporcao_mudam, melhoram, pioram e kappa_linear em relação à v1.
- resumo.json: estatísticas, classes, comparação, composição das falhas de CI, estrutura do CFR (b), sensibilidade e SHA-256 das entradas. Campos sem estimativa são null.
- cfr_variantes.png/.svg e cfr_classes.png/.svg.

Referências locais: metricas/ci.py; metricas/variantes.py; metricas/corretiva.py; metricas/dora.py; RQ95 e RQ96 em entregas/laboratorio-03/sprint-03; H3 em entregas/laboratorio-03/artigo/introducao.tex.
'''


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--entrada', type=Path, default=RAIZ / 'dados/lab03_final')
    p.add_argument('--saida', type=Path, default=RAIZ / 'entregas/laboratorio-03/sprint-03/RQ97')
    p.add_argument('--commits', type=Path, default=None,
                   help='commits_releases.csv.gz (padrão: dentro de --entrada, se existir)')
    p.add_argument('--sem-commits', action='store_true', help='não calcula as heurísticas v2 e v3')
    args = p.parse_args()
    r = executar(args.entrada, args.saida, args.commits, not args.sem_commits)
    print(json.dumps({k: r[k] for k in ['classes', 'comparacao_a_b']}, ensure_ascii=False, indent=2))
