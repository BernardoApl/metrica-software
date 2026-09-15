# Kata 01 - Cálculo de Frete - COM IA

## Prompt do participante

Implementar `calcular_frete(peso, distancia, entrega_expressa)` em Python.

Regras:
- valor base de R$ 10;
- até 5 kg adiciona R$ 2/kg;
- acima de 5 kg adiciona R$ 3/kg;
- distância acima de 100 km adiciona R$ 15;
- entrega expressa acrescenta 30%;
- peso ou distância inválidos devem gerar erro;
- não modificar os testes prontos;
- iniciar/encerrar coleta da RQ28 e registrar o trial.

## Interação com IA

A implementação foi feita com auxílio do ChatGPT/Codex. Durante a leitura do projeto,
foi identificado que os testes prontos existentes em
`codigo-fonte/sprint-02/katas/kata01_frete_progressivo/testes/test_solucao.py`
ainda chamam a função com o terceiro parâmetro como `valor_compra`.

Para respeitar a restrição de não modificar os testes, a solução implementada em
`solucao.py` mantém compatibilidade com os testes versionados e também atende ao
enunciado informado para o caso em que o terceiro argumento é booleano
(`entrega_expressa`).

## Resultado

- RQ28 executada com tratamento `com_ia`.
- Testes da Kata 1 executados via `python -m unittest discover -s testes`.
- Resultado: sucesso.
