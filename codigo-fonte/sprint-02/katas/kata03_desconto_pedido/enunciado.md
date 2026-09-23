# Kata 03 — Desconto de Pedido

Issue: RQ39 (sem IA) / RQ36, RQ42 (mesma kata, outros integrantes/tratamentos).

Implemente `calcular_pedido(valor, tipo_cliente, cupom=False)` em `solucao.py`.

## Regras

1. `valor <= 0` deve levantar `ValueError`.
2. Desconto-base pelo valor da compra (cumulativo por faixa, não somado):
   - `valor < 100`: sem desconto-base;
   - `100 <= valor < 300`: 5% de desconto-base;
   - `valor >= 300`: 10% de desconto-base.
3. Cliente `"premium"` (parâmetro `tipo_cliente`) acrescenta mais 5% de desconto.
4. `cupom=True` acrescenta mais 5% de desconto.
5. O desconto total é limitado a 20% (mesmo que a soma das regras acima ultrapasse esse valor).
6. O retorno é o valor final da compra após o desconto, arredondado para 2 casas decimais.

## Assinatura

```python
def calcular_pedido(valor: float, tipo_cliente: str, cupom: bool = False) -> float:
    ...
```

Tempo estimado: ~20–25 minutos.
