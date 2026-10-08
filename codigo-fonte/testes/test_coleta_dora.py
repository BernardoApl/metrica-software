"""RQ80: coleta de workflows, releases e runs com um cliente REST falso."""

import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import unquote

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "coleta"))
import coleta_dora


def instante_do_filtro(valor, fim=False):
    """``AAAA-MM-DD`` (dia inteiro) ou ``AAAA-MM-DDTHH:MM:SS+00:00``, como a busca do GitHub."""
    if "T" not in valor:
        return datetime.fromisoformat(valor + ("T23:59:59+00:00" if fim else "T00:00:00+00:00"))
    return datetime.fromisoformat(valor)


def instante_do_run(run):
    return datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))


class ClienteFalso:
    """Simula a API: ``releases`` por repo e ``runs`` filtrados por ``created``."""

    def __init__(self, workflows=1, releases=(), runs=(), status=None, total_informado=None,
                 compares=None):
        self.workflows = workflows
        self.releases = list(releases)
        self.runs = list(runs)
        self.status = status or {}
        # Simula o total_count impreciso da API: funcao (total real) -> total informado.
        self.total_informado = total_informado or (lambda total: total)
        # (base, head) -> lista de commits no formato da API, ou um status HTTP de erro.
        # Pares nao configurados devolvem um compare vazio.
        self.compares = compares or {}
        self.chamadas = []

    def get(self, caminho, parametros=None, compactar=None):
        parametros = dict(parametros or {})
        self.chamadas.append((caminho, parametros))
        tipo = caminho.rsplit("/", 1)[-1]
        if tipo in self.status:
            return {"status": self.status[tipo], "corpo": None, "link": ""}
        pagina = parametros.get("page", 1)
        por_pagina = parametros.get("per_page", 30)
        if "/compare/" in caminho:
            base, head = unquote(caminho.split("/compare/", 1)[1]).split("...")
            commits = self.compares.get((base, head), [])
            if isinstance(commits, int):
                return {"status": commits, "corpo": None, "link": ""}
            itens = commits[(pagina - 1) * por_pagina: pagina * por_pagina]
            corpo = {"status": "ahead", "ahead_by": len(commits), "behind_by": 0,
                     "total_commits": len(commits), "commits": itens, "files": ["enorme"]}
            itens_total = len(commits)
        elif tipo == "workflows":
            corpo = {"total_count": self.workflows, "workflows": []}
            itens_total = 0
        elif tipo == "releases":
            itens = self.releases[(pagina - 1) * por_pagina: pagina * por_pagina]
            corpo, itens_total = itens, len(self.releases)
        else:
            de, ate = [instante_do_filtro(v, fim=i == 1)
                       for i, v in enumerate(parametros["created"].split(".."))]
            filtrados = [r for r in self.runs if de <= instante_do_run(r) <= ate]
            itens = filtrados[(pagina - 1) * por_pagina: pagina * por_pagina]
            corpo = {"total_count": self.total_informado(len(filtrados)), "workflow_runs": itens}
            itens_total = min(len(filtrados), 1000)
        link = ""
        if pagina * por_pagina < itens_total:
            link = '<proxima>; rel="next"'
        if compactar is not None:
            corpo = compactar(corpo)
        return {"status": 200, "corpo": corpo, "link": link, "_pagina": pagina,
                "_caminho": caminho, "_parametros": parametros}

    def paginar(self, caminho, parametros=None, compactar=None, max_paginas=None):
        parametros = dict(parametros or {})
        pagina = 1
        while True:
            resposta = self.get(caminho, dict(parametros, page=pagina), compactar)
            yield resposta
            if resposta["status"] != 200 or not resposta["link"]:
                return
            if max_paginas and pagina >= max_paginas:
                return
            pagina += 1


def commit_api(sha, data, mensagem="feat: algo"):
    """Um item de ``commits`` como o ``compare`` devolve (so os campos usados + extras)."""
    return {"sha": sha, "commit": {"author": {"name": "x", "date": data},
                                   "committer": {"date": data}, "message": mensagem},
            "author": {"login": "x"}, "parents": [{"sha": "pai"}]}


def release(tag, publicada, draft=False, prerelease=False):
    return {"id": hash(tag) & 0xFFFF, "tag_name": tag, "name": tag, "draft": draft,
            "prerelease": prerelease, "created_at": publicada, "published_at": publicada,
            "target_commitish": "main", "extra": "descartado"}


def run_em(dia, i, conclusao="success"):
    return {"id": i, "workflow_id": 1, "name": "CI", "event": "push", "head_branch": "main",
            "head_sha": "abc", "status": "completed", "conclusion": conclusao, "run_attempt": 1,
            "created_at": "%sT10:00:00Z" % dia, "run_started_at": "%sT10:00:00Z" % dia,
            "updated_at": "%sT10:05:00Z" % dia, "repository": {"enorme": True}}


def test_meses_da_janela_cobre_todos_os_dias_sem_sobreposicao():
    meses = coleta_dora.meses_da_janela("2025-10-15", "2026-02-10")
    assert meses == [
        (date(2025, 10, 15), date(2025, 10, 31)),
        (date(2025, 11, 1), date(2025, 11, 30)),
        (date(2025, 12, 1), date(2025, 12, 31)),
        (date(2026, 1, 1), date(2026, 1, 31)),
        (date(2026, 2, 1), date(2026, 2, 10)),
    ]
    assert len(coleta_dora.meses_da_janela("2025-10-01", "2026-09-30")) == 12


def test_limites_e_semanas_da_janela():
    abertura, fechamento = coleta_dora.limites_da_janela("2025-10-01", "2026-09-30")
    assert abertura == datetime(2025, 10, 1, tzinfo=timezone.utc)
    assert fechamento == datetime(2026, 9, 30, 23, 59, 59, tzinfo=timezone.utc)
    assert coleta_dora.semanas_da_janela("2025-10-01", "2026-09-30") == pytest.approx(365 / 7)
    with pytest.raises(ValueError):
        coleta_dora.limites_da_janela("2026-01-02", "2026-01-01")


def test_contar_workflows():
    assert coleta_dora.contar_workflows(ClienteFalso(workflows=0), "o/r") == {"status": 200, "total": 0}
    assert coleta_dora.contar_workflows(ClienteFalso(workflows=4), "o/r")["total"] == 4
    erro = ClienteFalso(status={"workflows": 404})
    assert coleta_dora.contar_workflows(erro, "o/r") == {"status": 404, "total": None}


def test_releases_percorre_todas_as_paginas_mesmo_anteriores_a_janela():
    novas = [release("v2.%d" % i, "2026-0%d-01T00:00:00Z" % (i + 1)) for i in range(5)]
    antigas = [release("v1.%d" % i, "2024-01-%02dT00:00:00Z" % (1 + i % 28)) for i in range(250)]
    cliente = ClienteFalso(releases=list(reversed(novas)) + antigas)
    resultado = coleta_dora.coletar_releases(cliente, "o/r", "2025-10-01", "2026-09-30")
    assert resultado["status"] == 200
    assert len(cliente.chamadas) == 3  # published_at pode nao seguir a ordem da listagem
    assert sum(r["dentro_janela"] for r in resultado["releases"]) == 5
    assert "extra" not in resultado["releases"][0]


def test_releases_validas_exclui_draft_prerelease_e_fora_da_janela():
    releases = [
        dict(release("ok", "2026-01-01T00:00:00Z"), dentro_janela=True),
        dict(release("rascunho", "2026-01-01T00:00:00Z", draft=True), dentro_janela=True),
        dict(release("rc", "2026-01-01T00:00:00Z", prerelease=True), dentro_janela=True),
        dict(release("velha", "2024-01-01T00:00:00Z"), dentro_janela=False),
        dict(release("sem-data", None), dentro_janela=True),
    ]
    assert [r["tag_name"] for r in coleta_dora.releases_validas(releases)] == ["ok"]
    assert len(coleta_dora.releases_validas(releases, incluir_prerelease=True)) == 2


def test_releases_com_erro_http():
    resultado = coleta_dora.coletar_releases(ClienteFalso(status={"releases": 404}), "o/r",
                                             "2025-10-01", "2026-09-30")
    assert resultado == {"status": 404, "releases": []}


def test_runs_mes_a_mes_com_subdivisao_quando_passa_do_teto():
    runs = [run_em("2026-01-%02d" % (1 + i % 28), i) for i in range(1500)]
    runs += [run_em("2026-02-03", 10_000 + i) for i in range(10)]
    cliente = ClienteFalso(runs=runs)
    resultado = coleta_dora.coletar_runs(cliente, "o/r", "main", "2026-01-01", "2026-02-28")
    assert len(resultado["runs"]) == 1510
    assert resultado["teto_atingido"] == []
    assert "repository" not in resultado["runs"][0]
    intervalos = {p["created"] for _, p in cliente.chamadas}
    assert "2026-01-01..2026-01-31" in intervalos
    assert "2026-01-01..2026-01-16" in intervalos  # janeiro foi dividido ao meio
    assert all(p["event"] == "push" and p["branch"] == "main" for _, p in cliente.chamadas)


def test_segundo_unico_acima_do_teto_e_registrado():
    # 1.200 runs no mesmo segundo: nao ha como dividir mais; a coleta fica incompleta.
    cliente = ClienteFalso(runs=[run_em("2026-01-05", i) for i in range(1200)])
    resultado = coleta_dora.coletar_runs(cliente, "o/r", "main", "2026-01-05", "2026-01-05")
    assert len(resultado["runs"]) == 1000
    assert resultado["teto_atingido"] == [{
        "intervalo": "2026-01-05T10:00:00+00:00..2026-01-05T10:00:00+00:00",
        "total_informado": 1200}]


def test_runs_com_erro_http_levantam_erro_de_coleta():
    with pytest.raises(coleta_dora.ErroColeta):
        coleta_dora.coletar_runs(ClienteFalso(status={"runs": 404}), "o/r", "main",
                                 "2026-01-01", "2026-01-31")


def test_total_de_runs_usa_uma_unica_chamada_barata():
    cliente = ClienteFalso(runs=[run_em("2026-01-05", i) for i in range(70)])
    assert coleta_dora.total_de_runs(cliente, "o/r", "main", "2025-10-01", "2026-09-30") == {
        "status": 200, "total": 70}
    assert cliente.chamadas[0][1]["per_page"] == 1
    erro = ClienteFalso(status={"runs": 403})
    assert coleta_dora.total_de_runs(erro, "o/r", "main", "2025-10-01", "2026-09-30")["total"] is None


def test_limite_operacional_interrompe_a_coleta():
    cliente = ClienteFalso(runs=[run_em("2026-01-%02d" % (1 + i % 28), i) for i in range(400)])
    with pytest.raises(coleta_dora.LimiteDeRunsExcedido):
        coleta_dora.coletar_runs(cliente, "o/r", "main", "2026-01-01", "2026-01-31", limite=250)
    paginas = [p for _, p in cliente.chamadas if "page" in p]
    assert len(paginas) == 3  # parou na pagina em que passou de 250, sem pedir a 4a
    assert len(coleta_dora.coletar_runs(cliente, "o/r", "main", "2026-01-01", "2026-01-31",
                                        limite=400)["runs"]) == 400
