"""Kata 01: calculo de frete progressivo por peso e distancia."""


def calcular_frete(peso_kg: float, distancia_km: float, valor_compra: float) -> float:
    if peso_kg <= 0:
        raise ValueError("peso_kg deve ser maior que zero")
    if distancia_km < 0:
        raise ValueError("distancia_km nao pode ser negativa")

    if valor_compra >= 300:
        return 0.0

    if peso_kg <= 5:
        valor = peso_kg * 2.0
    elif peso_kg <= 20:
        valor = 10.0 + (peso_kg - 5) * 1.5
    else:
        valor = 32.5 + (peso_kg - 20) * 1.0

    if distancia_km <= 50:
        multiplicador = 1.0
    elif distancia_km <= 200:
        multiplicador = 1.3
    else:
        multiplicador = 1.6

    return round(max(5.0, valor * multiplicador), 2)
