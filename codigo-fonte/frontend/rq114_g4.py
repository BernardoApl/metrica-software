"""RQ114: gráfico G4 — curvas de poder do t pareado e do Wilcoxon pareado (Q2 e Q3).

Lê `entregas/experimento-cache/RQ113/resultados.json` (não refaz as simulações) e
substitui o bloco entre `G4:INICIO` e `G4:FIM` em `index.html` por quatro painéis SVG
estáticos (um por cenário), uma tabela-resumo e um texto gerado dos números. Funciona
sem JavaScript. Cores fixas por teste, iguais às do G2 e do G3.

    python codigo-fonte/frontend/rq114_g4.py
"""
from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ENTRADA = RAIZ / 'entregas/experimento-cache/RQ113/resultados.json'
PAGINA = Path(__file__).with_name('index.html')
INICIO, FIM = '<!-- G4:INICIO -->', '<!-- G4:FIM -->'
TESTES = [('t_pareado', 't pareado', '#2a78d6'), ('wilcoxon_pareado', 'Wilcoxon pareado', '#eb6834')]
NOMES = {t: r for t, r, _ in TESTES}
ALFA, ALFA2 = '0.05', '0.01'
L, A = 320, 230
M = dict(e=54, d=12, s=14, i=40)


def exigir(condicao, mensagem):
    if not condicao:
        raise ValueError(mensagem)


def carregar(entrada=ENTRADA):
    m = json.loads(Path(entrada).read_text(encoding='utf-8'))
    exigir(m.get('schema_version') == 1 and m.get('questoes') == ['Q2', 'Q3'], 'Esperados os resultados da RQ113.')
    exigir(ALFA in map(lambda a: f'{a:g}', m['alfas']) and ALFA2 in map(lambda a: f'{a:g}', m['alfas']),
           'Resultados sem α = 0,05 e 0,01.')
    exigir('base' in m['cenarios'], 'Cenário base ausente.')
    for c in m['cenarios'].values():
        efeitos = [p['efeito_dz'] for p in c['pontos']]
        exigir(len(efeitos) >= 5 and efeitos[0] == 0 and efeitos == sorted(efeitos),
               'O G4 exige ao menos 5 efeitos crescentes começando em zero.')
        for p in c['pontos']:
            for t, _, _ in TESTES:
                for alfa in (ALFA, ALFA2):
                    r = p['testes'][t][alfa]
                    exigir(math.isclose(r['proporcao'], r['rejeicoes'] / m['repeticoes'], abs_tol=1e-12) and
                           0 <= r['ic95'][0] <= r['proporcao'] <= r['ic95'][1] <= 1, 'Proporção ou IC inconsistente.')
    return m


def pct(v, casas=1):
    return f'{100 * v:.{casas}f}%'.replace('.', ',')


def br(v, casas=1):
    return f'{v:.{casas}f}'.replace('.', ',')


def painel(nome, c, repeticoes):
    sx = lambda dz: M['e'] + dz * (L - M['e'] - M['d'])
    sy = lambda v: A - M['i'] - v * (A - M['s'] - M['i'])
    titulo = html.escape(c['rotulo'])
    desc = (f"Proporção de rejeições por tamanho de efeito no cenário {titulo}, {c['n_pares']} pares. "
            + ' '.join(f"{rot}: {pct(c['pontos'][0]['testes'][t][ALFA]['proporcao'])} em d_z = 0 e "
                       f"{pct(c['pontos'][-1]['testes'][t][ALFA]['proporcao'])} em d_z = {br(c['pontos'][-1]['efeito_dz'])}."
                       for t, rot, _ in TESTES))
    s = [f'<svg class="g4-svg" viewBox="0 0 {L} {A}" role="img" aria-labelledby="g4-{nome}-t g4-{nome}-d">',
         f'<title id="g4-{nome}-t">Poder — {titulo}</title><desc id="g4-{nome}-d">{desc}</desc>']
    for v in (0, .25, .5, .75, 1):
        s.append(f'<path d="M{M["e"]} {sy(v):.1f} H{L - M["d"]}" class="g4-grade"/>'
                 f'<text x="{M["e"] - 6}" y="{sy(v) + 4:.1f}" text-anchor="end">{int(v * 100)}%</text>')
    for v, rot in ((.05, '5%'), (.8, '80%')):
        s.append(f'<path d="M{M["e"]} {sy(v):.1f} H{L - M["d"]}" class="g4-ref"/>'
                 f'<text x="{L - M["d"]}" y="{sy(v) - 4:.1f}" text-anchor="end" class="g4-ref-rotulo">{rot}</text>')
    for dz in (0, .2, .4, .6, .8, 1):
        s.append(f'<text x="{sx(dz):.1f}" y="{A - M["i"] + 16}" text-anchor="middle">{br(dz)}</text>')
    s.append(f'<path d="M{M["e"]} {sy(0):.1f} H{L - M["d"]}" class="g4-base"/>')
    meio = (M['s'] + A - M['i']) / 2
    s.append(f'<text x="12" y="{meio:.1f}" text-anchor="middle" class="g4-rotulo" '
             f'transform="rotate(-90 12 {meio:.1f})">Rejeições de H0 (%)</text>')
    s.append(f'<text x="{M["e"] + (L - M["e"] - M["d"]) / 2:.1f}" y="{A - 6}" text-anchor="middle" class="g4-rotulo">'
             'Tamanho do efeito d<tspan baseline-shift="sub" font-size="9">z</tspan> (adimensional)</text>')
    for t, rot, cor in TESTES:
        for alfa, classe in ((ALFA2, 'g4-linha-01'), (ALFA, 'g4-linha')):
            pts = ' '.join(f"{sx(p['efeito_dz']):.1f},{sy(p['testes'][t][alfa]['proporcao']):.1f}" for p in c['pontos'])
            s.append(f'<polyline points="{pts}" class="{classe}" stroke="{cor}"/>')
        for p in c['pontos']:
            r, r01 = p['testes'][t][ALFA], p['testes'][t][ALFA2]
            dica = (f"{rot}, d_z = {br(p['efeito_dz'])} (δ = {br(p['delta_ms'], 3)} ms): {pct(r['proporcao'])} de rejeições "
                    f"com α = 0,05 (IC 95% {pct(r['ic95'][0])} a {pct(r['ic95'][1])}); {pct(r01['proporcao'])} com α = 0,01. "
                    f"{r['rejeicoes']} de {repeticoes} amostras.")
            s.append(f'<circle cx="{sx(p["efeito_dz"]):.1f}" cy="{sy(r["proporcao"]):.1f}" r="4" fill="{cor}" class="g4-ponto">'
                     f'<title>{html.escape(dica)}</title></circle>')
    s.append('</svg>')
    return '\n'.join(s)


def texto(m):
    r = m['resumo']
    base, out, ass = r['base'], r.get('outliers'), r.get('assimetria')
    frases = [f"Cada ponto é a proporção de {format(m['repeticoes'], ',').replace(',', '.')} amostras simuladas em que o teste "
              'rejeitou H0; no efeito zero, essa proporção é o erro tipo I, e a partir dele é o poder.']
    def lider(x):
        return 'os dois praticamente empatam' if x['mais_poderoso'] == 'empate' else f"o {NOMES[x['mais_poderoso']]} detecta melhor"
    frases.append(f"Com as diferenças reais simetrizadas (base, 30 pares), {lider(base)}: 80% de poder exige "
                  f"d<sub>z</sub> ≈ {br(base['dz_para_80']['t_pareado'], 2)} no t e ≈ {br(base['dz_para_80']['wilcoxon_pareado'], 2)} "
                  'no Wilcoxon' + (', porque os extremos reais inflam o desvio padrão usado pelo t.'
                                   if base['mais_poderoso'] == 'wilcoxon_pareado' else '.'))
    if out and ass:
        frases.append(f"A vantagem do Wilcoxon cresce com outliers (até {br(100 * abs(out['maior_diferenca']['t_menos_wilcoxon']))} p.p.) "
                      f"e muda de lado na assimetria: ali o t tem mais poder (até {br(100 * abs(ass['maior_diferenca']['t_menos_wilcoxon']))} p.p.), "
                      f"e o Wilcoxon rejeita {pct(ass['erro_tipo_i']['wilcoxon_pareado'])} das amostras sem efeito na média, "
                      'porque testa a simetria (mediana), não a média.')
    if 'amostra_pequena' in r:
        p = m['cenarios']['amostra_pequena']['pontos'][-1]['testes']
        frases[-1] = frases[-1][:-1] + (f"; com 10 pares, os dois perdem poder ({pct(p['t_pareado'][ALFA]['proporcao'])} e "
                                        f"{pct(p['wilcoxon_pareado'][ALFA]['proporcao'])} em d<sub>z</sub> = 1).")
    return ' '.join(frases)


def fragmento(m):
    linhas = ['<p class="origem-selo">SIMULAÇÃO · efeito conhecido somado às diferenças</p>',
              f'<p>{texto(m)}</p>',
              '<ul class="g4-legenda" aria-label="Legenda do G4">',
              *[f'<li><span class="g4-chave" style="background:{cor}" aria-hidden="true"></span>{rot}</li>' for _, rot, cor in TESTES],
              '<li><span class="g4-chave tracejada" aria-hidden="true"></span>Linha fina tracejada: mesmo teste com α = 0,01</li>',
              '<li><span class="g4-chave referencia" aria-hidden="true"></span>Referências de 5% (erro tipo I) e 80% (poder usual)</li>',
              '</ul>', '<div class="g4-paineis">']
    for nome, c in m['cenarios'].items():
        linhas += [f'<figure class="g4-painel"><figcaption><strong>{html.escape(c["rotulo"])}</strong> · {c["questao"]}'
                   f'<br><span>{html.escape(c["violacao"][:1].upper() + c["violacao"][1:])}</span></figcaption>', painel(nome, c, m['repeticoes']),
                   '</figure>']
    linhas += ['</div>', '<p class="notation">Eixo vertical: proporção de amostras com p &lt; α (%). Passe o mouse sobre um ponto para ver '
               'o valor, o IC 95% e o δ em ms. d<sub>z</sub> = δ / σ<sub>d</sub>, o deslocamento somado às diferenças em desvios padrão.</p>',
               '<div class="tabela-rolavel" tabindex="0" role="region" aria-label="Resumo do poder por cenário"><table class="tabela-resultados">',
               '<caption>G4 — Resumo por cenário (α = 0,05)</caption>',
               '<thead><tr><th scope="col">Cenário</th><th scope="col">Erro tipo I (t / Wilcoxon)</th>'
               '<th scope="col">d<sub>z</sub> para 80% de poder (t / Wilcoxon)</th><th scope="col">Quem detecta melhor</th></tr></thead><tbody>']
    for nome, c in m['cenarios'].items():
        r = m['resumo'][nome]
        dz = ' / '.join(br(r['dz_para_80'][t], 2) if r['dz_para_80'][t] is not None else '&gt; 1' for t, _, _ in TESTES)
        tipo = ' / '.join(f"{pct(r['erro_tipo_i'][t])} ({r['calibracao'][t]})" for t, _, _ in TESTES)
        quem = ('empate' if r['mais_poderoso'] == 'empate' else
                f"{NOMES[r['mais_poderoso']]} (até {br(100 * abs(r['maior_diferenca']['t_menos_wilcoxon']))} p.p.)")
        linhas.append(f'<tr><th scope="row">{html.escape(c["rotulo"])}</th><td data-label="Erro tipo I (t / Wilcoxon)">{tipo}</td>'
                      f'<td data-label="d_z para 80% de poder">{dz}</td><td data-label="Quem detecta melhor">{quem}</td></tr>')
    linhas += ['</tbody></table></div>',
               '<details class="g4-explicacao"><summary>Como os cenários foram construídos?</summary>',
               '<p>Todos reamostram os 30 pares reais. Na base, cada diferença é centrada na média real e recebe um sinal sorteado: '
               'a variação observada é mantida e H0 vale para os dois testes. Outliers: 10% das diferenças com magnitude 5 vezes maior. '
               'Amostra pequena: 10 pares. Assimetria: diferenças centradas sem sortear o sinal, com a assimetria real (≈ 1,9).</p>',
               '<p>A base não usa a troca de rótulos da Q1 (G3), que gera diferenças bimodais de ±6 ms; nessa forma um deslocamento '
               'mínimo reordena todos os postos e a curva do Wilcoxon ganha degraus artificiais. Por isso o ponto d<sub>z</sub> = 0 '
               'do G4 é próximo do G3, mas não igual.</p>',
               '<p>Com α = 0,01 (linhas tracejadas) as curvas descem: há menos falsos positivos, mas é preciso um efeito maior para '
               'chegar ao mesmo poder.</p></details>',
               f'<p class="notation">Fonte: simulações Q2/Q3 da #113, semente {m["semente"]}, {format(m["repeticoes"], ",").replace(",", ".")} '
               'amostras por ponto. Resultados estáticos da execução salva; o gráfico não refaz as simulações.</p>']
    return '\n'.join(linhas)


def executar(entrada=ENTRADA, pagina=PAGINA):
    m = carregar(entrada)
    pagina = Path(pagina)
    texto_html = pagina.read_text(encoding='utf-8')
    exigir(texto_html.count(INICIO) == 1 and texto_html.count(FIM) == 1 and texto_html.index(INICIO) < texto_html.index(FIM),
           'Marcadores G4 ausentes ou inválidos.')
    novo = texto_html[:texto_html.index(INICIO) + len(INICIO)] + '\n' + fragmento(m) + '\n' + texto_html[texto_html.index(FIM):]
    pagina.write_text(novo, encoding='utf-8')
    return m


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--entrada', type=Path, default=ENTRADA)
    parser.add_argument('--pagina', type=Path, default=PAGINA)
    args = parser.parse_args()
    try:
        executar(args.entrada, args.pagina)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(1, f'G4 não gerado: {exc}\n')
    print('G4 atualizado com os resultados da RQ113.')
