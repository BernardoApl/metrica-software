"""Frequencia de deploy (RQ 01) e classificacao DORA (tabela de referencia da RQ 07).

Cortes fixos da disciplina:

| Metrica                  | Elite      | High           | Medium              | Low        |
|--------------------------|------------|----------------|---------------------|------------|
| Deployment frequency     | >= 7/sem   | >= 1 e < 7/sem | >= 1/mes e < 1/sem  | < 1/mes    |
| Lead time (mediana)      | < 1 dia    | 1 dia a < 7    | 7 a < 30 dias       | >= 30 dias |
| Change failure rate      | <= 15%     | > 15% e <= 30% | > 30% e <= 45%      | > 45%      |
| Recuperacao (mediana)    | < 1 hora   | 1 h a < 1 dia  | 1 dia a < 1 semana  | >= 1 sem   |

Classificacao geral: Elite=4, High=3, Medium=2, Low=1 em cada metrica; a
categoria e a mediana das quatro notas, arredondada para baixo.
"""

from __future__ import annotations

import math
from statistics import median
from typing import Iterable, Optional

ELITE, HIGH, MEDIUM, LOW = "Elite", "High", "Medium", "Low"
NOTAS = {ELITE: 4, HIGH: 3, MEDIUM: 2, LOW: 1}
CATEGORIAS = {nota: categoria for categoria, nota in NOTAS.items()}

#: Um mes medio (365,25 / 12 dias) expresso em semanas: "1 por mes" ~ 0,23 por semana.
SEMANAS_POR_MES = 365.25 / 12 / 7


def frequencia_de_deploy(releases: int, semanas: float) -> float:
    """RQ 01: releases publicadas na janela / semanas da janela."""
    if semanas <= 0:
        raise ValueError("A janela precisa ter duracao positiva.")
    return releases / semanas


def classificar_frequencia(por_semana: Optional[float]) -> Optional[str]:
    if por_semana is None:
        return None
    if por_semana >= 7:
        return ELITE
    if por_semana >= 1:
        return HIGH
    if por_semana >= 1 / SEMANAS_POR_MES:
        return MEDIUM
    return LOW


def classificar_lead_time(dias: Optional[float]) -> Optional[str]:
    if dias is None:
        return None
    if dias < 1:
        return ELITE
    if dias < 7:
        return HIGH
    if dias < 30:
        return MEDIUM
    return LOW


def classificar_cfr(taxa: Optional[float]) -> Optional[str]:
    """``taxa`` em fracao (0,15 = 15%)."""
    if taxa is None:
        return None
    if taxa <= 0.15:
        return ELITE
    if taxa <= 0.30:
        return HIGH
    if taxa <= 0.45:
        return MEDIUM
    return LOW


def classificar_recuperacao(horas: Optional[float]) -> Optional[str]:
    if horas is None:
        return None
    if horas < 1:
        return ELITE
    if horas < 24:
        return HIGH
    if horas < 24 * 7:
        return MEDIUM
    return LOW


def classificacao_geral(categorias: Iterable[Optional[str]]) -> Optional[str]:
    """Mediana das notas das quatro metricas, arredondada para baixo.

    Devolve ``None`` se alguma das quatro categorias estiver ausente: a
    classificacao geral so e definida com as quatro metricas.
    """
    categorias = list(categorias)
    if len(categorias) != 4:
        raise ValueError("A classificacao geral usa exatamente quatro metricas.")
    if any(categoria is None for categoria in categorias):
        return None
    return CATEGORIAS[math.floor(median(NOTAS[c] for c in categorias))]


def classificar_repositorio(frequencia: Optional[float], lead_time_dias: Optional[float],
                            cfr: Optional[float], recuperacao_horas: Optional[float]) -> dict:
    categorias = {
        "classe_frequencia": classificar_frequencia(frequencia),
        "classe_lead_time": classificar_lead_time(lead_time_dias),
        "classe_cfr": classificar_cfr(cfr),
        "classe_recuperacao": classificar_recuperacao(recuperacao_horas),
    }
    categorias["classe_geral"] = classificacao_geral(categorias.values())
    return categorias
