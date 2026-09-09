# Kata 03 — Deduplicador de Contatos

Implemente `deduplicar_contatos(contatos)` em `solucao.py`.

## Entrada

Lista de dicionários `{"nome": str, "telefone": str, "email": str}`, com telefones em formatos variados (ex.: `"(11) 91234-5678"`, `"11912345678"`, `"+55 11 91234-5678"`).

## Regras

1. Normalize o telefone removendo todos os caracteres não numéricos e mantendo apenas os últimos 11 dígitos. Dois contatos são duplicados se o telefone normalizado for igual.
2. Ao encontrar duplicados, mantenha o registro cujo campo `"nome"` seja o mais longo (mais completo). Em caso de empate, mantenha o primeiro que apareceu.
3. A lista de saída deve preservar a ordem da primeira ocorrência de cada telefone normalizado.
4. Lista vazia retorna lista vazia.

## Assinatura

```python
def deduplicar_contatos(contatos: list[dict]) -> list[dict]:
    ...
```

Tempo estimado: ~20–25 minutos.
