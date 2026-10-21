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
4. Para os repositórios incluídos, compara cada release da janela com a anterior (`compare`) e calcula o lead time nas duas variantes (RQ76).
5. Calcula frequência de deploy, lead time, CFR de CI, tempo de recuperação, as classes DORA e a classificação geral, e grava os CSVs em `dados/lab03/`.

**Retomada.** Toda resposta da API vai para `dados/.cache/lab03_rest/`. Se a coleta parar por rate limit, queda de rede ou `Ctrl+C`, rode o **mesmo comando** de novo: o que já foi baixado sai do cache, sem gastar cota. No início, o script consulta `GET /rate_limit` (não consome cota) e mostra quantas requisições restam. Quando a cota está acabando (restam tantas quanto `trabalhadores`), ele espera sozinho até o `X-RateLimit-Reset`. Erros 5xx e quedas de rede são repetidos com backoff exponencial (1 s, 2 s, 4 s, …, até 60 s). Detalhes em [RQ78](entregas/laboratorio-03/sprint-01/RQ78_cache_rate_limit_retry.md).

**Configuração** (`config/pipeline.json`):

| Chave | Significado |
|---|---|
| `janela.inicio`, `janela.fim` | Janela de observação, com as duas datas inclusivas. **Provisória: 2025-10-01 a 2026-09-30, até o professor confirmar as datas oficiais.** Se mudar a janela, as URLs mudam e o cache antigo não é reaproveitado |
| `meta_repositorios` | Tamanho da amostra (100 na S01, ≥ 300 na S02) |
| `criterios.minimo_releases`, `criterios.minimo_runs_validos` | Critério mínimo de inclusão do enunciado (5 e 50) |
| `limite_runs_por_repositorio` | Teto operacional de runs por repositório na janela (custo de API). Quem passa dele é descartado e aparece no funil |
| `limite_paginas_compare` | Máximo de páginas de 100 commits por `compare` entre releases (20 = 2.000 commits). Comparações maiores ficam marcadas como truncadas |
| `trabalhadores` | Quantos candidatos são avaliados em paralelo. O resultado é o mesmo da execução sequencial |
| `commits_via_git` | `true` obtém os commits entre releases e as datas das tags de um **clone git parcial** (só commits, sem árvores nem blobs), em vez de `compare` e `/commits/{sha}` na API. Exige o `git` no PATH. Se o clone falhar, aquele repositório usa a API. Padrão: `false` (S01) |
| `git.tempo_limite_segundos`, `git.clones_simultaneos`, `git.diretorio_clones` | Tempo máximo por operação do git (padrão 900), quantos clones existem ao mesmo tempo (padrão 2) e onde ficam. O clone é anônimo (o token não é usado) e a pasta é apagada assim que o repositório é avaliado |
| `diretorio_cache`, `diretorio_saida` | Onde ficam o cache da API e os CSVs gerados |

Para testar rapidamente, crie uma cópia da config com `"meta_repositorios": 3` e `"diretorio_saida"` apontando para outra pasta.

### Saídas

O dicionário de dados oficial, cobrindo todas as colunas de todos os CSVs da amostra final, está em [`dados/lab03_final/DICIONARIO.md`](dados/lab03_final/DICIONARIO.md) (gerado pela RQ84). O da amostra piloto continua em [`dados/lab03/DICIONARIO.md`](dados/lab03/DICIONARIO.md).

| Arquivo | Conteúdo |
|---|---|
| `dados/lab03/funil_selecao.csv` | Funil de seleção: quantos repositórios restaram em cada etapa |
| `dados/lab03/candidatos_avaliados.csv` | Cada candidato avaliado e o motivo do descarte ou da inclusão |
| `dados/lab03/metricas_repositorios.csv` | Uma linha por repositório da amostra, com as métricas |
| `dados/lab03/releases.csv` | Releases coletadas dos repositórios da amostra, incluindo as anteriores à janela, que servem de base para o lead time |
| `dados/lab03/workflow_runs.csv.gz` | Workflow runs de `push` no default branch, dentro da janela |
| `dados/lab03/lead_time_releases.csv` | Lead time de cada release da janela, a release anterior usada e o motivo quando não há lead time (RQ76) |
| `dados/lab03/commits_releases.csv.gz` | Commits de cada release (sha, data de autoria, 1ª linha da mensagem), vindos do `compare` (RQ76) |
| `dados/lab03/intervalos_runs.csv` | Auditoria da coleta de runs: cada intervalo consultado, total informado, runs coletados e se foi subdividido (RQ77) |
| `dados/lab03/resumo_execucao.json` | Configuração usada, data da coleta e contadores de requisições e de cache |

### RQ82 — Coleta final (≥ 300 repositórios)

```bash
python -u codigo-fonte/rq82_amostra_final.py --config config/rq82_amostra_final.json
```

Retomável (checkpoint por repositório + cache HTTP) e feito para rodar sem supervisão: falha temporária da API não derruba a coleta (o repositório é refeito numa nova passada, `--passadas`, padrão 3), o rate limit é esperado sozinho e cada linha do log leva a hora. Os commits entre releases e as datas das tags vêm de um clone git parcial (`commits_via_git`), o que elimina as chamadas mais numerosas da coleta; repositórios com mais de 20.000 runs são descartados logo após a primeira página de cada mês, sem baixar até o limite. Detalhes e medições em [RQ82](entregas/laboratorio-03/sprint-02/RQ82_amostra_final.md).

### RQ83 — Calcular as variantes obrigatórias

Após exportar a amostra final da RQ82, execute sem token ou acesso à API:

```bash
python codigo-fonte/rq83_metricas_variantes.py
```

Calcula frequência, lead time por release e por commit, CFR de CI e de
entrega, recuperação, quartis e censura. Grava os resultados em
`dados/lab03_final/rq83/`. Entradas ausentes ou incompletas são informadas;
o piloto parcial não substitui a amostra final.
Definições, comandos e limitações em
[RQ83](entregas/laboratorio-03/sprint-02/RQ83_metricas_variantes.md).

### RQ89 — Avaliar a heurística de release corretiva

Depois que o consenso da amostra-ouro (RQ88) estiver num CSV (`id_release`, `corretiva`), compare as versões da heurística de `codigo-fonte/metricas/corretiva.py`:

```bash
python codigo-fonte/validacao/rq89_heuristica.py avaliar --consenso dados/lab03_final/amostra_ouro/consenso_releases.csv
```

Grava precisão, recall e F1 por versão e a lista de erros em `dados/lab03_final/amostra_ouro/`. Para recalcular o CFR de entrega com outra versão: `python codigo-fonte/rq83_metricas_variantes.py --heuristica correcao_de_defeito_v3`. Detalhes em [RQ89](entregas/laboratorio-03/sprint-02/RQ89_heuristica_corretiva.md).

### RQ84 — Consolidar o dataset final

Depois da RQ83, junta coleta, métricas nas variantes e consenso da amostra-ouro num CSV único (`dados/lab03_final/dataset_final.csv`), regenera o dicionário de dados e confere se toda coluna de todo CSV final está documentada:

```bash
python codigo-fonte/rq84_dataset_final.py
```

Detalhes em [RQ84](entregas/laboratorio-03/sprint-02/RQ84_dataset_final_dicionario.md).

### RQ91 — Deployment Frequency e classificação DORA

Reconta as releases da amostra final, confere as métricas exportadas e gera
mediana, quartis, IQR, distribuição das classes de frequência e gráficos.
Complementa a análise com concentração das releases, extremos mantidos na
amostra e painel mensal com zeros explícitos e taxas normalizadas pelos dias
observados. Inclui auditoria dos filtros e confronto descritivo com a H1:

```bash
python codigo-fonte/analise/rq91_deployment_frequency.py
```

Execução local, sem token ou nova coleta. Resultados e discussão da H1 em
[RQ91 — relatório](entregas/laboratorio-03/sprint-03/RQ91/RELATORIO.md).
As classes são as da **frequência**, pelos cortes da disciplina; a classificação
geral das quatro métricas é distinta. A confirmação da janela permanece
registrada como pendência nos dados de entrada.

### RQ92 — Tempo de recuperação após falhas

Reconstitui os episódios de falha por workflow, reconcilia a coleta e analisa
mediana/IQR, classes de recuperação e censuras à esquerda e à direita:

```bash
python codigo-fonte/analise/rq92_tempo_recuperacao.py
```

Sucessos encerrados após o fim da janela são censurados nesta análise, com
auditoria antes/depois. Repositórios sem episódios completos ficam como
**Não estimável**. Relatório escrito, gráficos, episódios e resultados em
[RQ92 — análise da recuperação](entregas/laboratorio-03/sprint-03/RQ92/RELATORIO.md).
O comando usa os CSVs locais e não requer token.
Inclui limites descritivos de recuperação em 1 h, 24 h e 7 dias, com casos
indeterminados por censura, e diagnóstico da mediana em subconjuntos com
pelo menos 5 e 10 episódios completos. A definição principal permanece igual.

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
| `codigo-fonte/coleta/git_local.py` | Clone git parcial (só commits e tags): commits entre releases e datas das tags sem gastar cota da API |
| `codigo-fonte/coleta/coleta_dora.py` | Coleta de workflows, releases, runs (subdivisão mensal da janela, e por dia/hora quando um intervalo chega ao teto de 1.000, RQ77) e `compare` entre releases (RQ76) |
| `codigo-fonte/metricas/ci.py` | CFR (a) e tempo de recuperação (RQ79) |
| `codigo-fonte/metricas/lead_time.py` | Lead time por release (a) e por commit (b) (RQ76) |
| `codigo-fonte/metricas/dora.py` | Frequência de deploy e classificação DORA |
| `codigo-fonte/metricas/corretiva.py` | Versões da heurística de release corretiva, para o CFR (b) (RQ89) |
| `codigo-fonte/pipeline_dora.py` | Orquestra tudo num único comando (RQ80) |
