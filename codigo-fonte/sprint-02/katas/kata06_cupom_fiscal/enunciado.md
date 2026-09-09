# Kata 06 — Validador de Cupom Fiscal

Implemente `validar_cupom(codigo)` em `solucao.py`. **Atenção:** este é um algoritmo de checksum fictício, criado para este experimento — não corresponde a nenhuma validação real (CPF/CNPJ) e não deve ser resolvido "de cabeça" por já ter sido visto antes.

## Regras

1. `codigo` deve ser uma string com exatamente 9 caracteres, todos dígitos numéricos. Caso contrário, retorne `False` (não lance exceção).
2. Os 8 primeiros dígitos (`d0`..`d7`) formam a base. O peso de cada posição `i` (0-indexado) é `2 + i` (ou seja, pesos `2,3,4,5,6,7,8,9` da esquerda para a direita).
3. O dígito verificador esperado é `soma % 10`, onde `soma = sum(d_i * peso_i)` para `i` de 0 a 7.
4. O 9º dígito do código deve ser igual ao dígito verificador esperado para o código ser válido.

## Exemplo

Base `12345678`: `soma = 1*2 + 2*3 + 3*4 + 4*5 + 5*6 + 6*7 + 7*8 + 8*9 = 240`, verificador `= 240 % 10 = 0`. Código válido: `"123456780"`.

## Assinatura

```python
def validar_cupom(codigo: str) -> bool:
    ...
```

Tempo estimado: ~20–25 minutos.
