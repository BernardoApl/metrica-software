# RQ116 — Q3: erro tipo I com violações de pressupostos

A Q3 pede repetir a Q1 e a Q2 em situações que violam os pressupostos do teste paramétrico. A parte de poder (Q2) já está na #113 e no G4. Esta issue repete a Q1: com efeito zero, com que frequência cada teste rejeita H0 quando os dados não se comportam bem?

## Executar

```powershell
python codigo-fonte/analise/rq116_q3_violacoes.py
```

Leva cerca de 20 segundos e grava em `entregas/experimento-cache/RQ116/`, sobrescrevendo. A saída é determinística com a semente 116.

| Arquivo | Conteúdo |
|---|---|
| `resultados.json` | Configuração, erro tipo I por situação, tamanho, teste e α, com IC 95% Clopper-Pearson e classificação (conservador, perto do nominal, liberal) |
| `erro_tipo_i.csv` | O mesmo em formato longo |
| `RELATORIO.md` | Tabelas e leitura gerada dos números |

## Situações

As amostras vêm dos mesmos geradores da #113 (`amostras_h0`), então o G3 e o G4 descrevem os mesmos dados. Cada situação roda com 10, 20, 30 e 50 pares, 10.000 amostras em cada.

| Situação | Como é gerada | Pressuposto atingido |
|---|---|---|
| Sem violação | diferenças reais centradas, com sinal sorteado | nenhum (referência) |
| Outliers | a anterior com 10% das diferenças multiplicadas por 5 | normalidade: cauda pesada |
| Assimetria | diferenças reais centradas, sem sortear o sinal (assimetria ≈ 1,9) | normalidade do t; simetria do Wilcoxon |
| Amostra pequena | qualquer situação com 10 pares | o t depende mais da normalidade |

Na assimetria, a média das diferenças é zero, então H0 do t é verdadeira. A H0 do Wilcoxon (distribuição simétrica em zero) é falsa. Para a pergunta do cenário, que é sobre o tempo médio, as rejeições do Wilcoxon contam como falsos positivos.

## Resultado (α = 0,05)

| Situação | 10 pares, t / Wilcoxon | 30 pares, t / Wilcoxon | 50 pares, t / Wilcoxon |
|---|---|---|---|
| Sem violação | 3,5% / 4,2% | 4,5% / 4,7% | 4,9% / 5,2% |
| Outliers | 2,9% / 4,4% | 3,6% / 5,0% | 3,9% / 4,9% |
| Assimetria | 12,3% / 10,7% | 8,3% / 21,6% | 6,9% / 32,4% |

- Com outliers, o t fica conservador (rejeita menos que 5%), porque os extremos inflam o desvio padrão. O Wilcoxon fica perto de 5%.
- Na assimetria, o t é liberal com poucos pares e se aproxima de 5% conforme a amostra cresce (teorema central do limite). O Wilcoxon faz o contrário: rejeita cada vez mais, porque detecta a assimetria, que não é o que a pergunta testa.
- Ou seja, a violação de normalidade pesa mais no t com amostras pequenas; a falta de simetria pesa mais no Wilcoxon com amostras grandes.

## Validação

```powershell
python -m pytest codigo-fonte/testes/test_rq116_q3_violacoes.py -q
```

Os testes conferem tamanho e média zero das amostras, reprodutibilidade, que α = 0,01 nunca rejeita mais que α = 0,05, que só a assimetria quebra a simetria, a consistência da entrega salva e os arquivos gravados.

## Limitações

Reamostra os 30 pares reais e não reproduz a tendência temporal da coleta. A contaminação (10% × 5) e os tamanhos são escolhas do grupo. O erro Monte Carlo é de cerca de ±0,4 p.p. perto de 5%.
