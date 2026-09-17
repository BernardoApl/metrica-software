"""Kata 02: calculo de tarifa de estacionamento por tempo e tipo de veiculo."""

import math

TARIFAS = {
    "carro": {"primeira_hora": 8.0, "hora_adicional": 4.0, "diaria": 40.0},
    "moto": {"primeira_hora": 5.0, "hora_adicional": 2.0, "diaria": 25.0},
    "caminhao": {"primeira_hora": 15.0, "hora_adicional": 7.0, "diaria": 70.0},
}


def calcular_estacionamento(horas: float, tipo_veiculo: str) -> float:
    if horas <= 0:
        raise ValueError("horas deve ser maior que zero")
    if tipo_veiculo not in TARIFAS:
        raise ValueError("tipo_veiculo invalido")

    tarifa = TARIFAS[tipo_veiculo]
    horas_cobradas = math.ceil(horas)

    valor = tarifa["primeira_hora"] + max(0, horas_cobradas - 1) * tarifa["hora_adicional"]
    valor = min(valor, tarifa["diaria"])

    return round(valor, 2)
