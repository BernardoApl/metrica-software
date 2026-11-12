"""RQ117: completa o G3 com o erro tipo I de cada situação simulada (Q1 e Q3).

O bloco da #111 detalha a Q1. Este bloco põe a Q1 (#110) ao lado das situações da Q3
(#116) no mesmo gráfico, com a linha de 5%, e mostra como o erro tipo I muda com o
número de pares. Lê só resultados salvos; não roda simulações.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # permite executar como script

from analise.rq113_poder import classificar_tipo_i  # noqa: E402
from frontend import rq111_g3 as rq111  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
ENTRADA_Q3 = RAIZ / 'entregas/experimento-cache/RQ116/resultados.json'
PAGINA = Path(__file__).with_name('index.html')
INICIO, FIM = '<!-- G3Q3:INICIO (gerado por rq117_g3_q3.py) -->', '<!-- G3Q3:FIM -->'
# Mesmas cores dos testes no G2, G3 e G4.
TESTES = [('t_pareado', 't pareado', '#2a78d6'), ('wilcoxon_pareado', 'Wilcoxon pareado', '#eb6834')]
ALFA = '0.05'


def carregar_q3(entrada=ENTRADA_Q3):
    m = json.loads(Path(entrada).read_text(encoding='utf-8'))
    if m.get('questao') != 'Q3' or m.get('medida') != 'erro_tipo_i' or ALFA not in {f'{a:g}' for a in m['alfas']}:
        raise ValueError('O G3 exige o erro tipo I da Q3 (#116) com α = 0,05.')
    for nome in ('base', 'outliers', 'assimetria'):
        tamanhos = [p['n_pares'] for p in m['situacoes'][nome]]
        if tamanhos != sorted(tamanhos) or 10 not in tamanhos or m['n_padrao'] not in tamanhos:
            raise ValueError(f'Tamanhos de amostra inesperados em {nome}.')
        for p in m['situacoes'][nome]:
            for teste, _, _ in TESTES:
                r = p['testes'][teste][ALFA]
                if r['rejeicoes'] / m['repeticoes'] != r['proporcao'] or not r['ic95'][0] <= r['proporcao'] <= r['ic95'][1]:
                    raise ValueError(f'Taxa ou intervalo inconsistente em {nome}, {p["n_pares"]} pares.')
    return m


def ponto(m, situacao, n):
    return next(p for p in m['situacoes'][situacao] if p['n_pares'] == n)


def taxa(m, situacao, n, teste):
    return ponto(m, situacao, n)['testes'][teste][ALFA]


def situacoes(q1, q3):
    """Grupos do gráfico principal: a Q1 e as situações da Q3, na ordem em que o texto as cita."""
    n = q3['n_padrao']
    grupos = [dict(rotulo=['Q1 · troca de rótulos', f"{q1['n_pares']} pares"], fonte='#110',
                   testes={t: dict(proporcao=q1['resultados'][t]['erro_tipo_i'],
                                   ic95=q1['resultados'][t]['ic95_clopper_pearson'],
                                   rejeicoes=q1['resultados'][t]['rejeicoes_h0'],
                                   calibracao=classificar_tipo_i(q1['resultados'][t]['ic95_clopper_pearson']))
                           for t, _, _ in TESTES})]
    for nome, rotulo, pares in (('base', 'Q3 · amostra pequena', 10), ('outliers', 'Q3 · outliers 10% × 5', n),
                                ('assimetria', 'Q3 · assimetria', n)):
        grupos.append(dict(rotulo=[rotulo, f'{pares} pares'], fonte='#116',
                           testes={t: taxa(q3, nome, pares, t) for t, _, _ in TESTES}))
    return grupos


def pct(v, casas=1):
    return rq111.pct(v, casas)


def teto_de(valores, passo=.05):
    return max(.1, passo * -(-max(valores) // passo))


def grafico_situacoes(grupos):
    largura, altura, esq, dir, topo, base = 640, 300, 56, 12, 20, 236
    teto = teto_de([g['testes'][t]['ic95'][1] for g in grupos for t, _, _ in TESTES])
    y = lambda v: base - v / teto * (base - topo)
    passo_x = (largura - esq - dir) / len(grupos)
    svg = [f'<svg class="g3q3-svg" viewBox="0 0 {largura} {altura}" role="img" aria-labelledby="g3q3-a-t g3q3-a-d">',
           '<title id="g3q3-a-t">Erro tipo I dos dois testes em cada situação simulada</title>',
           '<desc id="g3q3-a-d">Barras agrupadas por situação, com intervalo de confiança de 95% e linha de referência '
           'em 5%. Valores exatos na tabela abaixo do gráfico.</desc>']
    passo_y = .05 if teto > .15 else .02
    v = 0.0
    while v <= teto + 1e-9:
        svg.append(f'<path d="M{esq} {y(v):.1f} H{largura - dir}" class="g4-grade"/>'
                   f'<text x="{esq - 6}" y="{y(v) + 4:.1f}" text-anchor="end">{pct(v, 0)}</text>')
        v += passo_y
    # Referência antes das barras: os rótulos de valor ficam por cima da linha tracejada.
    svg += [f'<path d="M{esq} {y(.05):.1f} H{largura - dir}" class="g3q3-ref"/>',
            f'<text x="{largura - dir}" y="{y(.05) - 5:.1f}" text-anchor="end" class="g3q3-ref-rotulo">5% (α)</text>']
    for i, g in enumerate(grupos):
        centro = esq + passo_x * (i + .5)
        for j, (teste, rotulo, cor) in enumerate(TESTES):
            r = g['testes'][teste]
            x = centro + (j - 1) * 30 + 2
            lo, hi = r['ic95']
            dica = (f"{rotulo}, {' · '.join(g['rotulo'])}: {pct(r['proporcao'], 2)} das amostras sem efeito "
                    f"rejeitaram H0 (IC 95% {pct(lo, 2)} a {pct(hi, 2)}; {r['calibracao']}). Fonte: {g['fonte']}.")
            svg += [f'<g class="g3q3-barra"><title>{dica}</title>'
                    f'<rect x="{x:.1f}" y="{y(r["proporcao"]):.1f}" width="26" height="{base - y(r["proporcao"]):.1f}" '
                    f'rx="3" fill="{cor}"/>'
                    f'<path d="M{x + 13:.1f} {y(lo):.1f} V{y(hi):.1f}" class="g3q3-ic"/></g>',
                    f'<text x="{x + 13:.1f}" y="{y(hi) - 5:.1f}" text-anchor="middle" class="g3q3-valor">'
                    f'{pct(r["proporcao"])}</text>']
        svg.append(f'<text x="{centro:.1f}" y="{base + 18}" text-anchor="middle" class="g3q3-grupo">{g["rotulo"][0]}'
                   f'<tspan x="{centro:.1f}" dy="14">{g["rotulo"][1]}</tspan></text>')
    svg += [f'<path d="M{esq} {base} H{largura - dir}" class="g4-base"/>',
            f'<text x="14" y="{(topo + base) / 2:.1f}" text-anchor="middle" class="g4-rotulo" '
            f'transform="rotate(-90 14 {(topo + base) / 2:.1f})">Erro tipo I (% de amostras com p &lt; 0,05)</text>',
            f'<text x="{(esq + largura - dir) / 2:.1f}" y="{altura - 4}" text-anchor="middle" class="g4-rotulo">'
            'Situação simulada (sem efeito na média)</text>', '</svg>']
    return '\n'.join(svg)


def grafico_tamanho(m, situacao, rotulo_painel, teto):
    largura, altura, esq, dir, topo, base = 320, 230, 54, 12, 14, 190
    tamanhos = [p['n_pares'] for p in m['situacoes'][situacao]]
    x = lambda n: esq + (n - tamanhos[0]) / (tamanhos[-1] - tamanhos[0]) * (largura - esq - dir)
    y = lambda v: base - v / teto * (base - topo)
    ident = f'g3q3-{situacao}'
    svg = [f'<svg class="g4-svg" viewBox="0 0 {largura} {altura}" role="img" aria-labelledby="{ident}-t {ident}-d">',
           f'<title id="{ident}-t">Erro tipo I por tamanho da amostra: {rotulo_painel}</title>',
           f'<desc id="{ident}-d">' + ' '.join(
               f"{rotulo}: {pct(taxa(m, situacao, tamanhos[0], t)['proporcao'])} com {tamanhos[0]} pares e "
               f"{pct(taxa(m, situacao, tamanhos[-1], t)['proporcao'])} com {tamanhos[-1]} pares."
               for t, rotulo, _ in TESTES) + '</desc>']
    v = 0.0
    while v <= teto + 1e-9:
        svg.append(f'<path d="M{esq} {y(v):.1f} H{largura - dir}" class="g4-grade"/>'
                   f'<text x="{esq - 6}" y="{y(v) + 4:.1f}" text-anchor="end">{pct(v, 0)}</text>')
        v += .1
    svg += [f'<path d="M{esq} {y(.05):.1f} H{largura - dir}" class="g4-ref"/>',
            f'<text x="{esq + 4}" y="{y(.05) - 4:.1f}" class="g4-ref-rotulo">5%</text>']
    svg += [f'<text x="{x(n):.1f}" y="{base + 16}" text-anchor="middle">{n}</text>' for n in tamanhos]
    svg += [f'<path d="M{esq} {base} H{largura - dir}" class="g4-base"/>',
            f'<text x="12" y="{(topo + base) / 2:.1f}" text-anchor="middle" class="g4-rotulo" '
            f'transform="rotate(-90 12 {(topo + base) / 2:.1f})">Erro tipo I (%)</text>',
            f'<text x="{(esq + largura - dir) / 2:.1f}" y="{altura - 6}" text-anchor="middle" class="g4-rotulo">'
            'Pares por amostra (n)</text>']
    for teste, rotulo, cor in TESTES:
        pontos = [(n, taxa(m, situacao, n, teste)) for n in tamanhos]
        svg.append('<polyline points="' + ' '.join(f'{x(n):.1f},{y(r["proporcao"]):.1f}' for n, r in pontos) +
                   f'" class="g4-linha" stroke="{cor}"/>')
        for n, r in pontos:
            lo, hi = r['ic95']
            svg.append(f'<circle cx="{x(n):.1f}" cy="{y(r["proporcao"]):.1f}" r="4" fill="{cor}" class="g4-ponto">'
                       f'<title>{rotulo}, {rotulo_painel}, {n} pares: {pct(r["proporcao"], 2)} '
                       f'(IC 95% {pct(lo, 2)} a {pct(hi, 2)}; {r["calibracao"]}).</title></circle>')
    svg.append('</svg>')
    return '\n'.join(svg)


def texto(m):
    n = m['n_padrao']
    t, w = 't_pareado', 'wilcoxon_pareado'
    v = lambda s, k, teste: pct(taxa(m, s, k, teste)['proporcao'])
    return (f"Cada barra é a proporção de 10.000 amostras sem efeito em que o teste rejeitou H0; o esperado é ficar "
            f"perto da linha de 5%. Com outliers, o t pareado fica conservador ({v('outliers', n, t)} com {n} pares), "
            f"porque os extremos inflam o desvio padrão, enquanto o Wilcoxon se mantém em {v('outliers', n, w)}. "
            f"Na assimetria com média zero, os dois se desviam: o t é liberal com poucos pares ({v('assimetria', 10, t)} "
            f"com 10) e se aproxima de 5% com mais pares ({v('assimetria', 50, t)} com 50), e o Wilcoxon se afasta "
            f"cada vez mais ({v('assimetria', 10, w)} → {v('assimetria', 50, w)}), porque testa a simetria, não a média. "
            f"Com amostra pequena e sem violação, os dois ficam um pouco abaixo de 5% "
            f"({v('base', 10, t)} e {v('base', 10, w)}).")


def tabela(q1, m):
    linhas = []
    q1_celulas = ''.join(f"<td data-label=\"{rotulo}\">{pct(q1['resultados'][t]['erro_tipo_i'], 2)}</td>"
                         for t, rotulo, _ in TESTES)
    linhas.append(f'<tr><th scope="row">Q1 · troca de rótulos (#110)</th><td data-label="Pares">{q1["n_pares"]}</td>'
                  f'{q1_celulas}</tr>')
    rotulos = {'base': 'Sem violação', 'outliers': 'Outliers 10% × 5', 'assimetria': 'Assimetria'}
    for nome, rotulo_s in rotulos.items():
        for p in m['situacoes'][nome]:
            celulas = ''.join(f"<td data-label=\"{rotulo}\">{pct(p['testes'][t][ALFA]['proporcao'], 2)} "
                              f"<small>({p['testes'][t][ALFA]['calibracao']})</small></td>" for t, rotulo, _ in TESTES)
            linhas.append(f'<tr><th scope="row">Q3 · {rotulo_s}</th><td data-label="Pares">{p["n_pares"]}</td>{celulas}</tr>')
    return '\n'.join(linhas)


def fragmento(q1, m):
    grupos = situacoes(q1, m)
    teto_n = teto_de([p['testes'][t][ALFA]['ic95'][1] for s in ('base', 'outliers', 'assimetria')
                      for p in m['situacoes'][s] for t, _, _ in TESTES], passo=.1)
    paineis = ''.join(
        f'<figure class="g4-painel"><figcaption><strong>{rotulo}</strong><br><span>{info}</span></figcaption>\n'
        f'{grafico_tamanho(m, nome, rotulo, teto_n)}\n</figure>\n'
        for nome, rotulo, info in (('base', 'Sem violação', 'diferenças simétricas em torno de zero'),
                                   ('outliers', 'Outliers (10% × 5)', 'cauda pesada, ainda simétrica'),
                                   ('assimetria', 'Assimetria real', 'média zero, sem simetria')))
    legenda = ''.join(f'<li><span class="g4-chave" style="background:{cor}" aria-hidden="true"></span>{rotulo}</li>'
                      for _, rotulo, cor in TESTES)
    return f"""<h3 class="g3q3-titulo">G3 — Erro tipo I em cada situação simulada (Q1 e Q3)</h3>
<p class="origem-selo">SIMULAÇÃO · efeito zero na média, 10.000 amostras por barra</p>
<p>{texto(m)}</p>
<ul class="g4-legenda" aria-label="Legenda do G3 por situação">{legenda}<li><span class="g4-chave referencia" aria-hidden="true"></span>Referência de 5% (α)</li><li><span class="g3q3-chave-ic" aria-hidden="true"></span>Haste: IC 95% Monte Carlo</li></ul>
<figure class="g3q3-figura">
{grafico_situacoes(grupos)}
</figure>
<h4 class="g3q3-subtitulo">A violação pesa diferente conforme o tamanho da amostra</h4>
<div class="g3q3-paineis">
{paineis}</div>
<details>
<summary>Ver os valores em tabela</summary>
<div class="tabela-rolavel" tabindex="0" role="region" aria-label="Erro tipo I por situação e tamanho">
<table class="tabela-resultados">
<caption>Erro tipo I por situação (α = 0,05)</caption>
<thead><tr><th scope="col">Situação</th><th scope="col">Pares</th><th scope="col">t pareado</th><th scope="col">Wilcoxon pareado</th></tr></thead>
<tbody>
{tabela(q1, m)}
</tbody>
</table>
</div>
</details>
<p class="notation">Fontes: Q1 da #110 (troca de rótulos) e Q3 da #116, que usa os mesmos geradores do G4 (#113). Conservador: o IC 95% fica abaixo de 5%; liberal: acima. Na assimetria, a H0 do Wilcoxon (simetria) é falsa por construção; as rejeições dele contam como falso positivo porque a pergunta do cenário é sobre o tempo médio.</p>"""


def inserir(html, bloco):
    if html.count(INICIO) != 1 or html.count(FIM) != 1 or html.index(INICIO) > html.index(FIM):
        raise ValueError('Marcadores G3Q3 ausentes ou inválidos.')
    return html[:html.index(INICIO) + len(INICIO)] + '\n' + bloco + '\n' + html[html.index(FIM):]


def executar(entrada_q1=rq111.ENTRADA, entrada_q3=ENTRADA_Q3, pagina=PAGINA):
    q1, q3 = rq111.carregar(entrada_q1), carregar_q3(entrada_q3)
    pagina = Path(pagina)
    pagina.write_text(inserir(pagina.read_text(encoding='utf-8'), fragmento(q1, q3)), encoding='utf-8')
    return q3


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--pagina', type=Path, default=PAGINA)
    args = parser.parse_args()
    try:
        executar(pagina=args.pagina)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(1, f'G3 (Q3) não gerado: {exc}\n')
    print('G3 atualizado com o erro tipo I da Q3 (#116).')
