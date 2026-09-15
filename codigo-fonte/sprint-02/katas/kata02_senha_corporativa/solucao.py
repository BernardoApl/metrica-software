"""Kata 02: calculo de estacionamento."""


def validar_senha(horas, tipo_veiculo):
    if horas <= 0:
        raise ValueError("A quantidade de horas deve ser maior que zero.")

    tipo_veiculo = tipo_veiculo.lower()
    if tipo_veiculo not in ["carro", "moto"]:
        raise ValueError("Tipo de veiculo invalido. Use 'carro' ou 'moto'.")

    if horas <= 1:
        valor_base = 6.00
    else:
        valor_base = 6.00 + (horas - 1) * 4.00

    if horas > 8:
        valor_base = 35.00

    if tipo_veiculo == "moto":
        valor_final = valor_base * 0.80
    else:
        valor_final = valor_base

    return float(valor_final)
