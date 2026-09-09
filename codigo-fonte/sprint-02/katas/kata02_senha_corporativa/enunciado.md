# Kata 02 — Validador de Senha Corporativa

Implemente `validar_senha(senha, nome_usuario)` em `solucao.py`. A função **não lança exceção**, apenas retorna `True`/`False`.

## Regras (todas devem ser satisfeitas para retornar `True`)

1. Comprimento mínimo de 8 caracteres.
2. Contém pelo menos uma letra maiúscula, uma minúscula, um dígito e um caractere especial dentre `!@#$%&*`.
3. Não contém 3 caracteres idênticos consecutivos (ex.: `"aaa"` ou `"111"` tornam a senha inválida).
4. Não contém o `nome_usuario` como substring, ignorando maiúsculas/minúsculas.

## Assinatura

```python
def validar_senha(senha: str, nome_usuario: str) -> bool:
    ...
```

Tempo estimado: ~20–25 minutos.
