"""Kata 03: calculo de desconto de pedido por valor, tipo de cliente e cupom (RQ39 - sem IA)."""

DESCONTO_MAXIMO = 0.20
BONUS_CLIENTE_PREMIUM = 0.05
BONUS_CUPOM = 0.05


def calcular_pedido(valor: float, tipo_cliente: str, cupom: bool = False) -> float:
    if valor <= 0:
        raise ValueError("valor deve ser maior que zero")

    desconto = _desconto_base_por_faixa(valor)

    if tipo_cliente == "premium":
        desconto += BONUS_CLIENTE_PREMIUM

    if cupom:
        desconto += BONUS_CUPOM

    desconto = min(desconto, DESCONTO_MAXIMO)

    return round(valor * (1 - desconto), 2)


def _desconto_base_por_faixa(valor: float) -> float:
    if valor >= 300:
        return 0.10
    if valor >= 100:
        return 0.05
    return 0.0
