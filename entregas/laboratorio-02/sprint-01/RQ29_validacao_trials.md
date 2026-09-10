# RQ29 - Validacao do Registro dos Trials e Piloto da Coleta

Issue: #29. Etapa correspondente: preparacao operacional da coleta do LAB02.

## Objetivo

Validar se o CSV produzido pelo cronometro da RQ28 esta pronto para uso no experimento e executar um piloto da instrumentacao antes dos trials reais.

## Artefatos implementados

- `codigo-fonte/sprint-02/rq29_validar_trials.py`: valida o arquivo de trials gerado pela RQ28.
- `codigo-fonte/sprint-02/test_rq29.py`: testes offline da validacao e do piloto.
- `dados/lab02_rq29_piloto.csv`: saida esperada do piloto sintetico, gerada sem resolver kata real.

## Regras de validacao

O validador confere:

- cabecalho exatamente igual ao schema da RQ28;
- campos obrigatorios preenchidos;
- `trial_id` em formato UUID e sem duplicidade;
- `tratamento` limitado a `com_ia` ou `sem_ia`;
- `status` limitado a `sucesso`, `limite_atingido`, `interrompido` ou `erro_execucao`;
- coerencia entre `status`, `sucesso` e `censurado`;
- duracao nao negativa, menor ou igual ao limite, e igual ao limite quando censurada;
- limite no intervalo do experimento, ate 2100 segundos;
- timestamps ISO validos, com fim posterior ou igual ao inicio;
- numero de verificacoes inteiro e nao negativo;
- `comando_testes` como lista JSON nao vazia de strings.

## Como validar registros reais

Na raiz do projeto:

```powershell
python codigo-fonte/sprint-02/rq29_validar_trials.py --csv dados/lab02_rq28_tempos.csv
```

Para relatorio estruturado:

```powershell
python codigo-fonte/sprint-02/rq29_validar_trials.py --csv dados/lab02_rq28_tempos.csv --json
```

## Como executar o piloto

Na raiz do projeto:

```powershell
python codigo-fonte/sprint-02/rq29_validar_trials.py --piloto --saida-piloto dados/lab02_rq29_piloto.csv
```

O piloto executa um comando de teste sintetico que retorna sucesso imediatamente, grava um registro no mesmo formato da RQ28 e valida o CSV resultante. Ele nao deve ser misturado com `dados/lab02_rq28_tempos.csv`, pois nao representa uma medicao real de participante resolvendo kata.

## Criterio de aceite

A RQ29 e considerada atendida quando:

- os testes automatizados de RQ28 e RQ29 passam;
- o piloto gera ao menos um registro valido;
- o validador acusa erro para registros inconsistentes;
- o CSV real dos trials pode ser validado antes da analise estatistica.
