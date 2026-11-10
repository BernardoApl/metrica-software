"""RQ111: gráfico G3 estático e acessível, alimentado pelos resultados da RQ110."""
import argparse
import hashlib
import json
import math
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ENTRADA = RAIZ / 'entregas/experimento-cache/RQ110/resultados.json'
PAGINA = Path(__file__).with_name('index.html')
INICIO, FIM = '<!-- G3:INICIO -->', '<!-- G3:FIM -->'
TESTES = [('t_pareado', 't pareado', '#2a78d6'), ('wilcoxon_pareado', 'Wilcoxon pareado', '#eb6834')]


def carregar(entrada):
    entrada = Path(entrada)
    m = json.loads(entrada.read_text(encoding='utf-8'))
    if m.get('status') != 'concluida' or m.get('cenario') != 'h0' or m.get('questao') != 'Q1' or m.get('alfa') != .05:
        raise ValueError('G3 exige Q1 concluída sob H0 e alfa de 5%.')
    n = m['repeticoes']
    if type(n) is not int or n < 1:
        raise ValueError('Contagem de repetições inválida.')
    for nome, _, _ in TESTES:
        r = m['resultados'][nome]
        taxa, (lo, hi) = r['erro_tipo_i'], r['ic95_clopper_pearson']
        if (r['falhas'] != 0 or r['repeticoes_validas'] != n or
                not all(math.isfinite(v) for v in [taxa, lo, hi]) or
                not 0 <= lo <= taxa <= hi <= 1 or
                not math.isclose(taxa, r['rejeicoes_h0'] / n, abs_tol=1e-12)):
            raise ValueError('Taxa ou intervalo inconsistente.')
    for nome in ('repeticoes.csv', 'parametros_origem.json', 'RELATORIO.md'):
        if hashlib.sha256((entrada.parent / nome).read_bytes()).hexdigest() != m['artefatos_sha256'][nome]:
            raise ValueError(f'Artefato alterado: {nome}')
    return m


def pct(v, casas=2):
    return f'{100*v:.{casas}f}%'.replace('.', ',')


def fragmento(m):
    interpretacao = ' '.join(f'{rotulo}: o IC 95% ' + ('contém' if m['resultados'][nome]['ic95_clopper_pearson'][0] <= .05 <= m['resultados'][nome]['ic95_clopper_pearson'][1] else 'não contém') + ' a referência de 5%.' for nome, rotulo, _ in TESTES)
    teto = max(.08, math.ceil(max(m['resultados'][t]['ic95_clopper_pearson'][1] for t, _, _ in TESTES) * 100 / 2) * .02)
    y = lambda v: 250 - v / teto * 190
    svg = ['<svg class="g3-svg" viewBox="0 0 420 310" role="img" aria-labelledby="g3-svg-titulo g3-svg-desc">',
           '<title id="g3-svg-titulo">Erro Tipo I dos testes pareados</title>',
           '<desc id="g3-svg-desc">Barras partindo de zero, com intervalos de confiança de 95% e referência tracejada de 5%. Valores exatos na tabela abaixo.</desc>']
    for i in range(5):
        v = teto * i / 4
        svg.append(f'<path d="M55 {y(v):.3f} H400" stroke="#d9e1e7"/><text x="46" y="{y(v)+5:.3f}" text-anchor="end">{pct(v, 0)}</text>')
    for (nome, rotulo, cor), x in zip(TESTES, [150, 310]):
        r = m['resultados'][nome]
        taxa, (lo, hi) = r['erro_tipo_i'], r['ic95_clopper_pearson']
        svg += [f'<rect x="{x-30}" y="{y(taxa):.3f}" width="60" height="{250-y(taxa):.3f}" fill="{cor}"/>',
                f'<path d="M{x} {y(lo):.3f} V{y(hi):.3f} M{x-10} {y(lo):.3f} H{x+10} M{x-10} {y(hi):.3f} H{x+10}" stroke="#192b3c" stroke-width="2"/>',
                f'<text x="{x}" y="{y(hi)-12:.3f}" text-anchor="middle" font-weight="700">{pct(taxa)}</text>',
                f'<text x="{x}" y="277" text-anchor="middle">{rotulo}</text>']
    svg += [f'<path d="M55 {y(.05):.3f} H400" stroke="#192b3c" stroke-width="2" stroke-dasharray="6 4"/>', '</svg>']
    linhas = [f'<p>Quando H0 é verdadeira, quantas vezes os testes apontam uma diferença? Cada barra resume {m["repeticoes"]:,} experimentos simulados de {m["n_pares"]} pares, com semente {m["semente"]}.</p>'.replace('10,000', '10.000'),
        '<figure class="g3-figura">', *svg,
        '<figcaption>Linha tracejada: referência de 5%. Hastes: intervalo de confiança de 95% da taxa estimada.</figcaption></figure>',
        '<div class="tabela-rolavel" tabindex="0" role="region" aria-label="Resultados do erro Tipo I"><table>',
        '<caption>G3 — Comparação dos testes sob H0</caption>',
        '<thead><tr><th scope="col">Teste</th><th scope="col">Rejeições / repetições</th><th scope="col">Erro Tipo I</th><th scope="col">IC 95%</th><th scope="col">Diferença de 5%</th></tr></thead><tbody>']
    for nome, rotulo, _ in TESTES:
        r = m['resultados'][nome]
        lo, hi = r['ic95_clopper_pearson']
        desvio = f"{100*(r['erro_tipo_i']-.05):+.2f}".replace('.', ',')
        linhas.append(f'<tr><th scope="row">{rotulo}</th><td>{r["rejeicoes_h0"]} / {m["repeticoes"]}</td><td>{pct(r["erro_tipo_i"])}</td><td>{pct(lo, 4)} a {pct(hi, 4)}</td><td>{desvio} p.p.</td></tr>')
    linhas += ['</tbody></table></div>', '<details class="g3-explicacao"><summary>Como interpretar este gráfico?</summary>',
        '<p>Erro Tipo I é rejeitar H0 quando ela é verdadeira. A referência de 5% é o nível nominal de cada teste; a taxa simulada pode variar. Estar mais perto da linha nesta execução não demonstra que um teste seja sempre melhor.</p>',
        '<p>Os intervalos binomiais exatos quantificam a incerteza Monte Carlo. Não representam a dispersão dos tempos nem o poder estatístico dos testes. As 10.000 simulações não são novas medições reais.</p>',
        f'<p>{interpretacao} A tabela mantém quatro casas decimais para não esconder diferenças pelo arredondamento.</p>',
        '</details>', '<p class="notation">Fonte: simulação Q1 da #110, com H0 construída por trocas aleatórias dos rótulos. Resultados estáticos da execução salva; o gráfico não executa novas simulações.</p>']
    return '\n'.join(linhas)


def executar(entrada=ENTRADA, pagina=PAGINA):
    m = carregar(entrada)
    pagina = Path(pagina)
    html = pagina.read_text(encoding='utf-8')
    if html.count(INICIO) != 1 or html.count(FIM) != 1 or html.index(INICIO) > html.index(FIM):
        raise ValueError('Marcadores G3 ausentes ou inválidos.')
    html = html[:html.index(INICIO)+len(INICIO)] + '\n' + fragmento(m) + '\n' + html[html.index(FIM):]
    pagina.write_text(html, encoding='utf-8')
    return m


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--entrada', type=Path, default=ENTRADA)
    parser.add_argument('--pagina', type=Path, default=PAGINA)
    args = parser.parse_args()
    try:
        executar(args.entrada, args.pagina)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(1, f'G3 não gerado: {exc}\n')
    print('G3 atualizado com os resultados da RQ110.')
