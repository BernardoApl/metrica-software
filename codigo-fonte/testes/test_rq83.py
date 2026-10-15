"""RQ83: exemplos calculados a mao e integracao offline dos CSVs."""
import csv
import json

import pytest

from metricas import variantes
import rq83_metricas_variantes as rq83
from pipeline_dora import salvar_csv
from test_metricas_ci import run

JANELA = {'inicio': '2026-03-01', 'fim': '2026-03-31'}


def release(tag, dia, **extra):
    return dict(id=int(dia), tag_name=tag, published_at=f'2026-03-{dia:02d}T00:00:00Z',
                draft=False, prerelease=False, **extra)


@pytest.mark.parametrize('a,b,esperado', [
    ('v2.3.0', 'v2.3.1', True), ('2.3.0', '2.3.8+build.1', True),
    ('v2.3.0', 'v2.4.0', False), ('v2.3.2', 'v2.3.1', False),
    ('v2.3.0', 'v2.3.1-rc.1', False), ('release-x', 'release-y', False),
    ('2.03.0', '2.03.1', False), ('v1.0.0', 'v1.0.0', False),
])
def test_heuristica_patch(a, b, esperado):
    assert variantes.corretiva_patch(a, b) == esperado


def test_cfr_sete_dias_censura_e_uma_falha_por_release():
    releases = [release('v1.0.0', 1), release('v1.0.1', 8), release('v1.0.2', 9),
                release('v1.1.0', 24), release('v1.1.1', 25)]
    r = variantes.cfr_entrega(releases, '2026-03-01T00:00:00Z', '2026-03-31T00:00:00Z')
    assert r['releases_avaliadas_cfr'] == 4  # dia 24 tem exatamente sete dias
    assert r['releases_censuradas_cfr'] == 1
    assert r['releases_falha_cfr'] == 3
    assert r['cfr_entrega'] == .75
    assert r['detalhes'][-1]['falha'] is None


def test_cfr_nao_inclui_draft_prerelease_fora_janela_ou_correcao_tardia():
    releases = [release('v1.0.0', 1), release('v1.0.1', 9),
                dict(release('v1.0.2', 10), draft=True),
                dict(release('v1.0.3', 11), prerelease=True),
                release('v1.1.0', 12)]
    r = variantes.cfr_entrega(releases, '2026-03-01T00:00:00Z', '2026-03-31T00:00:00Z')
    assert r['releases_avaliadas_cfr'] == 3
    assert r['cfr_entrega'] == 0
    r = variantes.cfr_entrega([release('v1.0.0', 30)], '2026-03-01T00:00:00Z', '2026-03-31T00:00:00Z')
    assert r['cfr_entrega'] is None


def test_resumo_iqr_linear():
    assert variantes.resumo([1, 5, 13]) == dict(n=3, mediana=5, q1=3, q3=9, iqr=6)
    assert variantes.resumo([4])['iqr'] == 0
    assert variantes.resumo([])['mediana'] is None


def dados():
    repos = dict(nome_completo='o/r', branch_padrao='main', releases_janela=3, runs_validos=4)
    releases = [release('v1.0.0', 1), release('v1.1.0', 15), release('v1.1.1', 17)]
    runs = [run('09:00', 'success'), run('10:00', 'failure'), run('10:30', 'failure'), run('11:15', 'success', fim='11:20')]
    registros = [dict(tag_name='v1.1.0', anterior='v1.0.0', motivo='', commits=3, truncado=False),
                 dict(tag_name='v1.1.1', anterior='v1.1.0', motivo='', commits=1, truncado=False)]
    commits = [dict(tag_name='v1.1.0', anterior='v1.0.0', sha=str(dia), data_autor=f'2026-03-{dia:02d}T00:00:00Z') for dia in (2, 10, 14)]
    commits.append(dict(tag_name='v1.1.1', anterior='v1.1.0', sha='16', data_autor='2026-03-16T00:00:00Z'))
    return repos, releases, runs, registros, commits


def test_calcula_variantes_por_release_e_por_todos_commits():
    linha, detalhes, episodios = rq83.calcular_repositorio(*dados(), JANELA)
    assert linha['calculo_completo']
    assert linha['lead_time_release_mediana_dias'] == 7  # mediana de 13 e 1
    assert linha['lead_time_commit_mediana_dias'] == 3  # mediana de 13, 5, 1 e 1
    assert linha['lead_time_commit_iqr_dias'] == 6
    assert linha['cfr_ci'] == .5
    assert linha['cfr_entrega'] == pytest.approx(1/3)
    assert linha['recuperacao_mediana_horas'] == pytest.approx(4/3)
    assert linha['frequencia_deploy_semana'] == pytest.approx(3/(31/7))
    assert linha['releases_sem_anterior'] == 1


def test_compare_truncado_ou_ausente_nao_vira_medicao_completa():
    repo, releases, runs, registros, commits = dados()
    registros[0]['truncado'] = 'True'
    linha, *_ = rq83.calcular_repositorio(repo, releases, runs, registros, commits, JANELA)
    assert not linha['calculo_completo']
    assert 'compare_truncado' in linha['pendencias']
    assert linha['lead_time_commit_mediana_dias'] == 1  # somente compare inteiro
    linha, *_ = rq83.calcular_repositorio(repo, releases, runs, [], [], JANELA, False)
    assert linha['lead_time_commit_mediana_dias'] is None
    assert 'arquivos_lead_time_ausentes' in linha['pendencias']


def test_filtros_ci_censura_e_sucesso_apos_janela():
    repo, releases, runs, registros, commits = dados()
    runs += [run('12:00', 'failure', event='schedule'), run('13:00', 'failure', head_branch='dev'),
             run('14:00', 'cancelled'), run('15:00', 'failure', workflow_id=2),
             run('16:00', 'success', workflow_id=2, updated_at='2026-04-01T00:00:00Z')]
    repo['runs_validos'] = 6
    linha, _, episodios = rq83.calcular_repositorio(repo, releases, runs, registros, commits, JANELA)
    assert linha['cfr_ci'] == .5
    assert linha['episodios_censurados'] == 1
    assert linha['episodios_censura_esquerda'] == 1
    assert linha['recuperacao_mediana_horas'] == pytest.approx(4/3)


def test_duplicate_commit_e_falta_data_sao_pendencias():
    repo, releases, runs, registros, commits = dados()
    commits[0]['data_autor'] = ''
    linha, *_ = rq83.calcular_repositorio(repo, releases, runs, registros, commits, JANELA)
    assert 'commits_incompletos' in linha['pendencias']


def gravar_entrada(pasta):
    pasta.mkdir()
    repo, releases, runs, registros, commits = dados()
    for nome, linhas in zip(rq83.ARQUIVOS[1:], ([repo], releases, runs, registros, commits)):
        linhas = [dict(linha, nome_completo='o/r') for linha in linhas]
        salvar_csv(pasta / nome, linhas, list(linhas[0]), comprimir=nome.endswith('.gz'))
    (pasta / 'resumo_execucao.json').write_text(json.dumps({'config': {'janela': JANELA}}))


def test_cli_exporta_deterministico_e_preserva_entrada(tmp_path):
    entrada, saida = tmp_path / 'entrada', tmp_path / 'saida'
    gravar_entrada(entrada)
    antes = {f.name: f.read_bytes() for f in entrada.iterdir()}
    assert rq83.principal(['--entrada', str(entrada), '--saida', str(saida)]) == 0
    primeira = (saida / 'metricas_variantes.csv').read_bytes()
    assert rq83.principal(['--entrada', str(entrada), '--saida', str(saida)]) == 0
    assert (saida / 'metricas_variantes.csv').read_bytes() == primeira
    assert antes == {f.name: f.read_bytes() for f in entrada.iterdir()}
    auditoria = json.loads((saida / 'resumo_rq83.json').read_text())
    assert not auditoria['janela_confirmada']
    assert not auditoria['heuristica_validada_manualmente']
    assert len(auditoria['entrada_sha256']) == 6


def test_cli_falha_em_entrada_incompleta_e_modo_parcial_explicito(tmp_path):
    entrada, saida = tmp_path / 'entrada', tmp_path / 'saida'
    gravar_entrada(entrada)
    (entrada / 'commits_releases.csv.gz').unlink()
    args = ['--entrada', str(entrada), '--saida', str(saida)]
    assert rq83.principal(args) == 1
    assert not saida.exists()
    assert rq83.principal(args + ['--permitir-parcial']) == 2
    with (saida / 'metricas_variantes.csv').open() as f:
        assert next(csv.DictReader(f))['lead_time_release_mediana_dias'] == ''
    assert rq83.principal(['--entrada', str(entrada), '--saida', str(entrada)]) == 1
