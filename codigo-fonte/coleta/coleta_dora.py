"""RQ80: coleta de workflows, releases e workflow runs de um repositorio.

Endpoints (secao 4 do enunciado):

- ``GET /repos/{o}/{r}/actions/workflows`` -- ``total_count = 0`` indica que o
  repositorio nao usa Actions e ele e descartado antes das chamadas caras;
- ``GET /repos/{o}/{r}/releases`` -- campos ``draft``, ``prerelease``,
  ``published_at`` e ``tag_name``;
- ``GET /repos/{o}/{r}/actions/runs?branch=..&event=push&created=..`` -- a busca
  filtrada devolve no maximo 1.000 resultados, entao a janela e dividida em
  meses e, se um mes passar do teto, ele e subdividido ao meio ate caber. Um
  unico dia acima de 1.000 runs e registrado como ``teto_atingido``.

Atencao: em intervalos longos o ``total_count`` dessa busca satura (observado:
2.500 para um mes inteiro de um repositorio que tinha 1.332 runs em um unico
dia). Ele serve para decidir subdivisoes e para descartar quem tem poucos runs,
mas nao para estimar o volume de repositorios muito ativos; por isso o limite
operacional por repositorio e verificado durante a paginacao.

Todas as funcoes recebem o cliente REST por parametro (testes usam um falso).
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable, Optional

TETO_BUSCA = 1000
POR_PAGINA = 100

CAMPOS_RUN = ("id", "workflow_id", "name", "event", "head_branch", "head_sha", "status",
              "conclusion", "run_attempt", "created_at", "run_started_at", "updated_at")
CAMPOS_RELEASE = ("id", "tag_name", "name", "draft", "prerelease", "created_at",
                  "published_at", "target_commitish")


def para_data(valor) -> date:
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor)[:10])


def limites_da_janela(inicio, fim) -> tuple[datetime, datetime]:
    """Datas inclusivas -> instantes UTC (fim as 23:59:59)."""
    inicio, fim = para_data(inicio), para_data(fim)
    if fim < inicio:
        raise ValueError("Fim da janela anterior ao inicio.")
    return (datetime.combine(inicio, time.min, timezone.utc),
            datetime.combine(fim, time(23, 59, 59), timezone.utc))


def semanas_da_janela(inicio, fim) -> float:
    inicio, fim = para_data(inicio), para_data(fim)
    return ((fim - inicio).days + 1) / 7


def meses_da_janela(inicio, fim) -> list[tuple[date, date]]:
    """Divide ``[inicio, fim]`` (inclusivo) em intervalos de mes civil."""
    inicio, fim = para_data(inicio), para_data(fim)
    intervalos = []
    atual = inicio
    while atual <= fim:
        proximo_mes = (atual.replace(day=1) + timedelta(days=32)).replace(day=1)
        ultimo = min(fim, proximo_mes - timedelta(days=1))
        intervalos.append((atual, ultimo))
        atual = ultimo + timedelta(days=1)
    return intervalos


def _data_utc(texto: Optional[str]) -> Optional[datetime]:
    if not texto:
        return None
    return datetime.fromisoformat(texto.replace("Z", "+00:00")).astimezone(timezone.utc)


def compactar_runs(corpo: dict) -> dict:
    """Mantem so os campos usados; cada run original traz o repositorio inteiro."""
    return {
        "total_count": corpo.get("total_count"),
        "workflow_runs": [{campo: run.get(campo) for campo in CAMPOS_RUN}
                          for run in corpo.get("workflow_runs") or []],
    }


def compactar_releases(corpo: list) -> list:
    return [{campo: release.get(campo) for campo in CAMPOS_RELEASE} for release in corpo or []]


def compactar_workflows(corpo: dict) -> dict:
    return {"total_count": corpo.get("total_count"),
            "workflows": [{"id": w.get("id"), "name": w.get("name"), "path": w.get("path"),
                           "state": w.get("state")} for w in corpo.get("workflows") or []]}


def contar_workflows(cliente, nome: str) -> dict:
    pagina = cliente.get("/repos/%s/actions/workflows" % nome, {"per_page": 100},
                         compactar=compactar_workflows)
    if pagina["status"] != 200:
        return {"status": pagina["status"], "total": None}
    return {"status": 200, "total": pagina["corpo"].get("total_count") or 0}


def coletar_releases(cliente, nome: str, inicio, fim) -> dict:
    """Releases da janela + as anteriores da primeira pagina que passa do inicio.

    A listagem vem da mais nova para a mais antiga; a paginacao para depois de
    uma pagina inteira anterior a janela. Releases anteriores a janela sao
    mantidas (servem de base do ``compare`` no lead time), marcadas com
    ``dentro_janela = False``.
    """
    abertura, fechamento = limites_da_janela(inicio, fim)
    releases = []
    status = 200
    for pagina in cliente.paginar("/repos/%s/releases" % nome, {"per_page": POR_PAGINA},
                                  compactar=compactar_releases):
        status = pagina["status"]
        if status != 200:
            break
        itens = pagina["corpo"] or []
        antigas = 0
        for release in itens:
            data = _data_utc(release.get("published_at") or release.get("created_at"))
            release = dict(release, dentro_janela=bool(data and abertura <= data <= fechamento))
            releases.append(release)
            if data is not None and data < abertura:
                antigas += 1
        if itens and antigas == len(itens):
            break
    return {"status": status, "releases": releases}


def releases_validas(releases: Iterable[dict], incluir_prerelease: bool = False) -> list[dict]:
    """Definicao principal de deploy: publicada (``draft = false``) dentro da janela."""
    return [r for r in releases
            if r.get("dentro_janela") and not r.get("draft") and r.get("published_at")
            and (incluir_prerelease or not r.get("prerelease"))]


def _parametros_runs(branch: str, de: date, ate: date, por_pagina: int) -> dict:
    return {"branch": branch, "event": "push", "created": "%s..%s" % (de, ate),
            "per_page": por_pagina, "exclude_pull_requests": "true"}


def total_de_runs(cliente, nome: str, branch: str, inicio, fim) -> dict:
    """Uma chamada barata (``per_page=1``) que informa o total da janela inteira."""
    pagina = cliente.get("/repos/%s/actions/runs" % nome,
                         _parametros_runs(branch, para_data(inicio), para_data(fim), 1),
                         compactar=compactar_runs)
    if pagina["status"] != 200:
        return {"status": pagina["status"], "total": None}
    return {"status": 200, "total": pagina["corpo"].get("total_count") or 0}


class LimiteDeRunsExcedido(RuntimeError):
    """O repositorio tem mais runs na janela do que o limite operacional configurado."""


def _coletar_intervalo(cliente, nome, branch, de, ate, registros, avisos, limite=None):
    caminho = "/repos/%s/actions/runs" % nome
    parametros = _parametros_runs(branch, de, ate, POR_PAGINA)
    primeira = cliente.get(caminho, parametros, compactar=compactar_runs)
    if primeira["status"] != 200:
        raise ErroColeta("HTTP %s ao listar runs de %s (%s..%s)"
                         % (primeira["status"], nome, de, ate))
    total = primeira["corpo"].get("total_count") or 0
    if total > TETO_BUSCA and de < ate:
        meio = de + (ate - de) // 2
        _coletar_intervalo(cliente, nome, branch, de, meio, registros, avisos, limite)
        _coletar_intervalo(cliente, nome, branch, meio + timedelta(days=1), ate, registros, avisos,
                           limite)
        return
    if total > TETO_BUSCA:
        avisos.append({"intervalo": "%s..%s" % (de, ate), "total_informado": total})
    for pagina in cliente.paginar(caminho, parametros, compactar=compactar_runs,
                                  max_paginas=TETO_BUSCA // POR_PAGINA):
        if pagina["status"] != 200:
            raise ErroColeta("HTTP %s ao paginar runs de %s" % (pagina["status"], nome))
        for run in pagina["corpo"].get("workflow_runs") or []:
            registros[run["id"]] = run
        if limite is not None and len(registros) > limite:
            raise LimiteDeRunsExcedido("%s passou de %d runs na janela" % (nome, limite))


class ErroColeta(RuntimeError):
    """Resposta inesperada no meio da coleta de um repositorio."""


def coletar_runs(cliente, nome: str, branch: str, inicio, fim, limite: Optional[int] = None) -> dict:
    """Todos os runs de ``push`` no ``branch`` dentro da janela, mes a mes, sem duplicatas.

    :raises LimiteDeRunsExcedido: se ``limite`` for informado e ultrapassado.
    """
    registros: dict = {}
    avisos: list = []
    for de, ate in meses_da_janela(inicio, fim):
        _coletar_intervalo(cliente, nome, branch, de, ate, registros, avisos, limite)
    runs = sorted(registros.values(), key=lambda r: (r.get("created_at") or "", r["id"]))
    return {"runs": runs, "teto_atingido": avisos}
