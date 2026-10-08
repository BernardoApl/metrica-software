# RQ76 — Lead Time e Testes Unitários

Issue: #76. Cobre a RQ 02 do LAB03 (*lead time for changes*, variantes (a) e (b)) e a coleta de commits entre releases (seção 4 do enunciado). Com o lead time pronto, o pipeline passa a calcular as quatro métricas DORA e a **classificação geral** de cada repositório.

## Código

| Arquivo | Conteúdo |
|---|---|
| [`codigo-fonte/metricas/lead_time.py`](../../../codigo-fonte/metricas/lead_time.py) | Funções puras: pares (release anterior, R), lead time por release e por commit, agregação do repositório |
| [`codigo-fonte/coleta/coleta_dora.py`](../../../codigo-fonte/coleta/coleta_dora.py) | `coletar_compare`: `GET /compare/{anterior}...{R}` com paginação |
| [`codigo-fonte/pipeline_dora.py`](../../../codigo-fonte/pipeline_dora.py) | `calcular_lead_time`: integra o compare ao pipeline, preenche `classe_lead_time` e `classe_geral` e exporta os CSVs novos |
| [`codigo-fonte/testes/test_metricas_lead_time.py`](../../../codigo-fonte/testes/test_metricas_lead_time.py) | Testes das funções de cálculo, com fixtures |
| [`codigo-fonte/testes/test_rq76_compare.py`](../../../codigo-fonte/testes/test_rq76_compare.py) | Testes da coleta do compare e do pipeline |

```bash
pytest codigo-fonte/testes/test_metricas_lead_time.py codigo-fonte/testes/test_rq76_compare.py --cov=metricas --cov-report=term-missing
```

Cobertura de `metricas/lead_time.py`: 100% (o módulo `metricas` inteiro continua em 100%).

## Definição implementada

Para cada release R publicada na janela (não draft, não pré-release):

1. **Release anterior** = a release publicada imediatamente antes de R por `published_at`, com a mesma definição de deploy. Ela pode estar fora da janela: a coleta de releases já guarda as anteriores à janela.
2. **Commits de R** = `GET /repos/{o}/{r}/compare/{anterior}...{R}`, todas as páginas (`per_page=100`, seguindo o `Link`), porque sem paginação a API para em 250 commits.
3. **Data do commit** = `commit.author.date`; **data de R** = `published_at`.
4. **(a) por release:** `lead_time(R) = data de R − commit mais antigo de R`. Valor do repositório = mediana entre as releases.
5. **(b) por commit:** cada commit contribui com `data de R − data do commit`. Valor do repositório = mediana de todos os commits de todas as releases.

A `classe_lead_time` usa a variante (a), que é a da combinação de referência C1 da RQ 07. Com ela, `classe_geral` (mediana das quatro notas, arredondada para baixo) passa a ser preenchida.

### Decisões que vão para a Metodologia

| Situação | Tratamento | Coluna que conta |
|---|---|---|
| R é a primeira release da história | ignorada (enunciado) | `releases_sem_anterior` |
| `compare` devolve 404 (tag apagada/reescrita), 422, ou erro persistente | ignorada e contada (FAQ do enunciado). O erro não vai para o cache, então a próxima execução tenta de novo | `releases_compare_indisponivel` |
| `compare` sem commits novos (mesma tag republicada, release de outro branch já contida na anterior) | sem lead time, fora das duas variantes | `releases_sem_commits` |
| commit com data de autoria **posterior** à publicação de R (relógio errado, tag movida depois de publicar) | descartado das duas variantes | `commits_negativos` |
| `compare` com mais de `limite_paginas_compare` páginas (padrão 20 = 2.000 commits) | usa os commits obtidos e marca | `releases_compare_truncado` |
| pré-release como release anterior | não, na definição principal. `pares_de_releases(..., incluir_prerelease=True)` já atende a variante C2 da RQ 07 | — |

## Testes (casos de borda pedidos na seção 7)

- **Exemplo numérico do enunciado** (`v1.1` em 15/03 com commits de 02/03, 10/03 e 14/03): (a) = 13 dias; (b) = 13, 5 e 1 dias.
- **Commit "esquecido"**: um commit de 100 dias numa release faz a mediana (a) do repositório ser 3 e a (b) ser 1 (fixture calculada no papel). É o efeito que o artigo precisa discutir.
- Release **sem commits novos**; repositório com **uma única release**; **primeira release da história**; release anterior **fora da janela**.
- `compare` 404, 422, ausente ou com erro persistente; `compare` truncado; falha no meio da paginação.
- Commit com data posterior à release, commit sem data, fusos horários diferentes, fração de dia.
- Pré-release e draft não servem de deploy nem de release anterior; empate de `published_at`.
- Paginação além de 250 commits; tags de monorepo com `@` e `/`, e tags com espaço, `+` e `#` na URL.
- Pipeline: colunas de lead time, `classe_geral`, `lead_time_releases.csv`, `commits_releases.csv.gz` e limite de páginas lido da config.

## Saídas novas

- Colunas em `metricas_repositorios.csv`: `lead_time_release_mediana_dias`, `lead_time_commit_mediana_dias`, contagens de releases ignoradas, `classe_lead_time` e `classe_geral`.
- `lead_time_releases.csv`: uma linha por release da janela, com a release anterior, o lead time (a) e o motivo quando não há lead time.
- `commits_releases.csv.gz`: commits de cada release (sha, data de autoria, 1ª linha da mensagem). As mensagens servem para a heurística de release corretiva (`revert`, `hotfix`, `fix`) do CFR (b).

Tudo documentado em [`dados/lab03/DICIONARIO.md`](../../../dados/lab03/DICIONARIO.md).

## Custo de coleta na amostra da S01

Aplicando `pares_de_releases` ao `releases.csv` já coletado:

| Item | Valor |
|---|---:|
| releases na janela (não draft, não pré-release) | 6.217 |
| sem release anterior (primeira da história) | 20, todas de repositórios criados entre 2025 e 2026 |
| chamadas de `compare` (1ª página) | 6.197 |

São pelo menos 6,2 mil requisições, cerca de 1h15 de cota com 5.000 req/h, mais as páginas extras de releases grandes. O cache e a retomada da RQ78 dão conta disso.

## Ameaças à validade (para o artigo)

- **Rebase e squash merge** distorcem `commit.author.date` (o enunciado já aponta isso). Um *rebase* preserva a data original de autoria, então um commit escrito semanas antes e rebaseado na véspera da release infla o lead time. Um *squash* junta vários commits num só e esconde a data dos commits originais.
- **Monorepos** que publicam várias releases por pacote (`@scope/pkg@x.y.z`) comparam R com a release anterior de **outro** pacote, porque a "release anterior" é a do repositório.
- **Releases de branches de manutenção** (ex.: `v1.9.3` depois de `v2.0.0`) são comparadas com a anterior por data. O `compare` usa a base comum, então pode trazer commits que não fazem parte daquela linha.
- O `compare` lista os commits alcançáveis a partir da tag, e não só os do default branch.

## Para gerar os dados

O `dados/lab03/metricas_repositorios.csv` atual ainda não tem as colunas de lead time. É preciso rodar o pipeline de novo na máquina que tem o cache: runs e releases saem do cache, e só os `compare` vão à rede.
