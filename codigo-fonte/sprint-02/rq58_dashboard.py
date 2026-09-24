"""RQ58: dashboard do LAB02 a partir do pipeline consolidado da RQ57.

Le os CSVs preparados pela RQ57 e gera:

- `lab02_rq58_resumo_dashboard.csv`: indicadores agregados para auditoria;
- `rq58_dashboard_inicial.png`: dashboard estatico em Matplotlib/Seaborn.

O dashboard e tolerante a dados incompletos. Ele mostra cobertura de issues e
metricas estaticas, sem preencher lacunas com zero.
"""

from __future__ import annotations

import argparse
import csv
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path


DADOS_PADRAO = Path(__file__).resolve().parents[2] / "dados"
CSV_RQ57_UNIFICADO_PADRAO = DADOS_PADRAO / "lab02_rq57_dataset_unificado.csv"
CSV_RQ57_RESUMO_PADRAO = DADOS_PADRAO / "lab02_rq57_resumo_tratamento.csv"
SAIDA_RESUMO_PADRAO = DADOS_PADRAO / "lab02_rq58_resumo_dashboard.csv"
SAIDA_GRAFICO_PADRAO = DADOS_PADRAO / "rq58_dashboard_inicial.png"

COLUNAS_RESUMO = ("categoria", "tratamento", "metrica", "valor", "observacao")


def _float_ou_none(valor):
    if valor is None or str(valor).strip() == "":
        return None
    try:
        return float(valor)
    except ValueError:
        return None


def _bool_ou_false(valor) -> bool:
    return str(valor).strip().lower() in {"true", "1", "sim"}


def carregar_csv(caminho: Path) -> list[dict]:
    if not caminho.is_file():
        return []
    with caminho.open(newline="", encoding="utf-8") as arquivo:
        return list(csv.DictReader(arquivo))


def _mediana(valores: list[float]):
    return round(statistics.median(valores), 4) if valores else ""


def _agrupar_por_tratamento(registros: list[dict]) -> dict[str, list[dict]]:
    grupos = defaultdict(list)
    for registro in registros:
        tratamento = registro.get("tratamento", "")
        if tratamento:
            grupos[tratamento].append(registro)
    return grupos


def resumir(unificado: list[dict], resumo_tratamento: list[dict]) -> list[dict]:
    """Cria indicadores agregados a partir dos CSVs da RQ57."""
    linhas = []
    por_tratamento = _agrupar_por_tratamento(unificado)
    tratamentos = sorted(por_tratamento)

    for tratamento in tratamentos:
        trials = por_tratamento[tratamento]
        duracoes = [
            valor for valor in (_float_ou_none(r.get("duracao_efetiva_segundos")) for r in trials)
            if valor is not None
        ]
        sucessos = [
            valor for valor in (_float_ou_none(r.get("sucesso_binario")) for r in trials)
            if valor is not None
        ]
        issues_informadas = sum(1 for r in trials if _bool_ou_false(r.get("issue_informada")))
        metricas_estaticas = sum(1 for r in trials if _bool_ou_false(r.get("metricas_rq30_disponiveis")))
        complexidades = [
            valor for valor in (_float_ou_none(r.get("complexidade_por_loc")) for r in trials)
            if valor is not None
        ]

        linhas.extend([
            {
                "categoria": "cobertura",
                "tratamento": tratamento,
                "metrica": "trials_unicos",
                "valor": len(trials),
                "observacao": "Trials unicos apos deduplicacao da RQ57.",
            },
            {
                "categoria": "cobertura",
                "tratamento": tratamento,
                "metrica": "issues_informadas",
                "valor": issues_informadas,
                "observacao": "Registros com issue preenchida, excluindo placeholder <ISSUE>.",
            },
            {
                "categoria": "cobertura",
                "tratamento": tratamento,
                "metrica": "metricas_rq30_disponiveis",
                "valor": metricas_estaticas,
                "observacao": "Trials com medicao estatica vinculada por trial_id.",
            },
            {
                "categoria": "tempo",
                "tratamento": tratamento,
                "metrica": "duracao_mediana_segundos",
                "valor": _mediana(duracoes),
                "observacao": "Mediana de duracao efetiva calculada pela RQ57.",
            },
            {
                "categoria": "sucesso",
                "tratamento": tratamento,
                "metrica": "taxa_sucesso",
                "valor": round(sum(sucessos) / len(sucessos), 4) if sucessos else "",
                "observacao": "Media de sucesso_binario nos trials validos.",
            },
            {
                "categoria": "metricas_estaticas",
                "tratamento": tratamento,
                "metrica": "complexidade_por_loc_mediana",
                "valor": _mediana(complexidades),
                "observacao": (
                    "Mediana disponivel na RQ57."
                    if complexidades else "Sem RQ30 suficiente para este tratamento."
                ),
            },
        ])

    # Mantem o resumo por participante/tratamento rastreavel no CSV da RQ58.
    for linha in resumo_tratamento:
        escopo = "%s|%s" % (linha.get("participante", ""), linha.get("tratamento", ""))
        linhas.append({
            "categoria": "resumo_participante",
            "tratamento": escopo,
            "metrica": "n_trials",
            "valor": linha.get("n_trials", ""),
            "observacao": "Linha herdada de lab02_rq57_resumo_tratamento.csv.",
        })
    return linhas


def salvar_resumo(linhas: list[dict], caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS_RESUMO)
        escritor.writeheader()
        escritor.writerows(linhas)


def _preparar_matplotlib_cache() -> None:
    cache_matplotlib = DADOS_PADRAO / ".cache" / "matplotlib"
    cache_matplotlib.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache_matplotlib))


def gerar_dashboard(unificado: list[dict], resumo_tratamento: list[dict], saida: Path) -> None:
    _preparar_matplotlib_cache()

    import matplotlib.pyplot as plt
    import pandas as pd
    import seaborn as sns

    df = pd.DataFrame(unificado)
    resumo = pd.DataFrame(resumo_tratamento)
    if df.empty:
        raise ValueError("Sem registros no dataset unificado da RQ57.")

    numericas_df = [
        "duracao_efetiva_segundos", "sucesso_binario", "complexidade_por_loc",
    ]
    for coluna in numericas_df:
        if coluna in df:
            df[coluna] = pd.to_numeric(df[coluna], errors="coerce")

    for coluna in ("issue_informada", "metricas_rq30_disponiveis"):
        if coluna in df:
            df[coluna] = df[coluna].astype(str).str.lower().isin(["true", "1", "sim"])

    for coluna in (
        "n_trials", "n_issues_informadas", "n_metricas_estaticas",
        "mediana_tempo_segundos", "taxa_sucesso", "mediana_complexidade_por_loc",
    ):
        if coluna in resumo:
            resumo[coluna] = pd.to_numeric(resumo[coluna], errors="coerce")

    sns.set_theme(style="whitegrid", context="notebook")
    figura, eixos = plt.subplots(2, 2, figsize=(15, 10))
    figura.suptitle("RQ58 - Dashboard do LAB02 a partir da RQ57", fontsize=16, fontweight="bold")

    ordem = sorted(df["tratamento"].dropna().unique())

    sns.countplot(data=df, x="tratamento", order=ordem, ax=eixos[0][0], color="#4C78A8")
    eixos[0][0].set_title("Trials unicos por tratamento")
    eixos[0][0].set_xlabel("")
    eixos[0][0].set_ylabel("Quantidade")

    sns.barplot(
        data=resumo, x="participante", y="mediana_tempo_segundos", hue="tratamento",
        errorbar=None, ax=eixos[0][1],
    )
    eixos[0][1].set_title("Mediana de tempo por participante")
    eixos[0][1].set_xlabel("")
    eixos[0][1].set_ylabel("Segundos")
    eixos[0][1].legend(title="Tratamento", fontsize=8, title_fontsize=8, loc="best")

    cobertura = resumo.melt(
        id_vars=["participante", "tratamento"],
        value_vars=["n_issues_informadas", "n_metricas_estaticas"],
        var_name="cobertura",
        value_name="quantidade",
    )
    cobertura["cobertura"] = cobertura["cobertura"].map({
        "n_issues_informadas": "Issues informadas",
        "n_metricas_estaticas": "Medicoes RQ30",
    })
    sns.barplot(
        data=cobertura, x="participante", y="quantidade", hue="cobertura",
        estimator=sum, errorbar=None, ax=eixos[1][0],
    )
    eixos[1][0].set_title("Cobertura de issues e RQ30")
    eixos[1][0].set_xlabel("")
    eixos[1][0].set_ylabel("Quantidade")
    eixos[1][0].legend(title="Cobertura", fontsize=8, title_fontsize=8, loc="best")

    eixo_metricas = eixos[1][1]
    metricas = df.dropna(subset=["complexidade_por_loc"])
    if not metricas.empty:
        sns.stripplot(
            data=metricas, x="tratamento", y="complexidade_por_loc", hue="participante",
            order=ordem, dodge=True, ax=eixo_metricas,
        )
        eixo_metricas.set_title("Complexidade por LOC (RQ30 disponivel)")
        eixo_metricas.set_xlabel("")
        eixo_metricas.set_ylabel("Complexidade / LOC")
        eixo_metricas.legend(title="Participante", fontsize=8, title_fontsize=8, loc="best")
        tratamentos_com_metricas = set(metricas["tratamento"].dropna())
        tratamentos_sem_metricas = [t for t in ordem if t not in tratamentos_com_metricas]
        if tratamentos_sem_metricas:
            eixo_metricas.text(
                0.98, 0.95,
                "Sem RQ30: " + ", ".join(tratamentos_sem_metricas),
                transform=eixo_metricas.transAxes,
                ha="right", va="top", fontsize=9,
                bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "alpha": 0.85},
            )
    else:
        eixo_metricas.axis("off")
        eixo_metricas.text(
            0.5, 0.5,
            "Metricas estaticas ainda indisponiveis.\nRode a RQ30 para os trials concluidos.",
            ha="center", va="center", fontsize=12,
        )

    total_trials = len(df)
    total_metricas = int(df.get("metricas_rq30_disponiveis", []).sum())
    total_issues = int(df.get("issue_informada", []).sum())
    figura.text(
        0.01, 0.01,
        "RQ57: %d trials unicos | Issues informadas: %d/%d | RQ30: %d/%d medicoes"
        % (total_trials, total_issues, total_trials, total_metricas, total_trials),
        fontsize=9,
    )
    figura.tight_layout(rect=(0, 0.03, 1, 0.95))
    saida.parent.mkdir(parents=True, exist_ok=True)
    figura.savefig(saida, dpi=300, bbox_inches="tight")
    plt.close(figura)


def principal(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-unificado", type=Path, default=CSV_RQ57_UNIFICADO_PADRAO)
    parser.add_argument("--csv-resumo-tratamento", type=Path, default=CSV_RQ57_RESUMO_PADRAO)
    parser.add_argument("--saida-resumo", type=Path, default=SAIDA_RESUMO_PADRAO)
    parser.add_argument("--saida-grafico", type=Path, default=SAIDA_GRAFICO_PADRAO)
    parser.add_argument("--sem-grafico", action="store_true",
                        help="Gera apenas o CSV-resumo, dispensando pandas/matplotlib/seaborn.")
    args = parser.parse_args(argv)

    unificado = carregar_csv(args.csv_unificado)
    resumo_tratamento = carregar_csv(args.csv_resumo_tratamento)
    if not unificado:
        parser.error("CSV unificado da RQ57 nao encontrado ou vazio: %s" % args.csv_unificado)
    if not resumo_tratamento:
        parser.error("CSV de resumo da RQ57 nao encontrado ou vazio: %s" % args.csv_resumo_tratamento)

    linhas = resumir(unificado, resumo_tratamento)
    salvar_resumo(linhas, args.saida_resumo)
    print("Resumo salvo em: %s" % args.saida_resumo.resolve())

    if not args.sem_grafico:
        try:
            gerar_dashboard(unificado, resumo_tratamento, args.saida_grafico)
            print("Dashboard salvo em: %s" % args.saida_grafico.resolve())
        except ImportError as erro:
            print(
                "Aviso: dependencia ausente (%s). Instale pandas, matplotlib e seaborn "
                "ou rode com --sem-grafico." % erro.name,
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(principal())
