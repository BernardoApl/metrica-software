# Dicionário de dados — LAB03 (Sprint 01)

Arquivos gerados por `python codigo-fonte/pipeline_dora.py --config config/pipeline.json`. Datas em ISO 8601 UTC. Valores vazios significam **indefinido**, e não zero. Por exemplo, um repositório sem falhas tem tempo de recuperação vazio.

Janela usada: ver `resumo_execucao.json` (`config.janela`). As duas datas são inclusivas e o fim vai até 23:59:59 UTC.

## `metricas_repositorios.csv` — uma linha por repositório da amostra

| Coluna | Tipo | Unidade | Fórmula / origem |
|---|---|---|---|
| `nome_completo` | texto | — | `owner/repo` (GraphQL `nameWithOwner`, RQ74) |
| `url` | texto | — | GraphQL `url` |
| `estrelas` | inteiro | estrelas | GraphQL `stargazerCount` na coleta RQ74 |
| `linguagem` | texto | — | GraphQL `primaryLanguage.name` (pode ser vazio) |
| `criado_em` | data | — | GraphQL `createdAt` |
| `idade_anos` | real | anos | (referência da coleta RQ74 − `criado_em`) / 365,25 |
| `contribuidores_total` | inteiro | pessoas | número da última página de `GET /contributors?per_page=1&anon=true` (vazio se não coletado) |
| `branch_padrao` | texto | — | `defaultBranchRef.name`; só esse branch é considerado |
| `workflows_total` | inteiro | workflows | `total_count` de `GET /actions/workflows` |
| `releases_janela` | inteiro | releases | releases com `draft = false`, `prerelease = false` e `published_at` dentro da janela |
| `prereleases_janela` | inteiro | releases | pré-releases publicadas na janela (variante da RQ 07) |
| `frequencia_deploy_semana` | real | releases/semana | `releases_janela` ÷ (dias da janela ÷ 7) — RQ 01 |
| `runs_coletados` | inteiro | runs | runs de `push` no default branch criados na janela, de qualquer `conclusion` |
| `runs_validos` | inteiro | runs | `runs_falha + runs_sucesso` |
| `runs_falha` | inteiro | runs | `conclusion` ∈ {`failure`, `timed_out`, `startup_failure`} |
| `runs_sucesso` | inteiro | runs | `conclusion = success` |
| `cfr_ci` | real | fração (0–1) | CFR (a) = `runs_falha ÷ runs_validos` — RQ 03 (a) |
| `recuperacao_mediana_horas` | real | horas | mediana dos episódios completos de todos os workflows; episódio = `updated_at` do sucesso − `run_started_at` da 1ª falha — RQ 04 |
| `episodios_falha` | inteiro | episódios | total de episódios, incluindo os censurados |
| `episodios_completos` | inteiro | episódios | episódios usados na mediana |
| `episodios_censurados` | inteiro | episódios | episódios sem sucesso até o fim da janela (censura à direita) |
| `episodios_censura_esquerda` | inteiro | episódios | episódios em que o workflow já começa a janela falhando, sem sucesso anterior observado |
| `proporcao_episodios_censurados` | real | fração (0–1) | `episodios_censurados ÷ episodios_falha` |
| `intervalos_no_teto` | inteiro | intervalos | dias com mais de 1.000 runs, em que a API só devolve os 1.000 primeiros. Se for maior que 0, a coleta desse repositório está incompleta |
| `classe_frequencia` | categoria | Elite/High/Medium/Low | tabela de referência da RQ 07 aplicada a `frequencia_deploy_semana` |
| `classe_cfr` | categoria | idem | tabela da RQ 07 aplicada a `cfr_ci` |
| `classe_recuperacao` | categoria | idem | tabela da RQ 07 aplicada a `recuperacao_mediana_horas` |

Lead time (RQ 02) e CFR de entrega (RQ 03 b) dependem do `compare` entre releases, que é parte de outra issue. Por isso, as colunas de lead time e a classificação geral ainda não estão neste arquivo. `releases.csv` já traz a release anterior à janela, que serve de base para esse cálculo.

## `releases.csv`

| Coluna | Tipo | Origem |
|---|---|---|
| `nome_completo` | texto | repositório |
| `id`, `tag_name`, `name`, `draft`, `prerelease`, `created_at`, `published_at`, `target_commitish` | — | `GET /repos/{o}/{r}/releases` |
| `dentro_janela` | booleano | `published_at` (ou `created_at`, se ausente) dentro da janela |

## `workflow_runs.csv.gz` (CSV compactado; `pandas.read_csv` lê direto)

| Coluna | Tipo | Origem |
|---|---|---|
| `nome_completo` | texto | repositório |
| `id`, `workflow_id`, `name`, `event`, `head_branch`, `head_sha`, `status`, `conclusion`, `run_attempt`, `created_at`, `run_started_at`, `updated_at` | — | `GET /repos/{o}/{r}/actions/runs?branch={default}&event=push&created={intervalo}` |

## `candidatos_avaliados.csv`

| Coluna | Tipo | Significado |
|---|---|---|
| `posicao` | inteiro | ordem de avaliação (estrelas decrescentes, entre os aptos no pré-filtro) |
| `motivo` | categoria | `incluido`, `sem_actions`, `poucas_releases`, `poucos_runs`, `runs_acima_do_limite`, `inacessivel` |
| `workflows_total`, `releases_janela`, `runs_total_informado`, `runs_validos` | inteiro | valores até a etapa em que o candidato parou. `runs_total_informado` é o `total_count` da API, que **satura em 2.500** em intervalos longos |
| `erro` | texto | status HTTP, quando `motivo = inacessivel` |

## `funil_selecao.csv`

| Coluna | Significado |
|---|---|
| `etapa`, `criterio` | nome e regra da etapa |
| `entrada`, `removidos_na_etapa`, `aprovados` | contagens de repositórios |

A etapa `avaliados_ate_a_meta` registra os candidatos aptos que **não foram avaliados**, porque a meta de repositórios foi atingida antes de chegar a eles.
