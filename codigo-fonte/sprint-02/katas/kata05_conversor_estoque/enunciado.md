# Kata 05 — Conversor de Unidades de Estoque

Implemente `converter(quantidade, unidade_origem, unidade_destino, tabela)` em `solucao.py`.

## Entrada

- `tabela`: `dict[tuple[str, str], float]` com conversões diretas e **direcionadas**, ex.: `{("caixa", "pacote"): 10, ("pacote", "unidade"): 12}` significa que 1 caixa = 10 pacotes e 1 pacote = 12 unidades. A tabela não contém automaticamente a conversão inversa.
- Pode ser necessário passar por unidades intermediárias (ex.: `caixa -> pacote -> unidade`) para achar o fator de conversão.

## Regras

1. Se `unidade_origem == unidade_destino`, retorne `quantidade` (arredondada a 6 casas decimais).
2. Caso exista um caminho de conversões diretas ligando origem a destino, retorne `quantidade` multiplicada pelo produto dos fatores ao longo do caminho, arredondado a 6 casas decimais.
3. Se não existir caminho (nem direto nem por unidades intermediárias) ligando origem a destino, levante `ValueError`.
4. A tabela não deve ser tratada como bidirecional — uma conversão só existe no sentido em que está definida.

## Assinatura

```python
def converter(quantidade: float, unidade_origem: str, unidade_destino: str, tabela: dict) -> float:
    ...
```

Tempo estimado: ~20–25 minutos.
