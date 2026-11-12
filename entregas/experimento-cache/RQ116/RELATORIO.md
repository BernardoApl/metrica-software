# RQ116 — Q3: erro tipo I com violações de pressupostos

10.000 amostras por situação e tamanho, com efeito zero; semente 116; testes bilaterais; decisão p < α.

Erro tipo I = proporção de amostras com p < α quando não há efeito na média. O esperado é α.

## Sem violação

Violação: diferenças simétricas em torno de zero.

| Pares | t α=0,05 | Wilcoxon α=0,05 | t α=0,01 | Wilcoxon α=0,01 | Assimetria de d |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 3,50% | 4,22% | 0,66% | 0,82% | 0,05 |
| 20 | 4,29% | 4,87% | 0,48% | 0,90% | 0,01 |
| 30 | 4,45% | 4,72% | 0,61% | 0,89% | -0,00 |
| 50 | 4,89% | 5,18% | 0,73% | 1,00% | 0,01 |

Com 30 pares: t pareado 4,5% (conservador); Wilcoxon 4,7% (perto do nominal). Ao variar a amostra, t pareado vai de 3,5% (10 pares) a 4,9% (50 pares); Wilcoxon vai de 4,2% (10 pares) a 5,2% (50 pares).

## Outliers (10% × 5)

Violação: cauda pesada: 10% das diferenças 5 vezes maiores.

| Pares | t α=0,05 | Wilcoxon α=0,05 | t α=0,01 | Wilcoxon α=0,01 | Assimetria de d |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 2,85% | 4,40% | 0,27% | 0,87% | 0,04 |
| 20 | 3,78% | 5,05% | 0,35% | 0,93% | -0,08 |
| 30 | 3,64% | 5,03% | 0,43% | 0,93% | -0,06 |
| 50 | 3,94% | 4,94% | 0,43% | 0,92% | 0,08 |

Com 30 pares: t pareado 3,6% (conservador); Wilcoxon 5,0% (perto do nominal). Ao variar a amostra, t pareado vai de 2,9% (10 pares) a 3,9% (50 pares); Wilcoxon vai de 4,4% (10 pares) a 4,9% (50 pares).

## Assimetria real

Violação: diferenças assimétricas com média zero.

| Pares | t α=0,05 | Wilcoxon α=0,05 | t α=0,01 | Wilcoxon α=0,01 | Assimetria de d |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 12,26% | 10,65% | 5,42% | 3,97% | 1,84 |
| 20 | 9,72% | 16,49% | 4,78% | 5,63% | 1,84 |
| 30 | 8,35% | 21,63% | 3,72% | 8,72% | 1,84 |
| 50 | 6,93% | 32,40% | 2,57% | 14,27% | 1,84 |

Com 30 pares: t pareado 8,3% (liberal); Wilcoxon 21,6% (liberal). Ao variar a amostra, t pareado vai de 12,3% (10 pares) a 6,9% (50 pares); Wilcoxon vai de 10,7% (10 pares) a 32,4% (50 pares). A média é zero, mas a distribuição não é simétrica: para a pergunta sobre o tempo médio, as rejeições do Wilcoxon são falsos positivos, e crescem com a amostra porque ele detecta a assimetria.

## Limitações

As amostras reamostram os 30 pares reais; outliers (10% × 5) e tamanhos são escolhas do grupo para estressar os testes. A tendência temporal da coleta não é reproduzida. Com 10.000 amostras, o erro Monte Carlo é de cerca de ±0,4 p.p. perto de 5% (IC 95% Clopper-Pearson em `resultados.json`).
