# RQ58 - Dashboard Inicial do LAB02

## Objetivo

Construir um dashboard inicial do LAB02 com Matplotlib/Seaborn para acompanhar:

- quantidade de trials por tratamento;
- tempo mediano por participante e tratamento;
- cobertura de issues informadas e medicoes RQ30;
- metricas estaticas disponiveis, sem imputar valores ausentes.

Esta entrega usa a RQ57 como fonte preparada. Assim, o dashboard consome o dataset ja deduplicado por `trial_id` e com campos derivados como `duracao_efetiva_segundos`, `sucesso_binario`, `issue_informada`, `metricas_rq30_disponiveis` e `complexidade_por_loc`.

## Implementacao

Script:

```text
codigo-fonte/sprint-02/rq58_dashboard.py
```

Entradas padrao:

```text
dados/lab02_rq57_dataset_unificado.csv
dados/lab02_rq57_resumo_tratamento.csv
```

Saidas:

```text
dados/lab02_rq58_resumo_dashboard.csv
dados/rq58_dashboard_inicial.png
```

## Paineis do Dashboard

O PNG gerado possui quatro paineis:

1. **Trials unicos por tratamento** - conta os trials apos a deduplicacao da RQ57.
2. **Mediana de tempo por participante** - compara `com_ia` e `sem_ia` por participante quando ambos existem.
3. **Cobertura de issues e RQ30** - mostra quantos registros possuem issue informada e quantos possuem medicao estatica.
4. **Complexidade por LOC** - exibe apenas os pontos com RQ30 disponivel, deixando explicita a ausencia de metricas para tratamentos sem cobertura.

## Comandos

Gerar resumo e dashboard:

```powershell
python codigo-fonte/sprint-02/rq58_dashboard.py
```

Gerar apenas o CSV-resumo:

```powershell
python codigo-fonte/sprint-02/rq58_dashboard.py --sem-grafico
```

Testes offline:

```powershell
cd codigo-fonte/sprint-02
python -m unittest test_rq58.py
```

## Resultado Atual

Com os dados atuais do repositorio:

- RQ57 consolida 12 trials unicos;
- 8 dos 12 trials possuem issue informada;
- 2 dos 12 trials possuem metricas RQ30 vinculadas;
- a taxa de sucesso aparece como 100% nos trials consolidados;
- a parte de metricas estaticas ainda e preliminar, pois so ha RQ30 para trials `com_ia` do participante `bblop`.

## Limitacoes

O dashboard ja funciona como visao inicial, mas a versao final depende de:

- completar a coleta RQ30 para os demais trials bem-sucedidos;
- corrigir ou substituir registros antigos com `<ISSUE>`;
- reexecutar RQ57 e RQ58 depois da consolidacao final dos CSVs;
- atualizar RQ51-RQ54 antes de usar o dashboard como evidencia conclusiva no relatorio final.
