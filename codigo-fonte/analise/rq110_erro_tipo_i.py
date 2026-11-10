"""RQ110: Q1 — 10.000 experimentos sob H0 e erro Tipo I dos testes pareados."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import sys
from pathlib import Path

import numpy as np
import scipy
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analise import rq104_gerador_simulacao as rq104
from analise import rq105_testes_pareados as rq105

SAIDA = rq104.RAIZ / 'entregas/experimento-cache/RQ110'
TESTES = ('t_pareado', 'wilcoxon_pareado')


def exigir(condicao, mensagem):
    if not condicao:
        raise ValueError(mensagem)


def hash_arquivo(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def resumir(linhas, alfa):
    """Não reduz o denominador silenciosamente se houver falhas de cálculo."""
    total = len(linhas)
    exigir(total > 0, 'Nenhuma repetição disponível.')
    resumo = {}
    for teste in TESTES:
        validas = [r for r in linhas if r[f'{teste}_status'] == 'ok']
        rejeicoes = sum(r[f'{teste}_p'] < alfa for r in validas)
        falhas = total - len(validas)
        # A taxa oficial só é emitida quando todos os experimentos são válidos.
        taxa = rejeicoes / total if not falhas else None
        ic = stats.binomtest(rejeicoes, total).proportion_ci(method='exact') if not falhas else None
        resumo[teste] = dict(repeticoes_solicitadas=total, repeticoes_validas=len(validas),
            falhas=falhas, rejeicoes_h0=rejeicoes, erro_tipo_i=taxa,
            erro_padrao_monte_carlo=math.sqrt(taxa * (1 - taxa) / total) if taxa is not None else None,
            ic95_clopper_pearson=[float(ic.low), float(ic.high)] if ic else None,
            alfa_nominal=alfa, desvio_do_nominal=taxa - alfa if taxa is not None else None,
            alfa_no_ic95=bool(ic.low <= alfa <= ic.high) if ic else None)
    return resumo


def simular(parametros, repeticoes=10_000, semente=110, alfa=.05):
    exigir(type(repeticoes) is int and repeticoes > 0, 'Repetições devem ser um inteiro positivo.')
    exigir(type(semente) is int and semente >= 0, 'Semente deve ser um inteiro não negativo.')
    exigir(isinstance(alfa, (int, float)) and not isinstance(alfa, bool) and math.isfinite(alfa) and 0 < alfa < 1,
           'Alfa deve estar entre 0 e 1.')
    exigir(parametros['n'] >= 3, 'Os testes exigem pelo menos três pares.')
    rng = np.random.default_rng(semente)
    # Mesmo lote para os dois testes; sem selecionar amostras pelo resultado.
    lote = rq104.gerar_lote(parametros, rng, repeticoes, cenario='h0')
    linhas = []
    funcoes = (rq105.teste_t_pareado, rq105.teste_wilcoxon_pareado)
    for i in range(repeticoes):
        sem, com = lote['sem'][i], lote['com'][i]
        linha = dict(repeticao=i + 1, n_pares=parametros['n'],
                     rotulos_trocados=int(lote['trocado'][i].sum()),
                     media_diferenca_ms=float(lote['diferenca'][i].mean()))
        for nome, funcao in zip(TESTES, funcoes):
            try:
                resultado = funcao(sem, com, alfa)
                p = float(resultado['p_valor'])
                estatistica = float(resultado['estatistica'])
                exigir(math.isfinite(p) and 0 <= p <= 1 and math.isfinite(estatistica), 'Resultado estatístico inválido.')
                linha.update({f'{nome}_status': 'ok', f'{nome}_estatistica': estatistica,
                              f'{nome}_p': p, f'{nome}_rejeita_h0': p < alfa, f'{nome}_erro': ''})
            except (ValueError, FloatingPointError) as exc:
                linha.update({f'{nome}_status': 'erro', f'{nome}_estatistica': None,
                              f'{nome}_p': None, f'{nome}_rejeita_h0': None, f'{nome}_erro': str(exc)})
        linhas.append(linha)
    return linhas, resumir(linhas, alfa)


def relatorio(m):
    linhas = ['# RQ110 — Q1: erro Tipo I', '',
        f"Foram solicitadas {m['repeticoes']:,} repetições, com {m['n_pares']} pares por amostra, semente {m['semente']} e α = {m['alfa']}. Status: **{m['status']}**.", '',
        'Q1: com H0 verdadeira, com que frequência cada teste rejeita H0?', '',
        '| Teste | Válidas | Rejeições | Erro Tipo I | IC 95% | Erro padrão Monte Carlo |',
        '| --- | ---: | ---: | ---: | --- | ---: |']
    for nome, r in m['resultados'].items():
        if r['erro_tipo_i'] is None:
            linhas.append(f"| {nome} | {r['repeticoes_validas']} | {r['rejeicoes_h0']} | indisponível: houve falhas | — | — |")
        else:
            lo, hi = r['ic95_clopper_pearson']
            linhas.append(f"| {nome} | {r['repeticoes_validas']} | {r['rejeicoes_h0']} | {r['erro_tipo_i']:.2%} | {lo:.2%} a {hi:.2%} | {r['erro_padrao_monte_carlo']:.4%} |")
    linhas += ['', '## Método', '',
        'Cada repetição gera uma nova amostra pelo cenário `h0` da #104: reamostra pares completos nos estratos da #103 e troca os rótulos de cada par independentemente com probabilidade 1/2. Condicionalmente à magnitude, cada diferença tem sinal equiprovável; portanto sua distribuição é simétrica em zero e sua média é zero. H0 vale para ambos os testes neste modelo. Não se reutiliza uma única amostra nem se usa o cenário observado para estimar erro Tipo I.', '',
        'Os dois testes bilaterais da #105 recebem a mesma amostra em cada repetição. A decisão é estritamente `p < alfa`. O Wilcoxon usa distribuição exata dos sinais com postos médios até 50 diferenças não nulas e a aproximação já definida pela #105 acima desse limite. A simulação padrão usa 30 pares.', '',
        'Erro Tipo I = número de rejeições / número total de repetições. Os intervalos são binomiais exatos de Clopper–Pearson; o erro padrão Monte Carlo é sqrt(taxa × (1 − taxa) / repetições). Se houver falhas, elas permanecem no CSV, a execução fica incompleta e a taxa oficial não é calculada. Não há reposição seletiva de experimentos.', '',
        '## Interpretação', '']
    for nome, r in m['resultados'].items():
        if r['erro_tipo_i'] is not None:
            dentro = 'contém' if r['alfa_no_ic95'] else 'não contém'
            linhas.append(f"- {nome}: a taxa estimada difere do nominal em {100 * r['desvio_do_nominal']:+.3f} pontos percentuais; o IC 95% {dentro} α. Isso descreve a calibração neste modelo, sem provar que o nível é exatamente α.")
    linhas += ['', 'O nível nominal não obriga uma realização Monte Carlo a ter exatamente 5% de rejeições. A incerteza dos intervalos refere-se à simulação, condicionada à distribuição empírica de origem; não inclui a incerteza da coleta original. A discretização do Wilcoxon também pode torná-lo conservador.', '',
        '## Escopo e reprodução', '',
        'As 10.000 repetições não são novas medições de desempenho. A simulação não preserva a tendência temporal da coleta real, nem estabelece poder estatístico (erro Tipo II) ou validade universal dos testes. O modelo nulo de troca de rótulos é uma construção artificial apropriada à Q1.', '',
        '`repeticoes.csv` registra estatísticas, p-valores, decisões e erros de ambos os testes. `resultados.json` registra a configuração, versões e hashes. `parametros_origem.json` preserva o contrato da #103. Reproduza com a mesma semente, parâmetros, quantidade de repetições, código e versões; alterar o tamanho do lote muda a sequência de sorteios da #104.', '',
        'Referência do intervalo: [SciPy — proportion_ci](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats._result_classes.BinomTestResult.proportion_ci.html).', '']
    return '\n'.join(linhas)


def executar(parametros_json=rq104.PARAMETROS, saida=SAIDA, repeticoes=10_000, semente=110, alfa=.05):
    saida = Path(saida)
    exigir(not saida.exists() or not any(saida.iterdir()), 'Pasta de saída não vazia; escolha outra para preservar a execução anterior.')
    conteudo = Path(parametros_json).read_bytes()
    parametros = rq104.carregar_parametros(parametros_json)
    linhas, resultados = simular(parametros, repeticoes, semente, alfa)
    exigir(hash_arquivo(parametros_json) == hashlib.sha256(conteudo).hexdigest() == parametros['sha256'],
           'Parâmetros alterados durante a execução.')
    m = dict(schema_version=1, questao='Q1', cenario='h0',
        status='concluida' if all(r['falhas'] == 0 for r in resultados.values()) else 'concluida_com_erros',
        repeticoes=repeticoes, n_pares=parametros['n'], semente=semente, alfa=alfa,
        alternativa='bilateral', criterio_rejeicao='p < alfa', gerador='numpy.random.default_rng / PCG64',
        parametros_sha256=parametros['sha256'], origem=parametros['origem'],
        versoes=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__),
        codigo_sha256={Path(p).name: hash_arquivo(p) for p in (__file__, rq104.__file__, rq105.__file__)},
        resultados=resultados)
    saida.mkdir(parents=True, exist_ok=True)
    (saida / 'parametros_origem.json').write_bytes(conteudo)
    with (saida / 'repeticoes.csv').open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)
    (saida / 'RELATORIO.md').write_text(relatorio(m), encoding='utf-8')
    m['artefatos_sha256'] = {nome: hash_arquivo(saida / nome) for nome in
                            ('repeticoes.csv', 'parametros_origem.json', 'RELATORIO.md')}
    (saida / 'resultados.json').write_text(json.dumps(m, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    return m


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parametros', type=Path, default=rq104.PARAMETROS)
    parser.add_argument('--saida', type=Path, default=SAIDA)
    parser.add_argument('--repeticoes', type=int, default=10_000)
    parser.add_argument('--semente', type=int, default=110)
    parser.add_argument('--alfa', type=float, default=.05)
    args = parser.parse_args()
    try:
        m = executar(args.parametros, args.saida, args.repeticoes, args.semente, args.alfa)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(1, f'Simulação não concluída: {exc}\n')
    print(json.dumps(m['resultados'], ensure_ascii=True, indent=2))
    return 0 if m['status'] == 'concluida' else 1


if __name__ == '__main__':
    raise SystemExit(main())
