# metrica-software

Relatorio Sprint 3 - https://docs.google.com/document/d/12HiJGK0eD4MD7Lw4Nu5eoH-weQYHP1wi-tA8pVOEQvs/edit?tab=t.0

## LAB03 — Mineração de métricas DORA

![testes](https://github.com/BernardoApl/metrica-software/actions/workflows/testes.yml/badge.svg)

### Pré-requisitos

- Python 3.11 ou mais recente.
- Um token do GitHub (escopo `public_repo` é suficiente), em variável de ambiente ou num arquivo `.env` na raiz (que já está no `.gitignore`). **Nunca** commite o token.

```bash
pip install -r requirements.txt
```

```bash
export GITHUB_TOKEN=ghp_seu_token
```

No PowerShell, use `$env:GITHUB_TOKEN = "ghp_seu_token"`.

### Executar o pipeline (um único comando)

```bash
python codigo-fonte/pipeline_dora.py --config config/pipeline.json
```

O que o comando faz, em ordem:

1. Se o CSV de metadados configurado em `candidatos.metadados` não existir, roda a busca de candidatos (`rq73_coletar_candidatos.py`) e a coleta de metadados (`rq74_metadados_repositorios.py`).
2. Descarta, sem chamar a API, forks, repositórios arquivados, desabilitados, vazios ou sem default branch.
3. Percorre os candidatos por número de estrelas e aplica, do critério mais barato para o mais caro: usa GitHub Actions → ≥ 5 releases publicadas na janela → ≥ 50 workflow runs válidos no default branch. Para quando chega a `meta_repositorios`.
4. Calcula frequência de deploy, CFR de CI, tempo de recuperação e as classes DORA, e grava os CSVs em `dados/lab03/`.

**Retomada.** Toda resposta da API vai para `dados/.cache/lab03_rest/`. Se a coleta parar por rate limit, queda de rede ou `Ctrl+C`, rode o **mesmo comando** de novo: o que já foi baixado sai do cache, sem gastar cota. No início, o script consulta `GET /rate_limit` (não consome cota) e mostra quantas requisições restam. Quando a cota está acabando (restam tantas quanto `trabalhadores`), ele espera sozinho até o `X-RateLimit-Reset`. Erros 5xx e quedas de rede são repetidos com backoff exponencial (1 s, 2 s, 4 s, …, até 60 s). Detalhes em [RQ78](entregas/laboratorio-03/sprint-01/RQ78_cache_rate_limit_retry.md).

**Configuração** (`config/pipeline.json`):

| Chave | Significado |
|---|---|
| `janela.inicio`, `janela.fim` | Janela de observação, com as duas datas inclusivas. **Provisória: 2025-10-01 a 2026-09-30, até o professor confirmar as datas oficiais.** Se mudar a janela, as URLs mudam e o cache antigo não é reaproveitado |
| `meta_repositorios` | Tamanho da amostra (100 na S01, ≥ 300 na S02) |
| `criterios.minimo_releases`, `criterios.minimo_runs_validos` | Critério mínimo de inclusão do enunciado (5 e 50) |
| `limite_runs_por_repositorio` | Teto operacional de runs por repositório na janela (custo de API). Quem passa dele é descartado e aparece no funil |
| `trabalhadores` | Quantos candidatos são avaliados em paralelo. O resultado é o mesmo da execução sequencial |
| `diretorio_cache`, `diretorio_saida` | Onde ficam o cache da API e os CSVs gerados |

Para testar rapidamente, crie uma cópia da config com `"meta_repositorios": 3` e `"diretorio_saida"` apontando para outra pasta.

### Saídas

O dicionário de dados de cada coluna está em [`dados/lab03/DICIONARIO.md`](dados/lab03/DICIONARIO.md).

| Arquivo | Conteúdo |
|---|---|
| `dados/lab03/funil_selecao.csv` | Funil de seleção: quantos repositórios restaram em cada etapa |
| `dados/lab03/candidatos_avaliados.csv` | Cada candidato avaliado e o motivo do descarte ou da inclusão |
| `dados/lab03/metricas_repositorios.csv` | Uma linha por repositório da amostra, com as métricas |
| `dados/lab03/releases.csv` | Releases coletadas dos repositórios da amostra, incluindo as anteriores à janela, que servem de base para o lead time |
| `dados/lab03/workflow_runs.csv.gz` | Workflow runs de `push` no default branch, dentro da janela |
| `dados/lab03/intervalos_runs.csv` | Auditoria da coleta de runs: cada intervalo consultado, total informado, runs coletados e se foi subdividido (RQ77) |
| `dados/lab03/resumo_execucao.json` | Configuração usada, data da coleta e contadores de requisições e de cache |

### Testes

```bash
pytest --cov=metricas --cov-report=term-missing
```

A suíte padrão (`pytest.ini`) roda `codigo-fonte/testes`. Os testes não acessam a rede: o cliente da API é substituído por respostas sintéticas. O GitHub Actions ([`.github/workflows/testes.yml`](.github/workflows/testes.yml)) roda a mesma suíte a cada push e pull request, e falha se a cobertura do módulo `metricas` ficar abaixo de 80%.

### Estrutura do código do LAB03

| Caminho | Responsabilidade |
|---|---|
| `codigo-fonte/coleta/rq73_coletar_candidatos.py` | Busca de candidatos fatiada por faixas de estrelas |
| `codigo-fonte/coleta/rq74_metadados_repositorios.py` | Metadados via GraphQL (estrelas, linguagem, idade, contribuidores) |
| `codigo-fonte/coleta/cliente_rest.py` | Cliente REST próprio: cache, paginação, rate limit e backoff |
| `codigo-fonte/coleta/coleta_dora.py` | Coleta de workflows, releases e runs, com subdivisão mensal da janela (e por dia/hora quando um intervalo chega ao teto de 1.000, RQ77) |
| `codigo-fonte/metricas/ci.py` | CFR (a) e tempo de recuperação (RQ79) |
| `codigo-fonte/metricas/dora.py` | Frequência de deploy e classificação DORA |
| `codigo-fonte/pipeline_dora.py` | Orquestra tudo num único comando (RQ80) |
