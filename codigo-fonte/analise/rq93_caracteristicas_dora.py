"""RQ93 / RQ06: características e métricas DORA, análise local reproduzível."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests

RAIZ = Path(__file__).resolve().parents[2]
METRICAS = {
    'frequencia_deploy_semana': ('Frequência', 'releases/semana', 'maior'),
    'lead_time_release_mediana_dias': ('Lead time (a)', 'dias', 'menor'),
    'cfr_ci': ('CFR (a)', 'fração', 'menor'),
    'recuperacao_mediana_horas': ('Recuperação', 'horas', 'menor'),
}
NUMERICOS = ['contribuidores_total', 'estrelas', 'idade_anos']
FATORES = NUMERICOS + ['linguagem']
MINIMO = 5


def quartis(serie):
    """Cortes fixados na amostra do fator, sem separar valores empatados."""
    cortes = serie.dropna().quantile([.25,.5,.75]).to_numpy()
    if len(serie.dropna()) == 0:
        return pd.Series(None,index=serie.index,dtype=object), []
    grupos = serie.map(lambda v: None if pd.isna(v) else f'Q{np.searchsorted(cortes,v,side="left")+1}')
    return grupos, [float(v) for v in cortes]


def tamanho_delta(delta):
    d=abs(delta)
    return 'desprezível' if d<.147 else 'pequeno' if d<.33 else 'médio' if d<.474 else 'grande'


def comparar(grupos):
    """KW para >2 grupos; MW bilateral assintótico com correção de empates para 2."""
    arrays=[np.asarray(v,dtype=float) for v in grupos]
    if len(arrays)<2 or any(len(a)<MINIMO for a in arrays):
        raise ValueError('São necessários ao menos dois grupos com cinco valores válidos.')
    if any(not np.isfinite(a).all() for a in arrays):
        raise ValueError('Valores não finitos no teste.')
    n=sum(map(len,arrays))
    if len(arrays)==2:
        if np.unique(np.concatenate(arrays)).size==1:
            u,p=len(arrays[0])*len(arrays[1])/2,1.
        else:
            u,p=stats.mannwhitneyu(*arrays,alternative='two-sided',method='asymptotic',use_continuity=True)
        delta=2*float(u)/(len(arrays[0])*len(arrays[1]))-1
        return dict(teste='Mann–Whitney',estatistica=float(u),p=float(p),
                    efeito=delta,tipo_efeito='Cliff delta',magnitude=tamanho_delta(delta))
    # scipy.kruskal rejeita entradas globalmente constantes; não há diferença de ranks.
    if np.unique(np.concatenate(arrays)).size==1:
        h,p=0.,1.
    else:
        h,p=stats.kruskal(*arrays)
    return dict(teste='Kruskal–Wallis',estatistica=float(h),p=float(p),
                efeito=float(h)/(n-1),tipo_efeito='epsilon²',magnitude='ver valor numérico')


def holm(tabela):
    tabela=tabela.copy()
    mascara=tabela.p.notna()
    tabela['p_holm']=np.nan
    tabela['rejeita_005']=False
    if mascara.any():
        rejeita,ajustados,_,_=multipletests(tabela.loc[mascara,'p'],alpha=.05,method='holm')
        tabela.loc[mascara,'p_holm']=ajustados
        tabela.loc[mascara,'rejeita_005']=rejeita
    tabela['familia_n_testes']=int(mascara.sum())
    return tabela


def analisar(entrada):
    df=entrada.copy()
    obrigatorias=set(FATORES+list(METRICAS)+['nome_completo'])
    if not obrigatorias.issubset(df):
        raise ValueError(f'Colunas ausentes: {sorted(obrigatorias-set(df))}')
    if df.empty or df.nome_completo.isna().any() or df.nome_completo.duplicated().any():
        raise ValueError('Amostra vazia ou nomes ausentes/duplicados.')
    for col in NUMERICOS+list(METRICAS):
        df[col]=pd.to_numeric(df[col],errors='raise')
        v=df[col].dropna()
        if not np.isfinite(v).all() or (v<0).any():
            raise ValueError(f'Valores inválidos em {col}')
    if (df.cfr_ci.dropna()>1).any():
        raise ValueError('CFR deve ser fração entre zero e um.')
    df=df.sort_values('nome_completo').reset_index(drop=True)
    cortes={}
    for fator in NUMERICOS:
        df['grupo_'+fator],cortes[fator]=quartis(df[fator])
    df['grupo_linguagem']=df.linguagem.astype('string').str.strip().replace('',pd.NA)
    descricoes,testes,pares=[],[],[]
    for fator in FATORES:
        for metrica in METRICAS:
            grupos={}
            for nome,g in df.dropna(subset=['grupo_'+fator]).groupby('grupo_'+fator,sort=True):
                s=g[metrica].dropna()
                q=s.quantile([.25,.5,.75]) if len(s) else [np.nan]*3
                q1,med,q3=list(q)
                elegivel=len(s)>=MINIMO
                descricoes.append(dict(fator=fator,metrica=metrica,grupo=nome,
                    n_grupo=len(g),n_valido=len(s),ausentes=len(g)-len(s),
                    mediana=med,q1=q1,q3=q3,iqr=q3-q1,elegivel_teste=elegivel))
                if elegivel:grupos[str(nome)]=s.to_numpy()
            n=sum(map(len,grupos.values()))
            base=dict(fator=fator,metrica=metrica,n=n,k=len(grupos),
                      excluidos=len(df)-n,grupos='; '.join(grupos))
            if len(grupos)<2:
                testes.append(dict(**base,status='grupos insuficientes',teste=None,estatistica=None,
                                   p=None,efeito=None,tipo_efeito=None,magnitude=None))
                continue
            testes.append(dict(**base,status='calculado',**comparar(list(grupos.values()))))
            # Família secundária definida antes de observar a significância dos testes globais.
            for a,b in itertools.combinations(grupos,2):
                resultado=comparar([grupos[a],grupos[b]])
                pares.append(dict(fator=fator,metrica=metrica,grupo_a=a,grupo_b=b,
                    n_a=len(grupos[a]),n_b=len(grupos[b]),
                    mediana_a=float(np.median(grupos[a])),mediana_b=float(np.median(grupos[b])),
                    **resultado))
    testes=holm(pd.DataFrame(testes))
    pares=holm(pd.DataFrame(pares,columns=['fator','metrica','grupo_a','grupo_b','n_a','n_b',
        'mediana_a','mediana_b','teste','estatistica','p','efeito','tipo_efeito','magnitude']))
    significativos={(r.fator,r.metrica) for r in testes.itertuples() if r.rejeita_005}
    pares['omnibus_significativo']=[(r.fator,r.metrica) in significativos for r in pares.itertuples()]
    pares['diferenca_sustentada']=pares.rejeita_005 & pares.omnibus_significativo
    return df,pd.DataFrame(descricoes),testes,pares,cortes


def figura(testes,saida):
    cache=RAIZ/'dados/.cache/matplotlib';cache.mkdir(parents=True,exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR',str(cache))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    matplotlib.rcParams['svg.hashsalt']='rq93'
    fig,ax=plt.subplots(figsize=(9,4.8),constrained_layout=True)
    matriz=np.full((len(FATORES),len(METRICAS)),np.nan)
    for i,f in enumerate(FATORES):
        for j,m in enumerate(METRICAS):
            r=testes[(testes.fator==f)&(testes.metrica==m)].iloc[0]
            if r.tipo_efeito=='epsilon²':matriz[i,j]=r.efeito
    im=ax.imshow(np.ma.masked_invalid(matriz),vmin=0,vmax=max(.1,float(np.nanmax(matriz))) if np.isfinite(matriz).any() else .1,cmap='Blues')
    for i,f in enumerate(FATORES):
        for j,m in enumerate(METRICAS):
            r=testes[(testes.fator==f)&(testes.metrica==m)].iloc[0]
            texto=f'{r.efeito:.3f}'+(' *' if r.rejeita_005 else '') if r.tipo_efeito=='epsilon²' else 'MW: ver CSV' if r.teste=='Mann–Whitney' else 'n insuficiente'
            cor='white' if np.isfinite(matriz[i,j]) and im.norm(matriz[i,j])>.6 else 'black'
            ax.text(j,i,texto,ha='center',va='center',color=cor)
    ax.set_xticks(range(len(METRICAS)),[v[0] for v in METRICAS.values()])
    ax.set_yticks(range(len(FATORES)),['Contribuidores','Estrelas','Idade','Linguagem'])
    ax.set_title('RQ93 · Associação entre características e métricas DORA\nε² de Kruskal–Wallis; * p ajustado por Holm < 0,05')
    fig.colorbar(im,ax=ax,label='ε² = H / (n − 1)')
    for ext in ['png','svg']:
        fig.savefig(saida/f'efeitos_dora.{ext}',dpi=180,metadata={'Date':None} if ext=='svg' else None)
        if ext=='svg':
            svg=saida/'efeitos_dora.svg'
            svg.write_text('\n'.join(linha.rstrip() for linha in svg.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
    plt.close(fig)


def fmt(v):
    return '—' if v is None or pd.isna(v) else f'{v:.4g}'


def executar(entrada,saida,recuperacao):
    fonte=entrada/'metricas_repositorios.csv'
    config_path=entrada/'resumo_execucao.json'
    config=json.loads(config_path.read_text(encoding='utf-8'))['config']
    df=pd.read_csv(fonte)
    hashes={str(fonte.relative_to(RAIZ)) if fonte.is_relative_to(RAIZ) else str(fonte):hashlib.sha256(fonte.read_bytes()).hexdigest(),
            str(config_path):hashlib.sha256(config_path.read_bytes()).hexdigest()}
    fonte_recuperacao='CSV original da coleta (referência C1)'
    if recuperacao is not None:
        meta_path=recuperacao.parent/'resumo.json'
        meta=json.loads(meta_path.read_text(encoding='utf-8'))
        if meta['fontes_sha256']['metricas_repositorios.csv']!=hashlib.sha256(fonte.read_bytes()).hexdigest() or meta['janela']!=config['janela']:
            raise ValueError('RQ92 não corresponde à coleta/janela atual; reexecute a RQ92.')
        r=pd.read_csv(recuperacao)
        if r.nome_completo.duplicated().any() or set(r.nome_completo)!=set(df.nome_completo):
            raise ValueError('RQ92 tem repositórios divergentes/duplicados.')
        df['recuperacao_original_horas']=df.recuperacao_mediana_horas
        df['recuperacao_mediana_horas']=df.nome_completo.map(r.set_index('nome_completo').recuperacao_mediana_horas)
        hashes[str(recuperacao)]=hashlib.sha256(recuperacao.read_bytes()).hexdigest()
        hashes[str(meta_path)]=hashlib.sha256(meta_path.read_bytes()).hexdigest()
        fonte_recuperacao='RQ92, com ajuste do fim da janela e censura; hash da coleta reconciliado'
    dados,desc,testes,pares,cortes=analisar(df)
    saida.mkdir(parents=True,exist_ok=True)
    cols=['nome_completo']+FATORES+['grupo_'+f for f in FATORES]+list(METRICAS)
    for nome,tabela in [('repositorios_grupos',dados[cols]),('descritivas_grupos',desc),
                       ('testes_holm',testes),('comparacoes_pares',pares)]:
        tabela.to_csv(saida/f'{nome}.csv',index=False,float_format='%.12g')
    resumo=dict(repositorios=len(dados),janela=config['janela'],janela_confirmada=config.get('janela_confirmada',False),
        fatores=FATORES,metricas=METRICAS,cortes_quartis=cortes,minimo_por_grupo=MINIMO,
        testes_principais=int(testes.p.notna().sum()),significativos_holm=int(testes.rejeita_005.sum()),
        pares_testados=len(pares),pares_sustentados=int(pares.diferenca_sustentada.sum()),
        fonte_recuperacao=fonte_recuperacao,fontes_sha256=hashes,
        tipo_projeto='não analisado: consenso humano indisponível; rótulos de IA não utilizados')
    (saida/'resumo.json').write_text(json.dumps(resumo,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    figura(testes,saida)
    tabela='\n'.join(f'| {r.fator} | {METRICAS[r.metrica][0]} | {r.n} | {r.k} | {r.teste or r.status} | {fmt(r.p)} | {fmt(r.p_holm)} | {r.tipo_efeito}: {fmt(r.efeito)} | {"sim" if r.rejeita_005 else "não"} |' for r in testes.itertuples())
    comparacoes=pares.loc[pares.diferenca_sustentada].sort_values(['p_holm','fator','metrica','grupo_a','grupo_b'])
    destaques='\n'.join(f'| {r.fator} | {METRICAS[r.metrica][0]} | {r.grupo_a} × {r.grupo_b} | {fmt(r.mediana_a)} × {fmt(r.mediana_b)} | {fmt(r.efeito)} ({r.magnitude}) | {fmt(r.p_holm)} |' for r in comparacoes.head(20).itertuples()) or '| — | — | Nenhum par sustentado | — | — | — |'
    h6=[]
    achados=[]
    for r in testes.loc[testes.rejeita_005].itertuples():
        achados.append(f'- **{r.fator} × {METRICAS[r.metrica][0]}**: {r.tipo_efeito}={fmt(r.efeito)}, p Holm={fmt(r.p_holm)}. Há evidência de diferenças entre as distribuições dos grupos; os pares abaixo delimitam quais contrastes têm suporte.')
    efeitos_kw=testes.loc[testes.tipo_efeito=='epsilon²','efeito'].dropna()
    h6.append(f'- Efeitos: {int((efeitos_kw<.06).sum())} de {len(efeitos_kw)} testes KW apresentam ε² < 0,06, conforme o limiar previsto na H6.')
    for f,m in [('linguagem','frequencia_deploy_semana')]+[('estrelas',m) for m in METRICAS]:
        r=testes[(testes.fator==f)&(testes.metrica==m)].iloc[0]
        h6.append(f'- {f}, {METRICAS[m][0]}: efeito {fmt(r.efeito)}; p Holm {fmt(r.p_holm)}; '+('associação sustentada após ajuste.' if r.rejeita_005 else 'sem evidência de associação após ajuste.'))
    for m in ['frequencia_deploy_semana','recuperacao_mediana_horas','cfr_ci']:
        d=desc[(desc.fator=='contribuidores_total') & (desc.metrica==m)].set_index('grupo')
        if 'Q1' in d.index and 'Q4' in d.index:
            p=pares[(pares.fator=='contribuidores_total')&(pares.metrica==m)&(pares.grupo_a=='Q1')&(pares.grupo_b=='Q4')]
            suporte='par sem evidência ajustada' if p.empty or not p.iloc[0].diferenca_sustentada else 'par com diferença sustentada após Holm'
            h6.append(f'- Contribuidores, {METRICAS[m][0]}: Q1 mediana {fmt(d.loc["Q1","mediana"])}; Q4 {fmt(d.loc["Q4","mediana"])} {METRICAS[m][1]}; {suporte}.')
    aviso='confirmada na configuração' if resumo['janela_confirmada'] else '**ainda não confirmada pelo professor na configuração**'
    texto=f'''# RQ93 — RQ06: Características dos repositórios e desempenho DORA

## Pergunta e estratégia

Quais características estão associadas ao desempenho DORA? Foram analisados **{len(dados)} repositórios** na janela {config['janela']['inicio']} a {config['janela']['fim']}, {aviso}. Há quatro fatores, superando o mínimo de três: contribuidores, estrelas, idade e linguagem. O tipo de projeto não foi inferido por IA: o consenso humano necessário não está disponível. Essa parte da H6 permanece pendente.

Métricas: frequência (releases/semana), lead time (a) por release (dias), CFR (a) de CI (fração) e recuperação (horas). Recuperação: {fonte_recuperacao}. Valores ausentes não são zero. A frequência maior e as demais métricas menores representam desempenho mais favorável sob esses proxies. Não foi criado um índice global que misture unidades. Variantes de lead time/CFR e sensibilidade de definições são tratadas pelas demais RQs.

## Método reproduzível

Quartis são calculados uma única vez na amostra disponível de cada fator, antes de remover valores ausentes das métricas. Q1 ≤ P25; Q2 > P25 e ≤ P50; Q3 > P50 e ≤ P75; Q4 > P75. Empates nunca são separados artificialmente: grupos podem ficar desbalanceados ou vazios. Cortes: `{json.dumps(cortes,ensure_ascii=False)}`. Idade e demais metadados refletem a coleta; não garantem precedência temporal às métricas.

Todas as linguagens e grupos aparecem nas descritivas. Para teste, exigem-se pelo menos **5 valores válidos por grupo e métrica**. Grupos menores ficam registrados e excluídos daquele teste, sem juntar linguagens heterogêneas em “Outras”. Exclusões constam nos CSVs. Os testes com ≥3 grupos usam Kruskal–Wallis (correção de empates) e ε² = H/(n−1), conforme o enunciado. Com dois grupos, Mann–Whitney bilateral assintótico, correções de empates e continuidade, e δ = 2U₁/(n₁n₂)−1. Entradas globalmente constantes no KW recebem H=0 e p=1.

Família principal: **{resumo['testes_principais']} testes fator × métrica**, corrigidos juntos por Holm, α=0,05. Não se corrige separadamente cada fator. Testes não estimáveis ficam sem p. Família secundária: **{len(pares)} pares elegíveis**, definidos sem selecionar pelos resultados, corrigidos juntos por Holm. Um par só é destacado se tanto o teste global quanto o par passam suas correções. Essas são duas famílias distintas; não se afirma controle conjunto entre ambas.

Cliff δ positivo significa valores maiores em A que em B; isso é favorável para frequência e desfavorável para tempos/CFR. Magnitude de |δ|: <0,147 desprezível; <0,33 pequeno; <0,474 médio; demais grande. Não aplicamos esses cortes a ε². KW detecta diferenças de distribuições/ranks e não identifica sozinho os pares nem prova diferença de medianas quando as formas diferem.

## Resultados

**{resumo['significativos_holm']} de {resumo['testes_principais']} testes principais** permanecem significativos após Holm. Significância não significa causalidade nem efeito relevante; os tamanhos de efeito devem ser lidos junto dos p-valores.

{chr(10).join(achados) or 'Nenhuma associação sustentada após o ajuste.'}

| Fator | Métrica | n | Grupos | Teste | p bruto | p Holm | Efeito | Significativo |
|---|---|---:|---:|---|---:|---:|---|---|
{tabela}

![Tamanho dos efeitos e significância ajustada](efeitos_dora.png)

## Quais grupos diferem?

Há **{len(comparacoes)} pares sustentados** por ambos os critérios. Abaixo, até 20 pares ordenados por p ajustado; todos os pares, inclusive não significativos, constam em comparacoes_pares.csv. Medianas têm a unidade da métrica, CFR em fração.

| Fator | Métrica | A × B | Mediana A × B | δ e magnitude | p Holm |
|---|---|---|---|---|---:|
{destaques}

## Confronto com H6

A H6 original em artigo/introducao.tex prevê, para mais contribuidores, maior frequência, menor recuperação e maior CFR (a). O confronto Q1–Q4 é:

{chr(10).join(h6)}

A comparação acima distingue direção descritiva de evidência ajustada: uma ordenação das medianas sem par significativo não confirma a previsão. A tabela principal também permite confrontar associação entre linguagem e frequência e o efeito esperado das estrelas. Ausência de significância não demonstra equivalência ou efeito zero. O critério ε² < 0,06 previsto na H6 deve ser confrontado numericamente, não trocado por um novo corte após os resultados. A previsão sobre bibliotecas versus aplicações/CLI não foi testada sem rótulos humanos.

## Limitações e interpretação

As associações são observacionais, univariadas e não ajustadas por confundidores. Linguagem, idade, popularidade e contribuidores podem estar associados entre si. A amostra não probabilística de projetos populares e os filtros da coleta restringem generalização; projetos relacionados podem violar independência. Dados ausentes e exclusões de grupos pequenos mudam o conjunto em cada teste. A recuperação considera somente episódios completos, com a censura documentada na RQ92; lead time e CFR também são proxies, não medidas diretas de produção. A significância assintótica pode ser frágil em grupos pequenos mesmo com o piso de cinco observações. A divisão em quartis perde informação; não representa um ponto de corte causal.

## Reprodução e dicionário

Na raiz: `python codigo-fonte/analise/rq93_caracteristicas_dora.py`.
Opções: --entrada, --saida e --recuperacao (CSV da RQ92 acompanhado de resumo.json). Para usar explicitamente a referência original: --usar-recuperacao-original. A execução padrão exige a RQ92 atualizada e valida a janela e o hash do CSV original antes de integrar seu ajuste.

- repositorios_grupos.csv: nomes, fatores brutos, grupos e quatro métricas nas unidades acima.
- descritivas_grupos.csv: fator/métrica/grupo, n_grupo, n_valido, ausentes, mediana/Q1/Q3/IQR e elegivel_teste; inclui grupos pequenos.
- testes_holm.csv: n, k, excluidos, grupos, status, teste, estatistica H/U, p, p_holm, efeito e tipo, rejeita_005 e tamanho da família.
- comparacoes_pares.csv: grupos A/B, n e medianas, U, p, δ e magnitude, p_holm e sinalizadores de significância global/por par/conjunta dos critérios.
- resumo.json: configuração, cortes, contagens e hashes de todas as fontes usadas.
- efeitos_dora.png/.svg: ε² dos testes KW; MW não é misturado na mesma escala.

## Referências de implementação

- Enunciado LAB03, seção 5, RQ06: quartis, ε², Cliff δ e correção de Holm.
- [SciPy: Kruskal–Wallis](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.kruskal.html): teste, empates e tamanhos de grupo.
- [Statsmodels: multipletests](https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html): ajuste Holm.
'''
    (saida/'RELATORIO.md').write_text(texto,encoding='utf-8')
    print(json.dumps({k:resumo[k] for k in ['repositorios','testes_principais','significativos_holm','pares_testados','pares_sustentados']},indent=2))
    return resumo


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--entrada',type=Path,default=RAIZ/'dados/lab03_final')
    p.add_argument('--saida',type=Path,default=RAIZ/'entregas/laboratorio-03/sprint-03/RQ93')
    p.add_argument('--recuperacao',type=Path,default=RAIZ/'entregas/laboratorio-03/sprint-03/RQ92/repositorios.csv')
    p.add_argument('--usar-recuperacao-original',action='store_true')
    args=p.parse_args()
    executar(args.entrada,args.saida,None if args.usar_recuperacao_original else args.recuperacao)
