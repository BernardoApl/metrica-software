"""RQ57: pipeline Pandas que junta RQ28 (tempo) + RQ30 (metricas estaticas) num dataset unico.

Prepara os dados para o dashboard (RQ58) - nao gera grafico aqui. Gera dois CSVs em `dados/`:
- `lab02_rq57_dataset_unificado.csv`: uma linha por trial, tempo + metricas estaticas juntos (join por
  `trial_id`, herdado do RQ28/RQ30).
- `lab02_rq57_resumo_tratamento.csv`: uma linha por (participante, tratamento), com as medianas/taxas
  que o RQ58 vai plotar.

`duracao_efetiva_segundos` e `sucesso_binario` seguem a mesma regra do RQ51/RQ52: sucesso usa o tempo
real, censura usa o limite (35 min), interrupcao/erro de execucao ficam de fora (NaN). `complexidade_por_loc`
segue o RQ53 (complexidade total normalizada pelo tamanho do arquivo).

Quando o CSV da RQ28 contem o mesmo `trial_id` mais de uma vez, o pipeline preserva a primeira ocorrencia
para manter uma linha por trial no dataset do dashboard.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
RQ28_PADRAO = RAIZ / "dados" / "lab02_rq28_tempos.csv"
RQ30_PADRAO = RAIZ / "dados" / "lab02_rq30_metricas_estaticas.csv"
SAIDA_UNIFICADO_PADRAO = RAIZ / "dados" / "lab02_rq57_dataset_unificado.csv"
SAIDA_RESUMO_PADRAO = RAIZ / "dados" / "lab02_rq57_resumo_tratamento.csv"

COLUNAS_RQ28 = ["trial_id", "participante", "kata", "tratamento", "issue", "duracao_segundos",
                "limite_segundos", "status", "sucesso", "censurado"]
COLUNAS_RQ30_METRICAS = ["trial_id", "loc", "sloc", "lloc", "funcoes_analisadas", "complexidade_media",
                          "complexidade_maxima", "indice_manutenibilidade", "duplicacao_disponivel",
                          "duplicacao_percentual"]

STATUS_TENTATIVA_VALIDA = {"sucesso", "limite_atingido"}


def carregar_rq28(caminho: Path = RQ28_PADRAO) -> pd.DataFrame:
    if not Path(caminho).exists():
        return pd.DataFrame(columns=COLUNAS_RQ28 + [
            "issue_informada", "duracao_efetiva_segundos", "sucesso_binario",
        ])

    df = pd.read_csv(caminho, dtype=str)
    df = df.drop_duplicates(subset=["trial_id"], keep="first").copy()
    df["duracao_segundos"] = pd.to_numeric(df["duracao_segundos"], errors="coerce")
    df["limite_segundos"] = pd.to_numeric(df["limite_segundos"], errors="coerce")
    sucesso_bool = df["sucesso"].str.lower() == "true"
    censurado_bool = df["censurado"].str.lower() == "true"
    status_lower = df["status"].str.lower()
    issue_texto = df["issue"].fillna("").str.strip()

    df["issue_informada"] = (issue_texto != "") & (issue_texto != "<ISSUE>")

    df["duracao_efetiva_segundos"] = pd.NA
    df.loc[sucesso_bool, "duracao_efetiva_segundos"] = df.loc[sucesso_bool, "duracao_segundos"]
    censurado_sem_sucesso = censurado_bool & ~sucesso_bool
    df.loc[censurado_sem_sucesso, "duracao_efetiva_segundos"] = df.loc[censurado_sem_sucesso, "limite_segundos"]
    df["duracao_efetiva_segundos"] = pd.to_numeric(df["duracao_efetiva_segundos"], errors="coerce")

    tentativa_valida = status_lower.isin(STATUS_TENTATIVA_VALIDA)
    df["sucesso_binario"] = pd.NA
    df.loc[tentativa_valida, "sucesso_binario"] = sucesso_bool[tentativa_valida].astype(float)
    df["sucesso_binario"] = pd.to_numeric(df["sucesso_binario"], errors="coerce")
    return df


def carregar_rq30(caminho: Path = RQ30_PADRAO) -> pd.DataFrame:
    if not Path(caminho).exists():
        return pd.DataFrame(columns=COLUNAS_RQ30_METRICAS + ["complexidade_por_loc"])

    df = pd.read_csv(caminho, dtype=str)
    for coluna in ("loc", "funcoes_analisadas", "complexidade_media", "complexidade_maxima",
                   "indice_manutenibilidade", "duplicacao_percentual"):
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce")

    loc_sem_zero = df["loc"].where(df["loc"] != 0)
    df["complexidade_por_loc"] = (df["complexidade_media"] * df["funcoes_analisadas"]) / loc_sem_zero
    return df[COLUNAS_RQ30_METRICAS + ["complexidade_por_loc"]]


def construir_dataset_unificado(rq28: pd.DataFrame, rq30: pd.DataFrame) -> pd.DataFrame:
    unificado = rq28.merge(rq30, on="trial_id", how="left", suffixes=("", "_rq30"))
    unificado["metricas_rq30_disponiveis"] = unificado["loc"].notna()
    unificado["duplicacao_percentual_disponivel"] = unificado["duplicacao_percentual"].notna()
    return unificado


def construir_resumo_por_tratamento(unificado: pd.DataFrame) -> pd.DataFrame:
    if unificado.empty:
        return pd.DataFrame(columns=[
            "participante", "tratamento", "n_trials", "n_issues_informadas", "n_metricas_estaticas",
            "mediana_tempo_segundos", "taxa_sucesso", "mediana_complexidade_por_loc",
            "mediana_duplicacao_percentual", "mediana_indice_manutenibilidade",
        ])

    resumo = unificado.groupby(["participante", "tratamento"]).agg(
        n_trials=("trial_id", "count"),
        n_issues_informadas=("issue_informada", "sum"),
        n_metricas_estaticas=("metricas_rq30_disponiveis", "sum"),
        mediana_tempo_segundos=("duracao_efetiva_segundos", "median"),
        taxa_sucesso=("sucesso_binario", "mean"),
        mediana_complexidade_por_loc=("complexidade_por_loc", "median"),
        mediana_duplicacao_percentual=("duplicacao_percentual", "median"),
        mediana_indice_manutenibilidade=("indice_manutenibilidade", "median"),
    ).reset_index()
    return resumo


def executar(rq28_caminho: Path = RQ28_PADRAO, rq30_caminho: Path = RQ30_PADRAO):
    rq28 = carregar_rq28(rq28_caminho)
    rq30 = carregar_rq30(rq30_caminho)
    unificado = construir_dataset_unificado(rq28, rq30)
    resumo = construir_resumo_por_tratamento(unificado)
    return unificado, resumo


def principal(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rq28", type=Path, default=RQ28_PADRAO)
    parser.add_argument("--rq30", type=Path, default=RQ30_PADRAO)
    parser.add_argument("--saida-unificado", type=Path, default=SAIDA_UNIFICADO_PADRAO)
    parser.add_argument("--saida-resumo", type=Path, default=SAIDA_RESUMO_PADRAO)
    args = parser.parse_args(argv)

    unificado, resumo = executar(args.rq28, args.rq30)

    args.saida_unificado.parent.mkdir(parents=True, exist_ok=True)
    unificado.to_csv(args.saida_unificado, index=False)
    resumo.to_csv(args.saida_resumo, index=False)

    print("Dataset unificado: %d trials -> %s" % (len(unificado), args.saida_unificado))
    print("Resumo por participante/tratamento: %d linhas -> %s" % (len(resumo), args.saida_resumo))
    if not resumo.empty:
        print(resumo.to_string(index=False))
    else:
        print("Sem trials suficientes para resumo (veja RQ50 - auditoria do dataset).")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
