import csv
import matplotlib.pyplot as plt
from pathlib import Path


def gerar_grafico_prs_vs_releases():
    # Caminho do CSV
    diretorio_raiz = Path(__file__).resolve().parents[2]
    caminho_csv = diretorio_raiz / "dados" / "repositorios_consolidados.csv"

    prs_aceitas = []
    total_releases = []

    # Leitura dos dados
    with open(caminho_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                pr = int(row["RQ02_PRs_Aceitas"])
                rel = int(row["RQ03_Total_Releases"])
                prs_aceitas.append(pr)
                total_releases.append(rel)
            except (ValueError, KeyError):
                continue  # Pula linhas com dados ausentes

    # Configuração do Gráfico de Dispersão
    plt.figure(figsize=(10, 6))

    # alpha=0.5 deixa os pontos transparentes, ajudando a ver onde há aglomeração
    plt.scatter(prs_aceitas, total_releases, alpha=0.5, color='#2ca02c', edgecolors='black')

    # Aplicando escala logarítmica (ESSENCIAL para dados do GitHub devido aos outliers)
    plt.xscale('symlog')
    plt.yscale('symlog')

    # Estilização
    plt.title('Relação entre Pull Requests Aceitas e Total de Releases (1.000 Repositórios)', fontsize=14)
    plt.xlabel('Total de Pull Requests Aceitas (Escala Logarítmica)', fontsize=12)
    plt.ylabel('Total de Releases (Escala Logarítmica)', fontsize=12)
    plt.grid(True, which="both", ls="--", alpha=0.3)

    # Salva a imagem na pasta de dados
    caminho_saida = diretorio_raiz / "dados" / "rq20_prs_vs_releases.png"
    plt.savefig(caminho_saida, dpi=300, bbox_inches='tight')
    print(f"Gráfico gerado com sucesso em: {caminho_saida}")

    # Exibe o gráfico na tela
    plt.show()


if __name__ == "__main__":
    gerar_grafico_prs_vs_releases()