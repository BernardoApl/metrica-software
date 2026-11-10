# RQ110 — Q1: erro Tipo I

Foram solicitadas 10,000 repetições, com 30 pares por amostra, semente 110 e α = 0.05. Status: **concluida**.

Q1: com H0 verdadeira, com que frequência cada teste rejeita H0?

| Teste | Válidas | Rejeições | Erro Tipo I | IC 95% | Erro padrão Monte Carlo |
| --- | ---: | ---: | ---: | --- | ---: |
| t_pareado | 10000 | 544 | 5.44% | 5.00% a 5.90% | 0.2268% |
| wilcoxon_pareado | 10000 | 526 | 5.26% | 4.83% a 5.72% | 0.2232% |

## Método

Cada repetição gera uma nova amostra pelo cenário `h0` da #104: reamostra pares completos nos estratos da #103 e troca os rótulos de cada par independentemente com probabilidade 1/2. Condicionalmente à magnitude, cada diferença tem sinal equiprovável; portanto sua distribuição é simétrica em zero e sua média é zero. H0 vale para ambos os testes neste modelo. Não se reutiliza uma única amostra nem se usa o cenário observado para estimar erro Tipo I.

Os dois testes bilaterais da #105 recebem a mesma amostra em cada repetição. A decisão é estritamente `p < alfa`. O Wilcoxon usa distribuição exata dos sinais com postos médios até 50 diferenças não nulas e a aproximação já definida pela #105 acima desse limite. A simulação padrão usa 30 pares.

Erro Tipo I = número de rejeições / número total de repetições. Os intervalos são binomiais exatos de Clopper–Pearson; o erro padrão Monte Carlo é sqrt(taxa × (1 − taxa) / repetições). Se houver falhas, elas permanecem no CSV, a execução fica incompleta e a taxa oficial não é calculada. Não há reposição seletiva de experimentos.

## Interpretação

- t_pareado: a taxa estimada difere do nominal em +0.440 pontos percentuais; o IC 95% não contém α. Isso descreve a calibração neste modelo, sem provar que o nível é exatamente α.
- wilcoxon_pareado: a taxa estimada difere do nominal em +0.260 pontos percentuais; o IC 95% contém α. Isso descreve a calibração neste modelo, sem provar que o nível é exatamente α.

O nível nominal não obriga uma realização Monte Carlo a ter exatamente 5% de rejeições. A incerteza dos intervalos refere-se à simulação, condicionada à distribuição empírica de origem; não inclui a incerteza da coleta original. A discretização do Wilcoxon também pode torná-lo conservador.

## Escopo e reprodução

As 10.000 repetições não são novas medições de desempenho. A simulação não preserva a tendência temporal da coleta real, nem estabelece poder estatístico (erro Tipo II) ou validade universal dos testes. O modelo nulo de troca de rótulos é uma construção artificial apropriada à Q1.

`repeticoes.csv` registra estatísticas, p-valores, decisões e erros de ambos os testes. `resultados.json` registra a configuração, versões e hashes. `parametros_origem.json` preserva o contrato da #103. Reproduza com a mesma semente, parâmetros, quantidade de repetições, código e versões; alterar o tamanho do lote muda a sequência de sorteios da #104.

Referência do intervalo: [SciPy — proportion_ci](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats._result_classes.BinomTestResult.proportion_ci.html).
