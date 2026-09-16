# RQ43 - Inovacao - Integridade e Rastreabilidade dos Dados Reais dos Trials

## Objetivo

Validar se os dados reais dos trials do LAB02 podem ser rastreados de ponta a ponta antes da analise:

- registro de tempo da RQ28;
- pasta real do kata;
- arquivo `solucao.py` final;
- registro de prompt/interacao para trials `com_ia`;
- medicao estatica da RQ30 vinculada ao mesmo `trial_id`.

## Implementacao

Foi criado o script:

```text
codigo-fonte/sprint-02/rq43_validar_rastreabilidade_trials.py
```

O script reaproveita a validacao da RQ29 para o CSV de tempos e valida o CSV de metricas RQ30 pelo schema esperado, sem recalcular metricas. Em seguida, cruza os registros por `trial_id` e gera uma linha por trial com flags de rastreabilidade.

Arquivos de saida:

```text
dados/lab02_rq43_integridade_trials.csv
dados/lab02_rq43_integridade_trials.json
```

## Criterios verificados

Um trial fica rastreavel quando:

- o registro da RQ28 e valido;
- o diretorio registrado ainda existe;
- existe `solucao.py` no diretorio do kata;
- se o tratamento for `com_ia`, existe registro de prompt/interacao;
- se o trial teve sucesso, existe medicao RQ30 com o mesmo `trial_id`;
- nao ha metricas RQ30 apontando para `trial_id` inexistente na RQ28.

## Comandos usados

Validacao das metricas reais:

```powershell
python codigo-fonte/sprint-02/rq31_validar_metricas.py --csv dados/lab02_rq30_metricas_estaticas.csv
```

Validacao integrada da RQ43:

```powershell
python codigo-fonte/sprint-02/rq43_validar_rastreabilidade_trials.py
```

Testes offline da RQ43:

```powershell
cd codigo-fonte/sprint-02
python -m unittest test_rq43.py
```

## Resultado atual

Com os dados reais existentes no repositorio:

- trials reais: 2;
- trials rastreaveis: 2;
- trials com alerta: 0;
- RQ28 valido: `True`;
- RQ30 valido: `True`;
- status final: integridade e rastreabilidade OK.

## Observacao

A duplicacao da RQ30 foi marcada como indisponivel (`--sem-duplicacao`) para nao depender de Node.js/`jscpd` nesta validacao. As demais metricas estruturais foram coletadas com Radon conforme a RQ30.
