"""Kata 01: calculo de frete progressivo por peso e distancia (RQ37 - sem IA)."""

FAIXAS_PESO = [(5, 2.0), (20, 1.5), (float("inf"), 1.0)]
FAIXAS_DISTANCIA = [(50, 1.0), (200, 1.3), (float("inf"), 1.6)]
FRETE_MINIMO = 5.0
VALOR_COMPRA_FRETE_GRATIS = 300


def calcular_frete(peso_kg: float, distancia_km: float, valor_compra: float) -> float:
    if peso_kg <= 0:
        raise ValueError("peso_kg deve ser maior que zero")
    if distancia_km < 0:
        raise ValueError("distancia_km nao pode ser negativa")

    if valor_compra >= VALOR_COMPRA_FRETE_GRATIS:
        return 0.0

    valor_base = _valor_por_peso(peso_kg)
    multiplicador = _multiplicador_por_distancia(distancia_km)

    return round(max(FRETE_MINIMO, valor_base * multiplicador), 2)


def _valor_por_peso(peso_kg: float) -> float:
    restante = peso_kg
    limite_anterior = 0.0
    valor = 0.0

    for limite, preco_por_kg in FAIXAS_PESO:
        peso_na_faixa = min(restante, limite - limite_anterior)
        if peso_na_faixa <= 0:
            break
        valor += peso_na_faixa * preco_por_kg
        restante -= peso_na_faixa
        limite_anterior = limite
        if restante <= 0:
            break

    return valor


def _multiplicador_por_distancia(distancia_km: float) -> float:
    for limite, multiplicador in FAIXAS_DISTANCIA:
        if distancia_km <= limite:
            return multiplicador
    return FAIXAS_DISTANCIA[-1][1]
