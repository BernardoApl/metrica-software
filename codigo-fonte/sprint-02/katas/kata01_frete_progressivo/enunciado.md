# Kata 01 — Frete Progressivo

Implemente `calcular_frete(peso_kg, distancia_km, valor_compra)` em `solucao.py`.

## Regras

1. Se `valor_compra >= 300`, o frete é gratuito (`0.0`).
2. Caso contrário, o valor base é calculado por faixa de peso, cumulativo:
   - até 5 kg: R$ 2,00/kg;
   - de 5 a 20 kg: R$ 1,50/kg sobre o excedente acima de 5 kg;
   - acima de 20 kg: R$ 1,00/kg sobre o excedente acima de 20 kg.
3. O valor base é multiplicado conforme a distância:
   - até 50 km: x1.0;
   - de 50 a 200 km: x1.3;
   - acima de 200 km: x1.6.
4. O frete mínimo (quando não gratuito) é R$ 5,00.
5. `peso_kg <= 0` ou `distancia_km < 0` deve levantar `ValueError`.
6. O resultado deve ser arredondado para 2 casas decimais.

## Assinatura

```python
def calcular_frete(peso_kg: float, distancia_km: float, valor_compra: float) -> float:
    ...
```

Tempo estimado: ~20–25 minutos.
