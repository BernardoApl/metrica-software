"""RQ112: seção de resultados reais, calculados com as rotinas da RQ105."""
import argparse
import html
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analise import rq103_parametros_cache as rq103
from analise import rq105_testes_pareados as rq105

PAGINA = Path(__file__).with_name('index.html')
INICIO, FIM = '<!-- REAIS:INICIO -->', '<!-- REAIS:FIM -->'


def numero(v, casas=3):
    return f'{v:.{casas}f}'.replace('.', ',')


def pvalor(v):
    # Não arredondar p-valores pequenos para zero.
    return f'{v:.2e}'.replace('.', ',') if v < .001 else numero(v, 4)


def carregar(coleta=rq103.COLETA):
    meta, pares = rq103.carregar(coleta)
    sem, com = [p['sem_cache'] for p in pares], [p['com_cache'] for p in pares]
    return dict(origem=meta['execucao_id'], resultados=rq105.aplicar(sem, com, rotulo='Dados reais'),
                sem=sem, com=com)


def fragmento(dados):
    r = dados['resultados']
    t, w = r['t_pareado'], r['wilcoxon_pareado']
    decisao = lambda teste: 'Rejeita H0' if teste['rejeita_h0'] else 'Não rejeita H0'
    conclusao = ('Ambos os testes rejeitam H0' if t['rejeita_h0'] and w['rejeita_h0'] else
                 'Nenhum dos testes rejeita H0' if not t['rejeita_h0'] and not w['rejeita_h0'] else
                 'Os testes discordam na decisão sobre H0')
    direcao = 'menor' if t['media_diferenca_ms'] > 0 else 'maior' if t['media_diferenca_ms'] < 0 else 'igual'
    linhas = ['<p class="origem-selo">COLETA REAL · Mesma operação e entrada</p>',
        f'<p>Resultados dos <strong>{r["n_pares"]} pares medidos</strong> na coleta local. Aqui são usados os dados reais, não as amostras simuladas do G3. Diferença: tempo sem cache − tempo com cache.</p>',
        '<dl class="study-facts resultados-resumo">',
        f'<div><dt>Tempo médio sem cache</dt><dd><strong>{numero(statistics.mean(dados["sem"]), 6)} ms</strong></dd></div>',
        f'<div><dt>Tempo médio com cache</dt><dd><strong>{numero(statistics.mean(dados["com"]), 6)} ms</strong></dd></div>',
        f'<div><dt>Diferença média</dt><dd><strong>{numero(t["media_diferenca_ms"], 6)} ms</strong></dd></div></dl>',
        f'<p class="leitura-resultado"><strong>{conclusao}</strong> a α = {numero(t["alfa"], 2)}. O tempo médio observado com cache foi {direcao}. Essa leitura depende dos pressupostos descritos abaixo e não demonstra ganho universal.</p>',
        '<div class="tabela-rolavel" tabindex="0" role="region" aria-label="Estatísticas dos testes nos dados reais"><table class="tabela-resultados">',
        f'<caption>Testes bilaterais · α = {numero(t["alfa"], 2)} · tempos por operação no lote</caption>',
        '<thead><tr><th scope="col">Teste</th><th scope="col">Estatística</th><th scope="col">p-valor</th><th scope="col">Tamanho de efeito</th><th scope="col">Decisão</th></tr></thead><tbody>',
        f'<tr><th scope="row">t pareado</th><td data-label="Estatística">t({t["graus_liberdade"]}) = {numero(t["estatistica"])}</td><td data-label="p-valor">{pvalor(t["p_valor"])}</td><td data-label="Tamanho de efeito">Cohen d<sub>z</sub> = {numero(t["efeito_d_cohen_dz"])}</td><td data-label="Decisão">{decisao(t)}</td></tr>',
        f'<tr><th scope="row">Wilcoxon pareado</th><td data-label="Estatística">W+ = {numero(w["estatistica"], 1)}</td><td data-label="p-valor">{pvalor(w["p_valor"])}</td><td data-label="Tamanho de efeito">r rank-biserial = {numero(w["efeito_rank_biserial"])}</td><td data-label="Decisão">{decisao(w)}</td></tr>',
        '</tbody></table></div>',
        '<p class="notation">Notação: e−21 significa × 10⁻²¹. O p-valor não é a probabilidade de H0 ser verdadeira. Os dois tamanhos de efeito usam escalas diferentes e não devem ser comparados numericamente entre si.</p>',
        '<div class="resultados-intervalo"><h3>Magnitude e incerteza</h3>',
        f'<p>IC 95% da diferença média: <strong>{numero(t["ic95_media_ms"][0])} a {numero(t["ic95_media_ms"][1])} ms</strong>. Mediana das diferenças: {numero(w["mediana_diferenca_ms"])} ms. Estimador de Hodges–Lehmann: {numero(w["hodges_lehmann_ms"])} ms.</p>',
        '<p>Diferenças positivas indicam menor tempo com cache. O intervalo da média depende dos pressupostos do teste t; não é um intervalo do tamanho de efeito nem do estimador de Hodges–Lehmann.</p></div>',
        '<details class="resultados-detalhes"><summary>Como ler os testes e os tamanhos de efeito?</summary>',
        '<p>O teste t avalia a média das diferenças. Cohen d<sub>z</sub> divide essa média pelo desvio padrão das diferenças. O Wilcoxon avalia os postos das diferenças sob a hipótese de simetria em zero; W+ soma os postos positivos. Seu efeito rank-biserial varia de −1 a 1.</p>',
        f'<p>Wilcoxon: método {html.escape(w["metodo"])}; {w["n_efetivo"]} diferenças não nulas e {w["zeros_descartados"]} zeros descartados. W+ não deve ser confundido com min(W+, W−), usado por algumas bibliotecas.</p>',
        '<p>Rejeitar H0 indica evidência segundo o modelo do teste, não ganho universal. Não rejeitar H0 não demonstra equivalência.</p></details>',
        '<aside class="aviso" aria-label="Limitações dos resultados"><h3>Limites desta conclusão</h3>',
        f'<p>Shapiro–Wilk das diferenças: p = {pvalor(t["pressupostos"]["shapiro_p"])}; ' + ('normalidade rejeitada' if t['pressupostos']['normalidade_rejeitada'] else 'normalidade não rejeitada') + '. Esse diagnóstico não garante os demais pressupostos.</p>',
        '<p>Os pares compartilham entrada e ambiente; a análise da #103 identificou tendência temporal. Independência e simetria não estão garantidas. Os resultados inferenciais devem ser lidos com essa ressalva.</p>',
        '<p>O cache aquecido retorna um resultado em memória, enquanto a outra condição relê e agrega o CSV. O preenchimento do cache fica fora da medição principal. Os 300 repositórios são registros da entrada, não 300 amostras independentes.</p></aside>',
        f'<p class="notation">Origem: coleta {html.escape(dados["origem"])}. Validação da #103 e testes da #105. Resultados estáticos; atualização pelo comando do dashboard.</p>']
    return '\n'.join(linhas)


def executar(coleta=rq103.COLETA, pagina=PAGINA):
    dados = carregar(coleta)
    pagina = Path(pagina)
    texto = pagina.read_text(encoding='utf-8')
    if texto.count(INICIO) != 1 or texto.count(FIM) != 1 or texto.index(INICIO) > texto.index(FIM):
        raise ValueError('Marcadores da seção de resultados reais ausentes ou inválidos.')
    pagina.write_text(texto[:texto.index(INICIO)+len(INICIO)] + '\n' + fragmento(dados) + '\n' + texto[texto.index(FIM):], encoding='utf-8')
    return dados


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--coleta', type=Path, default=rq103.COLETA)
    parser.add_argument('--pagina', type=Path, default=PAGINA)
    args = parser.parse_args()
    try:
        executar(args.coleta, args.pagina)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(1, f'Resultados reais não atualizados: {exc}\n')
    print('Seção de resultados reais atualizada.')
