"""RQ92 / RQ04: recuperação de CI, censura e confronto com H4, sem rede."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path

import pandas as pd

CODIGO = Path(__file__).resolve().parents[1]
RAIZ = CODIGO.parent
sys.path.insert(0, str(CODIGO))
from coleta.coleta_dora import limites_da_janela  # noqa: E402
from metricas import ci, dora  # noqa: E402


def respeitar_corte(episodios, fim):
    """Sucesso após o corte não é recuperação observada dentro da janela."""
    ajustados, tardios, fora = [], 0, 0
    for original in episodios:
        e = dict(original)
        if e['inicio'] > fim:
            fora += 1
            continue
        e['sucesso_apos_janela'] = not e['censurado'] and e['fim'] > fim
        if e['sucesso_apos_janela']:
            tardios += 1
            e.update(fim=fim, censurado=True)
        e['horas'] = (e['fim']-e['inicio']).total_seconds()/3600
        if not math.isfinite(e['horas']) or e['horas'] < 0:
            raise ValueError('Episódio com duração inválida.')
        e['completo'] = not e['censurado'] and not e['censura_esquerda']
        e['situacao'] = ('ambas' if e['censurado'] and e['censura_esquerda'] else
                        'direita' if e['censurado'] else 'esquerda' if e['censura_esquerda'] else 'completo')
        ajustados.append(e)
    return ajustados, tardios, fora


def resumir_episodios(episodios):
    completos = pd.Series([e['horas'] for e in episodios if e['completo']], dtype=float)
    n = len(episodios)
    direita = sum(e['censurado'] for e in episodios)
    esquerda = sum(e['censura_esquerda'] for e in episodios)
    ambas = sum(e['situacao']=='ambas' for e in episodios)
    mediana = float(completos.median()) if len(completos) else None
    return dict(episodios=n, completos=len(completos), censura_direita=direita,
                censura_esquerda=esquerda, censura_ambas=ambas,
                censura_qualquer=direita+esquerda-ambas,
                proporcao_censura_direita=direita/n if n else None,
                proporcao_censura_qualquer=(direita+esquerda-ambas)/n if n else None,
                recuperacao_mediana_horas=mediana,
                classe_recuperacao=dora.classificar_recuperacao(mediana) or 'Não estimável',
                situacao_repositorio='estimável' if len(completos) else 'somente censura' if n else 'sem episódio')


def reconciliar(original, salvo):
    pares = {'episodios':'episodios_falha', 'episodios_completos':'episodios_completos',
             'episodios_censurados':'episodios_censurados',
             'episodios_censura_esquerda':'episodios_censura_esquerda',
             'mediana_horas':'recuperacao_mediana_horas'}
    for calculado, exportado in pares.items():
        a, b = original[calculado], salvo[exportado]
        if a is None and pd.isna(b):
            continue
        if a is None or pd.isna(b) or abs(a-float(b)) > .00000051:
            raise ValueError(f"Métrica não reconciliada em {salvo['nome_completo']}: {exportado}")


def estatisticas(serie):
    s = pd.Series(serie, dtype=float).dropna()
    if s.empty:
        return dict(n=0, mediana=None, q1=None, q3=None, iqr=None, minimo=None, maximo=None)
    q1, mediana, q3 = [float(s.quantile(q)) for q in [.25,.5,.75]]
    return dict(n=len(s), mediana=mediana, q1=q1, q3=q3, iqr=q3-q1,
                minimo=float(s.min()), maximo=float(s.max()))


def analisar_horizontes(ep, df):
    """Limites descritivos sem imputar recuperação nem supor censura independente.

    Exclui início desconhecido (censura esquerda). Uma censura direita antes
    do horizonte deixa o desfecho indeterminado; no/depois do horizonte,
    confirma ausência de recuperação até aquele instante.
    """
    conhecidos = ep.loc[~ep.censura_esquerda.astype(bool)]
    linhas = []
    for nome, grupo in conhecidos.groupby('nome_completo', sort=True):
        for h in [1,24,168]:
            recuperados = int((~grupo.censurado.astype(bool) & (grupo.horas<=h)).sum())
            desconhecidos = int((grupo.censurado.astype(bool) & (grupo.horas<h)).sum())
            n = len(grupo)
            linhas.append(dict(nome_completo=nome, horizonte_horas=h, episodios=n,
                recuperados=recuperados, indeterminados=desconhecidos,
                nao_recuperados=n-recuperados-desconhecidos,
                limite_inferior=recuperados/n, limite_superior=(recuperados+desconhecidos)/n))
    por_repo = pd.DataFrame(linhas, columns=['nome_completo','horizonte_horas','episodios',
        'recuperados','indeterminados','nao_recuperados','limite_inferior','limite_superior'])
    resumo = []
    for h in [1,24,168]:
        g = por_repo.loc[por_repo.horizonte_horas==h]
        n, rec, inc = [int(g[c].sum()) for c in ['episodios','recuperados','indeterminados']]
        resumo.append(dict(horizonte_horas=h, repositorios=len(g), episodios=n,
            recuperados=rec, indeterminados=inc, nao_recuperados=n-rec-inc,
            limite_inferior=rec/n if n else None, limite_superior=(rec+inc)/n if n else None,
            limite_inferior_peso_igual=float(g.limite_inferior.mean()) if len(g) else None,
            limite_superior_peso_igual=float(g.limite_superior.mean()) if len(g) else None,
            episodios_excluidos_inicio_desconhecido=len(ep)-len(conhecidos)))
    robustez=[]
    for minimo in [1,5,10]:
        grupo=df.loc[df.completos>=minimo]
        robustez.append(dict(minimo_completos=minimo, excluidos=len(df)-len(grupo),
                             **estatisticas(grupo.recuperacao_mediana_horas)))
    return por_repo, pd.DataFrame(resumo), pd.DataFrame(robustez)


def analisar(metricas, runs, inicio, fim):
    for tabela, campos in [(metricas, {'nome_completo','branch_padrao','recuperacao_mediana_horas',
        'episodios_falha','episodios_completos','episodios_censurados','episodios_censura_esquerda'}),
        (runs, {'nome_completo','id','workflow_id','event','head_branch','conclusion','created_at','run_started_at','updated_at'})]:
        if not campos.issubset(tabela.columns):
            raise ValueError(f'Colunas ausentes: {sorted(campos-set(tabela.columns))}')
    if metricas.empty or metricas.nome_completo.isna().any() or metricas.nome_completo.duplicated().any():
        raise ValueError('Amostra vazia ou identificadores inválidos/duplicados.')
    chaves = runs[['nome_completo','id','workflow_id']]
    if chaves.isna().any().any() or chaves.astype(str).apply(lambda c:c.str.strip().eq('')).any().any() or runs.duplicated(['nome_completo','id']).any():
        raise ValueError('Runs com identificadores ausentes/duplicados.')
    if not set(runs.nome_completo).issubset(set(metricas.nome_completo)):
        raise ValueError('Runs fora da amostra.')
    abertura, fechamento = limites_da_janela(inicio, fim)
    grupos = {nome:g for nome,g in runs.groupby('nome_completo', sort=False)}
    linhas, detalhes, divergencias = [], [], []
    total_validos = 0
    for salvo in metricas.sort_values('nome_completo').to_dict('records'):
        nome = salvo['nome_completo']
        registros = grupos[nome].to_dict('records') if nome in grupos else []
        validos = ci.filtrar_runs_validos(registros, salvo['branch_padrao'], abertura, fechamento)
        total_validos += len(validos)
        original = ci.tempo_de_recuperacao(validos, fechamento)
        reconciliar(original, salvo)
        episodios, tardios, fora = respeitar_corte(original['detalhes'], fechamento)
        r = resumir_episodios(episodios)
        linhas.append(dict(nome_completo=nome, runs_validos=len(validos), **r))
        detalhes.extend(dict(nome_completo=nome, **e) for e in episodios)
        divergencias.append(dict(nome_completo=nome, sucessos_apos_janela=tardios,
            episodios_iniciados_apos_janela=fora, mediana_exportada=original['mediana_horas'],
            mediana_rq92=r['recuperacao_mediana_horas'], completos_exportados=original['episodios_completos'],
            completos_rq92=r['completos'], censura_direita_exportada=original['episodios_censurados'],
            censura_direita_rq92=r['censura_direita']))
    df = pd.DataFrame(linhas)
    ep = pd.DataFrame(detalhes, columns=['nome_completo','workflow_id','inicio','fim','falhas','censura_esquerda',
                                      'horas','censurado','sucesso_apos_janela','completo','situacao'])
    audit = pd.DataFrame(divergencias)
    categorias = ['Elite','High','Medium','Low','Não estimável']
    contagens = df.classe_recuperacao.value_counts().reindex(categorias, fill_value=0)
    classes = pd.DataFrame({'classe_recuperacao':categorias, 'repositorios':contagens.values})
    classes['percentual_amostra'] = classes.repositorios / len(df)*100
    n_est = int(df.recuperacao_mediana_horas.notna().sum())
    classes['percentual_estimaveis'] = [n/n_est*100 if n_est and c!='Não estimável' else None
                                      for c,n in zip(categorias,contagens.values)]
    resumo = dict(repositorios=len(df), runs_lidos=len(runs), runs_validos=total_validos,
        janela=dict(inicio=inicio, fim=fim), recuperacao_horas=estatisticas(df.recuperacao_mediana_horas),
        censura_direita_por_repositorio=estatisticas(df.proporcao_censura_direita),
        censura_qualquer_por_repositorio=estatisticas(df.proporcao_censura_qualquer),
        repositorios_censura_direita_ge_10pct=int((df.proporcao_censura_direita>=.1).sum()),
        episodios={k:int(df[k].sum()) for k in ['episodios','completos','censura_direita','censura_esquerda','censura_ambas','censura_qualquer']},
        situacoes=df.situacao_repositorio.value_counts().to_dict(), classes=classes.to_dict('records'),
        sucessos_tardios_reclassificados=int(audit.sucessos_apos_janela.sum()),
        episodios_iniciados_apos_janela=int(audit.episodios_iniciados_apos_janela.sum()),
        repositorios_com_correcao_corte=int(((audit.sucessos_apos_janela>0)|(audit.episodios_iniciados_apos_janela>0)).sum()))
    total = resumo['episodios']['episodios']
    resumo['censura_direita_global'] = resumo['episodios']['censura_direita']/total if total else None
    return df, ep, audit, classes, resumo


def graficos(df, ep, classes, destino):
    cache = RAIZ/'dados/.cache/matplotlib'
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR', str(cache))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    matplotlib.rcParams['svg.hashsalt'] = 'rq92'
    fig, axes = plt.subplots(1,3,figsize=(15,4.6),constrained_layout=True)
    valores = df.recuperacao_mediana_horas.dropna().sort_values().to_numpy()
    if len(valores):
        axes[0].step(valores,[(i+1)/len(valores)*100 for i in range(len(valores))],where='post')
    axes[0].set_xscale('symlog',linthresh=1)
    axes[0].set(xlabel='Mediana do repositório (horas, symlog)',ylabel='Repositórios estimáveis (%)',
                title=f'Recuperação · n = {len(valores)}',ylim=(0,101),xlim=(0,max(168,max(valores,default=0))*1.1))
    for x in [1,24,168]:axes[0].axvline(x,color='gray',linestyle=':',linewidth=1)
    bars=axes[1].bar(['Elite','High','Medium','Low','Não\nestimável'],classes.repositorios,
                     color=['#1C6855','#377EB8','#B58A27','#8D5959','#999999'])
    axes[1].bar_label(bars,padding=3)
    axes[1].set(title='Classes de recuperação',ylabel='Repositórios',ylim=(0,max(classes.repositorios)*1.2))
    counts=ep.situacao.value_counts().reindex(['completo','direita','esquerda','ambas'],fill_value=0)
    bars=axes[2].bar(['Completo','Só direita','Só esquerda','Ambas'],counts.values,color=['#377EB8','#B58A27','#8D5959','#999999'])
    axes[2].bar_label(bars,padding=3)
    axes[2].set(title='Episódios · grupos sem sobreposição',ylabel='Episódios',ylim=(0,max(1,max(counts))*1.2))
    axes[2].tick_params(axis='x',labelsize=8)
    fig.suptitle('RQ92 · Recuperação após falhas de CI (proxy)')
    for ext in ['png','svg']:
        fig.savefig(destino/f'recuperacao_censura.{ext}',dpi=180,metadata={'Date':None} if ext=='svg' else None)
    plt.close(fig)


def grafico_horizontes(horizontes, destino):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9,4.5), constrained_layout=True)
    x=list(range(len(horizontes)))
    inferior=horizontes.limite_inferior.fillna(0)*100
    largura=(horizontes.limite_superior-horizontes.limite_inferior).fillna(0)*100
    ax.bar(x,inferior,color='#377EB8',label='Recuperação confirmada')
    ax.bar(x,largura,bottom=inferior,color='#E3B34F',label='Desfecho indeterminado por censura')
    for i,r in enumerate(horizontes.itertuples()):
        label='Sem dados' if pd.isna(r.limite_inferior) else f'{100*r.limite_inferior:.2f}%–{100*r.limite_superior:.2f}%'
        ax.text(i, (0 if pd.isna(r.limite_superior) else r.limite_superior*100)+1.5,label,ha='center')
    ax.set_xticks(x,['Até 1 hora','Até 24 horas','Até 7 dias'])
    ax.set(ylabel='Episódios com início conhecido (%)',ylim=(0,112),
           title='Recuperação por prazo · limites descritivos da amostra')
    ax.legend(loc='upper left',bbox_to_anchor=(0,-.12),fontsize=9)
    for ext in ['png','svg']:
        fig.savefig(destino/f'horizontes_recuperacao.{ext}',dpi=180,metadata={'Date':None} if ext=='svg' else None)
    plt.close(fig)


def numero(x):
    return 'não estimável' if x is None else f'{x:.4f}'


def executar(entrada, saida):
    fontes=[entrada/n for n in ['metricas_repositorios.csv','workflow_runs.csv.gz','resumo_execucao.json']]
    config=json.loads(fontes[2].read_text(encoding='utf-8'))['config']
    m=pd.read_csv(fontes[0])
    runs=pd.read_csv(fontes[1],keep_default_na=False)
    df,ep,audit,classes,resumo=analisar(m,runs,**config['janela'])
    por_repo,horizontes,robustez=analisar_horizontes(ep,df)
    resumo['horizontes']=json.loads(horizontes.to_json(orient='records',force_ascii=False))
    resumo['robustez_cobertura']=json.loads(robustez.to_json(orient='records',force_ascii=False))
    resumo['janela_confirmada']=config.get('janela_confirmada',False) is True
    resumo['fontes_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in fontes}
    # JSON estrito: categorias sem denominador têm null, não NaN.
    resumo['classes']=json.loads(classes.to_json(orient='records',force_ascii=False))
    saida.mkdir(parents=True,exist_ok=True)
    for nome,tabela in [('repositorios',df),('episodios',ep),('auditoria_corte',audit),('classes_dora',classes),
                       ('horizontes_por_repositorio',por_repo),('horizontes_resumo',horizontes),('robustez_cobertura',robustez)]:
        tabela.to_csv(saida/f'{nome}.csv',index=False,float_format='%.12g')
    (saida/'resumo.json').write_text(json.dumps(resumo,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    graficos(df,ep,classes,saida)
    grafico_horizontes(horizontes,saida)
    def pct(v):
        return 'não estimável' if pd.isna(v) else f'{100*v:.2f}%'
    tabela_h='\n'.join(f'| {r.horizonte_horas} h | {r.episodios} | {r.recuperados} | {r.indeterminados} | {pct(r.limite_inferior)}–{pct(r.limite_superior)} | {pct(r.limite_inferior_peso_igual)}–{pct(r.limite_superior_peso_igual)} |' for r in horizontes.itertuples())
    tabela_r='\n'.join(f'| {r.minimo_completos} | {r.n} | {r.excluidos} | {numero(r.mediana) if not pd.isna(r.mediana) else "não estimável"} | {numero(r.iqr) if not pd.isna(r.iqr) else "não estimável"} |' for r in robustez.itertuples())
    dia=horizontes.loc[horizontes.horizonte_horas==24].iloc[0]
    medianas_robustez='; '.join(f'mínimo {r.minimo_completos}: {numero(r.mediana) if not pd.isna(r.mediana) else "não estimável"} h (n={r.n})' for r in robustez.itertuples())
    s=resumo['recuperacao_horas']; c=resumo['episodios']; cens=resumo['censura_direita_por_repositorio']
    tabela='\n'.join(f'| {r.classe_recuperacao} | {r.repositorios} | {r.percentual_amostra:.2f}% |' for r in classes.itertuples())
    h4='não avaliável' if s['mediana'] is None else 'compatível' if 1<=s['mediana']<24 else 'fora da faixa prevista'
    cens_h4 = ('não avaliável' if resumo['censura_direita_global'] is None else
               'abaixo' if resumo['censura_direita_global']<.1 else 'igual ou acima')
    aviso='confirmada na configuração' if resumo['janela_confirmada'] else '**ainda não confirmada pelo professor na configuração**'
    relatorio=f'''# RQ92 — RQ04: Tempo de recuperação após falhas

## Pergunta e método

Qual o tempo de recuperação após uma execução de CI/CD com falha? Análise local de **{len(df)} repositórios**, janela UTC inclusiva {config['janela']['inicio']} a {config['janela']['fim']}, {aviso}.

Somente runs criados na janela, do default branch e disparados por push. Success encerra um episódio; failure, timed_out e startup_failure indicam falha; demais conclusões são ignoradas. Cada workflow é ordenado separadamente. Falhas consecutivas formam um único episódio: início da primeira falha até updated_at do sucesso seguinte. Usa-se run_started_at (fallback created_at, conforme o módulo de métricas). A mediana do repositório considera todos os episódios completos dos seus workflows; a estatística da amostra é a mediana dessas medianas, com igual peso por repositório. Não é a mediana de todos os episódios agrupados.

Primeira falha sem sucesso anterior observado é marcada como censura à esquerda pelo projeto. Episódio não recuperado no corte é censurado à direita. Esses registros permanecem no CSV, mas não entram no cálculo pontual de recuperação. Durações censuradas são limites observados, não tempos finais. Um repositório sem episódio completo recebe **Não estimável**, nunca zero ou Elite.

## Resultados e análise escrita

Há **{s['n']} repositórios com tempo estimável** e **{len(df)-s['n']} sem estimativa**. A mediana das medianas é **{numero(s['mediana'])} horas**; Q1–Q3 = **{numero(s['q1'])}–{numero(s['q3'])} horas** e IQR = **{numero(s['iqr'])} horas**. Mínimo–máximo = {numero(s['minimo'])}–{numero(s['maximo'])} horas. Quartis usam interpolação linear; extremos permanecem na amostra.

| Classe de recuperação | Repositórios | % de toda a amostra |
|---|---:|---:|
{tabela}

Faixas da disciplina: Elite < 1 h; High ≥ 1 h e < 24 h; Medium ≥ 24 h e < 168 h; Low ≥ 168 h. Estas classes representam somente recuperação, não a classificação DORA geral. O CSV inclui percentuais sobre a amostra toda e, separadamente, sobre os estimáveis.

![Recuperação e censura](recuperacao_censura.png)

## Censura e cobertura

- Runs lidos: {resumo['runs_lidos']}; válidos após filtros: {resumo['runs_validos']}.
- Episódios: **{c['episodios']}**, dos quais **{c['completos']} completos**.
- Censura à direita: **{c['censura_direita']}**; à esquerda: **{c['censura_esquerda']}**; ambas: **{c['censura_ambas']}**.
- União de censuras: **{c['censura_qualquer']}**. Direita e esquerda não devem ser somadas sem descontar a interseção.
- Proporção global à direita: **{numero(resumo['censura_direita_global']*100 if resumo['censura_direita_global'] is not None else None)}%** dos episódios.
- Entre os {cens['n']} repositórios com episódios, proporção de censura à direita: mediana **{numero(cens['mediana'])}**, Q1–Q3 **{numero(cens['q1'])}–{numero(cens['q3'])}** (frações de 0 a 1).
- Situações por repositório: {json.dumps(resumo['situacoes'],ensure_ascii=False)}.

A proporção global pesa mais os projetos com muitos episódios; a mediana das proporções dá igual peso a cada repositório com episódios. Por isso, os dois indicadores respondem a perguntas distintas. Repositórios sem episódios ficam fora do denominador da proporção, sem receber artificialmente censura zero.

## Auditoria do encerramento da janela

As métricas originais foram reconstituídas a partir dos runs e conferidas com o CSV de entrada (tolerância de exportação: seis casas decimais). Depois da reconciliação, a RQ92 aplica o corte temporal: **{resumo['sucessos_tardios_reclassificados']} episódios** cujo sucesso terminou após a janela passam a censurados. Foram excluídos **{resumo['episodios_iniciados_apos_janela']} episódios** cujo início real só ocorreu após o corte. **{resumo['repositorios_com_correcao_corte']} repositórios** tiveram ajuste no encerramento. O arquivo auditoria_corte.csv mostra antes/depois, incluindo medianas e contagens. Os dados coletados e as métricas exportadas originais não são sobrescritos; esta correção deve ser considerada antes de reutilizar a classe de recuperação original em outras RQs.

## Confronto com H4 e interpretação

A H4 em artigo/introducao.tex previa recuperação mediana entre uma hora e um dia (High), cauda longa e censura abaixo de 10%. Resultado para a faixa de recuperação prevista: **{h4}**. A tabela e a distribuição mostram a heterogeneidade sem equiparar todos os projetos ao comportamento da mediana. O máximo de {numero(s['maximo'])} horas, comparado ao Q3 de {numero(s['q3'])} horas, permite avaliar a extensão da cauda.

A censura à direita global está **{cens_h4} de 10%**, mas **{resumo['repositorios_censura_direita_ge_10pct']} repositórios** apresentam pelo menos 10% de censura à direita. Logo, uma baixa proporção global não implica cobertura adequada em todos os projetos. A contagem por repositório e a separação de casos não estimáveis são necessárias para interpretar a H4.

A censura é apresentada tanto globalmente quanto por repositório, sem escolher posteriormente o denominador mais favorável à hipótese. Essa comparação é descritiva; não prova que toda falha se recupera no mesmo dia. As medianas são condicionadas a episódios completos: excluir durações desconhecidas do cálculo pode favorecer episódios curtos, especialmente em projetos com alta censura. Não atribuímos aos censurados a duração até o corte como se fossem recuperações e não estimamos tempos desconhecidos.

## Recuperação por prazo: o que é observado e o que permanece desconhecido

Para complementar a mediana, avaliamos se cada episódio se recuperou em até **1 h, 24 h e 168 h**. Excluímos os {int(ep.censura_esquerda.sum())} episódios sem início conhecido. Entre os restantes, um sucesso até o prazo confirma recuperação; uma duração completa acima do prazo ou censura direita no/depois do prazo confirma que não houve recuperação até ali. Censura antes do prazo deixa o desfecho indeterminado.

O limite inferior é recuperados/n; o superior é (recuperados + indeterminados)/n. São limites descritivos dos desfechos da amostra, **não intervalos de confiança**, previsões ou estimativas de sobrevivência. Não imputamos data de recuperação. A coluna de peso igual calcula a média dos limites de cada repositório com início conhecido; a coluna por episódio pesa mais projetos com muitos episódios. Nenhuma substitui a mediana principal.

| Prazo | Episódios | Recuperados | Indeterminados | Limites por episódio | Limites com peso igual por repositório |
|---|---:|---:|---:|---|---|
{tabela_h}

Em 24 horas, a recuperação confirmada corresponde a **{pct(dia.limite_inferior)} dos episódios**, versus **{pct(dia.limite_inferior_peso_igual)} com peso igual por repositório**. A diferença mostra por que a resposta sobre um episódio e a resposta sobre um projeto não devem ser confundidas. Os limites superiores correspondentes são {pct(dia.limite_superior)} e {pct(dia.limite_superior_peso_igual)}; o intervalo incorpora apenas os desfechos indeterminados entre os episódios de início conhecido.

![Recuperação por prazo e censura](horizontes_recuperacao.png)

Os horizontes incluem o instante exato (≤). Isso é diferente dos cortes estritos de classe DORA (< 1 h, < 24 h, < 168 h); o resultado por prazo não reclassifica repositórios. Um intervalo estreito indica pouca indeterminação por censura direita naquele prazo, não ausência de viés de seleção ou de censura esquerda.

## Robustez à quantidade de episódios completos

Uma mediana baseada em um único episódio oferece menos evidência que uma baseada em dezenas. Recalculamos a estatística em subconjuntos exploratórios com no mínimo 5 e 10 episódios completos. São limiares de diagnóstico, não critérios novos de inclusão nem confirmação da H4.

| Mínimo de completos | Repositórios | Excluídos da amostra de 300 | Mediana (h) | IQR (h) |
|---|---:|---:|---:|---:|
{tabela_r}

Comparação das medianas: **{medianas_robustez}**. Essa leitura permite verificar se o valor central depende fortemente de projetos com poucos episódios completos, sem redefinir a amostra oficial.

Os subconjuntos podem conter projetos de perfis diferentes. Alterações na mediana não demonstram que aumentar o número de falhas melhora ou piora a recuperação. A análise principal continua incluindo todos os repositórios estimáveis; a censura é mantida nas saídas e no diagnóstico de cobertura.

## Limitações

Falha de CI não equivale a incidente em produção. O tempo inclui espera até nova execução, agendamento e duração do pipeline, não apenas trabalho ativo de reparo. Não há evidência aqui para atribuir caudas longas especificamente a workflows secundários. Execuções concorrentes, reexecuções e updated_at como aproximação do término limitam a interpretação; o CSV contém o estado coletado, não um histórico completo de mudanças de estado. O agrupamento segue o módulo existente por workflow e início da execução. Repositórios populares, filtros de inclusão e limite de runs geram seleção não probabilística. A censura à esquerda reflete falta de histórico anterior, não necessariamente o início real da falha. IQR é dispersão, não intervalo de confiança.

## Reprodução e dicionário das saídas

`python codigo-fonte/analise/rq92_tempo_recuperacao.py`

Opções: --entrada (pasta da coleta) e --saida (destino). Não exige token ou rede.

- repositorios.csv: nome_completo; runs_validos; episodios/completos/censura_direita/censura_esquerda/censura_ambas/censura_qualquer (contagens); proporcao_censura_* (fração, vazio sem episódios); recuperacao_mediana_horas (vazio sem completos); classe_recuperacao e situacao_repositorio.
- episodios.csv: repositório, workflow_id, inicio/fim UTC, falhas (runs no episódio), horas (duração completa ou parcial), censurado (direita), censura_esquerda, sucesso_apos_janela, completo e situacao (grupos exclusivos).
- auditoria_corte.csv: repositório, sucessos_apos_janela e episodios_iniciados_apos_janela (contagens), medianas antes/depois em horas, completos e censuras à direita antes/depois.
- classes_dora.csv: classe, contagem e percentuais (amostra total e somente estimáveis); Não estimável não recebe percentual entre estimáveis.
- resumo.json: estatísticas, cobertura, censura, auditoria e SHA-256 das entradas. Campos sem estimativa são null.
- recuperacao_censura.png/.svg: distribuição acumulada das medianas, classes e episódios sem dupla contagem.
- horizontes_por_repositorio.csv: nome_completo, horizonte_horas, episodios (início conhecido), recuperados/indeterminados/nao_recuperados (contagens), limite_inferior e limite_superior (frações).
- horizontes_resumo.csv: mesmos totais por horizonte, repositorios incluídos, limites por episódio e limites *_peso_igual (média por repositório), episodios_excluidos_inicio_desconhecido.
- robustez_cobertura.csv: minimo_completos (limiar), excluidos, n e mediana/q1/q3/iqr/minimo/maximo em horas. Campos sem dados ficam vazios.
- horizontes_recuperacao.png/.svg: limites descritivos por prazo; não são intervalos de confiança.

Referências locais: enunciado LAB03, seções 3 e 5 (RQ04); metricas/ci.py; metricas/dora.py; H4 registrada em entregas/laboratorio-03/artigo/introducao.tex.
'''
    (saida/'RELATORIO.md').write_text(relatorio,encoding='utf-8')
    return resumo


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--entrada',type=Path,default=RAIZ/'dados/lab03_final')
    p.add_argument('--saida',type=Path,default=RAIZ/'entregas/laboratorio-03/sprint-03/RQ92')
    args=p.parse_args()
    r=executar(args.entrada,args.saida)
    print(json.dumps({k:r[k] for k in ['recuperacao_horas','episodios','sucessos_tardios_reclassificados']},ensure_ascii=False,indent=2))
