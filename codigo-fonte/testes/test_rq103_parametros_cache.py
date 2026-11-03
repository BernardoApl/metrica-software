import csv
import json
import shutil

import pytest

from analise import rq103_parametros_cache as rq


@pytest.fixture
def origem(tmp_path):
    destino = tmp_path / 'coleta'
    shutil.copytree(rq.COLETA, destino)
    return destino


def modificar_meta(pasta, **campos):
    p = pasta / 'execucao.json'
    m = json.loads(p.read_text(encoding='utf-8'))
    m.update(campos)
    p.write_text(json.dumps(m), encoding='utf-8')


def alterar_csv(pasta, arquivo, coluna, valor):
    p = pasta / arquivo
    linhas = rq.ler_csv(p)
    linhas[0][coluna] = valor
    with p.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=linhas[0].keys())
        w.writeheader()
        w.writerows(linhas)
    m = json.loads((pasta / 'execucao.json').read_text(encoding='utf-8'))
    m['artefatos_sha256'][arquivo] = rq.sha(p)
    modificar_meta(pasta, **m)


def test_descritivas_conhecidas():
    d = rq.descrever([1, 2, 3, 4, 100])
    assert d['media'] == 22
    assert (d['q1'], d['mediana'], d['q3'], d['mad']) == (2, 3, 4, 1)
    assert d['pares_fora_cercas_iqr'] == [5]
    assert rq.correlacao([1, 1], [2, 3]) is None
    assert rq.quantil([1, 3], .25) == 1.5


def test_dados_reais_e_contrato_pareado():
    resumo, parametros = rq.analisar(rq.COLETA)
    assert resumo['pares_validos'] == 30
    assert resumo['pares_excluidos'] == 0
    assert [e['quantidade'] for e in parametros['estratos']] == [15, 15]
    originais = {int(p['par_id']): p for p in rq.ler_csv(rq.COLETA / 'pares.csv')}
    ids = []
    for e in parametros['estratos']:
        for p in e['pares']:
            ids.append(p['par_id_origem'])
            real = originais[p['par_id_origem']]
            assert real['ordem_primeiro'] == e['ordem_primeiro']
            assert p['tempo_sem_cache_ms'] == float(real['tempo_sem_cache_ms'])
            assert p['tempo_com_cache_ms'] == float(real['tempo_com_cache_ms'])
    assert sorted(ids) == list(range(1, 31))
    assert parametros == rq.analisar(rq.COLETA)[1]


def test_exportacao_sem_sobrescrever(tmp_path):
    saida = tmp_path / 'analise'
    rq.executar(rq.COLETA, saida)
    assert {p.name for p in saida.iterdir()} == {'resumo.json', 'parametros_simulacao.json', 'RELATORIO.md'}
    assert 'não gera dados simulados' in (saida / 'RELATORIO.md').read_text(encoding='utf-8')
    antes = (saida / 'resumo.json').read_bytes()
    with pytest.raises(ValueError, match='já contém'):
        rq.executar(rq.COLETA, saida)
    assert (saida / 'resumo.json').read_bytes() == antes


def test_hash_modificado_bloqueia_publicacao(origem, tmp_path):
    with (origem / 'pares.csv').open('a') as f:
        f.write('\n')
    with pytest.raises(ValueError, match='Hash divergente'):
        rq.executar(origem, tmp_path / 'nao_criar')
    assert not (tmp_path / 'nao_criar').exists()


@pytest.mark.parametrize('status', ['em_andamento', 'interrompida', 'concluida_com_erros', 'erro'])
def test_status_incompleto(origem, status):
    modificar_meta(origem, status=status)
    with pytest.raises(ValueError, match='concluída'):
        rq.analisar(origem)


@pytest.mark.parametrize('arquivo,coluna,valor', [
    ('pares.csv', 'tempo_sem_cache_ms', 'NaN'),
    ('pares.csv', 'tempo_com_cache_ms', '0'),
    ('pares.csv', 'tempo_sem_cache_ms', '-2'),
    ('pares.csv', 'diferenca_ms', '0'),
    ('pares.csv', 'valido', 'False'),
    ('pares.csv', 'par_id', '2'),
    ('pares.csv', 'ordem_primeiro', 'sem_cache'),
    ('tempos.csv', 'tempo_ms', '500'),
    ('tempos.csv', 'cache_hits', '0'),
    ('tempos.csv', 'resultado_sha256', 'diferente'),
    ('tempos.csv', 'concluidas', '19'),
])
def test_incoerencia_mesmo_com_hash_atualizado(origem, arquivo, coluna, valor):
    alterar_csv(origem, arquivo, coluna, valor)
    with pytest.raises(ValueError):
        rq.analisar(origem)
