"""RQ104: gerador de dados simulados pareados (com e sem cache), com semente fixa.

Implementa o contrato `reamostragem_empirica_pareada_estratificada_v1` definido na
RQ103 (`entregas/experimento-cache/RQ103/parametros_simulacao.json`):

* para cada estrato (tratamento que iniciou o par), sorteia com reposição e
  probabilidade uniforme índices de pares completos, na quantidade original;
* os dois tempos de um par são copiados juntos (nunca se sorteiam as marginais
  separadamente);
* a lista final é embaralhada com o mesmo gerador, inicializado uma única vez.

Além do cenário observado, o gerador oferece o cenário ``h0``: depois da
reamostragem, os rótulos "com cache" e "sem cache" de cada par são trocados com
probabilidade 1/2. Isso torna o rótulo irrelevante (H0 verdadeira por
construção): a diferença pareada d = t_sem - t_com fica simétrica em torno de
zero, o que satisfaz a H0 do t pareado (média zero) e a do Wilcoxon (simetria em
torno de zero). Os tempos continuam positivos, pois são sempre valores reais
observados.

Execução (um conjunto simulado de cada cenário, semente 104):

    python codigo-fonte/analise/rq104_gerador_simulacao.py
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
PARAMETROS = RAIZ / 'entregas/experimento-cache/RQ103/parametros_simulacao.json'
SAIDA = RAIZ / 'entregas/experimento-cache/RQ104'
METODO = 'reamostragem_empirica_pareada_estratificada_v1'
CENARIOS = ('observado', 'h0')
SEMENTE_PADRAO = 104
COLUNAS = ('sim_id', 'par_id_origem', 'ordem_primeiro', 'tempo_sem_cache_ms',
           'tempo_com_cache_ms', 'diferenca_ms', 'rotulos_trocados')


def exigir(condicao, mensagem):
    if not condicao:
        raise ValueError(mensagem)


def carregar_parametros(caminho=PARAMETROS):
    """Lê e valida o contrato da RQ103, devolvendo os estratos como arrays."""
    caminho = Path(caminho)
    p = json.loads(caminho.read_text(encoding='utf-8'))
    exigir(p.get('schema_version') == 1 and p.get('metodo') == METODO,
           f'Contrato não suportado: esperado {METODO} (schema 1).')
    exigir(p.get('unidade') == 'ms por operação no lote', 'Unidade inesperada.')
    estratos = []
    for e in p['estratos']:
        pares = e['pares']
        exigir(e['quantidade'] >= 1 and len(pares) >= 1, 'Estrato vazio.')
        sem = np.array([x['tempo_sem_cache_ms'] for x in pares], dtype=float)
        com = np.array([x['tempo_com_cache_ms'] for x in pares], dtype=float)
        exigir(np.all(np.isfinite(sem)) and np.all(np.isfinite(com)), 'Tempo não finito.')
        exigir(np.all(sem > 0) and np.all(com > 0), 'Tempos devem ser positivos.')
        estratos.append(dict(ordem_primeiro=e['ordem_primeiro'], quantidade=int(e['quantidade']),
                             par_id=np.array([x['par_id_origem'] for x in pares], dtype=int),
                             sem=sem, com=com))
    exigir(sum(e['quantidade'] for e in estratos) == p['tamanho_amostra_pares'],
           'Soma dos estratos difere do tamanho da amostra.')
    return dict(origem=p['origem'], sha256=hashlib.sha256(caminho.read_bytes()).hexdigest(),
                n=int(p['tamanho_amostra_pares']), semente_sugerida=p.get('semente_sugerida'),
                estratos=estratos)


def gerar_lote(parametros, rng, repeticoes=1, cenario='observado'):
    """Gera `repeticoes` conjuntos simulados de n pares, vetorizado.

    Devolve um dicionário de arrays com forma (repeticoes, n): `sem`, `com`,
    `diferenca`, `par_id`, `estrato` (índice do estrato de origem) e `trocado`.
    A ordem dos sorteios é fixa (estratos na ordem do contrato, depois o
    embaralhamento, depois as trocas de rótulo), então a mesma semente reproduz
    exatamente os mesmos dados.
    """
    exigir(cenario in CENARIOS, f'Cenário inválido: {cenario}. Use um de {CENARIOS}.')
    exigir(int(repeticoes) >= 1, 'repeticoes deve ser >= 1.')
    repeticoes = int(repeticoes)
    partes = {k: [] for k in ('sem', 'com', 'par_id', 'estrato')}
    for k, e in enumerate(parametros['estratos']):
        idx = rng.integers(0, len(e['sem']), size=(repeticoes, e['quantidade']))
        partes['sem'].append(e['sem'][idx])
        partes['com'].append(e['com'][idx])
        partes['par_id'].append(e['par_id'][idx])
        partes['estrato'].append(np.full(idx.shape, k))
    dados = {k: np.concatenate(v, axis=1) for k, v in partes.items()}
    # Embaralha cada conjunto (linha) com o mesmo gerador: a ordem das linhas não
    # carrega informação, mas o contrato pede a lista final embaralhada.
    ordem = rng.permuted(np.tile(np.arange(parametros['n']), (repeticoes, 1)), axis=1)
    dados = {k: np.take_along_axis(v, ordem, axis=1) for k, v in dados.items()}
    if cenario == 'h0':
        trocado = rng.random(dados['sem'].shape) < .5
        dados['sem'], dados['com'] = (np.where(trocado, dados['com'], dados['sem']),
                                      np.where(trocado, dados['sem'], dados['com']))
    else:
        trocado = np.zeros(dados['sem'].shape, dtype=bool)
    dados['trocado'] = trocado
    dados['diferenca'] = dados['sem'] - dados['com']
    return dados


def gerar_amostra(parametros, semente=SEMENTE_PADRAO, cenario='observado'):
    """Um único conjunto simulado, como lista de dicionários (uma linha por par)."""
    rng = np.random.default_rng(semente)
    d = gerar_lote(parametros, rng, 1, cenario)
    nomes = [e['ordem_primeiro'] for e in parametros['estratos']]
    return [dict(sim_id=i + 1, par_id_origem=int(d['par_id'][0, i]),
                 ordem_primeiro=nomes[d['estrato'][0, i]],
                 tempo_sem_cache_ms=float(d['sem'][0, i]), tempo_com_cache_ms=float(d['com'][0, i]),
                 diferenca_ms=round(float(d['diferenca'][0, i]), 9), rotulos_trocados=bool(d['trocado'][0, i]))
            for i in range(parametros['n'])]


def gravar_csv(linhas, caminho):
    with Path(caminho).open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        w.writeheader()
        w.writerows(linhas)


def ler_amostra(caminho):
    """Lê um CSV gravado por `gravar_csv` e devolve (sem, com) como arrays."""
    with Path(caminho).open(encoding='utf-8', newline='') as f:
        linhas = list(csv.DictReader(f))
    exigir(linhas and set(COLUNAS) <= set(linhas[0]), f'CSV de amostra inválido: {caminho}')
    return (np.array([float(r['tempo_sem_cache_ms']) for r in linhas]),
            np.array([float(r['tempo_com_cache_ms']) for r in linhas]))


def executar(parametros_json=PARAMETROS, saida=SAIDA, semente=SEMENTE_PADRAO):
    parametros = carregar_parametros(parametros_json)
    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    manifesto = dict(schema_version=1, metodo=METODO, semente=semente, gerador='numpy.random.default_rng',
                     numpy=np.__version__, parametros_sha256=parametros['sha256'],
                     execucao_id_origem=parametros['origem']['execucao_id'], n_pares=parametros['n'],
                     aviso='Dados SIMULADOS por reamostragem de pares reais da RQ102; não são novas medições.',
                     cenarios={})
    for cenario in CENARIOS:
        linhas = gerar_amostra(parametros, semente, cenario)
        nome = f'amostra_simulada_{cenario}.csv'
        gravar_csv(linhas, saida / nome)
        dif = np.array([r['diferenca_ms'] for r in linhas])
        manifesto['cenarios'][cenario] = dict(
            arquivo=nome, sha256=hashlib.sha256((saida / nome).read_bytes()).hexdigest(),
            pares_origem_distintos=len({r['par_id_origem'] for r in linhas}),
            rotulos_trocados=sum(r['rotulos_trocados'] for r in linhas),
            media_diferenca_ms=float(dif.mean()), mediana_diferenca_ms=float(np.median(dif)))
    (saida / 'manifesto.json').write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + '\n',
                                          encoding='utf-8')
    return manifesto


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--parametros', type=Path, default=PARAMETROS)
    parser.add_argument('--saida', type=Path, default=SAIDA)
    parser.add_argument('--semente', type=int, default=SEMENTE_PADRAO)
    args = parser.parse_args()
    try:
        m = executar(args.parametros, args.saida, args.semente)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f'Geração não concluída: {exc}\n')
    for nome, c in m['cenarios'].items():
        print(f"RQ104 [{nome}]: {m['n_pares']} pares, média d = {c['media_diferenca_ms']:.4f} ms "
              f"-> {args.saida / c['arquivo']}")


if __name__ == '__main__':
    main()
