import csv
import hashlib
import json

import pytest

from coleta import rq102_tempos_cache as coleta


@pytest.fixture
def entrada(tmp_path):
    p = tmp_path / 'origem.csv'
    p.write_text('nome_completo,linguagem,estrelas\na/a,Python,10\nb/b,Python,20\nc/c,,5\n', encoding='utf-8')
    return p


def test_agregacao_e_cache_reutilizam_resultado_igual(entrada):
    chamadas = []
    def operacao():
        chamadas.append(1)
        return coleta.agregar_csv(entrada)
    cache = coleta.CacheResultado(operacao)
    esperado = (('Python', 2, 30), ('Sem linguagem', 1, 5))
    assert cache.executar() == cache.executar() == esperado
    assert len(chamadas) == 1
    assert (cache.hits, cache.misses) == (1, 1)
    cache.limpar()
    assert cache.executar() == esperado
    assert len(chamadas) == 2


@pytest.mark.parametrize('pares', [2, 3, 30, 31])
def test_ordens_balanceadas_reproduziveis(pares):
    plano = coleta.plano_ordens(pares, 102)
    assert plano == coleta.plano_ordens(pares, 102)
    assert abs(sum(o[0] == 'com_cache' for o in plano) - sum(o[0] == 'sem_cache' for o in plano)) <= 1
    assert all(set(o) == {'com_cache', 'sem_cache'} for o in plano)


def test_relogio_conversao_e_validacao_de_todas_as_respostas():
    ticks = iter([100, 6_000_100])
    r = coleta.medir(lambda: (1,), 3, (1,), lambda: next(ticks))
    assert r['tempo_ms'] == 2
    assert r['duracao_total_ns'] == 6_000_000
    respostas = iter([(0,), (1,)])
    r = coleta.medir(lambda: next(respostas), 2, (1,))
    assert r['status'] == 'resultado_divergente'
    assert r['tempo_ms'] is None


def test_falha_preservada_sem_tempo_valido():
    def falhar():
        raise RuntimeError('falha controlada')
    r = coleta.medir(falhar, 4, ())
    assert r['status'] == 'erro'
    assert r['concluidas'] == 0
    assert r['tempo_ms'] is None
    assert 'falha controlada' in r['erro']


@pytest.mark.parametrize('ordem', [coleta.TRATAMENTOS, coleta.TRATAMENTOS[::-1]])
def test_priming_fora_dos_hits_e_recarga_por_par(ordem):
    chamadas = []
    def operacao():
        chamadas.append(1)
        return (42,)
    for _ in range(2):
        linhas = coleta.coletar_par(operacao, (42,), ordem, 5)
        com = next(r for r in linhas if r['tratamento'] == 'com_cache')
        sem = next(r for r in linhas if r['tratamento'] == 'sem_cache')
        assert (com['cache_hits'], com['cache_misses']) == (5, 0)
        assert (sem['cache_hits'], sem['cache_misses']) == (0, 0)
        assert all(r['status'] == 'ok' for r in linhas)
    assert len(chamadas) == 12  # dois primings + dez recálculos


def test_exports_pareados_hashes_aquecimento_e_nao_sobrescrita(entrada, tmp_path):
    pasta, meta = coleta.executar(entrada, tmp_path/'saida', pares=4, repeticoes=2, aquecimentos=1)
    assert meta['status'] == 'concluida'
    assert meta['pares_validos'] == 4
    assert meta['repositorios'] == 3
    assert (pasta/'entrada.csv').read_bytes() == entrada.read_bytes()
    with (pasta/'tempos.csv').open(encoding='utf-8', newline='') as f:
        linhas = list(csv.DictReader(f))
    assert len(linhas) == 8
    with (pasta/'pares.csv').open(encoding='utf-8', newline='') as f:
        pares = list(csv.DictReader(f))
    for par in pares:
        bruto = {r['tratamento']: float(r['tempo_ms']) for r in linhas if r['par_id'] == par['par_id']}
        assert float(par['diferenca_ms']) == pytest.approx(bruto['sem_cache'] - bruto['com_cache'])
        assert par['valido'] == 'True'
    with (pasta/'aquecimentos.csv').open(encoding='utf-8', newline='') as f:
        assert len(list(csv.DictReader(f))) == 2
    for nome, sha in meta['artefatos_sha256'].items():
        assert hashlib.sha256((pasta/nome).read_bytes()).hexdigest() == sha
    outra, _ = coleta.executar(entrada, tmp_path/'saida', pares=2, repeticoes=1, aquecimentos=0)
    assert outra != pasta
    assert len(list((tmp_path/'saida').iterdir())) == 2


@pytest.mark.parametrize('conteudo', [
    'nome_completo,linguagem,estrelas\n',
    'nome_completo,linguagem,estrelas\na/a,X,3\na/a,X,4\n',
    'nome_completo,linguagem,estrelas\na/a,X,-1\n',
    'nome_completo,linguagem,estrelas\na/a,X,NaN\n',
    'nome_completo,linguagem\na/a,X\n',
])
def test_csv_invalido_registra_falha(conteudo, entrada, tmp_path):
    entrada.write_text(conteudo, encoding='utf-8')
    with pytest.raises(ValueError):
        coleta.executar(entrada, tmp_path/'saida', pares=2, repeticoes=1)
    meta = json.loads(next((tmp_path/'saida').glob('*/execucao.json')).read_text(encoding='utf-8'))
    assert meta['status'] == 'erro'
    assert meta['pares_validos'] == 0


@pytest.mark.parametrize('parametros', [{'pares': 0}, {'pares': True}, {'repeticoes': 0}, {'aquecimentos': -1}])
def test_parametros_invalidos_nao_criam_saida(entrada, tmp_path, parametros):
    with pytest.raises(ValueError):
        coleta.executar(entrada, tmp_path/'saida', **parametros)
    assert not (tmp_path/'saida').exists()


def test_erro_de_uma_condicao_mantem_par_invalido(entrada, tmp_path, monkeypatch):
    original = coleta.coletar_par
    def com_falha(*args):
        linhas = original(*args)
        linhas[0].update(status='erro', erro='falha controlada', tempo_ms=None, tempo_por_operacao_ns=None)
        return linhas
    monkeypatch.setattr(coleta, 'coletar_par', com_falha)
    pasta, meta = coleta.executar(entrada, tmp_path/'saida', pares=2, repeticoes=1, aquecimentos=0)
    assert meta['status'] == 'concluida_com_erros'
    assert meta['pares_validos'] == 0
    with (pasta/'pares.csv').open(encoding='utf-8', newline='') as f:
        assert all(r['valido'] == 'False' and r['diferenca_ms'] == '' for r in csv.DictReader(f))


def test_interrupcao_marca_metadata(entrada, tmp_path, monkeypatch):
    def interromper(*args):
        raise KeyboardInterrupt
    monkeypatch.setattr(coleta, 'coletar_par', interromper)
    with pytest.raises(KeyboardInterrupt):
        coleta.executar(entrada, tmp_path/'saida', pares=2, aquecimentos=0)
    meta = json.loads(next((tmp_path/'saida').glob('*/execucao.json')).read_text(encoding='utf-8'))
    assert meta['status'] == 'interrompida'
    assert meta['pares_concluidos'] == 0
