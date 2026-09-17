"""Kata 04: calculo de tarifa de energia eletrica por consumo, ligacao e bandeira."""

FAIXAS_CONSUMO = {
    "residencial": [(100, 0.50), (300, 0.70), (float("inf"), 0.90)],
    "comercial": [(100, 0.65), (300, 0.85), (float("inf"), 1.05)],
}

SOBRETAXA_BANDEIRA = {"verde": 0.0, "amarela": 0.02, "vermelha": 0.04}

TARIFA_MINIMA = {"residencial": 20.0, "comercial": 50.0}


def calcular_tarifa_energia(consumo_kwh: float, tipo_ligacao: str, bandeira: str) -> float:
    if consumo_kwh <= 0:
        raise ValueError("consumo_kwh deve ser maior que zero")
    if tipo_ligacao not in FAIXAS_CONSUMO:
        raise ValueError("tipo_ligacao invalido")
    if bandeira not in SOBRETAXA_BANDEIRA:
        raise ValueError("bandeira invalida")

    valor = _valor_por_consumo(consumo_kwh, FAIXAS_CONSUMO[tipo_ligacao])
    valor += consumo_kwh * SOBRETAXA_BANDEIRA[bandeira]
    valor = max(valor, TARIFA_MINIMA[tipo_ligacao])

    return round(valor, 2)


def _valor_por_consumo(consumo_kwh: float, faixas: list) -> float:
    restante = consumo_kwh
    limite_anterior = 0.0
    valor = 0.0

    for limite, preco_por_kwh in faixas:
        consumo_na_faixa = min(restante, limite - limite_anterior)
        if consumo_na_faixa <= 0:
            break
        valor += consumo_na_faixa * preco_por_kwh
        restante -= consumo_na_faixa
        limite_anterior = limite
        if restante <= 0:
            break

    return valor
