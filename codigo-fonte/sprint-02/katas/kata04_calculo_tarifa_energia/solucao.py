def calcular_conta_energia(consumo_kwh, cliente_social=False):
    if consumo_kwh <= 0:
        raise ValueError("O consumo de energia deve ser estritamente maior que zero")

    if consumo_kwh <= 100:
        valor = consumo_kwh * 0.50
    elif consumo_kwh <= 200:
        valor = (100 * 0.50) + ((consumo_kwh - 100) * 0.65)
    else:
        valor = (100 * 0.50) + (100 * 0.65) + ((consumo_kwh - 200) * 0.80)

    if cliente_social:
        valor *= 0.90

    if consumo_kwh > 500:
        valor *= 1.05

    return float(valor)
