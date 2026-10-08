# RQ80 — Integrar Pipeline, Testes e GitHub Actions

Issue: #80. Requisitos de engenharia da seção 7 do enunciado, para a entrega Lab03S01.

## Requisitos da seção 7 e como foram atendidos

| Requisito | Como foi atendido |
|---|---|
| Execução com um único comando | `python codigo-fonte/pipeline_dora.py --config config/pipeline.json` (ver [README](../../../README.md)) |
| Token fora do repositório | lido de `GITHUB_TOKEN`/`GH_TOKEN` ou de `.env`, que está no `.gitignore` |
| Cache local e retomada | [`cliente_rest.py`](../../../codigo-fonte/coleta/cliente_rest.py) grava cada resposta em `dados/.cache/lab03_rest/` (um JSON por URL, com escrita atômica). Rodar o mesmo comando de novo reaproveita tudo |
| Rate limit | lê `X-RateLimit-Remaining`/`X-RateLimit-Reset` a cada resposta e dorme até o reset. Também trata 403/429 com `Retry-After` e o limite secundário (espera de ≥ 60 s) |
| Erros temporários | 5xx e falhas de rede: backoff exponencial de 1, 2, 4, 8 e 16 s, com 6 tentativas |
| Testes com pytest e fixtures | `codigo-fonte/testes/test_metricas_ci.py`, `test_metricas_dora.py`, `test_cliente_rest.py`, `test_coleta_dora.py` e `test_pipeline_dora.py`, todos offline |
| Cobertura ≥ 80% do módulo de métricas | `pytest --cov=metricas` → 100% (`metricas/ci.py` e `metricas/dora.py`) |
| CI do grupo | [`.github/workflows/testes.yml`](../../../.github/workflows/testes.yml): roda a cada push e PR, com `--cov-fail-under=80` |
| Funil de seleção | `dados/lab03/funil_selecao.csv`, gerado automaticamente, mais o motivo por candidato em `candidatos_avaliados.csv` |
| Dicionário de dados | [`dados/lab03/DICIONARIO.md`](../../../dados/lab03/DICIONARIO.md) |
| Subdivisão mensal da janela | [`coleta_dora.py`](../../../codigo-fonte/coleta/coleta_dora.py): um intervalo por mês civil. Se o mês informar mais de 1.000 runs, ele é dividido ao meio até caber, e um único dia acima de 1.000 é registrado em `intervalos_no_teto` |

## Achados da coleta que vão para Metodologia e Ameaças

- **O `total_count` de `/actions/runs` satura.** Para o `openclaw/openclaw`, a consulta do mês inteiro informou 2.500 runs, enquanto um único dia informou 1.332. O total serve para decidir subdivisões e para descartar quem tem menos de 50 runs, mas não estima o volume de repositórios muito ativos.
- **Teto operacional por repositório** (`limite_runs_por_repositorio`, 20.000 runs na janela). Repositórios com milhares de runs por dia custariam milhares de chamadas cada. A coleta deles é interrompida ao passar do teto, e o descarte aparece no funil (`limite_operacional_runs`). Isso enviesa a amostra contra os projetos com CI mais intensa, e precisa ser discutido como ameaça à validade externa.
- **Ordem de avaliação.** Os candidatos são avaliados por estrelas, em ordem decrescente, até a meta. Os aptos que ficam depois da meta aparecem no funil como não avaliados. Com `trabalhadores > 1` a avaliação é paralela, mas os resultados são consumidos na ordem: o funil e a amostra são idênticos aos de uma execução sequencial, e há um teste que garante isso.
- **Pré-filtro sem API.** Forks, repositórios arquivados, desabilitados, vazios ou sem default branch saem antes de qualquer chamada REST.

## Fora do escopo desta issue

Lead time (RQ 02) e CFR de entrega (RQ 03 b) usam o `compare` entre releases (integrante B). O pipeline já salva, em `releases.csv`, as releases da janela e a anterior a ela, e as colunas novas entram em `metricas_repositorios.csv` quando essa issue for integrada.

## Resultado da coleta Lab03S01 (100 repositórios)

Coleta executada em 08/10/2026 com `config/pipeline.json` (janela provisória 2025-10-01 a 2026-09-30, 8 trabalhadores), com 9.146 requisições à API e 3.452 respostas reaproveitadas do cache. Os arquivos estão em `dados/lab03/`.

| Etapa | Entrada | Removidos | Aprovados |
|---|---:|---:|---:|
| candidatos_iniciais | 8000 | 0 | 8000 |
| metadados_validos_e_ativos (481 arquivados) | 8000 | 481 | 7519 |
| avaliados_ate_a_meta | 7519 | 7247 | 272 |
| api_acessivel | 272 | 0 | 272 |
| usa_github_actions | 272 | 19 | 253 |
| minimo_releases (≥ 5) | 253 | 121 | 132 |
| limite_operacional_runs (≤ 20.000) | 132 | 18 | 114 |
| minimo_runs (≥ 50 válidos) | 114 | 14 | **100** |

Visão inicial, apenas para checagem de sanidade (a análise fica para a S03):

- 382.863 runs de `push` no default branch, todos dentro da janela. Nenhum dia passou do teto de 1.000 runs (`intervalos_no_teto = 0`).
- 18.153 releases coletadas: 8.715 publicadas dentro da janela (contando pré-releases) e as demais anteriores a ela, mantidas como base do `compare` do lead time.
- Frequência mediana de 0,54 release/semana (IQR 0,23–1,22); CFR (a) mediano de 5,1% (IQR 2,4%–12,2%); recuperação mediana de 3,4 h (IQR 1,5–7,6 h).
- 7 repositórios não tiveram nenhum episódio completo de falha, e por isso estão com a recuperação indefinida.
- O teto operacional removeu 18 repositórios, cerca de 14% dos que passaram pelo critério de releases. É um viés relevante para a seção de ameaças à validade.
