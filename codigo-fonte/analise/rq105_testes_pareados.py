"""RQ105: teste t pareado e Wilcoxon pareado (signed-rank), com interpretação.

Convenção da #101: d = t_sem - t_com (d > 0 significa que o cache foi mais rápido).
Os dois testes são bilaterais com alfa = 0,05.

* t pareado: H0 mu_d = 0. Estatística t = media(d) / (s_d / sqrt(n)), com n - 1 gl.
  Tamanho do efeito: d de Cohen para pares (d_z = media(d) / s_d) e IC 95% da média.
* Wilcoxon pareado: H0 a distribuição de d é simétrica em torno de 0. Descarta
  diferenças nulas (zero_method='wilcox'), ordena |d| (postos médios em empates) e
  usa W+ = soma dos postos das diferenças positivas. O p-valor é exato, pela
  distribuição de permutação dos sinais condicionada aos postos observados (vale
  também com empates); acima de 50 pares usa a aproximação normal com correção
  de empates. Tamanho do efeito: correlação rank-biserial pareada
  r = (W+ - W-) / (W+ + W-) e estimador de Hodges-Lehmann (mediana das médias de Walsh).

Aplica os dois testes às duas amostras simuladas da RQ104 e aos 30 pares reais da RQ102:

    python codigo-fonte/analise/rq105_testes_pareados.py
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analise import rq103_parametros_cache as rq103  # noqa: E402
from analise import rq104_gerador_simulacao as rq104  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
ENTRADA_RQ104 = RAIZ / 'entregas/experimento-cache/RQ104'
SAIDA = RAIZ / 'entregas/experimento-cache/RQ105'
ALFA = 0.05
LIMITE_EXATO = 50


def exigir(condicao, mensagem):
    if not condicao:
        raise ValueError(mensagem)


def diferencas(sem, com):
    sem, com = np.asarray(sem, dtype=float), np.asarray(com, dtype=float)
    exigir(sem.shape == com.shape and sem.ndim == 1, 'As duas séries devem ter o mesmo tamanho.')
    exigir(len(sem) >= 3, 'São necessários pelo menos 3 pares.')
    exigir(np.all(np.isfinite(sem)) and np.all(np.isfinite(com)), 'Tempos não finitos.')
    return sem - com


# ---------------------------------------------------------------- t pareado

def teste_t_pareado(sem, com, alfa=ALFA):
    d = diferencas(sem, com)
    n = len(d)
    gl = n - 1
    media, dp = float(d.mean()), float(d.std(ddof=1))
    exigir(dp > 0, 'Desvio padrão das diferenças é zero; o t pareado não está definido.')
    r = stats.ttest_rel(sem, com)
    ep = dp / math.sqrt(n)
    critico = float(stats.t.ppf(1 - alfa / 2, gl))
    t95 = float(stats.t.ppf(.975, gl))
    shapiro = stats.shapiro(d)
    return dict(
        teste='t pareado', compara='média das diferenças pareadas', h0='μd = 0', h1='μd ≠ 0',
        n=n, graus_liberdade=gl, estatistica=float(r.statistic), estatistica_nome='t', p_valor=float(r.pvalue),
        valor_critico=critico, regiao_rejeicao=f'|t| > {critico:.4f}', alfa=alfa,
        rejeita_h0=bool(r.pvalue < alfa),
        media_diferenca_ms=media, desvio_padrao_diferenca_ms=dp, erro_padrao_ms=ep,
        ic95_media_ms=[media - t95 * ep, media + t95 * ep],
        efeito_d_cohen_dz=media / dp, magnitude=magnitude_cohen(media / dp),
        pressupostos=dict(shapiro_w=float(shapiro.statistic), shapiro_p=float(shapiro.pvalue),
                          normalidade_rejeitada=bool(shapiro.pvalue < alfa),
                          assimetria=float(stats.skew(d, bias=False))))


def magnitude_cohen(dz):
    a = abs(dz)
    return 'desprezível' if a < .2 else 'pequeno' if a < .5 else 'médio' if a < .8 else 'grande'


# ---------------------------------------------------------------- Wilcoxon

def postos_wilcoxon(d):
    """Remove zeros e devolve (diferenças não nulas, postos médios de |d|)."""
    d = np.asarray(d, dtype=float)
    d = d[d != 0]
    return d, stats.rankdata(np.abs(d))


def distribuicao_nula_wplus(postos):
    """Distribuição exata de W+ sob H0, condicionada aos postos (aceita postos médios).

    Sob H0 cada sinal é + ou - com probabilidade 1/2, independente dos demais, então
    W+ = soma(s_i * r_i) com s_i ~ Bernoulli(1/2). Os postos médios são múltiplos de
    1/2, então a convolução é feita com postos dobrados (inteiros).
    Devolve (valores de W+, probabilidades).
    """
    dobrados = np.rint(np.asarray(postos) * 2).astype(int)
    exigir(np.allclose(dobrados, np.asarray(postos) * 2), 'Postos devem ser múltiplos de 1/2.')
    contagem = np.zeros(int(dobrados.sum()) + 1)
    contagem[0] = 1.0
    for r in dobrados:
        contagem[r:] = contagem[r:] + contagem[:len(contagem) - r].copy()
    prob = contagem / contagem.sum()
    suporte = np.flatnonzero(prob > 0)
    return suporte / 2.0, prob[suporte]


def regiao_rejeicao_wplus(valores, prob, alfa=ALFA):
    """Limites (inferior, superior) de W+: rejeita se W+ <= inferior ou W+ >= superior.

    Cada cauda tem probabilidade <= alfa/2 (a distribuição é discreta e simétrica,
    por isso o nível real fica um pouco abaixo de alfa). None se uma cauda não existe.
    """
    acum = np.cumsum(prob)
    dentro = np.flatnonzero(acum <= alfa / 2 + 1e-12)
    if not len(dentro):
        return None, None, 0.0
    inferior = float(valores[dentro[-1]])
    superior = float(valores.max() + valores.min() - inferior)
    nivel = float(prob[valores <= inferior].sum() + prob[valores >= superior].sum())
    return inferior, superior, nivel


def p_valor_exato_wplus(w, valores, prob):
    abaixo = prob[valores <= w + 1e-9].sum()
    acima = prob[valores >= w - 1e-9].sum()
    return float(min(1.0, 2 * min(abaixo, acima)))


def hodges_lehmann(d):
    d = np.asarray(d, dtype=float)
    i, j = np.triu_indices(len(d))
    return float(np.median((d[i] + d[j]) / 2))


def teste_wilcoxon_pareado(sem, com, alfa=ALFA):
    d_total = diferencas(sem, com)
    d, postos = postos_wilcoxon(d_total)
    n = len(d)
    exigir(n >= 1, 'Todas as diferenças são zero; o Wilcoxon não está definido.')
    w_mais = float(postos[d > 0].sum())
    w_menos = float(postos[d < 0].sum())
    total = n * (n + 1) / 2
    empates = bool(len(np.unique(np.abs(d))) < n)
    if n <= LIMITE_EXATO:
        valores, prob = distribuicao_nula_wplus(postos)
        p = p_valor_exato_wplus(w_mais, valores, prob)
        inferior, superior, nivel = regiao_rejeicao_wplus(valores, prob, alfa)
        metodo = 'exato (permutação dos sinais' + (', postos médios)' if empates else ')')
        z = None
    else:
        r = stats.wilcoxon(d, method='approx', zero_method='wilcox')
        p, z = float(r.pvalue), float(getattr(r, 'zstatistic', np.nan))
        _, cont = np.unique(np.abs(d), return_counts=True)
        dp = math.sqrt(n * (n + 1) * (2 * n + 1) / 24 - (cont ** 3 - cont).sum() / 48)
        c = stats.norm.ppf(alfa / 2) * dp
        inferior, superior, nivel = total / 2 + c, total / 2 - c, alfa
        metodo = 'aproximação normal com correção de empates'
    rb = (w_mais - w_menos) / total
    return dict(
        teste='Wilcoxon pareado', compara='postos dos |d| com sinal (simetria de d em torno de 0)',
        h0='distribuição de d simétrica em torno de 0', h1='distribuição de d deslocada de 0',
        n=len(d_total), n_efetivo=n, zeros_descartados=int(len(d_total) - n), empates_em_abs_d=empates,
        estatistica=w_mais, estatistica_nome='W+', w_menos=w_menos, w_scipy_min=min(w_mais, w_menos),
        w_mais_esperado_h0=total / 2, z=z, p_valor=p, metodo=metodo, alfa=alfa,
        regiao_rejeicao=(f'W+ ≤ {inferior:g} ou W+ ≥ {superior:g}' if inferior is not None
                         else 'nenhuma (amostra pequena demais para rejeitar a este alfa)'),
        limites_rejeicao=[inferior, superior], nivel_real=nivel, rejeita_h0=bool(p < alfa),
        mediana_diferenca_ms=float(np.median(d_total)), hodges_lehmann_ms=hodges_lehmann(d_total),
        efeito_rank_biserial=rb, magnitude=magnitude_rank_biserial(rb))


def magnitude_rank_biserial(r):
    a = abs(r)
    return 'desprezível' if a < .1 else 'pequeno' if a < .3 else 'médio' if a < .5 else 'grande'


# ---------------------------------------------------------------- interpretação

def fmt_p(p):
    return f'{p:.3g}' if p >= 1e-4 else f'{p:.2e}'


def interpretar(t, w, sem, com):
    """Texto curto em português: decisão, direção, magnitude, concordância e ressalvas."""
    sem, com = np.asarray(sem, float), np.asarray(com, float)
    alfa = t['alfa']
    frases = []
    for r, efeito in ((t, f"d de Cohen d_z = {t['efeito_d_cohen_dz']:.2f} ({t['magnitude']})"),
                      (w, f"rank-biserial r = {w['efeito_rank_biserial']:.2f} ({w['magnitude']})")):
        decisao = 'rejeita H0' if r['rejeita_h0'] else 'não rejeita H0'
        frases.append(f"{r['teste']}: {r['estatistica_nome']} = "
                      f"{r['estatistica']:.4g}, p = {fmt_p(r['p_valor'])} → {decisao} a α = {alfa:g}; {efeito}.")
    if t['rejeita_h0'] or w['rejeita_h0']:
        direcao = 'mais rápida com cache' if t['media_diferenca_ms'] > 0 else 'mais lenta com cache'
        frases.append(f"Direção: a operação foi {direcao}. Diferença média {t['media_diferenca_ms']:.4g} ms "
                      f"(IC 95% {t['ic95_media_ms'][0]:.4g} a {t['ic95_media_ms'][1]:.4g} ms); "
                      f"estimador de Hodges-Lehmann {w['hodges_lehmann_ms']:.4g} ms.")
    if t['rejeita_h0'] == w['rejeita_h0']:
        frases.append('Os dois testes chegam à mesma conclusão.')
    else:
        frases.append('Os testes discordam: ' + ('só o t pareado' if t['rejeita_h0'] else 'só o Wilcoxon') +
                      ' rejeita H0. Isso costuma indicar diferenças assimétricas ou com valores extremos, '
                      'em que média e postos contam histórias diferentes.')
    pz = t['pressupostos']
    if pz['normalidade_rejeitada']:
        frases.append(f"Pressuposto: Shapiro-Wilk rejeita a normalidade das diferenças (p = {fmt_p(pz['shapiro_p'])}, "
                      f"assimetria {pz['assimetria']:.2f}); o p-valor do t depende da aproximação pelo TLC.")
    else:
        frases.append(f"Pressuposto: Shapiro-Wilk não rejeita a normalidade das diferenças (p = {fmt_p(pz['shapiro_p'])}).")
    if (t['rejeita_h0'] or w['rejeita_h0']) and com.mean() > 0 and sem.mean() > 0:
        frases.append(f"Importância prática: tempo médio {sem.mean():.4g} ms sem cache e {com.mean():.4g} ms com cache "
                      f"(razão {sem.mean() / com.mean():.3g}×). Significância estatística não é, sozinha, relevância prática.")
    return frases


def aplicar(sem, com, alfa=ALFA, rotulo=''):
    t = teste_t_pareado(sem, com, alfa)
    w = teste_wilcoxon_pareado(sem, com, alfa)
    return dict(amostra=rotulo, n_pares=len(sem), t_pareado=t, wilcoxon_pareado=w,
                interpretacao=interpretar(t, w, sem, com))


def amostras(entrada_rq104=ENTRADA_RQ104, coleta=rq103.COLETA):
    entrada_rq104 = Path(entrada_rq104)
    if not (entrada_rq104 / 'amostra_simulada_observado.csv').exists():
        rq104.executar(saida=entrada_rq104)
    _, reais = rq103.carregar(coleta)
    return {
        'simulada_observado': ('Simulada (RQ104), cenário observado', *rq104.ler_amostra(entrada_rq104 / 'amostra_simulada_observado.csv')),
        'simulada_h0': ('Simulada (RQ104), H0 verdadeira', *rq104.ler_amostra(entrada_rq104 / 'amostra_simulada_h0.csv')),
        'reais': ('Dados reais (RQ102)', np.array([p['sem_cache'] for p in reais]), np.array([p['com_cache'] for p in reais])),
    }


def relatorio(resultados):
    linhas = ['# RQ105 — Teste t pareado e Wilcoxon pareado', '',
              'Convenção: d = t_sem − t_com (ms por operação). Testes bilaterais, α = 0,05. '
              'Gerado por `codigo-fonte/analise/rq105_testes_pareados.py`.', '',
              '| Amostra | Teste | Estatística | p-valor | Tamanho do efeito | Conclusão |',
              '| --- | --- | ---: | ---: | --- | --- |']
    for r in resultados.values():
        t, w = r['t_pareado'], r['wilcoxon_pareado']
        linhas.append(f"| {r['amostra']} | t pareado | t({t['graus_liberdade']}) = {t['estatistica']:.4g} | "
                      f"{fmt_p(t['p_valor'])} | d_z = {t['efeito_d_cohen_dz']:.3g} ({t['magnitude']}) | "
                      f"{'rejeita' if t['rejeita_h0'] else 'não rejeita'} H0 |")
        linhas.append(f"| {r['amostra']} | Wilcoxon pareado | W+ = {w['estatistica']:g} | {fmt_p(w['p_valor'])} | "
                      f"r = {w['efeito_rank_biserial']:.3g} ({w['magnitude']}) | "
                      f"{'rejeita' if w['rejeita_h0'] else 'não rejeita'} H0 |")
    for r in resultados.values():
        linhas += ['', f"## {r['amostra']}", '', *[f'- {f}' for f in r['interpretacao']], '',
                   f"Regiões de rejeição: t pareado {r['t_pareado']['regiao_rejeicao']}; "
                   f"Wilcoxon {r['wilcoxon_pareado']['regiao_rejeicao']} "
                   f"(nível real {r['wilcoxon_pareado']['nivel_real']:.4f}, método {r['wilcoxon_pareado']['metodo']})."]
    linhas += ['', '## Leitura', '',
               'Na amostra simulada do cenário observado e nos dados reais, todas as diferenças são positivas: '
               'W+ atinge o máximo possível e o t é muito grande, então os dois testes rejeitam H0 com folga. '
               'Na amostra gerada com H0 verdadeira (rótulos trocados ao acaso), espera-se não rejeitar H0; '
               'com α = 0,05, uma rejeição aqui seria um erro tipo I, que ocorre em cerca de 5% das amostras '
               '(medido na Sprint 2).', '',
               'Ressalvas: os pares compartilham entrada e ambiente e a coleta mostra tendência temporal (RQ103), '
               'então a independência entre pares é uma suposição. Os dados simulados reamostram pares reais e '
               'não são novas medições.', '']
    return '\n'.join(linhas)


def executar(saida=SAIDA, alfa=ALFA, **kwargs):
    resultados = {k: aplicar(sem, com, alfa, rotulo) for k, (rotulo, sem, com) in amostras(**kwargs).items()}
    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    (saida / 'resultados.json').write_text(json.dumps(resultados, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
                                           encoding='utf-8')
    (saida / 'RELATORIO.md').write_text(relatorio(resultados), encoding='utf-8')
    return resultados


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--saida', type=Path, default=SAIDA)
    parser.add_argument('--alfa', type=float, default=ALFA)
    args = parser.parse_args()
    try:
        resultados = executar(args.saida, args.alfa)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f'Testes não concluídos: {exc}\n')
    for r in resultados.values():
        print(f"\n== {r['amostra']} ==")
        for f in r['interpretacao']:
            print(' -', f)


if __name__ == '__main__':
    main()
