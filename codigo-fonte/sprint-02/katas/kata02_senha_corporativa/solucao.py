"""Kata 02: validacao de senha corporativa."""

import re

CARACTERES_ESPECIAIS = "!@#$%&*"


def validar_senha(senha: str, nome_usuario: str) -> bool:
    if len(senha) < 8:
        return False
    if not re.search(r"[A-Z]", senha):
        return False
    if not re.search(r"[a-z]", senha):
        return False
    if not re.search(r"[0-9]", senha):
        return False
    if not any(caractere in CARACTERES_ESPECIAIS for caractere in senha):
        return False
    for i in range(len(senha) - 2):
        if senha[i] == senha[i + 1] == senha[i + 2]:
            return False
    if nome_usuario.lower() in senha.lower():
        return False

    return True
