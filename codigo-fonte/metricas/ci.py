"""RQ79: CFR pelo proxy de CI (RQ 03a) e tempo de recuperacao (RQ 04).

Definicoes operacionais (secao 3 do enunciado):

- so contam workflow runs do default branch, disparados por ``push`` e criados
  dentro da janela de observacao;
- ``conclusion`` define sucesso/falha; ``cancelled``, ``skipped``, ``neutral``,
  ``action_required``, ``stale`` e vazio (em andamento) sao ignorados e nao
  entram em nenhum calculo -- inclusive nao encerram nem interrompem episodios;
- episodio de falha: comeca na primeira falha apos um sucesso do mesmo workflow
  e termina na proxima execucao bem-sucedida desse workflow. Duracao =
  ``updated_at`` do sucesso - ``run_started_at`` da primeira falha.

Censura:

- *a direita*: o episodio nao terminou ate o fim da janela. Ele e mantido e
  marcado como censurado, com a duracao parcial (limite inferior) ate o fim da
  janela, mas nao entra na mediana;
- *a esquerda*: o workflow ja comeca a janela falhando, sem sucesso anterior
  observado. Nao sabemos quando o episodio comecou, entao ele tambem e
  registrado, marcado e excluido da mediana.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from statistics import median
from typing import Iterable, Optional

SUCESSO = "sucesso"
FALHA = "falha"

CONCLUSOES_SUCESSO = frozenset({"success"})
CONCLUSOES_FALHA = frozenset({"failure", "timed_out", "startup_failure"})


def data_utc(valor) -> datetime:
    """Converte ``2026-01-01T10:00:00Z`` (ou um ``datetime``) para UTC com fuso."""
    if isinstance(valor, datetime):
        data = valor
    else:
        data = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    if data.tzinfo is None:
        raise ValueError("Data sem fuso horario: %r" % (valor,))
    return data.astimezone(timezone.utc)


def classificar_conclusao(conclusao: Optional[str]) -> Optional[str]:
    """Devolve ``"sucesso"``, ``"falha"`` ou ``None`` (execucao ignorada)."""
    if conclusao in CONCLUSOES_SUCESSO:
        return SUCESSO
    if conclusao in CONCLUSOES_FALHA:
        return FALHA
    return None


def inicio_da_execucao(run: dict) -> datetime:
    """``run_started_at`` e o inicio real; ``created_at`` cobre runs antigos sem o campo."""
    return data_utc(run.get("run_started_at") or run["created_at"])


def filtrar_runs_validos(runs: Iterable[dict], branch: str, inicio, fim) -> list[dict]:
    """Mantem runs de ``push`` no ``branch`` criados em ``[inicio, fim]`` e com conclusao valida."""
    inicio, fim = data_utc(inicio), data_utc(fim)
    validos = []
    for run in runs:
        if run.get("event") != "push" or run.get("head_branch") != branch:
            continue
        if not inicio <= data_utc(run["created_at"]) <= fim:
            continue
        if classificar_conclusao(run.get("conclusion")) is None:
            continue
        validos.append(run)
    return validos


def cfr_ci(runs: Iterable[dict]) -> dict:
    """CFR (a) = falhas / (falhas + sucessos); runs ignorados nao entram no denominador."""
    falhas = sucessos = ignorados = 0
    for run in runs:
        classe = classificar_conclusao(run.get("conclusion"))
        if classe == FALHA:
            falhas += 1
        elif classe == SUCESSO:
            sucessos += 1
        else:
            ignorados += 1
    total = falhas + sucessos
    return {
        "falhas": falhas,
        "sucessos": sucessos,
        "ignorados": ignorados,
        "cfr": falhas / total if total else None,
    }


def _ordenar(runs: Iterable[dict]) -> list[dict]:
    return sorted(runs, key=lambda run: (inicio_da_execucao(run), run.get("id") or 0))


def episodios_de_falha(runs: Iterable[dict], fim_janela) -> list[dict]:
    """Episodios de falha de **um unico workflow**, em ordem cronologica."""
    fim_janela = data_utc(fim_janela)
    episodios = []
    anterior = None  # ultima classe valida observada
    aberto = None
    for run in _ordenar(runs):
        classe = classificar_conclusao(run.get("conclusion"))
        if classe is None:
            continue
        if classe == FALHA and aberto is None:
            aberto = {
                "workflow_id": run.get("workflow_id"),
                "inicio": inicio_da_execucao(run),
                "falhas": 0,
                "censura_esquerda": anterior is None,
            }
        if classe == FALHA and aberto is not None:
            aberto["falhas"] += 1
        elif classe == SUCESSO and aberto is not None:
            fim = data_utc(run["updated_at"])
            episodios.append(_fechar(aberto, fim, censurado=False))
            aberto = None
        anterior = classe
    if aberto is not None:
        episodios.append(_fechar(aberto, max(fim_janela, aberto["inicio"]), censurado=True))
    return episodios


def _fechar(episodio: dict, fim: datetime, censurado: bool) -> dict:
    return {
        **episodio,
        "fim": fim,
        "horas": (fim - episodio["inicio"]).total_seconds() / 3600,
        "censurado": censurado,
    }


def tempo_de_recuperacao(runs: Iterable[dict], fim_janela) -> dict:
    """Agrupa por workflow, extrai os episodios e resume o repositorio.

    A mediana usa apenas episodios completos (sem censura a esquerda ou a
    direita). As contagens de censurados sao devolvidas para serem reportadas.
    """
    por_workflow = defaultdict(list)
    for run in runs:
        por_workflow[run.get("workflow_id")].append(run)

    episodios = []
    for workflow_runs in por_workflow.values():
        episodios.extend(episodios_de_falha(workflow_runs, fim_janela))

    completos = [e["horas"] for e in episodios if not e["censurado"] and not e["censura_esquerda"]]
    censurados = sum(1 for e in episodios if e["censurado"])
    return {
        "episodios": len(episodios),
        "episodios_completos": len(completos),
        "episodios_censurados": censurados,
        "episodios_censura_esquerda": sum(1 for e in episodios if e["censura_esquerda"]),
        "proporcao_censurados": censurados / len(episodios) if episodios else None,
        "mediana_horas": median(completos) if completos else None,
        "detalhes": episodios,
    }


def metricas_ci_repositorio(runs: Iterable[dict], branch: str, inicio, fim) -> dict:
    """Aplica os filtros da secao 3 e calcula CFR (a) e tempo de recuperacao juntos."""
    validos = filtrar_runs_validos(runs, branch, inicio, fim)
    cfr = cfr_ci(validos)
    recuperacao = tempo_de_recuperacao(validos, fim)
    return {
        "runs_validos": len(validos),
        "runs_falha": cfr["falhas"],
        "runs_sucesso": cfr["sucessos"],
        "cfr_ci": cfr["cfr"],
        "recuperacao_mediana_horas": recuperacao["mediana_horas"],
        "episodios_falha": recuperacao["episodios"],
        "episodios_completos": recuperacao["episodios_completos"],
        "episodios_censurados": recuperacao["episodios_censurados"],
        "episodios_censura_esquerda": recuperacao["episodios_censura_esquerda"],
        "proporcao_episodios_censurados": recuperacao["proporcao_censurados"],
    }
