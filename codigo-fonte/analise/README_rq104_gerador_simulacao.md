# RQ104 — Gerador de dados simulados com semente fixa

Implementação em `rq104_gerador_simulacao.py` (NumPy). Segue o contrato `reamostragem_empirica_pareada_estratificada_v1` da [RQ103](README_rq103_parametros_cache.md): sorteia **pares completos** com reposição dentro de cada estrato (tratamento que iniciou o par), preservando 15 + 15 pares, e embaralha a lista final com o mesmo gerador `numpy.random.default_rng(104)`, inicializado uma única vez.

## Executar

Na raiz do projeto:

```powershell
python codigo-fonte/analise/rq104_gerador_simulacao.py
```

Grava em `entregas/experimento-cache/RQ104/` (sobrescreve; a saída é determinística):

| Arquivo | Conteúdo |
|---|---|
| `amostra_simulada_observado.csv` | 30 pares simulados no cenário observado (efeito presente, como na coleta real) |
| `amostra_simulada_h0.csv` | 30 pares simulados com **H0 verdadeira** |
| `manifesto.json` | Semente, versão do NumPy, hash do contrato da RQ103, hash e resumo de cada CSV |

Colunas: `sim_id`, `par_id_origem` (par real sorteado), `ordem_primeiro`, `tempo_sem_cache_ms`, `tempo_com_cache_ms`, `diferenca_ms` (= sem − com) e `rotulos_trocados`.

## Cenários

- **`observado`**: aplica exatamente o algoritmo da RQ103. Como na coleta real, todas as diferenças são positivas (o cache foi sempre mais rápido).
- **`h0`**: após a reamostragem, troca os rótulos "com cache"/"sem cache" de cada par com probabilidade 1/2. O rótulo deixa de ter relação com o tempo, então H0 é verdadeira por construção: a diferença `d` fica simétrica em torno de zero, o que satisfaz a H0 do t pareado (μ<sub>d</sub> = 0) e a do Wilcoxon (simetria em torno de 0). Os tempos continuam sendo valores reais observados e positivos. Esse cenário responde à observação da RQ103 de que o contrato, sozinho, "não gera uma distribuição sob H0".

## Uso por outras RQs

```python
from analise import rq104_gerador_simulacao as g
p = g.carregar_parametros()
rng = np.random.default_rng(104)
lote = g.gerar_lote(p, rng, repeticoes=10_000, cenario='h0')  # arrays (10000, 30)
```

`gerar_lote` é vetorizado e serve às simulações de erro tipo I e poder da Sprint 2. A mesma semente e a mesma sequência de chamadas reproduzem exatamente os mesmos dados.

## Limitações

A reamostragem herda as limitações da RQ103: só produz valores já observados (não cria extremos novos), não preserva a tendência temporal da coleta e não cria evidência independente nova. Os dados gerados são **simulados** e o manifesto indica isso.

## Validação

```powershell
python -m pytest codigo-fonte/testes/test_rq104_gerador_simulacao.py -q
```

Os testes verificam reprodutibilidade por semente, preservação dos pares e dos estratos, formas do lote vetorizado, a simetria do cenário `h0` e a recusa de contratos incompatíveis.
