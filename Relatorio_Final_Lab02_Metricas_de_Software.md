# Relatorio Final - LAB02 Metricas de Software

## Resumo Executivo

Este relatorio consolida o experimento do LAB02 sobre o uso de assistentes de IA generativa na resolucao de katas de programacao em Python. O objetivo e comparar os tratamentos `com_ia` e `sem_ia` em tres dimensoes:

- RQ1: tempo de resolucao ate os testes passarem;
- RQ2: sucesso funcional e defeitos observados;
- RQ3: estrutura do codigo produzido, usando metricas estaticas como complexidade, LOC, indice de manutenibilidade e duplicacao.

No estado atual do repositorio, a base de tempo da RQ28 ja possui trials suficientes para alimentar uma primeira visao do dashboard. A RQ57 tambem ja prepara um dataset unificado para a RQ58. Entretanto, a coleta da RQ30 ainda esta parcial: apenas 2 dos 12 trials unicos consolidados possuem metricas estaticas vinculadas por `trial_id`. Por isso, qualquer conclusao sobre RQ3 ainda deve ser tratada como preliminar.

## 1. Contexto e Objetivo

O experimento segue o desenho definido na RQ33: comparar tarefas de programacao resolvidas com e sem assistente de IA, usando katas autorais e testes automatizados. A linguagem usada e Python, com coleta de tempo por script de cronometragem e metricas estruturais extraidas do arquivo `solucao.py` final de cada trial.

O estudo busca responder:

- O uso de IA reduz o tempo de resolucao?
- O uso de IA altera a taxa de sucesso funcional?
- O uso de IA altera a complexidade, tamanho ou duplicacao do codigo produzido?

## 2. Fontes de Dados

As principais fontes usadas ate este ponto sao:

| Fonte | Arquivo | Papel no relatorio |
|---|---|---|
| RQ28 | `dados/lab02_rq28_tempos.csv` | Tempo, status, tratamento, participante, kata e comandos de teste |
| RQ30 | `dados/lab02_rq30_metricas_estaticas.csv` | Complexidade, LOC, MI e duplicacao por trial |
| RQ57 | `dados/lab02_rq57_dataset_unificado.csv` | Dataset unido por `trial_id`, pronto para dashboard |
| RQ57 | `dados/lab02_rq57_resumo_tratamento.csv` | Resumo por participante e tratamento |
| RQ58 | `dados/rq58_dashboard_inicial.png` | Dashboard inicial com a cobertura disponivel |

## 3. Estado Atual da Consolidacao

A RQ57 consolida os dados atuais em:

- 12 trials unicos no dataset unificado;
- 5 grupos por participante/tratamento;
- 8 trials com issue informada corretamente;
- 2 trials com metricas estaticas RQ30 disponiveis;
- 0 duplicidades de `trial_id` no dataset preparado.

Resumo atual da RQ57:

| Participante | Tratamento | Trials | Issues informadas | Medicoes RQ30 | Mediana do tempo (s) | Taxa de sucesso |
|---|---:|---:|---:|---:|---:|---:|
| Arthur | sem_ia | 2 | 2 | 0 | 787.2887615 | 1.0 |
| Joao_Pedro | com_ia | 1 | 1 | 0 | 72.25 | 1.0 |
| Joao_Pedro | sem_ia | 2 | 2 | 0 | 974.0775 | 1.0 |
| bblop | com_ia | 2 | 2 | 2 | 35.133 | 1.0 |
| bblop | sem_ia | 5 | 1 | 0 | 0.281 | 1.0 |

## 4. Metodologia Sintetica

Cada trial foi cronometrado pela RQ28. O comando de teste usado em cada kata segue o padrao:

```powershell
python -m unittest discover -s testes
```

O script registra duracao, status, sucesso, censura, numero de verificacoes e comando executado. Para preparar os dados do dashboard, a RQ57:

- remove duplicidades por `trial_id`;
- calcula `duracao_efetiva_segundos`;
- calcula `sucesso_binario`;
- marca se a issue foi informada;
- junta RQ28 e RQ30 por `trial_id`;
- calcula `complexidade_por_loc`;
- cria flags de cobertura de metricas estaticas.

## 5. Resultados Preliminares

### RQ1 - Tempo de Resolucao

Os dados atuais permitem uma leitura preliminar por participante e tratamento. Ainda assim, os resultados estatisticos finais devem aguardar a consolidacao completa das medicoes e a reexecucao dos scripts RQ51-RQ53 sobre os CSVs atualizados.

### RQ2 - Sucesso e Defeitos

No dataset unificado atual, todos os 12 trials consolidados aparecem como sucesso. Isso sugere ausencia de falhas funcionais nos trials registrados, mas ainda e necessario verificar se todos os trials esperados do desenho experimental foram coletados e se os registros antigos com placeholder de issue devem ser mantidos ou substituidos.

### RQ3 - Metricas Estaticas

A analise estrutural ainda esta incompleta. Apenas os trials `com_ia` do participante `bblop` possuem RQ30 vinculada ate o momento. Assim, qualquer comparacao entre `com_ia` e `sem_ia` para complexidade, LOC, duplicacao ou indice de manutenibilidade ainda nao e conclusiva.

## 6. Limitacoes Atuais

- A RQ30 ainda precisa ser executada para a maioria dos trials bem-sucedidos.
- Alguns registros antigos da RQ28 ainda usam `<ISSUE>` como placeholder.
- Os arquivos de RQ51, RQ52 e RQ53 existentes podem estar desatualizados em relacao ao CSV atual da RQ28, pois seus JSONs indicam execucao anterior com menos trials.
- A RQ57 corrige duplicidade apenas no dataset preparado para dashboard; ela nao altera o CSV bruto da RQ28.

## 7. Proximos Passos

1. Completar a coleta RQ30 para todos os trials bem-sucedidos.
2. Reexecutar RQ57 depois da nova RQ30.
3. Reexecutar RQ51, RQ52, RQ53 e RQ54 com os CSVs atualizados.
4. Atualizar o dashboard da RQ58 usando o dataset consolidado.
5. Escrever os resultados finais da RQ59.
6. Fechar a discussao e conclusao na RQ60.

