"""RQ115: seção 7 do dashboard — conclusão, comparação das hipóteses e recomendação.

Junta os resultados salvos (não refaz simulações):

* dados reais: validados pela #103 e testados pelas rotinas da #105 (via #112);
* Q1 — erro tipo I: `entregas/experimento-cache/RQ110/resultados.json`;
* Q2/Q3 — poder: `entregas/experimento-cache/RQ113/resultados.json`.

A recomendação é derivada dos números por uma regra explícita (`recomendar`), para que
mude sozinha se as simulações mudarem. Substitui o bloco entre `CONCLUSAO:INICIO` e
`CONCLUSAO:FIM` em `index.html`.

    python codigo-fonte/frontend/rq115_conclusao.py
"""
from __future__ import annotations

import argparse
import html
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from frontend import rq112_resultados_reais as rq112  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
Q1 = RAIZ / 'entregas/experimento-cache/RQ110/resultados.json'
Q2 = RAIZ / 'entregas/experimento-cache/RQ113/resultados.json'
PAGINA = Path(__file__).with_name('index.html')
INICIO, FIM = '<!-- CONCLUSAO:INICIO -->', '<!-- CONCLUSAO:FIM -->'
NOMES = {'t_pareado': 't pareado', 'wilcoxon_pareado': 'Wilcoxon pareado'}
ALFA = '0.05'
LIMIAR_ASSIMETRIA = 1.0      # |assimetria| a partir da qual o cenário "assimetria" representa os dados reais
TETO_LIBERAL = 0.10          # um teste com erro tipo I acima disso (2 × α) não é recomendado

# Expectativa do grupo ANTES de simular (item c do enunciado). Baseada no que a #103
# mostrou dos dados reais: diferenças assimétricas à direita e três extremos.
# O grupo pode editar este texto; ele é reproduzido sem alteração no dashboard.
EXPECTATIVA = dict(
    teste='wilcoxon_pareado',
    motivo='Os dados reais (#103) mostraram diferenças assimétricas à direita (coeficiente ≈ 1,9), Shapiro-Wilk '
           'rejeitando a normalidade e três valores extremos no início da coleta. Como o t pareado supõe '
           'diferenças aproximadamente normais e é sensível a extremos, esperávamos que o Wilcoxon, baseado em '
           'postos, mantivesse o erro tipo I perto de 5% e tivesse mais poder.')


def exigir(condicao, mensagem):
    if not condicao:
        raise ValueError(mensagem)


def carregar(q1=Q1, q2=Q2, coleta=None):
    m1 = json.loads(Path(q1).read_text(encoding='utf-8'))
    m2 = json.loads(Path(q2).read_text(encoding='utf-8'))
    exigir(m1.get('questao') == 'Q1' and m1.get('status') == 'concluida', 'Q1 (#110) ausente ou incompleta.')
    exigir(m2.get('questoes') == ['Q2', 'Q3'] and 'assimetria' in m2['cenarios'] and 'base' in m2['cenarios'],
           'Q2/Q3 (#113) ausente ou incompleta.')
    reais = rq112.carregar(coleta) if coleta else rq112.carregar()
    return dict(q1=m1, q2=m2, reais=reais)


def cenario_dos_dados(assimetria_real, resumo):
    """Qual cenário simulado mais se parece com as diferenças reais."""
    return 'assimetria' if abs(assimetria_real) >= LIMIAR_ASSIMETRIA else 'base' if 'outliers' not in resumo else 'outliers'


def recomendar(cenario, resumo):
    """Teste mais poderoso no cenário dos dados, desde que seu erro tipo I não passe de 2 × α."""
    r = resumo[cenario]
    candidatos = ['t_pareado', 'wilcoxon_pareado']
    if r['mais_poderoso'] in candidatos:
        candidatos.remove(r['mais_poderoso'])
        candidatos.insert(0, r['mais_poderoso'])
    for teste in candidatos:
        if r['erro_tipo_i'][teste] <= TETO_LIBERAL:
            return teste
    return min(candidatos, key=lambda t: r['erro_tipo_i'][t])


def pct(v, casas=1):
    return f'{100 * v:.{casas}f}%'.replace('.', ',')


def milhar(v):
    return f'{round(v, -3):,.0f}'.replace(',', '.')


def br(v, casas=2):
    return f'{v:.{casas}f}'.replace('.', ',')


def montar(d):
    q1, q2, reais = d['q1'], d['q2'], d['reais']['resultados']
    t, w = reais['t_pareado'], reais['wilcoxon_pareado']
    resumo = q2['resumo']
    assim_real = t['pressupostos']['assimetria']
    cen = cenario_dos_dados(assim_real, resumo)
    rec = recomendar(cen, resumo)
    outro = 'wilcoxon_pareado' if rec == 't_pareado' else 't_pareado'
    rc = resumo[cen]
    acertou = EXPECTATIVA['teste'] == rec
    tipo1 = {k: v['erro_tipo_i'] for k, v in q1['resultados'].items()}
    vantagem_w = {c: -r['maior_diferenca']['t_menos_wilcoxon'] for c, r in resumo.items()
                  if r['mais_poderoso'] == 'wilcoxon_pareado'}
    return dict(cenario=cen, recomendado=rec, outro=outro, acertou=acertou, assimetria_real=assim_real,
                tipo1_q1=tipo1, resumo_cenario=rc, vantagem_wilcoxon=vantagem_w, t=t, w=w,
                sem=statistics.mean(d['reais']['sem']), com=statistics.mean(d['reais']['com']))


def fragmento(d):
    c = montar(d)
    q2, resumo = d['q2'], d['q2']['resumo']
    t, w, rec, outro, rc = c['t'], c['w'], c['recomendado'], c['outro'], c['resumo_cenario']
    rotulo_cen = html.escape(q2['cenarios'][c['cenario']]['rotulo'])
    ultimo = q2['cenarios']['base']['pontos'][-1]['testes']
    poder_max = min(ultimo[tt][ALFA]['proporcao'] for tt in NOMES)
    decisao = lambda r: 'rejeitada' if r['rejeita_h0'] else 'não rejeitada'
    pv = rq112.pvalor
    achados = [
        f"<strong>Erro tipo I (G3):</strong> com H0 verdadeira, o t rejeitou {pct(c['tipo1_q1']['t_pareado'], 2)} e o "
        f"Wilcoxon {pct(c['tipo1_q1']['wilcoxon_pareado'], 2)} das amostras, os dois perto de 5%.",
        f"<strong>Poder (G4):</strong> com diferenças simétricas o Wilcoxon detectou melhor o efeito"
        + (f" (até {br(100 * max(c['vantagem_wilcoxon'].values()), 1)} p.p. com outliers)" if c['vantagem_wilcoxon'] else '')
        + '.',
        f"<strong>Assimetria (G4):</strong> com a assimetria real e média zero, o Wilcoxon rejeitou "
        f"{pct(resumo['assimetria']['erro_tipo_i']['wilcoxon_pareado'])} das amostras sem efeito na média, e o t teve mais "
        f"poder (até {br(100 * abs(resumo['assimetria']['maior_diferenca']['t_menos_wilcoxon']), 1)} p.p.).",
    ]
    if c['acertou']:
        veredito = (f"A simulação <strong>confirmou</strong> a expectativa no cenário que mais se parece com os dados reais "
                    f"({rotulo_cen}).")
    else:
        veredito = (f"A simulação <strong>confirmou a expectativa só em parte</strong>: o Wilcoxon ganha quando as diferenças "
                    f"são simétricas com extremos, mas não no cenário que mais se parece com os dados reais (“{rotulo_cen}”, "
                    f"assimetria {br(c['assimetria_real'])}). A diferença se explica porque o Wilcoxon não testa a média: "
                    'com diferenças assimétricas, ele detecta a mediana deslocada mesmo quando a média não mudou e fica liberal.')
    linhas = [
        '<div class="conclusao-comparacao">',
        f'<article class="conclusao-cartao"><p class="conclusao-rotulo">Antes de simular</p><h3>Esperávamos que o '
        f'{NOMES[EXPECTATIVA["teste"]]} se saísse melhor</h3><p>{html.escape(EXPECTATIVA["motivo"])}</p></article>',
        '<article class="conclusao-cartao encontrado"><p class="conclusao-rotulo">O que encontramos</p>'
        f'<h3>Depende da forma das diferenças</h3><ul>{"".join(f"<li>{a}</li>" for a in achados)}</ul></article>',
        '</div>',
        f'<p>{veredito}</p>',
        '<h3 class="conclusao-subtitulo">Comparação das hipóteses nos dados reais</h3>',
        '<div class="tabela-rolavel" tabindex="0" role="region" aria-label="Comparação das hipóteses"><table class="tabela-resultados">',
        f'<caption>{reais_n(d)} pares reais · bilateral · α = 0,05</caption>',
        '<thead><tr><th scope="col">Teste</th><th scope="col">H0 testada</th><th scope="col">Resultado</th>'
        '<th scope="col">H0</th><th scope="col">Efeito</th></tr></thead><tbody>',
        f'<tr><th scope="row">t pareado</th><td data-label="H0 testada">média das diferenças μ<sub>d</sub> = 0</td>'
        f'<td data-label="Resultado">t({t["graus_liberdade"]}) = {br(t["estatistica"])}; p = {pv(t["p_valor"])}</td>'
        f'<td data-label="H0">{decisao(t)}</td><td data-label="Efeito">d<sub>z</sub> = {br(t["efeito_d_cohen_dz"])} ({t["magnitude"]})</td></tr>',
        f'<tr><th scope="row">Wilcoxon pareado</th><td data-label="H0 testada">diferenças simétricas em torno de 0</td>'
        f'<td data-label="Resultado">W+ = {w["estatistica"]:g}; p = {pv(w["p_valor"])}</td>'
        f'<td data-label="H0">{decisao(w)}</td><td data-label="Efeito">r = {br(w["efeito_rank_biserial"])} ({w["magnitude"]})</td></tr>',
        '</tbody></table></div>',
        f'<p>{"Os dois testes chegam à mesma conclusão" if t["rejeita_h0"] == w["rejeita_h0"] else "Os testes discordam"}: '
        f'o tempo médio caiu de {br(c["sem"], 3)} ms para {br(c["com"] * 1000, 3)} µs por operação '
        f'(diferença média {br(t["media_diferenca_ms"], 2)} ms, IC 95% {br(t["ic95_media_ms"][0])} a {br(t["ic95_media_ms"][1])} ms). '
        'O efeito é tão grande que a escolha do teste não muda a decisão aqui; ela importa para efeitos pequenos e para o '
        'que se afirma (média ou mediana).</p>',
        '<aside class="conclusao-recomendacao" aria-labelledby="titulo-recomendacao">',
        f'<p class="conclusao-rotulo">Recomendação</p><h3 id="titulo-recomendacao">Usar o {NOMES[rec]} neste cenário</h3>',
        f'<p>As diferenças reais são assimétricas ({br(c["assimetria_real"])}), e o cenário simulado mais parecido com elas é '
        f'“{rotulo_cen}”. Ali o {NOMES[rec]} teve erro tipo I de {pct(rc["erro_tipo_i"][rec])} e '
        + (f'mais poder' if rc['mais_poderoso'] == rec else 'poder comparável')
        + f', enquanto o {NOMES[outro]} rejeitou {pct(rc["erro_tipo_i"][outro])} das amostras sem efeito'
        + (' na média' if c['cenario'] == 'assimetria' else '')
        + '. Como H0 fala do <strong>tempo médio</strong>, recomendamos relatar o '
        f'{NOMES[rec]} com o IC 95% da média e usar o {NOMES[outro]} e o estimador de Hodges–Lehmann como verificação de robustez.</p>',
        '<p><strong>Quando a escolha mudaria:</strong></p><ul>',
        f'<li>se as diferenças fossem aproximadamente simétricas, mas com extremos (cenários base e outliers): Wilcoxon, que '
        f'precisou de d<sub>z</sub> ≈ {br(resumo["outliers"]["dz_para_80"]["wilcoxon_pareado"])} contra '
        f'≈ {br(resumo["outliers"]["dz_para_80"]["t_pareado"])} do t para 80% de poder com outliers;</li>',
        '<li>se a pergunta fosse sobre o tempo <em>típico</em> (mediana), e não o médio: Wilcoxon, cuja hipótese é essa;</li>',
        '<li>com amostras muito pequenas (10 pares), os dois perdem poder e ficam parecidos: o problema passa a ser coletar mais '
        'pares, não escolher o teste.</li></ul></aside>',
        '<details class="conclusao-detalhes"><summary>Tamanho da amostra e importância prática</summary>',
        f'<p>O efeito observado (d<sub>z</sub> = {br(t["efeito_d_cohen_dz"])}) está muito além da grade do G4 (d<sub>z</sub> ≤ 1), '
        f'onde, com 30 pares, os dois testes já chegam a {pct(poder_max)} de poder: o poder para detectá-lo é praticamente 100%. '
        f'Para um efeito moderado, 80% de poder com 30 pares exigiria d<sub>z</sub> ≈ {br(resumo["base"]["dz_para_80"]["t_pareado"])} '
        f'(t) ou ≈ {br(resumo["base"]["dz_para_80"]["wilcoxon_pareado"])} (Wilcoxon) na base.</p>',
        '<p>Com p-valores dessa ordem, o que importa é o tamanho do efeito: o cache reduziu o tempo em cerca de '
        + milhar(c['sem'] / c['com']) + ' vezes, mas são milissegundos por operação numa máquina local. '
        'Significância estatística não é, sozinha, relevância prática.</p></details>',
        '<aside class="aviso" aria-label="Limitações do estudo"><h3>Principal limitação</h3>',
        '<p>Os 30 pares vêm de uma única execução na mesma máquina, com tendência temporal (#103): a independência entre pares é '
        'uma suposição, e o resultado não se generaliza para cache frio, API, banco de dados ou outras máquinas. As simulações '
        'reamostram esses pares; não são novas medições.</p></aside>',
        '<p class="notation">Gerado por <code>codigo-fonte/frontend/rq115_conclusao.py</code> a partir dos resultados salvos da '
        '#105, #110 e #113. A recomendação segue uma regra explícita: o teste mais poderoso no cenário que mais se parece com os '
        'dados reais, desde que seu erro tipo I não passe de 10% (2 × α).</p>',
    ]
    return '\n'.join(linhas)


def reais_n(d):
    return d['reais']['resultados']['n_pares']


def executar(pagina=PAGINA, **kwargs):
    d = carregar(**kwargs)
    pagina = Path(pagina)
    texto = pagina.read_text(encoding='utf-8')
    exigir(texto.count(INICIO) == 1 and texto.count(FIM) == 1 and texto.index(INICIO) < texto.index(FIM),
           'Marcadores da conclusão ausentes ou inválidos.')
    pagina.write_text(texto[:texto.index(INICIO) + len(INICIO)] + '\n' + fragmento(d) + '\n' + texto[texto.index(FIM):],
                      encoding='utf-8')
    return montar(d)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--pagina', type=Path, default=PAGINA)
    args = parser.parse_args()
    try:
        c = executar(args.pagina)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(1, f'Conclusão não gerada: {exc}\n')
    print(f"Conclusão atualizada: recomendado {NOMES[c['recomendado']]} (cenário {c['cenario']}).")
