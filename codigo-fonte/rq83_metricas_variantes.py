"""Calcula as variantes obrigatorias DORA usando exclusivamente CSVs locais."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys

from bootstrap import configurar_caminhos, RAIZ_PROJETO
configurar_caminhos()
import coleta_dora
from metricas import ci, dora, lead_time, variantes
from pipeline_dora import salvar_csv

ARQUIVOS = ('resumo_execucao.json', 'metricas_repositorios.csv', 'releases.csv',
            'workflow_runs.csv.gz', 'lead_time_releases.csv', 'commits_releases.csv.gz')


def booleano(valor):
    if valor in (True, 'True', 'true', '1'):
        return True
    if valor in (False, 'False', 'false', '0', '', None):
        return False
    raise ValueError(f'Booleano invalido: {valor!r}')


def ler_csv(caminho, campos):
    abrir = gzip.open if caminho.suffix == '.gz' else open
    with abrir(caminho, 'rt', encoding='utf-8-sig', newline='') as arquivo:
        leitor = csv.DictReader(arquivo)
        faltam = set(campos) - set(leitor.fieldnames or [])
        if faltam:
            raise ValueError(f'{caminho.name}: colunas ausentes: {sorted(faltam)}')
        return list(leitor)


def agrupar(linhas):
    grupos = defaultdict(list)
    for linha in linhas:
        grupos[linha['nome_completo']].append(linha)
    return grupos


def calcular_repositorio(repo, releases, runs, registros_lead, commits, janela, lead_disponivel=True):
    inicio, fim = coleta_dora.limites_da_janela(janela['inicio'], janela['fim'])
    pendencias = []
    releases = [dict(r, draft=booleano(r.get('draft')), prerelease=booleano(r.get('prerelease')),
                     dentro_janela=bool(r.get('published_at') and inicio <= ci.data_utc(r['published_at']) <= fim),
                     id=int(r.get('id') or 0)) for r in releases]
    ids = [r['id'] for r in releases]
    if len(set(ids)) != len(ids):
        raise ValueError(f'{repo["nome_completo"]}: releases duplicadas')
    runs = [dict(r, id=int(r['id'])) for r in runs]
    if len({r['id'] for r in runs}) != len(runs):
        raise ValueError(f'{repo["nome_completo"]}: runs duplicados')
    validas = coleta_dora.releases_validas(releases)
    validos = ci.filtrar_runs_validos(runs, repo['branch_padrao'], inicio, fim)
    cfr = ci.cfr_ci(validos)
    # Um sucesso terminado depois da janela nao encerra um episodio observado.
    observados = [dict(r, conclusion=None) if r['conclusion'] == 'success'
                  and ci.data_utc(r['updated_at']) > fim else r
                  for r in validos if ci.inicio_da_execucao(r) <= fim]
    recuperacao = ci.tempo_de_recuperacao(observados, fim)
    if int(repo.get('intervalos_no_teto') or 0):
        pendencias.append('runs_truncados_na_coleta')
    if not validos:
        pendencias.append('sem_runs_validos')
    if len(validas) != int(repo.get('releases_janela') or 0):
        pendencias.append('contagem_releases_diverge_da_coleta')
    if len(validos) != int(repo.get('runs_validos') or 0):
        pendencias.append('contagem_runs_diverge_da_coleta')

    por_par = {}
    for r in registros_lead:
        chave = (r['anterior'], r['tag_name'])
        if chave in por_par:
            raise ValueError(f'Compare duplicado: {chave}')
        por_par[chave] = r
    commits_por_par = defaultdict(list)
    for c in commits:
        commits_por_par[(c['anterior'], c['tag_name'])].append(c)
    avaliacoes = []
    if not lead_disponivel:
        pendencias.append('arquivos_lead_time_ausentes')
    for anterior, r in lead_time.pares_de_releases(releases):
        compare = None
        if anterior is not None:
            chave = (anterior['tag_name'], r['tag_name'])
            registro = por_par.get(chave)
            itens = commits_por_par[chave]
            if not registro or registro['motivo'] == lead_time.COMPARE_INDISPONIVEL:
                pendencias.append(f'compare_indisponivel:{r["tag_name"]}')
            elif booleano(registro['truncado']):
                pendencias.append(f'compare_truncado:{r["tag_name"]}')
            elif (any(not c.get('data_autor') or not c.get('sha') for c in itens)
                  or len({c['sha'] for c in itens}) != len(itens)
                  or len(itens) != int(registro['commits'] or 0)):
                pendencias.append(f'commits_incompletos:{r["tag_name"]}')
            else:
                compare = dict(status=200, commits=itens, truncado=False)
        avaliacoes.append(lead_time.avaliar_release(r, anterior, compare))
    lt = lead_time.metricas_lead_time(avaliacoes)
    entrega = variantes.cfr_entrega(releases, inicio, fim)
    linha = dict(nome_completo=repo['nome_completo'], releases_janela=len(validas),
                 frequencia_deploy_semana=dora.frequencia_de_deploy(len(validas), coleta_dora.semanas_da_janela(**janela)),
                 **lt, runs_validos=len(validos), runs_falha=cfr['falhas'], runs_sucesso=cfr['sucessos'],
                 cfr_ci=cfr['cfr'], **{k: v for k, v in entrega.items() if k != 'detalhes'},
                 episodios_falha=recuperacao['episodios'], episodios_completos=recuperacao['episodios_completos'],
                 episodios_censurados=recuperacao['episodios_censurados'],
                 episodios_censura_esquerda=recuperacao['episodios_censura_esquerda'],
                 proporcao_episodios_censurados=recuperacao['proporcao_censurados'])
    distribuicoes = {
        'lead_time_release': [a['lead_time_dias'] for a in avaliacoes if a['lead_time_dias'] is not None],
        'lead_time_commit': [v for a in avaliacoes for v in a['lead_times_commits']],
        'recuperacao': [e['horas'] for e in recuperacao['detalhes'] if not e['censurado'] and not e['censura_esquerda']],
    }
    for metrica, valores in distribuicoes.items():
        unidade = 'horas' if metrica == 'recuperacao' else 'dias'
        linha.update({f'{metrica}_{k}_{unidade}': v for k, v in variantes.resumo(valores).items() if k != 'n'})
    linha.update(calculo_completo=not pendencias, pendencias=';'.join(sorted(set(pendencias))))
    return linha, entrega['detalhes'], recuperacao['detalhes']


def executar(entrada, saida, permitir_parcial=False):
    entrada, saida = Path(entrada).resolve(), Path(saida).resolve()
    if saida == entrada or entrada.is_relative_to(saida):
        raise ValueError('Use uma pasta de saida separada dos dados de entrada.')
    obrigatorios = ARQUIVOS[:4] if permitir_parcial else ARQUIVOS
    faltam = [nome for nome in obrigatorios if not (entrada / nome).is_file()]
    if faltam:
        raise ValueError(f'Coleta incompleta em {entrada}: faltam {", ".join(faltam)}. '
                         'Finalize a exportacao da #82; para diagnosticar o piloto, use --permitir-parcial.')
    hashes = {nome: hashlib.sha256((entrada / nome).read_bytes()).hexdigest()
              for nome in ARQUIVOS if (entrada / nome).is_file()}
    fonte = json.loads((entrada / 'resumo_execucao.json').read_text(encoding='utf-8'))
    janela = fonte['config']['janela']
    if coleta_dora.para_data(janela['fim']) < coleta_dora.para_data(janela['inicio']):
        raise ValueError('Janela invertida.')
    repos = ler_csv(entrada / ARQUIVOS[1], ('nome_completo', 'branch_padrao', 'releases_janela', 'runs_validos'))
    if not repos or len({r['nome_completo'].casefold() for r in repos}) != len(repos):
        raise ValueError('Amostra vazia ou com repositorios duplicados.')
    releases = agrupar(ler_csv(entrada / ARQUIVOS[2], ('nome_completo', 'id', 'tag_name', 'published_at', 'draft', 'prerelease')))
    runs = agrupar(ler_csv(entrada / ARQUIVOS[3], ('nome_completo', 'id', 'workflow_id', 'event', 'head_branch', 'conclusion', 'created_at', 'run_started_at', 'updated_at')))
    disponivel = all((entrada / nome).is_file() for nome in ARQUIVOS[4:])
    registros = agrupar(ler_csv(entrada / ARQUIVOS[4], ('nome_completo', 'tag_name', 'anterior', 'motivo', 'commits', 'truncado'))) if disponivel else defaultdict(list)
    commits = agrupar(ler_csv(entrada / ARQUIVOS[5], ('nome_completo', 'tag_name', 'anterior', 'sha', 'data_autor'))) if disponivel else defaultdict(list)
    metricas, detalhes_cfr, episodios = [], [], []
    for repo in sorted(repos, key=lambda r: r['nome_completo'].casefold()):
        nome = repo['nome_completo']
        linha, detalhes, eps = calcular_repositorio(repo, releases[nome], runs[nome], registros[nome], commits[nome], janela, disponivel)
        metricas.append(linha)
        detalhes_cfr.extend(dict(nome_completo=nome, **d) for d in detalhes)
        episodios.extend(dict(nome_completo=nome, **e) for e in eps)
    # Nao exporta resultados de um conjunto de arquivos alterado durante a leitura.
    if any(hashlib.sha256((entrada / nome).read_bytes()).hexdigest() != sha for nome, sha in hashes.items()):
        raise ValueError('Dados de entrada mudaram durante o calculo. Execute novamente apos a coleta.')
    saida.mkdir(parents=True, exist_ok=True)
    salvar_csv(saida / 'metricas_variantes.csv', metricas, list(metricas[0]))
    salvar_csv(saida / 'cfr_entrega_releases.csv', detalhes_cfr,
               ('nome_completo', 'tag_name', 'published_at', 'censurada', 'falha', 'corretiva_tag', 'tag_semver', 'heuristica'))
    salvar_csv(saida / 'episodios_recuperacao.csv', episodios,
               ('nome_completo', 'workflow_id', 'inicio', 'fim', 'horas', 'falhas', 'censurado', 'censura_esquerda'))
    campos = ('frequencia_deploy_semana', 'lead_time_release_mediana_dias', 'lead_time_commit_mediana_dias',
              'cfr_ci', 'cfr_entrega', 'recuperacao_mediana_horas')
    auditoria = dict(issue=83, gerado_em=datetime.now(timezone.utc).isoformat(), janela=janela,
                     janela_confirmada=fonte['config'].get('janela_confirmada', False),
                     repositorios=len(metricas), heuristica=variantes.HEURISTICA, heuristica_validada_manualmente=False,
                     calculo_completo=all(m['calculo_completo'] for m in metricas), entrada_sha256=hashes,
                     arquivos_ausentes=[n for n in ARQUIVOS if n not in hashes],
                     pendencias=[dict(nome_completo=m['nome_completo'], motivos=m['pendencias']) for m in metricas if m['pendencias']],
                     resumo_entre_repositorios={c: variantes.resumo([m[c] for m in metricas if m[c] is not None]) for c in campos})
    (saida / 'resumo_rq83.json').write_text(json.dumps(auditoria, ensure_ascii=False, indent=2), encoding='utf-8')
    return auditoria


def principal(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--entrada', type=Path, default=RAIZ_PROJETO / 'dados/lab03_final')
    parser.add_argument('--saida', type=Path)
    parser.add_argument('--permitir-parcial', action='store_true', help='Diagnostica dados antigos sem commits; nao declara calculo completo.')
    args = parser.parse_args(argv)
    try:
        resultado = executar(args.entrada, args.saida or args.entrada / 'rq83', args.permitir_parcial)
    except (OSError, ValueError, KeyError) as erro:
        print(f'[erro] {erro}', file=sys.stderr)
        return 1
    print(f'RQ83: {resultado["repositorios"]} repositorios; calculo_completo={resultado["calculo_completo"]}')
    return 0 if resultado['calculo_completo'] else 2


if __name__ == '__main__':
    raise SystemExit(principal())
