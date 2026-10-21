import gzip
import json
import random
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from analise import rq97_cfr as rq97
from coleta.coleta_dora import limites_da_janela
from metricas import corretiva, variantes

INICIO, FIM = limites_da_janela('2026-01-01', '2026-12-31')


def rel(nome, tag, publicada, i, draft=False, prerelease=False):
    return dict(nome_completo=nome, id=str(i), tag_name=tag, draft=str(draft), prerelease=str(prerelease),
                published_at=publicada)


def entregas_de(linhas, fim=FIM):
    return rq97.preparar_entregas(pd.DataFrame(linhas), fim)


# ------------------------------------------------------------- exemplo do enunciado
def exemplo():
    return [rel('org/a', 'v2.2.0', '2026-04-20T10:00:00Z', 1),
            rel('org/a', 'v2.3.0', '2026-05-10T10:00:00Z', 2),
            rel('org/a', 'v2.3.1', '2026-05-12T10:00:00Z', 3),
            rel('org/a', 'v2.4.0', '2026-06-01T10:00:00Z', 4),
            rel('org/a', 'v2.5.0', '2026-06-20T10:00:00Z', 5)]


def test_exemplo_do_enunciado_v230_falha_e_v240_nao():
    e = entregas_de(exemplo())['org/a']
    flags = rq97.sinalizar_corretivas(e)
    assert flags.tolist() == [False, False, True, False, False]  # só v2.3.1 muda apenas o patch
    falha = rq97.falhas_por_release(e.t, flags)
    assert falha.tolist() == [False, True, False, False, False]  # v2.3.0 falhou; v2.4.0 não
    r = rq97.cfr_entrega_de(e.t, flags, INICIO, FIM)
    assert (r['releases_avaliadas_cfr'], r['releases_falha_cfr'], r['releases_censuradas_cfr']) == (5, 1, 0)
    assert r['cfr_entrega'] == pytest.approx(.2)


def test_corretiva_exatamente_em_sete_dias_conta_e_no_instante_da_release_nao():
    linhas = [rel('org/a', 'v1.0.0', '2026-03-01T00:00:00Z', 1), rel('org/a', 'v1.0.1', '2026-03-08T00:00:00Z', 2)]
    e = entregas_de(linhas)['org/a']
    assert rq97.falhas_por_release(e.t, rq97.sinalizar_corretivas(e)).tolist() == [True, False]
    linhas[1]['published_at'] = '2026-03-08T00:00:01Z'
    e = entregas_de(linhas)['org/a']
    assert rq97.falhas_por_release(e.t, rq97.sinalizar_corretivas(e)).tolist() == [False, False]
    # Empate de published_at: a corretiva não é posterior à release, então não a faz falhar.
    linhas[1]['published_at'] = linhas[0]['published_at']
    e = entregas_de(linhas)['org/a']
    assert not rq97.falhas_por_release(e.t, rq97.sinalizar_corretivas(e)).any()


def test_ultimos_sete_dias_da_janela_sao_censurados_e_releases_antes_da_janela_nao_contam():
    linhas = [rel('org/a', 'v0.9.0', '2025-12-30T10:00:00Z', 1),   # antes da janela: só dá contexto
              rel('org/a', 'v1.0.0', '2026-01-02T10:00:00Z', 2),
              rel('org/a', 'v1.0.1', '2026-12-24T23:59:59Z', 3),  # t + 7d = 31/12 23:59:59 = fim: avaliável
              rel('org/a', 'v1.0.2', '2026-12-25T00:00:00Z', 4)]  # censurada
    e = entregas_de(linhas)['org/a']
    r = rq97.cfr_entrega_de(e.t, rq97.sinalizar_corretivas(e), INICIO, FIM)
    # v0.9.0 só dá contexto; v1.0.0 e v1.0.1 são avaliadas; v1.0.2 (nos últimos 7 dias) é censurada.
    assert (r['releases_avaliadas_cfr'], r['releases_censuradas_cfr']) == (2, 1)
    # v1.0.2 é patch de v1.0.1 em até 7 dias, então só v1.0.1 falha.
    assert r['releases_falha_cfr'] == 1 and r['cfr_entrega'] == pytest.approx(.5)


def test_draft_prerelease_e_sem_data_ficam_de_fora():
    linhas = exemplo() + [rel('org/a', 'v2.5.1', '2026-06-21T10:00:00Z', 6, prerelease=True),
                          rel('org/a', 'v2.5.2', '2026-06-21T11:00:00Z', 7, draft=True),
                          rel('org/a', 'v2.5.3', '', 8)]
    e = entregas_de(linhas)['org/a']
    assert e.tags == ['v2.2.0', 'v2.3.0', 'v2.3.1', 'v2.4.0', 'v2.5.0']
    with pytest.raises(ValueError, match='duplicadas'):
        entregas_de(linhas + [linhas[0]])
    with pytest.raises(ValueError, match='ausentes'):
        rq97.preparar_entregas(pd.DataFrame(linhas).drop(columns='draft'), FIM)


def test_repositorio_com_uma_release_ou_sem_release_avaliavel_fica_indefinido():
    e = entregas_de([rel('org/a', 'v1.0.0', '2026-03-01T00:00:00Z', 1)])['org/a']
    r = rq97.cfr_entrega_de(e.t, rq97.sinalizar_corretivas(e), INICIO, FIM)
    assert (r['releases_avaliadas_cfr'], r['releases_falha_cfr'], r['cfr_entrega']) == (1, 0, 0.0)
    tarde = entregas_de([rel('org/a', 'v1.0.0', '2026-12-30T00:00:00Z', 1)])['org/a']
    r = rq97.cfr_entrega_de(tarde.t, rq97.sinalizar_corretivas(tarde), INICIO, FIM)
    assert r['cfr_entrega'] is None and r['releases_avaliadas_cfr'] == 0 and r['releases_censuradas_cfr'] == 1


def test_heuristica_desconhecida_e_rejeitada():
    e = entregas_de(exemplo())['org/a']
    with pytest.raises(ValueError, match='Heurística'):
        rq97.sinalizar_corretivas(e, 'v99')


# ------------------------------------------- equivalência com a função oficial do projeto
MENSAGENS = ['fix: crash ao abrir arquivo', 'feat: nova tela', 'revert "feat: nova tela"', 'docs: fix typo',
             'Merge branch main', 'chore: bump deps', 'hotfix na autenticação', 'add support for x',
             'fix(ci): flaky test', 'refactor parser']


def sintetico(semente):
    rng = random.Random(semente)
    t = datetime(2025, 12, 10, tzinfo=timezone.utc)
    major, minor, patch = 1, 0, 0
    linhas, mensagens = [], {}
    for i in range(rng.randint(1, 45)):
        t += timedelta(hours=rng.choice([1, 12, 40, 100, 200, 400]))
        sorteio = rng.random()
        if sorteio < .45:
            patch += 1
        elif sorteio < .8:
            minor, patch = minor + 1, 0
        elif sorteio < .9:
            major, minor, patch = major + 1, 0, 0
        tag = f'v{major}.{minor}.{patch}' if rng.random() > .15 else f'build-{i}'
        linhas.append(rel('org/s', tag, t.strftime('%Y-%m-%dT%H:%M:%SZ'), i + 1))
        if rng.random() > .2:  # compare completo
            mensagens[tag] = [rng.choice(MENSAGENS) for _ in range(rng.randint(0, 6))]
    return linhas, mensagens


@pytest.mark.parametrize('semente', range(40))
@pytest.mark.parametrize('heuristica', sorted(corretiva.HEURISTICAS))
def test_versao_vetorizada_igual_a_variantes_cfr_entrega(semente, heuristica):
    linhas, mensagens = sintetico(semente)
    inicio, fim = limites_da_janela('2026-01-01', '2026-03-15')
    e = entregas_de(linhas, fim)['org/s']
    contagens = {('org/s', t): np.sum([rq97._evidencias_mensagem(m) for m in ms] or [[0] * 5], axis=0)
                 for t, ms in mensagens.items()}
    disponiveis = set(contagens)
    flags = rq97.sinalizar_corretivas(e, heuristica, contagens, disponiveis)
    meu = rq97.cfr_entrega_de(e.t, flags, inicio, fim)
    registros = [dict(tag_name=l['tag_name'], published_at=l['published_at'], draft=False, prerelease=False,
                      id=int(l['id'])) for l in linhas]
    oficial = variantes.cfr_entrega(registros, inicio, fim, heuristica, mensagens)
    assert meu['releases_avaliadas_cfr'] == oficial['releases_avaliadas_cfr']
    assert meu['releases_falha_cfr'] == oficial['releases_falha_cfr']
    assert meu['releases_censuradas_cfr'] == oficial['releases_censuradas_cfr']
    assert meu['cfr_entrega'] == oficial['cfr_entrega']


# ------------------------------------------------------------ mensagens dos commits
def escrever_commits(caminho, linhas):
    with gzip.open(caminho, 'wt', encoding='utf-8', newline='') as f:
        f.write('nome_completo,tag_name,anterior,sha,data_autor,mensagem\n')
        for nome, tag, anterior, sha, mensagem in linhas:
            texto = '"' + mensagem.replace('"', '""') + '"'
            f.write(f'{nome},{tag},{anterior},{sha},2026-01-01T00:00:00Z,{texto}\n')


def test_agregar_commits_em_blocos_soma_as_evidencias(tmp_path):
    caminho = tmp_path / 'commits.csv.gz'
    escrever_commits(caminho, [('org/a', 'v1.0.1', 'v1.0.0', 's1', 'fix: crash'),
                               ('org/a', 'v1.0.1', 'v1.0.0', 's2', 'feat: add tela'),
                               ('org/a', 'v1.0.1', 'v1.0.0', 's3', 'Merge branch x'),
                               ('org/a', 'v1.1.0', 'v1.0.1', 's4', 'revert "feat"'),
                               ('org/a', 'v1.1.0', 'v1.0.1', 's5', 'docs: fix typo')])
    contagens, linhas = rq97.agregar_commits(caminho, tamanho_bloco=2)  # força o corte no meio de uma release
    esperado = corretiva.evidencias(None, None, ['fix: crash', 'feat: add tela', 'Merge branch x'])
    assert dict(zip(rq97.CAMPOS_EVIDENCIA, contagens[('org/a', 'v1.0.1')])) == \
        {c: esperado[c] for c in rq97.CAMPOS_EVIDENCIA}
    assert linhas == {('org/a', 'v1.0.1'): 3, ('org/a', 'v1.1.0'): 2}
    assert contagens[('org/a', 'v1.1.0')].tolist() == [2, 1, 2, 0, 0]  # úteis, revert, fix, fix de defeito, feat


def test_releases_com_mensagens_aplica_as_mesmas_regras_do_rq83():
    entregas = entregas_de([rel('org/a', 'v1.0.0', '2026-01-02T00:00:00Z', 1),
                            rel('org/a', 'v1.0.1', '2026-01-03T00:00:00Z', 2),
                            rel('org/a', 'v1.0.2', '2026-01-04T00:00:00Z', 3),
                            rel('org/a', 'v1.0.3', '2026-01-05T00:00:00Z', 4),
                            rel('org/a', 'v1.0.4', '2026-01-06T00:00:00Z', 5),
                            rel('org/a', 'v1.0.5', '2026-01-07T00:00:00Z', 6)])

    def lead(tag, anterior, motivo='', commits=1, truncado=False):
        return dict(nome_completo='org/a', tag_name=tag, anterior=anterior, motivo=motivo, commits=str(commits),
                    truncado=str(truncado))
    tabela = pd.DataFrame([lead('v1.0.0', '', 'sem_release_anterior', 0),
                           lead('v1.0.1', 'v1.0.0', ''),                              # ok
                           lead('v1.0.2', 'v1.0.1', 'compare_indisponivel', 0),       # sem compare
                           lead('v1.0.3', 'v1.0.2', '', 1, True),                     # truncado
                           lead('v1.0.4', 'v1.0.0', ''),                              # anterior diferente
                           lead('v1.0.5', 'v1.0.4', 'sem_commits_novos', 0)])         # zero commits: disponível
    linhas = {('org/a', 'v1.0.1'): 1, ('org/a', 'v1.0.3'): 1, ('org/a', 'v1.0.4'): 1}
    assert rq97.releases_com_mensagens(tabela, linhas, entregas) == {('org/a', 'v1.0.1'), ('org/a', 'v1.0.5')}
    linhas[('org/a', 'v1.0.1')] = 2  # commits lidos não batem com o compare
    assert rq97.releases_com_mensagens(tabela, linhas, entregas) == {('org/a', 'v1.0.5')}


def test_v3_sem_mensagens_usa_so_a_tag_e_com_zero_commits_nao_e_corretiva():
    e = entregas_de([rel('org/a', 'v1.0.0', '2026-01-02T00:00:00Z', 1),
                     rel('org/a', 'v1.0.1', '2026-01-03T00:00:00Z', 2)])['org/a']
    assert rq97.sinalizar_corretivas(e, 'correcao_de_defeito_v3').tolist() == [False, True]
    chave = ('org/a', 'v1.0.1')
    sem_fix = rq97.sinalizar_corretivas(e, 'correcao_de_defeito_v3', {chave: np.zeros(5, dtype=int)}, {chave})
    assert sem_fix.tolist() == [False, False]  # compare completo, sem commit de correção de defeito


# ------------------------------------------------------------------- CFR (a)
def runs_de(linhas):
    return pd.DataFrame(linhas, columns=['nome_completo', 'workflow_id', 'event', 'head_branch', 'conclusion',
                                         'created_at'])


METRICAS_A = pd.DataFrame([dict(nome_completo='org/a', branch_padrao='main', runs_falha=2, runs_sucesso=3,
                                cfr_ci=.4)])


def runs_a():
    return runs_de([
        ('org/a', '1', 'push', 'main', 'success', '2026-02-01T10:00:00Z'),
        ('org/a', '1', 'push', 'main', 'success', '2026-02-02T10:00:00Z'),
        ('org/a', '1', 'push', 'main', 'failure', '2026-02-03T10:00:00Z'),
        ('org/a', '2', 'push', 'main', 'success', '2026-02-04T10:00:00Z'),
        ('org/a', '2', 'push', 'main', 'startup_failure', '2026-02-05T10:00:00Z'),
        ('org/a', '2', 'push', 'main', 'cancelled', '2026-02-06T10:00:00Z'),          # ignorado
        ('org/a', '2', 'push', 'main', '', '2026-02-06T11:00:00Z'),                   # em andamento: ignorado
        ('org/a', '1', 'schedule', 'main', 'failure', '2026-02-07T10:00:00Z'),        # evento fora
        ('org/a', '1', 'push', 'dev', 'failure', '2026-02-08T10:00:00Z'),             # branch fora
        ('org/a', '1', 'push', 'main', 'failure', '2025-12-31T23:59:59Z'),            # antes da janela
        ('org/a', '1', 'push', 'main', 'failure', '2027-01-01T00:00:00Z')])           # depois da janela


def test_cfr_ci_recontagem_e_composicao_das_falhas():
    r = rq97.cfr_ci_por_repositorio(runs_a(), METRICAS_A, INICIO, FIM).iloc[0]
    assert (r.runs_push_branch, r.runs_sucesso_recontado, r.runs_falha_recontado, r.runs_ignorados) == (7, 3, 2, 2)
    assert (r.falhas_failure, r.falhas_startup_failure, r.falhas_timed_out) == (1, 1, 0)
    assert r.cfr_ci_recontado == pytest.approx(.4)
    assert r.workflows_com_falha == 2 and r.workflows_com_runs == 2
    assert r.participacao_workflow_mais_falho == pytest.approx(.5)


def test_cfr_ci_sem_runs_validos_fica_indefinido_e_divergencia_e_rejeitada():
    vazio = runs_de([('org/a', '1', 'push', 'main', 'cancelled', '2026-02-01T10:00:00Z')])
    metricas = METRICAS_A.assign(runs_falha=0, runs_sucesso=0, cfr_ci=np.nan)
    r = rq97.cfr_ci_por_repositorio(vazio, metricas, INICIO, FIM)
    assert pd.isna(r.cfr_ci_recontado.iloc[0]) and r.runs_ignorados.iloc[0] == 1
    rq97.conferir_cfr_ci(r, metricas)  # nada a reclamar
    certo = rq97.cfr_ci_por_repositorio(runs_a(), METRICAS_A, INICIO, FIM)
    with pytest.raises(ValueError, match='org/a'):
        rq97.conferir_cfr_ci(certo, METRICAS_A.assign(runs_falha=3))
    with pytest.raises(ValueError, match='org/a'):
        rq97.conferir_cfr_ci(certo, METRICAS_A.assign(cfr_ci=.5))
    with pytest.raises(ValueError, match='ausentes'):
        rq97.cfr_ci_por_repositorio(runs_a().drop(columns='event'), METRICAS_A, INICIO, FIM)


# ------------------------------------------------------------------- estatísticas
def test_bootstrap_da_mediana_e_deterministico_e_cobre_a_mediana():
    valores = [0.0, .02, .05, .08, .1, .3]
    inf, sup = rq97.ic_bootstrap_mediana(valores)
    assert (inf, sup) == rq97.ic_bootstrap_mediana(valores)
    assert inf <= np.median(valores) <= sup
    assert rq97.ic_bootstrap_mediana([.1]) == (None, None)
    assert rq97.ic_bootstrap_mediana([None, float('nan')]) == (None, None)


def test_wilcoxon_pareado_e_rank_bisserial():
    b = pd.Series([.5, .6, .7, .8, .9])
    a = pd.Series([.1, .2, .3, .4, .5])
    w = rq97.wilcoxon_pareado(b, a)
    assert w['n'] == 5 and w['rank_bisserial'] == pytest.approx(1.0)
    assert rq97.wilcoxon_pareado(a, a) is None


# -------------------------------------------------------------------- integração
def monta_entrada(tmp_path, com_commits=False):
    entrada = tmp_path / 'entrada'
    entrada.mkdir()
    repos = {
        'org/a': ('main', [('v1.0.0', '2026-01-05'), ('v1.0.1', '2026-01-06'), ('v1.1.0', '2026-03-01'),
                           ('v1.1.1', '2026-03-03'), ('v1.2.0', '2026-06-01'), ('v1.3.0', '2026-12-29')], 2, 8),
        'org/b': ('master', [(f'nightly-{i}', f'2026-02-0{i}') for i in range(1, 6)], 1, 9),
        'org/c': ('main', [('v2.0.0', '2026-01-10'), ('v2.0.1', '2026-01-12'), ('v2.0.2', '2026-01-13'),
                           ('v2.1.0', '2026-05-01'), ('v2.1.1', '2026-05-03')], 5, 5),
        'org/d': ('main', [('v3.0.0', '2026-02-01'), ('v3.1.0', '2026-04-01'), ('v3.2.0', '2026-08-01')], 0, 10),
    }
    metricas, releases, runs, lead, commits = [], [], [], [], []
    for k, (nome, (branch, tags, falhas, sucessos)) in enumerate(repos.items()):
        metricas.append(dict(nome_completo=nome, linguagem='Python', estrelas=1000 - k, idade_anos=2.0 + k,
                             contribuidores_total=10 * (k + 1), branch_padrao=branch,
                             frequencia_deploy_semana=len(tags) / (365 / 7), releases_janela=len(tags),
                             cfr_ci=falhas / (falhas + sucessos), runs_validos=falhas + sucessos,
                             runs_falha=falhas, runs_sucesso=sucessos))
        for i, (tag, dia) in enumerate(tags):
            releases.append(rel(nome, tag, f'{dia}T12:00:00Z', 100 * k + i + 1))
            anterior = tags[i - 1][0] if i else ''
            lead.append(dict(nome_completo=nome, tag_name=tag, anterior=anterior, published_at=f'{dia}T12:00:00Z',
                             commits='1' if i else '0', commits_negativos='0', truncado='False',
                             lead_time_dias='1' if i else '', motivo='' if i else 'sem_release_anterior'))
            if i:
                commits.append((nome, tag, anterior, f's{k}{i}', 'fix: erro de login' if i % 2 else 'feat: nova tela'))
        for j in range(falhas + sucessos):
            runs.append((nome, '7', 'push', branch, 'failure' if j < falhas else 'success',
                         f'2026-03-{j + 1:02d}T10:00:00Z'))
    pd.DataFrame(metricas).to_csv(entrada / 'metricas_repositorios.csv', index=False)
    pd.DataFrame(releases).to_csv(entrada / 'releases.csv', index=False)
    pd.DataFrame(lead).to_csv(entrada / 'lead_time_releases.csv', index=False)
    with gzip.open(entrada / 'workflow_runs.csv.gz', 'wt', encoding='utf-8', newline='') as f:
        runs_de(runs).to_csv(f, index=False)
    (entrada / 'resumo_execucao.json').write_text(json.dumps(
        {'config': {'janela': {'inicio': '2026-01-01', 'fim': '2026-12-31'}, 'janela_confirmada': False}}))
    if com_commits:
        escrever_commits(entrada / 'commits_releases.csv.gz', commits)
    return entrada


def test_executar_sem_commits_gera_saidas_e_numeros_calculados_a_mao(tmp_path):
    entrada = monta_entrada(tmp_path)
    saida = tmp_path / 'saida'
    resumo = rq97.executar(entrada, saida, usar_commits=False)
    for nome in ['repositorios.csv', 'estatisticas.csv', 'classes_dora.csv', 'transicoes_classes.csv',
                 'resumo.json', 'RELATORIO.md', 'cfr_variantes.png', 'cfr_variantes.svg', 'cfr_classes.png']:
        assert (saida / nome).is_file(), nome
    assert not (saida / 'sensibilidade_heuristica.csv').exists() and not resumo['heuristicas_com_mensagens']
    t = pd.read_csv(saida / 'repositorios.csv').set_index('nome_completo')
    # org/a: v1.0.0 (falha: v1.0.1), v1.0.1, v1.1.0 (falha: v1.1.1), v1.1.1, v1.2.0 avaliadas; v1.3.0 censurada
    assert (t.loc['org/a', 'releases_avaliadas_cfr'], t.loc['org/a', 'releases_falha_cfr'],
            t.loc['org/a', 'releases_censuradas_cfr']) == (5, 2, 1)
    assert t.loc['org/a', 'cfr_entrega'] == pytest.approx(.4) and t.loc['org/a', 'cfr_ci'] == pytest.approx(.2)
    # org/b: nenhuma tag SemVer -> CFR (b) = 0 por construção
    assert t.loc['org/b', 'cfr_entrega'] == 0 and t.loc['org/b', 'proporcao_semver'] == 0
    # org/c: v2.0.0 e v2.0.1 falham (v2.0.1/v2.0.2 são patch), v2.0.2 não, v2.1.0 falha (v2.1.1), v2.1.1 não
    assert t.loc['org/c', 'releases_falha_cfr'] == 3 and t.loc['org/c', 'cfr_entrega'] == pytest.approx(.6)
    assert t.loc['org/d', 'cfr_entrega'] == 0 and t.loc['org/d', 'cfr_ci'] == 0
    assert t.loc['org/c', 'classe_cfr_a'] == 'Low' and t.loc['org/d', 'classe_cfr_a'] == 'Elite'
    assert resumo['entrega']['repositorios_sem_nenhum_semver'] == 1
    assert resumo['entrega']['repositorios_cfr_zero'] == 2
    assert resumo['ci']['runs_falha'] == 8 and resumo['ci']['repositorios_sem_falha'] == 1
    assert resumo['comparacao_a_b']['n'] == 4
    assert set(resumo['fontes_sha256']) == {'entrada/metricas_repositorios.csv', 'entrada/releases.csv',
                                            'entrada/workflow_runs.csv.gz', 'entrada/lead_time_releases.csv',
                                            'entrada/resumo_execucao.json'}
    assert 'H3 ' in (saida / 'RELATORIO.md').read_text(encoding='utf-8')
    json.loads((saida / 'resumo.json').read_text(encoding='utf-8'))


def test_executar_com_commits_calcula_v2_e_v3(tmp_path):
    entrada = monta_entrada(tmp_path, com_commits=True)
    saida = tmp_path / 'saida'
    resumo = rq97.executar(entrada, saida)
    assert resumo['heuristicas_com_mensagens'] and (saida / 'sensibilidade_heuristica.csv').is_file()
    t = pd.read_csv(saida / 'repositorios.csv').set_index('nome_completo')
    # v2: qualquer fix conta. Em org/b só há mensagens alternadas: v1.. nightly-2 (fix), nightly-4 (fix).
    assert t.loc['org/b', 'cfr_entrega_patch_ou_mensagem_v2'] > t.loc['org/b', 'cfr_entrega']
    assert 'cfr_entrega_correcao_de_defeito_v3' in t.columns
    assert resumo['entrega']['disponiveis_para_mensagens'] > 0
    texto = (saida / 'RELATORIO.md').read_text(encoding='utf-8')
    assert 'Sensibilidade à heurística' in texto and 'patch_ou_mensagem_v2' in texto


def test_analisar_rejeita_entradas_inconsistentes(tmp_path):
    entrada = monta_entrada(tmp_path)
    metricas, releases, runs, lead = rq97.ler_entrada(entrada)
    recontado = rq97.cfr_ci_por_repositorio(runs, metricas, INICIO, FIM)
    entregas = rq97.preparar_entregas(releases, FIM)
    rq97.analisar(metricas, recontado, entregas, INICIO, FIM)
    with pytest.raises(ValueError, match='ausentes'):
        rq97.analisar(metricas.drop(columns='cfr_ci'), recontado, entregas, INICIO, FIM)
    with pytest.raises(ValueError, match='duplicados'):
        rq97.analisar(pd.concat([metricas, metricas.iloc[[0]]]), recontado, entregas, INICIO, FIM)
    with pytest.raises(ValueError, match='fora da amostra'):
        rq97.analisar(metricas.iloc[1:], recontado, entregas, INICIO, FIM)
    with pytest.raises(ValueError, match='fora do intervalo'):
        rq97.analisar(metricas.assign(cfr_ci=1.5, runs_falha=3, runs_sucesso=-2), recontado.assign(
            runs_falha_recontado=3, runs_sucesso_recontado=-2, cfr_ci_recontado=1.5), entregas, INICIO, FIM)
