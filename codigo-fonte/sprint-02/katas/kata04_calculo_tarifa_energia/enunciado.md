# Kata 04 — Cálculo de Tarifa de Energia

Issue: RQ48 (com IA) / RQ47 (mesma kata, outro integrante/tratamento).

Implemente `calcular_tarifa_energia(consumo_kwh, tipo_ligacao, bandeira)` em `solucao.py`.

## Regras

1. `consumo_kwh <= 0` deve levantar `ValueError`.
2. `tipo_ligacao` deve ser `"residencial"` ou `"comercial"`; qualquer outro valor levanta `ValueError`.
3. `bandeira` deve ser `"verde"`, `"amarela"` ou `"vermelha"`; qualquer outro valor levanta `ValueError`.
4. O valor da energia é calculado por faixa de consumo, cumulativo (cada faixa cobra apenas o excedente sobre a faixa anterior):
   - residencial: até 100 kWh a R$ 0,50/kWh; de 100 a 300 kWh a R$ 0,70/kWh sobre o excedente; acima de 300 kWh a R$ 0,90/kWh sobre o excedente.
   - comercial: até 100 kWh a R$ 0,65/kWh; de 100 a 300 kWh a R$ 0,85/kWh sobre o excedente; acima de 300 kWh a R$ 1,05/kWh sobre o excedente.
5. A bandeira tarifária adiciona uma sobretaxa por kWh sobre o consumo total (não apenas sobre uma faixa):
   - verde: +R$ 0,00/kWh;
   - amarela: +R$ 0,02/kWh;
   - vermelha: +R$ 0,04/kWh.
6. Existe uma tarifa mínima (custo de disponibilidade), aplicada quando o valor calculado pelas regras acima for menor que ela:
   - residencial: R$ 20,00;
   - comercial: R$ 50,00.
7. O resultado deve ser arredondado para 2 casas decimais.

## Assinatura

```python
def calcular_tarifa_energia(consumo_kwh: float, tipo_ligacao: str, bandeira: str) -> float:
    ...
```

Tempo estimado: ~20–25 minutos.
