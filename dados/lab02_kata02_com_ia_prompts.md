# RQ38 - Kata 2 - Cálculo de Estacionamento - COM IA

## Prompt do participante

Fazer a RQ38 - Kata 2 - Cálculo de Estacionamento - COM IA.

A pasta versionada para "Kata 2" no repositório (`kata02_senha_corporativa`) corresponde a um
tema antigo (validação de senha), incompatível com o título atual da Issue no GitHub Projects
("Cálculo de Estacionamento"). Como não existe pasta/testes para esse tema, criar do zero:
`enunciado.md`, `solucao.py` (stub) e `testes/test_solucao.py`, seguindo o padrão dos katas já
validados na RQ32, e então implementar a solução.

Função esperada:

```python
def calcular_estacionamento(horas, tipo_veiculo):
    ...
```

Regras definidas (nenhuma fonte externa fixava a regra de negócio; foram definidas para manter
dificuldade equivalente aos demais katas — faixas cumulativas + valor mínimo/máximo, no estilo do
Kata 1 - Frete):

- `horas <= 0` ou `tipo_veiculo` fora de `{carro, moto, caminhao}` levantam `ValueError`;
- fração de hora é cobrada como hora cheia (arredondamento para cima);
- tarifa da primeira hora e das horas adicionais variam por tipo de veículo;
- existe uma diária (teto de cobrança) por tipo de veículo.

## Interação com IA

Implementação feita com auxílio do Claude Code (nota: o desenho do experimento, RQ33, fixa
ChatGPT gratuito como ferramenta padronizada do grupo para os trials `com_ia`; o uso do Claude
Code aqui é uma divergência de ferramenta em relação ao protocolo original, registrada como
limitação no Relatório Final). A IA leu a estrutura dos katas já existentes (RQ32) para manter o
mesmo padrão (função pura, tipos simples, 6-7 casos de teste, ao menos uma validação de erro) e
gerou o enunciado, o stub e os testes de aceitação antes de implementar `solucao.py`.

## Resultado

- Pasta criada: `codigo-fonte/sprint-02/katas/kata02_calculo_estacionamento/`.
- Testes executados via `python -m unittest discover -s testes`.
- Resultado: sucesso (7 testes, cobrindo tarifa por tipo de veículo, arredondamento de fração de
  hora, teto da diária e as duas validações de erro).
