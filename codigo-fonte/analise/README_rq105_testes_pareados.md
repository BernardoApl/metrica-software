# RQ105 — Teste t pareado e Wilcoxon pareado

Implementação em `rq105_testes_pareados.py` (NumPy + SciPy). Convenção da #101: `d = t_sem − t_com`, em ms por operação (d > 0: o cache foi mais rápido). Os dois testes são **bilaterais** com α = 0,05, como nas hipóteses da #101.

## Executar

```powershell
python codigo-fonte/analise/rq105_testes_pareados.py
```

Aplica os dois testes a três amostras e grava `entregas/experimento-cache/RQ105/resultados.json` e `RELATORIO.md`:

1. `simulada_observado`: o conjunto simulado da RQ104 (efeito presente) — entrega da Sprint 1;
2. `simulada_h0`: o conjunto simulado da RQ104 com H0 verdadeira;
3. `reais`: os 30 pares reais da RQ102, validados pela função `carregar` da RQ103 (seção 6 do dashboard).

Se os CSVs da RQ104 não existirem, são gerados antes.

## O que cada teste calcula

| | t pareado | Wilcoxon pareado (signed-rank) |
|---|---|---|
| Compara | a média das diferenças | os postos de \|d\| com o sinal de d |
| H0 | μ<sub>d</sub> = 0 | distribuição de d simétrica em torno de 0 |
| Estatística | t = d̄ / (s<sub>d</sub>/√n), n − 1 gl (`scipy.stats.ttest_rel`) | W+ = soma dos postos das diferenças positivas |
| Distribuição sob H0 | t de Student com n − 1 gl | exata: permutação dos sinais condicionada aos postos (postos médios em empates); aproximação normal acima de 50 pares |
| Região de rejeição | \|t\| > t<sub>0,975; n−1</sub> | W+ ≤ c ou W+ ≥ n(n+1)/2 − c, cada cauda ≤ α/2 |
| Tamanho do efeito | d de Cohen para pares d<sub>z</sub> = d̄/s<sub>d</sub>, IC 95% da média | correlação rank-biserial r = (W+ − W−)/(W+ + W−) e estimador de Hodges-Lehmann |
| Diagnóstico | Shapiro-Wilk e assimetria das diferenças | zeros descartados (`zero_method='wilcox'`) e presença de empates |

O p-valor exato do Wilcoxon foi implementado (convolução dos postos dobrados) porque a amostra simulada reamostra pares com reposição e, portanto, tem empates em |d|; nesse caso a distribuição exata clássica, sem empates, não se aplica. Sem empates, o resultado coincide com `scipy.stats.wilcoxon(method='exact')` (verificado nos testes). A mesma distribuição alimenta o gráfico G2 (RQ106).

`interpretar` produz o texto: decisão de cada teste, direção e magnitude da diferença, se os testes concordam, o pressuposto de normalidade e a importância prática (razão entre os tempos médios).

## Resultado (semente 104)

| Amostra | t pareado | Wilcoxon pareado |
|---|---|---|
| Simulada, cenário observado | t(29) = 30,14; p = 1,9·10⁻²³; d<sub>z</sub> = 5,5 | W+ = 465; p = 1,9·10⁻⁹; r = 1 |
| Simulada, H0 verdadeira | t(29) = −0,86; p = 0,40 | W+ = 190; p = 0,39 |
| Dados reais | t(29) = 24,93; p = 3,9·10⁻²¹; d<sub>z</sub> = 4,55 | W+ = 465; p = 1,9·10⁻⁹; r = 1 |

No cenário observado e nos dados reais, todos os 30 pares têm d > 0: W+ atinge o máximo (465) e o p-valor exato do Wilcoxon é o menor possível com n = 30 (2/2³⁰). Os dois testes rejeitam H0. O t tem p-valor muito menor porque usa a magnitude das diferenças, não só a ordem. Shapiro-Wilk rejeita a normalidade das diferenças (assimetria positiva, puxada pelos primeiros pares da coleta), então o p-valor do t depende do TLC. Com H0 verdadeira, nenhum dos dois rejeita, como esperado.

## Validação

```powershell
python -m pytest codigo-fonte/testes/test_rq105_testes_pareados.py -q
```

Os testes conferem o t com a fórmula, o Wilcoxon com o SciPy exato, o valor crítico tabelado para n = 30 (137), postos médios e zeros, Hodges-Lehmann, entradas inválidas e as conclusões das três amostras.
