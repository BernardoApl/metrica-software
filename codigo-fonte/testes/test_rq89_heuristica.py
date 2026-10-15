"""RQ89: versoes da heuristica de release corretiva e avaliacao P/R/F1 (sem rede).

Os valores esperados foram calculados a mao na fixture ``SORTEIO`` (ver tabela
no comentario); nenhum rotulo aqui e humano ou real.
"""
import gzip
import json
import sys
from pathlib import Path

import pandas as pd
import pytest
from openpyxl import Workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "validacao"))
import rq89_heuristica as rq89
from metricas import corretiva, variantes
import test_rq83

V1, V2, V3 = "patch_semver_v1", "patch_ou_mensagem_v2", "correcao_de_defeito_v3"


# ------------------------------------------------------------------ evidencias
def ev(mensagens, anterior="v1.0.0", atual="v1.1.0"):
    return corretiva.evidencias(anterior, atual, mensagens)


def test_evidencias_contam_fix_revert_e_ignoram_merge():
    e = ev(["fix: crash ao abrir", "Fixes #12", 'Revert "feat: x"', "hotfix login",
            "Merge pull request #3 from a/b", "", "prefix da funcao", "fixture nova"])
    assert e["uteis"] == 6  # merge e linha vazia ficam de fora
    assert e["revert_hotfix"] == 2
    assert e["fix"] == 4  # 2 fix + 2 revert/hotfix
    assert e["fix_defeito"] == 2
    assert e["feat"] == 0


@pytest.mark.parametrize("mensagem", [
    "fix typo in README", "fix(docs): link quebrado", "fix lint warnings", "fix flaky test",
    "fix ci workflow", "fix deps", "Fix spelling",
])
def test_fix_trivial_nao_conta_como_defeito(mensagem):
    e = ev([mensagem])
    assert e["fix"] == 1 and e["fix_defeito"] == 0


def test_feature_so_conta_se_nao_for_correcao():
    e = ev(["feat(api): nova rota", "Add suporte a yaml", "fix: add null check"])
    assert (e["feat"], e["fix"], e["fix_defeito"]) == (2, 1, 1)


def test_sem_mensagens_so_a_tag_vale():
    e = ev(None, "v1.0.0", "v1.0.1")
    assert e["patch"] and not e["mensagens_disponiveis"] and e["fix"] == 0
    assert ev([], "v1.0.0", "v1.0.1")["mensagens_disponiveis"]


def test_classificar_rejeita_versao_desconhecida():
    with pytest.raises(ValueError, match="desconhecida"):
        corretiva.classificar("v99", "v1.0.0", "v1.0.1")


# --------------------------------------------------------------- versoes (casos)
@pytest.mark.parametrize("versao,anterior,atual,mensagens,esperado", [
    # v1 ignora mensagens
    (V1, "v1.0.0", "v1.0.1", ["feat: x"], True),
    (V1, "v1.0.0", "v1.1.0", ["fix: crash"], False),
    # v2: patch OU qualquer fix/revert/hotfix
    (V2, "v1.0.0", "v1.1.0", ["fix: crash"], True),
    (V2, "v1.0.0", "v1.1.0", ["feat: x", "fix typo"], True),
    (V2, "v1.0.0", "v1.1.0", ["feat: x"], False),
    (V2, "v1.0.0", "v1.0.1", None, True),
    # v3: exige defeito de verdade
    (V3, "v1.0.0", "v1.0.1", ["bump deps"], False),            # patch sem fix
    (V3, "v1.0.0", "v1.0.1", ["fix typo in docs"], False),     # fix trivial
    (V3, "v1.0.0", "v1.0.1", ["feat: x", "fix: crash"], True),  # patch + fix de defeito
    (V3, "v1.0.0", "v1.1.0", ["feat: x", "fix: crash"], False),  # tem feature e nao e patch
    (V3, "v1.0.0", "v1.1.0", ["fix: crash", "fix: leak"], True),  # so correcoes
    (V3, "v1.0.0", "v1.1.0", ["fix: crash", "chore: a", "chore: b"], False),  # fix e 1/3
    (V3, "v1.0.0", "v1.1.0", ["fix: crash", "chore: a"], True),  # exatamente metade
    (V3, "v1.0.0", "v1.1.0", ['Revert "feat: x"'], True),
    (V3, "v1.0.0", "v1.0.1", None, True),                       # sem mensagens: so a tag
    (V3, "v1.0.0", "v1.1.0", None, False),
    (V3, "r1", "r2", ["fix: crash"], True),                     # tag nao SemVer, so correcoes
])
def test_versoes_da_heuristica(versao, anterior, atual, mensagens, esperado):
    assert corretiva.classificar(versao, anterior, atual, mensagens) is esperado


def test_padrao_continua_v1_ate_a_validacao():
    assert corretiva.HEURISTICA_PADRAO == V1 == variantes.HEURISTICA
    assert set(corretiva.HEURISTICAS) == {V1, V2, V3}


# ------------------------------------------------------------- CFR com mensagens
def release(tag, dia):
    return test_rq83.release(tag, dia)


def test_cfr_usa_a_heuristica_escolhida_e_registra_o_nome():
    releases = [release("v1.0.0", 1), release("v1.1.0", 3), release("v1.2.0", 20)]
    mensagens = {"v1.1.0": ["fix: crash ao abrir"]}
    args = (releases, "2026-03-01T00:00:00Z", "2026-03-31T00:00:00Z")
    padrao = variantes.cfr_entrega(*args, mensagens_por_release=mensagens)
    assert padrao["cfr_entrega"] == 0  # v1: v1.1.0 muda o minor, nao e patch
    v3 = variantes.cfr_entrega(*args, heuristica=V3, mensagens_por_release=mensagens)
    assert v3["releases_avaliadas_cfr"] == 3
    assert v3["releases_falha_cfr"] == 1  # v1.0.0 foi seguida da corretiva v1.1.0 em 2 dias
    assert v3["cfr_entrega"] == pytest.approx(1 / 3)
    assert {d["heuristica"] for d in v3["detalhes"]} == {V3}
    assert v3["detalhes"][0]["corretiva_tag"] == "v1.1.0"


def test_rq83_propaga_heuristica_e_mensagens_dos_commits():
    repo, releases, runs, registros, commits = test_rq83.dados()
    for c in commits:
        c["mensagem"] = "feat: nova opcao"
    base, *_ = test_rq83.rq83.calcular_repositorio(repo, releases, runs, registros, commits,
                                                    test_rq83.JANELA)
    assert base["cfr_entrega"] == pytest.approx(1 / 3)  # v1: v1.1.1 e patch
    v3, *_ = test_rq83.rq83.calcular_repositorio(repo, releases, runs, registros, commits,
                                                  test_rq83.JANELA, True, V3)
    assert v3["cfr_entrega"] == 0  # patch sem nenhum fix de defeito nao e corretiva


# ------------------------------------------------------- avaliacao (valores a mao)
# id        anterior->atual        mensagens                         consenso  v1 v2 v3
# R01-1     v1.0.0->v1.0.1         fix: crash ao abrir               sim       T  T  T
# R01-2     v1.0.1->v1.1.0         feat + fix alinhamento            nao       F  T  F
# R01-3     v1.1.0->v1.1.1         bump deps, update docs            nao       T  T  F
# R01-4     v1.1.1->v1.2.0         Revert "feat: x"                  sim       F  T  T
# R01-5     release-5->release-6   2x fix de defeito                 sim       F  T  T
# R02-1     v3.0.0->v3.0.1         (sem compare)                     sim       T  T  T
# R02-2     v3.0.1->v3.1.0         feat, chore, Merge                nao       F  F  F
# R02-3     v3.1.0->v3.1.1         fix typo in README                nao       T  T  F
# v1: VP=2 FP=2 FN=2 VN=2 -> P=R=F1=0,5
# v2: VP=4 FP=3 FN=0 VN=1 -> P=4/7, R=1, F1=8/11
# v3: VP=4 FP=0 FN=0 VN=4 -> P=R=F1=1
SORTEIO = [
    ("R01-1", "o/a", "v1.0.0", "v1.0.1", ["fix: crash ao abrir"], True),
    ("R01-2", "o/a", "v1.0.1", "v1.1.0", ["feat: nova tela", "fix: alinhamento do botao"], False),
    ("R01-3", "o/a", "v1.1.0", "v1.1.1", ["bump deps", "update docs"], False),
    ("R01-4", "o/a", "v1.1.1", "v1.2.0", ['Revert "feat: x"'], True),
    ("R01-5", "o/a", "release-5", "release-6",
     ["fix: leak de memoria no parser", "fix: null pointer"], True),
    ("R02-1", "o/b", "v3.0.0", "v3.0.1", None, True),
    ("R02-2", "o/b", "v3.0.1", "v3.1.0", ["feat: x", "chore: y", "Merge pull request #3"], False),
    ("R02-3", "o/b", "v3.1.0", "v3.1.1", ["fix typo in README"], False),
]


@pytest.fixture
def pastas(tmp_path):
    entrada, amostra = tmp_path / "final", tmp_path / "final" / "amostra_ouro"
    amostra.mkdir(parents=True)
    pd.DataFrame([dict(id_release=i, id_repositorio=i[:3], nome_completo=n, tag_name=t,
                       release_anterior=a, published_at="2026-01-01T00:00:00Z",
                       link_release="https://github.com/%s/releases/tag/%s" % (n, t),
                       link_commits="https://github.com/%s/compare/%s...%s" % (n, a, t))
                  for i, n, a, t, _, _ in SORTEIO]).to_csv(amostra / "sorteio_releases.csv", index=False)
    commits = [dict(nome_completo=n, tag_name=t, anterior=a, sha="%s-%d" % (i, k),
                    data_autor="2026-01-01T00:00:00Z", mensagem=m)
               for i, n, a, t, ms, _ in SORTEIO for k, m in enumerate(ms or [])]
    with gzip.open(entrada / "commits_releases.csv.gz", "wt", encoding="utf-8", newline="") as f:
        pd.DataFrame(commits).to_csv(f, index=False)
    pd.DataFrame([dict(id_release=i, corretiva="sim" if real else "Não")
                  for i, *_, real in SORTEIO]).to_csv(amostra / "consenso_releases.csv", index=False)
    return entrada, amostra


def por_versao(resultados):
    return {r["versao"]: r for r in resultados}


def test_precisao_recall_f1_batem_com_o_calculo_a_mao(pastas):
    entrada, amostra = pastas
    tabela = rq89.ler_entradas(entrada, amostra)
    rotulos, invalidos = rq89.ler_rotulos(amostra / "consenso_releases.csv")
    assert invalidos == [] and sum(rotulos.values()) == 4
    r = por_versao(rq89.avaliar(tabela, rotulos))
    assert [(r[V1][k]) for k in ("vp", "fp", "fn", "vn")] == [2, 2, 2, 2]
    assert (r[V1]["precisao"], r[V1]["recall"], r[V1]["f1"]) == pytest.approx((.5, .5, .5))
    assert [(r[V2][k]) for k in ("vp", "fp", "fn", "vn")] == [4, 3, 0, 1]
    assert (r[V2]["precisao"], r[V2]["recall"], r[V2]["f1"]) == pytest.approx((4 / 7, 1, 8 / 11))
    assert [(r[V3][k]) for k in ("vp", "fp", "fn", "vn")] == [4, 0, 0, 4]
    assert r[V3]["f1"] == pytest.approx(1)
    assert r[V1]["sem_mensagens"] == 1 and r[V1]["n"] == 8
    assert rq89.melhor(list(r.values()))["versao"] == V3


def test_empate_de_f1_fica_com_a_versao_mais_recente():
    a, b = {"versao": "antiga", "f1": .8}, {"versao": "nova", "f1": .8}
    assert rq89.melhor([a, b])["versao"] == "nova"


def test_heuristica_que_nao_marca_nada_tem_precisao_zero_sem_erro(tmp_path):
    tabela = pd.DataFrame([dict(id_release="R01-1", release_anterior="r1", tag_name="r2",
                                mensagens=["feat: x"])])
    r = rq89.avaliar(tabela, {"R01-1": True}, [V1])[0]
    assert (r["precisao"], r["recall"], r["f1"]) == (0, 0, 0)


def test_erros_listam_fp_e_fn_com_evidencias_e_links(pastas):
    entrada, amostra = pastas
    tabela = rq89.ler_entradas(entrada, amostra)
    rotulos, _ = rq89.ler_rotulos(amostra / "consenso_releases.csv")
    erros = rq89.listar_erros(tabela, rotulos)
    v1 = erros[erros["versao"] == V1].set_index("id_release")
    assert set(v1.index) == {"R01-3", "R02-3", "R01-4", "R01-5"}
    assert v1.loc["R01-3", "erro"] == "falso_positivo" and v1.loc["R01-4", "erro"] == "falso_negativo"
    assert v1.loc["R01-3", "link_commits"].endswith("/compare/v1.1.0...v1.1.1")
    assert erros[erros["versao"] == V3].empty


def test_ler_rotulos_aceita_coluna_alternativa_e_marca_invalidos(tmp_path):
    caminho = tmp_path / "c.csv"
    pd.DataFrame({"id_release": ["R01-1", "R01-2", "R01-3"],
                  "consenso": ["SIM", "nao", "talvez"]}).to_csv(caminho, index=False)
    rotulos, invalidos = rq89.ler_rotulos(caminho)
    assert rotulos == {"R01-1": True, "R01-2": False} and invalidos == ["R01-3"]


def test_ler_rotulos_recusa_arquivo_sem_colunas_ou_com_id_repetido(tmp_path):
    ruim = tmp_path / "ruim.csv"
    pd.DataFrame({"id": ["R01-1"]}).to_csv(ruim, index=False)
    with pytest.raises(ValueError, match="precisa das colunas"):
        rq89.ler_rotulos(ruim)
    dup = tmp_path / "dup.csv"
    pd.DataFrame({"id_release": ["R01-1", "R01-1"], "corretiva": ["sim", "nao"]}).to_csv(dup, index=False)
    with pytest.raises(ValueError, match="repetido"):
        rq89.ler_rotulos(dup)


def test_ler_rotulos_de_planilha_xlsx_de_avaliador(tmp_path):
    livro = Workbook()
    repos = livro.active
    repos.title = "repositorios"
    repos.append(["id_repositorio", "nome_completo", "tipo_projeto", "entregas_reais"])
    repos.append(["R01", "o/a", "biblioteca/framework", "sim"])
    rel = livro.create_sheet("releases")
    rel.append(["id_release", "nome_completo", "tag_name", "corretiva"])
    rel.append(["R01-1", "o/a", "v1.0.1", "sim"])
    rel.append(["R01-2", "o/a", "v1.1.0", None])
    caminho = tmp_path / "rotulos_x.xlsx"
    livro.save(caminho)
    rotulos, invalidos = rq89.ler_rotulos(caminho)
    assert rotulos == {"R01-1": True} and invalidos == ["R01-2"]


def test_cli_grava_relatorios_e_o_codigo_de_saida_segue_o_limiar(pastas):
    entrada, amostra = pastas
    args = ["avaliar", "--entrada", str(entrada), "--amostra", str(amostra),
            "--consenso", str(amostra / "consenso_releases.csv")]
    assert rq89.principal(args) == 0  # v3 tem F1 = 1
    resumo = json.loads((amostra / "avaliacao_heuristica.json").read_text())
    assert resumo["melhor_versao"] == V3 and resumo["atinge_limiar"]
    assert resumo["versao_padrao_atual"] == V1
    assert len(pd.read_csv(amostra / "avaliacao_heuristica.csv")) == 3
    assert (amostra / "erros_heuristica.csv").exists()
    assert rq89.principal(args + ["--limiar", "1.01"]) == 2  # nenhuma passa de 1,01


def test_cli_avisa_release_sem_rotulo_e_recusa_rotulo_fora_do_sorteio(pastas):
    entrada, amostra = pastas
    consenso = amostra / "parcial.csv"
    pd.DataFrame({"id_release": ["R01-1", "R01-2", "R01-3"],
                  "corretiva": ["sim", "nao", ""]}).to_csv(consenso, index=False)
    resumo = rq89.executar(consenso, entrada, amostra, amostra / "saida")
    assert resumo["releases_rotuladas"] == 2
    assert "R01-3" in resumo["releases_sem_rotulo"] and "R02-1" in resumo["releases_sem_rotulo"]
    fora = amostra / "fora.csv"
    pd.DataFrame({"id_release": ["R99-1"], "corretiva": ["sim"]}).to_csv(fora, index=False)
    with pytest.raises(ValueError, match="fora do sorteio"):
        rq89.executar(fora, entrada, amostra, amostra / "saida")


def test_cli_explica_o_que_falta_quando_nao_ha_coleta_final(tmp_path, capsys):
    assert rq89.principal(["avaliar", "--entrada", str(tmp_path), "--amostra", str(tmp_path),
                           "--consenso", str(tmp_path / "x.csv")]) == 1
    assert "Faltam" in capsys.readouterr().err
