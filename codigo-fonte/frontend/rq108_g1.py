"""RQ108: desenha o G1, histogramas dos dados reais ao lado dos simulados."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
DADOS = RAIZ / 'entregas/experimento-cache/RQ107/dados_visualizacao.json'
SAIDA = Path(__file__).resolve().parent / 'graficos/g1.svg'

# Cores de real/simulado, distintas das que os gráficos G2-G4 reservam aos testes.
COR_REAL, COR_SIMULADO = '#7a5195', '#009e73'
TINTA, TINTA_SUAVE, GRADE, FUNDO = '#192b3c', '#4d6171', '#e4e9ed', '#ffffff'
TITULOS_LINHA = {
    'sem_cache': 'Sem cache: tempo por operação',
    'com_cache': 'Com cache: tempo por operação',
    'diferenca': 'Diferença pareada (o que os testes analisam)',
}
EIXO_X = {
    'sem_cache': 'Tempo por operação sem cache (ms)',
    'com_cache': 'Tempo por operação com cache (µs)',
    'diferenca': 'd = tempo sem cache − tempo com cache (ms)',
}


def desenhar_painel(eixo, bordas, contagens, cor, teto):
    larguras = [b - a for a, b in zip(bordas, bordas[1:])]
    eixo.bar(bordas[:-1], contagens, width=larguras, align='edge', color=cor, edgecolor=FUNDO, linewidth=1.5, zorder=2)
    eixo.set_xlim(bordas[0], bordas[-1])
    eixo.set_ylim(0, teto)
    eixo.yaxis.get_major_locator().set_params(integer=True)
    eixo.grid(axis='y', color=GRADE, linewidth=.8, zorder=0)
    eixo.spines[['top', 'right', 'left']].set_visible(False)
    eixo.spines['bottom'].set_color(TINTA_SUAVE)
    eixo.tick_params(colors=TINTA_SUAVE, labelsize=9, length=0)


def anotar_extremos(eixo, serie):
    """Identifica no painel real os pares fora das cercas, mantidos na análise."""
    pares = serie['real']['forma']['pares_fora_cercas_iqr']
    if not pares:
        return
    fora = [serie['real']['valores'][p - 1] for p in pares]
    nomes = ', '.join(str(p) for p in pares)
    eixo.annotate(f'Valores extremos: pares {nomes}\n(mantidos na análise)',
                  xy=(min(fora), 1.1), xytext=(.97, .86), textcoords='axes fraction',
                  ha='right', va='top', fontsize=9, color=TINTA,
                  arrowprops=dict(arrowstyle='-', color=TINTA_SUAVE, linewidth=.8))


def desenhar_g1(dados):
    series = dados['series']
    fig, eixos = plt.subplots(len(series), 2, figsize=(10.5, 9.4), facecolor=FUNDO)
    for linha, (nome, serie) in zip(eixos, series.items()):
        h = serie['histograma']
        teto = max(h['real'] + h['simulado']) + 1
        desenhar_painel(linha[0], h['bordas'], h['real'], COR_REAL, teto)
        desenhar_painel(linha[1], h['bordas'], h['simulado'], COR_SIMULADO, teto)
        linha[0].set_title(TITULOS_LINHA[nome], loc='left', fontsize=11, color=TINTA, fontweight='bold')
        linha[0].set_ylabel('Frequência (nº de pares)', fontsize=9.5, color=TINTA_SUAVE)
        for eixo in linha:
            eixo.set_xlabel(EIXO_X[nome], fontsize=9.5, color=TINTA_SUAVE)
    anotar_extremos(eixos[0][0], series['sem_cache'])
    fig.suptitle('G1. Tempos reais e simulados por grupo, com as mesmas classes em cada linha',
                 x=.06, ha='left', fontsize=13.5, color=TINTA, fontweight='bold')
    fig.legend(handles=[Patch(color=COR_REAL, label=f"Dados reais ({dados['pares_reais']} pares)"),
                        Patch(color=COR_SIMULADO, label=f"Dados simulados ({dados['pares_simulados']} pares)")],
               loc='upper left', bbox_to_anchor=(.05, .965), ncol=2, frameon=False, fontsize=10, labelcolor=TINTA)
    fig.tight_layout(rect=(0, 0, 1, .945), h_pad=1.6)
    return fig


def numero_br(valor, casas=2):
    return f'{valor:.{casas}f}'.replace('.', ',')


def linha_tabela(serie, origem, forma):
    celulas = [forma['n'], numero_br(forma['media']), numero_br(forma['mediana']),
               numero_br(forma['desvio_padrao_amostral']), numero_br(forma['minimo']),
               numero_br(forma['maximo']), numero_br(forma['assimetria']), len(forma['pares_fora_cercas_iqr'])]
    tds = ''.join(f'<td>{c}</td>' for c in celulas)
    return f"<tr><th scope=\"row\">{serie['rotulo']} ({serie['unidade']})</th><td>{origem}</td>{tds}</tr>"


def fragmento_html(dados):
    """Texto, figura e tabela do G1. Os números vêm do JSON para não divergir do gráfico."""
    sem, com = dados['series']['sem_cache'], dados['series']['com_cache']
    real, simulado, cache = sem['real']['forma'], sem['simulado']['forma'], com['real']['forma']
    extremos = ', '.join(str(p) for p in real['pares_fora_cercas_iqr'])
    vezes = f"{int(round(real['mediana'] * 1000 / cache['mediana'], -3)):,}".replace(',', '.')
    linhas = '\n'.join(linha_tabela(s, origem, s[chave]['forma'])
                       for s in dados['series'].values()
                       for chave, origem in (('real', 'Real'), ('simulado', 'Simulado')))
    aviso = ''
    if dados['origem_simulados'] != 'rq104':
        aviso = ('<p class="aviso"><strong>Dados simulados provisórios.</strong> Gerados pelo algoritmo definido '
                 'na #103 até a publicação do gerador da #104, que os substitui ao reconstruir o dashboard.</p>\n')
    return f"""<p>Sem cache, os tempos reais são assimétricos à direita (coeficiente de assimetria {numero_br(real['assimetria'])}), com mediana de {numero_br(real['mediana'])} ms e máximo de {numero_br(real['maximo'])} ms; os valores extremos são os pares {extremos}, os primeiros da coleta. Com cache, os tempos ficam perto de {numero_br(cache['mediana'])} µs, cerca de {vezes} vezes menores, e quase simétricos ({numero_br(cache['assimetria'])}). Como os dados não parecem normais, a simulação não impõe uma distribuição: sorteia pares observados completos, com reposição, mantendo {dados['pares_simulados'] // 2} pares por ordem de execução e semente {dados['semente']}; por isso a mediana simulada fica próxima ({numero_br(simulado['mediana'])} ms), mas os valores só repetem os observados. A diferença d, que os testes analisam, tem quase a mesma forma do tempo sem cache, porque o tempo com cache é desprezível perto dele.</p>
{aviso}<figure class="grafico">
  <img src="graficos/g1.svg" alt="Histogramas em seis painéis: tempo sem cache, tempo com cache e diferença pareada, com dados reais à esquerda e simulados à direita. Os valores exatos estão na tabela a seguir.">
</figure>
<details>
  <summary>Ver os valores em tabela</summary>
  <div class="tabela-rolavel">
    <table>
      <thead><tr><th scope="col">Série</th><th scope="col">Origem</th><th scope="col">n</th><th scope="col">Média</th><th scope="col">Mediana</th><th scope="col">Desvio padrão</th><th scope="col">Mínimo</th><th scope="col">Máximo</th><th scope="col">Assimetria</th><th scope="col">Extremos</th></tr></thead>
      <tbody>
{linhas}
      </tbody>
    </table>
  </div>
  <p class="notation">Extremos: valores fora das cercas de 1,5 × IQR, todos mantidos. Dados: <code>entregas/experimento-cache/RQ107/dados_visualizacao.json</code>.</p>
</details>"""


def executar(dados=DADOS, saida=SAIDA):
    conteudo = json.loads(Path(dados).read_text(encoding='utf-8'))
    saida = Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    fig = desenhar_g1(conteudo)
    # Texto como texto, sem data e com salt fixo: o SVG é pesquisável e reproduzível.
    with plt.rc_context({'svg.fonttype': 'none', 'svg.hashsalt': 'g1'}):
        fig.savefig(saida, format='svg', metadata={'Date': None})
    plt.close(fig)
    return saida


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dados', type=Path, default=DADOS)
    parser.add_argument('--saida', type=Path, default=SAIDA)
    args = parser.parse_args()
    try:
        print(f'RQ108: G1 salvo em {executar(args.dados, args.saida)}')
    except (OSError, KeyError, ValueError) as exc:
        sys.exit(f'G1 não gerado: {exc}')


if __name__ == '__main__':
    main()
