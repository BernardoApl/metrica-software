# RQ79 — CFR de CI e Tempo de Recuperação com Testes

Issue: #79. Cobre a RQ 03 (a) e a RQ 04 do LAB03.

## Código

- [`codigo-fonte/metricas/ci.py`](../../../codigo-fonte/metricas/ci.py): funções puras, sem acesso à rede.
- [`codigo-fonte/testes/test_metricas_ci.py`](../../../codigo-fonte/testes/test_metricas_ci.py): testes com pytest e fixtures montadas à mão.

```bash
pytest codigo-fonte/testes/test_metricas_ci.py --cov=metricas --cov-report=term-missing
```

## Definições implementadas

| Função | O que faz |
|---|---|
| `classificar_conclusao` | `success` → sucesso; `failure`, `timed_out`, `startup_failure` → falha; qualquer outro valor (incluindo vazio) → ignorado |
| `filtrar_runs_validos` | mantém só `event = push`, `head_branch = default branch`, `created_at` dentro da janela e conclusão válida |
| `cfr_ci` | CFR (a) = falhas ÷ (falhas + sucessos). Sem runs válidos, o CFR é indefinido (`None`), e não 0 |
| `episodios_de_falha` | episódios de **um** workflow: começam na primeira falha após um sucesso e terminam no próximo sucesso. Duração = `updated_at` do sucesso − `run_started_at` da primeira falha (`created_at` se o campo faltar) |
| `tempo_de_recuperacao` | agrupa por `workflow_id`, junta os episódios de todos os workflows e tira a mediana em horas |
| `metricas_ci_repositorio` | aplica o filtro e devolve CFR (a), mediana de recuperação e contagens de censura numa única linha por repositório |

### Decisões que precisam ir para a Metodologia

- **Execuções ignoradas não quebram episódios.** Um `cancelled` entre duas falhas não encerra o episódio nem inicia outro.
- **Censura à direita.** Um episódio sem sucesso até o fim da janela fica marcado como `censurado`, com a duração parcial até o fim da janela (limite inferior). Ele **não entra na mediana**, e a proporção de censurados é reportada por repositório (`proporcao_episodios_censurados`).
- **Censura à esquerda.** Se a primeira execução válida de um workflow na janela já é uma falha, não sabemos quando o episódio começou, porque não houve sucesso anterior observado. O episódio é marcado como `censura_esquerda` e também fica fora da mediana. Isso não está no enunciado; é uma decisão do grupo, para não subestimar o tempo de recuperação.
- **Repositório sem falhas** tem mediana de recuperação indefinida (`None`), e não 0 h.

## Casos de borda testados

- Exemplo numérico da RQ 04 (09:00 sucesso, 10:00 e 10:30 falha, sucesso que termina às 11:20 → 1h20).
- Execuções `cancelled`/`skipped` ignoradas no CFR e no meio de um episódio.
- Falha nunca recuperada (censurada) e falha no início da janela (censura à esquerda).
- Runs de `schedule`/`workflow_dispatch`, de outro branch e fora da janela descartados.
- Sucesso de um workflow que não encerra a falha de outro workflow.
- Repositório sem falhas e conjunto vazio de runs.

Cobertura do módulo `metricas.ci`: 100%.
