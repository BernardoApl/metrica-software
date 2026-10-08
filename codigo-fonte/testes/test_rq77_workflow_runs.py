"""RQ77: coleta de workflow runs sem perder dados no teto de 1.000 da busca (sem rede)."""

import csv
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "coleta"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import coleta_dora
import pipeline_dora
from test_coleta_dora import ClienteFalso, run_em
from test_pipeline_dora import cenario, config  # noqa: F401 - fixtures do pytest

UTC = timezone.utc


def runs_espalhados(inicio, quantidade, passo_segundos, primeiro_id=0):
    """``quantidade`` runs a partir de ``inicio``, um a cada ``passo_segundos``."""
    runs = []
    for i in range(quantidade):
        instante = (inicio + timedelta(seconds=i * passo_segundos)).strftime("%Y-%m-%dT%H:%M:%SZ")
        run = run_em(instante[:10], primeiro_id + i)
        run["created_at"] = run["run_started_at"] = instante
        runs.append(run)
    return runs


def criados(cliente):
    return [p["created"] for _, p in cliente.chamadas]


# ------------------------------------------------------- formato do intervalo
def test_dias_inteiros_mantem_o_formato_da_s01():
    de = datetime(2026, 1, 1, tzinfo=UTC)
    ate = datetime(2026, 1, 31, 23, 59, 59, tzinfo=UTC)
    assert coleta_dora.formatar_intervalo(de, ate) == "2026-01-01..2026-01-31"


def test_fracao_de_dia_usa_data_e_hora_utc():
    de = datetime(2026, 1, 5, 12, 0, 0, tzinfo=UTC)
    ate = datetime(2026, 1, 5, 17, 59, 59, tzinfo=UTC)
    assert (coleta_dora.formatar_intervalo(de, ate)
            == "2026-01-05T12:00:00+00:00..2026-01-05T17:59:59+00:00")


def test_url_da_janela_e_dos_meses_nao_muda_e_o_cache_vale():
    cliente = ClienteFalso(runs=[run_em("2026-01-10", 1)])
    coleta_dora.total_de_runs(cliente, "o/r", "main", "2025-10-01", "2026-09-30")
    coleta_dora.coletar_runs(cliente, "o/r", "main", "2026-01-01", "2026-02-28")
    assert set(criados(cliente)) == {"2025-10-01..2026-09-30", "2026-01-01..2026-01-31",
                                     "2026-02-01..2026-02-28"}


# ---------------------------------------------------------------- divisao
def test_varios_dias_sao_divididos_por_dia():
    de = datetime(2026, 1, 1, tzinfo=UTC)
    ate = datetime(2026, 1, 31, 23, 59, 59, tzinfo=UTC)
    (a, b), (c, d) = coleta_dora.dividir_intervalo(de, ate)
    assert (a, b) == (de, datetime(2026, 1, 16, 23, 59, 59, tzinfo=UTC))
    assert (c, d) == (datetime(2026, 1, 17, tzinfo=UTC), ate)


def test_um_dia_e_dividido_ao_meio_dia():
    de = datetime(2026, 1, 5, tzinfo=UTC)
    ate = datetime(2026, 1, 5, 23, 59, 59, tzinfo=UTC)
    (a, b), (c, d) = coleta_dora.dividir_intervalo(de, ate)
    assert b == datetime(2026, 1, 5, 11, 59, 59, tzinfo=UTC)
    assert c == datetime(2026, 1, 5, 12, 0, 0, tzinfo=UTC)


def test_um_segundo_nao_tem_como_dividir():
    instante = datetime(2026, 1, 5, 10, 0, 0, tzinfo=UTC)
    assert coleta_dora.dividir_intervalo(instante, instante) is None


def test_metades_cobrem_o_intervalo_sem_lacuna_nem_sobreposicao():
    sorteio = random.Random(77)
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for _ in range(500):
        de = base + timedelta(seconds=sorteio.randrange(0, 86400 * 60))
        ate = de + timedelta(seconds=sorteio.randrange(1, 86400 * 40))
        (a, b), (c, d) = coleta_dora.dividir_intervalo(de, ate)
        assert a == de and d == ate
        assert a <= b < c <= d
        assert c - b == timedelta(seconds=1)


# ------------------------------------------------------- teto de 1.000 runs
def test_total_count_subestimado_nao_perde_runs():
    """Caso angular/angular 2026-04: a API informa <= 1.000, mas o mes tem mais."""
    runs = runs_espalhados(datetime(2026, 4, 1, tzinfo=UTC), 1500, 1700)
    cliente = ClienteFalso(runs=runs, total_informado=lambda total: min(total, 1000))
    resultado = coleta_dora.coletar_runs(cliente, "o/r", "main", "2026-04-01", "2026-04-30")
    assert len(resultado["runs"]) == 1500
    assert resultado["teto_atingido"] == []
    abril = resultado["intervalos"][0]
    assert abril == {"intervalo": "2026-04-01..2026-04-30", "total_informado": 1000,
                     "coletados": 1000, "subdividido": True}


def test_dia_acima_do_teto_e_dividido_em_horas_sem_perder_runs():
    runs = runs_espalhados(datetime(2026, 1, 5, tzinfo=UTC), 1500, 50)  # 1.500 runs em ~21 h
    cliente = ClienteFalso(runs=runs)
    resultado = coleta_dora.coletar_runs(cliente, "o/r", "main", "2026-01-01", "2026-01-31")
    assert len(resultado["runs"]) == 1500
    assert resultado["teto_atingido"] == []
    assert "2026-01-05T00:00:00+00:00..2026-01-05T11:59:59+00:00" in criados(cliente)
    assert [r["id"] for r in resultado["runs"]] == list(range(1500))  # ordem cronologica


def test_exatamente_mil_runs_no_mes_sao_conferidos_e_nao_viram_aviso():
    runs = runs_espalhados(datetime(2026, 3, 1, tzinfo=UTC), 1000, 2000)
    cliente = ClienteFalso(runs=runs)
    resultado = coleta_dora.coletar_runs(cliente, "o/r", "main", "2026-03-01", "2026-03-31")
    assert len(resultado["runs"]) == 1000
    assert resultado["teto_atingido"] == []
    assert resultado["intervalos"][0]["subdividido"] is True


def test_mes_abaixo_do_teto_tem_uma_consulta_so():
    cliente = ClienteFalso(runs=runs_espalhados(datetime(2026, 3, 1, tzinfo=UTC), 999, 2000))
    resultado = coleta_dora.coletar_runs(cliente, "o/r", "main", "2026-03-01", "2026-03-31")
    assert resultado["intervalos"] == [{"intervalo": "2026-03-01..2026-03-31",
                                        "total_informado": 999, "coletados": 999,
                                        "subdividido": False}]


def test_auditoria_registra_cada_consulta_com_o_que_foi_coletado():
    runs = [run_em("2026-01-%02d" % (1 + i % 28), i) for i in range(1500)]
    runs += [run_em("2026-02-03", 10_000 + i) for i in range(10)]
    resultado = coleta_dora.coletar_runs(ClienteFalso(runs=runs), "o/r", "main",
                                         "2026-01-01", "2026-02-28")
    intervalos = {i["intervalo"]: i for i in resultado["intervalos"]}
    assert intervalos["2026-01-01..2026-01-31"]["subdividido"] is True
    assert intervalos["2026-01-01..2026-01-31"]["coletados"] is None  # nem paginou
    folhas = [i for i in resultado["intervalos"] if not i["subdividido"]]
    assert sum(i["coletados"] for i in folhas) == 1510
    assert all(i["coletados"] < coleta_dora.TETO_BUSCA for i in folhas)


def test_limite_operacional_vale_tambem_dentro_da_subdivisao():
    runs = runs_espalhados(datetime(2026, 1, 5, tzinfo=UTC), 1500, 50)
    with pytest.raises(coleta_dora.LimiteDeRunsExcedido):
        coleta_dora.coletar_runs(ClienteFalso(runs=runs), "o/r", "main", "2026-01-01",
                                 "2026-01-31", limite=1200)


def test_erro_http_numa_subdivisao_identifica_o_intervalo():
    class FalhaNaSubdivisao(ClienteFalso):
        def get(self, caminho, parametros=None, compactar=None):
            if "T" in (parametros or {}).get("created", ""):
                return {"status": 502, "corpo": None, "link": ""}
            return super().get(caminho, parametros, compactar)

    runs = runs_espalhados(datetime(2026, 1, 5, tzinfo=UTC), 1500, 50)
    with pytest.raises(coleta_dora.ErroColeta, match=r"2026-01-05T00:00:00\+00:00"):
        coleta_dora.coletar_runs(FalhaNaSubdivisao(runs=runs), "o/r", "main", "2026-01-05",
                                 "2026-01-05")


# --------------------------------------------------------------- pipeline
def test_pipeline_exporta_auditoria_dos_intervalos(cenario, config):  # noqa: F811
    cliente, candidatos = cenario
    resultado = pipeline_dora.executar(cliente, candidatos, config, registrar=lambda _: None)
    saida = pipeline_dora.exportar(resultado, config, cliente)
    with (saida / "intervalos_runs.csv").open(encoding="utf-8") as arquivo:
        linhas = list(csv.DictReader(arquivo))
    assert tuple(linhas[0]) == pipeline_dora.COLUNAS_INTERVALOS
    assert {l["nome_completo"] for l in linhas} == {"o/bom", "o/tambem-bom"}
    assert sum(1 for l in linhas if l["nome_completo"] == "o/bom") == 12  # um por mes
    assert all(l["subdividido"] == "False" for l in linhas)
