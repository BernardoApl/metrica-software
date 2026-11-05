"""RQ107: prepara os dados reais e simulados do experimento de cache para os gráficos.

Lê os pares validados pela RQ103 e um conjunto simulado, calcula as descritivas
de forma e os histogramas com as mesmas classes para real e simulado, e exporta
um JSON único para o frontend. Saída determinística: reexecutar não altera o arquivo.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # permite executar como script

from analise import rq103_parametros_cache as rq103  # noqa: E402

RAIZ = rq103.RAIZ
PARAMETROS = RAIZ / 'entregas/experimento-cache/RQ103/parametros_simulacao.json'
SIMULADOS_RQ104 = RAIZ / 'entregas/experimento-cache/RQ104/pares_simulados.csv'
SAIDA = RAIZ / 'entregas/experimento-cache/RQ107/dados_visualizacao.json'

# Tempos com cache ficam abaixo de 1 µs: em ms o eixo só mostraria zeros.
SERIES = {
    'sem_cache': dict(rotulo='Sem cache', unidade='ms', fator=1.0),
    'com_cache': dict(rotulo='Com cache', unidade='µs', fator=1000.0),
    'diferenca': dict(rotulo='Diferença d = sem − com', unidade='ms', fator=1.0),
}
COLUNAS_SIMULADOS = ('tempo_sem_cache_ms', 'tempo_com_cache_ms')


def pares_reais(coleta=rq103.COLETA):
    """Reutiliza a validação da RQ103: coleta incoerente interrompe o processamento."""
    meta, pares = rq103.carregar(coleta)
    return meta, [(p['sem_cache'], p['com_cache']) for p in pares]


def reamostrar_contrato_rq103(parametros, semente=None):
    """Provisório até a #104: aplica o algoritmo publicado em parametros_simulacao.json."""
    rng = np.random.default_rng(parametros['semente_sugerida'] if semente is None else semente)
    pares = []
    for estrato in parametros['estratos']:
        origem = estrato['pares']
        for i in rng.integers(0, len(origem), size=estrato['quantidade']):
            pares.append((origem[i]['tempo_sem_cache_ms'], origem[i]['tempo_com_cache_ms']))
    return [pares[i] for i in rng.permutation(len(pares))]


def ler_simulados(caminho):
    with Path(caminho).open(encoding='utf-8-sig', newline='') as arquivo:
        linhas = list(csv.DictReader(arquivo))
    rq103.exigir(linhas, f'Simulados vazios: {caminho}')
    rq103.exigir(all(c in linhas[0] for c in COLUNAS_SIMULADOS),
                 f'Simulados devem ter as colunas {COLUNAS_SIMULADOS}.')
    pares = [tuple(rq103.numero(linha[c]) for c in COLUNAS_SIMULADOS) for linha in linhas]
    rq103.exigir(all(s > 0 and c > 0 for s, c in pares), 'Tempos simulados devem ser positivos.')
    return pares


def pares_simulados(parametros, execucao_id, caminho_rq104=SIMULADOS_RQ104):
    """Prefere a saída oficial da #104; sem ela, usa o contrato da RQ103 e declara isso."""
    rq103.exigir(parametros['origem']['execucao_id'] == execucao_id,
                 'Parâmetros da simulação vêm de outra coleta.')
    if Path(caminho_rq104).exists():
        return ler_simulados(caminho_rq104), 'rq104'
    return reamostrar_contrato_rq103(parametros), 'contrato_rq103_provisorio'


def serie(pares, nome):
    if nome == 'diferenca':
        valores = [s - c for s, c in pares]
    else:
        valores = [p[nome == 'com_cache'] for p in pares]
    return np.asarray(valores) * SERIES[nome]['fator']


def forma(valores):
    """Descritivas da RQ103 mais a assimetria, que orienta a escolha entre os testes."""
    return dict(rq103.descrever(valores.tolist()), assimetria=float(stats.skew(valores, bias=False)))


def histogramas(real, simulado, classes=12):
    """Classes compartilhadas: as alturas de real e simulado são comparáveis barra a barra."""
    bordas = np.histogram_bin_edges(np.concatenate([real, simulado]), bins=classes)
    return dict(bordas=bordas.tolist(),
                real=np.histogram(real, bordas)[0].tolist(),
                simulado=np.histogram(simulado, bordas)[0].tolist())


def processar(coleta=rq103.COLETA, parametros=PARAMETROS, caminho_rq104=SIMULADOS_RQ104):
    meta, reais = pares_reais(coleta)
    config = json.loads(Path(parametros).read_text(encoding='utf-8'))
    simulados, origem = pares_simulados(config, meta['execucao_id'], caminho_rq104)
    saida = dict(schema_version=1, execucao_id=meta['execucao_id'], origem_simulados=origem,
                 metodo_simulacao=config['metodo'], semente=config['semente_sugerida'],
                 pares_reais=len(reais), pares_simulados=len(simulados), series={})
    for nome, info in SERIES.items():
        r, s = serie(reais, nome), serie(simulados, nome)
        saida['series'][nome] = dict(
            rotulo=info['rotulo'], unidade=info['unidade'],
            real=dict(valores=r.tolist(), forma=forma(r)),
            simulado=dict(valores=s.tolist(), forma=forma(s)),
            histograma=histogramas(r, s))
    return saida


def executar(saida=SAIDA, **kwargs):
    dados = processar(**kwargs)
    saida = Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(dados, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    return dados


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--saida', type=Path, default=SAIDA)
    args = parser.parse_args()
    dados = executar(args.saida)
    print(f"RQ107: {dados['pares_reais']} pares reais, {dados['pares_simulados']} simulados "
          f"({dados['origem_simulados']}); saída em {args.saida}")


if __name__ == '__main__':
    main()
