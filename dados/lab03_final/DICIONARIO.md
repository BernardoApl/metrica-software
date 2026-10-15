# Dicionário de dados — LAB03 (amostra final)

> Gerado por `python codigo-fonte/rq84_dataset_final.py` (RQ84) a partir das definições em `rq84_dataset_final.py`. **Não edite à mão**: altere as definições e gere de novo. A mesma informação está em `dicionario_dados.csv`.

- Janela de observação: ver `resumo_execucao.json` (`config.janela`).
- Datas em ISO 8601 UTC. Lead time em **dias**, recuperação em **horas**, CFR como **fração** de 0 a 1, frequência em **releases por semana**.
- Célula vazia = **indefinido** (não é zero). Ex.: repositório sem falhas tem recuperação vazia; fora da amostra-ouro, `tipo_projeto` é vazio.
- Mediana e quartis usam interpolação linear (tipo 7).
- Tabela de referência DORA da RQ 07 (cortes fixos da disciplina): frequência ≥ 7/sem Elite, ≥ 1 High, ≥ 1/mês Medium; lead time < 1 dia Elite, < 7 High, < 30 Medium; CFR ≤ 15% Elite, ≤ 30% High, ≤ 45% Medium; recuperação < 1 h Elite, < 24 h High, < 1 semana Medium; o resto é Low.

## Arquivos

| Arquivo | Conteúdo | Gerado por |
|---|---|---|
| [`dataset_final.csv`](#dataset_finalcsv) | **Dataset final para a análise (S03)**: uma linha por repositório, com metadados, fatores da RQ 06, métricas das RQ 01 a 04 em todas as variantes, classes DORA da combinação de referência C1 e marcadores de qualidade. Métricas vêm da RQ83; metadados, da coleta | RQ84 `rq84_dataset_final.py` |
| [`metricas_repositorios.csv`](#metricas_repositorioscsv) | métricas calculadas pelo pipeline durante a coleta (uma linha por repositório da amostra) | RQ82/RQ80 `pipeline_dora.py` |
| [`candidatos_avaliados.csv`](#candidatos_avaliadoscsv) | cada candidato avaliado e o motivo do descarte ou da inclusão | RQ82/RQ80 `pipeline_dora.py` |
| [`funil_selecao.csv`](#funil_selecaocsv) | funil de seleção: quantos repositórios restaram em cada etapa | RQ82/RQ80 `pipeline_dora.py` |
| [`releases.csv`](#releasescsv) | todas as releases dos repositórios da amostra, inclusive as anteriores à janela (base do `compare`) | RQ82 `GET /repos/{o}/{r}/releases` |
| [`workflow_runs.csv.gz`](#workflow_runscsvgz) | workflow runs de `push` no default branch, criados na janela (CSV compactado; `pandas.read_csv` lê direto) | RQ82/RQ77 `GET /actions/runs?branch=…&event=push&created=…` |
| [`intervalos_runs.csv`](#intervalos_runscsv) | auditoria da coleta de runs: cada intervalo consultado | RQ77 `coleta_dora.coletar_runs` |
| [`lead_time_releases.csv`](#lead_time_releasescsv) | lead time de cada release da janela (definição principal) | RQ76 `pipeline_dora.calcular_lead_time` |
| [`commits_releases.csv.gz`](#commits_releasescsvgz) | commits de cada release, do `compare` com a anterior (CSV compactado) | RQ76 `GET /compare/{anterior}...{R}` |
| [`tags.csv`](#tagscsv) | tags dos repositórios da amostra, com a data do commit apontado (variante de deploy da RQ 07) | RQ75 `GET /tags` + `GET /commits/{sha}` |
| [`rq83/metricas_variantes.csv`](#rq83metricas_variantescsv) | métricas das RQ 01 a 04 em todas as variantes obrigatórias, com quartis | RQ83 `rq83_metricas_variantes.py` |
| [`rq83/cfr_entrega_releases.csv`](#rq83cfr_entrega_releasescsv) | avaliação de cada release da janela no CFR (b) | RQ83 `metricas/variantes.cfr_entrega` |
| [`rq83/episodios_recuperacao.csv`](#rq83episodios_recuperacaocsv) | episódios de falha por workflow (evidência da RQ 04) | RQ83 / RQ79 `metricas/ci.episodios_de_falha` |
| [`amostra_ouro/sorteio_repositorios.csv`](#amostra_ourosorteio_repositorioscsv) | os 60 repositórios sorteados para a validação manual (`random_state=42`) | RQ86 `validacao/rq86_amostra_ouro.py gerar` |
| [`amostra_ouro/sorteio_releases.csv`](#amostra_ourosorteio_releasescsv) | as releases sorteadas (5 por repositório) para rotular como corretiva ou não | RQ86 `validacao/rq86_amostra_ouro.py gerar` |
| [`amostra_ouro/consenso_repositorios.csv`](#amostra_ouroconsenso_repositorioscsv) | rótulos dos 3 avaliadores e consenso por repositório | RQ88 `validacao/rq88_concordancia.py` |
| [`amostra_ouro/consenso_releases.csv`](#amostra_ouroconsenso_releasescsv) | rótulos dos 3 avaliadores e consenso por release sorteada (referência do F1 da RQ89) | RQ88 `validacao/rq88_concordancia.py` |
| [`amostra_ouro/concordancia_fleiss.csv`](#amostra_ouroconcordancia_fleisscsv) | kappa de Fleiss por dimensão rotulada | RQ88 `validacao/rq88_concordancia.py` |
| [`amostra_ouro/pendencias_reuniao.csv`](#amostra_ouropendencias_reuniaocsv) | pauta da reunião de consenso (empates e divergências) | RQ88 `validacao/rq88_concordancia.py` |
| [`amostra_ouro/decisoes_reuniao.csv`](#amostra_ourodecisoes_reuniaocsv) | decisões da reunião de consenso (escrito pelo grupo) | grupo, conforme protocolo da RQ88 |
| [`amostra_ouro/avaliacao_heuristica.csv`](#amostra_ouroavaliacao_heuristicacsv) | precisão, recall e F1 de cada versão da heurística de release corretiva | RQ89 `validacao/rq89_heuristica.py avaliar` |
| [`amostra_ouro/erros_heuristica.csv`](#amostra_ouroerros_heuristicacsv) | falsos positivos e negativos de cada versão da heurística, com as evidências | RQ89 `validacao/rq89_heuristica.py avaliar` |

## `dataset_final.csv`

**Dataset final para a análise (S03)**: uma linha por repositório, com metadados, fatores da RQ 06, métricas das RQ 01 a 04 em todas as variantes, classes DORA da combinação de referência C1 e marcadores de qualidade. Métricas vêm da RQ83; metadados, da coleta. Gerado por RQ84 `rq84_dataset_final.py`.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `nome_completo` | texto | — | `owner/repo` (GraphQL `nameWithOwner`, RQ74). Chave de junção entre os arquivos |
| `url` | texto | — | GraphQL `url` |
| `estrelas` | inteiro | estrelas | GraphQL `stargazerCount` na coleta RQ74 |
| `linguagem` | texto | — | GraphQL `primaryLanguage.name` (vazio se o GitHub não detecta) |
| `criado_em` | data | — | GraphQL `createdAt` |
| `idade_anos` | real | anos | (data de referência da coleta RQ74 − `criado_em`) ÷ 365,25 |
| `contribuidores_total` | inteiro | pessoas | nº da última página de `GET /contributors?per_page=1&anon=true` (vazio se não coletado) |
| `branch_padrao` | texto | — | `defaultBranchRef.name`; só esse branch é considerado |
| `workflows_total` | inteiro | workflows | `total_count` de `GET /actions/workflows` |
| `estrelas_quartil` | categoria | Q1–Q4 | quartil de `estrelas` na amostra final: Q1 se ≤ P25, Q2 se ≤ P50, Q3 se ≤ P75, senão Q4 (empates vão para o quartil inferior) |
| `contribuidores_quartil` | categoria | Q1–Q4 | quartil de `contribuidores_total`, mesma regra; vazio se o valor é ausente |
| `idade_quartil` | categoria | Q1–Q4 | quartil de `idade_anos`, mesma regra |
| `na_amostra_ouro` | booleano | — | repositório sorteado para a validação manual (RQ86) |
| `tipo_projeto` | categoria | biblioteca_framework/aplicacao_servico/ferramenta_cli/outro | rótulo de consenso dos 3 avaliadores (RQ88); vazio fora da amostra-ouro |
| `entregas_reais` | categoria | sim/nao/incerto | consenso (RQ88): as releases representam entregas reais ao usuário?; vazio fora da amostra-ouro |
| `releases_janela` | inteiro | releases | releases com `draft = false`, `prerelease = false` e `published_at` dentro da janela (deploys, definição principal) |
| `prereleases_janela` | inteiro | releases | pré-releases publicadas na janela (variante da RQ 07) |
| `frequencia_deploy_semana` | real | releases/semana | RQ 01: `releases_janela` ÷ (dias da janela ÷ 7) |
| `lead_time_release_mediana_dias` | real | dias | RQ 02 (a): mediana, entre as releases, de `published_at` de R − `commit.author.date` do commit mais antigo de `compare/{anterior}...{R}` |
| `lead_time_release_q1_dias` | real | dias | 1º quartil da distribuição da variante (a) do repositório (interpolação linear, tipo 7) |
| `lead_time_release_q3_dias` | real | dias | 3º quartil da variante (a) |
| `lead_time_release_iqr_dias` | real | dias | `lead_time_release_q3_dias − lead_time_release_q1_dias` |
| `lead_time_commit_mediana_dias` | real | dias | RQ 02 (b): mediana, entre **todos** os commits de todas as releases, de `published_at` de R − `commit.author.date` |
| `lead_time_commit_q1_dias` | real | dias | 1º quartil da variante (b) |
| `lead_time_commit_q3_dias` | real | dias | 3º quartil da variante (b) |
| `lead_time_commit_iqr_dias` | real | dias | `lead_time_commit_q3_dias − lead_time_commit_q1_dias` |
| `releases_com_lead_time` | inteiro | releases | releases da janela com lead time calculado (entram na variante a) |
| `commits_com_lead_time` | inteiro | commits | commits que entram na variante (b) |
| `releases_sem_anterior` | inteiro | releases | primeira release da história do repositório: sem base para o `compare`, ignorada no lead time |
| `releases_sem_commits` | inteiro | releases | `compare` sem commits novos (ou só com datas posteriores à release), ignorada |
| `releases_compare_indisponivel` | inteiro | releases | `compare` com 404 (tag apagada/reescrita), 422 ou erro persistente, ignorada |
| `releases_compare_truncado` | inteiro | releases | `compare` incompleto (limite de páginas ou falha no meio da paginação) |
| `commits_negativos` | inteiro | commits | commits com `commit.author.date` posterior ao `published_at` da release, descartados das duas variantes |
| `runs_coletados` | inteiro | runs | runs de `push` no default branch criados na janela, de qualquer `conclusion` |
| `runs_validos` | inteiro | runs | `runs_falha + runs_sucesso` (push, default branch, janela, conclusão válida) |
| `runs_falha` | inteiro | runs | `conclusion` ∈ {`failure`, `timed_out`, `startup_failure`} |
| `runs_sucesso` | inteiro | runs | `conclusion = success` |
| `cfr_ci` | real | fração (0–1) | RQ 03 (a): `runs_falha ÷ runs_validos` |
| `cfr_entrega` | real | fração (0–1) | RQ 03 (b): `releases_falha_cfr ÷ releases_avaliadas_cfr` |
| `releases_avaliadas_cfr` | inteiro | releases | releases da janela publicadas mais de 7 dias antes do fim da janela (denominador do CFR b) |
| `releases_falha_cfr` | inteiro | releases | releases seguidas, em até 7 dias (inclusive), por uma release corretiva segundo a heurística |
| `releases_censuradas_cfr` | inteiro | releases | releases dos últimos 7 dias da janela, fora do denominador do CFR b (censura) |
| `releases_sem_semver` | inteiro | releases | releases da janela cuja tag não é SemVer `MAJOR.MINOR.PATCH` (a heurística por patch não as reconhece) |
| `heuristica_cfr_entrega` | categoria | — | versão da heurística de release corretiva usada no CFR (b) (`resumo_rq83.json`; RQ89) |
| `recuperacao_mediana_horas` | real | horas | RQ 04: mediana dos episódios completos de todos os workflows; episódio = `updated_at` do sucesso − `run_started_at` da 1ª falha do mesmo workflow |
| `recuperacao_q1_horas` | real | horas | 1º quartil dos episódios completos |
| `recuperacao_q3_horas` | real | horas | 3º quartil dos episódios completos |
| `recuperacao_iqr_horas` | real | horas | `recuperacao_q3_horas − recuperacao_q1_horas` |
| `episodios_falha` | inteiro | episódios | total de episódios de falha, incluindo os censurados |
| `episodios_completos` | inteiro | episódios | episódios usados na mediana (sem censura) |
| `episodios_censurados` | inteiro | episódios | episódios sem sucesso até o fim da janela (censura à direita) |
| `episodios_censura_esquerda` | inteiro | episódios | episódios em que o workflow já começa a janela falhando, sem sucesso anterior observado |
| `proporcao_episodios_censurados` | real | fração (0–1) | `episodios_censurados ÷ episodios_falha` |
| `classe_frequencia` | categoria | Elite/High/Medium/Low | tabela de referência da RQ 07 aplicada a `frequencia_deploy_semana` |
| `classe_lead_time` | categoria | Elite/High/Medium/Low | tabela da RQ 07 aplicada a `lead_time_release_mediana_dias` (variante a, combinação C1) |
| `classe_cfr` | categoria | Elite/High/Medium/Low | tabela da RQ 07 aplicada a `cfr_ci` (variante a, combinação C1) |
| `classe_recuperacao` | categoria | Elite/High/Medium/Low | tabela da RQ 07 aplicada a `recuperacao_mediana_horas` |
| `classe_geral` | categoria | Elite/High/Medium/Low | mediana das notas das quatro classes (Elite=4 … Low=1), arredondada para baixo; vazia se alguma for indefinida |
| `intervalos_no_teto` | inteiro | intervalos | intervalos de 1 segundo ainda com ≥ 1.000 runs (coleta de runs incompleta se > 0; RQ77) |
| `calculo_completo` | booleano | — | RQ83: todas as métricas do repositório calculadas sem pendência |
| `pendencias` | texto | — | RQ83: lista das pendências do repositório (ex.: compare truncado), separadas por `;` |

## `metricas_repositorios.csv`

métricas calculadas pelo pipeline durante a coleta (uma linha por repositório da amostra). Gerado por RQ82/RQ80 `pipeline_dora.py`.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `nome_completo` | texto | — | `owner/repo` (GraphQL `nameWithOwner`, RQ74). Chave de junção entre os arquivos |
| `url` | texto | — | GraphQL `url` |
| `estrelas` | inteiro | estrelas | GraphQL `stargazerCount` na coleta RQ74 |
| `linguagem` | texto | — | GraphQL `primaryLanguage.name` (vazio se o GitHub não detecta) |
| `criado_em` | data | — | GraphQL `createdAt` |
| `idade_anos` | real | anos | (data de referência da coleta RQ74 − `criado_em`) ÷ 365,25 |
| `contribuidores_total` | inteiro | pessoas | nº da última página de `GET /contributors?per_page=1&anon=true` (vazio se não coletado) |
| `branch_padrao` | texto | — | `defaultBranchRef.name`; só esse branch é considerado |
| `workflows_total` | inteiro | workflows | `total_count` de `GET /actions/workflows` |
| `releases_janela` | inteiro | releases | releases com `draft = false`, `prerelease = false` e `published_at` dentro da janela (deploys, definição principal) |
| `prereleases_janela` | inteiro | releases | pré-releases publicadas na janela (variante da RQ 07) |
| `frequencia_deploy_semana` | real | releases/semana | RQ 01: `releases_janela` ÷ (dias da janela ÷ 7) |
| `runs_coletados` | inteiro | runs | runs de `push` no default branch criados na janela, de qualquer `conclusion` |
| `runs_validos` | inteiro | runs | `runs_falha + runs_sucesso` (push, default branch, janela, conclusão válida) |
| `runs_falha` | inteiro | runs | `conclusion` ∈ {`failure`, `timed_out`, `startup_failure`} |
| `runs_sucesso` | inteiro | runs | `conclusion = success` |
| `cfr_ci` | real | fração (0–1) | RQ 03 (a): `runs_falha ÷ runs_validos` |
| `recuperacao_mediana_horas` | real | horas | RQ 04: mediana dos episódios completos de todos os workflows; episódio = `updated_at` do sucesso − `run_started_at` da 1ª falha do mesmo workflow |
| `episodios_falha` | inteiro | episódios | total de episódios de falha, incluindo os censurados |
| `episodios_completos` | inteiro | episódios | episódios usados na mediana (sem censura) |
| `episodios_censurados` | inteiro | episódios | episódios sem sucesso até o fim da janela (censura à direita) |
| `episodios_censura_esquerda` | inteiro | episódios | episódios em que o workflow já começa a janela falhando, sem sucesso anterior observado |
| `proporcao_episodios_censurados` | real | fração (0–1) | `episodios_censurados ÷ episodios_falha` |
| `intervalos_no_teto` | inteiro | intervalos | intervalos de 1 segundo ainda com ≥ 1.000 runs (coleta de runs incompleta se > 0; RQ77) |
| `lead_time_release_mediana_dias` | real | dias | RQ 02 (a): mediana, entre as releases, de `published_at` de R − `commit.author.date` do commit mais antigo de `compare/{anterior}...{R}` |
| `lead_time_commit_mediana_dias` | real | dias | RQ 02 (b): mediana, entre **todos** os commits de todas as releases, de `published_at` de R − `commit.author.date` |
| `releases_com_lead_time` | inteiro | releases | releases da janela com lead time calculado (entram na variante a) |
| `commits_com_lead_time` | inteiro | commits | commits que entram na variante (b) |
| `releases_sem_anterior` | inteiro | releases | primeira release da história do repositório: sem base para o `compare`, ignorada no lead time |
| `releases_sem_commits` | inteiro | releases | `compare` sem commits novos (ou só com datas posteriores à release), ignorada |
| `releases_compare_indisponivel` | inteiro | releases | `compare` com 404 (tag apagada/reescrita), 422 ou erro persistente, ignorada |
| `releases_compare_truncado` | inteiro | releases | `compare` incompleto (limite de páginas ou falha no meio da paginação) |
| `commits_negativos` | inteiro | commits | commits com `commit.author.date` posterior ao `published_at` da release, descartados das duas variantes |
| `classe_frequencia` | categoria | Elite/High/Medium/Low | tabela de referência da RQ 07 aplicada a `frequencia_deploy_semana` |
| `classe_lead_time` | categoria | Elite/High/Medium/Low | tabela da RQ 07 aplicada a `lead_time_release_mediana_dias` (variante a, combinação C1) |
| `classe_cfr` | categoria | Elite/High/Medium/Low | tabela da RQ 07 aplicada a `cfr_ci` (variante a, combinação C1) |
| `classe_recuperacao` | categoria | Elite/High/Medium/Low | tabela da RQ 07 aplicada a `recuperacao_mediana_horas` |
| `classe_geral` | categoria | Elite/High/Medium/Low | mediana das notas das quatro classes (Elite=4 … Low=1), arredondada para baixo; vazia se alguma for indefinida |

## `candidatos_avaliados.csv`

cada candidato avaliado e o motivo do descarte ou da inclusão. Gerado por RQ82/RQ80 `pipeline_dora.py`.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `posicao` | inteiro | — | ordem de avaliação (estrelas decrescentes, entre os aptos no pré-filtro) |
| `nome_completo` | texto | — | `owner/repo` (GraphQL `nameWithOwner`, RQ74). Chave de junção entre os arquivos |
| `estrelas` | inteiro | estrelas | GraphQL `stargazerCount` na coleta RQ74 |
| `motivo` | categoria | — | `incluido`, `sem_actions`, `poucas_releases`, `poucos_runs`, `runs_acima_do_limite`, `inacessivel` |
| `workflows_total` | inteiro | workflows | `total_count` de `GET /actions/workflows` |
| `releases_janela` | inteiro | releases | releases da janela até a etapa em que o candidato parou |
| `runs_total_informado` | inteiro | runs | `total_count` da busca de runs na janela inteira (satura em intervalos longos) |
| `runs_validos` | inteiro | runs | runs válidos até a etapa em que o candidato parou |
| `erro` | texto | — | status HTTP, quando `motivo = inacessivel` |

## `funil_selecao.csv`

funil de seleção: quantos repositórios restaram em cada etapa. Gerado por RQ82/RQ80 `pipeline_dora.py`.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `etapa` | texto | — | nome da etapa do funil |
| `criterio` | texto | — | regra aplicada na etapa |
| `entrada` | inteiro | repositórios | repositórios que chegaram à etapa |
| `removidos_na_etapa` | inteiro | repositórios | repositórios descartados na etapa |
| `aprovados` | inteiro | repositórios | `entrada − removidos_na_etapa` |

## `releases.csv`

todas as releases dos repositórios da amostra, inclusive as anteriores à janela (base do `compare`). Gerado por RQ82 `GET /repos/{o}/{r}/releases`.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `nome_completo` | texto | — | `owner/repo` (GraphQL `nameWithOwner`, RQ74). Chave de junção entre os arquivos |
| `id` | inteiro | — | id do objeto na API do GitHub |
| `tag_name` | texto | — | tag da release (`tag_name`) |
| `name` | texto | — | título da release ou nome do workflow (`name`) |
| `draft` | booleano | — | `draft` da release (rascunho; nunca é deploy) |
| `prerelease` | booleano | — | `prerelease` da release |
| `created_at` | data | — | `created_at` do objeto na API |
| `published_at` | data | — | `published_at` da release (data do deploy) |
| `target_commitish` | texto | — | branch ou SHA de onde a release foi criada |
| `dentro_janela` | booleano | — | data de publicação (release) ou de autoria do commit (tag) dentro da janela |

## `workflow_runs.csv.gz`

workflow runs de `push` no default branch, criados na janela (CSV compactado; `pandas.read_csv` lê direto). Gerado por RQ82/RQ77 `GET /actions/runs?branch=…&event=push&created=…`.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `nome_completo` | texto | — | `owner/repo` (GraphQL `nameWithOwner`, RQ74). Chave de junção entre os arquivos |
| `id` | inteiro | — | id do objeto na API do GitHub |
| `workflow_id` | inteiro | — | id do workflow do run (agrupa os episódios da RQ 04) |
| `name` | texto | — | título da release ou nome do workflow (`name`) |
| `event` | categoria | — | evento que disparou o run; sempre `push` |
| `head_branch` | texto | — | branch do run; sempre o default branch |
| `head_sha` | texto | — | SHA do commit do run |
| `status` | categoria | — | `status` do run (`completed`, `queued`…) |
| `conclusion` | categoria | — | `conclusion` do run: `success` = sucesso; `failure`/`timed_out`/`startup_failure` = falha; demais = ignorado |
| `run_attempt` | inteiro | tentativas | nº da tentativa (a API devolve só a última; ameaça à validade, RQ77) |
| `created_at` | data | — | `created_at` do objeto na API |
| `run_started_at` | data | — | início real da última tentativa do run |
| `updated_at` | data | — | última atualização do run (fim, para runs concluídos) |

## `intervalos_runs.csv`

auditoria da coleta de runs: cada intervalo consultado. Gerado por RQ77 `coleta_dora.coletar_runs`.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `nome_completo` | texto | — | `owner/repo` (GraphQL `nameWithOwner`, RQ74). Chave de junção entre os arquivos |
| `intervalo` | texto | — | filtro `created` consultado: `AAAA-MM-DD..AAAA-MM-DD` ou com hora UTC |
| `total_informado` | inteiro | runs | `total_count` da API para o intervalo |
| `coletados` | inteiro | runs | runs paginados no intervalo (vazio se subdividido sem paginar) |
| `subdividido` | booleano | — | intervalo dividido ao meio por ter chegado ao teto de 1.000 |

## `lead_time_releases.csv`

lead time de cada release da janela (definição principal). Gerado por RQ76 `pipeline_dora.calcular_lead_time`.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `nome_completo` | texto | — | `owner/repo` (GraphQL `nameWithOwner`, RQ74). Chave de junção entre os arquivos |
| `tag_name` | texto | — | tag da release (`tag_name`) |
| `anterior` | texto | — | `tag_name` da release publicada imediatamente antes (base do `compare`) |
| `published_at` | data | — | `published_at` da release (data do deploy) |
| `commits` | inteiro | commits | commits devolvidos pelo `compare` com data de autoria |
| `commits_negativos` | inteiro | commits | dos commits da release, quantos têm data posterior a ela (descartados) |
| `truncado` | booleano | — | `compare` incompleto (limite de páginas ou falha no meio) |
| `lead_time_dias` | real | dias | variante (a) da release: `published_at` − commit mais antigo |
| `motivo` | categoria | — | por que R ficou sem lead time: `sem_release_anterior`, `sem_commits_novos`, `compare_indisponivel` (vazio se calculado) |

## `commits_releases.csv.gz`

commits de cada release, do `compare` com a anterior (CSV compactado). Gerado por RQ76 `GET /compare/{anterior}...{R}`.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `nome_completo` | texto | — | `owner/repo` (GraphQL `nameWithOwner`, RQ74). Chave de junção entre os arquivos |
| `tag_name` | texto | — | tag da release (`tag_name`) |
| `anterior` | texto | — | `tag_name` da release publicada imediatamente antes (base do `compare`) |
| `sha` | texto | — | SHA do commit |
| `data_autor` | data | — | `commit.author.date` |
| `mensagem` | texto | — | 1ª linha de `commit.message`, até 200 caracteres |

## `tags.csv`

tags dos repositórios da amostra, com a data do commit apontado (variante de deploy da RQ 07). Gerado por RQ75 `GET /tags` + `GET /commits/{sha}`.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `nome_completo` | texto | — | `owner/repo` (GraphQL `nameWithOwner`, RQ74). Chave de junção entre os arquivos |
| `tag_name` | texto | — | tag da release (`tag_name`) |
| `sha` | texto | — | SHA do commit |
| `data_autor` | data | — | `commit.author.date` |
| `tem_release` | booleano | — | a tag tem release publicada associada |
| `dentro_janela` | booleano | — | `data_autor` do commit da tag dentro da janela |
| `status` | categoria | — | situação da coleta da tag (`ok` = data do commit obtida) |
| `status_commit` | inteiro | — | status HTTP de `GET /commits/{sha}` |
| `erro` | texto | — | mensagem de erro da API, quando houver |

## `rq83/metricas_variantes.csv`

métricas das RQ 01 a 04 em todas as variantes obrigatórias, com quartis. Gerado por RQ83 `rq83_metricas_variantes.py`.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `nome_completo` | texto | — | `owner/repo` (GraphQL `nameWithOwner`, RQ74). Chave de junção entre os arquivos |
| `releases_janela` | inteiro | releases | releases com `draft = false`, `prerelease = false` e `published_at` dentro da janela (deploys, definição principal) |
| `frequencia_deploy_semana` | real | releases/semana | RQ 01: `releases_janela` ÷ (dias da janela ÷ 7) |
| `lead_time_release_mediana_dias` | real | dias | RQ 02 (a): mediana, entre as releases, de `published_at` de R − `commit.author.date` do commit mais antigo de `compare/{anterior}...{R}` |
| `lead_time_commit_mediana_dias` | real | dias | RQ 02 (b): mediana, entre **todos** os commits de todas as releases, de `published_at` de R − `commit.author.date` |
| `releases_com_lead_time` | inteiro | releases | releases da janela com lead time calculado (entram na variante a) |
| `commits_com_lead_time` | inteiro | commits | commits que entram na variante (b) |
| `releases_sem_anterior` | inteiro | releases | primeira release da história do repositório: sem base para o `compare`, ignorada no lead time |
| `releases_sem_commits` | inteiro | releases | `compare` sem commits novos (ou só com datas posteriores à release), ignorada |
| `releases_compare_indisponivel` | inteiro | releases | `compare` com 404 (tag apagada/reescrita), 422 ou erro persistente, ignorada |
| `releases_compare_truncado` | inteiro | releases | `compare` incompleto (limite de páginas ou falha no meio da paginação) |
| `commits_negativos` | inteiro | commits | commits com `commit.author.date` posterior ao `published_at` da release, descartados das duas variantes |
| `runs_validos` | inteiro | runs | `runs_falha + runs_sucesso` (push, default branch, janela, conclusão válida) |
| `runs_falha` | inteiro | runs | `conclusion` ∈ {`failure`, `timed_out`, `startup_failure`} |
| `runs_sucesso` | inteiro | runs | `conclusion = success` |
| `cfr_ci` | real | fração (0–1) | RQ 03 (a): `runs_falha ÷ runs_validos` |
| `cfr_entrega` | real | fração (0–1) | RQ 03 (b): `releases_falha_cfr ÷ releases_avaliadas_cfr` |
| `releases_avaliadas_cfr` | inteiro | releases | releases da janela publicadas mais de 7 dias antes do fim da janela (denominador do CFR b) |
| `releases_falha_cfr` | inteiro | releases | releases seguidas, em até 7 dias (inclusive), por uma release corretiva segundo a heurística |
| `releases_censuradas_cfr` | inteiro | releases | releases dos últimos 7 dias da janela, fora do denominador do CFR b (censura) |
| `releases_sem_semver` | inteiro | releases | releases da janela cuja tag não é SemVer `MAJOR.MINOR.PATCH` (a heurística por patch não as reconhece) |
| `episodios_falha` | inteiro | episódios | total de episódios de falha, incluindo os censurados |
| `episodios_completos` | inteiro | episódios | episódios usados na mediana (sem censura) |
| `episodios_censurados` | inteiro | episódios | episódios sem sucesso até o fim da janela (censura à direita) |
| `episodios_censura_esquerda` | inteiro | episódios | episódios em que o workflow já começa a janela falhando, sem sucesso anterior observado |
| `proporcao_episodios_censurados` | real | fração (0–1) | `episodios_censurados ÷ episodios_falha` |
| `lead_time_release_q1_dias` | real | dias | 1º quartil da distribuição da variante (a) do repositório (interpolação linear, tipo 7) |
| `lead_time_release_q3_dias` | real | dias | 3º quartil da variante (a) |
| `lead_time_release_iqr_dias` | real | dias | `lead_time_release_q3_dias − lead_time_release_q1_dias` |
| `lead_time_commit_q1_dias` | real | dias | 1º quartil da variante (b) |
| `lead_time_commit_q3_dias` | real | dias | 3º quartil da variante (b) |
| `lead_time_commit_iqr_dias` | real | dias | `lead_time_commit_q3_dias − lead_time_commit_q1_dias` |
| `recuperacao_mediana_horas` | real | horas | RQ 04: mediana dos episódios completos de todos os workflows; episódio = `updated_at` do sucesso − `run_started_at` da 1ª falha do mesmo workflow |
| `recuperacao_q1_horas` | real | horas | 1º quartil dos episódios completos |
| `recuperacao_q3_horas` | real | horas | 3º quartil dos episódios completos |
| `recuperacao_iqr_horas` | real | horas | `recuperacao_q3_horas − recuperacao_q1_horas` |
| `calculo_completo` | booleano | — | RQ83: todas as métricas do repositório calculadas sem pendência |
| `pendencias` | texto | — | RQ83: lista das pendências do repositório (ex.: compare truncado), separadas por `;` |

## `rq83/cfr_entrega_releases.csv`

avaliação de cada release da janela no CFR (b). Gerado por RQ83 `metricas/variantes.cfr_entrega`.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `nome_completo` | texto | — | `owner/repo` (GraphQL `nameWithOwner`, RQ74). Chave de junção entre os arquivos |
| `tag_name` | texto | — | tag da release (`tag_name`) |
| `published_at` | data | — | `published_at` da release (data do deploy) |
| `censurada` | booleano | — | publicada nos últimos 7 dias da janela: fora do denominador do CFR (b) |
| `falha` | booleano | — | seguida por release corretiva em até 7 dias (vazio se censurada) |
| `corretiva_tag` | texto | — | tag da primeira release corretiva encontrada nos 7 dias |
| `tag_semver` | booleano | — | a tag segue SemVer `MAJOR.MINOR.PATCH` |
| `heuristica` | categoria | — | versão da heurística de release corretiva (RQ89) |

## `rq83/episodios_recuperacao.csv`

episódios de falha por workflow (evidência da RQ 04). Gerado por RQ83 / RQ79 `metricas/ci.episodios_de_falha`.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `nome_completo` | texto | — | `owner/repo` (GraphQL `nameWithOwner`, RQ74). Chave de junção entre os arquivos |
| `workflow_id` | inteiro | — | id do workflow do run (agrupa os episódios da RQ 04) |
| `inicio` | data | — | `run_started_at` da primeira falha do episódio |
| `fim` | data | — | `updated_at` do sucesso que encerra o episódio (ou fim da janela, se censurado) |
| `horas` | real | horas | `fim − inicio` |
| `falhas` | inteiro | runs | falhas no episódio |
| `censurado` | booleano | — | sem sucesso até o fim da janela (censura à direita) |
| `censura_esquerda` | booleano | — | workflow já começa a janela falhando |

## `amostra_ouro/sorteio_repositorios.csv`

os 60 repositórios sorteados para a validação manual (`random_state=42`). Gerado por RQ86 `validacao/rq86_amostra_ouro.py gerar`.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `id_repositorio` | texto | — | identificador do repositório sorteado (`R01`…`R60`) |
| `nome_completo` | texto | — | `owner/repo` (GraphQL `nameWithOwner`, RQ74). Chave de junção entre os arquivos |
| `linguagem` | texto | — | GraphQL `primaryLanguage.name` (vazio se o GitHub não detecta) |
| `estrelas` | inteiro | estrelas | GraphQL `stargazerCount` na coleta RQ74 |
| `link_repositorio` | texto | URL | página do repositório no GitHub |
| `link_releases` | texto | URL | página de releases do repositório |

## `amostra_ouro/sorteio_releases.csv`

as releases sorteadas (5 por repositório) para rotular como corretiva ou não. Gerado por RQ86 `validacao/rq86_amostra_ouro.py gerar`.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `id_release` | texto | — | identificador da release sorteada (`R01-1`…) |
| `id_repositorio` | texto | — | identificador do repositório sorteado (`R01`…`R60`) |
| `nome_completo` | texto | — | `owner/repo` (GraphQL `nameWithOwner`, RQ74). Chave de junção entre os arquivos |
| `tag_name` | texto | — | tag da release (`tag_name`) |
| `release_anterior` | texto | — | release publicada imediatamente antes (base do `compare`) |
| `published_at` | data | — | `published_at` da release (data do deploy) |
| `link_release` | texto | URL | página da release (release notes) |
| `link_commits` | texto | URL | `compare` com a release anterior (lista de commits) |

## `amostra_ouro/consenso_repositorios.csv`

rótulos dos 3 avaliadores e consenso por repositório. Gerado por RQ88 `validacao/rq88_concordancia.py`.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `id_repositorio` | texto | — | identificador do repositório sorteado (`R01`…`R60`) |
| `nome_completo` | texto | — | `owner/repo` (GraphQL `nameWithOwner`, RQ74). Chave de junção entre os arquivos |
| `tipo_projeto_BernardoApl` | categoria | código | tipo do projeto, segundo BernardoApl |
| `tipo_projeto_bacelete` | categoria | código | tipo do projeto, segundo bacelete |
| `tipo_projeto_Joaopedrotavaress` | categoria | código | tipo do projeto, segundo Joaopedrotavaress |
| `tipo_projeto_consenso` | categoria | biblioteca_framework/aplicacao_servico/ferramenta_cli/outro | rótulo de consenso: 3-0 unânime, 2-1 maioria, 1-1-1 decidido em reunião (RQ88) |
| `tipo_projeto_origem` | categoria | unanime/maioria/reuniao/empate_pendente | como o consenso foi obtido |
| `tipo_projeto_justificativa` | texto | — | justificativa registrada em `decisoes_reuniao.csv` (só `origem = reuniao`) |
| `entregas_reais_BernardoApl` | categoria | código | releases são entregas reais, segundo BernardoApl |
| `entregas_reais_bacelete` | categoria | código | releases são entregas reais, segundo bacelete |
| `entregas_reais_Joaopedrotavaress` | categoria | código | releases são entregas reais, segundo Joaopedrotavaress |
| `entregas_reais_consenso` | categoria | sim/nao/incerto | rótulo de consenso: 3-0 unânime, 2-1 maioria, 1-1-1 decidido em reunião (RQ88) |
| `entregas_reais_origem` | categoria | unanime/maioria/reuniao/empate_pendente | como o consenso foi obtido |
| `entregas_reais_justificativa` | texto | — | justificativa registrada em `decisoes_reuniao.csv` (só `origem = reuniao`) |

## `amostra_ouro/consenso_releases.csv`

rótulos dos 3 avaliadores e consenso por release sorteada (referência do F1 da RQ89). Gerado por RQ88 `validacao/rq88_concordancia.py`.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `id_release` | texto | — | identificador da release sorteada (`R01-1`…) |
| `id_repositorio` | texto | — | identificador do repositório sorteado (`R01`…`R60`) |
| `nome_completo` | texto | — | `owner/repo` (GraphQL `nameWithOwner`, RQ74). Chave de junção entre os arquivos |
| `tag_name` | texto | — | tag da release (`tag_name`) |
| `release_anterior` | texto | — | release publicada imediatamente antes (base do `compare`) |
| `published_at` | data | — | `published_at` da release (data do deploy) |
| `corretiva_BernardoApl` | categoria | código | release corretiva, segundo BernardoApl |
| `corretiva_bacelete` | categoria | código | release corretiva, segundo bacelete |
| `corretiva_Joaopedrotavaress` | categoria | código | release corretiva, segundo Joaopedrotavaress |
| `corretiva_consenso` | categoria | sim/nao | rótulo de consenso: 3-0 unânime, 2-1 maioria, 1-1-1 decidido em reunião (RQ88) |
| `corretiva_origem` | categoria | unanime/maioria/reuniao/empate_pendente | como o consenso foi obtido |
| `corretiva_justificativa` | texto | — | justificativa registrada em `decisoes_reuniao.csv` (só `origem = reuniao`) |

## `amostra_ouro/concordancia_fleiss.csv`

kappa de Fleiss por dimensão rotulada. Gerado por RQ88 `validacao/rq88_concordancia.py`.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `dimensao` | categoria | — | `tipo_projeto`, `entregas_reais` ou `corretiva` |
| `itens` | inteiro | itens | itens rotulados na dimensão |
| `avaliadores` | inteiro | pessoas | avaliadores independentes |
| `kappa_fleiss` | real | −1 a 1 | `statsmodels` `aggregate_raters` + `fleiss_kappa(method='fleiss')` sobre os rótulos independentes; vazio se indefinido (todos na mesma categoria) |
| `interpretacao` | categoria | — | Landis & Koch (1977): pobre, leve, razoavel, moderada, substancial, quase perfeita |
| `concordancia_total` | real | fração (0–1) | `itens_unanimes ÷ itens` |
| `itens_unanimes` | inteiro | itens | itens 3-0 |
| `itens_2_1` | inteiro | itens | itens 2-1 |
| `itens_1_1_1` | inteiro | itens | itens 1-1-1 |
| `distribuicao` | json | rótulos | contagem de rótulos por categoria, somando os 3 avaliadores |

## `amostra_ouro/pendencias_reuniao.csv`

pauta da reunião de consenso (empates e divergências). Gerado por RQ88 `validacao/rq88_concordancia.py`.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `dimensao` | categoria | — | `tipo_projeto`, `entregas_reais` ou `corretiva` |
| `id_item` | texto | — | `id_repositorio` ou `id_release` |
| `obrigatoria` | booleano | — | empate 1-1-1 (precisa de decisão); falso = divergência 2-1 para revisar |
| `BernardoApl` | categoria | código | rótulo de BernardoApl |
| `bacelete` | categoria | código | rótulo de bacelete |
| `Joaopedrotavaress` | categoria | código | rótulo de Joaopedrotavaress |
| `maioria` | categoria | código | rótulo da maioria nos itens 2-1 |

## `amostra_ouro/decisoes_reuniao.csv`

decisões da reunião de consenso (escrito pelo grupo). Gerado por grupo, conforme protocolo da RQ88.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `dimensao` | categoria | — | `tipo_projeto`, `entregas_reais` ou `corretiva` |
| `id_item` | texto | — | `id_repositorio` ou `id_release` |
| `rotulo` | categoria | código ou texto da lista | rótulo decidido em reunião |
| `justificativa` | texto | — | motivo da decisão (obrigatório) |

## `amostra_ouro/avaliacao_heuristica.csv`

precisão, recall e F1 de cada versão da heurística de release corretiva. Gerado por RQ89 `validacao/rq89_heuristica.py avaliar`.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `versao` | categoria | — | versão da heurística (`metricas/corretiva.py`) |
| `n` | inteiro | releases | releases com rótulo de consenso |
| `corretivas_consenso` | inteiro | releases | corretivas segundo o consenso |
| `corretivas_heuristica` | inteiro | releases | corretivas segundo a heurística |
| `vp` | inteiro | releases | verdadeiros positivos |
| `fp` | inteiro | releases | falsos positivos |
| `fn` | inteiro | releases | falsos negativos |
| `vn` | inteiro | releases | verdadeiros negativos |
| `precisao` | real | fração (0–1) | `vp ÷ (vp + fp)` (`precision_recall_fscore_support`, `zero_division=0`) |
| `recall` | real | fração (0–1) | `vp ÷ (vp + fn)` |
| `f1` | real | fração (0–1) | `2·P·R ÷ (P + R)` |
| `sem_mensagens` | inteiro | releases | releases sem mensagens de commit disponíveis (só a tag é avaliada) |

## `amostra_ouro/erros_heuristica.csv`

falsos positivos e negativos de cada versão da heurística, com as evidências. Gerado por RQ89 `validacao/rq89_heuristica.py avaliar`.

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `versao` | categoria | — | versão da heurística |
| `erro` | categoria | — | `falso_positivo` ou `falso_negativo` |
| `id_release` | texto | — | identificador da release sorteada (`R01-1`…) |
| `nome_completo` | texto | — | `owner/repo` (GraphQL `nameWithOwner`, RQ74). Chave de junção entre os arquivos |
| `tag_name` | texto | — | tag da release (`tag_name`) |
| `release_anterior` | texto | — | release publicada imediatamente antes (base do `compare`) |
| `ev_patch` | booleano | — | evidência: só o patch SemVer aumentou |
| `ev_mensagens_disponiveis` | booleano | — | evidência: há mensagens de commit do `compare` |
| `ev_uteis` | inteiro | commits | evidência: commits sem os de merge |
| `ev_revert_hotfix` | inteiro | commits | evidência: commits com `revert`/`hotfix` |
| `ev_fix` | inteiro | commits | evidência: commits com `fix`/`fixes`/`fixed`/`bugfix` |
| `ev_fix_defeito` | inteiro | commits | evidência: `fix` que não é de typo/docs/lint/CI/testes/dependências |
| `ev_feat` | inteiro | commits | evidência: commits de funcionalidade |
| `link_release` | texto | URL | página da release (release notes) |
| `link_commits` | texto | URL | `compare` com a release anterior (lista de commits) |
