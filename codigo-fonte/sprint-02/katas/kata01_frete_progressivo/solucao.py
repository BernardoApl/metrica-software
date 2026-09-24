"""Kata 01: calculo de frete progressivo por peso e distancia."""

FAIXAS_PESO = [
    (5, 2.0),
    (20, 1.5),
    (float("inf"), 1.0)
]

FAIXAS_DISTANCIA = [
    (50, 1.0),
    (200, 1.3),
    (float("inf"), 1.6)
]

FRETE_MINIMO = 5.0
VALOR_COMPRA_FRETE_GRATIS = 300


def calcular_frete(peso_kg: float, distancia_km: float, valor_compra: float) -> float:
    if peso_kg <= 0:
        raise ValueError("peso_kg deve ser maior que zero")

    if distancia_km < 0:
        raise ValueError("distancia_km nao pode ser negativa")

    if valor_compra >= VALOR_COMPRA_FRETE_GRATIS:
        return 0.0

    valor_peso = calcular_valor_peso(peso_kg)
    multiplicador = calcular_multiplicador_distancia(distancia_km)

    valor_frete = valor_peso * multiplicador

    return round(max(valor_frete, FRETE_MINIMO), 2)


def calcular_valor_peso(peso_kg: float) -> float:
    if peso_kg <= 5:
        return peso_kg * 2.0

    if peso_kg <= 20:
        valor_primeira_faixa = 5 * 2.0
        valor_segunda_faixa = (peso_kg - 5) * 1.5

        return valor_primeira_faixa + valor_segunda_faixa

    valor_primeira_faixa = 5 * 2.0
    valor_segunda_faixa = 15 * 1.5
    valor_terceira_faixa = (peso_kg - 20) * 1.0

    return valor_primeira_faixa + valor_segunda_faixa + valor_terceira_faixa


def calcular_multiplicador_distancia(distancia_km: float) -> float:
    if distancia_km <= 50:
        return 1.0

    if distancia_km <= 200:
        return 1.3

    return 1.6