import numpy as np
import pandas as pd
import pytest

from analise.rq93_caracteristicas_dora import analisar, comparar, holm, quartis


def test_quartis_preservam_empates_e_ausentes():
    grupos,cortes=quartis(pd.Series([1,1,1,1,1,2,3,4,np.nan]))
    assert grupos.iloc[:5].eq('Q1').all()
    assert pd.isna(grupos.iloc[-1])
    assert len(cortes)==3
    assert grupos.iloc[-2]=='Q4'


def test_kw_separacao_completa_e_constante():
    r=comparar([[1]*5,[2]*5,[3]*5])
    assert r['estatistica']==pytest.approx(14)
    assert r['efeito']==pytest.approx(1)
    assert r['p']<.001
    r=comparar([[1]*5]*3)
    assert r['efeito']==0 and r['p']==1


def test_cliff_delta_empates_e_direcao():
    x,y=[1,1,2,2,2],[2,2,3,3,3]
    r=comparar([x,y])
    assert r['efeito']==pytest.approx(-19/25)
    assert comparar([y,x])['efeito']==pytest.approx(19/25)
    assert r['magnitude']=='grande'
    assert comparar([[1]*5,[1]*5])['p']==1


def test_holm_familia_completa_e_p_ausente():
    r=holm(pd.DataFrame({'p':[.01,.03,.04,np.nan]}))
    assert r.p_holm.iloc[:3].tolist()==pytest.approx([.03,.06,.06])
    assert r.rejeita_005.tolist()==[True,False,False,False]
    assert r.familia_n_testes.eq(3).all()


def dados():
    n=40
    return pd.DataFrame({'nome_completo':[f'org/r{i:02}' for i in range(n)],
        'contribuidores_total':range(n),'estrelas':range(100,100+n),
        'idade_anos':np.arange(n)/10,'linguagem':['Python']*20+['Go']*20,
        'frequencia_deploy_semana':np.arange(n)/10,
        'lead_time_release_mediana_dias':[2.]*n,'cfr_ci':[.1]*n,
        'recuperacao_mediana_horas':[1.]*n})


def test_integracao_exclusoes_familias_e_ordem():
    d=dados()
    d.loc[:5,'recuperacao_mediana_horas']=np.nan
    grupos,desc,testes,pares,cortes=analisar(d)
    assert len(testes)==16
    assert testes.familia_n_testes.eq(16).all()
    linha=testes.query("fator=='contribuidores_total' and metrica=='recuperacao_mediana_horas'").iloc[0]
    assert linha.n==30 and linha.excluidos==10 and linha.k==3
    pequena=desc.query("fator=='contribuidores_total' and metrica=='recuperacao_mediana_horas' and grupo=='Q1'").iloc[0]
    assert pequena.n_valido==4 and not pequena.elegivel_teste
    assert pares.familia_n_testes.eq(len(pares)).all()
    assert (pares.loc[pares.diferenca_sustentada,'p_holm']<.05).all()
    embaralhado=analisar(d.sample(frac=1,random_state=42))
    pd.testing.assert_frame_equal(testes,embaralhado[2])
    pd.testing.assert_frame_equal(grupos,embaralhado[0])


def test_fatores_constantes_nao_geram_p_falso():
    d=dados()
    d['contribuidores_total']=1
    _,_,t,_,_=analisar(d)
    assert t.loc[t.fator=='contribuidores_total','p'].isna().all()
    assert t.familia_n_testes.eq(12).all()


@pytest.mark.parametrize('erro',['duplicado','infinito','cfr','negativo'])
def test_entradas_invalidas(erro):
    d=dados()
    if erro=='duplicado':d.loc[1,'nome_completo']=d.loc[0,'nome_completo']
    elif erro=='infinito':d.loc[0,'idade_anos']=np.inf
    elif erro=='cfr':d.loc[0,'cfr_ci']=1.5
    else:d.loc[0,'frequencia_deploy_semana']=-1
    with pytest.raises(ValueError):analisar(d)
