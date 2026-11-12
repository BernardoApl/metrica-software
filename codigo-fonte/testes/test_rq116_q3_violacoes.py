import json

import pytest

from analise import rq104_gerador_simulacao as rq104
from analise import rq116_q3_violacoes as rq

ENTREGA = rq.SAIDA / 'resultados.json'


@pytest.fixture(scope='module')
def parametros():
    return rq104.carregar_parametros()


@pytest.mark.parametrize('situacao', list(rq.SITUACOES))
@pytest.mark.parametrize('n', [10, 50])
def test_amostras_tem_o_tamanho_pedido_e_media_perto_de_zero(parametros, situacao, n):
    r = rq.simular(situacao, n, parametros, repeticoes=400)
    assert r['n_pares'] == n and r['repeticoes'] == 400
    assert abs(r['media_d_h0']) < 0.1  # efeito zero em ms (σ_d ≈ 1,3 ms na base)


def test_simulacao_e_reprodutivel_e_depende_da_semente(parametros):
    a = rq.simular('outliers', 20, parametros, repeticoes=300)
    assert a == rq.simular('outliers', 20, parametros, repeticoes=300)
    assert a != rq.simular('outliers', 20, parametros, repeticoes=300, semente=1)


def test_alfa_menor_nunca_rejeita_mais(parametros):
    r = rq.simular('assimetria', 30, parametros, repeticoes=500)
    for teste in rq.TESTES:
        assert r['testes'][teste]['0.01']['rejeicoes'] <= r['testes'][teste]['0.05']['rejeicoes']


def test_so_a_assimetria_quebra_a_simetria(parametros):
    simetricas = [rq.simular(s, 30, parametros, repeticoes=500)['assimetria_d_h0'] for s in ('base', 'outliers')]
    assert all(abs(x) < 0.3 for x in simetricas)
    assert rq.simular('assimetria', 30, parametros, repeticoes=500)['assimetria_d_h0'] > 1.5


@pytest.mark.parametrize('situacao,n', [('desconhecida', 30), ('base', 31)])
def test_argumentos_invalidos(parametros, situacao, n):
    with pytest.raises(ValueError):
        rq.simular(situacao, n, parametros, repeticoes=10)


def test_entrega_tem_todas_as_situacoes_e_tamanhos():
    m = json.loads(ENTREGA.read_text(encoding='utf-8'))
    assert m['repeticoes'] == 10_000 and m['semente'] == 116
    for situacao in rq.SITUACOES:
        assert [p['n_pares'] for p in m['situacoes'][situacao]] == list(rq.N_PARES)
        for p in m['situacoes'][situacao]:
            for teste in rq.TESTES:
                r = p['testes'][teste]['0.05']
                assert r['proporcao'] == r['rejeicoes'] / 10_000
                assert r['ic95'][0] <= r['proporcao'] <= r['ic95'][1]


def test_entrega_mostra_os_achados_da_q3():
    """Os números que o dashboard cita: o t se aproxima de 5% e o Wilcoxon se afasta na assimetria."""
    m = json.loads(ENTREGA.read_text(encoding='utf-8'))
    taxa = lambda s, n, t: next(p for p in m['situacoes'][s] if p['n_pares'] == n)['testes'][t]['0.05']['proporcao']
    assert taxa('assimetria', 50, 't_pareado') < taxa('assimetria', 10, 't_pareado')
    assert taxa('assimetria', 50, 'wilcoxon_pareado') > taxa('assimetria', 10, 'wilcoxon_pareado') > 0.05
    assert taxa('outliers', 30, 't_pareado') < 0.05


def test_executar_grava_os_tres_arquivos(tmp_path, monkeypatch):
    monkeypatch.setattr(rq, 'N_PARES', (10, 30))
    m = rq.executar(tmp_path, repeticoes=200)
    assert {p.name for p in tmp_path.iterdir()} == {'resultados.json', 'erro_tipo_i.csv', 'RELATORIO.md'}
    linhas = (tmp_path / 'erro_tipo_i.csv').read_text(encoding='utf-8').strip().splitlines()
    assert len(linhas) == 1 + 3 * 2 * 2 * 2  # cabeçalho + situações × tamanhos × testes × alfas
    assert 'Assimetria real' in (tmp_path / 'RELATORIO.md').read_text(encoding='utf-8')
    assert set(m['leituras']) == set(rq.SITUACOES)
