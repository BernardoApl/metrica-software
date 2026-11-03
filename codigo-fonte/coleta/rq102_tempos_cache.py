"""RQ102: tempos reais de agregação de CSV com e sem cache de resultado."""
from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import platform
import random
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
TRATAMENTOS = ('sem_cache', 'com_cache')
CAMPOS = ['execucao_id', 'par_id', 'ordem', 'tratamento', 'repeticoes',
          'concluidas', 'duracao_total_ns', 'tempo_por_operacao_ns', 'tempo_ms',
          'cache_hits', 'cache_misses', 'aquecimento_cache_ns', 'status', 'erro',
          'resultado_sha256', 'entrada_sha256']


def agora():
    return datetime.now(timezone.utc).isoformat()


def digest(valor):
    return hashlib.sha256(json.dumps(valor, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def agregar_csv(caminho):
    """Abre, interpreta e agrupa todos os registros; retorna tuplas imutáveis."""
    grupos = {}
    nomes = set()
    with Path(caminho).open(encoding='utf-8-sig', newline='') as arquivo:
        leitor = csv.DictReader(arquivo)
        if not {'nome_completo', 'linguagem', 'estrelas'} <= set(leitor.fieldnames or []):
            raise ValueError('CSV precisa de nome_completo, linguagem e estrelas.')
        for linha in leitor:
            nome = (linha['nome_completo'] or '').strip()
            if not nome or nome in nomes:
                raise ValueError('Nome de repositório vazio ou duplicado.')
            nomes.add(nome)
            estrelas = int(linha['estrelas'])
            if estrelas < 0:
                raise ValueError('Estrelas não podem ser negativas.')
            linguagem = (linha['linguagem'] or '').strip() or 'Sem linguagem'
            n, soma = grupos.get(linguagem, (0, 0))
            grupos[linguagem] = (n + 1, soma + estrelas)
    if not nomes:
        raise ValueError('CSV vazio.')
    return tuple((linguagem, n, soma) for linguagem, (n, soma) in sorted(grupos.items()))


class CacheResultado:
    """Cache privado de uma operação/entrada fixa; nunca compartilhado entre runs."""
    def __init__(self, operacao):
        self.operacao = operacao
        self.limpar()

    def limpar(self):
        self.valores = {}
        self.hits = self.misses = 0

    def executar(self):
        if 'resultado' in self.valores:
            self.hits += 1
            return self.valores['resultado']
        self.misses += 1
        resultado = self.operacao()
        self.valores['resultado'] = resultado
        return resultado


def plano_ordens(pares, semente):
    if isinstance(pares, bool) or not isinstance(pares, int) or pares < 2:
        raise ValueError('Use pelo menos dois pares.')
    ordens = [TRATAMENTOS if i % 2 == 0 else TRATAMENTOS[::-1] for i in range(pares)]
    random.Random(semente).shuffle(ordens)
    return ordens


def medir(operacao, repeticoes, esperado, relogio=time.perf_counter_ns):
    """Cronometra o lote; confere TODAS as respostas somente após parar o relógio."""
    if isinstance(repeticoes, bool) or not isinstance(repeticoes, int) or repeticoes < 1:
        raise ValueError('Repetições devem ser um inteiro positivo.')
    resultados = []
    erro = ''
    inicio = relogio()
    try:
        for _ in range(repeticoes):
            resultados.append(operacao())
    except Exception as exc:
        erro = f'{type(exc).__name__}: {exc}'
    duracao = relogio() - inicio
    if duracao < 0:
        raise ValueError('O relógio deve ser monotônico.')
    status = 'erro' if erro else 'ok'
    if not erro and any(resultado != esperado for resultado in resultados):
        status, erro = 'resultado_divergente', 'O resultado difere da referência.'
    valido = status == 'ok'
    return dict(repeticoes=repeticoes, concluidas=len(resultados), duracao_total_ns=duracao,
                tempo_por_operacao_ns=duracao / repeticoes if valido else None,
                tempo_ms=duracao / repeticoes / 1_000_000 if valido else None,
                status=status, erro=erro,
                resultado_sha256=digest(resultados[-1]) if resultados else '')


def coletar_par(operacao, esperado, ordem, repeticoes):
    """Limpa e aquece antes do par, independentemente da ordem sorteada."""
    cache = CacheResultado(operacao)
    priming = medir(cache.executar, 1, esperado)
    linhas = []
    for posicao, tratamento in enumerate(ordem, 1):
        hits, misses = cache.hits, cache.misses
        if tratamento == 'com_cache' and priming['status'] != 'ok':
            linha = dict(priming, repeticoes=repeticoes, concluidas=0,
                         duracao_total_ns=None, tempo_por_operacao_ns=None, tempo_ms=None,
                         status='erro_aquecimento')
        else:
            linha = medir(operacao if tratamento == 'sem_cache' else cache.executar,
                          repeticoes, esperado)
        linha.update(ordem=posicao, tratamento=tratamento,
                     cache_hits=cache.hits - hits, cache_misses=cache.misses - misses,
                     aquecimento_cache_ns=priming['duracao_total_ns'])
        linhas.append(linha)
    return linhas


def executar(entrada, saida, pares=30, repeticoes=20, aquecimentos=3, semente=102):
    plano = plano_ordens(pares, semente)
    if isinstance(repeticoes, bool) or not isinstance(repeticoes, int) or repeticoes < 1:
        raise ValueError('Repetições devem ser um inteiro positivo.')
    if isinstance(aquecimentos, bool) or not isinstance(aquecimentos, int) or aquecimentos < 0:
        raise ValueError('Aquecimentos devem ser um inteiro não negativo.')
    entrada, saida = Path(entrada).resolve(), Path(saida).resolve()
    conteudo = entrada.read_bytes()
    hash_entrada = hashlib.sha256(conteudo).hexdigest()
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:10]
    destino = saida / run_id
    destino.mkdir(parents=True, exist_ok=False)
    snapshot = destino / 'entrada.csv'
    snapshot.write_bytes(conteudo)
    operacao = lambda: agregar_csv(snapshot)
    relogio = time.get_clock_info('perf_counter')
    meta = dict(schema_version=1, execucao_id=run_id, iniciado_em=agora(), status='em_andamento',
                operacao='csv_agrupar_linguagem_v1', entrada_nome=entrada.name,
                entrada_sha256=hash_entrada, coletor_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                parametros=dict(pares=pares, repeticoes_por_tratamento=repeticoes,
                                pares_aquecimento=aquecimentos, semente=semente),
                plano=[list(ordem) for ordem in plano],
                cache='resultado em memória; vazio e preenchido antes de cada par; hits cronometrados',
                limite='Cache de aplicação, não de disco/OS. Mesma entrada repetida; não generaliza para rede ou cache frio.',
                unidade='ms por operação (tempo total do lote dividido pelas repetições)',
                ambiente=dict(python=sys.version, plataforma=platform.platform(),
                              arquitetura=platform.machine(), gc_habilitado=gc.isenabled()),
                relogio=dict(nome='perf_counter_ns', monotonic=relogio.monotonic,
                             resolucao_segundos=relogio.resolution, implementacao=relogio.implementation))
    def salvar_meta():
        (destino / 'execucao.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    salvar_meta()
    campos_pares = ['execucao_id', 'par_id', 'ordem_primeiro', 'tempo_sem_cache_ms',
                    'tempo_com_cache_ms', 'diferenca_ms', 'valido']
    concluidos = validos = 0
    try:
        esperado = operacao()
        meta['resultado_sha256'] = digest(esperado)
        meta['repositorios'] = sum(g[1] for g in esperado)
        (destino / 'resultado.json').write_text(json.dumps(esperado, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        # Aquecimentos do ambiente também são exportados, separados da amostra medida.
        with (destino / 'aquecimentos.csv').open('w', encoding='utf-8', newline='') as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=CAMPOS)
            escritor.writeheader()
            for i in range(aquecimentos):
                for linha in coletar_par(operacao, esperado, plano[i % pares], repeticoes):
                    escritor.writerow(dict(linha, execucao_id=run_id, par_id=i + 1, entrada_sha256=hash_entrada))
                    arquivo.flush()
                    if linha['status'] != 'ok':
                        raise ValueError('Falha no aquecimento; consulte aquecimentos.csv.')
        with (destino / 'tempos.csv').open('w', encoding='utf-8', newline='') as bruto, \
             (destino / 'pares.csv').open('w', encoding='utf-8', newline='') as pareado:
            escritor = csv.DictWriter(bruto, fieldnames=CAMPOS)
            escritor.writeheader()
            escritor_pares = csv.DictWriter(pareado, fieldnames=campos_pares)
            escritor_pares.writeheader()
            for par_id, ordem in enumerate(plano, 1):
                linhas = coletar_par(operacao, esperado, ordem, repeticoes)
                for linha in linhas:
                    escritor.writerow(dict(linha, execucao_id=run_id, par_id=par_id, entrada_sha256=hash_entrada))
                bruto.flush()
                por_tratamento = {linha['tratamento']: linha for linha in linhas}
                valido = all(linha['status'] == 'ok' for linha in linhas)
                sem = por_tratamento['sem_cache']['tempo_ms']
                com = por_tratamento['com_cache']['tempo_ms']
                escritor_pares.writerow(dict(execucao_id=run_id, par_id=par_id, ordem_primeiro=ordem[0],
                    tempo_sem_cache_ms=sem, tempo_com_cache_ms=com,
                    diferenca_ms=sem - com if valido else None, valido=valido))
                pareado.flush()
                concluidos += 1
                validos += int(valido)
        if hashlib.sha256(snapshot.read_bytes()).hexdigest() != hash_entrada:
            raise ValueError('Snapshot da entrada foi alterado durante a execução; descarte esta execução.')
        meta['status'] = 'concluida' if validos == pares else 'concluida_com_erros'
    except BaseException as exc:
        meta['status'] = 'interrompida' if isinstance(exc, KeyboardInterrupt) else 'erro'
        meta['erro'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        meta.update(finalizado_em=agora(), pares_concluidos=concluidos, pares_validos=validos)
        meta['artefatos_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in destino.iterdir() if p.is_file() and p.name != 'execucao.json'}
        salvar_meta()
    return destino, meta


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--entrada', type=Path, default=RAIZ / 'dados/lab03_final/metricas_repositorios.csv')
    parser.add_argument('--saida', type=Path, default=RAIZ / 'dados/experimento_cache')
    parser.add_argument('--pares', type=int, default=30)
    parser.add_argument('--repeticoes', type=int, default=20)
    parser.add_argument('--aquecimentos', type=int, default=3)
    parser.add_argument('--semente', type=int, default=102)
    args = parser.parse_args()
    try:
        destino, meta = executar(**vars(args))
    except (ValueError, OSError, csv.Error) as exc:
        parser.exit(1, f'Coleta não concluída: {exc}\n')
    print(json.dumps(dict(diretorio=str(destino), status=meta['status'],
                          pares_validos=meta['pares_validos']), ensure_ascii=False, indent=2))
    return 0 if meta['status'] == 'concluida' else 1


if __name__ == '__main__':
    raise SystemExit(main())
