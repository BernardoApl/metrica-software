"""RQ117: destaques do modo quadro, uma pergunta e poucos números grandes por seção.

Cada seção do dashboard ganha, logo abaixo do título, a pergunta que ela responde e
2 ou 3 números que dão a resposta. No modo quadro (tecla P) só ficam o destaque e o
gráfico, em letra grande. Os números vêm dos resultados salvos, nunca digitados à mão.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # permite executar como script

from frontend import rq115_conclusao as rq115  # noqa: E402
from frontend import rq117_g3_q3 as g3q3  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
DADOS_G1 = RAIZ / 'entregas/experimento-cache/RQ107/dados_visualizacao.json'
PAGINA = Path(__file__).with_name('index.html')
SECOES = ('cenario', 'dados', 'testes', 'erro-tipo-i', 'poder', 'resultados-reais', 'conclusao')
COR = {'t_pareado': 'var(--cor-t)', 'wilcoxon_pareado': 'var(--cor-w)'}


def marcadores(secao):
    return f'<!-- QUADRO:{secao}:INICIO (gerado por rq117_quadro.py) -->', f'<!-- QUADRO:{secao}:FIM -->'


def br(v, casas=2):
    return f'{v:.{casas}f}'.replace('.', ',')


def pct(v):
    return rq115.pct(v)


def potencia_dez(p):
    """3,89e-21 vira 3,9 × 10⁻²¹: legível de longe e sem arredondar para zero."""
    mantissa, expoente = f'{p:.1e}'.split('e')
    sobrescrito = str.maketrans('-0123456789', '⁻⁰¹²³⁴⁵⁶⁷⁸⁹')
    return f"{mantissa.replace('.', ',')} × 10{str(int(expoente)).translate(sobrescrito)}"


def numero(valor, legenda, teste=None):
    chave = (f'<span class="quadro-chave" style="background:{COR[teste]}" aria-hidden="true"></span>'
             if teste else '')
    return (f'<div class="quadro-numero"><p class="quadro-valor">{valor}</p>'
            f'<p class="quadro-legenda">{chave}{legenda}</p></div>')


def bloco(pergunta, numeros):
    return (f'<div class="quadro-destaque"><p class="quadro-pergunta">{pergunta}</p>\n'
            f'<div class="quadro-numeros">{"".join(numeros)}</div></div>')


def destaques(g1, conclusao, q1, q3, q2):
    sem, com = g1['series']['sem_cache']['real']['forma'], g1['series']['com_cache']['real']['forma']
    assimetria = g1['series']['diferenca']['real']['forma']['assimetria']
    vezes = rq115.milhar(sem['mediana'] * 1000 / com['mediana'])
    n = q3['n_padrao']
    t_assim = g3q3.taxa(q3, 'assimetria', n, 't_pareado')['proporcao']
    w_assim = g3q3.taxa(q3, 'assimetria', n, 'wilcoxon_pareado')['proporcao']
    q1_taxas = [q1['resultados'][t]['erro_tipo_i'] for t in ('t_pareado', 'wilcoxon_pareado')]
    outliers, assim = q2['resumo']['outliers'], q2['resumo']['assimetria']
    t, w = conclusao['t'], conclusao['w']
    rec, outro = conclusao['recomendado'], conclusao['outro']
    nomes = rq115.NOMES
    return {
        'cenario': bloco('Usar cache muda o tempo médio da operação?', [
            numero(f"{t['n']} pares", 'a mesma operação medida com e sem cache, na mesma máquina'),
            numero('H<sub>0</sub>', 'o tempo médio é o mesmo com e sem cache (μ<sub>d</sub> = 0)'),
            numero('H<sub>1</sub>', 'o tempo médio muda, para mais ou para menos: teste bilateral')]),
        'dados': bloco('Como são os tempos reais?', [
            numero(f"{br(sem['mediana'])} ms", 'tempo típico sem cache (mediana)'),
            numero(f"{br(com['mediana'])} µs", f'tempo típico com cache, cerca de {vezes} vezes menor'),
            numero(br(assimetria), 'assimetria das diferenças: cauda longa à direita, nada normal')]),
        'testes': bloco('O que cada teste compara?', [
            numero('Médias', 'a média das diferenças, contra uma t de Student', 't_pareado'),
            numero('Postos', 'a ordem das diferenças, sem supor normalidade', 'wilcoxon_pareado'),
            numero('5%', 'α: rejeita H<sub>0</sub> nas duas caudas da distribuição')]),
        'erro-tipo-i': bloco('Sem efeito nenhum, quantas vezes cada teste acusa diferença?', [
            numero(pct(t_assim), f't pareado, com diferenças assimétricas ({n} pares)', 't_pareado'),
            numero(pct(w_assim), f'Wilcoxon, com diferenças assimétricas ({n} pares)', 'wilcoxon_pareado'),
            numero(f'{pct(q1_taxas[0])} e {pct(q1_taxas[1])}', 'os dois, com dados bem comportados: o esperado é 5%')]),
        'poder': bloco('Qual teste percebe melhor um efeito real?', [
            numero(f"d<sub>z</sub> {br(outliers['dz_para_80']['wilcoxon_pareado'])}",
                   f"Wilcoxon chega a 80% de poder com outliers; o t precisa de "
                   f"{br(outliers['dz_para_80']['t_pareado'])}", 'wilcoxon_pareado'),
            numero(f"+{br(100 * assim['maior_diferenca']['t_menos_wilcoxon'], 1)} p.p.",
                   'de poder para o t pareado quando as diferenças são assimétricas', 't_pareado')]),
        'resultados-reais': bloco(f"E nos {t['n']} pares reais?", [
            numero(f"p = {potencia_dez(t['p_valor'])}", 't pareado: rejeita H<sub>0</sub>' if t['rejeita_h0']
                   else 't pareado: não rejeita H<sub>0</sub>', 't_pareado'),
            numero(f"p = {potencia_dez(w['p_valor'])}", 'Wilcoxon: rejeita H<sub>0</sub>' if w['rejeita_h0']
                   else 'Wilcoxon: não rejeita H<sub>0</sub>', 'wilcoxon_pareado'),
            numero(f"{br(t['media_diferenca_ms'])} ms", f"diferença média por operação "
                   f"(IC 95% de {br(t['ic95_media_ms'][0])} a {br(t['ic95_media_ms'][1])} ms)")]),
        'conclusao': bloco('Qual teste usar neste cenário?', [
            numero(nomes[rec], 'recomendado: a pergunta é sobre o tempo médio e os dados são assimétricos', rec),
            numero(nomes[outro], 'como verificação de robustez, ou se a pergunta fosse sobre o tempo típico', outro)]),
    }


def carregar():
    g1 = json.loads(DADOS_G1.read_text(encoding='utf-8'))
    dados_conclusao = rq115.carregar()
    return dict(g1=g1, conclusao=rq115.montar(dados_conclusao), q1=dados_conclusao['q1'],
                q2=dados_conclusao['q2'], q3=g3q3.carregar_q3())


def inserir(html, secao, bloco_html):
    inicio, fim = marcadores(secao)
    if html.count(inicio) != 1 or html.count(fim) != 1 or html.index(inicio) > html.index(fim):
        raise ValueError(f'Marcadores do quadro ausentes ou inválidos na seção {secao}.')
    return html[:html.index(inicio) + len(inicio)] + '\n' + bloco_html + '\n' + html[html.index(fim):]


def executar(pagina=PAGINA):
    d = carregar()
    blocos = destaques(d['g1'], d['conclusao'], d['q1'], d['q3'], d['q2'])
    pagina = Path(pagina)
    html = pagina.read_text(encoding='utf-8')
    for secao in SECOES:
        html = inserir(html, secao, blocos[secao])
    pagina.write_text(html, encoding='utf-8')
    return blocos


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--pagina', type=Path, default=PAGINA)
    args = parser.parse_args()
    try:
        executar(args.pagina)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(1, f'Destaques não gerados: {exc}\n')
    print('Destaques do modo quadro atualizados.')
