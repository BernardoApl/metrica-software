# RQ113 — Q2 e Q3: simulações de poder

Implementação em `rq113_poder.py` (NumPy + SciPy). Responde à **Q2** (com efeito, com que frequência cada teste o detecta?) e à parte de poder da **Q3** (o que muda quando os dados violam os pressupostos?). Os testes são os da #105: t pareado e Wilcoxon pareado, bilaterais, decisão estrita `p < α`.

## Executar

```powershell
python codigo-fonte/analise/rq113_poder.py
```

Leva cerca de 2 minutos (4 cenários × 9 efeitos × 10.000 amostras, com o p-valor exato do Wilcoxon). Grava em `entregas/experimento-cache/RQ113/` (sobrescreve; a saída é determinística com a semente 113):

| Arquivo | Conteúdo |
|---|---|
| `resultados.json` | Configuração, versões, curva de cada cenário (proporção de rejeições e IC 95% Clopper-Pearson, para α = 0,05 e 0,01), resumo e leitura em texto |
| `poder.csv` | O mesmo em formato longo: cenário, efeito, teste, α, rejeições, proporção, IC |
| `RELATORIO.md` | Tabelas por cenário e leitura gerada a partir dos números |

O `rq109_dashboard.py` **não** refaz essas simulações: o G4 (#114) lê o `resultados.json` salvo, como o G3 faz com a #110.

## Como o efeito é introduzido

Os dois testes só dependem de d = t<sub>sem</sub> − t<sub>com</sub>. Cada cenário gera 10.000 amostras de d com H0 verdadeira e soma um efeito conhecido:

d<sub>efeito</sub> = d<sub>H0</sub> + δ, com δ = d<sub>z</sub> × σ<sub>d</sub>

d<sub>z</sub> (d de Cohen para pares) vai de 0 a 1 em 9 valores: 0; 0,1; 0,2; 0,3; 0,4; 0,5; 0,6; 0,8; 1,0. Usar d<sub>z</sub> no eixo deixa os cenários comparáveis mesmo com escalas diferentes; o δ em ms de cada ponto também é registrado. Em d<sub>z</sub> = 0 a proporção de rejeições é o **erro tipo I** daquele cenário. As mesmas amostras-base servem a todos os efeitos de um cenário (números aleatórios comuns), então as curvas não oscilam por causa de sorteios diferentes.

## Cenários

Todos reamostram os 30 pares reais pelo gerador da #104 (contrato da #103).

| Cenário | Questão | d sob H0 | O que viola |
|---|---|---|---|
| `base` | Q2 | s × (d<sub>real</sub> − média), com sinal s = ±1 sorteado | nada: média zero e simetria em zero (H0 dos dois testes) |
| `amostra_pequena` | Q3 | a base com 10 pares (5 por estrato) | n pequeno: o TLC ajuda menos o t; o Wilcoxon exato fica mais discreto |
| `outliers` | Q3 | a base, com 10% das diferenças multiplicadas por 5 | cauda pesada (a coleta teve 3 extremos em 30 pares) |
| `assimetria` | Q3 | d<sub>real</sub> − média, sem sortear o sinal | assimetria real (≈ 1,9): a H0 do t (μ<sub>d</sub> = 0) vale, mas a do Wilcoxon (simetria em 0) não |

**Por que a base não usa a troca de rótulos da Q1 (#110).** A troca de rótulos produz diferenças bimodais (±6 ms, sem valores perto de zero). Nessa forma, um deslocamento mínimo reordena todos os postos e a curva do Wilcoxon ganha degraus que vêm da construção do modelo, não do cenário. Centrar as diferenças reais e sortear o sinal preserva a variação observada (inclusive os extremos) e mantém H0 verdadeira para os dois testes. Por isso o erro tipo I em d<sub>z</sub> = 0 do G4 é próximo do G3, mas não igual.

## Resultado (10.000 amostras, α = 0,05)

| Cenário | Erro tipo I t / Wilcoxon | d<sub>z</sub> para 80% de poder, t / Wilcoxon | Quem detecta melhor |
|---|---|---|---|
| Base | 4,5% / 4,9% | 0,53 / 0,45 | Wilcoxon (até +14,5 p.p.) |
| Amostra pequena | 3,8% / 4,6% | > 1 / ≈ 1,00 | praticamente empate (até +3,2 p.p. para o Wilcoxon) |
| Outliers | 3,6% / 4,8% | 0,47 / 0,30 | Wilcoxon (até +26,3 p.p.) |
| Assimetria | 8,0% / **21,8%** | 0,48 / 0,54 | t pareado (até +20,7 p.p.) |

- Nas diferenças simétricas com os extremos reais (base) e, mais ainda, com outliers, o Wilcoxon tem mais poder: os postos não deixam os extremos inflarem a variância, e o t fica conservador.
- Com 10 pares, os dois perdem muito poder e ficam parecidos.
- Na assimetria, o Wilcoxon rejeita H0 em 21,8% das amostras **sem efeito na média**, porque testa simetria/mediana, e a mediana das diferenças centradas é negativa. Para a pergunta "o cache altera o tempo médio?", isso é erro tipo I inflado. O t fica um pouco liberal (8%) e tem mais poder para deslocamentos da média. **A vantagem muda de lado** conforme a forma dos dados.

## Validação

```powershell
python -m pytest codigo-fonte/testes/test_rq113_poder.py -q
```

Os testes conferem os p-valores vetorizados com a #105 (inclusive com empates), a média zero e a simetria de cada cenário sob H0, a reprodutibilidade, o crescimento do poder com o efeito, que α = 0,01 nunca rejeita mais que α = 0,05, a interpolação de d<sub>z</sub> para 80% e os arquivos gravados.

## Limitações

As amostras reamostram os 30 pares reais (não criam valores além dos fatores definidos), não reproduzem a tendência temporal da coleta, e os fatores de contaminação (10% × 5) e o tamanho pequeno (10 pares) são escolhas do grupo para estressar os testes. As proporções têm erro Monte Carlo de até ±1 p.p. (IC 95% no JSON).
