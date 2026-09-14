# RQ31 - Validar Complexidade, LOC e Duplicação nos Katas

Issue: #31. Etapa correspondente: Passo 2 (Preparação do Experimento) do LAB02.

## Objetivo

Validar se o CSV produzido pelo script de métricas estáticas da RQ30 está pronto para uso no experimento e executar um piloto do script sobre os 6 katas reais antes dos trials.

## Artefatos implementados

- `codigo-fonte/sprint-02/rq31_validar_metricas.py`: valida o arquivo de métricas gerado pela RQ30 e executa o piloto.
- `codigo-fonte/sprint-02/test_rq31.py`: testes offline da validação e do piloto.
- `dados/lab02_rq31_piloto.csv`: saída do piloto, gerada rodando a RQ30 sobre o `solucao.py` (stub) atual dos 6 katas descritos em [RQ32 — Seleção e Validação de Katas](RQ32_katas.md).

## Por que o piloto usa os katas reais (e não um sintético)

Diferente do piloto de tempo da [RQ29](RQ29_validacao_trials.md), que usa um comando sintético para não misturar instrumentação com dados do experimento, aqui o objeto de análise é o próprio código-fonte. Rodar o piloto sobre os 6 `solucao.py` reais (ainda como stub, antes de qualquer trial) valida a ferramenta de ponta a ponta — inclusive a detecção de complexidade e a chamada ao `jscpd` — sem depender de um trial já resolvido e sem contaminar `dados/lab02_rq30_metricas_estaticas.csv` com dados de piloto.

## Regras de validação

O validador confere:

- cabeçalho exatamente igual ao schema da RQ30;
- campos obrigatórios preenchidos;
- `tratamento` limitado a `com_ia` ou `sem_ia`;
- ausência de combinação duplicada de `participante`/`kata`/`tratamento` (cada trial gera uma medição);
- `loc` não negativo;
- complexidade média coerente com a presença de funções no arquivo (arquivo com função analisada não pode ter complexidade menor que 1);
- Índice de Manutenibilidade no intervalo `[0, 100]`;
- `duplicacao_disponivel` booleano, com `duplicacao_percentual` preenchido e em `[0, 100]` somente quando a duplicação pôde ser medida;
- `arquivo` apontando para um `.py`.

## Como validar métricas reais

Na raiz do projeto:

```powershell
python codigo-fonte/sprint-02/rq31_validar_metricas.py --csv dados/lab02_rq30_metricas_estaticas.csv
```

## Como executar o piloto

Na raiz do projeto:

```powershell
python codigo-fonte/sprint-02/rq31_validar_metricas.py --piloto --saida-piloto dados/lab02_rq31_piloto.csv
```

Em ambiente sem Node.js/`jscpd`, adicione `--sem-duplicacao` — a validação continua passando, apenas sem a métrica de duplicação.

## Critério de aceite

A RQ31 é considerada atendida quando:

- os testes automatizados de RQ30 e RQ31 passam;
- o piloto roda sobre os 6 katas reais e gera 6 registros válidos;
- o validador acusa erro para registros inconsistentes (schema incompatível, tratamento inválido, duplicidade, métricas fora de intervalo);
- o CSV real das métricas pode ser validado antes da análise estatística da RQ3.
