# RQ36 - Kata 3 - Desconto de Pedido - COM IA

## Prompt do participante

Fazer a RQ36 - Kata 3 - Desconto de Pedido - COM IA.

Funcao esperada:

```python
def calcular_pedido(valor, tipo_cliente, cupom=False):
    ...
```

Regras:
- `valor <= 0` deve gerar erro;
- valor menor que R$100 nao recebe desconto-base;
- de R$100 ate R$299,99 recebe 5% de desconto-base;
- a partir de R$300 recebe 10% de desconto-base;
- cliente `premium` acrescenta 5%;
- cupom verdadeiro acrescenta 5%;
- desconto total limitado a 20%;
- retorno e o valor final da compra apos descontos.

## Analise do projeto

Ao analisar o repositorio apos o `git pull`, a pasta versionada da Kata 3 ainda
esta em `codigo-fonte/sprint-02/katas/kata03_deduplicador_contatos`, com testes
prontos antigos para `deduplicar_contatos(contatos)`.

Para corrigir a RQ36 sem quebrar os testes versionados, o arquivo `solucao.py`
foi atualizado para incluir `calcular_pedido(valor, tipo_cliente, cupom=False)`.
A funcao antiga foi mantida apenas por compatibilidade com os testes existentes
do repositorio.

## Interacao com IA

A implementacao foi feita com auxilio do ChatGPT/Codex. A IA analisou o
enunciado, os testes e a estrutura existente antes de editar o arquivo
`solucao.py`.

## Resultado

- RQ28 executada com tratamento `com_ia`.
- Issue registrada: `36`.
- Funcao da RQ36: `calcular_pedido`.
- Pasta usada: `kata03_deduplicador_contatos`, por ser a pasta da Kata 3 no repositorio atual.
- Testes executados via `python -m unittest discover -s testes`.
- Resultado dos testes existentes: sucesso.
- Exemplos da RQ36 validados manualmente.
