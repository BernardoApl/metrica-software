# Kata 04 — Escalonador de Turnos

Implemente `detectar_conflitos(turnos)` em `solucao.py`.

## Entrada

Lista de dicionários `{"funcionario": str, "inicio": "HH:MM", "fim": "HH:MM"}`, todos referentes ao mesmo dia.

## Regras

1. Dois turnos conflitam quando pertencem ao **mesmo funcionário** e seus intervalos se sobrepõem estritamente (tocar nas bordas, ex.: um termina às 10:00 e outro começa às 10:00, **não** é conflito).
2. Turnos de funcionários diferentes nunca conflitam entre si, mesmo que se sobreponham.
3. Retorne uma lista de tuplas `(i, j)` com `i < j`, sendo `i` e `j` os índices (na lista de entrada) dos turnos conflitantes, ordenada de forma crescente por `(i, j)`.
4. Um horário em formato inválido (`"HH:MM"` fora do padrão) deve levantar `ValueError`.
5. Lista vazia retorna lista vazia.

## Assinatura

```python
def detectar_conflitos(turnos: list[dict]) -> list[tuple]:
    ...
```

Tempo estimado: ~20–25 minutos.
