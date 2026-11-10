# RQ113 — Q2 e Q3: poder dos testes pareados

10,000 amostras por cenário e por efeito; semente 113; testes bilaterais. Poder = proporção de amostras com p < α. Em d_z = 0 a proporção é o erro tipo I do cenário.

Efeito: δ = d_z × σ_d somado a cada diferença d = t_sem − t_com (δ > 0: cache mais rápido).

## Base (30 pares) (Q2)

Nenhuma: variação real das diferenças, simetrizada em torno de zero. n = 30; σ_d = 1.296 ms; assimetria de d sob H0 = -0.01.

| d_z | δ (ms) | t pareado α=0,05 | Wilcoxon α=0,05 | t pareado α=0,01 | Wilcoxon α=0,01 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.0 | 0.000 | 4.5% | 4.9% | 0.8% | 1.0% |
| 0.1 | 0.130 | 8.6% | 12.6% | 1.9% | 3.7% |
| 0.2 | 0.259 | 20.2% | 26.3% | 7.0% | 9.9% |
| 0.3 | 0.389 | 38.6% | 48.5% | 18.4% | 24.9% |
| 0.4 | 0.518 | 58.1% | 72.6% | 34.7% | 47.3% |
| 0.5 | 0.648 | 76.1% | 86.9% | 53.1% | 68.0% |
| 0.6 | 0.778 | 87.6% | 94.4% | 71.0% | 81.8% |
| 0.8 | 1.037 | 98.1% | 99.7% | 92.2% | 97.9% |
| 1.0 | 1.296 | 99.9% | 100.0% | 98.8% | 99.6% |

Erro tipo I (d_z = 0): t 4.5%, Wilcoxon 4.9%. d_z para 80% de poder: t 0.53, Wilcoxon 0.45. Maior diferença de poder (t − Wilcoxon): -14.5 p.p. em d_z = 0.4.

## Amostra pequena (10 pares) (Q3)

N = 10: o t depende mais da normalidade; o wilcoxon fica mais discreto. n = 10; σ_d = 1.296 ms; assimetria de d sob H0 = 0.00.

| d_z | δ (ms) | t pareado α=0,05 | Wilcoxon α=0,05 | t pareado α=0,01 | Wilcoxon α=0,01 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.0 | 0.000 | 3.8% | 4.6% | 0.7% | 0.9% |
| 0.1 | 0.130 | 5.2% | 7.0% | 0.9% | 1.3% |
| 0.2 | 0.259 | 9.5% | 10.6% | 1.9% | 2.5% |
| 0.3 | 0.389 | 16.6% | 17.6% | 4.3% | 5.1% |
| 0.4 | 0.518 | 26.9% | 27.4% | 8.7% | 10.4% |
| 0.5 | 0.648 | 38.5% | 36.9% | 15.4% | 18.1% |
| 0.6 | 0.778 | 50.5% | 47.5% | 24.0% | 26.0% |
| 0.8 | 1.037 | 67.9% | 71.1% | 43.9% | 50.9% |
| 1.0 | 1.296 | 79.4% | 80.1% | 59.9% | 61.9% |

Erro tipo I (d_z = 0): t 3.8%, Wilcoxon 4.6%. d_z para 80% de poder: t não alcança na grade, Wilcoxon 1.00. Maior diferença de poder (t − Wilcoxon): -3.2 p.p. em d_z = 0.8.

## Outliers (10% × 5) (Q3)

Cauda pesada: 10% das diferenças com magnitude 5 vezes maior. n = 30; σ_d = 2.390 ms; assimetria de d sob H0 = 0.06.

| d_z | δ (ms) | t pareado α=0,05 | Wilcoxon α=0,05 | t pareado α=0,01 | Wilcoxon α=0,01 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.0 | 0.000 | 3.6% | 4.8% | 0.5% | 0.9% |
| 0.1 | 0.239 | 11.0% | 20.1% | 2.8% | 7.1% |
| 0.2 | 0.478 | 29.1% | 54.7% | 12.6% | 30.5% |
| 0.3 | 0.717 | 53.4% | 79.7% | 31.2% | 57.1% |
| 0.4 | 0.956 | 72.0% | 95.1% | 52.5% | 84.0% |
| 0.5 | 1.195 | 82.9% | 98.1% | 69.0% | 92.0% |
| 0.6 | 1.434 | 88.5% | 99.2% | 79.6% | 95.9% |
| 0.8 | 1.912 | 94.1% | 99.9% | 89.9% | 99.3% |
| 1.0 | 2.390 | 97.0% | 100.0% | 94.3% | 99.9% |

Erro tipo I (d_z = 0): t 3.6%, Wilcoxon 4.8%. d_z para 80% de poder: t 0.47, Wilcoxon 0.30. Maior diferença de poder (t − Wilcoxon): -26.3 p.p. em d_z = 0.3.

## Assimetria real (média zero) (Q3)

Diferenças assimétricas: h0 do t vale, a simetria do wilcoxon não. n = 30; σ_d = 1.296 ms; assimetria de d sob H0 = 1.84.

| d_z | δ (ms) | t pareado α=0,05 | Wilcoxon α=0,05 | t pareado α=0,01 | Wilcoxon α=0,01 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.0 | 0.000 | 8.0% | 21.8% | 3.6% | 8.5% |
| 0.1 | 0.130 | 5.6% | 8.5% | 1.5% | 2.5% |
| 0.2 | 0.259 | 10.7% | 5.2% | 1.4% | 1.0% |
| 0.3 | 0.389 | 28.3% | 12.3% | 5.9% | 3.0% |
| 0.4 | 0.518 | 57.9% | 37.2% | 20.4% | 15.9% |
| 0.5 | 0.648 | 85.9% | 70.6% | 50.0% | 44.0% |
| 0.6 | 0.778 | 98.0% | 92.0% | 82.6% | 76.1% |
| 0.8 | 1.037 | 100.0% | 100.0% | 99.9% | 100.0% |
| 1.0 | 1.296 | 100.0% | 100.0% | 100.0% | 100.0% |

Erro tipo I (d_z = 0): t 8.0%, Wilcoxon 21.8%. d_z para 80% de poder: t 0.48, Wilcoxon 0.54. Maior diferença de poder (t − Wilcoxon): +20.7 p.p. em d_z = 0.4.

## Leitura

A seção abaixo é gerada a partir dos números acima (ver `resumo` em `resultados.json`).

- **Base (30 pares)**: Erro tipo I em d_z = 0: t pareado 4,5% (conservador); Wilcoxon 4,9% (perto do nominal). O Wilcoxon detecta melhor o efeito, com vantagem de até 14,5 p.p. em d_z = 0,4; 80% de poder exige d_z ≈ 0,53 no t e ≈ 0,45 no Wilcoxon.
- **Amostra pequena (10 pares)**: Erro tipo I em d_z = 0: t pareado 3,8% (conservador); Wilcoxon 4,6% (conservador). O Wilcoxon detecta melhor o efeito, com vantagem de até 3,2 p.p. em d_z = 0,8; só o Wilcoxon chega a 80% de poder dentro da grade.
- **Outliers (10% × 5)**: Erro tipo I em d_z = 0: t pareado 3,6% (conservador); Wilcoxon 4,8% (perto do nominal). O Wilcoxon detecta melhor o efeito, com vantagem de até 26,3 p.p. em d_z = 0,3; 80% de poder exige d_z ≈ 0,47 no t e ≈ 0,30 no Wilcoxon.
- **Assimetria real (média zero)**: Erro tipo I em d_z = 0: t pareado 8,0% (liberal); Wilcoxon 21,8% (liberal). O t pareado detecta melhor o efeito, com vantagem de até 20,7 p.p. em d_z = 0,4; 80% de poder exige d_z ≈ 0,48 no t e ≈ 0,54 no Wilcoxon.

Limitações: as amostras reamostram os 30 pares reais (não criam valores novos fora dos fatores definidos), não reproduzem a tendência temporal da coleta e as proporções têm erro Monte Carlo (IC 95% em `resultados.json`, ±1 p.p. no pior caso).
