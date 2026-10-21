"""RQ91 / LAB03 RQ01: análise reexecutável da frequência, sem acesso à rede.

python codigo-fonte/analise/rq91_deployment_frequency.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import math
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

CODIGO = Path(__file__).resolve().parents[1]
RAIZ = CODIGO.parent
sys.path.insert(0, str(CODIGO))
from coleta.coleta_dora import semanas_da_janela  # noqa: E402
from metricas.dora import SEMANAS_POR_MES, classificar_frequencia  # noqa: E402

CLASSES = ['Elite', 'High', 'Medium', 'Low']


def booleanos(serie: pd.Series) -> pd.Series:
    valores = serie.astype(str).str.lower().map({'true': True, 'false': False})
    if valores.isna().any():
        raise ValueError(f'Booleano ausente/inválido: {serie.name}')
    return valores.astype(bool)


def analisar(metricas: pd.DataFrame, releases: pd.DataFrame, inicio: str, fim: str):
    """Reconta releases; rejeita inconsistências em vez de omitir repositórios."""
    for tabela, colunas in [(metricas, {'nome_completo', 'linguagem', 'releases_janela',
                                       'frequencia_deploy_semana', 'classe_frequencia'}),
                            (releases, {'nome_completo', 'id', 'draft', 'prerelease', 'published_at'})]:
        faltantes = colunas - set(tabela.columns)
        if faltantes:
            raise ValueError(f'Colunas obrigatórias ausentes: {sorted(faltantes)}')
    if metricas.empty or metricas.nome_completo.isna().any() or metricas.nome_completo.duplicated().any():
        raise ValueError('Amostra vazia, identificadores ausentes ou repositórios duplicados.')
    abertura = pd.Timestamp(inicio, tz='UTC')
    fechamento = pd.Timestamp(date.fromisoformat(fim) + timedelta(days=1), tz='UTC')
    if fechamento <= abertura:
        raise ValueError('Janela inválida.')
    semanas = semanas_da_janela(inicio, fim)
    if releases[['nome_completo', 'id']].isna().any().any() or releases.duplicated(['nome_completo', 'id']).any():
        raise ValueError('Releases com identificadores ausentes ou duplicados.')
    if not set(releases.nome_completo).issubset(set(metricas.nome_completo)):
        raise ValueError('Releases de repositórios fora da amostra.')
    draft, pre = booleanos(releases.draft), booleanos(releases.prerelease)
    datas = pd.to_datetime(releases.published_at, utc=True, errors='coerce', format='ISO8601')
    if (datas.isna() & ~draft).any():
        raise ValueError('Release publicada sem data válida.')
    validas = releases.loc[~draft & ~pre & (datas >= abertura) & (datas < fechamento)]
    contagens = validas.groupby('nome_completo').size()
    df = metricas[['nome_completo', 'linguagem']].copy()
    df['releases_janela'] = df.nome_completo.map(contagens).fillna(0).astype(int)
    esperado = pd.to_numeric(metricas.releases_janela, errors='raise')
    if not (df.releases_janela == esperado).all():
        raise ValueError('Contagem de releases diverge do CSV de métricas.')
    df['semanas_janela'] = semanas
    df['frequencia_deploy_semana'] = df.releases_janela / semanas
    # O pipeline exporta seis casas decimais. Classificar sempre antes de arredondar.
    salvo = pd.to_numeric(metricas.frequencia_deploy_semana, errors='raise')
    if not ((df.frequencia_deploy_semana - salvo).abs() <= 0.00000051).all():
        raise ValueError('Frequência exportada diverge da recontagem/janela.')
    df['classe_frequencia'] = df.frequencia_deploy_semana.map(classificar_frequencia)
    if not (df.classe_frequencia == metricas.classe_frequencia).all():
        raise ValueError('Classe de frequência diverge do CSV de métricas.')
    df = df.sort_values('nome_completo').reset_index(drop=True)
    f = df.frequencia_deploy_semana
    q1, mediana, q3 = (float(f.quantile(q, interpolation='linear')) for q in [.25, .5, .75])
    distribuicao = df.classe_frequencia.value_counts().reindex(CLASSES, fill_value=0)
    classes = pd.DataFrame({'classe_frequencia': CLASSES, 'repositorios': distribuicao.values})
    classes['percentual'] = classes.repositorios / len(df) * 100
    resumo = {
        'repositorios': len(df), 'releases_principais': int(df.releases_janela.sum()),
        'inicio': inicio, 'fim_inclusivo': fim, 'semanas': semanas,
        'mediana': mediana, 'q1': q1, 'q3': q3, 'iqr': q3-q1,
        'minimo': float(f.min()), 'maximo': float(f.max()),
        'p90': float(f.quantile(.9)), 'quantis': 'interpolação linear (pandas)',
        'unidade': 'releases por semana',
        'classes': classes.to_dict(orient='records'),
        'auditoria': {
            'linhas_releases': len(releases), 'drafts_excluidos': int(draft.sum()),
            'prereleases_excluidas': int((~draft & pre).sum()),
            'fora_janela_excluidas': int((~draft & ~pre & ~((datas >= abertura) & (datas < fechamento))).sum()),
            'releases_incluidas': len(validas),
            'contagens_frequencias_classes_reconciliadas': True,
        },
        'cortes': {'Elite': '>= 7/semana', 'High': '>= 1 e < 7/semana',
                   'Medium': f'>= {1/SEMANAS_POR_MES:.12f} e < 1/semana',
                   'Low': f'< {1/SEMANAS_POR_MES:.12f}/semana'},
    }
    return df, classes, resumo


def complementar(df, releases, inicio, fim):
    """Concentração e cadência mensal, preservando zeros e extremos."""
    ordenados = df.sort_values(['releases_janela', 'nome_completo'], ascending=[False, True]).copy()
    total = int(df.releases_janela.sum())
    k = max(1, math.ceil(len(df)*.1))
    q1, q3 = df.frequencia_deploy_semana.quantile([.25, .75])
    limite = float(q3 + 1.5*(q3-q1))
    ordenados['participacao_releases_percentual'] = ordenados.releases_janela / total * 100 if total else 0.
    ordenados['extremo_superior_tukey'] = ordenados.frequencia_deploy_semana > limite
    concentracao = {
        'top_10pct_quantidade': k,
        'top_10pct_releases': int(ordenados.head(k).releases_janela.sum()),
        'top_10pct_participacao_percentual': float(ordenados.head(k).participacao_releases_percentual.sum()),
        'limite_superior_tukey': limite,
        'extremos_superiores': int(ordenados.extremo_superior_tukey.sum()),
        'criterio_extremo': 'frequência > Q3 + 1,5 × IQR; todos mantidos na análise',
        'desempate_top': 'nome_completo em ordem crescente; k = teto(0,1 × n)',
    }
    abertura = pd.Timestamp(inicio, tz='UTC')
    fim_exclusivo = pd.Timestamp(date.fromisoformat(fim)+timedelta(days=1), tz='UTC')
    datas = pd.to_datetime(releases.published_at, utc=True, errors='coerce', format='ISO8601')
    mascara = ~booleanos(releases.draft) & ~booleanos(releases.prerelease) & (datas >= abertura) & (datas < fim_exclusivo)
    validas = releases.loc[mascara, ['nome_completo']].copy()
    validas['mes'] = datas[mascara].dt.strftime('%Y-%m')
    meses = pd.period_range(inicio, fim, freq='M').astype(str)
    grade = pd.MultiIndex.from_product([df.nome_completo, meses], names=['nome_completo', 'mes'])
    painel = validas.groupby(['nome_completo','mes']).size().reindex(grade, fill_value=0).rename('releases').reset_index()
    dias = {}
    for mes in meses:
        primeiro = pd.Timestamp(mes+'-01', tz='UTC')
        proximo = pd.Timestamp((primeiro.date().replace(day=28)+timedelta(days=4)).replace(day=1), tz='UTC')
        dias[mes] = (min(proximo, fim_exclusivo)-max(primeiro, abertura)).days
    painel['dias_observados_mes'] = painel.mes.map(dias)
    painel['frequencia_semana'] = painel.releases * 7 / painel.dias_observados_mes
    mensais = []
    for mes, grupo in painel.groupby('mes', sort=True):
        f = grupo.frequencia_semana
        a, b, c = [float(f.quantile(q)) for q in [.25,.5,.75]]
        mensais.append(dict(mes=mes, dias_observados=dias[mes], repositorios=len(grupo),
                            releases=int(grupo.releases.sum()), mediana=b, q1=a, q3=c, iqr=c-a,
                            repositorios_sem_release=int((grupo.releases==0).sum()),
                            percentual_sem_release=float((grupo.releases==0).mean()*100)))
    assert int(painel.releases.sum()) == total, 'Painel mensal não reconcilia com a contagem anual.'
    return ordenados.reset_index(drop=True), painel, pd.DataFrame(mensais), concentracao


def graficos(df, classes, destino, mensal):
    cache = RAIZ / 'dados/.cache/matplotlib'
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR', str(cache))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    # IDs e metadados fixos tornam as figuras reexecutáveis sem alterações artificiais.
    matplotlib.rcParams['svg.hashsalt'] = 'rq91'

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), constrained_layout=True)
    valores = df.frequencia_deploy_semana.sort_values().to_numpy()
    axes[0].step(valores, [100*(i+1)/len(valores) for i in range(len(valores))], where='post', color='#205781')
    axes[0].set(xlabel='Releases por semana (escala symlog)', ylabel='Repositórios acumulados (%)',
                title='Distribuição acumulada — todos os repositórios', ylim=(0, 101))
    axes[0].set_xscale('symlog', linthresh=.1)
    axes[0].set_xlim(0, max(7, float(valores[-1]))*1.1)
    for x, rotulo in [(1/SEMANAS_POR_MES, '1/mês'), (1, '1/sem'), (7, '7/sem')]:
        axes[0].axvline(x, color='#888888', linestyle=':', linewidth=1)
        axes[0].text(x, 5, rotulo, rotation=90, va='bottom', ha='right', fontsize=8)
    axes[0].grid(alpha=.2)
    bars = axes[1].bar(classes.classe_frequencia, classes.repositorios, color=['#1C6855','#377EB8','#B58A27','#8D5959'])
    axes[1].bar_label(bars, labels=[f'{n}\n({p:.1f}%)' for n,p in zip(classes.repositorios,classes.percentual)], padding=4)
    axes[1].set(title='Classes de frequência (cortes da disciplina)', ylabel='Repositórios')
    axes[1].set_ylim(0, max(classes.repositorios)*1.25)
    fig.suptitle(f'RQ91 · Deployment Frequency · n = {len(df)}')
    for ext in ['png', 'svg']:
        fig.savefig(destino / f'frequencia_dora.{ext}', dpi=180, metadata={'Date': None} if ext=='svg' else None)
    plt.close(fig)
    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True, constrained_layout=True)
    x = list(range(len(mensal)))
    axes[0].fill_between(x, mensal.q1.to_numpy(), mensal.q3.to_numpy(), color='#D6E7F2', label='Q1–Q3 (dispersão)')
    axes[0].plot(x, mensal.mediana, color='#205781', marker='o', label='Mediana')
    axes[0].set(ylabel='Releases/semana', title='Cadência mensal — mesmos repositórios, incluindo zeros', ylim=(0, None))
    axes[0].legend(loc='upper left')
    axes[1].bar(x, mensal.percentual_sem_release, color='#8D5959')
    axes[1].set(ylabel='Sem release no mês (%)', ylim=(0, 105))
    axes[1].set_xticks(x, mensal.mes, rotation=40, ha='right')
    for ax in axes:
        ax.grid(axis='y', alpha=.2)
    for ext in ['png', 'svg']:
        fig.savefig(destino / f'cadencia_mensal.{ext}', dpi=180, metadata={'Date': None} if ext=='svg' else None)
    plt.close(fig)


def executar(entrada: Path, saida: Path):
    fontes = [entrada / nome for nome in ['metricas_repositorios.csv', 'releases.csv', 'resumo_execucao.json']]
    config = json.loads(fontes[2].read_text(encoding='utf-8'))['config']
    releases = pd.read_csv(fontes[1])
    df, classes, resumo = analisar(pd.read_csv(fontes[0]), releases, **config['janela'])
    ranking, painel, mensal, concentracao_dados = complementar(df, releases, **config['janela'])
    resumo['concentracao'] = concentracao_dados
    resumo['hipotese_h1'] = {
        'faixa_mediana_prevista': [0.5, 1.0],
        'mediana_dentro_faixa': .5 <= resumo['mediana'] <= 1.,
        'medium_high_percentual': float(classes.loc[classes.classe_frequencia.isin(['Medium','High']), 'percentual'].sum()),
        'elite_percentual': float(classes.loc[classes.classe_frequencia=='Elite', 'percentual'].iloc[0]),
        'interpretacao': 'Comparação descritiva. Poucos Elite e concentração não tinham cortes numéricos pré-registrados.',
    }
    resumo['janela_confirmada'] = config.get('janela_confirmada', False) is True
    resumo['fontes_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in fontes}
    saida.mkdir(parents=True, exist_ok=True)
    df.to_csv(saida / 'repositorios.csv', index=False, float_format='%.12g')
    classes.to_csv(saida / 'classes_dora.csv', index=False, float_format='%.6f')
    ranking.to_csv(saida / 'concentracao_repositorios.csv', index=False, float_format='%.12g')
    painel.to_csv(saida / 'painel_mensal.csv', index=False, float_format='%.12g')
    mensal.to_csv(saida / 'resumo_mensal.csv', index=False, float_format='%.12g')
    (saida / 'resumo.json').write_text(json.dumps(resumo, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    graficos(df, classes, saida, mensal)
    top = '\n'.join(f'| {r.nome_completo} | {r.releases_janela} | {r.frequencia_deploy_semana:.4f} | {r.participacao_releases_percentual:.2f}% |' for r in ranking.head(10).itertuples())
    tabela = '\n'.join(f'| {r.classe_frequencia} | {r.repositorios} | {r.percentual:.2f}% |' for r in classes.itertuples())
    hipotese = 'compatível com' if .5 <= resumo['mediana'] <= 1 else 'fora de'
    concentracao = classes.loc[classes.classe_frequencia.isin(['Medium', 'High']), 'percentual'].sum()
    elite = classes.loc[classes.classe_frequencia == 'Elite', 'percentual'].iloc[0]
    ressalva = 'Confirmada na configuração de entrada.' if resumo['janela_confirmada'] else '**Provisória: janela ainda não confirmada pelo professor na configuração.**'
    texto = f'''# RQ91 — RQ01: Deployment Frequency e classificação DORA

## Método e rastreabilidade

Janela inclusiva UTC: {resumo['inicio']} a {resumo['fim_inclusivo']} ({resumo['semanas']:.6f} semanas). {ressalva}

Cada repositório tem o mesmo peso. Frequência = releases publicadas, não draft e não prerelease na janela / semanas da janela. Tags sem release ficam de fora. Os filtros usam published_at; não o texto da tag nem a marca dentro_janela. Contagens, frequências e classes foram reconciliadas com metricas_repositorios.csv. A classificação usa precisão completa antes do arredondamento. As faixas são as fixadas pela disciplina, reutilizando metricas/dora.py; um mês médio corresponde a 365,25/12 dias.

## Resultados

- Repositórios: **{resumo['repositorios']}**; releases principais: **{resumo['releases_principais']}**.
- Mediana: **{resumo['mediana']:.4f} releases/semana**.
- Q1–Q3: **{resumo['q1']:.4f}–{resumo['q3']:.4f}**; IQR (Q3 − Q1): **{resumo['iqr']:.4f}**.
- Mínimo–máximo: **{resumo['minimo']:.4f}–{resumo['maximo']:.4f}**; P90: **{resumo['p90']:.4f}**.
- Quartis calculados por interpolação linear; valores extremos mantidos.

| Classe de frequência | Repositórios | Percentual |
|---|---:|---:|
{tabela}

![Distribuição e classes de frequência](frequencia_dora.png)

Elite ≥ 7/semana; High ≥ 1 e < 7/semana; Medium ≥ 1/mês médio e < 1/semana; Low < 1/mês médio. **Esta é a classe de frequência, não a classificação geral das quatro métricas.**

## Discussão da H1 e limites

A H1 registrada em entregas/laboratorio-03/artigo/introducao.tex previa mediana entre 0,5 e 1 release/semana, concentração Medium/High e poucos Elite. A mediana observada está {hipotese} essa faixa. Medium e High somam {concentracao:.2f}% e Elite representa {elite:.2f}%. A distribuição acumulada e o contraste entre Q3 e máximo permitem avaliar a cauda à direita sem excluir extremos. A hipótese original foi preservada. Esta comparação é descritiva, sem teste de hipótese ou alegação causal.

Não foi atribuído um novo limite numérico a “poucos Elite” ou “concentração” depois de observar os resultados. A compatibilidade dessas partes da H1 é qualitativa; a comparação da mediana usa a faixa originalmente registrada. IQR descreve dispersão, não intervalo de confiança. Não estimamos um intervalo populacional com base nesta seleção não probabilística.

## Concentração e extremos

Os {concentracao_dados['top_10pct_quantidade']} repositórios de maior contagem (10% da amostra, arredondado para cima) concentram **{concentracao_dados['top_10pct_participacao_percentual']:.2f}% das releases**. Empates no corte são desfeitos pelo nome. Isso distingue a parcela de projetos em cada classe da parcela de releases produzida por eles.

Há **{concentracao_dados['extremos_superiores']} extremos superiores**, acima de Q3 + 1,5 × IQR = **{concentracao_dados['limite_superior_tukey']:.4f} releases/semana**. Esse sinalizador descritivo não prova erro ou automação; nenhuma observação foi removida. A tabela identifica os dez maiores para inspeção das práticas de publicação, sem presumir suas causas.

| Repositório | Releases | Releases/semana | Participação no total |
|---|---:|---:|---:|
{top}

## Cadência mensal

![Cadência e meses sem releases](cadencia_mensal.png)

O painel mantém todos os {resumo['repositorios']} repositórios em todos os meses, inclusive combinações sem releases. A frequência mensal é contagem × 7 / dias observados do mês; meses de tamanhos diferentes e eventuais meses parciais são normalizados. Os totais mensais reconciliam com as {resumo['releases_principais']} releases anuais.

A faixa Q1–Q3 mostra dispersão entre repositórios, não incerteza estatística. Meses anteriores à criação de um projeto permanecem com zero para preservar a coorte e o denominador comuns. Assim, a curva pode refletir entrada de projetos e não demonstra melhoria, piora ou sazonalidade. A mediana das frequências mensais não substitui a frequência anual nem define as classes DORA desta RQ.

Release é uma aproximação de deploy: bibliotecas, monorepos e coleções podem publicar versões sem colocar software em produção. O filtro mínimo de cinco releases elimina projetos de frequência muito baixa. A seleção de 300 candidatos, o limite de 20 mil runs e a janela fixa limitam a generalização. Repositórios criados durante a janela continuam com o denominador comum, conforme o enunciado; isso pode reduzir sua frequência. A validação humana da amostra-ouro e a sensibilidade da RQ07 continuam necessárias. Esta análise não utiliza sugestões de IA como rótulos humanos.

## Reprodução e arquivos

Na raiz: `python codigo-fonte/analise/rq91_deployment_frequency.py`.
Entradas em `dados/lab03_final`; opções `--entrada` e `--saida` permitem outra coleta e destino.

- `repositorios.csv`: nome_completo e linguagem da coleta; releases_janela recontada; semanas_janela em semanas; frequencia_deploy_semana = contagem/semanas; classe_frequencia pelos cortes acima.
- `classes_dora.csv`: classe_frequencia, repositorios (contagem), percentual = contagem/n × 100; inclui categorias com zero casos.
- `resumo.json`: estatísticas, cortes, janela e SHA-256 de cada entrada.
- `frequencia_dora.png` e `.svg`: figura raster e vetorial.
- `concentracao_repositorios.csv`: ranking completo, participação no total (%) e sinalizador extremo_superior_tukey; mesmas unidades das métricas originais.
- `painel_mensal.csv`: nome_completo × mes (AAAA-MM), releases (contagem), dias_observados_mes e frequencia_semana = releases × 7 / dias.
- `resumo_mensal.csv`: por mês, dias_observados, repositorios (n), releases (total), mediana/q1/q3/iqr em releases/semana, repositorios_sem_release e percentual_sem_release (sobre n).
- `cadencia_mensal.png` e `.svg`: dispersão mensal e proporção sem releases.

`resumo.json` também registra filtros mutuamente exclusivos: primeiro drafts, depois prereleases não draft, depois releases principais fora da janela e, por fim, incluídas. A soma desses grupos deve corresponder às linhas da entrada. Comparações exigem datas válidas nas releases publicadas, IDs únicos e concordância com o CSV de métricas. As saídas numéricas e SVG são determinísticas com as mesmas entradas e versões das dependências.

Referências locais: enunciado LAB03, seções 3, 5 (RQ01/RQ07) e 8; `codigo-fonte/metricas/dora.py`.
'''
    (saida / 'RELATORIO.md').write_text(texto, encoding='utf-8')
    return resumo


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--entrada', type=Path, default=RAIZ/'dados/lab03_final')
    parser.add_argument('--saida', type=Path, default=RAIZ/'entregas/laboratorio-03/sprint-03/RQ91')
    args = parser.parse_args()
    resultado = executar(args.entrada, args.saida)
    print(f"RQ91: {resultado['repositorios']} repositórios; mediana {resultado['mediana']:.4f}; IQR {resultado['iqr']:.4f}.")
    print(f'Resultados: {args.saida}')
