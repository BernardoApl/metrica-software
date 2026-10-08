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
| `intervalos_no_teto` | inteiro | intervalos | intervalos de **um segundo** ainda com 1.000 runs ou mais, em que a API só devolve os 1.000 primeiros (RQ77: dias e horas acima do teto são subdivididos até caber). Se for maior que 0, a coleta desse repositório está incompleta |
| `lead_time_release_mediana_dias` | real | dias | **RQ 02 (a)**: mediana, entre as releases, de `published_at` de R − `commit.author.date` do commit mais antigo de `compare/{anterior}...{R}` |
| `lead_time_commit_mediana_dias` | real | dias | **RQ 02 (b)**: mediana, entre **todos** os commits de todas as releases, de `published_at` de R − `commit.author.date` do commit |
| `releases_com_lead_time` | inteiro | releases | releases da janela com lead time calculado (entram na variante a) |
| `commits_com_lead_time` | inteiro | commits | commits que entram na variante (b) |
| `releases_sem_anterior` | inteiro | releases | primeira release da história do repositório: sem base para o `compare`, ignorada |
| `releases_sem_commits` | inteiro | releases | `compare` sem commits novos (ou só com commits de data posterior à release), ignorada |
| `releases_compare_indisponivel` | inteiro | releases | `compare` com 404 (tag apagada/reescrita), 422 ou erro persistente, ignorada |
| `releases_compare_truncado` | inteiro | releases | `compare` com mais páginas que `limite_paginas_compare` (ou que falhou no meio); o lead time usa só os commits obtidos |
| `commits_negativos` | inteiro | commits | commits com `commit.author.date` posterior a `published_at` da release, descartados das duas variantes |
| `classe_frequencia` | categoria | Elite/High/Medium/Low | tabela de referência da RQ 07 aplicada a `frequencia_deploy_semana` |
| `classe_cfr` | categoria | idem | tabela da RQ 07 aplicada a `cfr_ci` |
| `classe_lead_time` | categoria | idem | tabela da RQ 07 aplicada a `lead_time_release_mediana_dias` (variante a, combinação de referência C1) |
| `classe_recuperacao` | categoria | idem | tabela da RQ 07 aplicada a `recuperacao_mediana_horas` |
| `classe_geral` | categoria | idem | mediana das notas das quatro classes (Elite=4 … Low=1), arredondada para baixo. Vazia se alguma das quatro for indefinida |

O CFR de entrega (RQ 03 b) ainda não está neste arquivo; ele vai usar as mensagens de `commits_releases.csv.gz`.

**Release anterior (RQ76):** é a release publicada imediatamente anterior a R por `published_at`, com a mesma definição de deploy (não draft, não pré-release). Ela pode estar fora da janela.

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

## `intervalos_runs.csv` — auditoria da coleta de runs (RQ77)

Uma linha por consulta a `GET /actions/runs` feita para os repositórios da amostra. Serve para comprovar que nenhum intervalo ficou preso no teto de 1.000 resultados da busca.

| Coluna | Tipo | Significado |
|---|---|---|
| `nome_completo` | texto | repositório |
| `intervalo` | texto | valor do filtro `created`: `AAAA-MM-DD..AAAA-MM-DD` para dias inteiros, ou `AAAA-MM-DDTHH:MM:SS+00:00..` para frações de dia. Extremos inclusivos, em UTC |
| `total_informado` | inteiro | `total_count` devolvido pela API para o intervalo (impreciso: pode saturar ou subestimar) |
| `coletados` | inteiro | runs efetivamente paginados no intervalo. Vazio quando o intervalo foi subdividido sem paginar, porque `total_informado` já passava de 1.000 |
| `subdividido` | booleano | `True` se o intervalo foi dividido em duas metades, porque `total_informado` > 1.000 ou `coletados` = 1.000 |

Checagem: as linhas com `subdividido = False` cobrem a janela sem lacunas, e todas têm `coletados` < 1.000 (as exceções aparecem em `intervalos_no_teto`).

## `lead_time_releases.csv` — lead time por release (RQ76)

Uma linha por release da janela (não draft, não pré-release) dos repositórios da amostra.

| Coluna | Tipo | Unidade | Significado |
|---|---|---|---|
| `nome_completo`, `tag_name` | texto | — | repositório e release R |
| `anterior` | texto | — | `tag_name` da release anterior (base do `compare`); vazio se R é a primeira da história |
| `published_at` | data | — | data de R |
| `commits` | inteiro | commits | commits retornados pelo `compare` (com data de autoria) |
| `commits_negativos` | inteiro | commits | dos quais com data posterior a R (descartados) |
| `truncado` | booleano | — | `compare` incompleto (limite de páginas ou falha no meio) |
| `lead_time_dias` | real | dias | variante (a) da release: R − commit mais antigo. Vazio se `motivo` preenchido |
| `motivo` | categoria | — | por que R ficou sem lead time: `sem_release_anterior`, `sem_commits_novos`, `compare_indisponivel` |

## `commits_releases.csv.gz` — commits de cada release (RQ76)

| Coluna | Tipo | Origem |
|---|---|---|
| `nome_completo`, `tag_name`, `anterior` | texto | repositório, release R e base do `compare` |
| `sha` | texto | `commits[].sha` de `GET /repos/{o}/{r}/compare/{anterior}...{R}` |
| `data_autor` | data | `commits[].commit.author.date` |
| `mensagem` | texto | 1ª linha de `commits[].commit.message`, até 200 caracteres (para a heurística de release corretiva da RQ 03 b) |

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
