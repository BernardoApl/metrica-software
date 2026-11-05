# RQ105 — Teste t pareado e Wilcoxon pareado

Convenção: d = t_sem − t_com (ms por operação). Testes bilaterais, α = 0,05. Gerado por `codigo-fonte/analise/rq105_testes_pareados.py`.

| Amostra | Teste | Estatística | p-valor | Tamanho do efeito | Conclusão |
| --- | --- | ---: | ---: | --- | --- |
| Simulada (RQ104), cenário observado | t pareado | t(29) = 30.14 | 1.93e-23 | d_z = 5.5 (grande) | rejeita H0 |
| Simulada (RQ104), cenário observado | Wilcoxon pareado | W+ = 465 | 1.86e-09 | r = 1 (grande) | rejeita H0 |
| Simulada (RQ104), H0 verdadeira | t pareado | t(29) = -0.8622 | 0.396 | d_z = -0.157 (desprezível) | não rejeita H0 |
| Simulada (RQ104), H0 verdadeira | Wilcoxon pareado | W+ = 190 | 0.39 | r = -0.183 (pequeno) | não rejeita H0 |
| Dados reais (RQ102) | t pareado | t(29) = 24.93 | 3.89e-21 | d_z = 4.55 (grande) | rejeita H0 |
| Dados reais (RQ102) | Wilcoxon pareado | W+ = 465 | 1.86e-09 | r = 1 (grande) | rejeita H0 |

## Simulada (RQ104), cenário observado

- t pareado: t = 30.14, p = 1.93e-23 → rejeita H0 a α = 0.05; d de Cohen d_z = 5.50 (grande).
- Wilcoxon pareado: W+ = 465, p = 1.86e-09 → rejeita H0 a α = 0.05; rank-biserial r = 1.00 (grande).
- Direção: a operação foi mais rápida com cache. Diferença média 5.925 ms (IC 95% 5.523 a 6.327 ms); estimador de Hodges-Lehmann 5.692 ms.
- Os dois testes chegam à mesma conclusão.
- Pressuposto: Shapiro-Wilk rejeita a normalidade das diferenças (p = 1.37e-06, assimetria 2.93); o p-valor do t depende da aproximação pelo TLC.
- Importância prática: tempo médio 5.925 ms sem cache e 0.0004842 ms com cache (razão 1.22e+04×). Significância estatística não é, sozinha, relevância prática.

Regiões de rejeição: t pareado |t| > 2.0452; Wilcoxon W+ ≤ 137 ou W+ ≥ 328 (nível real 0.0490, método exato (permutação dos sinais, postos médios)).

## Simulada (RQ104), H0 verdadeira

- t pareado: t = -0.8622, p = 0.396 → não rejeita H0 a α = 0.05; d de Cohen d_z = -0.16 (desprezível).
- Wilcoxon pareado: W+ = 190, p = 0.39 → não rejeita H0 a α = 0.05; rank-biserial r = -0.18 (pequeno).
- Os dois testes chegam à mesma conclusão.
- Pressuposto: Shapiro-Wilk rejeita a normalidade das diferenças (p = 2.08e-05, assimetria 0.20); o p-valor do t depende da aproximação pelo TLC.

Regiões de rejeição: t pareado |t| > 2.0452; Wilcoxon W+ ≤ 137 ou W+ ≥ 328 (nível real 0.0490, método exato (permutação dos sinais, postos médios)).

## Dados reais (RQ102)

- t pareado: t = 24.93, p = 3.89e-21 → rejeita H0 a α = 0.05; d de Cohen d_z = 4.55 (grande).
- Wilcoxon pareado: W+ = 465, p = 1.86e-09 → rejeita H0 a α = 0.05; rank-biserial r = 1.00 (grande).
- Direção: a operação foi mais rápida com cache. Diferença média 6 ms (IC 95% 5.507 a 6.492 ms); estimador de Hodges-Lehmann 5.735 ms.
- Os dois testes chegam à mesma conclusão.
- Pressuposto: Shapiro-Wilk rejeita a normalidade das diferenças (p = 9.45e-05, assimetria 1.94); o p-valor do t depende da aproximação pelo TLC.
- Importância prática: tempo médio 6 ms sem cache e 0.0004912 ms com cache (razão 1.22e+04×). Significância estatística não é, sozinha, relevância prática.

Regiões de rejeição: t pareado |t| > 2.0452; Wilcoxon W+ ≤ 137 ou W+ ≥ 328 (nível real 0.0497, método exato (permutação dos sinais)).

## Leitura

Na amostra simulada do cenário observado e nos dados reais, todas as diferenças são positivas: W+ atinge o máximo possível e o t é muito grande, então os dois testes rejeitam H0 com folga. Na amostra gerada com H0 verdadeira (rótulos trocados ao acaso), espera-se não rejeitar H0; com α = 0,05, uma rejeição aqui seria um erro tipo I, que ocorre em cerca de 5% das amostras (medido na Sprint 2).

Ressalvas: os pares compartilham entrada e ambiente e a coleta mostra tendência temporal (RQ103), então a independência entre pares é uma suposição. Os dados simulados reamostram pares reais e não são novas medições.
