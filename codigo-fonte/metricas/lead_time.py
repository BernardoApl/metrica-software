"""RQ76: lead time for changes (RQ 02), nas duas variantes obrigatorias.

Definicao operacional (secao 5 do enunciado):

- para cada release R publicada na janela, os commits incluidos nela sao os do
  ``compare/{release anterior}...{R}``. A release anterior pode estar fora da
  janela; se nao existe (R e a primeira da historia), R e ignorada;
- data de R = ``published_at``; data do commit = ``commit.author.date``;
- **(a) por release:** lead time de R = data de R - commit mais antigo de R; o
  valor do repositorio e a mediana entre as releases;
- **(b) por commit:** cada commit de R contribui com data de R - data dele; o
  valor do repositorio e a mediana de todos os commits de todas as releases.

Decisoes do grupo (vao para a Metodologia):

- "release anterior" segue a mesma definicao de deploy: a release publicada
  (nao draft, nao pre-release) imediatamente anterior por ``published_at``;
- release sem commits novos (``compare`` vazio, ex.: a mesma tag republicada)
  nao tem lead time e fica fora das duas variantes, mas e contada;
- ``compare`` indisponivel (404 por tag apagada/reescrita, 422 etc.) e contado
  e a release e ignorada, como pede o FAQ do enunciado;
- commit com data de autoria **posterior** a publicacao da release (relogio
  errado, tag movida depois da publicacao) daria lead time negativo: ele e
  descartado das duas variantes e contado em ``commits_negativos``.

Todas as funcoes sao puras: recebem releases e datas ja coletadas.
"""

from __future__ import annotations

from datetime import datetime
from statistics import median
from typing import Iterable, Optional

from metricas.ci import data_utc

SEGUNDOS_POR_DIA = 86400

#: Motivos pelos quais uma release da janela fica sem lead time.
SEM_ANTERIOR = "sem_release_anterior"
SEM_COMMITS = "sem_commits_novos"
COMPARE_INDISPONIVEL = "compare_indisponivel"


def _publicada(release: dict) -> Optional[datetime]:
    valor = release.get("published_at")
    return data_utc(valor) if valor else None


def e_deploy(release: dict, incluir_prerelease: bool = False) -> bool:
    """Release publicada (``draft = false``, com ``published_at``); pre-release so se pedido."""
    return (not release.get("draft") and _publicada(release) is not None
            and (incluir_prerelease or not release.get("prerelease")))


def pares_de_releases(releases: Iterable[dict], incluir_prerelease: bool = False) -> list[tuple]:
    """``(anterior, R)`` para cada deploy R dentro da janela, em ordem cronologica.

    ``anterior`` e o deploy imediatamente anterior a R (pode estar fora da
    janela) ou ``None`` se R e o primeiro deploy conhecido. Empates de
    ``published_at`` sao desfeitos pelo ``id`` da release.
    """
    deploys = sorted((r for r in releases if e_deploy(r, incluir_prerelease)),
                     key=lambda r: (_publicada(r), r.get("id") or 0))
    pares = []
    for posicao, release in enumerate(deploys):
        if release.get("dentro_janela"):
            pares.append((deploys[posicao - 1] if posicao else None, release))
    return pares


def _dias(inicio: datetime, fim: datetime) -> float:
    return (fim - inicio).total_seconds() / SEGUNDOS_POR_DIA


def lead_times_dos_commits(data_release, datas_commits: Iterable) -> list[float]:
    """Variante (b) de uma release: ``data_release - data`` de cada commit, em dias.

    Valores negativos sao mantidos aqui; quem agrega decide descarta-los.
    """
    data_release = data_utc(data_release)
    return [_dias(data_utc(data), data_release) for data in datas_commits]


def lead_time_da_release(data_release, datas_commits: Iterable) -> Optional[float]:
    """Variante (a) de uma release: ``data_release - commit mais antigo``, em dias.

    ``None`` se a release nao tem commits (nao negativos).
    """
    validos = [dias for dias in lead_times_dos_commits(data_release, datas_commits) if dias >= 0]
    return max(validos) if validos else None


def avaliar_release(release: dict, anterior: Optional[dict], compare: Optional[dict]) -> dict:
    """Lead time de uma release a partir do resultado do ``compare``.

    :param compare: ``{"status": int, "commits": [{"data_autor": ...}, ...],
        "truncado": bool}`` ou ``None`` se nao houve compare (sem anterior).
    """
    resultado = {"tag_name": release.get("tag_name"), "published_at": release.get("published_at"),
                 "anterior": anterior.get("tag_name") if anterior else None,
                 "commits": 0, "commits_negativos": 0, "truncado": False,
                 "lead_time_dias": None, "lead_times_commits": [], "motivo": None}
    if anterior is None:
        return dict(resultado, motivo=SEM_ANTERIOR)
    if compare is None or compare.get("status") != 200:
        return dict(resultado, motivo=COMPARE_INDISPONIVEL)
    datas = [c["data_autor"] for c in compare.get("commits") or [] if c.get("data_autor")]
    todos = lead_times_dos_commits(release["published_at"], datas)
    validos = [dias for dias in todos if dias >= 0]
    resultado.update(commits=len(todos), commits_negativos=len(todos) - len(validos),
                     truncado=bool(compare.get("truncado")), lead_times_commits=validos)
    if not validos:
        return dict(resultado, motivo=SEM_COMMITS)
    return dict(resultado, lead_time_dias=max(validos))


def metricas_lead_time(avaliacoes: Iterable[dict]) -> dict:
    """Resume as releases avaliadas de um repositorio (saida de :func:`avaliar_release`)."""
    avaliacoes = list(avaliacoes)
    por_release = [a["lead_time_dias"] for a in avaliacoes if a["lead_time_dias"] is not None]
    por_commit = [dias for a in avaliacoes for dias in a["lead_times_commits"]]

    def contar(motivo):
        return sum(1 for a in avaliacoes if a["motivo"] == motivo)

    return {
        "lead_time_release_mediana_dias": median(por_release) if por_release else None,
        "lead_time_commit_mediana_dias": median(por_commit) if por_commit else None,
        "releases_com_lead_time": len(por_release),
        "commits_com_lead_time": len(por_commit),
        "releases_sem_anterior": contar(SEM_ANTERIOR),
        "releases_sem_commits": contar(SEM_COMMITS),
        "releases_compare_indisponivel": contar(COMPARE_INDISPONIVEL),
        "releases_compare_truncado": sum(1 for a in avaliacoes if a["truncado"]),
        "commits_negativos": sum(a["commits_negativos"] for a in avaliacoes),
    }
