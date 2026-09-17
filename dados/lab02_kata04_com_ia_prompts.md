# RQ48 - Kata 4 - Cálculo de Tarifa de Energia - COM IA

## Prompt do participante

Fazer a RQ48 - Kata 4 - Cálculo de Tarifa de Energia - COM IA.

Assim como na RQ38 (Kata 2), não existe pasta/testes para "Kata 4" no esquema de 4 katas das
Issues RQ34–48 — `kata04_escalonador_turnos` é um tema diferente, do esquema antigo de 6 katas
(RQ32). Criar do zero `enunciado.md`, `solucao.py` (stub) e `testes/test_solucao.py` em
`kata04_calculo_tarifa_energia/`, seguindo o mesmo padrão estrutural das demais katas, e então
implementar a solução.

Função esperada:

```python
def calcular_tarifa_energia(consumo_kwh, tipo_ligacao, bandeira):
    ...
```

Regras definidas (nenhuma fonte externa fixava a regra de negócio; foram desenhadas para manter
dificuldade equivalente ao Kata 1 - Frete, reaproveitando o padrão de faixas cumulativas +
sobretaxa + valor mínimo):

- `consumo_kwh <= 0`, `tipo_ligacao` fora de `{residencial, comercial}` ou `bandeira` fora de
  `{verde, amarela, vermelha}` levantam `ValueError`;
- tarifa por faixa de consumo cumulativa, com preços diferentes para residencial/comercial;
- bandeira tarifária soma uma sobretaxa por kWh sobre o consumo total;
- existe uma tarifa mínima (custo de disponibilidade) por tipo de ligação.

## Interação com IA

Implementação feita com auxílio do Claude Code (mesma ressalva da RQ38: o desenho do experimento,
RQ33, fixa ChatGPT gratuito como ferramenta padronizada do grupo para os trials `com_ia`; o uso do
Claude Code aqui diverge do protocolo original e fica registrado como limitação no Relatório
Final). A IA seguiu o padrão estrutural das katas já validadas (RQ32): função pura, tipos simples,
faixas cumulativas no mesmo estilo do Kata 1 (frete), e cobertura de 8 casos de teste (caminho
feliz em cada faixa de consumo, sobretaxa de bandeira, tarifa mínima e as três validações de
erro).

## Resultado

- Pasta criada: `codigo-fonte/sprint-02/katas/kata04_calculo_tarifa_energia/`.
- Testes executados via `python -m unittest discover -s testes`.
- Resultado: sucesso (8 testes).
