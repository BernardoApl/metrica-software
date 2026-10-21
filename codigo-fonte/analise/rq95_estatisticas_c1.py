"""RQ95: estatísticas descritivas das métricas DORA e classificação C1, sem rede.

python codigo-fonte/analise/rq95_estatisticas_c1.py

C1 é a combinação de referência: deploy = release publicada (não draft, não
pré-release), lead time (a) por release, CFR (a) de CI e recuperação por
workflow. Lê ``metricas_repositorios.csv`` da coleta final, reclassifica cada
repositório com ``metricas/dora.py`` e confere com as classes exportadas.
Opcionalmente lê ``repositorios.csv`` da RQ92 para medir o efeito do ajuste de
corte da recuperação sobre a C1, sem substituir o valor oficial.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path
from statistics import median

import pandas as pd

CODIGO = Path(__file__).resolve().parents[1]
RAIZ = CODIGO.parent
sys.path.insert(0, str(CODIGO))
from metricas import dora  # noqa: E402

CLASSES = ['Elite', 'High', 'Medium', 'Low']
TOLERANCIA = 0.00000051

#: (coluna do valor, coluna da classe, rótulo, unidade, classificador)
METRICAS = [
    ('frequencia_deploy_semana', 'classe_frequencia', 'Frequência de deploy (RQ01)', 'releases/semana',
     dora.classificar_frequencia),
    ('lead_time_release_mediana_dias', 'classe_lead_time', 'Lead time (a) por release (RQ02)', 'dias',
     dora.classificar_lead_time),
    ('cfr_ci', 'classe_cfr', 'CFR (a) de CI (RQ03)', 'fração', dora.classificar_cfr),
    ('recuperacao_mediana_horas', 'classe_recuperacao', 'Recuperação (RQ04)', 'horas',
     dora.classificar_recuperacao),
]
#: Métricas descritivas fora da C1, para contexto.
COMPLEMENTARES = [('lead_time_commit_mediana_dias', 'Lead time (b) por commit (RQ02)', 'dias')]
VELOCIDADE, ESTABILIDADE = ['classe_frequencia', 'classe_lead_time'], ['classe_cfr', 'classe_recuperacao']


def _valor(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else v


def estatisticas(serie) -> dict:
    s = pd.Series(serie, dtype=float)
    ausentes = int(s.isna().sum())
    s = s.dropna()
    if s.empty:
        return dict(n=0, indefinidos=ausentes, mediana=None, q1=None, q3=None, iqr=None,
                    p10=None, p90=None, minimo=None, maximo=None, media=None)
    q = {p: float(s.quantile(p, interpolation='linear')) for p in [.1, .25, .5, .75, .9]}
    return dict(n=len(s), indefinidos=ausentes, mediana=q[.5], q1=q[.25], q3=q[.75], iqr=q[.75] - q[.25],
                p10=q[.1], p90=q[.9], minimo=float(s.min()), maximo=float(s.max()), media=float(s.mean()))


def nota_mediana(notas) -> float | None:
    """Mediana bruta das notas (antes do arredondamento para baixo)."""
    notas = [n for n in notas if n is not None]
    return float(median(notas)) if notas else None


def classificar(df: pd.DataFrame, recuperacao: str = 'recuperacao_mediana_horas') -> pd.DataFrame:
    """Classes C1 por repositório; geral vazia se alguma métrica é indefinida."""
    saida = pd.DataFrame({'nome_completo': df.nome_completo})
    for valor, classe, _, _, funcao in METRICAS:
        coluna = recuperacao if classe == 'classe_recuperacao' else valor
        saida[classe] = [funcao(_valor(v)) for v in df[coluna]]
        saida[f'nota_{classe[7:]}'] = saida[classe].map(dora.NOTAS)
    classes = [m[1] for m in METRICAS]
    saida['classe_geral'] = [dora.classificacao_geral(linha) for linha in saida[classes].itertuples(index=False)]
    notas = saida[[f'nota_{c[7:]}' for c in classes]]
    saida['mediana_notas'] = [nota_mediana([None if pd.isna(n) else n for n in linha])
                              if not linha.isna().any() else None for _, linha in notas.iterrows()]
    saida['arredondado'] = saida.mediana_notas.map(lambda m: m is not None and not pd.isna(m) and m != int(m))
    return saida


def _perfil(classes: pd.DataFrame, colunas) -> pd.Series:
    """Alto (Elite/High nas duas métricas), baixo (Medium/Low nas duas) ou misto."""
    altas = classes[colunas].isin(['Elite', 'High'])
    definidas = classes[colunas].notna().all(axis=1)
    return pd.Series(['alto' if a.all() else 'baixo' if not a.any() else 'misto'
                      for _, a in altas.iterrows()], index=classes.index).where(definidas)


def analisar(metricas: pd.DataFrame, rq92: pd.DataFrame | None = None):
    colunas = {'nome_completo', 'lead_time_commit_mediana_dias', 'classe_geral'} | \
        {m[0] for m in METRICAS} | {m[1] for m in METRICAS}
    faltantes = colunas - set(metricas.columns)
    if faltantes:
        raise ValueError(f'Colunas obrigatórias ausentes: {sorted(faltantes)}')
    if metricas.empty or metricas.nome_completo.isna().any() or metricas.nome_completo.duplicated().any():
        raise ValueError('Amostra vazia, identificadores ausentes ou repositórios duplicados.')
    df = metricas.sort_values('nome_completo').reset_index(drop=True)
    for valor, *_ in METRICAS:
        df[valor] = pd.to_numeric(df[valor], errors='raise')
    if ((df.cfr_ci < 0) | (df.cfr_ci > 1)).any():
        raise ValueError('CFR fora do intervalo [0, 1].')
    for valor, *_ in METRICAS[:2] + METRICAS[3:]:
        if (df[valor] < 0).any():
            raise ValueError(f'Valor negativo em {valor}.')

    c1 = classificar(df)
    for _, classe, *_ in METRICAS + [(None, 'classe_geral')]:
        if not (c1[classe].fillna('') == df[classe].fillna('')).all():
            nome = c1.nome_completo[c1[classe].fillna('') != df[classe].fillna('')].iloc[0]
            raise ValueError(f'Classe exportada diverge da reclassificação em {nome}: {classe}')

    repos = df[['nome_completo', 'linguagem'] + [m[0] for m in METRICAS] +
               ['lead_time_commit_mediana_dias']].merge(c1, on='nome_completo')
    repos['perfil_velocidade'] = _perfil(repos, VELOCIDADE)
    repos['perfil_estabilidade'] = _perfil(repos, ESTABILIDADE)
    # Sensibilidade (não oficial): geral pelas métricas definidas quando falta alguma.
    notas = repos[[f'nota_{m[1][7:]}' for m in METRICAS]]
    repos['classe_geral_metricas_definidas'] = [
        dora.CATEGORIAS[math.floor(median(n.dropna()))] if n.notna().any() else None for _, n in notas.iterrows()]
    repos['metricas_indefinidas'] = notas.isna().sum(axis=1)

    est = pd.DataFrame([dict(metrica=valor, rotulo=rotulo, unidade=unidade, **estatisticas(repos[valor]))
                        for valor, _, rotulo, unidade, _ in METRICAS] +
                       [dict(metrica=valor, rotulo=rotulo, unidade=unidade, **estatisticas(repos[valor]))
                        for valor, rotulo, unidade in COMPLEMENTARES])
    est['classe_da_mediana'] = [funcao(_valor(m)) for m, (_, _, _, _, funcao) in
                                zip(est.mediana[:len(METRICAS)], METRICAS)] + [
        dora.classificar_lead_time(_valor(est.mediana.iloc[-1]))]

    linhas = []
    for classe in [m[1] for m in METRICAS] + ['classe_geral']:
        contagem = repos[classe].value_counts().reindex(CLASSES, fill_value=0)
        definidos = int(repos[classe].notna().sum())
        for categoria, n in contagem.items():
            linhas.append(dict(metrica=classe, classe=categoria, repositorios=int(n),
                               percentual_amostra=n / len(repos) * 100,
                               percentual_definidos=n / definidos * 100 if definidos else None))
        linhas.append(dict(metrica=classe, classe='Indefinida', repositorios=len(repos) - definidos,
                           percentual_amostra=(len(repos) - definidos) / len(repos) * 100,
                           percentual_definidos=None))
    classes = pd.DataFrame(linhas)

    perfis = pd.crosstab(repos.perfil_velocidade, repos.perfil_estabilidade).reindex(
        index=['alto', 'misto', 'baixo'], columns=['alto', 'misto', 'baixo'], fill_value=0)
    perfis.index.name, perfis.columns.name = 'velocidade', 'estabilidade'
    combinacoes = (repos.dropna(subset=['classe_geral'])
                   .assign(combinacao=lambda d: d[[m[1] for m in METRICAS]].apply(
                       lambda r: '/'.join(x[0] for x in r), axis=1))
                   .groupby(['combinacao', 'classe_geral']).size().rename('repositorios')
                   .reset_index().sort_values(['repositorios', 'combinacao'], ascending=[False, True]))

    # Classe de cada métrica versus a geral: quantas puxam para cima ou para baixo.
    geral = repos.classe_geral.map(dora.NOTAS)
    alinhamento = {m[1]: dict(acima=int((repos[f'nota_{m[1][7:]}'] > geral).sum()),
                              igual=int((repos[f'nota_{m[1][7:]}'] == geral).sum()),
                              abaixo=int((repos[f'nota_{m[1][7:]}'] < geral).sum())) for m in METRICAS}

    sensibilidade_rq92 = None
    if rq92 is not None:
        if not {'nome_completo', 'recuperacao_mediana_horas'}.issubset(rq92.columns):
            raise ValueError('Saída da RQ92 sem as colunas esperadas.')
        if set(rq92.nome_completo) != set(repos.nome_completo):
            raise ValueError('Saída da RQ92 com repositórios diferentes da amostra.')
        ajustado = df.drop(columns='recuperacao_mediana_horas').merge(
            rq92[['nome_completo', 'recuperacao_mediana_horas']], on='nome_completo')
        c92 = classificar(ajustado)
        repos['recuperacao_rq92_horas'] = ajustado.recuperacao_mediana_horas.to_numpy()
        repos['classe_recuperacao_rq92'] = c92.classe_recuperacao.to_numpy()
        repos['classe_geral_rq92'] = c92.classe_geral.to_numpy()
        mudou = lambda a, b: int((repos[a].fillna('') != repos[b].fillna('')).sum())  # noqa: E731
        sensibilidade_rq92 = dict(
            recuperacao_alterada=int((repos.recuperacao_rq92_horas - repos.recuperacao_mediana_horas)
                                     .abs().gt(TOLERANCIA).sum()),
            classe_recuperacao_alterada=mudou('classe_recuperacao', 'classe_recuperacao_rq92'),
            classe_geral_alterada=mudou('classe_geral', 'classe_geral_rq92'))

    sem_geral = repos.loc[repos.classe_geral.isna()]
    resumo = dict(
        repositorios=len(repos), combinacao='C1',
        definicao='release publicada (não draft, não pré-release); lead time (a); CFR (a) de CI; recuperação',
        estatisticas=json.loads(est.to_json(orient='records', force_ascii=False)),
        classes={c: repos[c].value_counts().reindex(CLASSES, fill_value=0).astype(int).to_dict()
                 for c in [m[1] for m in METRICAS] + ['classe_geral']},
        classe_geral_indefinida=int(repos.classe_geral.isna().sum()),
        motivo_indefinida={m[1]: int(sem_geral[m[1]].isna().sum()) for m in METRICAS},
        classe_geral_metricas_definidas_nos_indefinidos=sem_geral.classe_geral_metricas_definidas
            .value_counts().reindex(CLASSES, fill_value=0).astype(int).to_dict(),
        arredondados_para_baixo=int(repos.arredondado.sum()),
        alinhamento_com_geral=alinhamento,
        perfis_velocidade_estabilidade=json.loads(perfis.to_json(force_ascii=False)),
        combinacoes_mais_frequentes=json.loads(combinacoes.head(10).to_json(orient='records', force_ascii=False)),
        combinacoes_distintas=int(len(combinacoes)),
        sensibilidade_corte_rq92=sensibilidade_rq92)
    return repos, est, classes, perfis, combinacoes, resumo


def graficos(repos, classes, destino):
    cache = RAIZ / 'dados/.cache/matplotlib'
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR', str(cache))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    matplotlib.rcParams['svg.hashsalt'] = 'rq95'
    cortes = {'frequencia_deploy_semana': [1 / dora.SEMANAS_POR_MES, 1, 7],
              'lead_time_release_mediana_dias': [1, 7, 30], 'cfr_ci': [.15, .30, .45],
              'recuperacao_mediana_horas': [1, 24, 168]}
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    for ax, (valor, _, rotulo, unidade, _) in zip(axes.flat, METRICAS):
        v = repos[valor].dropna().sort_values().to_numpy()
        ax.step(v, [(i + 1) / len(v) * 100 for i in range(len(v))], where='post', color='#377EB8')
        if valor != 'cfr_ci':
            ax.set_xscale('log')
        for corte in cortes[valor]:
            ax.axvline(corte, color='gray', linestyle=':', linewidth=1)
        m = float(pd.Series(v).median())
        ax.axvline(m, color='#8D5959', linewidth=1.2, label=f'mediana = {m:.3g}')
        ax.set(title=f'{rotulo} · n = {len(v)}', xlabel=unidade + ('' if valor == 'cfr_ci' else ', log'),
               ylabel='Repositórios (%)', ylim=(0, 101))
        ax.legend(loc='lower right', fontsize=9)
    fig.suptitle('RQ95 · Distribuição das métricas da C1 (linhas pontilhadas: cortes DORA)')
    for ext in ['png', 'svg']:
        fig.savefig(destino / f'distribuicoes_c1.{ext}', dpi=180, metadata={'Date': None} if ext == 'svg' else None)
    plt.close(fig)

    cores = {'Elite': '#1C6855', 'High': '#377EB8', 'Medium': '#B58A27', 'Low': '#8D5959', 'Indefinida': '#BBBBBB'}
    ordem = [m[1] for m in METRICAS] + ['classe_geral']
    nomes = ['Frequência', 'Lead time (a)', 'CFR (a)', 'Recuperação', 'Geral C1']
    fig, ax = plt.subplots(figsize=(10, 4.8), constrained_layout=True)
    base = [0] * len(ordem)
    for categoria in CLASSES + ['Indefinida']:
        valores = [float(classes.loc[(classes.metrica == m) & (classes.classe == categoria),
                                     'percentual_amostra'].iloc[0]) for m in ordem]
        barras = ax.barh(nomes, valores, left=base, color=cores[categoria], label=categoria)
        ax.bar_label(barras, labels=[f'{v:.0f}%' if v >= 4 else '' for v in valores], label_type='center',
                     color='white', fontsize=8)
        base = [b + v for b, v in zip(base, valores)]
    ax.invert_yaxis()
    ax.set(xlabel=f'Repositórios (% de {len(repos)})', xlim=(0, 100), title='RQ95 · Classes DORA na combinação C1')
    ax.legend(ncol=5, loc='upper center', bbox_to_anchor=(.5, -.15), fontsize=9)
    for ext in ['png', 'svg']:
        fig.savefig(destino / f'classes_c1.{ext}', dpi=180, metadata={'Date': None} if ext == 'svg' else None)
    plt.close(fig)


def _n(x, casas=2):
    return 'não estimável' if x is None or (isinstance(x, float) and math.isnan(x)) else f'{x:.{casas}f}'


def relatorio(repos, est, classes, perfis, combinacoes, resumo, config):
    n = len(repos)
    casas = {'cfr_ci': 4, 'frequencia_deploy_semana': 3}
    tabela_est = '\n'.join(
        f'| {r.rotulo} | {r.unidade} | {r.n} | {r.indefinidos} | {_n(r.mediana, casas.get(r.metrica, 2))} | '
        f'{_n(r.q1, casas.get(r.metrica, 2))}–{_n(r.q3, casas.get(r.metrica, 2))} | '
        f'{_n(r.iqr, casas.get(r.metrica, 2))} | {_n(r.p10, casas.get(r.metrica, 2))}–'
        f'{_n(r.p90, casas.get(r.metrica, 2))} | {_n(r.minimo, 4)}–{_n(r.maximo, 2)} | '
        f'{_n(r.media, casas.get(r.metrica, 2))} | {r.classe_da_mediana} |' for r in est.itertuples())
    piv = classes.pivot(index='metrica', columns='classe', values='repositorios')
    nomes = {'classe_frequencia': 'Frequência', 'classe_lead_time': 'Lead time (a)', 'classe_cfr': 'CFR (a)',
             'classe_recuperacao': 'Recuperação', 'classe_geral': '**Geral C1**'}
    tabela_cls = '\n'.join(f'| {nomes[m]} | ' + ' | '.join(
        f'{int(piv.loc[m, c])} ({piv.loc[m, c] / n * 100:.1f}%)' for c in CLASSES + ['Indefinida']) + ' |'
        for m in nomes)
    tabela_perfis = '\n'.join(f'| **{v}** | ' + ' | '.join(str(int(perfis.loc[v, e])) for e in perfis.columns) + ' |'
                              for v in perfis.index)
    tabela_comb = '\n'.join(f'| {r.combinacao} | {r.classe_geral} | {r.repositorios} |'
                            for r in combinacoes.head(8).itertuples())
    alin = resumo['alinhamento_com_geral']
    tabela_alin = '\n'.join(f'| {nomes[m]} | {v["acima"]} | {v["igual"]} | {v["abaixo"]} |' for m, v in alin.items())
    geral = resumo['classes']['classe_geral']
    definidos = n - resumo['classe_geral_indefinida']
    moda = max(geral, key=geral.get)
    s92 = resumo['sensibilidade_corte_rq92']
    texto_rq92 = ('A saída da RQ92 não foi encontrada; a sensibilidade ao ajuste de corte não foi calculada.'
                  if s92 is None else
                  f'Com a recuperação ajustada pela RQ92 (sucesso após o fim da janela vira censura), '
                  f'**{s92["recuperacao_alterada"]} repositórios** mudam de valor, '
                  f'**{s92["classe_recuperacao_alterada"]}** mudam de classe de recuperação e '
                  f'**{s92["classe_geral_alterada"]}** mudam de classe geral. A C1 oficial mantém o valor exportado '
                  f'pela coleta' + ('; o ajuste não altera nenhuma classe.' if s92['classe_recuperacao_alterada'] == 0
                                    and s92['classe_geral_alterada'] == 0 else
                                    '; as classes alteradas estão em repositorios_c1.csv (colunas *_rq92).'))
    estab_alta = int(perfis['alto'].sum())
    veloc_alta = int(perfis.loc['alto'].sum())
    total_perfis = int(perfis.to_numpy().sum())
    cfr = resumo['classes']['classe_cfr']
    aviso = 'confirmada na configuração' if config.get('janela_confirmada') is True else \
        '**ainda não confirmada pelo professor na configuração**'
    est_i = est.set_index('metrica')
    return f'''# RQ95 — Estatísticas descritivas, mediana, IQR e classificação DORA C1

## Escopo

Consolida, para os **{n} repositórios** da amostra final, as estatísticas descritivas das quatro métricas DORA (RQ01 a RQ04) e a classificação na **combinação de referência C1**, que é a base de comparação da RQ07. Janela UTC inclusiva {config['janela']['inicio']} a {config['janela']['fim']}, {aviso}.

| Elemento | Definição na C1 |
|---|---|
| Deploy | Release publicada (`draft = false`), não pré-release |
| Frequência | Releases na janela / semanas da janela |
| Lead time | Variante (a): data da release − commit mais antigo; mediana entre releases |
| CFR | Variante (a): runs com falha / (falhas + sucessos), `event = push`, default branch |
| Recuperação | Mediana dos episódios completos de falha por workflow (horas) |
| Classe geral | Mediana das quatro notas (Elite 4 … Low 1), arredondada para baixo; indefinida se alguma métrica for indefinida |

Valores e classes vêm de `metricas_repositorios.csv`; as classes foram **recalculadas** com `metricas/dora.py` e conferem com as exportadas em todos os repositórios. O CFR (b) de entrega não entra na C1 e não é consolidado aqui.

## Estatísticas descritivas

Valores por repositório; estatística da amostra com igual peso por repositório. Quartis e percentis por interpolação linear. A média aparece só para mostrar a assimetria: ela fica muito acima da mediana em todas as métricas de tempo.

| Métrica | Unidade | n | Indefinidos | Mediana | Q1–Q3 | IQR | P10–P90 | Mín.–máx. | Média | Classe da mediana |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
{tabela_est}

![Distribuições](distribuicoes_c1.png)

## Classificação DORA (C1)

| Métrica | Elite | High | Medium | Low | Indefinida |
|---|---:|---:|---:|---:|---:|
{tabela_cls}

![Classes C1](classes_c1.png)

- A classe geral mais frequente é **{moda}** ({geral[moda]} de {definidos} repositórios classificados). Elite e High somam {geral['Elite'] + geral['High']} ({(geral['Elite'] + geral['High']) / definidos * 100:.1f}% dos classificados).
- **{resumo['classe_geral_indefinida']} repositórios** ficam sem classe geral, todos por recuperação indefinida (sem episódio completo de falha: {resumo['motivo_indefinida']['classe_recuperacao']}). Não recebem zero nem Elite. Como sensibilidade não oficial, a mediana das três métricas definidas os colocaria em: {json.dumps(resumo['classe_geral_metricas_definidas_nos_indefinidos'], ensure_ascii=False)}.
- **{resumo['arredondados_para_baixo']} repositórios** têm mediana de notas não inteira (ex.: 3,5) e são arredondados para baixo; a regra é conservadora e desloca a distribuição para classes piores.
- O CFR (a) concentra **{cfr['Elite']} repositórios em Elite** ({cfr['Elite'] / n * 100:.1f}%): com a mediana de {_n(est_i.loc['cfr_ci', 'mediana'] * 100, 1)}% de falhas, o corte de 15% discrimina pouco. Frequência e lead time são as métricas que mais diferenciam os repositórios.

### Quem puxa a classe geral

Comparação entre a classe de cada métrica e a classe geral do repositório (só classificados):

| Métrica | Acima da geral | Igual | Abaixo da geral |
|---|---:|---:|---:|
{tabela_alin}

### Velocidade e estabilidade

Perfil **alto** = Elite ou High nas duas métricas da dimensão; **baixo** = Medium ou Low nas duas; **misto** = uma de cada. Velocidade = frequência e lead time; estabilidade = CFR e recuperação.

| Velocidade \\ Estabilidade | alto | misto | baixo |
|---|---:|---:|---:|
{tabela_perfis}

Entre os {total_perfis} repositórios com as quatro métricas definidas, **{estab_alta} ({estab_alta / total_perfis * 100:.1f}%) têm estabilidade alta**, mas só **{veloc_alta} ({veloc_alta / total_perfis * 100:.1f}%) têm velocidade alta**. Na C1, a classe geral é limitada pela velocidade: as métricas de estabilidade ficam acima da geral e as de velocidade, abaixo (tabela anterior). A tabela é descritiva; a associação entre as dimensões é objeto da RQ05.

### Combinações mais frequentes

{resumo['combinacoes_distintas']} combinações distintas de classes (Frequência/Lead time/CFR/Recuperação, pela inicial):

| Combinação (F/L/C/R) | Geral | Repositórios |
|---|---|---:|
{tabela_comb}

## Sensibilidade ao corte da janela (RQ92)

{texto_rq92}

## Limitações

As classes são da combinação C1; outras definições operacionais (pré-releases, tags, lead time (b), CFR (b)) são avaliadas na RQ07. Os cortes DORA vêm de questionários com empresas e não foram calibrados para projetos open-source. A mediana das notas trata as classes como equidistantes. A amostra é de repositórios populares que usam GitHub Actions, não probabilística. IQR é dispersão, não intervalo de confiança.

## Reprodução e dicionário das saídas

`python codigo-fonte/analise/rq95_estatisticas_c1.py` (opções `--entrada`, `--rq92` e `--saida`). Não exige token nem rede.

- estatisticas_descritivas.csv: metrica, rotulo, unidade; n e indefinidos (contagens); mediana, q1, q3, iqr, p10, p90, minimo, maximo, media (na unidade da métrica); classe_da_mediana.
- repositorios_c1.csv: nome_completo, linguagem, as quatro métricas e o lead time (b) (unidades acima); classe_* e nota_* (4 = Elite … 1 = Low) por métrica; classe_geral; mediana_notas (antes do arredondamento) e arredondado; perfil_velocidade e perfil_estabilidade (alto, misto, baixo; vazio se indefinido); classe_geral_metricas_definidas (sensibilidade, não oficial) e metricas_indefinidas (contagem); recuperacao_rq92_horas, classe_recuperacao_rq92 e classe_geral_rq92 (sensibilidade ao corte).
- classes_c1.csv: metrica, classe (inclui Indefinida), repositórios, percentual_amostra e percentual_definidos.
- perfis_velocidade_estabilidade.csv: repositórios por perfil de velocidade × estabilidade.
- combinacoes_classes.csv: combinação F/L/C/R, classe geral e repositórios.
- resumo.json: estatísticas, classes, indefinidos, arredondamentos, alinhamento, perfis, sensibilidade e SHA-256 das entradas. Campos sem estimativa são null.
- distribuicoes_c1.png/.svg e classes_c1.png/.svg.

Referências locais: metricas/dora.py; RQ91, RQ92 e RQ94 em entregas/laboratorio-03/sprint-03; Seção 2 de entregas/laboratorio-03/artigo/metodologia.tex.
'''


def executar(entrada: Path, saida: Path, rq92: Path | None = None):
    fontes = [entrada / 'metricas_repositorios.csv', entrada / 'resumo_execucao.json']
    config = json.loads(fontes[1].read_text(encoding='utf-8'))['config']
    tabela92 = None
    if rq92 is not None and rq92.exists():
        tabela92 = pd.read_csv(rq92)
        fontes.append(rq92)
    repos, est, classes, perfis, combinacoes, resumo = analisar(pd.read_csv(fontes[0]), tabela92)
    resumo['janela'] = config['janela']
    resumo['janela_confirmada'] = config.get('janela_confirmada', False) is True
    resumo['fontes_sha256'] = {f'{p.parent.name}/{p.name}': hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in fontes}
    saida.mkdir(parents=True, exist_ok=True)
    for nome, tabela in [('repositorios_c1', repos), ('estatisticas_descritivas', est), ('classes_c1', classes),
                         ('combinacoes_classes', combinacoes)]:
        tabela.to_csv(saida / f'{nome}.csv', index=False, float_format='%.12g')
    perfis.to_csv(saida / 'perfis_velocidade_estabilidade.csv')
    (saida / 'resumo.json').write_text(json.dumps(resumo, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
                                       encoding='utf-8')
    graficos(repos, classes, saida)
    (saida / 'RELATORIO.md').write_text(relatorio(repos, est, classes, perfis, combinacoes, resumo, config),
                                        encoding='utf-8')
    return resumo


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--entrada', type=Path, default=RAIZ / 'dados/lab03_final')
    p.add_argument('--rq92', type=Path, default=RAIZ / 'entregas/laboratorio-03/sprint-03/RQ92/repositorios.csv')
    p.add_argument('--saida', type=Path, default=RAIZ / 'entregas/laboratorio-03/sprint-03/RQ95')
    args = p.parse_args()
    r = executar(args.entrada, args.saida, args.rq92)
    print(json.dumps({k: r[k] for k in ['classes', 'classe_geral_indefinida', 'arredondados_para_baixo',
                                        'sensibilidade_corte_rq92']}, ensure_ascii=False, indent=2))
