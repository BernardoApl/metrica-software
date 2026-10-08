"""RQ76: testes do lead time for changes (RQ 02), variantes (a) por release e (b) por commit.

As fixtures sao releases e commits montados a mao, com o resultado calculado no
papel. O ponto de partida e o exemplo numerico do enunciado: ``v1.1`` publicada
em 15/03 com commits de 02/03, 10/03 e 14/03 -> (a) 13 dias; (b) 13, 5 e 1 dias.
"""

import pytest

from metricas import lead_time
from metricas.lead_time import COMPARE_INDISPONIVEL, SEM_ANTERIOR, SEM_COMMITS


def release(tag, publicada, dentro=True, draft=False, prerelease=False, id_=None):
    return {"id": id_ or abs(hash(tag)) % 10_000, "tag_name": tag, "published_at": publicada,
            "draft": draft, "prerelease": prerelease, "dentro_janela": dentro}


def compare(*datas, status=200, truncado=False):
    return {"status": status, "truncado": truncado,
            "commits": [{"sha": "c%d" % i, "data_autor": d} for i, d in enumerate(datas)]}


# ------------------------------------------------------------------ fixtures
@pytest.fixture
def exemplo_enunciado():
    """``v1.0`` (anterior, fora da janela) e ``v1.1`` com os tres commits do enunciado."""
    anterior = release("v1.0", "2026-02-20T12:00:00Z", dentro=False)
    v11 = release("v1.1", "2026-03-15T12:00:00Z")
    commits = compare("2026-03-02T12:00:00Z", "2026-03-10T12:00:00Z", "2026-03-14T12:00:00Z")
    return anterior, v11, commits


@pytest.fixture
def repositorio_com_commit_esquecido():
    """Tres releases; a ultima carrega um commit antigo "esquecido" de 100 dias.

    Lead times por release (a): v2 = 2, v3 = 3, v4 = 100 dias -> mediana 3.
    Lead times por commit (b): v2 -> [2, 1]; v3 -> [3, 2, 1]; v4 -> [100, 1, 1, 1, 1]
    -> 10 valores, ordenados [1,1,1,1,1,1,2,2,3,100] -> mediana 1.
    """
    return [
        lead_time.avaliar_release(
            release("v2", "2026-01-10T00:00:00Z"), release("v1", "2026-01-01T00:00:00Z"),
            compare("2026-01-08T00:00:00Z", "2026-01-09T00:00:00Z")),
        lead_time.avaliar_release(
            release("v3", "2026-02-10T00:00:00Z"), release("v2", "2026-01-10T00:00:00Z"),
            compare("2026-02-07T00:00:00Z", "2026-02-08T00:00:00Z", "2026-02-09T00:00:00Z")),
        lead_time.avaliar_release(
            release("v4", "2026-05-11T00:00:00Z"), release("v3", "2026-02-10T00:00:00Z"),
            compare("2026-01-31T00:00:00Z", *["2026-05-10T00:00:00Z"] * 4)),
    ]


# -------------------------------------------------------- exemplo do enunciado
def test_variante_a_do_exemplo_e_13_dias(exemplo_enunciado):
    _, v11, commits = exemplo_enunciado
    datas = [c["data_autor"] for c in commits["commits"]]
    assert lead_time.lead_time_da_release(v11["published_at"], datas) == pytest.approx(13)


def test_variante_b_do_exemplo_e_13_5_e_1_dias(exemplo_enunciado):
    _, v11, commits = exemplo_enunciado
    datas = [c["data_autor"] for c in commits["commits"]]
    assert lead_time.lead_times_dos_commits(v11["published_at"], datas) == pytest.approx([13, 5, 1])


def test_avaliar_release_do_exemplo(exemplo_enunciado):
    anterior, v11, commits = exemplo_enunciado
    avaliacao = lead_time.avaliar_release(v11, anterior, commits)
    assert avaliacao["lead_time_dias"] == pytest.approx(13)
    assert avaliacao["lead_times_commits"] == pytest.approx([13, 5, 1])
    assert avaliacao["anterior"] == "v1.0"
    assert avaliacao["commits"] == 3
    assert avaliacao["motivo"] is None


def test_lead_time_em_fracao_de_dia():
    assert lead_time.lead_time_da_release("2026-03-15T18:00:00Z",
                                          ["2026-03-15T06:00:00Z"]) == pytest.approx(0.5)


def test_fusos_diferentes_sao_convertidos_para_utc():
    # 09:00-03:00 = 12:00 UTC; release as 12:00 UTC do dia seguinte -> 1 dia.
    assert lead_time.lead_time_da_release("2026-03-16T12:00:00Z",
                                          ["2026-03-15T09:00:00-03:00"]) == pytest.approx(1)


# ------------------------------------------------------ agregacao do repositorio
def test_mediana_por_release_e_por_commit(repositorio_com_commit_esquecido):
    resumo = lead_time.metricas_lead_time(repositorio_com_commit_esquecido)
    assert resumo["lead_time_release_mediana_dias"] == pytest.approx(3)
    assert resumo["lead_time_commit_mediana_dias"] == pytest.approx(1)
    assert resumo["releases_com_lead_time"] == 3
    assert resumo["commits_com_lead_time"] == 10


def test_commit_esquecido_explode_a_variante_a_mas_nao_a_b(repositorio_com_commit_esquecido):
    v4 = repositorio_com_commit_esquecido[-1]
    assert v4["lead_time_dias"] == pytest.approx(100)
    assert sorted(v4["lead_times_commits"]) == pytest.approx([1, 1, 1, 1, 100])


def test_repositorio_sem_nenhuma_release_avaliavel_tem_lead_time_indefinido():
    resumo = lead_time.metricas_lead_time([
        lead_time.avaliar_release(release("v1", "2026-01-01T00:00:00Z"), None, None)])
    assert resumo["lead_time_release_mediana_dias"] is None
    assert resumo["lead_time_commit_mediana_dias"] is None
    assert resumo["releases_sem_anterior"] == 1
    assert lead_time.metricas_lead_time([])["releases_com_lead_time"] == 0


# ----------------------------------------------------------- casos de borda
def test_primeira_release_da_historia_e_ignorada():
    avaliacao = lead_time.avaliar_release(release("v1", "2026-01-01T00:00:00Z"), None, None)
    assert avaliacao["motivo"] == SEM_ANTERIOR
    assert avaliacao["lead_time_dias"] is None


def test_release_sem_commits_novos_e_ignorada_e_contada():
    avaliacao = lead_time.avaliar_release(release("v1.0.1", "2026-01-02T00:00:00Z"),
                                          release("v1.0.0", "2026-01-01T00:00:00Z"), compare())
    assert avaliacao["motivo"] == SEM_COMMITS
    assert avaliacao["lead_time_dias"] is None
    assert avaliacao["lead_times_commits"] == []
    assert lead_time.metricas_lead_time([avaliacao])["releases_sem_commits"] == 1


@pytest.mark.parametrize("resposta", [compare(status=404), compare(status=422), None,
                                      {"status": None, "commits": []}])
def test_compare_indisponivel_ignora_a_release(resposta):
    avaliacao = lead_time.avaliar_release(release("v2", "2026-01-02T00:00:00Z"),
                                          release("v1", "2026-01-01T00:00:00Z"), resposta)
    assert avaliacao["motivo"] == COMPARE_INDISPONIVEL
    assert lead_time.metricas_lead_time([avaliacao])["releases_compare_indisponivel"] == 1


def test_commit_posterior_a_release_e_descartado_e_contado():
    avaliacao = lead_time.avaliar_release(
        release("v2", "2026-01-10T00:00:00Z"), release("v1", "2026-01-01T00:00:00Z"),
        compare("2026-01-05T00:00:00Z", "2026-01-11T00:00:00Z"))
    assert avaliacao["lead_time_dias"] == pytest.approx(5)
    assert avaliacao["lead_times_commits"] == pytest.approx([5])
    assert avaliacao["commits"] == 2
    assert avaliacao["commits_negativos"] == 1
    assert lead_time.metricas_lead_time([avaliacao])["commits_negativos"] == 1


def test_release_so_com_commits_negativos_fica_sem_lead_time():
    avaliacao = lead_time.avaliar_release(
        release("v2", "2026-01-10T00:00:00Z"), release("v1", "2026-01-01T00:00:00Z"),
        compare("2026-01-11T00:00:00Z"))
    assert avaliacao["motivo"] == SEM_COMMITS
    assert lead_time.lead_time_da_release("2026-01-10T00:00:00Z", ["2026-01-11T00:00:00Z"]) is None


def test_commit_sem_data_e_ignorado():
    resposta = {"status": 200, "commits": [{"sha": "a", "data_autor": None},
                                           {"sha": "b", "data_autor": "2026-01-09T00:00:00Z"}]}
    avaliacao = lead_time.avaliar_release(release("v2", "2026-01-10T00:00:00Z"),
                                          release("v1", "2026-01-01T00:00:00Z"), resposta)
    assert avaliacao["lead_time_dias"] == pytest.approx(1)
    assert avaliacao["commits"] == 1


def test_compare_truncado_e_contado():
    avaliacao = lead_time.avaliar_release(
        release("v2", "2026-01-10T00:00:00Z"), release("v1", "2026-01-01T00:00:00Z"),
        compare("2026-01-09T00:00:00Z", truncado=True))
    assert avaliacao["truncado"] is True
    assert lead_time.metricas_lead_time([avaliacao])["releases_compare_truncado"] == 1


# ------------------------------------------------------------ pares de releases
def test_pares_usam_a_release_anterior_mesmo_fora_da_janela():
    releases = [
        release("v3", "2026-03-01T00:00:00Z"),
        release("v2", "2026-02-01T00:00:00Z"),
        release("v1", "2025-06-01T00:00:00Z", dentro=False),
    ]
    pares = [(a and a["tag_name"], r["tag_name"]) for a, r in lead_time.pares_de_releases(releases)]
    assert pares == [("v1", "v2"), ("v2", "v3")]


def test_unica_release_do_repositorio_nao_tem_par():
    pares = lead_time.pares_de_releases([release("v1", "2026-03-01T00:00:00Z")])
    assert [(a, r["tag_name"]) for a, r in pares] == [(None, "v1")]


def test_draft_prerelease_e_sem_data_nao_sao_deploy_nem_anterior():
    releases = [
        release("v2", "2026-03-01T00:00:00Z"),
        release("v2-rc1", "2026-02-20T00:00:00Z", prerelease=True),
        release("rascunho", "2026-02-15T00:00:00Z", draft=True),
        release("sem-data", None),
        release("v1", "2026-01-01T00:00:00Z"),
    ]
    pares = [(a and a["tag_name"], r["tag_name"]) for a, r in lead_time.pares_de_releases(releases)]
    assert pares == [(None, "v1"), ("v1", "v2")]


def test_variante_com_prerelease_compara_com_a_pre_release():
    releases = [release("v2", "2026-03-01T00:00:00Z"),
                release("v2-rc1", "2026-02-20T00:00:00Z", prerelease=True),
                release("v1", "2026-01-01T00:00:00Z")]
    pares = lead_time.pares_de_releases(releases, incluir_prerelease=True)
    assert [(a and a["tag_name"], r["tag_name"]) for a, r in pares] == [
        (None, "v1"), ("v1", "v2-rc1"), ("v2-rc1", "v2")]


def test_ordem_e_por_published_at_e_empate_pelo_id():
    releases = [release("b", "2026-03-01T00:00:00Z", id_=2),
                release("a", "2026-03-01T00:00:00Z", id_=1),
                release("c", "2026-01-01T00:00:00+00:00", id_=3)]
    pares = [(a and a["tag_name"], r["tag_name"]) for a, r in lead_time.pares_de_releases(releases)]
    assert pares == [(None, "c"), ("c", "a"), ("a", "b")]


def test_e_deploy():
    assert lead_time.e_deploy(release("v1", "2026-01-01T00:00:00Z"))
    assert not lead_time.e_deploy(release("v1", "2026-01-01T00:00:00Z", draft=True))
    assert not lead_time.e_deploy(release("v1", "2026-01-01T00:00:00Z", prerelease=True))
    assert lead_time.e_deploy(release("v1", "2026-01-01T00:00:00Z", prerelease=True),
                              incluir_prerelease=True)
