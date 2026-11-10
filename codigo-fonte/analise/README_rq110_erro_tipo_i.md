# RQ110 — Q1: simulações e erro Tipo I

Executa 10.000 experimentos sob H0, aplicando os testes t pareado e Wilcoxon da #105 às mesmas amostras. Usa o gerador `h0` da #104 e os parâmetros reais calibrados na #103. Não altera o dashboard nem implementa poder estatístico.

## Execução

Na raiz do projeto, com as dependências de `requirements.txt` instaladas:

```powershell
python codigo-fonte/analise/rq110_erro_tipo_i.py
```

Padrões: 10.000 repetições, 30 pares definidos pelo contrato da #103, semente 110, testes bilaterais e alfa 0,05. O número de pares é lido do contrato, não confundido com o número de experimentos.

A entrega fica em `entregas/experimento-cache/RQ110/`. O programa recusa sobrescrever uma pasta não vazia. Para reproduzir a entrega em outra pasta:

```powershell
python codigo-fonte/analise/rq110_erro_tipo_i.py --saida dados/.cache/rq110_reproducao --repeticoes 10000 --semente 110 --alfa 0.05
```

`--parametros` aceita outro contrato compatível da #103. Preserve a mesma versão de Python, NumPy e SciPy, os parâmetros e o código para reprodução. Como o gerador da #104 sorteia arrays em lote, mudar o número de repetições muda a sequência; uma execução menor não é necessariamente um prefixo da maior.

## Método e saídas

H0 é imposta por troca independente dos rótulos com/sem cache em cada par, com probabilidade 1/2. As diferenças têm média zero e distribuição simétrica por construção. A simulação observada, com ganho de cache, não é utilizada para medir erro Tipo I.

- `repeticoes.csv`: uma linha por experimento, com estatísticas, p-valores, decisões estritas `p < alfa`, quantidade de trocas de rótulo e erros por teste.
- `resultados.json`: taxa de rejeição sob H0, contagens, erro padrão Monte Carlo, IC binomial exato de 95%, desvio do nível nominal, versões e hashes.
- `parametros_origem.json`: cópia exata da entrada usada.
- `RELATORIO.md`: resultados e interpretação escrita.

Nenhuma amostra é descartada pelo resultado. Se um teste falhar ou retornar valores não finitos, a falha fica registrada e sua taxa oficial fica indisponível: o denominador não é reduzido silenciosamente. O programa termina com código 1 se houver falhas. Erros de entrada interrompem antes da publicação dos resultados. Uma interrupção durante a simulação exige reinício; não há retomada parcial.

O IC mede a incerteza Monte Carlo condicionada ao cenário artificial, não a incerteza dos tempos reais. A dependência temporal da coleta não é reproduzida. Não interpretar a taxa como validade universal dos testes, nem confundir com poder ou probabilidade de H0 ser verdadeira. O Wilcoxon mantém o método exato com empates da #105 para até 50 diferenças não nulas.

## Testes

```powershell
python -m pytest codigo-fonte/testes/test_rq110_erro_tipo_i.py codigo-fonte/testes/test_rq104_gerador_simulacao.py codigo-fonte/testes/test_rq105_testes_pareados.py -q
```

Cobrem reprodutibilidade, correspondência com o gerador H0 e os testes existentes, decisão estrita no limite de alfa, denominador, IC, argumentos inválidos, falhas preservadas e exportação sem sobrescrita.

Referência: [intervalo binomial exato no SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats._result_classes.BinomTestResult.proportion_ci.html).
