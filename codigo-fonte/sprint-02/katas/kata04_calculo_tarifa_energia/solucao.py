def calcular_tarifa_energia(consumo_kwh, tipo_ligacao, bandeira):
    if consumo_kwh <= 0:
        raise ValueError("O consumo de energia deve ser estritamente maior que zero")

    tarifas = {
        "residencial": (0.50, 0.70, 0.90, 20.00),
        "comercial": (0.65, 0.85, 1.05, 50.00),
    }
    sobretaxas = {
        "verde": 0.00,
        "amarela": 0.02,
        "vermelha": 0.04,
    }

    if tipo_ligacao not in tarifas:
        raise ValueError("Tipo de ligacao invalido")
    if bandeira not in sobretaxas:
        raise ValueError("Bandeira tarifaria invalida")

    faixa_1, faixa_2, faixa_3, tarifa_minima = tarifas[tipo_ligacao]

    if consumo_kwh <= 100:
        valor = consumo_kwh * faixa_1
    elif consumo_kwh <= 300:
        valor = (100 * faixa_1) + ((consumo_kwh - 100) * faixa_2)
    else:
        valor = (100 * faixa_1) + (200 * faixa_2) + ((consumo_kwh - 300) * faixa_3)

    valor += consumo_kwh * sobretaxas[bandeira]
    valor = max(valor, tarifa_minima)
    return round(valor, 2)
