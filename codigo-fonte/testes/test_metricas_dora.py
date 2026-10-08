"""RQ80: testes da frequencia de deploy e da classificacao DORA de referencia."""

import pytest

from metricas import dora


def test_frequencia_de_deploy_em_releases_por_semana():
    assert dora.frequencia_de_deploy(365, 365 / 7) == pytest.approx(7.0)
    assert dora.frequencia_de_deploy(0, 52.14) == 0
    with pytest.raises(ValueError):
        dora.frequencia_de_deploy(5, 0)


@pytest.mark.parametrize("por_semana, esperado", [
    (7, "Elite"), (10, "Elite"), (6.99, "High"), (1, "High"),
    (0.99, "Medium"), (0.23, "Medium"), (0.22, "Low"), (0, "Low"), (None, None),
])
def test_classificar_frequencia(por_semana, esperado):
    assert dora.classificar_frequencia(por_semana) == esperado


@pytest.mark.parametrize("dias, esperado", [
    (0.5, "Elite"), (1, "High"), (6.99, "High"), (7, "Medium"),
    (29.9, "Medium"), (30, "Low"), (None, None),
])
def test_classificar_lead_time(dias, esperado):
    assert dora.classificar_lead_time(dias) == esperado


@pytest.mark.parametrize("taxa, esperado", [
    (0, "Elite"), (0.15, "Elite"), (0.1501, "High"), (0.30, "High"),
    (0.31, "Medium"), (0.45, "Medium"), (0.46, "Low"), (None, None),
])
def test_classificar_cfr(taxa, esperado):
    assert dora.classificar_cfr(taxa) == esperado


@pytest.mark.parametrize("horas, esperado", [
    (0.5, "Elite"), (1, "High"), (23.9, "High"), (24, "Medium"),
    (167.9, "Medium"), (168, "Low"), (None, None),
])
def test_classificar_recuperacao(horas, esperado):
    assert dora.classificar_recuperacao(horas) == esperado


@pytest.mark.parametrize("categorias, esperado", [
    (["Elite", "High", "High", "Low"], "High"),        # exemplo do enunciado (4, 3, 3, 1)
    (["Elite", "Elite", "High", "High"], "High"),      # mediana 3,5 -> 3
    (["Elite", "Medium", "Low", "Low"], "Low"),        # mediana 1,5 -> 1
    (["Elite", "Elite", "Elite", "Elite"], "Elite"),
    (["Elite", None, "High", "High"], None),           # metrica ausente
])
def test_classificacao_geral(categorias, esperado):
    assert dora.classificacao_geral(categorias) == esperado


def test_classificacao_geral_exige_quatro_metricas():
    with pytest.raises(ValueError):
        dora.classificacao_geral(["Elite", "High"])


def test_classificar_repositorio_sem_lead_time_deixa_geral_indefinida():
    resultado = dora.classificar_repositorio(2.0, None, 0.1, 0.5)
    assert resultado == {
        "classe_frequencia": "High",
        "classe_lead_time": None,
        "classe_cfr": "Elite",
        "classe_recuperacao": "Elite",
        "classe_geral": None,
    }
    assert dora.classificar_repositorio(2.0, 3, 0.1, 0.5)["classe_geral"] == "High"
