"""RQ109: reconstrói o dashboard do LAB04 com um único comando e o abre no navegador."""
from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # permite executar como script

from analise import rq107_dados_visualizacao as rq107  # noqa: E402
from analise import rq104_gerador_simulacao as rq104  # noqa: E402
from analise import rq105_testes_pareados as rq105  # noqa: E402
from analise import rq106_dados_g2 as rq106  # noqa: E402
from frontend import rq108_g1 as rq108  # noqa: E402
from frontend import rq111_g3 as rq111  # noqa: E402
from frontend import rq112_resultados_reais as rq112  # noqa: E402
from frontend import rq114_g4 as rq114  # noqa: E402
from frontend import rq115_conclusao as rq115  # noqa: E402

PAGINA = Path(__file__).resolve().parent / 'index.html'
INICIO_G1, FIM_G1 = '<!-- G1:INICIO (gerado por rq109_dashboard.py) -->', '<!-- G1:FIM -->'


def inserir_g1(html, fragmento):
    """Troca só o bloco entre marcadores; o restante da página continua editável à mão."""
    inicio, fim = html.find(INICIO_G1), html.find(FIM_G1)
    if inicio < 0 or fim < inicio:
        raise ValueError('Marcadores do G1 ausentes em index.html.')
    return f'{html[:inicio + len(INICIO_G1)]}\n{fragmento}\n{html[fim:]}'


def construir(pagina=PAGINA, dados=rq107.SAIDA, grafico=rq108.SAIDA, **kwargs_rq107):
    conteudo = rq107.executar(dados, **kwargs_rq107)
    rq108.executar(dados, grafico)
    pagina = Path(pagina)
    pagina.write_text(inserir_g1(pagina.read_text(encoding='utf-8'), rq108.fragmento_html(conteudo)), encoding='utf-8')
    return conteudo['origem_simulados']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sem-abrir', action='store_true', help='só reconstrói, sem abrir o navegador')
    args = parser.parse_args()
    try:
        rq104.executar()  # dados simulados oficiais (semente 104), lidos pela #107
        rq105.executar()  # t pareado e Wilcoxon pareado
        rq106.executar()  # dados do G2
        origem = construir()
        rq111.executar()  # G3 reutiliza a execução salva; não repete 10.000 simulações
        rq112.executar()  # resultados reais validados e testes pareados da #105
        rq114.executar()  # G4 reutiliza a execução salva da #113 (≈ 2 min para refazer)
        rq115.executar()  # conclusão e recomendação a partir dos resultados salvos
    except (ValueError, OSError, KeyError) as exc:
        sys.exit(f'Dashboard não construído: {exc}')
    print(f'Dashboard reconstruído em {PAGINA} (simulados: {origem})')
    if not args.sem_abrir:
        webbrowser.open(PAGINA.as_uri())


if __name__ == '__main__':
    main()
