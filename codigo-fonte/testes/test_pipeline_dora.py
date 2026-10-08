"""RQ80: integracao do pipeline (selecao, funil, metricas, exportacao) sem rede."""

import csv
import gzip
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline_dora
from test_coleta_dora import ClienteFalso, release, run_em


class ClientePorRepositorio:
    """Encaminha cada chamada ao ClienteFalso do repositorio da URL."""

    def __init__(self, repositorios):
        self.repositorios = repositorios
        self.requisicoes = 0
        self.acertos_cache = 0

    def _alvo(self, caminho):
        partes = caminho.split("/")
        return self.repositorios["%s/%s" % (partes[2], partes[3])]

    def get(self, caminho, parametros=None, compactar=None):
        self.requisicoes += 1
        return self._alvo(caminho).get(caminho, parametros, compactar)

    def paginar(self, caminho, parametros=None, compactar=None, max_paginas=None):
        return self._alvo(caminho).paginar(caminho, parametros, compactar, max_paginas)


def candidato(nome, estrelas, **extra):
    base = {"nome_completo": nome, "url": "https://github.com/" + nome, "estrelas": str(estrelas),
            "status_metadados": "ok", "fork": "False", "arquivado": "False",
            "desabilitado": "False", "vazio": "False", "branch_padrao": "main",
            "linguagem": "Python", "criado_em": "2020-01-01T00:00:00Z", "idade_anos": "6.7",
            "contribuidores_total": "10"}
    base.update(extra)
    return base


def releases_mensais(n):
    return [release("v1.%d" % i, "2026-%02d-15T12:00:00Z" % (i + 1)) for i in reversed(range(n))]


def runs_alternados(n, padrao=("success", "failure", "success", "success")):
    """Um run por hora a partir de 01/01, repetindo ``padrao`` de conclusoes."""
    runs = []
    for i in range(n):
        run = run_em("2026-01-%02d" % (1 + i // 24), i, padrao[i % len(padrao)])
        for campo in ("created_at", "run_started_at", "updated_at"):
            run[campo] = run[campo].replace("T10:", "T%02d:" % (i % 24))
        runs.append(run)
    return runs


@pytest.fixture
def config(tmp_path):
    return pipeline_dora._mesclar(pipeline_dora.CONFIG_PADRAO, {
        "meta_repositorios": 2,
        "trabalhadores": 2,
        "limite_runs_por_repositorio": 500,
        "diretorio_saida": str(tmp_path / "saida"),
    })


@pytest.fixture
def cenario():
    repositorios = {
        "o/bom": ClienteFalso(releases=releases_mensais(6), runs=runs_alternados(80)),
        "o/sem-actions": ClienteFalso(workflows=0),
        "o/poucas-releases": ClienteFalso(releases=releases_mensais(3), runs=runs_alternados(80)),
        "o/poucos-runs": ClienteFalso(releases=releases_mensais(6), runs=runs_alternados(20)),
        "o/gigante": ClienteFalso(releases=releases_mensais(6), runs=runs_alternados(600)),
        "o/bloqueado": ClienteFalso(status={"workflows": 451}),
        "o/cancelados": ClienteFalso(releases=releases_mensais(6),
                                     runs=runs_alternados(80, ("success", "cancelled", "cancelled"))),
        "o/tambem-bom": ClienteFalso(releases=releases_mensais(9), runs=runs_alternados(60)),
        "o/nunca-avaliado": ClienteFalso(releases=releases_mensais(9), runs=runs_alternados(60)),
    }
    candidatos = [candidato(nome, 1000 - i) for i, nome in enumerate(repositorios)]
    candidatos += [candidato("o/fork", 5000, fork="True"),
                   candidato("o/arquivado", 4000, arquivado="True"),
                   candidato("o/sem-branch", 3000, branch_padrao=""),
                   candidato("o/sem-metadados", 2000, status_metadados="erro")]
    return ClientePorRepositorio(repositorios), candidatos


def test_pre_filtro():
    assert pipeline_dora.motivo_pre_filtro(candidato("o/a", 1)) is None
    assert pipeline_dora.motivo_pre_filtro(candidato("o/a", 1, fork="True")) == "fork"
    assert pipeline_dora.motivo_pre_filtro(candidato("o/a", 1, vazio="True")) == "arquivado_ou_desabilitado"
    assert pipeline_dora.motivo_pre_filtro(candidato("o/a", 1, branch_padrao=" ")) == "sem_default_branch"
    assert pipeline_dora.motivo_pre_filtro(candidato("o/a", 1, status_metadados="x")) == "metadados_indisponiveis"


def test_executar_seleciona_em_ordem_de_estrelas_e_monta_funil(cenario, config):
    cliente, candidatos = cenario
    resultado = pipeline_dora.executar(cliente, candidatos, config, registrar=lambda _: None)
    assert [r["nome_completo"] for r in resultado["amostra"]] == ["o/bom", "o/tambem-bom"]
    motivos = {a["nome_completo"]: a["motivo"] for a in resultado["avaliacoes"]}
    assert motivos == {
        "o/bom": "incluido", "o/sem-actions": "sem_actions",
        "o/poucas-releases": "poucas_releases", "o/poucos-runs": "poucos_runs",
        "o/gigante": "runs_acima_do_limite", "o/bloqueado": "inacessivel",
        "o/cancelados": "poucos_runs", "o/tambem-bom": "incluido",
    }
    funil = {e["etapa"]: (e["entrada"], e["removidos_na_etapa"], e["aprovados"])
             for e in resultado["funil"]}
    assert funil == {
        "candidatos_iniciais": (13, 0, 13),
        "metadados_validos_e_ativos": (13, 4, 9),
        "avaliados_ate_a_meta": (9, 1, 8),
        "api_acessivel": (8, 1, 7),
        "usa_github_actions": (7, 1, 6),
        "minimo_releases": (6, 1, 5),
        "limite_operacional_runs": (5, 1, 4),
        "minimo_runs": (4, 2, 2),
    }


def test_metricas_da_amostra(cenario, config):
    cliente, candidatos = cenario
    resultado = pipeline_dora.executar(cliente, candidatos, config, registrar=lambda _: None)
    bom = resultado["amostra"][0]
    assert bom["releases_janela"] == 6
    assert bom["frequencia_deploy_semana"] == pytest.approx(6 / (365 / 7))
    assert bom["runs_validos"] == 80
    assert bom["cfr_ci"] == pytest.approx(0.25)
    assert bom["classe_frequencia"] == "Low"
    assert bom["classe_cfr"] == "High"
    assert bom["episodios_falha"] == 20
    assert {r["nome_completo"] for r in resultado["runs"]} == {"o/bom", "o/tambem-bom"}
    assert len(resultado["releases"]) == 6 + 9


def test_resultado_paralelo_igual_ao_sequencial(cenario, config):
    cliente, candidatos = cenario
    paralelo = pipeline_dora.executar(cliente, candidatos, config, registrar=lambda _: None)
    sequencial = pipeline_dora.executar(cliente, candidatos, dict(config, trabalhadores=1),
                                        registrar=lambda _: None)
    assert paralelo["funil"] == sequencial["funil"]
    assert paralelo["amostra"] == sequencial["amostra"]


def test_exportar_gera_csvs_e_resumo(cenario, config):
    cliente, candidatos = cenario
    resultado = pipeline_dora.executar(cliente, candidatos, config, registrar=lambda _: None)
    saida = pipeline_dora.exportar(resultado, config, cliente)
    with (saida / "metricas_repositorios.csv").open(encoding="utf-8") as arquivo:
        linhas = list(csv.DictReader(arquivo))
    assert [l["nome_completo"] for l in linhas] == ["o/bom", "o/tambem-bom"]
    assert tuple(linhas[0]) == pipeline_dora.COLUNAS_METRICAS
    with gzip.open(saida / "workflow_runs.csv.gz", "rt", encoding="utf-8") as arquivo:
        assert len(list(csv.DictReader(arquivo))) == 140
    with (saida / "funil_selecao.csv").open(encoding="utf-8") as arquivo:
        assert list(csv.DictReader(arquivo))[-1]["aprovados"] == "2"
    resumo = json.loads((saida / "resumo_execucao.json").read_text(encoding="utf-8"))
    assert resumo["meta_atingida"] is True
    assert resumo["pre_filtro"]["fork"] == 1
    assert (saida / "candidatos_avaliados.csv").exists()
    assert (saida / "releases.csv").exists()


def test_carregar_config_mescla_padroes_e_valida(tmp_path):
    arquivo = tmp_path / "c.json"
    arquivo.write_text(json.dumps({"meta_repositorios": 7, "criterios": {"minimo_releases": 3}}),
                       encoding="utf-8")
    config = pipeline_dora.carregar_config(arquivo)
    assert config["meta_repositorios"] == 7
    assert config["criterios"] == {"minimo_releases": 3, "minimo_runs_validos": 50}
    assert pipeline_dora.carregar_config(None)["janela"]["inicio"] == "2025-10-01"
    arquivo.write_text(json.dumps({"janela": {"inicio": "2026-01-02", "fim": "2026-01-01"}}),
                       encoding="utf-8")
    with pytest.raises(ValueError):
        pipeline_dora.carregar_config(arquivo)
    arquivo.write_text(json.dumps({"meta_repositorios": 0}), encoding="utf-8")
    with pytest.raises(ValueError):
        pipeline_dora.carregar_config(arquivo)


def test_ler_candidatos_ordena_por_estrelas_e_remove_duplicados(tmp_path):
    arquivo = tmp_path / "metadados.csv"
    with arquivo.open("w", encoding="utf-8", newline="") as saida:
        escritor = csv.DictWriter(saida, fieldnames=["nome_completo", "estrelas"])
        escritor.writeheader()
        escritor.writerows([{"nome_completo": "o/b", "estrelas": "10"},
                            {"nome_completo": "o/a", "estrelas": "50"},
                            {"nome_completo": "O/B", "estrelas": "10"},
                            {"nome_completo": "", "estrelas": "99"}])
    assert [c["nome_completo"] for c in pipeline_dora.ler_candidatos(arquivo)] == ["o/a", "o/b"]


def test_preparar_candidatos_roda_rq73_e_rq74_quando_faltam(tmp_path, config):
    config = pipeline_dora._mesclar(config, {"candidatos": {
        "saida_busca": str(tmp_path / "busca.json"), "metadados": str(tmp_path / "meta.csv")}})
    comandos = []
    pipeline_dora.preparar_candidatos(config, executar=lambda cmd, check: comandos.append(cmd))
    assert [Path(c[1]).name for c in comandos] == ["rq73_coletar_candidatos.py",
                                                   "rq74_metadados_repositorios.py"]
    (tmp_path / "meta.csv").write_text("nome_completo\n", encoding="utf-8")
    comandos.clear()
    pipeline_dora.preparar_candidatos(config, executar=lambda cmd, check: comandos.append(cmd))
    assert comandos == []
