"""RQ82: coleta retomavel e consolidacao auditada de pelo menos 300 repositorios."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import pipeline_dora as pipeline
from cliente_github import obter_token
from cliente_rest import ErroAutenticacaoREST, ErroREST
from rq75_releases_tags_commits import coletar_tags, COLUNAS, salvar_json
from rq74_metadados_repositorios import substituir_com_retentativa


def validar_config(config):
    if config['meta_repositorios'] < 300:
        raise ValueError('A RQ82 exige meta de pelo menos 300 repositorios.')
    if config['criterios']['minimo_releases'] < 5 or config['criterios']['minimo_runs_validos'] < 50:
        raise ValueError('Nao reduza os criterios minimos de 5 releases e 50 runs validos.')
    if config.get('limite_paginas_compare') is not None:
        raise ValueError('A coleta final deve usar limite de paginas de compare nulo.')
    limite_runs = config.get('limite_runs_por_repositorio')
    if limite_runs is not None and (type(limite_runs) is not int or limite_runs < config['criterios']['minimo_runs_validos']):
        raise ValueError('O limite operacional de runs deve ser inteiro, pelo menos o minimo exigido, ou nulo.')
    if type(config.get('janela_confirmada')) is not bool:
        raise ValueError('Informe janela_confirmada como booleano.')
    inicio = pipeline.coleta_dora.para_data(config['janela']['inicio'])
    fim = pipeline.coleta_dora.para_data(config['janela']['fim'])
    if (fim - inicio).days + 1 not in (365, 366):
        raise ValueError('A janela final deve abranger 12 meses (365 ou 366 dias).')


def problemas_coleta(avaliacao):
    if avaliacao['motivo'] != pipeline.INCLUIDO:
        return []
    m = avaliacao['metricas']
    problemas = []
    for campo in ('intervalos_no_teto', 'releases_compare_indisponivel', 'releases_compare_truncado'):
        if m.get(campo, 0):
            problemas.append(campo)
    if avaliacao.get('status_tags') != 200 or any(t.get('status') != 'ok' for t in avaliacao.get('tags', [])):
        problemas.append('tags_incompletas')
    if any(not c.get('sha') or not c.get('data_autor') for c in avaliacao.get('commits', [])):
        problemas.append('commits_sem_sha_ou_data')
    return problemas


def criar_avaliador(config, candidatos):
    # O hash evita reutilizar resultados de outra janela, base ou implementacao.
    fontes = [Path(__file__), Path(pipeline.__file__),
              Path(pipeline.coleta_dora.__file__), Path(pipeline.lead_time.__file__),
              Path(pipeline.ci.__file__), Path(pipeline.dora.__file__),
              Path(sys.modules[coletar_tags.__module__].__file__),
              Path(pipeline.git_local.__file__)]
    contexto = hashlib.sha256(json.dumps({'config': config, 'candidatos': candidatos},
                                       sort_keys=True).encode())
    for fonte in fontes:
        contexto.update(fonte.read_bytes())
    pasta = pipeline.caminho_projeto(config['diretorio_checkpoints']) / contexto.hexdigest()
    pasta.mkdir(parents=True, exist_ok=True)
    fabrica_git = pipeline.criar_fabrica_git(config)

    def avaliar(cliente, candidato, configuracao):
        nome = candidato['nome_completo']
        caminho = pasta / (hashlib.sha256(nome.casefold().encode()).hexdigest() + '.json.gz')
        if caminho.exists():
            with gzip.open(caminho, 'rt', encoding='utf-8') as arquivo:
                salvo = json.load(arquivo)
            if salvo.get('reutilizavel') and salvo['avaliacao']['nome_completo'] == nome:
                return salvo['avaliacao']
        argumentos = (cliente, candidato, configuracao)
        try:
            avaliacao = (pipeline.avaliar_repositorio(*argumentos, fabrica_git=fabrica_git)
                         if fabrica_git else pipeline.avaliar_repositorio(*argumentos))
        except ErroAutenticacaoREST:
            raise
        except ErroREST as erro:
            # Falha que persistiu depois das tentativas do cliente (5xx, rede): nao derruba
            # a coleta inteira. Nao e gravada como reutilizavel nem entra no cache HTTP,
            # entao a proxima passada tenta de novo.
            return {'nome_completo': nome, 'estrelas': pipeline._inteiro(candidato.get('estrelas')),
                    'motivo': 'inacessivel', 'erro': str(erro), 'transitorio': True}
        if avaliacao['motivo'] == pipeline.INCLUIDO and 'tags' not in avaliacao:
            # Sem tags do clone git (desligado ou falhou): busca pela API.
            janela = configuracao['janela']
            try:
                tags = coletar_tags(cliente, nome, janela['inicio'], janela['fim'],
                                    avaliacao['releases'], avaliacao.get('commits', ()))
                avaliacao.update(tags=tags['tags'], status_tags=tags['status'])
            except ErroAutenticacaoREST:
                raise
            except ErroREST as erro:
                avaliacao.update(tags=[], status_tags=None, erro_tags=str(erro))
        problemas = problemas_coleta(avaliacao)
        reutilizavel = avaliacao['motivo'] != 'inacessivel' and not problemas
        temporario = caminho.with_suffix('.tmp')
        with gzip.open(temporario, 'wt', encoding='utf-8') as arquivo:
            json.dump({'avaliacao': avaliacao, 'reutilizavel': reutilizavel}, arquivo, ensure_ascii=False)
        substituir_com_retentativa(temporario, caminho)
        return avaliacao

    return avaliar


def validar_amostra(resultado, config):
    amostra = resultado['amostra']
    nomes = [r['nome_completo'].casefold() for r in amostra]
    pendencias = []
    if len(amostra) < max(300, config['meta_repositorios']):
        pendencias.append({'motivo': 'meta_nao_atingida', 'total': len(amostra)})
    if len(set(nomes)) != len(nomes):
        pendencias.append({'motivo': 'repositorios_duplicados'})
    if not config.get('janela_confirmada'):
        pendencias.append({'motivo': 'janela_nao_confirmada'})
    for linha in amostra:
        nome = linha['nome_completo']
        if linha['releases_janela'] < config['criterios']['minimo_releases'] or linha['runs_validos'] < config['criterios']['minimo_runs_validos']:
            pendencias.append({'nome_completo': nome, 'motivo': 'criterios_nao_atendidos'})
        if linha.get('contribuidores_total') in (None, ''):
            pendencias.append({'nome_completo': nome, 'motivo': 'contribuidores_ausentes'})
        if linha.get('idade_anos') in (None, ''):
            pendencias.append({'nome_completo': nome, 'motivo': 'idade_ausente'})
    for avaliacao in resultado['avaliacoes']:
        pendencias.extend({'nome_completo': avaliacao['nome_completo'], 'motivo': p}
                          for p in problemas_coleta(avaliacao))
        if avaliacao.get('transitorio'):
            pendencias.append({'nome_completo': avaliacao['nome_completo'],
                               'motivo': 'falha_temporaria_persistente', 'erro': avaliacao.get('erro')})
    if resultado['funil'][-1]['aprovados'] != len(amostra):
        pendencias.append({'motivo': 'funil_inconsistente'})
    return {'issue': 82, 'repositorios': len(amostra), 'meta': config['meta_repositorios'],
            'janela': config['janela'], 'amostra_final_validada': not pendencias,
            'pendencias': pendencias}


def registrar_com_hora(mensagem):
    print('%s %s' % (datetime.now().strftime('%H:%M:%S'), mensagem), flush=True)


def executar_com_passadas(cliente, candidatos, config, passadas, espera=120, dormir=time.sleep):
    """Repete a avaliacao enquanto sobrar repositorio que falhou por erro temporario da API.

    Cada passada reaproveita checkpoints e cache HTTP: so o que falhou e refeito. Uma
    falha temporaria tirava o repositorio do funil e puxava um candidato de menos
    estrelas para o lugar dele; refazer a passada devolve a ordem por estrelas.
    """
    passadas = max(1, passadas)
    for passada in range(1, passadas + 1):
        resultado = pipeline.executar(cliente, candidatos, config, registrar=registrar_com_hora,
                                      avaliador=criar_avaliador(config, candidatos))
        falhas = [a['nome_completo'] for a in resultado['avaliacoes'] if a.get('transitorio')]
        if not falhas or passada == passadas:
            return resultado
        registrar_com_hora('[passada %d] %d repositorio(s) com falha temporaria da API (%s...); '
                           'nova passada em %d s.' % (passada, len(falhas), falhas[0], espera * passada))
        dormir(espera * passada)


def principal(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=pipeline.RAIZ_PROJETO / 'config/rq82_amostra_final.json')
    parser.add_argument('--passadas', type=int, default=3,
                        help='Quantas vezes repetir a avaliacao se houver falha temporaria da API.')
    args = parser.parse_args(argv)
    try:
        config = pipeline.carregar_config(args.config)
        validar_config(config)
        entrada = pipeline.caminho_projeto(config['candidatos']['metadados'])
        candidatos = pipeline.ler_candidatos(entrada)
        cliente = pipeline.criar_cliente(obter_token(), config)
        resultado = executar_com_passadas(cliente, candidatos, config, args.passadas)
        saida = pipeline.exportar(resultado, config, cliente)
        pipeline.salvar_csv(saida / 'tags.csv', resultado['tags'], COLUNAS['tags'])
        auditoria = validar_amostra(resultado, config)
        auditoria['entrada_sha256'] = hashlib.sha256(entrada.read_bytes()).hexdigest()
        salvar_json(saida / 'validacao_rq82.json', auditoria)
        print(f'RQ82: {len(resultado["amostra"])} repositorios; validada={auditoria["amostra_final_validada"]}; saida={saida}')
        return 0 if auditoria['amostra_final_validada'] else 2
    except (OSError, ValueError, KeyError, RuntimeError) as erro:
        print(f'[erro] {erro}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('Interrompido. Reexecute para reaproveitar cache e checkpoints.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    raise SystemExit(principal())
