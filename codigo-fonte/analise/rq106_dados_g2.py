"""RQ106: dados do gráfico G2 (distribuições sob H0, regiões de rejeição e p-valores).

Para cada amostra da RQ105 calcula, para os dois testes:

* t pareado: densidade da t de Student com n - 1 gl, valores críticos e t observado;
* Wilcoxon pareado: distribuição exata de W+ sob H0 (permutação dos sinais,
  condicionada aos postos da amostra), limites da região de rejeição e W+ observado.

Grava `codigo-fonte/frontend/dados/g2.js` (atribui `window.G2_DADOS`), lido pelo
`g2.js` do frontend. Um arquivo .js, e não .json, para a página abrir também por
file:// sem servidor.

    python codigo-fonte/analise/rq106_dados_g2.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analise import rq105_testes_pareados as rq105  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
SAIDA = RAIZ / 'codigo-fonte/frontend/dados/g2.js'
LIMITE_T = 5.0          # eixo do t: [-5, 5]; observados fora disso são indicados na borda
PONTOS_T = 401
ORDEM = ('simulada_h0', 'simulada_observado', 'reais')


def dados_t(r):
    gl = r['graus_liberdade']
    x = np.linspace(-LIMITE_T, LIMITE_T, PONTOS_T)
    return dict(gl=gl, x=np.round(x, 4).tolist(), densidade=np.round(stats.t.pdf(x, gl), 6).tolist(),
                critico=round(r['valor_critico'], 6), observado=r['estatistica'], p_valor=r['p_valor'],
                rejeita_h0=r['rejeita_h0'])


def dados_wilcoxon(sem, com, r):
    d, postos = rq105.postos_wilcoxon(np.asarray(sem) - np.asarray(com))
    valores, prob = rq105.distribuicao_nula_wplus(postos)
    inferior, superior = r['limites_rejeicao']
    return dict(n_efetivo=r['n_efetivo'], total=float(postos.sum()), empates=r['empates_em_abs_d'],
                valores=valores.tolist(), probabilidade=[float(f'{p:.6g}') for p in prob],
                limite_inferior=inferior, limite_superior=superior, nivel_real=r['nivel_real'],
                observado=r['estatistica'], espelho=float(postos.sum()) - r['estatistica'],
                p_valor=r['p_valor'], metodo=r['metodo'], rejeita_h0=r['rejeita_h0'])


def montar(resultados=None, amostras=None):
    amostras = amostras or rq105.amostras()
    resultados = resultados or {k: rq105.aplicar(s, c, rotulo=n) for k, (n, s, c) in amostras.items()}
    saida = dict(schema_version=1, alfa=rq105.ALFA, gerado_por='codigo-fonte/analise/rq106_dados_g2.py',
                 amostras={})
    for chave in ORDEM:
        rotulo, sem, com = amostras[chave]
        r = resultados[chave]
        saida['amostras'][chave] = dict(
            rotulo=rotulo, n_pares=r['n_pares'],
            media_diferenca_ms=r['t_pareado']['media_diferenca_ms'],
            t=dados_t(r['t_pareado']), wilcoxon=dados_wilcoxon(sem, com, r['wilcoxon_pareado']))
    return saida


def executar(saida=SAIDA):
    dados = montar()
    saida = Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    corpo = json.dumps(dados, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    saida.write_text('// Gerado por codigo-fonte/analise/rq106_dados_g2.py. Não editar à mão.\n'
                     f'window.G2_DADOS = {corpo};\n', encoding='utf-8')
    return dados


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--saida', type=Path, default=SAIDA)
    args = parser.parse_args()
    dados = executar(args.saida)
    for k, a in dados['amostras'].items():
        print(f"RQ106 [{k}]: t = {a['t']['observado']:.4g} (p = {a['t']['p_valor']:.3g}); "
              f"W+ = {a['wilcoxon']['observado']:g} (p = {a['wilcoxon']['p_valor']:.3g})")
    print(f'-> {args.saida}')


if __name__ == '__main__':
    main()
