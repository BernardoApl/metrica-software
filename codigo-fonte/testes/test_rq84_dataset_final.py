"""RQ84: dataset final consolidado e dicionario de dados (sem rede)."""

import json
import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "codigo-fonte"))
sys.path.insert(0, str(RAIZ / "codigo-fonte" / "coleta"))
sys.path.insert(0, str(RAIZ / "codigo-fonte" / "validacao"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline_dora
import rq84_dataset_final as rq84
import rq86_amostra_ouro as ouro
import rq88_concordancia as rq88
import rq89_heuristica as rq89
from metricas import corretiva
from rq75_releases_tags_commits import COLUNAS as COLUNAS_RQ75
from test_rq88_concordancia import amostra_gerada  # noqa: F401 - fixture do pytest


# ======================================================= dicionario x codigo
def test_toda_coluna_documentada_tem_definicao():
    for arquivo, (descricao, gerado_por, colunas) in rq84.ARQUIVOS.items():
        assert descricao and gerado_por
        assert len(colunas) == len(set(colunas)), arquivo
        for coluna in colunas:
            definicao = rq84.definicao(arquivo, coluna)
            assert definicao is not None, (arquivo, coluna)
            tipo, unidade, formula = definicao
            assert tipo in {"texto", "inteiro", "real", "booleano", "data", "categoria", "json"}
            assert unidade and formula


@pytest.mark.parametrize("arquivo, colunas", [
    ("metricas_repositorios.csv", pipeline_dora.COLUNAS_METRICAS),
    ("candidatos_avaliados.csv", pipeline_dora.COLUNAS_AVALIACAO),
    ("funil_selecao.csv", pipeline_dora.COLUNAS_FUNIL),
    ("releases.csv", pipeline_dora.COLUNAS_RELEASES),
    ("workflow_runs.csv.gz", pipeline_dora.COLUNAS_RUNS),
    ("intervalos_runs.csv", pipeline_dora.COLUNAS_INTERVALOS),
    ("lead_time_releases.csv", pipeline_dora.COLUNAS_LEAD_TIME),
    ("commits_releases.csv.gz", pipeline_dora.COLUNAS_COMMITS),
    ("tags.csv", COLUNAS_RQ75["tags"]),
    ("amostra_ouro/sorteio_repositorios.csv", ouro.COLUNAS_REPOSITORIOS),
    ("amostra_ouro/sorteio_releases.csv", ouro.COLUNAS_RELEASES),
])
def test_dicionario_acompanha_as_colunas_do_codigo(arquivo, colunas):
    """Se alguma RQ mudar as colunas que exporta, este teste aponta o dicionario desatualizado."""
    assert tuple(rq84.ARQUIVOS[arquivo][2]) == tuple(colunas)


def test_avaliadores_iguais_aos_da_rq86():
    assert rq84.AVALIADORES == ouro.AVALIADORES


def test_dicionario_cobre_as_saidas_da_rq89():
    tabela = pd.DataFrame({"id_release": ["R01-1", "R01-2"], "nome_completo": ["o/r", "o/r"],
                           "release_anterior": ["v1.0.0", "v1.0.1"],
                           "tag_name": ["v1.0.1", "v1.1.0"],
                           "mensagens": [["fix: x"], None]})
    rotulos = {"R01-1": False, "R01-2": True}
    avaliacao = rq89.avaliar(tabela, rotulos)
    assert tuple(avaliacao[0]) == rq84.ARQUIVOS["amostra_ouro/avaliacao_heuristica.csv"][2]
    erros = rq89.listar_erros(tabela, rotulos)
    assert set(erros.columns) <= set(rq84.ARQUIVOS["amostra_ouro/erros_heuristica.csv"][2])
    evidencias = ["ev_" + k for k in corretiva.evidencias("v1.0.0", "v1.0.1", ["fix: x"])]
    assert set(evidencias) <= set(rq84.ARQUIVOS["amostra_ouro/erros_heuristica.csv"][2])


def test_dicionario_cobre_as_saidas_reais_da_rq88(amostra_gerada, tmp_path):  # noqa: F811
    pasta = tmp_path / "final"
    shutil.copytree(amostra_gerada, pasta / "amostra_ouro")
    (pasta / "amostra_ouro" / "decisoes_reuniao.csv").write_text(
        "dimensao,id_item,rotulo,justificativa\ntipo_projeto,R01,outro,x\n", encoding="utf-8")
    rq88.executar(pasta / "amostra_ouro")
    cobertura = rq84.verificar_cobertura(pasta)
    assert cobertura["erros"] == []
    assert "amostra_ouro/consenso_releases.csv" in cobertura["arquivos_conferidos"]
    assert "amostra_ouro/pendencias_reuniao.csv" in cobertura["arquivos_conferidos"]


@pytest.fixture
def pasta_piloto(tmp_path):
    """Copia dos dados reais commitados: coleta piloto (dados/lab03) + RQ83 piloto."""
    pasta = tmp_path / "lab03_final"
    pasta.mkdir()
    for arquivo in (RAIZ / "dados" / "lab03").iterdir():
        if arquivo.suffix in (".csv", ".json", ".gz"):
            shutil.copy(arquivo, pasta / arquivo.name)
    shutil.copytree(RAIZ / "dados" / "rq83_piloto", pasta / "rq83")
    return pasta


def test_dicionario_cobre_os_arquivos_reais_da_coleta_piloto(pasta_piloto):
    cobertura = rq84.verificar_cobertura(pasta_piloto)
    assert cobertura["erros"] == []
    assert {"metricas_repositorios.csv", "workflow_runs.csv.gz",
            "rq83/metricas_variantes.csv"} <= set(cobertura["arquivos_conferidos"])


def test_cobertura_aponta_coluna_e_arquivo_sem_documentacao(tmp_path):
    pd.DataFrame({"etapa": [1], "coluna_nova": [2]}).to_csv(tmp_path / "funil_selecao.csv",
                                                            index=False)
    pd.DataFrame({"x": [1]}).to_csv(tmp_path / "arquivo_novo.csv", index=False)
    (tmp_path / ".cache").mkdir()
    pd.DataFrame({"y": [1]}).to_csv(tmp_path / ".cache" / "ignorado.csv", index=False)
    cobertura = rq84.verificar_cobertura(tmp_path)
    assert cobertura["completo"] is False
    assert "arquivo_novo.csv: arquivo sem documentação no dicionário" in cobertura["erros"]
    assert "funil_selecao.csv: coluna `coluna_nova` sem documentação" in cobertura["erros"]
    assert any("`criterio` documentada, mas ausente" in a for a in cobertura["avisos"])
    assert ".cache/ignorado.csv" not in cobertura["arquivos_conferidos"]


def test_markdown_e_csv_do_dicionario(tmp_path):
    rq84.escrever_dicionario(tmp_path, {"inicio": "2025-10-01", "fim": "2026-09-30"})
    texto = (tmp_path / "DICIONARIO.md").read_text(encoding="utf-8")
    assert "2025-10-01 a 2026-09-30" in texto
    assert "None" not in texto
    for arquivo in rq84.ARQUIVOS:
        assert "## `%s`" % arquivo in texto
    tabela = pd.read_csv(tmp_path / "dicionario_dados.csv")
    assert list(tabela.columns) == ["arquivo", "coluna", "tipo", "unidade", "formula_ou_origem",
                                    "gerado_por"]
    assert len(tabela) == sum(len(c) for _, _, c in rq84.ARQUIVOS.values())
    assert not tabela.isna().any().any()


# ============================================================== quartis
def test_quartis_pelos_cortes_p25_p50_p75():
    serie = pd.Series([1, 2, 3, 4, 5, 6, 7, 8])  # P25 = 2,75; P50 = 4,5; P75 = 6,25
    assert rq84.quartil(serie).tolist() == ["Q1", "Q1", "Q2", "Q2", "Q3", "Q3", "Q4", "Q4"]


def test_quartil_com_empates_e_ausentes():
    serie = pd.Series([5, 5, 5, 5, None, 10])
    assert rq84.quartil(serie).tolist() == ["Q1", "Q1", "Q1", "Q1", None, "Q4"]


# ========================================================== consolidacao
def escrever_entradas(pasta, n=8, janela_rq83=None, extra_rq83=None):
    nomes = ["o/r%d" % i for i in range(n)]
    coleta = pd.DataFrame({
        "nome_completo": nomes, "url": ["https://github.com/" + x for x in nomes],
        "estrelas": [1000 * (i + 1) for i in range(n)], "linguagem": "Go",
        "criado_em": "2020-01-01T00:00:00Z", "idade_anos": [1.0 + i for i in range(n)],
        "contribuidores_total": [10 * (i + 1) for i in range(n)], "branch_padrao": "main",
        "workflows_total": 3, "releases_janela": 52, "prereleases_janela": 1,
        "frequencia_deploy_semana": 1.0, "runs_coletados": 200, "runs_validos": 100,
        "runs_falha": 10, "runs_sucesso": 90, "cfr_ci": 0.1, "recuperacao_mediana_horas": 2.0,
        "intervalos_no_teto": 0,
    })
    variantes = pd.DataFrame({
        "nome_completo": list(reversed(nomes)), "releases_janela": 52,
        "frequencia_deploy_semana": 1.0, "lead_time_release_mediana_dias": 3.0,
        "lead_time_commit_mediana_dias": 1.5, "runs_validos": 100, "runs_falha": 10,
        "runs_sucesso": 90, "cfr_ci": 0.1, "cfr_entrega": 0.2, "recuperacao_mediana_horas": 2.0,
        "calculo_completo": True, "pendencias": "",
    })
    for coluna, valores in (extra_rq83 or {}).items():
        variantes[coluna] = valores
    (pasta / "rq83").mkdir(parents=True)
    coleta.to_csv(pasta / "metricas_repositorios.csv", index=False)
    variantes.to_csv(pasta / "rq83" / "metricas_variantes.csv", index=False)
    janela = {"inicio": "2025-10-01", "fim": "2026-09-30"}
    (pasta / "resumo_execucao.json").write_text(json.dumps({"config": {"janela": janela}}),
                                                encoding="utf-8")
    (pasta / "rq83" / "resumo_rq83.json").write_text(json.dumps(
        {"janela": janela_rq83 or janela, "heuristica": "patch_semver_v1",
         "janela_confirmada": False}), encoding="utf-8")
    return nomes


def test_consolida_metadados_metricas_classes_e_quartis(tmp_path):
    escrever_entradas(tmp_path)
    resumo = rq84.executar(tmp_path)
    dataset = pd.read_csv(tmp_path / "dataset_final.csv", keep_default_na=False)
    assert tuple(dataset.columns) == rq84.COLUNAS_DATASET
    assert dataset["nome_completo"].tolist() == ["o/r%d" % i for i in range(8)]
    linha = dataset.iloc[0]
    # frequencia 1/sem High, lead time 3 dias High, CFR 10% Elite, recuperacao 2 h High.
    assert (linha["classe_frequencia"], linha["classe_lead_time"], linha["classe_cfr"],
            linha["classe_recuperacao"], linha["classe_geral"]) == (
        "High", "High", "Elite", "High", "High")
    assert linha["cfr_entrega"] == 0.2
    assert linha["heuristica_cfr_entrega"] == "patch_semver_v1"
    assert dataset["estrelas_quartil"].tolist() == ["Q1", "Q1", "Q2", "Q2", "Q3", "Q3", "Q4", "Q4"]
    assert dataset["na_amostra_ouro"].tolist() == [False] * 8
    assert dataset["tipo_projeto"].tolist() == [""] * 8
    assert resumo["sem_pendencias"] is True
    assert resumo["cobertura_dicionario"]["completo"] is True
    assert (tmp_path / "DICIONARIO.md").exists()
    assert set(resumo["entradas_sha256"]) == {"metricas", "resumo_coleta", "variantes",
                                              "resumo_rq83"}


def test_tipo_do_projeto_vem_do_consenso_da_amostra_ouro(tmp_path):
    escrever_entradas(tmp_path)
    (tmp_path / "amostra_ouro").mkdir()
    pd.DataFrame({"id_repositorio": ["R01", "R02"], "nome_completo": ["o/r1", "o/r5"]}).to_csv(
        tmp_path / "amostra_ouro" / "sorteio_repositorios.csv", index=False)
    pd.DataFrame({"id_repositorio": ["R01", "R02"], "nome_completo": ["o/r1", "o/r5"],
                  "tipo_projeto_consenso": ["ferramenta_cli", "outro"],
                  "entregas_reais_consenso": ["sim", "incerto"]}).to_csv(
        tmp_path / "amostra_ouro" / "consenso_repositorios.csv", index=False)
    resumo = rq84.executar(tmp_path)
    dataset = pd.read_csv(tmp_path / "dataset_final.csv").set_index("nome_completo")
    assert dataset.loc["o/r1", "tipo_projeto"] == "ferramenta_cli"
    assert dataset.loc["o/r5", "entregas_reais"] == "incerto"
    assert pd.isna(dataset.loc["o/r0", "tipo_projeto"])
    assert bool(dataset.loc["o/r1", "na_amostra_ouro"]) is True
    assert (resumo["na_amostra_ouro"], resumo["com_tipo_projeto"]) == (2, 2)


def test_divergencia_entre_coleta_e_rq83_e_reportada(tmp_path):
    escrever_entradas(tmp_path, extra_rq83={"cfr_ci": [0.1] * 7 + [0.5]})
    resumo = rq84.executar(tmp_path)
    assert resumo["divergencias_coleta_rq83"] == {"cfr_ci": ["o/r0"]}  # lista invertida na RQ83
    assert resumo["sem_pendencias"] is False
    dataset = pd.read_csv(tmp_path / "dataset_final.csv").set_index("nome_completo")
    assert dataset.loc["o/r0", "cfr_ci"] == 0.5  # a RQ83 e a fonte autoritativa


def test_calculo_incompleto_vira_pendencia_e_classe_geral_vazia(tmp_path):
    escrever_entradas(tmp_path, extra_rq83={
        "calculo_completo": [True] * 7 + [False],
        "lead_time_release_mediana_dias": [3.0] * 7 + [None]})
    resumo = rq84.executar(tmp_path)
    assert resumo["repositorios_com_calculo_incompleto"] == ["o/r0"]
    dataset = pd.read_csv(tmp_path / "dataset_final.csv").set_index("nome_completo")
    assert pd.isna(dataset.loc["o/r0", "classe_geral"])
    assert resumo["classe_geral"] == {"High": 7, "indefinida": 1}


def test_repositorios_diferentes_entre_coleta_e_rq83(tmp_path):
    escrever_entradas(tmp_path)
    variantes = pd.read_csv(tmp_path / "rq83" / "metricas_variantes.csv")
    variantes.iloc[:-1].to_csv(tmp_path / "rq83" / "metricas_variantes.csv", index=False)
    with pytest.raises(ValueError, match="repositorios diferentes"):
        rq84.executar(tmp_path)


def test_janela_diferente_entre_coleta_e_rq83(tmp_path):
    escrever_entradas(tmp_path, janela_rq83={"inicio": "2025-09-01", "fim": "2026-08-31"})
    with pytest.raises(ValueError, match="Janela"):
        rq84.executar(tmp_path)


def test_repositorio_duplicado(tmp_path):
    escrever_entradas(tmp_path)
    coleta = pd.read_csv(tmp_path / "metricas_repositorios.csv")
    pd.concat([coleta, coleta.iloc[[0]]]).to_csv(tmp_path / "metricas_repositorios.csv",
                                                 index=False)
    with pytest.raises(ValueError, match="duplicados"):
        rq84.executar(tmp_path)


def test_consolidacao_real_da_piloto(pasta_piloto):
    resumo = rq84.executar(pasta_piloto)
    assert resumo["repositorios"] == 100
    assert resumo["divergencias_coleta_rq83"] == {}  # coleta e RQ83 concordam
    assert resumo["cobertura_dicionario"]["erros"] == []
    # A piloto nao tem lead time: calculo incompleto e classe geral indefinida.
    assert len(resumo["repositorios_com_calculo_incompleto"]) == 100
    dataset = pd.read_csv(pasta_piloto / "dataset_final.csv")
    assert dataset["estrelas_quartil"].value_counts().to_dict() == {
        "Q1": 25, "Q2": 25, "Q3": 25, "Q4": 25}


# ================================================================== CLI
def test_cli(tmp_path, capsys):
    assert rq84.principal(["--pasta", str(tmp_path / "vazia")]) == 1
    assert "RQ82" in capsys.readouterr().err
    assert rq84.principal(["--pasta", str(tmp_path / "doc"), "--somente-dicionario"]) == 0
    assert (tmp_path / "doc" / "DICIONARIO.md").exists()
    escrever_entradas(tmp_path / "ok")
    assert rq84.principal(["--pasta", str(tmp_path / "ok")]) == 0
    escrever_entradas(tmp_path / "pendente", extra_rq83={"calculo_completo": [False] * 8})
    assert rq84.principal(["--pasta", str(tmp_path / "pendente")]) == 2
    assert "calculo incompleto" in capsys.readouterr().out
