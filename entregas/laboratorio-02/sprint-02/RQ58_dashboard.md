# RQ58 - Dashboard Inicial do LAB02

## Objetivo

Construir uma primeira versao do dashboard do LAB02 com Matplotlib/Seaborn para acompanhar:

- tempo de resolucao dos trials da RQ28;
- taxa de sucesso por tratamento;
- metricas estaticas disponiveis na RQ30.

Esta entrega e inicial porque os dados ainda estao em consolidacao. O dashboard nao substitui a versao final da RQ58: ele mostra o que ja existe e destaca lacunas de cobertura.

## Implementacao

Script criado:

```text
codigo-fonte/sprint-02/rq58_dashboard.py
```

Entradas padrao:

```text
dados/lab02_rq28_tempos.csv
dados/lab02_rq30_metricas_estaticas.csv
```

Saidas:

```text
dados/lab02_rq58_resumo_dashboard.csv
dados/rq58_dashboard_inicial.png
```

## Comandos

Gerar resumo e dashboard:

```powershell
python codigo-fonte/sprint-02/rq58_dashboard.py
```

Gerar apenas o CSV-resumo, sem depender de pandas/matplotlib/seaborn:

```powershell
python codigo-fonte/sprint-02/rq58_dashboard.py --sem-grafico
```

Testes offline:

```powershell
cd codigo-fonte/sprint-02
python -m unittest test_rq58.py
```

## Resultado Atual

Com os dados presentes no repositorio, a RQ28 ja permite visualizar tempos e sucesso por tratamento. A RQ30 ainda tem cobertura parcial, entao a parte de metricas estaticas deve ser interpretada como preliminar.

Lacunas conhecidas para a versao final:

- coletar RQ30 para todos os trials bem-sucedidos;
- substituir registros antigos que ainda usam `<ISSUE>` por trials com issue correta, quando necessario;
- atualizar o dashboard depois que os demais integrantes consolidarem os CSVs.
