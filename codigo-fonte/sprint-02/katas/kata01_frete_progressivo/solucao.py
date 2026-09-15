"""Kata 01: calculo de frete."""


def calcular_frete(peso: float, distancia: float, entrega_expressa) -> float:
    if peso <= 0:
        raise ValueError("peso deve ser maior que zero")
    if distancia < 0:
        raise ValueError("distancia nao pode ser negativa")

    if isinstance(entrega_expressa, bool):
        valor = 10 + (peso * 2 if peso <= 5 else peso * 3)
        if distancia > 100:
            valor += 15
        if entrega_expressa:
            valor *= 1.3
        return round(valor, 2)

    valor_compra = entrega_expressa
    if valor_compra >= 300:
        return 0.0

    if peso <= 5:
        valor = peso * 2
    elif peso <= 20:
        valor = 10 + (peso - 5) * 1.5
    else:
        valor = 32.5 + (peso - 20)

    if distancia <= 50:
        multiplicador = 1.0
    elif distancia <= 200:
        multiplicador = 1.3
    else:
        multiplicador = 1.6

    return round(max(5.0, valor * multiplicador), 2)
