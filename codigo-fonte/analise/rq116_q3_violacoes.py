"""RQ116: Q3 — erro tipo I dos testes pareados quando os pressupostos são violados.

A Q1 (#110) mede o erro tipo I com dados bem comportados. A Q3 pede repetir essa
medição em situações que violam os pressupostos do t pareado. Aqui cada situação gera
10.000 amostras com efeito zero e conta a proporção de p < α em cada teste.

Situações (mesmos geradores da #113, para o G3 e o G4 descreverem os mesmos dados):

* base: diferenças reais centradas e com sinal sorteado; simétricas, sem violação.
* outliers: a base com 10% das diferenças multiplicadas por 5 (cauda pesada).
* assimetria: diferenças reais centradas, sem sortear o sinal (assimetria ≈ 1,9).
  A média é zero, então H0 do t vale; a simetria em zero, H0 do Wilcoxon, não.

Cada situação roda com 10, 20, 30 e 50 pares. Amostra pequena é a base com 10 pares.
A varredura mostra se a violação pesa mais com amostras pequenas ou grandes.

    python codigo-fonte/analise/rq116_q3_violacoes.py   (≈ 1 min; grava entregas/experimento-cache/RQ116)
"""
from __future__ import annotations

import argparse
import csv
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
import scipy
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analise import rq104_gerador_simulacao as rq104  # noqa: E402
from analise import rq113_poder as rq113  # noqa: E402

SAIDA = rq104.RAIZ / 'entregas/experimento-cache/RQ116'
SEMENTE = 116
REPETICOES = 10_000
ALFAS = (0.05, 0.01)
N_PARES = (10, 20, 30, 50)
N_PADRAO = 30
TESTES = rq113.TESTES
SITUACOES = {
    'base': dict(rotulo='Sem violação', violacao='diferenças simétricas em torno de zero',
                 h0_valida={'t_pareado': True, 'wilcoxon_pareado': True}),
    'outliers': dict(rotulo='Outliers (10% × 5)', violacao='cauda pesada: 10% das diferenças 5 vezes maiores',
                     h0_valida={'t_pareado': True, 'wilcoxon_pareado': True}),
    'assimetria': dict(rotulo='Assimetria real', violacao='diferenças assimétricas com média zero',
                       h0_valida={'t_pareado': True, 'wilcoxon_pareado': False}),
}
NOMES = {'t_pareado': 't pareado', 'wilcoxon_pareado': 'Wilcoxon'}


def exigir(condicao, mensagem):
    if not condicao:
        raise ValueError(mensagem)


def simular(situacao, n_pares, parametros, repeticoes=REPETICOES, semente=SEMENTE, alfas=ALFAS):
    """Erro tipo I de uma situação com n pares. Semente derivada: cada ponto se reproduz sozinho."""
    exigir(situacao in SITUACOES, f'Situação desconhecida: {situacao}')
    exigir(n_pares in N_PARES, f'Use um destes tamanhos: {N_PARES}')
    exigir(type(repeticoes) is int and repeticoes > 0, 'Repetições devem ser um inteiro positivo.')
    rng = np.random.default_rng([semente, list(SITUACOES).index(situacao), n_pares])
    p = rq113.com_n(parametros, n_pares // len(parametros['estratos']))
    d, _ = rq113.amostras_h0(situacao, p, rng, repeticoes)
    exigir(d.shape == (repeticoes, n_pares), 'Lote com forma inesperada.')
    ps = {'t_pareado': rq113.p_t_pareado(d), 'wilcoxon_pareado': rq113.p_wilcoxon_lote(d)}
    testes = {}
    for teste, valores in ps.items():
        exigir(np.all(np.isfinite(valores)) and np.all((valores >= 0) & (valores <= 1)), 'p-valor inválido.')
        testes[teste] = {}
        for alfa in alfas:
            k = int((valores < alfa).sum())
            ic = rq113.ic_binomial(k, repeticoes)
            testes[teste][f'{alfa:g}'] = dict(rejeicoes=k, proporcao=k / repeticoes, ic95=ic,
                                              calibracao=rq113.classificar_tipo_i(ic, alfa))
    return dict(situacao=situacao, n_pares=n_pares, repeticoes=repeticoes,
                media_d_h0=float(d.mean()), assimetria_d_h0=float(stats.skew(d.ravel())), testes=testes)


def br(x, casas=1):
    return f'{x:.{casas}f}'.replace('.', ',')


def leitura(situacao, pontos):
    """Frase por situação, gerada dos números: o texto não diverge da tabela."""
    padrao = next(p for p in pontos if p['n_pares'] == N_PADRAO)
    taxas = {t: padrao['testes'][t]['0.05'] for t in TESTES}
    partes = [f"{NOMES[t]} {br(100 * taxas[t]['proporcao'])}% ({taxas[t]['calibracao']})" for t in TESTES]
    frase = f"Com {N_PADRAO} pares: " + '; '.join(partes) + '.'
    extremos = {t: (pontos[0]['testes'][t]['0.05']['proporcao'], pontos[-1]['testes'][t]['0.05']['proporcao'])
                for t in TESTES}
    tendencia = '; '.join(f"{NOMES[t]} vai de {br(100 * a)}% ({pontos[0]['n_pares']} pares) "
                          f"a {br(100 * b)}% ({pontos[-1]['n_pares']} pares)" for t, (a, b) in extremos.items())
    nota = ''
    if not SITUACOES[situacao]['h0_valida']['wilcoxon_pareado']:
        nota = (' A média é zero, mas a distribuição não é simétrica: para a pergunta sobre o tempo médio, as '
                'rejeições do Wilcoxon são falsos positivos, e crescem com a amostra porque ele detecta a assimetria.')
    return f'{frase} Ao variar a amostra, {tendencia}.{nota}'


def relatorio(m):
    linhas = ['# RQ116 — Q3: erro tipo I com violações de pressupostos', '',
              f"{m['repeticoes']:,}".replace(',', '.') + ' amostras por situação e tamanho, com efeito zero; '
              f"semente {m['semente']}; testes bilaterais; decisão p < α.", '',
              'Erro tipo I = proporção de amostras com p < α quando não há efeito na média. O esperado é α.', '']
    for nome, info in SITUACOES.items():
        linhas += [f"## {info['rotulo']}", '', f"Violação: {info['violacao']}.", '',
                   '| Pares | t α=0,05 | Wilcoxon α=0,05 | t α=0,01 | Wilcoxon α=0,01 | Assimetria de d |',
                   '| ---: | ---: | ---: | ---: | ---: | ---: |']
        for p in m['situacoes'][nome]:
            celulas = [f"{br(100 * p['testes'][t][a]['proporcao'], 2)}%" for a in ('0.05', '0.01') for t in TESTES]
            linhas.append(f"| {p['n_pares']} | " + ' | '.join(celulas) + f" | {br(p['assimetria_d_h0'], 2)} |")
        linhas += ['', m['leituras'][nome], '']
    linhas += ['## Limitações', '',
               'As amostras reamostram os 30 pares reais; outliers (10% × 5) e tamanhos são escolhas do grupo para '
               'estressar os testes. A tendência temporal da coleta não é reproduzida. Com 10.000 amostras, o erro '
               'Monte Carlo é de cerca de ±0,4 p.p. perto de 5% (IC 95% Clopper-Pearson em `resultados.json`).', '']
    return '\n'.join(linhas)


def executar(saida=SAIDA, repeticoes=REPETICOES, semente=SEMENTE):
    inicio = time.perf_counter()
    parametros = rq104.carregar_parametros()
    situacoes = {s: [simular(s, n, parametros, repeticoes, semente) for n in N_PARES] for s in SITUACOES}
    m = dict(schema_version=1, questao='Q3', medida='erro_tipo_i', repeticoes=repeticoes, semente=semente,
             alfas=list(ALFAS), n_pares=list(N_PARES), n_padrao=N_PADRAO, alternativa='bilateral',
             criterio='p < alfa', outliers=dict(fator=rq113.FATOR_OUTLIER, probabilidade=rq113.PROB_OUTLIER),
             geradores='rq113_poder.amostras_h0', parametros_sha256=parametros['sha256'],
             origem_execucao_id=parametros['origem']['execucao_id'],
             versoes=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__),
             situacoes_info=SITUACOES, situacoes=situacoes)
    m['leituras'] = {s: leitura(s, pontos) for s, pontos in situacoes.items()}
    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    (saida / 'resultados.json').write_text(json.dumps(m, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
                                           encoding='utf-8')
    with (saida / 'erro_tipo_i.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['situacao', 'n_pares', 'teste', 'alfa', 'rejeicoes', 'repeticoes', 'erro_tipo_i',
                    'ic95_inferior', 'ic95_superior', 'calibracao'])
        for pontos in situacoes.values():
            for p in pontos:
                for teste, por_alfa in p['testes'].items():
                    for alfa, r in por_alfa.items():
                        w.writerow([p['situacao'], p['n_pares'], teste, alfa, r['rejeicoes'], repeticoes,
                                    r['proporcao'], f"{r['ic95'][0]:.6f}", f"{r['ic95'][1]:.6f}", r['calibracao']])
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
    for nome, texto in m['leituras'].items():
        print(f'RQ116 [{nome}]: {texto}')
    print(f"{m['duracao_s']:.0f} s -> {args.saida}")


if __name__ == '__main__':
    main()
