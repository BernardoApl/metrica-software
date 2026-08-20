import json
import csv
import sys
from pathlib import Path


def carregar_dados_json(caminho_arquivo: Path) -> list:
    """Lê o arquivo JSON consolidado e retorna a lista de repositórios."""
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            dados = json.load(f)
            return dados.get("repositorios", [])
    except FileNotFoundError:
        print(f"Erro: O arquivo {caminho_arquivo} não foi encontrado.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Erro: O arquivo {caminho_arquivo} não contém um JSON válido.")
        sys.exit(1)


def validar_e_consolidar(repositorios: list) -> list:
    """Aplica as validações de consistência e mapeia os dados para o formato CSV."""
    dados_validados = []

    # Validação 1: O Lab01S02 exige a paginação completa (1.000 repositórios)
    if len(repositorios) != 1000:
        print(f"[AVISO] O número total de repositórios é {len(repositorios)}, o esperado era 1000.")

    for repo in repositorios:
        nome = repo.get("nome_completo", "Desconhecido")

        # Extração das Métricas
        idade_anos = repo.get("rq01_idade_anos")
        total_prs = repo.get("rq02_pull_requests_aceitos", 0)
        total_releases = repo.get("rq03_total_releases", 0)
        atualizacao_dias = repo.get("rq04_dias_desde_ultima_atualizacao")
        linguagem = repo.get("rq05_linguagem_primaria")
        razao_issues = repo.get("rq06_razao_fechadas_total")

        # Tratamento de valores ausentes/nulos
        if linguagem is None:
            linguagem = "Sem linguagem definida"

        if razao_issues is None:
            razao_issues = "N/A"  # Repositórios que não utilizam a feature de Issues

        # Validação 2: Inconsistências (Outliers lógicos)
        if idade_anos is not None and idade_anos < 0:
            print(f"[ALERTA] Idade negativa encontrada no repositório {nome}: {idade_anos} anos.")

        if atualizacao_dias is not None and atualizacao_dias < 0:
            print(f"[ALERTA] Atualização negativa encontrada no repositório {nome}: {atualizacao_dias} dias.")

        # Monta a linha estruturada
        dados_validados.append({
            "Repositorio": nome,
            "RQ01_Idade_Anos": idade_anos,
            "RQ02_PRs_Aceitas": total_prs,
            "RQ03_Total_Releases": total_releases,
            "RQ04_Dias_Ultima_Atualizacao": atualizacao_dias,
            "RQ05_Linguagem_Primaria": linguagem,
            "RQ06_Razao_Issues_Fechadas": razao_issues
        })

    return dados_validados


def exportar_csv(dados: list, caminho_saida: Path):
    """Gera o arquivo CSV consolidado."""
    if not dados:
        print("Nenhum dado para exportar.")
        return

    colunas = dados[0].keys()

    # Cria o diretório de saída caso não exista
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(caminho_saida, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=colunas)
            writer.writeheader()
            writer.writerows(dados)
        print(f"Sucesso: {len(dados)} repositórios exportados para '{caminho_saida}'.")
    except OSError as e:
        print(f"Erro ao salvar o arquivo CSV: {e}")


def main():
    # Resolve os caminhos relativos ao diretório raiz do projeto
    diretorio_raiz = Path(__file__).resolve().parents[2]
    caminho_entrada = diretorio_raiz / "dados" / "lab01s01_unificado.json"
    caminho_saida = diretorio_raiz / "dados" / "repositorios_consolidados.csv"

    print("Iniciando a consolidação dos dados...")
    repositorios_brutos = carregar_dados_json(caminho_entrada)
    dados_processados = validar_e_consolidar(repositorios_brutos)
    exportar_csv(dados_processados, caminho_saida)


if __name__ == "__main__":
    main()