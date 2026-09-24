# RQ57 - Preparar Pipeline de Dados do Dashboard

## Objetivo

Preparar, com Pandas, a base consolidada que alimenta o dashboard da RQ58. O pipeline junta os dados de tempo da RQ28 com as metricas estaticas da RQ30, mantendo uma linha por trial e produzindo tambem um resumo por participante e tratamento.

## Implementacao

Script principal:

```text
codigo-fonte/sprint-03/rq57_pipeline_dashboard.py
```

Testes automatizados:

```text
codigo-fonte/sprint-03/test_rq57.py
```

Entradas padrao:

```text
dados/lab02_rq28_tempos.csv
dados/lab02_rq30_metricas_estaticas.csv
```

Saidas geradas:

```text
dados/lab02_rq57_dataset_unificado.csv
dados/lab02_rq57_resumo_tratamento.csv
```

## Transformacoes

O pipeline executa as seguintes etapas:

- carrega a RQ28 e remove duplicidades por `trial_id`, preservando a primeira ocorrencia para garantir uma linha por trial;
- converte duracao e limite para valores numericos;
- calcula `duracao_efetiva_segundos`, usando a duracao real quando o trial teve sucesso e o limite quando o trial foi censurado;
- calcula `sucesso_binario`, coerente com os testes estatisticos da RQ52;
- marca `issue_informada`, tratando `<ISSUE>` como placeholder e nao como issue valida;
- carrega a RQ30 e calcula `complexidade_por_loc`, seguindo a normalizacao usada na RQ53;
- faz o join por `trial_id`;
- marca `metricas_rq30_disponiveis` e `duplicacao_percentual_disponivel`;
- gera um resumo por `(participante, tratamento)` com contagem de trials, cobertura de issues, cobertura de metricas, mediana de tempo, taxa de sucesso e medianas das metricas estaticas disponiveis.

## Comandos

Gerar os CSVs da RQ57:

```powershell
python codigo-fonte/sprint-03/rq57_pipeline_dashboard.py
```

Rodar os testes da RQ57:

```powershell
cd codigo-fonte/sprint-03
python -m unittest test_rq57.py
```

## Resultado Atual

Com os dados atuais do repositorio, o pipeline gerou:

- dataset unificado: 12 trials unicos;
- resumo por participante/tratamento: 5 linhas;
- RQ30 disponivel para 2 trials, ambos do participante `bblop` no tratamento `com_ia`;
- todos os trials consolidados no resumo atual possuem sucesso registrado;
- alguns trials ainda nao possuem metricas estaticas RQ30, entao campos como `complexidade_por_loc`, `duplicacao_percentual` e `indice_manutenibilidade` permanecem vazios nesses casos.

Resumo atual por participante/tratamento:

```text
Arthur      sem_ia  n=2  mediana_tempo=787.288761s  metricas=0
Joao_Pedro  com_ia  n=1  mediana_tempo=72.250000s   metricas=0
Joao_Pedro  sem_ia  n=2  mediana_tempo=974.077500s  metricas=0
bblop       com_ia  n=2  mediana_tempo=35.133000s   metricas=2
bblop       sem_ia  n=5  mediana_tempo=0.281000s    metricas=0
```

## Limitacoes

Esta entrega prepara a base para o dashboard, mas ainda depende da coleta completa da RQ30 para melhorar a comparacao de metricas estaticas. Tambem foram encontrados registros antigos da RQ28 com placeholder `<ISSUE>`; o pipeline nao remove esses trials, mas expõe a cobertura de issues no campo `issue_informada` e no resumo `n_issues_informadas`.

A deduplicacao por `trial_id` foi aplicada apenas no dataset preparado para o dashboard. Ela nao substitui uma correcao definitiva do CSV bruto da RQ28.
