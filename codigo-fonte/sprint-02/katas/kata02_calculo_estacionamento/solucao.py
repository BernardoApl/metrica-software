"""Kata 02: calculo de tarifa de estacionamento por tempo e tipo de veiculo (RQ38 - com IA)."""

import math

TIPOS_VEICULO = ("carro", "moto", "caminhao")
PRIMEIRA_HORA = {"carro": 8.0, "moto": 5.0, "caminhao": 15.0}
HORA_ADICIONAL = {"carro": 4.0, "moto": 2.0, "caminhao": 7.0}
DIARIA = {"carro": 40.0, "moto": 25.0, "caminhao": 70.0}


def calcular_estacionamento(horas: float, tipo_veiculo: str) -> float:
    if horas <= 0:
        raise ValueError("horas deve ser maior que zero")
    if tipo_veiculo not in TIPOS_VEICULO:
        raise ValueError("tipo_veiculo invalido")

    horas_cobradas = math.ceil(horas)
    horas_adicionais = max(0, horas_cobradas - 1)

    valor = PRIMEIRA_HORA[tipo_veiculo] + horas_adicionais * HORA_ADICIONAL[tipo_veiculo]
    valor = min(valor, DIARIA[tipo_veiculo])

    return round(valor, 2)
