"""RQ80: coleta de workflows, releases e workflow runs de um repositorio.

Endpoints (secao 4 do enunciado):

- ``GET /repos/{o}/{r}/actions/workflows`` -- ``total_count = 0`` indica que o
  repositorio nao usa Actions e ele e descartado antes das chamadas caras;
- ``GET /repos/{o}/{r}/releases`` -- campos ``draft``, ``prerelease``,
  ``published_at`` e ``tag_name``;
- ``GET /repos/{o}/{r}/actions/runs?branch=..&event=push&created=..`` -- a busca
  filtrada devolve no maximo 1.000 resultados, entao a janela e dividida em
  meses e, se um mes passar do teto, ele e subdividido ao meio ate caber.

Atencao: em intervalos longos o ``total_count`` dessa busca satura (observado:
2.500 para um mes inteiro de um repositorio que tinha 1.332 runs em um unico
dia). Ele serve para decidir subdivisoes e para descartar quem tem poucos runs,
mas nao para estimar o volume de repositorios muito ativos; por isso o limite
operacional por repositorio e verificado durante a paginacao.

RQ77: o ``total_count`` tambem nao basta para detectar o teto. Na coleta da
S01, ``angular/angular`` teve exatamente 1.000 runs em 2026-04, enquanto os
meses vizinhos tinham 1.084 a 2.160: o total informado nao passou de 1.000, a
paginacao parou na 10a pagina e o resto do mes se perdeu sem aviso. Agora um
intervalo tambem e subdividido quando a paginacao devolve 1.000 runs. Um dia
inteiro acima do teto e dividido em horas, minutos e segundos (``created``
aceita data e hora); so um intervalo de um segundo acima do teto fica em
``teto_atingido``. Intervalos de dias inteiros mantem a URL ``AAAA-MM-DD..``,
entao o cache de coletas anteriores continua valendo. Cada consulta fica em
``intervalos`` para auditoria (``intervalos_runs.csv``).

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


UM_SEGUNDO = timedelta(seconds=1)
FIM_DO_DIA = time(23, 59, 59)


def _instante(dia, fim: bool = False) -> datetime:
    """``dia`` as 00:00:00 UTC, ou as 23:59:59 UTC com ``fim=True``."""
    return datetime.combine(para_data(dia), FIM_DO_DIA if fim else time.min, timezone.utc)


def _dias_inteiros(de: datetime, ate: datetime) -> bool:
    return de.time() == time.min and ate.time() == FIM_DO_DIA


def formatar_intervalo(de: datetime, ate: datetime) -> str:
    """Valor de ``created``: ``AAAA-MM-DD..AAAA-MM-DD`` para dias inteiros, senao data e hora UTC.

    Os dois extremos sao inclusivos, com resolucao de um segundo.
    """
    if _dias_inteiros(de, ate):
        return "%s..%s" % (de.date(), ate.date())
    formato = "%Y-%m-%dT%H:%M:%S+00:00"
    return "%s..%s" % (de.strftime(formato), ate.strftime(formato))


def dividir_intervalo(de: datetime, ate: datetime) -> Optional[tuple]:
    """Divide ``[de, ate]`` em duas metades sem sobreposicao, ou ``None`` se for um segundo so.

    Varios dias inteiros sao divididos por dia (mesmas URLs da coleta da S01,
    que ficam no cache); um dia ou menos e dividido por segundo.
    """
    if de >= ate:
        return None
    dias = (ate.date() - de.date()).days
    if _dias_inteiros(de, ate) and dias >= 1:
        meio = de.date() + timedelta(days=dias // 2)
        return (de, _instante(meio, fim=True)), (_instante(meio + timedelta(days=1)), ate)
    meio = (de + (ate - de) // 2).replace(microsecond=0)
    return (de, meio), (meio + UM_SEGUNDO, ate)


def _parametros_runs(branch: str, de: datetime, ate: datetime, por_pagina: int) -> dict:
    return {"branch": branch, "event": "push", "created": formatar_intervalo(de, ate),
            "per_page": por_pagina, "exclude_pull_requests": "true"}


def total_de_runs(cliente, nome: str, branch: str, inicio, fim) -> dict:
    """Uma chamada barata (``per_page=1``) que informa o total da janela inteira."""
    pagina = cliente.get("/repos/%s/actions/runs" % nome,
                         _parametros_runs(branch, _instante(inicio), _instante(fim, fim=True), 1),
                         compactar=compactar_runs)
    if pagina["status"] != 200:
        return {"status": pagina["status"], "total": None}
    return {"status": 200, "total": pagina["corpo"].get("total_count") or 0}


class LimiteDeRunsExcedido(RuntimeError):
    """O repositorio tem mais runs na janela do que o limite operacional configurado."""


def _coletar_intervalo(cliente, nome, branch, de, ate, registros, intervalos, avisos, limite=None):
    """Coleta ``[de, ate]``, subdividindo se o total informado OU o coletado chegar ao teto."""
    caminho = "/repos/%s/actions/runs" % nome
    parametros = _parametros_runs(branch, de, ate, POR_PAGINA)
    primeira = cliente.get(caminho, parametros, compactar=compactar_runs)
    if primeira["status"] != 200:
        raise ErroColeta("HTTP %s ao listar runs de %s (%s)"
                         % (primeira["status"], nome, parametros["created"]))
    total = primeira["corpo"].get("total_count") or 0
    metades = dividir_intervalo(de, ate)
    registro = {"intervalo": parametros["created"], "total_informado": total,
                "coletados": None, "subdividido": False}
    intervalos.append(registro)

    def subdividir():
        registro["subdividido"] = True
        for metade_de, metade_ate in metades:
            _coletar_intervalo(cliente, nome, branch, metade_de, metade_ate, registros,
                               intervalos, avisos, limite)

    if total > TETO_BUSCA and metades:
        subdividir()
        return
    coletados = 0
    for pagina in cliente.paginar(caminho, parametros, compactar=compactar_runs,
                                  max_paginas=TETO_BUSCA // POR_PAGINA):
        if pagina["status"] != 200:
            raise ErroColeta("HTTP %s ao paginar runs de %s" % (pagina["status"], nome))
        itens = pagina["corpo"].get("workflow_runs") or []
        coletados += len(itens)
        for run in itens:
            registros[run["id"]] = run
        if limite is not None and len(registros) > limite:
            raise LimiteDeRunsExcedido("%s passou de %d runs na janela" % (nome, limite))
    registro["coletados"] = coletados
    if coletados >= TETO_BUSCA and metades:
        # total_count disse que cabia, mas a paginacao bateu no teto: pode haver mais.
        subdividir()
        return
    if total > TETO_BUSCA or coletados >= TETO_BUSCA:
        avisos.append({"intervalo": parametros["created"], "total_informado": total})


class ErroColeta(RuntimeError):
    """Resposta inesperada no meio da coleta de um repositorio."""


def coletar_runs(cliente, nome: str, branch: str, inicio, fim, limite: Optional[int] = None) -> dict:
    """Todos os runs de ``push`` no ``branch`` dentro da janela, mes a mes, sem duplicatas.

    Devolve ``runs`` (por ``created_at``), ``teto_atingido`` (intervalos de um
    segundo ainda acima do teto, ou seja, coleta incompleta) e ``intervalos``
    (cada consulta feita, com total informado, runs coletados e se foi
    subdividida).

    :raises LimiteDeRunsExcedido: se ``limite`` for informado e ultrapassado.
    """
    registros: dict = {}
    intervalos: list = []
    avisos: list = []
    for de, ate in meses_da_janela(inicio, fim):
        _coletar_intervalo(cliente, nome, branch, _instante(de), _instante(ate, fim=True),
                           registros, intervalos, avisos, limite)
    runs = sorted(registros.values(), key=lambda r: (r.get("created_at") or "", r["id"]))
    return {"runs": runs, "teto_atingido": avisos, "intervalos": intervalos}
