"""RQ113: Q2 e Q3 — poder do t pareado e do Wilcoxon pareado por tamanho de efeito.

Os dois testes só dependem da diferença pareada d = t_sem - t_com. Cada cenário gera
10.000 amostras de d sob H0 (efeito zero) e soma um efeito δ conhecido:

    d_efeito = d_H0 + δ,   δ = d_z × σ_d

onde σ_d é o desvio padrão populacional de d_H0 no cenário e d_z é o tamanho de efeito
padronizado (d de Cohen para pares). Usar d_z no eixo permite comparar cenários com
escalas diferentes. As mesmas amostras-base são reutilizadas para todos os efeitos de
um cenário (números aleatórios comuns): as curvas ficam suaves e as diferenças entre
efeitos não vêm de sorteios diferentes.

Cenários (todos calibrados nos 30 pares reais, pelo contrato da #103 / gerador da #104):

* base (Q2): reamostra pares reais, centra cada diferença na média real e sorteia o
  sinal (±1 com chance 1/2): d_H0 = s × (d_real − média). É a variação real em torno
  do centro, simetrizada; H0 vale para os dois testes (média zero e simetria em zero).
  Não se usa a troca de rótulos da Q1 (#110) porque ela gera diferenças bimodais
  (±6 ms, nada perto de zero), forma em que um deslocamento mínimo reordena todos os
  postos e a curva do Wilcoxon ganha degraus que não dizem nada sobre o cenário.
* amostra_pequena (Q3): a base com 10 pares (5 por estrato).
* outliers (Q3): a base com contaminação: cada diferença é multiplicada por 5 com
  probabilidade 10% (a coleta real teve 3 extremos em 30 pares). Continua simétrica,
  então H0 vale para os dois testes; o que muda é a cauda pesada.
* assimetria (Q3): d_H0 = d_real − média(d_real), sem sortear o sinal. Mantém a
  assimetria real (coeficiente ≈ 1,9) e tem média zero: H0 do t (μ_d = 0) é verdadeira,
  mas a do Wilcoxon (simetria em zero) não é. Rejeições do Wilcoxon com δ = 0 são,
  portanto, falsos positivos para a pergunta "o cache altera o tempo médio?".

Decisão estrita p < α, bilateral, para α = 0,05 e α = 0,01. O t é o mesmo da #105
(vetorizado) e o Wilcoxon usa o p-valor exato da #105 (permutação dos sinais com postos
médios). O efeito d_z = 0 de cada cenário é o erro tipo I daquele cenário.

    python codigo-fonte/analise/rq113_poder.py      (≈ 1 min; grava entregas/experimento-cache/RQ113)
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
import math
import platform
import sys
import time
from pathlib import Path

import numpy as np
import scipy
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analise import rq104_gerador_simulacao as rq104  # noqa: E402
from analise import rq105_testes_pareados as rq105  # noqa: E402

SAIDA = rq104.RAIZ / 'entregas/experimento-cache/RQ113'
SEMENTE = 113
REPETICOES = 10_000
EFEITOS_DZ = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0)
ALFAS = (0.05, 0.01)
FATOR_OUTLIER, PROB_OUTLIER = 5.0, 0.10
TESTES = ('t_pareado', 'wilcoxon_pareado')
CENARIOS = {
    'base': dict(rotulo='Base (30 pares)', questao='Q2',
                 violacao='nenhuma: variação real das diferenças, simetrizada em torno de zero'),
    'amostra_pequena': dict(rotulo='Amostra pequena (10 pares)', questao='Q3',
                            violacao='n = 10: o t depende mais da normalidade; o Wilcoxon fica mais discreto'),
    'outliers': dict(rotulo='Outliers (10% × 5)', questao='Q3',
                     violacao='cauda pesada: 10% das diferenças com magnitude 5 vezes maior'),
    'assimetria': dict(rotulo='Assimetria real (média zero)', questao='Q3',
                       violacao='diferenças assimétricas: H0 do t vale, a simetria do Wilcoxon não'),
}


def exigir(condicao, mensagem):
    if not condicao:
        raise ValueError(mensagem)


# ------------------------------------------------------------- testes vetorizados

def p_t_pareado(d):
    """p-valores bilaterais do t pareado, uma amostra por linha (igual a ttest_rel)."""
    d = np.atleast_2d(d)
    n = d.shape[1]
    dp = d.std(axis=1, ddof=1)
    exigir(np.all(dp > 0), 'Amostra com desvio padrão zero.')
    t = d.mean(axis=1) / (dp / math.sqrt(n))
    return 2 * stats.t.sf(np.abs(t), n - 1)


def p_wilcoxon(d):
    """p-valor exato do Wilcoxon pareado (mesma regra da #105) para uma amostra."""
    d = d[d != 0]
    exigir(len(d) >= 1, 'Todas as diferenças são zero.')
    postos = stats.rankdata(np.abs(d))
    w = postos[d > 0].sum()
    if len(d) > rq105.LIMITE_EXATO:
        return float(stats.wilcoxon(d, method='approx').pvalue)
    dobrados = np.rint(postos * 2).astype(int)
    c = np.zeros(int(dobrados.sum()) + 1)
    c[0] = 1.0
    for r in dobrados:
        c[r:] += c[:-r].copy()
    c /= c.sum()
    k = int(round(w * 2))
    return float(min(1.0, 2 * min(c[:k + 1].sum(), c[k:].sum())))


def p_wilcoxon_lote(d):
    return np.array([p_wilcoxon(linha) for linha in np.atleast_2d(d)])


# ------------------------------------------------------------- cenários

def diferencas_reais(parametros):
    return np.concatenate([e['sem'] - e['com'] for e in parametros['estratos']])


def com_n(parametros, por_estrato):
    p = copy.deepcopy(parametros)
    for e in p['estratos']:
        e['quantidade'] = por_estrato
    p['n'] = por_estrato * len(p['estratos'])
    return p


def amostras_h0(cenario, parametros, rng, repeticoes):
    """Devolve (d sob H0 com forma (repeticoes, n), σ_d populacional do cenário)."""
    exigir(cenario in CENARIOS, f'Cenário desconhecido: {cenario}')
    d_real = diferencas_reais(parametros)
    centro = d_real.mean()
    sigma = float(d_real.std())  # populacional: a distribuição empírica é a "população"
    p = com_n(parametros, 5) if cenario == 'amostra_pequena' else parametros
    d = rq104.gerar_lote(p, rng, repeticoes, 'observado')['diferenca'] - centro
    if cenario == 'assimetria':
        return d, sigma
    d = d * rng.choice((-1.0, 1.0), size=d.shape)
    if cenario == 'outliers':
        d = np.where(rng.random(d.shape) < PROB_OUTLIER, d * FATOR_OUTLIER, d)
        sigma *= math.sqrt((1 - PROB_OUTLIER) + PROB_OUTLIER * FATOR_OUTLIER ** 2)
    return d, sigma


def ic_binomial(k, n):
    ic = stats.binomtest(int(k), int(n)).proportion_ci(method='exact')
    return [float(ic.low), float(ic.high)]


def simular_cenario(cenario, parametros, repeticoes=REPETICOES, semente=SEMENTE,
                    efeitos=EFEITOS_DZ, alfas=ALFAS):
    exigir(cenario in CENARIOS, f'Cenário desconhecido: {cenario}')
    exigir(type(repeticoes) is int and repeticoes > 0, 'Repetições devem ser um inteiro positivo.')
    # Uma semente derivada por cenário: rodar um cenário isolado reproduz o mesmo resultado.
    rng = np.random.default_rng([semente, list(CENARIOS).index(cenario)])
    base, sigma = amostras_h0(cenario, parametros, rng, repeticoes)
    pontos = []
    for dz in efeitos:
        delta = dz * sigma
        d = base + delta
        ps = {'t_pareado': p_t_pareado(d), 'wilcoxon_pareado': p_wilcoxon_lote(d)}
        ponto = dict(efeito_dz=dz, delta_ms=delta, testes={})
        for teste, p in ps.items():
            exigir(np.all(np.isfinite(p)) and np.all((p >= 0) & (p <= 1)), 'p-valor inválido.')
            ponto['testes'][teste] = {}
            for alfa in alfas:
                k = int((p < alfa).sum())
                ponto['testes'][teste][f'{alfa:g}'] = dict(rejeicoes=k, proporcao=k / repeticoes,
                                                          ic95=ic_binomial(k, repeticoes))
        pontos.append(ponto)
    return dict(cenario=cenario, **CENARIOS[cenario], n_pares=int(base.shape[1]), sigma_d_ms=sigma,
                assimetria_d_h0=float(stats.skew(base.ravel())), pontos=pontos)


def tamanho_para_poder(curva, alvo=0.8):
    """Menor d_z da grade com poder ≥ alvo, por interpolação linear (None se não alcança)."""
    for (x0, y0), (x1, y1) in zip(curva, curva[1:]):
        if y0 < alvo <= y1:
            return x0 + (alvo - y0) * (x1 - x0) / (y1 - y0)
    return None


NOMES = {'t_pareado': 't pareado', 'wilcoxon_pareado': 'Wilcoxon'}


def classificar_tipo_i(ic, alfa=0.05):
    """Pelo IC 95% Monte Carlo: 'liberal' se fica todo acima de α, 'conservador' se abaixo."""
    return 'liberal' if ic[0] > alfa else 'conservador' if ic[1] < alfa else 'perto do nominal'


def resumir(cenarios, alfa='0.05'):
    """Diagnósticos para o texto do G4 e da conclusão."""
    resumo = {}
    for nome, c in cenarios.items():
        curvas = {t: [(p['efeito_dz'], p['testes'][t][alfa]['proporcao']) for p in c['pontos']] for t in TESTES}
        dif = [(p['efeito_dz'], p['testes']['t_pareado'][alfa]['proporcao'] -
                p['testes']['wilcoxon_pareado'][alfa]['proporcao']) for p in c['pontos'] if p['efeito_dz'] > 0]
        maior = max(dif, key=lambda x: abs(x[1]))
        zero = c['pontos'][0]['testes']
        resumo[nome] = dict(
            erro_tipo_i={t: curvas[t][0][1] for t in TESTES},
            calibracao={t: classificar_tipo_i(zero[t][alfa]['ic95'], float(alfa)) for t in TESTES},
            dz_para_80={t: tamanho_para_poder(curvas[t]) for t in TESTES},
            maior_diferenca=dict(efeito_dz=maior[0], t_menos_wilcoxon=maior[1]),
            mais_poderoso=('empate' if abs(maior[1]) < 0.03 else
                           't_pareado' if sum(x[1] for x in dif) > 0 else 'wilcoxon_pareado'))
    return resumo


def br(x, casas=1):
    return f'{x:.{casas}f}'.replace('.', ',')


def leitura(c, r):
    """Duas frases por cenário, só a partir dos números (usadas no relatório e no G4)."""
    tipo = '; '.join(f"{NOMES[t]} {br(100 * r['erro_tipo_i'][t])}% ({r['calibracao'][t]})" for t in TESTES)
    m = r['maior_diferenca']
    if r['mais_poderoso'] == 'empate':
        poder = (f"O poder dos dois é praticamente igual (diferença máxima de {br(100 * abs(m['t_menos_wilcoxon']))} p.p.)")
    else:
        lider = NOMES[r['mais_poderoso']]
        poder = (f"O {lider} detecta melhor o efeito, com vantagem de até {br(100 * abs(m['t_menos_wilcoxon']))} p.p. "
                 f"em d_z = {br(m['efeito_dz'])}")
    dz80 = r['dz_para_80']
    if all(v is not None for v in dz80.values()):
        poder += (f"; 80% de poder exige d_z ≈ {br(dz80['t_pareado'], 2)} no t e ≈ {br(dz80['wilcoxon_pareado'], 2)} "
                  'no Wilcoxon')
    elif any(v is not None for v in dz80.values()):
        quem = next(NOMES[t] for t, v in dz80.items() if v is not None)
        poder += f'; só o {quem} chega a 80% de poder dentro da grade'
    else:
        poder += '; nenhum chega a 80% de poder dentro da grade (d_z ≤ 1)'
    return f"Erro tipo I em d_z = 0: {tipo}. {poder}."


def relatorio(m):
    pct = lambda v: f'{100 * v:.1f}%'
    linhas = ['# RQ113 — Q2 e Q3: poder dos testes pareados', '',
              f"{m['repeticoes']:,} amostras por cenário e por efeito; semente {m['semente']}; testes bilaterais. "
              'Poder = proporção de amostras com p < α. Em d_z = 0 a proporção é o erro tipo I do cenário.', '',
              'Efeito: δ = d_z × σ_d somado a cada diferença d = t_sem − t_com (δ > 0: cache mais rápido).', '']
    for nome, c in m['cenarios'].items():
        r = m['resumo'][nome]
        linhas += [f"## {c['rotulo']} ({c['questao']})", '',
                   f"{c['violacao'].capitalize()}. n = {c['n_pares']}; σ_d = {c['sigma_d_ms']:.3f} ms; "
                   f"assimetria de d sob H0 = {c['assimetria_d_h0']:.2f}.", '',
                   '| d_z | δ (ms) | t pareado α=0,05 | Wilcoxon α=0,05 | t pareado α=0,01 | Wilcoxon α=0,01 |',
                   '| ---: | ---: | ---: | ---: | ---: | ---: |']
        for p in c['pontos']:
            t, w = p['testes']['t_pareado'], p['testes']['wilcoxon_pareado']
            linhas.append(f"| {p['efeito_dz']:.1f} | {p['delta_ms']:.3f} | {pct(t['0.05']['proporcao'])} | "
                          f"{pct(w['0.05']['proporcao'])} | {pct(t['0.01']['proporcao'])} | {pct(w['0.01']['proporcao'])} |")
        dz80 = {k: (f'{v:.2f}' if v is not None else 'não alcança na grade') for k, v in r['dz_para_80'].items()}
        linhas += ['', f"Erro tipo I (d_z = 0): t {pct(r['erro_tipo_i']['t_pareado'])}, Wilcoxon "
                   f"{pct(r['erro_tipo_i']['wilcoxon_pareado'])}. d_z para 80% de poder: t {dz80['t_pareado']}, "
                   f"Wilcoxon {dz80['wilcoxon_pareado']}. Maior diferença de poder (t − Wilcoxon): "
                   f"{100 * r['maior_diferenca']['t_menos_wilcoxon']:+.1f} p.p. em d_z = {r['maior_diferenca']['efeito_dz']:.1f}.", '']
    linhas += ['## Leitura', '',
               'A seção abaixo é gerada a partir dos números acima (ver `resumo` em `resultados.json`).', '']
    for nome, c in m['cenarios'].items():
        linhas.append(f"- **{c['rotulo']}**: {m['leituras'][nome]}")
    linhas += ['',
               'Limitações: as amostras reamostram os 30 pares reais (não criam valores novos fora dos fatores '
               'definidos), não reproduzem a tendência temporal da coleta e as proporções têm erro Monte Carlo '
               '(IC 95% em `resultados.json`, ±1 p.p. no pior caso).', '']
    return '\n'.join(linhas)


def executar(saida=SAIDA, repeticoes=REPETICOES, semente=SEMENTE, cenarios=tuple(CENARIOS)):
    inicio = time.perf_counter()
    parametros = rq104.carregar_parametros()
    resultado = {c: simular_cenario(c, parametros, repeticoes, semente) for c in cenarios}
    m = dict(schema_version=1, questoes=['Q2', 'Q3'], repeticoes=repeticoes, semente=semente,
             efeitos_dz=list(EFEITOS_DZ), alfas=list(ALFAS), alternativa='bilateral', criterio='p < alfa',
             outliers=dict(fator=FATOR_OUTLIER, probabilidade=PROB_OUTLIER),
             parametros_sha256=parametros['sha256'], origem_execucao_id=parametros['origem']['execucao_id'],
             versoes=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__),
             cenarios=resultado, resumo=resumir(resultado))
    m['leituras'] = {c: leitura(resultado[c], m['resumo'][c]) for c in resultado}
    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    (saida / 'resultados.json').write_text(json.dumps(m, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
                                           encoding='utf-8')
    with (saida / 'poder.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['cenario', 'n_pares', 'efeito_dz', 'delta_ms', 'teste', 'alfa', 'rejeicoes', 'repeticoes',
                    'proporcao_rejeicoes', 'ic95_inferior', 'ic95_superior'])
        for c in resultado.values():
            for p in c['pontos']:
                for teste, por_alfa in p['testes'].items():
                    for alfa, r in por_alfa.items():
                        w.writerow([c['cenario'], c['n_pares'], p['efeito_dz'], f"{p['delta_ms']:.6f}", teste, alfa,
                                    r['rejeicoes'], repeticoes, r['proporcao'], f"{r['ic95'][0]:.6f}", f"{r['ic95'][1]:.6f}"])
    (saida / 'RELATORIO.md').write_text(relatorio(m), encoding='utf-8')
    m['duracao_s'] = time.perf_counter() - inicio
    return m


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--saida', type=Path, default=SAIDA)
    parser.add_argument('--repeticoes', type=int, default=REPETICOES)
    parser.add_argument('--semente', type=int, default=SEMENTE)
    args = parser.parse_args()
    try:
        m = executar(args.saida, args.repeticoes, args.semente)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f'Simulação não concluída: {exc}\n')
    for nome, r in m['resumo'].items():
        print(f"RQ113 [{nome}]: tipo I t={r['erro_tipo_i']['t_pareado']:.3f} "
              f"W={r['erro_tipo_i']['wilcoxon_pareado']:.3f}; d_z p/ 80%: {r['dz_para_80']}")
    print(f"{m['duracao_s']:.0f} s -> {args.saida}")


if __name__ == '__main__':
    main()
