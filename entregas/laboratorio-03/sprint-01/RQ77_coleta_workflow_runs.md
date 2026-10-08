# RQ77 — Coletar Workflow Runs do GitHub Actions

Issue: #77. Coleta dos workflow runs do default branch dentro da janela, com subdivisão mensal (seção 4 do enunciado). Os runs alimentam o CFR (a) e o tempo de recuperação (RQ79).

A versão base da coleta entrou na #80 ([`coleta_dora.py`](../../../codigo-fonte/coleta/coleta_dora.py)). Esta issue auditou os 382.863 runs coletados na S01 e corrigiu uma perda silenciosa de dados no teto de 1.000 resultados da busca.

## Como os runs são coletados

```
GET /repos/{owner}/{repo}/actions/runs?branch={default_branch}&event=push&created={intervalo}&per_page=100&exclude_pull_requests=true
```

| Regra do enunciado | Implementação |
|---|---|
| Só o default branch | `branch = default_branch` (campo `defaultBranchRef` da RQ74). Push de tag tem `head_branch` = nome da tag e fica de fora |
| Só `event = push` | filtro `event=push` na própria API; `schedule`, `workflow_dispatch` e `pull_request` não vêm |
| Só a janela | `created=AAAA-MM-DD..AAAA-MM-DD`, um intervalo por mês civil |
| Teto de 1.000 por consulta | o intervalo é dividido ao meio até caber (detalhes abaixo) |
| Paginação | segue o `Link rel="next"` até 10 páginas de 100 |
| Classificação por `conclusion` | feita depois, em [`metricas/ci.py`](../../../codigo-fonte/metricas/ci.py) (RQ79). A coleta guarda todos os runs, inclusive `cancelled` e em andamento, para não esconder nada |

Campos guardados por run (o resto, como o objeto `repository` repetido em cada run, é descartado antes de ir para o cache): `id`, `workflow_id`, `name`, `event`, `head_branch`, `head_sha`, `status`, `conclusion`, `run_attempt`, `created_at`, `run_started_at`, `updated_at`.

## O problema encontrado na coleta da S01

A decisão de subdividir um mês dependia só do `total_count` da primeira página. O grupo já tinha visto que esse total é impreciso em intervalos longos (satura). Na auditoria de `workflow_runs.csv.gz` apareceu o caso oposto:

| `angular/angular` | out | nov | dez | jan | fev | mar | **abr** | mai | jun | jul | ago | set |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| runs coletados | 1855 | 2160 | 1200 | 1750 | 1112 | 1124 | **1000** | 968 | 1084 | 1044 | 816 | 966 |

Abril parou em **exatamente 1.000**, o teto da busca, com os meses vizinhos acima disso. Se a API informou `total_count ≤ 1.000`, a paginação parou na 10ª página e o resto do mês se perdeu **sem aviso** (`intervalos_no_teto = 0`). Foi o único repositório-mês da amostra nessa situação, mas a falha é silenciosa e ficaria mais frequente na amostra de 300+ da S02.

## O que mudou

1. **Subdivisão também pelo que foi coletado.** Se a paginação de um intervalo devolve 1.000 runs, ele é dividido ao meio e coletado de novo, independentemente do `total_count`. Um intervalo com exatamente 1.000 runs reais custa algumas chamadas a mais, mas nunca perde dados.
2. **Dia acima do teto dividido em horas, minutos e segundos.** O filtro `created` aceita data e hora (`2026-01-05T00:00:00+00:00..2026-01-05T11:59:59+00:00`). Antes, um dia com mais de 1.000 runs ficava incompleto. Agora só um intervalo de **um segundo** acima do teto vai para `teto_atingido`, o que na prática não acontece.
3. **Cache da S01 preservado.** Intervalos de dias inteiros continuam com a mesma URL (`AAAA-MM-DD..AAAA-MM-DD`) e são divididos nos mesmos pontos de antes. Rodar o pipeline de novo reaproveita todo o cache e só faz as chamadas novas, no caso o abril do `angular/angular`.
4. **Auditoria exportada.** O pipeline gera [`dados/lab03/intervalos_runs.csv`](../../../dados/lab03/DICIONARIO.md) com cada consulta feita: intervalo, `total_count` informado, runs coletados e se foi subdividido. É a evidência pedida no enunciado ("confira se nenhum mês atingiu o teto").
5. Um erro HTTP no meio de uma subdivisão agora informa o intervalo exato na mensagem.

## Testes

[`codigo-fonte/testes/test_rq77_workflow_runs.py`](../../../codigo-fonte/testes/test_rq77_workflow_runs.py), mais o cliente falso de [`test_coleta_dora.py`](../../../codigo-fonte/testes/test_coleta_dora.py), que passou a entender filtros com data e hora e a simular um `total_count` errado:

- caso `angular/angular`: 1.500 runs num mês com a API informando 1.000 → coleta os 1.500;
- 1.500 runs num único dia → divide por horas e coleta todos, em ordem cronológica;
- exatamente 1.000 runs → conferido por subdivisão, sem aviso; 999 → uma consulta só;
- 500 intervalos sorteados: as duas metades cobrem o intervalo sem lacuna nem sobreposição;
- URLs da janela e dos meses idênticas às da S01 (cache válido);
- limite operacional de runs respeitado dentro das subdivisões;
- 1.200 runs no mesmo segundo → `teto_atingido` (único caso sem solução);
- `intervalos_runs.csv` exportado pelo pipeline, com uma linha por mês.

```bash
pytest codigo-fonte/testes/test_rq77_workflow_runs.py codigo-fonte/testes/test_coleta_dora.py --cov=coleta_dora --cov-report=term-missing
```

Cobertura de `coleta_dora.py`: 99%.

## Retrato dos runs da S01 (100 repositórios)

| Item | Valor |
|---|---:|
| runs de `push` no default branch, na janela | 382.863 |
| `success` / `failure` / `startup_failure` | 310.548 / 36.579 / 961 |
| `cancelled` / `skipped` (ignorados nas métricas) | 32.859 / 1.910 |
| em andamento na hora da coleta (`queued`, sem `conclusion`) | 6 |
| ids duplicados | 0 |
| repositório-meses com mais de 1.000 runs (subdivididos) | 117 |
| maior volume num único dia | 758 (`headroomlabs-ai/headroom`, 14/07/2026) |
| runs reexecutados (`run_attempt > 1`) | 5.427 (1,4%) |
| workflows distintos por repositório (mediana) | 4 |

## Ameaças à validade (para o artigo)

- **Reexecuções escondem falhas.** A listagem devolve só a **última** tentativa de cada run. Um run que falhou e passou ao ser reexecutado conta como sucesso, e `run_started_at`/`updated_at` passam a ser os da última tentativa. Isso subestima o CFR (a) e pode distorcer episódios de recuperação em 1,4% dos runs. Recuperar as tentativas anteriores exigiria uma chamada por run (`/runs/{id}/attempts/{n}`), o que é inviável na escala da coleta.
- **Runs em andamento** na hora da coleta ficam sem `conclusion` e são ignorados. Como a janela termina antes da coleta, são poucos (6).
- **Renomeação do default branch** durante a janela (ex.: `master` → `main`) faz os runs do nome antigo ficarem de fora.
- O **limite operacional** de 20.000 runs por repositório continua descartando os projetos com CI mais intensa (ver RQ80).

## Para corrigir o dataset da S01

O `angular/angular` de abril precisa ser recoletado. Basta rodar o pipeline de novo na máquina que tem o cache (`dados/.cache/lab03_rest/`): todo o resto sai do cache, e o `intervalos_runs.csv` passa a existir.
