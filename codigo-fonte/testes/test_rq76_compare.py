"""RQ76: coleta do compare entre releases e lead time no pipeline (sem rede)."""

import csv
import gzip
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "coleta"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import coleta_dora
import pipeline_dora
from cliente_rest import ErroREST
from test_coleta_dora import ClienteFalso, commit_api, release
from test_pipeline_dora import ClientePorRepositorio, candidato, config, runs_alternados  # noqa: F401


def commits_diarios(quantidade, mes="2026-02", prefixo="c"):
    return [commit_api("%s%d" % (prefixo, i), "%s-%02dT12:00:00Z" % (mes, 1 + i % 28),
                       "fix: corrige %d\n\ncorpo longo que nao vai para o cache" % i)
            for i in range(quantidade)]


# ------------------------------------------------------------------- coleta
def test_compactar_compare_guarda_so_o_necessario():
    corpo = {"status": "ahead", "ahead_by": 1, "behind_by": 0, "total_commits": 1,
             "commits": [commit_api("abc", "2026-01-01T00:00:00Z", "fix: x\n\ncorpo")],
             "files": [{"patch": "enorme"}], "base_commit": {"sha": "b"}}
    assert coleta_dora.compactar_compare(corpo) == {
        "status": "ahead", "ahead_by": 1, "behind_by": 0, "total_commits": 1,
        "commits": [{"sha": "abc", "data_autor": "2026-01-01T00:00:00Z", "mensagem": "fix: x"}]}


def test_compactar_compare_com_mensagem_vazia_e_longa():
    corpo = {"commits": [commit_api("a", "2026-01-01T00:00:00Z", ""),
                         commit_api("b", "2026-01-01T00:00:00Z", "x" * 500)]}
    commits = coleta_dora.compactar_compare(corpo)["commits"]
    assert commits[0]["mensagem"] == ""
    assert len(commits[1]["mensagem"]) == coleta_dora.TAMANHO_MENSAGEM


@pytest.mark.parametrize("base, head, esperado", [
    ("v1.0", "v1.1", "/repos/o/r/compare/v1.0...v1.1"),
    ("@scope/pkg@1.0.0", "@scope/pkg@1.1.0", "/repos/o/r/compare/@scope/pkg@1.0.0...@scope/pkg@1.1.0"),
    ("v1 beta", "v1+build#2", "/repos/o/r/compare/v1%20beta...v1%2Bbuild%232"),
])
def test_caminho_compare_escapa_tags(base, head, esperado):
    assert coleta_dora.caminho_compare("o/r", base, head) == esperado


def test_compare_pagina_alem_de_250_commits():
    cliente = ClienteFalso(compares={("v1", "v2"): commits_diarios(320)})
    resultado = coleta_dora.coletar_compare(cliente, "o/r", "v1", "v2")
    assert resultado["status"] == 200
    assert resultado["total_commits"] == 320
    assert len(resultado["commits"]) == 320
    assert resultado["truncado"] is False
    assert [p["page"] for _, p in cliente.chamadas] == [1, 2, 3, 4]
    assert all(p["per_page"] == 100 for _, p in cliente.chamadas)
    assert resultado["commits"][0]["mensagem"] == "fix: corrige 0"


def test_compare_acima_do_limite_de_paginas_fica_truncado():
    cliente = ClienteFalso(compares={("v1", "v2"): commits_diarios(320)})
    resultado = coleta_dora.coletar_compare(cliente, "o/r", "v1", "v2", max_paginas=2)
    assert len(resultado["commits"]) == 200
    assert resultado["truncado"] is True


def test_compare_404_de_tag_apagada():
    cliente = ClienteFalso(compares={("sumiu", "v2"): 404})
    assert coleta_dora.coletar_compare(cliente, "o/r", "sumiu", "v2") == {
        "status": 404, "total_commits": None, "commits": [], "truncado": False}


def test_compare_que_falha_no_meio_mantem_o_que_veio_e_marca_truncado():
    class FalhaNaSegundaPagina(ClienteFalso):
        def get(self, caminho, parametros=None, compactar=None):
            if (parametros or {}).get("page") == 2:
                return {"status": 500, "corpo": None, "link": ""}
            return super().get(caminho, parametros, compactar)

    resultado = coleta_dora.coletar_compare(
        FalhaNaSegundaPagina(compares={("v1", "v2"): commits_diarios(150)}), "o/r", "v1", "v2")
    assert resultado["status"] == 200
    assert len(resultado["commits"]) == 100
    assert resultado["truncado"] is True


def test_compare_vazio_e_commits_repetidos():
    cliente = ClienteFalso()
    assert coleta_dora.coletar_compare(cliente, "o/r", "v1", "v1")["commits"] == []
    repetidos = [commit_api("a", "2026-01-01T00:00:00Z")] * 2
    resultado = coleta_dora.coletar_compare(ClienteFalso(compares={("v1", "v2"): repetidos}),
                                            "o/r", "v1", "v2")
    assert [c["sha"] for c in resultado["commits"]] == ["a"]


# ----------------------------------------------------------------- pipeline
@pytest.fixture
def repositorio_com_lead_time():
    """``v0`` antes da janela e ``v1``..``v6`` na janela, uma por mes (dia 15).

    Cada release tem 2 commits, dos dias 13 e 14 do mes -> lead times 2 e 1 dia;
    (a) = 2 dias em todas, (b) = mediana de [2, 1] * 6 = 1,5. Excecoes:
    ``v3`` tem compare 404 e ``v5`` nao tem commits novos.
    """
    releases = [release("v%d" % i, "2026-%02d-15T12:00:00Z" % i) for i in range(6, 0, -1)]
    releases.append(release("v0", "2025-06-15T12:00:00Z"))
    compares = {}
    for i in range(1, 7):
        mes = "2026-%02d" % i
        compares[("v%d" % (i - 1), "v%d" % i)] = [
            commit_api("a%d" % i, mes + "-13T12:00:00Z"),
            commit_api("b%d" % i, mes + "-14T12:00:00Z", "revert: desfaz")]
    compares[("v2", "v3")] = 404
    compares[("v4", "v5")] = []
    return ClienteFalso(releases=releases, runs=runs_alternados(80), compares=compares)


def test_pipeline_calcula_lead_time_e_classe_geral(repositorio_com_lead_time, config):  # noqa: F811
    cliente = ClientePorRepositorio({"o/lead": repositorio_com_lead_time})
    resultado = pipeline_dora.executar(cliente, [candidato("o/lead", 10)],
                                       dict(config, meta_repositorios=1), registrar=lambda _: None)
    linha = resultado["amostra"][0]
    assert linha["lead_time_release_mediana_dias"] == pytest.approx(2)
    assert linha["lead_time_commit_mediana_dias"] == pytest.approx(1.5)
    assert linha["releases_com_lead_time"] == 4
    assert linha["commits_com_lead_time"] == 8
    assert linha["releases_sem_anterior"] == 0  # v0 fora da janela serve de base para v1
    assert linha["releases_compare_indisponivel"] == 1
    assert linha["releases_sem_commits"] == 1
    assert linha["classe_lead_time"] == "High"
    # frequencia Low, lead time High, CFR High (25%), recuperacao: ver test_pipeline_dora.
    assert linha["classe_geral"] is not None


def test_pipeline_exporta_lead_time_por_release_e_commits(repositorio_com_lead_time, config):  # noqa: F811
    cliente = ClientePorRepositorio({"o/lead": repositorio_com_lead_time})
    config = dict(config, meta_repositorios=1)
    resultado = pipeline_dora.executar(cliente, [candidato("o/lead", 10)], config,
                                       registrar=lambda _: None)
    saida = pipeline_dora.exportar(resultado, config, cliente)
    with (saida / "lead_time_releases.csv").open(encoding="utf-8") as arquivo:
        releases = list(csv.DictReader(arquivo))
    assert tuple(releases[0]) == pipeline_dora.COLUNAS_LEAD_TIME
    assert [r["tag_name"] for r in releases] == ["v1", "v2", "v3", "v4", "v5", "v6"]
    assert {r["tag_name"]: r["motivo"] for r in releases if r["motivo"]} == {
        "v3": "compare_indisponivel", "v5": "sem_commits_novos"}
    assert releases[0]["anterior"] == "v0"
    with gzip.open(saida / "commits_releases.csv.gz", "rt", encoding="utf-8") as arquivo:
        commits = list(csv.DictReader(arquivo))
    assert tuple(commits[0]) == pipeline_dora.COLUNAS_COMMITS
    assert len(commits) == 8
    assert {c["mensagem"] for c in commits} == {"feat: algo", "revert: desfaz"}
    with (saida / "metricas_repositorios.csv").open(encoding="utf-8") as arquivo:
        assert float(next(csv.DictReader(arquivo))["lead_time_release_mediana_dias"]) == 2


def test_erro_persistente_no_compare_nao_derruba_o_repositorio(repositorio_com_lead_time, config):  # noqa: F811
    class CompareQuebrado(ClientePorRepositorio):
        def paginar(self, caminho, parametros=None, compactar=None, max_paginas=None):
            if "/compare/" in caminho and caminho.endswith("...v4"):
                raise ErroREST("HTTP 502 persistente")
            return super().paginar(caminho, parametros, compactar, max_paginas)

    cliente = CompareQuebrado({"o/lead": repositorio_com_lead_time})
    resultado = pipeline_dora.executar(cliente, [candidato("o/lead", 10)],
                                       dict(config, meta_repositorios=1), registrar=lambda _: None)
    linha = resultado["amostra"][0]
    assert linha["releases_compare_indisponivel"] == 2  # v3 (404) e v4 (502)
    assert linha["releases_com_lead_time"] == 3


def test_limite_de_paginas_do_compare_vem_da_config(repositorio_com_lead_time, config):  # noqa: F811
    repositorio_com_lead_time.compares[("v0", "v1")] = commits_diarios(250, mes="2026-01")
    cliente = ClientePorRepositorio({"o/lead": repositorio_com_lead_time})
    resultado = pipeline_dora.executar(
        cliente, [candidato("o/lead", 10)],
        dict(config, meta_repositorios=1, limite_paginas_compare=2), registrar=lambda _: None)
    assert resultado["amostra"][0]["releases_compare_truncado"] == 1
    v1 = next(r for r in resultado["lead_time"] if r["tag_name"] == "v1")
    assert v1["commits"] == 200
