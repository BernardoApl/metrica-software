"""RQ58: dashboard inicial do LAB02 com tempo, sucesso e metricas estaticas.

Le os CSVs reais ja coletados pela RQ28 e RQ30 e gera:

- um CSV-resumo com indicadores agregados;
- uma imagem PNG em Matplotlib/Seaborn para acompanhamento inicial.

Esta versao e intencionalmente tolerante a dados incompletos: o dashboard
mostra a cobertura disponivel e anota lacunas em vez de inventar valores.
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
CSV_RQ28_PADRAO = DADOS_PADRAO / "lab02_rq28_tempos.csv"
CSV_RQ30_PADRAO = DADOS_PADRAO / "lab02_rq30_metricas_estaticas.csv"
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


def resumir(tempos: list[dict], metricas: list[dict]) -> list[dict]:
    """Cria linhas agregadas para o dashboard e para auditoria textual."""
    linhas = []
    tratamentos = sorted({
        registro.get("tratamento", "")
        for registro in [*tempos, *metricas]
        if registro.get("tratamento")
    })

    for tratamento in tratamentos:
        trials = [r for r in tempos if r.get("tratamento") == tratamento]
        sucessos = [r for r in trials if _bool_ou_false(r.get("sucesso"))]
        duracoes = [
            valor for valor in (_float_ou_none(r.get("duracao_segundos")) for r in trials)
            if valor is not None
        ]
        linhas.extend([
            {
                "categoria": "tempo",
                "tratamento": tratamento,
                "metrica": "trials",
                "valor": len(trials),
                "observacao": "Registros da RQ28.",
            },
            {
                "categoria": "tempo",
                "tratamento": tratamento,
                "metrica": "taxa_sucesso",
                "valor": round(len(sucessos) / len(trials), 4) if trials else "",
                "observacao": "Sucessos / trials no CSV da RQ28.",
            },
            {
                "categoria": "tempo",
                "tratamento": tratamento,
                "metrica": "duracao_mediana_segundos",
                "valor": _mediana(duracoes),
                "observacao": "Mediana usada por robustez com N pequeno.",
            },
        ])

        metricas_tratamento = [r for r in metricas if r.get("tratamento") == tratamento]
        for metrica in ("complexidade_media", "loc", "duplicacao_percentual"):
            valores = [
                valor for valor in (_float_ou_none(r.get(metrica)) for r in metricas_tratamento)
                if valor is not None
            ]
            linhas.append({
                "categoria": "metricas_estaticas",
                "tratamento": tratamento,
                "metrica": f"{metrica}_mediana",
                "valor": _mediana(valores),
                "observacao": (
                    "Medicoes disponiveis na RQ30."
                    if valores else "Sem medicoes validas na RQ30 para este tratamento."
                ),
            })
    return linhas


def salvar_resumo(linhas: list[dict], caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS_RESUMO)
        escritor.writeheader()
        escritor.writerows(linhas)


def _dataframe_tempos(pd, tempos: list[dict]):
    linhas = []
    for registro in tempos:
        duracao = _float_ou_none(registro.get("duracao_segundos"))
        if duracao is None:
            continue
        linhas.append({
            "participante": registro.get("participante", ""),
            "kata": registro.get("kata", ""),
            "tratamento": registro.get("tratamento", ""),
            "issue": registro.get("issue", ""),
            "duracao_segundos": duracao,
            "sucesso": _bool_ou_false(registro.get("sucesso")),
        })
    return pd.DataFrame(linhas)


def _dataframe_metricas(pd, metricas: list[dict]):
    linhas = []
    for registro in metricas:
        linhas.append({
            "participante": registro.get("participante", ""),
            "kata": registro.get("kata", ""),
            "tratamento": registro.get("tratamento", ""),
            "complexidade_media": _float_ou_none(registro.get("complexidade_media")),
            "loc": _float_ou_none(registro.get("loc")),
            "duplicacao_percentual": _float_ou_none(registro.get("duplicacao_percentual")),
        })
    return pd.DataFrame(linhas)


def gerar_dashboard(tempos: list[dict], metricas: list[dict], saida: Path) -> None:
    cache_matplotlib = DADOS_PADRAO / ".cache" / "matplotlib"
    cache_matplotlib.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache_matplotlib))

    import matplotlib.pyplot as plt
    import pandas as pd
    import seaborn as sns

    df_tempos = _dataframe_tempos(pd, tempos)
    df_metricas = _dataframe_metricas(pd, metricas)

    if df_tempos.empty:
        raise ValueError("Sem registros de tempo para gerar o dashboard.")

    sns.set_theme(style="whitegrid", context="notebook")
    figura, eixos = plt.subplots(2, 2, figsize=(15, 10))
    figura.suptitle("RQ58 - Dashboard inicial do LAB02", fontsize=16, fontweight="bold")

    ordem = sorted(df_tempos["tratamento"].dropna().unique())

    sns.countplot(data=df_tempos, x="tratamento", order=ordem, ax=eixos[0][0], color="#4C78A8")
    eixos[0][0].set_title("Trials coletados por tratamento")
    eixos[0][0].set_xlabel("")
    eixos[0][0].set_ylabel("Quantidade")

    sns.stripplot(
        data=df_tempos, x="tratamento", y="duracao_segundos", hue="kata",
        order=ordem, dodge=True, ax=eixos[0][1],
    )
    eixos[0][1].set_title("Tempo de resolucao por tratamento e kata")
    eixos[0][1].set_xlabel("")
    eixos[0][1].set_ylabel("Segundos")
    eixos[0][1].legend(title="Kata", fontsize=8, title_fontsize=8, loc="best")

    sucesso = (
        df_tempos.groupby("tratamento", as_index=False)["sucesso"]
        .mean()
        .assign(taxa_sucesso=lambda dados: dados["sucesso"] * 100)
    )
    sns.barplot(data=sucesso, x="tratamento", y="taxa_sucesso", order=ordem, ax=eixos[1][0], color="#59A14F")
    eixos[1][0].set_title("Taxa de sucesso por tratamento")
    eixos[1][0].set_xlabel("")
    eixos[1][0].set_ylabel("% de trials com sucesso")
    eixos[1][0].set_ylim(0, 105)

    eixo_metricas = eixos[1][1]
    metricas_disponiveis = not df_metricas.empty and df_metricas[["complexidade_media", "loc"]].notna().any().any()
    if metricas_disponiveis:
        metricas_longas = df_metricas.melt(
            id_vars=["tratamento", "kata"],
            value_vars=["complexidade_media", "loc"],
            var_name="metrica",
            value_name="valor",
        ).dropna(subset=["valor"])
        sns.barplot(
            data=metricas_longas, x="metrica", y="valor", hue="tratamento",
            estimator="median", errorbar=None, ax=eixo_metricas,
        )
        eixo_metricas.set_title("Metricas estaticas disponiveis (mediana)")
        eixo_metricas.set_xlabel("")
        eixo_metricas.set_ylabel("Valor")
        eixo_metricas.legend(title="Tratamento", fontsize=8, title_fontsize=8, loc="best")
        tratamentos_com_metricas = set(metricas_longas["tratamento"].dropna())
        tratamentos_sem_metricas = [
            tratamento for tratamento in ordem if tratamento not in tratamentos_com_metricas
        ]
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
            "Metricas estaticas ainda indisponiveis.\nRode a RQ30 para os trials concluídos.",
            ha="center", va="center", fontsize=12,
        )

    cobertura = "RQ28: %d trials | RQ30: %d medicoes" % (len(df_tempos), len(df_metricas))
    figura.text(
        0.01, 0.01,
        cobertura + " | Dashboard inicial: resultados mudam quando novos CSVs forem consolidados.",
        fontsize=9,
    )
    figura.tight_layout(rect=(0, 0.03, 1, 0.95))
    saida.parent.mkdir(parents=True, exist_ok=True)
    figura.savefig(saida, dpi=300, bbox_inches="tight")
    plt.close(figura)


def principal(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-rq28", type=Path, default=CSV_RQ28_PADRAO)
    parser.add_argument("--csv-rq30", type=Path, default=CSV_RQ30_PADRAO)
    parser.add_argument("--saida-resumo", type=Path, default=SAIDA_RESUMO_PADRAO)
    parser.add_argument("--saida-grafico", type=Path, default=SAIDA_GRAFICO_PADRAO)
    parser.add_argument("--sem-grafico", action="store_true",
                        help="Gera apenas o CSV-resumo, dispensando pandas/matplotlib/seaborn.")
    args = parser.parse_args(argv)

    tempos = carregar_csv(args.csv_rq28)
    metricas = carregar_csv(args.csv_rq30)
    if not tempos:
        parser.error("CSV da RQ28 nao encontrado ou sem registros: %s" % args.csv_rq28)

    linhas = resumir(tempos, metricas)
    salvar_resumo(linhas, args.saida_resumo)
    print("Resumo salvo em: %s" % args.saida_resumo.resolve())

    if not args.sem_grafico:
        try:
            gerar_dashboard(tempos, metricas, args.saida_grafico)
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
