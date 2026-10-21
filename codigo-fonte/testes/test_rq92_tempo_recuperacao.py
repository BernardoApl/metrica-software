import pandas as pd
import pytest

from analise.rq92_tempo_recuperacao import analisar, respeitar_corte, resumir_episodios, analisar_horizontes
from metricas import ci

FIM=ci.data_utc('2026-01-31T23:59:59Z')


def episodio(inicio, fim, esquerda=False, direita=False):
    return dict(inicio=ci.data_utc(inicio),fim=ci.data_utc(fim),workflow_id=1,
                falhas=1,censura_esquerda=esquerda,censurado=direita)


def test_corte_nao_transforma_sucesso_tardio_em_recuperacao():
    ep=[episodio('2026-01-31T22:00:00Z','2026-02-01T01:00:00Z')]
    corrigidos,tardios,fora=respeitar_corte(ep,FIM)
    assert (tardios,fora)==(1,0)
    assert corrigidos[0]['horas']==pytest.approx(7199/3600)
    assert corrigidos[0]['situacao']=='direita'
    r=resumir_episodios(corrigidos)
    assert r['recuperacao_mediana_horas'] is None
    assert r['classe_recuperacao']=='Não estimável'
    assert ep[0]['fim']>FIM  # a entrada não foi alterada


def test_censuras_sobrepostas_e_mediana_somente_completos():
    ep=[episodio('2026-01-01T00:00:00Z','2026-01-01T02:00:00Z'),
        episodio('2026-01-01T00:00:00Z','2026-01-01T08:00:00Z',esquerda=True),
        episodio('2026-01-30T00:00:00Z','2026-01-31T23:59:59Z',esquerda=True,direita=True)]
    r=resumir_episodios(respeitar_corte(ep,FIM)[0])
    assert r['recuperacao_mediana_horas']==2
    assert r['censura_qualquer']==2 and r['censura_ambas']==1
    assert r['completos']+r['censura_qualquer']==r['episodios']
    assert r['proporcao_censura_direita']==pytest.approx(1/3)


def test_sem_episodio_nao_significa_zero():
    r=resumir_episodios([])
    assert r['situacao_repositorio']=='sem episódio'
    assert r['proporcao_censura_direita'] is None
    assert r['recuperacao_mediana_horas'] is None


def test_inicios_apos_janela_e_duracoes_negativas():
    ep=[episodio('2026-02-01T00:00:00Z','2026-02-01T01:00:00Z')]
    assert respeitar_corte(ep,FIM)==([],0,1)
    with pytest.raises(ValueError,match='duração inválida'):
        respeitar_corte([episodio('2026-01-02T00:00:00Z','2026-01-01T00:00:00Z')],FIM)


def test_workflows_separados_e_reconciliacao_exportacao():
    def run(i,h,c,w=1,event='push'):
        t=f'2026-01-01T{h}:00:00Z'
        return dict(nome_completo='org/a',id=i,workflow_id=w,event=event,head_branch='main',
                    conclusion=c,created_at=t,run_started_at=t,updated_at=t)
    runs=pd.DataFrame([run(1,'09','success'),run(2,'10','failure'),run(3,'11','success',2),
                       run(4,'12','cancelled'),run(5,'14','success'),run(6,'15','failure',event='schedule')])
    m=pd.DataFrame([dict(nome_completo='org/a',branch_padrao='main',recuperacao_mediana_horas=4.,
        episodios_falha=1,episodios_completos=1,episodios_censurados=0,episodios_censura_esquerda=0)])
    df,ep,audit,classes,resumo=analisar(m,runs,'2026-01-01','2026-01-31')
    assert len(ep)==1 and ep.horas.iloc[0]==4
    assert resumo['runs_validos']==4
    assert df.classe_recuperacao.iloc[0]=='High'
    assert classes.repositorios.sum()==1
    m.loc[0,'episodios_falha']=2
    with pytest.raises(ValueError,match='não reconciliada'):
        analisar(m,runs,'2026-01-01','2026-01-31')


def test_limites_por_prazo_censura_e_pesos_distintos():
    ep=pd.DataFrame([
        ['a',1,False,False],  # recuperado exatamente em 1h
        ['a',2,False,False],  # não recuperado em 1h
        ['a',.5,True,False],  # censura antes: indeterminado
        ['a',1,True,False],  # censura no prazo: não recuperado
        ['b',.2,False,False],
        ['b',.1,False,True],  # início desconhecido: excluído
    ],columns=['nome_completo','horas','censurado','censura_esquerda'])
    df=pd.DataFrame({'completos':[2,1,0], 'recuperacao_mediana_horas':[1.5,.2,None]})
    por_repo,h,r=analisar_horizontes(ep,df)
    uma=h.iloc[0]
    assert uma.episodios==5 and uma.recuperados==2 and uma.indeterminados==1
    assert uma.nao_recuperados==2
    assert uma.limite_inferior==pytest.approx(.4)
    assert uma.limite_superior==pytest.approx(.6)
    assert uma.limite_inferior_peso_igual==pytest.approx((.25+1)/2)
    assert uma.episodios_excluidos_inicio_desconhecido==1
    assert r.n.tolist()==[2,0,0]
    assert pd.isna(r.mediana.iloc[1])
    assert (por_repo.recuperados+por_repo.indeterminados+por_repo.nao_recuperados==por_repo.episodios).all()


def test_limites_sem_inicio_conhecido_nao_inventam_estimativa():
    ep=pd.DataFrame([['a',2,True,True]],columns=['nome_completo','horas','censurado','censura_esquerda'])
    df=pd.DataFrame({'completos':[0], 'recuperacao_mediana_horas':[None]})
    por_repo,h,r=analisar_horizontes(ep,df)
    assert por_repo.empty
    assert h.limite_inferior.isna().all() and h.limite_superior.isna().all()
    assert h.episodios.eq(0).all()
