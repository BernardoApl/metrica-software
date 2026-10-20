"""Pipeline com commits vindos do clone git: sem compare na API, com fallback e corte antecipado de runs."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import coleta_dora
import git_local
import pipeline_dora as pipeline
import rq82_amostra_final as rq82
from test_coleta_dora import ClienteFalso, commit_api
from test_pipeline_dora import candidato, releases_mensais, runs_alternados


class CloneFalso:
    """Substitui ``CloneLocal``: um commit de 5 dias antes de cada release, sem tocar no git."""

    def __init__(self, falha_no_compare=False):
        self.falha_no_compare = falha_no_compare
        self.fechado = False
        self.comparacoes = []

    def commits_entre(self, base, head):
        if self.falha_no_compare:
            raise git_local.ErroGit("git log falhou")
        self.comparacoes.append((base, head))
        return {"status": 200, "total_commits": 1, "truncado": False,
                "commits": [{"sha": "s-" + head, "data_autor": "2026-01-01T00:00:00Z",
                             "mensagem": "feat: x"}]}

    def tags(self):
        return {}

    def fechar(self):
        self.fechado = True


class FabricaFalsa:
    def __init__(self, clone=None, erro=None):
        self.clone, self.erro = clone, erro

    def abrir(self, nome):
        if self.erro:
            raise self.erro
        return self.clone


@pytest.fixture
def config(tmp_path):
    return pipeline._mesclar(pipeline.CONFIG_PADRAO, {
        "meta_repositorios": 1, "limite_runs_por_repositorio": 500,
        "diretorio_saida": str(tmp_path / "saida")})


def repositorio(**extra):
    compares = {("v1.%d" % (i - 1), "v1.%d" % i): [commit_api("api%d" % i, "2026-01-01T00:00:00Z")]
                for i in range(1, 6)}
    return ClienteFalso(releases=releases_mensais(6), runs=runs_alternados(80), compares=compares, **extra)


class Roteador:
    """Entrega ao ClienteFalso do repositorio e conta as chamadas a /compare/."""

    def __init__(self, falso):
        self.falso = falso

    def get(self, *a, **kw):
        return self.falso.get(*a, **kw)

    def paginar(self, *a, **kw):
        return self.falso.paginar(*a, **kw)

    @property
    def comparacoes_na_api(self):
        return [c for c, _ in self.falso.chamadas if "/compare/" in c]


def test_com_clone_nao_usa_compare_da_api_e_devolve_tags(config):
    cliente = Roteador(repositorio())
    clone = CloneFalso()
    avaliacao = pipeline.avaliar_repositorio(cliente, candidato("o/bom", 10), config,
                                             fabrica_git=FabricaFalsa(clone))
    assert avaliacao["motivo"] == pipeline.INCLUIDO
    assert avaliacao["metricas"]["fonte_commits"] == "git"
    assert cliente.comparacoes_na_api == []
    assert len(clone.comparacoes) == 5 and clone.fechado
    assert avaliacao["metricas"]["releases_com_lead_time"] == 5
    assert avaliacao["status_tags"] == 200 and avaliacao["tags"] == []
    assert {c["sha"] for c in avaliacao["commits"]} == {"s-v1.%d" % i for i in range(1, 6)}


def test_clone_que_nao_abre_cai_na_api(config):
    cliente = Roteador(repositorio())
    fabrica = FabricaFalsa(erro=git_local.ErroGit("timeout"))
    avaliacao = pipeline.avaliar_repositorio(cliente, candidato("o/bom", 10), config, fabrica_git=fabrica)
    assert avaliacao["metricas"]["fonte_commits"] == "api"
    assert len(cliente.comparacoes_na_api) == 5
    assert "tags" not in avaliacao  # a RQ82 busca as tags pela API


def test_erro_do_git_no_meio_refaz_o_repositorio_pela_api_e_fecha_o_clone(config):
    cliente = Roteador(repositorio())
    clone = CloneFalso(falha_no_compare=True)
    avaliacao = pipeline.avaliar_repositorio(cliente, candidato("o/bom", 10), config,
                                             fabrica_git=FabricaFalsa(clone))
    assert clone.fechado
    assert avaliacao["metricas"]["fonte_commits"] == "api"
    assert len(cliente.comparacoes_na_api) == 5 and "tags" not in avaliacao


def test_sem_fabrica_continua_igual(config):
    cliente = Roteador(repositorio())
    avaliacao = pipeline.avaliar_repositorio(cliente, candidato("o/bom", 10), config)
    assert avaliacao["metricas"]["fonte_commits"] == "api"
    assert len(cliente.comparacoes_na_api) == 5


def test_criar_fabrica_so_com_a_opcao_ligada(config):
    assert pipeline.criar_fabrica_git(config) is None
    ligada = pipeline.criar_fabrica_git(dict(config, commits_via_git=True))
    assert isinstance(ligada, git_local.FabricaClones)


def test_runs_acima_do_limite_abortam_sem_paginar():
    cliente = ClienteFalso(runs=runs_alternados(600))
    with pytest.raises(coleta_dora.LimiteDeRunsExcedido):
        coleta_dora.coletar_runs(cliente, "o/gigante", "main", "2025-10-01", "2026-09-30", limite=500)
    assert cliente.chamadas and all("page" not in p for _, p in cliente.chamadas)


def test_runs_dentro_do_limite_continuam_completos():
    cliente = ClienteFalso(runs=runs_alternados(300))
    coleta = coleta_dora.coletar_runs(cliente, "o/medio", "main", "2025-10-01", "2026-09-30", limite=500)
    assert len(coleta["runs"]) == 300


def test_falha_temporaria_da_api_nao_derruba_a_coleta_e_e_refeita(tmp_path, monkeypatch):
    config = pipeline._mesclar(pipeline.CONFIG_PADRAO, {
        "diretorio_checkpoints": str(tmp_path / "ck"), "diretorio_saida": str(tmp_path / "s")})
    candidatos = [candidato("o/r0", 10)]
    monkeypatch.setattr(pipeline, "avaliar_repositorio",
                        lambda *a: (_ for _ in ()).throw(rq82.ErroREST("HTTP 502")))
    resultado = rq82.criar_avaliador(config, candidatos)(None, candidatos[0], config)
    assert resultado["motivo"] == "inacessivel" and resultado["transitorio"]
    assert not list((tmp_path / "ck").rglob("*.json.gz"))  # nada reutilizavel foi gravado


def test_autenticacao_continua_interrompendo(tmp_path, monkeypatch):
    config = pipeline._mesclar(pipeline.CONFIG_PADRAO, {"diretorio_checkpoints": str(tmp_path / "ck")})
    candidatos = [candidato("o/r0", 10)]
    monkeypatch.setattr(pipeline, "avaliar_repositorio",
                        lambda *a: (_ for _ in ()).throw(rq82.ErroAutenticacaoREST("401")))
    with pytest.raises(rq82.ErroAutenticacaoREST):
        rq82.criar_avaliador(config, candidatos)(None, candidatos[0], config)


def test_passadas_repetem_ate_nao_haver_falha_temporaria(monkeypatch):
    respostas = [{"avaliacoes": [{"nome_completo": "o/a", "transitorio": True}]},
                 {"avaliacoes": [{"nome_completo": "o/a"}]}]
    esperas = []
    monkeypatch.setattr(pipeline, "executar", lambda *a, **kw: respostas.pop(0))
    monkeypatch.setattr(rq82, "criar_avaliador", lambda *a: None)
    resultado = rq82.executar_com_passadas(None, [], {}, passadas=3, espera=10, dormir=esperas.append)
    assert resultado == {"avaliacoes": [{"nome_completo": "o/a"}]} and esperas == [10]


def test_ultima_passada_devolve_mesmo_com_falha_e_a_auditoria_acusa(tmp_path, monkeypatch):
    resultado = {"avaliacoes": [{"nome_completo": "o/a", "motivo": "inacessivel",
                                 "transitorio": True, "erro": "HTTP 502"}],
                 "amostra": [], "funil": [{"aprovados": 0}]}
    monkeypatch.setattr(pipeline, "executar", lambda *a, **kw: resultado)
    monkeypatch.setattr(rq82, "criar_avaliador", lambda *a: None)
    assert rq82.executar_com_passadas(None, [], {}, passadas=2, espera=0, dormir=lambda _: None) is resultado
    config = pipeline._mesclar(pipeline.CONFIG_PADRAO, {"meta_repositorios": 300, "janela_confirmada": True})
    motivos = {p["motivo"] for p in rq82.validar_amostra(resultado, config)["pendencias"]}
    assert "falha_temporaria_persistente" in motivos
