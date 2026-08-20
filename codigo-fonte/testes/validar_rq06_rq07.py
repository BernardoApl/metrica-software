import csv
import statistics
from collections import defaultdict
from pathlib import Path


def validar_rq06_rq07():
    # Caminho do CSV gerado no passo anterior
    diretorio_raiz = Path(__file__).resolve().parents[2]
    caminho_csv = diretorio_raiz / "dados" / "repositorios_consolidados.csv"

    if not caminho_csv.exists():
        print(f"Erro: Arquivo {caminho_csv} não encontrado. Rode a consolidação primeiro.")
        return

    # Variáveis para RQ06
    rq06_validas = []
    rq06_ausentes = 0
    rq06_inconsistentes = []

    # Variáveis para RQ07
    repos_sem_linguagem = 0
    linguagens_distintas = set()
    metricas_por_linguagem = defaultdict(lambda: {"prs": [], "releases": [], "atualizacao": []})

    with open(caminho_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        linhas = list(reader)
        total_repos = len(linhas)

        for row in linhas:
            nome = row["Repositorio"]

            # --- Validação RQ06 (Issues) ---
            razao = row.get("RQ06_Razao_Issues_Fechadas")
            if razao == "N/A" or not razao:
                rq06_ausentes += 1
            else:
                try:
                    razao_float = float(razao)
                    # A razão deve estar sempre entre 0.0 (0%) e 1.0 (100%)
                    if 0.0 <= razao_float <= 1.0:
                        rq06_validas.append(razao_float)
                    else:
                        rq06_inconsistentes.append((nome, razao_float))
                except ValueError:
                    rq06_ausentes += 1

            # --- Validação RQ07 (Linguagens x Métricas) ---
            linguagem = row.get("RQ05_Linguagem_Primaria")

            if linguagem == "Sem linguagem definida" or not linguagem:
                repos_sem_linguagem += 1
            else:
                linguagens_distintas.add(linguagem)
                try:
                    prs = int(row.get("RQ02_PRs_Aceitas", 0))
                    releases = int(row.get("RQ03_Total_Releases", 0))
                    atualizacao = float(row.get("RQ04_Dias_Ultima_Atualizacao", 0))

                    metricas_por_linguagem[linguagem]["prs"].append(prs)
                    metricas_por_linguagem[linguagem]["releases"].append(releases)
                    metricas_por_linguagem[linguagem]["atualizacao"].append(atualizacao)
                except ValueError:
                    pass

    # --- Relatório de Saída ---
    print("=" * 50)
    print(f"VALIDAÇÃO DE DADOS NOS {total_repos} REPOSITÓRIOS")
    print("=" * 50)

    # Print RQ06
    print("\n--- RQ06: Percentual de Issues Fechadas ---")
    print(f"Valores válidos contabilizados: {len(rq06_validas)}")
    print(f"Valores ausentes (Repos sem issues ou N/A): {rq06_ausentes}")
    if rq06_inconsistentes:
        print(f"Inconsistências (Razão > 1 ou < 0): {len(rq06_inconsistentes)} encontradas!")
        for inc in rq06_inconsistentes:
            print(f"  - {inc[0]}: {inc[1]}")
    else:
        print("Inconsistências (Razão > 1 ou < 0): Nenhuma encontrada. Dados íntegros!")

    if rq06_validas:
        print(f"Distribuição -> Mínimo: {min(rq06_validas)}, Máximo: {max(rq06_validas)}")
        print(f"Distribuição -> Mediana: {statistics.median(rq06_validas):.4f}")

    # Print RQ07
    print("\n--- RQ07: Métricas por Linguagem ---")
    print(f"Repositórios sem linguagem mapeada: {repos_sem_linguagem}")
    print(f"Linguagens distintas encontradas: {len(linguagens_distintas)}")

    print("\nTop 5 Linguagens por volume de repositórios (Distribuição de PRs):")
    # Ordena linguagens pelo número de repositórios
    top_linguagens = sorted(metricas_por_linguagem.items(), key=lambda x: len(x[1]["prs"]), reverse=True)[:5]

    for lang, metricas in top_linguagens:
        qtd_repos = len(metricas["prs"])
        mediana_prs = statistics.median(metricas["prs"])
        max_prs = max(metricas["prs"])  # Ajuda a achar Outliers
        print(f" - {lang} ({qtd_repos} repos): Mediana de PRs = {mediana_prs:.1f} | Outlier Máximo = {max_prs}")


if __name__ == "__main__":
    validar_rq06_rq07()