# Kata 02 — Cálculo de Estacionamento

Issue: RQ38 (com IA) / RQ35, RQ41 (mesma kata, outros integrantes/tratamentos).

Implemente `calcular_estacionamento(horas, tipo_veiculo)` em `solucao.py`.

## Regras

1. `horas <= 0` deve levantar `ValueError`.
2. `tipo_veiculo` deve ser um de `"carro"`, `"moto"` ou `"caminhao"`; qualquer outro valor levanta `ValueError`.
3. Frações de hora contam como hora cheia para fins de cobrança (arredondamento para cima).
4. Tarifa da primeira hora:
   - carro: R$ 8,00
   - moto: R$ 5,00
   - caminhao: R$ 15,00
5. Cada hora adicional além da primeira:
   - carro: R$ 4,00/h
   - moto: R$ 2,00/h
   - caminhao: R$ 7,00/h
6. Existe uma diária (valor máximo cobrado no período): quando o total calculado pelas regras acima ultrapassar a diária, cobra-se a diária:
   - carro: R$ 40,00
   - moto: R$ 25,00
   - caminhao: R$ 70,00
7. O resultado deve ser arredondado para 2 casas decimais.

## Assinatura

```python
def calcular_estacionamento(horas: float, tipo_veiculo: str) -> float:
    ...
```

Tempo estimado: ~20–25 minutos.
