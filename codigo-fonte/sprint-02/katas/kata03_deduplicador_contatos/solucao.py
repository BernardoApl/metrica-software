"""Kata 03: desconto de pedido."""


def calcular_pedido(valor: float, tipo_cliente: str, cupom: bool = False) -> float:
    if valor <= 0:
        raise ValueError("valor deve ser maior que zero")

    desconto = 0.0

    if valor >= 300:
        desconto += 0.10
    elif valor >= 100:
        desconto += 0.05

    if tipo_cliente == "premium":
        desconto += 0.05

    if cupom:
        desconto += 0.05

    desconto = min(desconto, 0.20)

    return round(valor * (1 - desconto), 2)


def _normalizar_telefone(telefone: str) -> str:
    digitos = ""

    for caractere in telefone:
        if caractere.isdigit():
            digitos += caractere

    return digitos[-11:]


def deduplicar_contatos(contatos: list[dict]) -> list[dict]:
    contatos_por_telefone = {}
    ordem = []

    for contato in contatos:
        telefone = _normalizar_telefone(contato["telefone"])

        if telefone not in contatos_por_telefone:
            contatos_por_telefone[telefone] = contato
            ordem.append(telefone)
        else:
            contato_atual = contatos_por_telefone[telefone]

            if len(contato["nome"]) > len(contato_atual["nome"]):
                contatos_por_telefone[telefone] = contato

    resultado = []

    for telefone in ordem:
        resultado.append(contatos_por_telefone[telefone])

    return resultado