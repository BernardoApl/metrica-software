import csv
import matplotlib.pyplot as plt
from pathlib import Path


def gerar_grafico_idade_vs_releases():
    # Caminho do CSV consolidado
    diretorio_raiz = Path(__file__).resolve().parents[2]
    caminho_csv = diretorio_raiz / "dados" / "repositorios_consolidados.csv"

    idade_anos = []
    total_releases = []

    # Leitura dos dados
    with open(caminho_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # Usamos float para idade e int para releases
                idade = float(row["RQ01_Idade_Anos"])
                rel = int(row["RQ03_Total_Releases"])
                idade_anos.append(idade)
                total_releases.append(rel)
            except (ValueError, KeyError, TypeError):
                continue  # Ignora linhas com dados ausentes ou mal formatados

    # Configuração do Gráfico
    plt.figure(figsize=(10, 6))

    # Criando o scatter plot (pontos vermelhos para diferenciar do gráfico anterior)
    plt.scatter(idade_anos, total_releases, alpha=0.5, color='#d62728', edgecolors='black')

    # Aplicando escala logarítmica apenas no eixo Y (Releases)
    plt.yscale('symlog')

    # Estilização
    plt.title('Relação entre Idade do Repositório e Total de Releases', fontsize=14)
    plt.xlabel('Idade do Repositório (Anos)', fontsize=12)
    plt.ylabel('Total de Releases (Escala Logarítmica)', fontsize=12)
    plt.grid(True, which="both", ls="--", alpha=0.3)

    # Salva a imagem na pasta de dados
    caminho_saida = diretorio_raiz / "dados" / "rq22_idade_vs_releases.png"
    plt.savefig(caminho_saida, dpi=300, bbox_inches='tight')
    print(f"Gráfico gerado com sucesso em: {caminho_saida}")

    # Exibe o gráfico na tela
    plt.show()


if __name__ == "__main__":
    gerar_grafico_idade_vs_releases()