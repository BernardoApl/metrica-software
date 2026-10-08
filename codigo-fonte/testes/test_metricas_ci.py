"""RQ79: testes de CFR (a) e tempo de recuperacao com fixtures montadas a mao."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from metricas import ci


FIM_JANELA = "2026-03-31T23:59:59Z"


def run(hora, conclusao, workflow_id=1, fim=None, dia="2026-03-10", **extra):
    """Run sintetico; ``fim`` e o horario de ``updated_at`` (padrao: 5 min depois)."""
    inicio = "%sT%s:00Z" % (dia, hora)
    if fim is None:
        h, m = map(int, hora.split(":"))
        m += 5
        fim = "%02d:%02d" % (h + m // 60, m % 60)
    base = {
        "id": int(dia.replace("-", "") + hora.replace(":", "")) * 10 + workflow_id,
        "workflow_id": workflow_id,
        "event": "push",
        "head_branch": "main",
        "conclusion": conclusao,
        "created_at": inicio,
        "run_started_at": inicio,
        "updated_at": "%sT%s:00Z" % (dia, fim),
    }
    base.update(extra)
    return base


@pytest.fixture
def exemplo_enunciado():
    """Tabela da RQ 04: episodio de 10:00 ate 11:20 -> 1h20."""
    return [
        run("09:00", "success"),
        run("10:00", "failure"),
        run("10:30", "failure"),
        run("11:15", "success", fim="11:20"),
    ]


@pytest.mark.parametrize("conclusao, esperado", [
    ("success", "sucesso"),
    ("failure", "falha"),
    ("timed_out", "falha"),
    ("startup_failure", "falha"),
    ("cancelled", None),
    ("skipped", None),
    ("neutral", None),
    ("action_required", None),
    ("stale", None),
    (None, None),
    ("", None),
])
def test_tabela_de_conclusao_da_secao_3(conclusao, esperado):
    assert ci.classificar_conclusao(conclusao) == esperado


def test_data_utc_aceita_datetime_e_rejeita_data_sem_fuso():
    from datetime import datetime, timezone
    data = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert ci.data_utc(data) == data
    assert ci.data_utc("2026-01-01T07:00:00-03:00").hour == 10
    with pytest.raises(ValueError):
        ci.data_utc("2026-01-01T10:00:00")


def test_cfr_ci_ignora_cancelados_no_denominador():
    runs = [run("09:00", "success"), run("10:00", "failure"), run("11:00", "timed_out"),
            run("12:00", "success"), run("13:00", "cancelled"), run("14:00", None)]
    resultado = ci.cfr_ci(runs)
    assert resultado == {"falhas": 2, "sucessos": 2, "ignorados": 2, "cfr": 0.5}


def test_cfr_ci_sem_runs_validos_e_indefinido():
    assert ci.cfr_ci([run("09:00", "cancelled")])["cfr"] is None
    assert ci.cfr_ci([])["cfr"] is None


def test_filtro_mantem_apenas_push_no_default_branch_dentro_da_janela():
    runs = [
        run("09:00", "success"),
        run("09:10", "success", event="schedule"),
        run("09:20", "success", event="workflow_dispatch"),
        run("09:30", "failure", head_branch="feature"),
        run("09:40", "skipped"),
        run("09:50", "success", dia="2025-12-31"),
        run("10:00", "failure", dia="2026-04-01"),
    ]
    validos = ci.filtrar_runs_validos(runs, "main", "2026-01-01T00:00:00Z", FIM_JANELA)
    assert [r["created_at"] for r in validos] == ["2026-03-10T09:00:00Z"]


def test_exemplo_do_enunciado_resulta_em_1h20(exemplo_enunciado):
    episodios = ci.episodios_de_falha(exemplo_enunciado, FIM_JANELA)
    assert len(episodios) == 1
    assert episodios[0]["horas"] == pytest.approx(80 / 60)
    assert episodios[0]["falhas"] == 2
    assert not episodios[0]["censurado"]
    assert not episodios[0]["censura_esquerda"]


def test_ordem_de_entrada_nao_importa(exemplo_enunciado):
    embaralhado = list(reversed(exemplo_enunciado))
    assert ci.episodios_de_falha(embaralhado, FIM_JANELA)[0]["horas"] == pytest.approx(80 / 60)


def test_cancelado_no_meio_nao_encerra_nem_interrompe_episodio():
    runs = [run("09:00", "success"), run("10:00", "failure"),
            run("10:10", "cancelled"), run("10:20", "skipped"),
            run("11:00", "success", fim="11:30")]
    episodios = ci.episodios_de_falha(runs, FIM_JANELA)
    assert len(episodios) == 1
    assert episodios[0]["horas"] == pytest.approx(1.5)


def test_falha_nunca_recuperada_e_censurada_ate_o_fim_da_janela():
    runs = [run("09:00", "success"), run("10:00", "failure", dia="2026-03-31")]
    episodio = ci.episodios_de_falha(runs, FIM_JANELA)[0]
    assert episodio["censurado"]
    assert episodio["horas"] == pytest.approx(13 + 59 / 60 + 59 / 3600)


def test_falha_no_inicio_da_janela_tem_censura_a_esquerda():
    runs = [run("08:00", "failure"), run("08:30", "success", fim="08:40"),
            run("09:00", "failure"), run("09:30", "success", fim="10:00")]
    episodios = ci.episodios_de_falha(runs, FIM_JANELA)
    assert [e["censura_esquerda"] for e in episodios] == [True, False]
    assert episodios[1]["horas"] == pytest.approx(1.0)


def test_run_sem_run_started_at_usa_created_at():
    falha = run("10:00", "failure")
    falha["run_started_at"] = None
    runs = [run("09:00", "success"), falha, run("11:00", "success", fim="11:00")]
    assert ci.episodios_de_falha(runs, FIM_JANELA)[0]["horas"] == pytest.approx(1.0)


def test_episodios_sao_calculados_dentro_de_cada_workflow():
    # O sucesso do workflow 2 nao encerra a falha do workflow 1.
    runs = [
        run("09:00", "success", workflow_id=1),
        run("10:00", "failure", workflow_id=1),
        run("10:30", "success", workflow_id=2),
        run("12:00", "success", workflow_id=1, fim="12:00"),
        run("13:00", "success", workflow_id=2),
        run("14:00", "failure", workflow_id=2),
        run("14:30", "success", workflow_id=2, fim="14:30"),
    ]
    resumo = ci.tempo_de_recuperacao(runs, FIM_JANELA)
    assert resumo["episodios"] == 2
    assert sorted(e["horas"] for e in resumo["detalhes"]) == pytest.approx([0.5, 2.0])
    assert resumo["mediana_horas"] == pytest.approx(1.25)


def test_mediana_exclui_censurados_mas_reporta_proporcao():
    runs = [
        run("09:00", "success", workflow_id=1),
        run("10:00", "failure", workflow_id=1),
        run("11:00", "success", workflow_id=1, fim="11:00"),
        run("09:00", "success", workflow_id=2),
        run("10:00", "failure", workflow_id=2),
    ]
    resumo = ci.tempo_de_recuperacao(runs, FIM_JANELA)
    assert resumo["mediana_horas"] == pytest.approx(1.0)
    assert resumo["episodios_censurados"] == 1
    assert resumo["proporcao_censurados"] == pytest.approx(0.5)


def test_repositorio_sem_falhas_nao_tem_tempo_de_recuperacao():
    resumo = ci.tempo_de_recuperacao([run("09:00", "success"), run("10:00", "success")], FIM_JANELA)
    assert resumo["episodios"] == 0
    assert resumo["mediana_horas"] is None
    assert resumo["proporcao_censurados"] is None


def test_metricas_ci_repositorio_aplica_filtros_antes_de_calcular(exemplo_enunciado):
    runs = exemplo_enunciado + [
        run("10:15", "failure", event="schedule"),
        run("10:20", "cancelled"),
        run("10:25", "failure", head_branch="dev"),
    ]
    resultado = ci.metricas_ci_repositorio(runs, "main", "2026-01-01T00:00:00Z", FIM_JANELA)
    assert resultado["runs_validos"] == 4
    assert resultado["runs_falha"] == 2
    assert resultado["cfr_ci"] == pytest.approx(0.5)
    assert resultado["recuperacao_mediana_horas"] == pytest.approx(80 / 60)
    assert resultado["episodios_falha"] == 1
    assert resultado["episodios_censurados"] == 0
    assert resultado["proporcao_episodios_censurados"] == 0
