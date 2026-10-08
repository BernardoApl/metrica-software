"""RQ75: releases, tags datadas pelo commit e commits entre releases."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap import RAIZ_PROJETO, configurar_caminhos
configurar_caminhos()
from cliente_github import obter_token
from cliente_rest import ClienteREST, ErroREST, ErroAutenticacaoREST
from coleta_dora import coletar_releases, coletar_compare, limites_da_janela, CAMPOS_RELEASE
from metricas.lead_time import pares_de_releases
from pipeline_dora import salvar_csv
from rq74_metadados_repositorios import ler_selecao, substituir_com_retentativa


def compactar_tags(corpo):
    return [{'tag_name': t['name'], 'sha': (t.get('commit') or {}).get('sha')}
            for t in corpo]


def compactar_commit(corpo):
    commit = corpo.get('commit') or {}
    return {'sha': corpo.get('sha'), 'data_autor': (commit.get('author') or {}).get('date')}


def coletar_tags(cliente, nome, inicio, fim, releases):
    abertura, fechamento = limites_da_janela(inicio, fim)
    fechamento += timedelta(seconds=1)
    associadas = {r.get('tag_name') for r in releases}
    tags, vistos, commits = [], set(), {}
    status = 200
    for pagina in cliente.paginar(f'/repos/{nome}/tags', {'per_page': 100}, compactar=compactar_tags):
        status = pagina['status']
        if status != 200:
            break
        for tag in pagina['corpo'] or []:
            if tag['tag_name'] in vistos:
                continue
            vistos.add(tag['tag_name'])
            sha = tag.get('sha')
            if sha and sha not in commits:
                try:
                    commits[sha] = cliente.get(f'/repos/{nome}/commits/{quote(sha, safe="")}',
                                              compactar=compactar_commit)
                except ErroAutenticacaoREST:
                    raise
                except ErroREST as erro:
                    commits[sha] = {'status': None, 'corpo': None, 'erro': str(erro)}
            resposta = commits.get(sha, {'status': None, 'corpo': None})
            corpo = resposta.get('corpo') or {}
            texto = corpo.get('data_autor')
            data = None
            if texto:
                try:
                    data = datetime.fromisoformat(texto.replace('Z', '+00:00'))
                    if data.tzinfo is None:
                        data = None
                except ValueError:
                    pass
            valido = resposta['status'] == 200 and corpo.get('sha') == sha and data is not None
            tags.append(dict(tag, data_autor=texto, status_commit=resposta['status'],
                             status='ok' if valido else 'indisponivel',
                             erro=resposta.get('erro'), tem_release=tag['tag_name'] in associadas,
                             dentro_janela=bool(valido and abertura <= data < fechamento)))
    return {'status': status, 'tags': tags}


def coletar_repositorio(cliente, nome, inicio, fim, max_paginas=None):
    resultado = {'nome_completo': nome, 'janela': {'inicio': inicio, 'fim': fim},
                 'coletado_em': datetime.now(timezone.utc).isoformat(),
                 'releases': [], 'tags': [], 'comparacoes': [], 'commits': [], 'concluido': False}
    releases = coletar_releases(cliente, nome, inicio, fim)
    resultado.update(releases=releases['releases'], status_releases=releases['status'])
    if releases['status'] != 200:
        return resultado
    tags = coletar_tags(cliente, nome, inicio, fim, releases['releases'])
    resultado.update(tags=tags['tags'], status_tags=tags['status'])
    for anterior, release in pares_de_releases(releases['releases']):
        linha = dict(release_id=release['id'], tag_name=release['tag_name'],
                     anterior=anterior['tag_name'] if anterior else None,
                     status=None, total_commits=None, coletados=0, truncado=False,
                     motivo='sem_release_anterior' if anterior is None else None)
        if anterior is not None:
            try:
                compare = coletar_compare(cliente, nome, anterior['tag_name'], release['tag_name'], max_paginas)
            except ErroAutenticacaoREST:
                raise
            except ErroREST as erro:
                compare = {'status': None, 'commits': [], 'truncado': True, 'erro': str(erro)}
            linha.update(status=compare['status'], total_commits=compare.get('total_commits'),
                         coletados=len(compare['commits']), truncado=compare['truncado'],
                         motivo=('compare_indisponivel' if compare['status'] != 200 else
                                 'compare_truncado' if compare['truncado'] else None),
                         erro=compare.get('erro'))
            resultado['commits'].extend(dict(c, release_id=release['id'], tag_name=release['tag_name'],
                                             anterior=anterior['tag_name']) for c in compare['commits'])
        resultado['comparacoes'].append(linha)
    resultado['concluido'] = (tags['status'] == 200 and all(t['status'] == 'ok' for t in tags['tags'])
        and all(c['motivo'] in (None, 'sem_release_anterior') for c in resultado['comparacoes']))
    return resultado


COLUNAS = {
    'releases': ('nome_completo', *CAMPOS_RELEASE, 'dentro_janela'),
    'tags': ('nome_completo', 'tag_name', 'sha', 'data_autor', 'tem_release', 'dentro_janela', 'status', 'status_commit', 'erro'),
    'comparacoes': ('nome_completo', 'release_id', 'tag_name', 'anterior', 'status', 'total_commits', 'coletados', 'truncado', 'motivo', 'erro'),
    'commits': ('nome_completo', 'release_id', 'tag_name', 'anterior', 'sha', 'data_autor', 'mensagem'),
}


def salvar_json(caminho, dados):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(caminho.suffix + '.tmp')
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding='utf-8')
    substituir_com_retentativa(temporario, caminho)


def exportar(resultados, saida, contexto):
    for tipo, colunas in COLUNAS.items():
        linhas = (dict(linha, nome_completo=r['nome_completo']) for r in resultados for linha in r[tipo])
        comprimido = tipo == 'commits'
        salvar_csv(saida / (tipo + ('.csv.gz' if comprimido else '.csv')), linhas, colunas, comprimido)
    salvar_json(saida / 'resumo.json', dict(contexto, total=len(resultados),
        completos=sum(r['concluido'] for r in resultados),
        concluido=(len(resultados) == len(contexto.get('repositorios_solicitados', resultados))
                   and all(r['concluido'] for r in resultados)),
        contagens={t: sum(len(r[t]) for r in resultados) for t in COLUNAS}))


def principal(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=RAIZ_PROJETO / 'config/pipeline.json')
    parser.add_argument('--entrada', type=Path, default=RAIZ_PROJETO / 'dados/lab03/metricas_repositorios.csv')
    parser.add_argument('--repositorio', action='append', help='Restringe a coleta a owner/repo da entrada; repetivel.')
    parser.add_argument('--saida', type=Path, default=RAIZ_PROJETO / 'dados/lab03/rq75')
    parser.add_argument('--cache', type=Path, default=RAIZ_PROJETO / 'dados/.cache/rq75')
    args = parser.parse_args(argv)
    try:
        config = json.loads(args.config.read_text(encoding='utf-8'))
        inicio, fim = config['janela']['inicio'], config['janela']['fim']
        limites_da_janela(inicio, fim)
        nomes = ler_selecao(args.entrada)
        if args.repositorio:
            desejados = {n.casefold() for n in args.repositorio}
            if not desejados <= {n.casefold() for n in nomes}:
                raise ValueError('Repositorio solicitado ausente da entrada.')
            nomes = [n for n in nomes if n.casefold() in desejados]
        contexto = dict(issue=75, janela=config['janela'], aviso_janela=config.get('_comentario'),
                        repositorios_solicitados=nomes,
                        entrada_sha256=hashlib.sha256(args.entrada.read_bytes()).hexdigest())
        resumo = args.saida / 'resumo.json'
        if resumo.exists():
            anterior = json.loads(resumo.read_text(encoding='utf-8'))
            if any(anterior.get(k) != contexto[k] for k in ('janela', 'repositorios_solicitados', 'entrada_sha256')):
                raise ValueError('Saida pertence a outra entrada/janela. Informe outra --saida.')
        cliente = ClienteREST(obter_token(), args.cache)
        resultados = []
        for nome in nomes:
            checkpoint = args.saida / 'repositorios' / (nome.replace('/', '__') + '.json')
            if checkpoint.exists():
                salvo = json.loads(checkpoint.read_text(encoding='utf-8'))
                if salvo.get('nome_completo') != nome or salvo.get('janela') != config['janela']:
                    raise ValueError('Checkpoint pertence a outro repositorio/janela.')
                resultados.append(salvo)
        exportar(resultados, args.saida, contexto)
        for nome in nomes:
            salvo = next((r for r in resultados if r['nome_completo'] == nome), None)
            if salvo and salvo['concluido']:
                continue
            resultado = coletar_repositorio(cliente, nome, inicio, fim)
            salvar_json(args.saida / 'repositorios' / (nome.replace('/', '__') + '.json'), resultado)
            resultados = [r for r in resultados if r['nome_completo'] != nome]
            resultados.append(resultado)
            exportar(resultados, args.saida, contexto)
            print(f'RQ75: {len(resultados)}/{len(nomes)} processados; {nome}; completo={resultado["concluido"]}', flush=True)
        return 0 if all(r['concluido'] for r in resultados) else 1
    except (OSError, ValueError, KeyError, ErroREST, RuntimeError) as erro:
        print(f'[erro] {erro}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('Interrompido. Reexecute para retomar pelo cache.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    raise SystemExit(principal())
