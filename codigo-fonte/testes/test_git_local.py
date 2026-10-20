"""Clone git parcial: tags e commits entre releases, com um repositorio git real e local (sem rede)."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "coleta"))
import git_local

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git nao instalado")


def git(pasta, *argumentos, data=None):
    ambiente = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
                    GIT_COMMITTER_EMAIL="t@t")
    if data:
        ambiente.update(GIT_AUTHOR_DATE=data, GIT_COMMITTER_DATE=data)
    resultado = subprocess.run(["git", *argumentos], cwd=pasta, env=ambiente, check=True,
                               capture_output=True, text=True)
    return resultado.stdout.strip()


def commitar(pasta, arquivo, mensagem, data):
    (pasta / arquivo).write_text(mensagem, encoding="utf-8")
    git(pasta, "add", arquivo)
    git(pasta, "commit", "-q", "-m", mensagem, data=data)
    return git(pasta, "rev-parse", "HEAD")


@pytest.fixture
def servidor(tmp_path):
    """Remoto ``file://`` com o repositorio ``o/r``: v1.0 (leve) -> v1.1 (anotada) -> v2.0."""
    trabalho = tmp_path / "trabalho"
    trabalho.mkdir()
    git(trabalho, "init", "-q", "-b", "main")
    c1 = commitar(trabalho, "a", "feat: primeiro", "2026-01-01T10:00:00+0000")
    git(trabalho, "tag", "v1.0")
    commitar(trabalho, "b", "feat: segundo", "2026-01-05T10:00:00+0300")  # 07:00 UTC
    c3 = commitar(trabalho, "c", "fix: crash\n\ncorpo longo", "2026-01-06T10:00:00+0000")
    git(trabalho, "tag", "-a", "v1.1", "-m", "release 1.1")
    commitar(trabalho, "d", "feat: terceiro", "2026-02-01T10:00:00+0000")
    git(trabalho, "tag", "v2.0")
    remoto = tmp_path / "remoto" / "o" / "r.git"
    remoto.parent.mkdir(parents=True)
    git(tmp_path, "clone", "-q", "--bare", str(trabalho), str(remoto))
    git(remoto, "config", "uploadpack.allowFilter", "true")
    return {"base": (tmp_path / "remoto").as_uri(), "c1": c1, "c3": c3, "pasta": tmp_path / "clones"}


def abrir(servidor, **extra):
    return git_local.CloneLocal("o/r", servidor["pasta"] / "o__r", base=servidor["base"], **extra).abrir()


def test_tags_resolve_tag_leve_e_anotada_com_data_utc(servidor):
    with abrir(servidor) as clone:
        tags = clone.tags()
    assert set(tags) == {"v1.0", "v1.1", "v2.0"}
    assert tags["v1.0"] == {"sha": servidor["c1"], "data_autor": "2026-01-01T10:00:00Z"}
    assert tags["v1.1"] == {"sha": servidor["c3"], "data_autor": "2026-01-06T10:00:00Z"}


def test_commits_entre_tags_no_formato_do_compare(servidor):
    with abrir(servidor) as clone:
        compare = clone.commits_entre("v1.0", "v1.1")
    assert compare["status"] == 200 and compare["total_commits"] == 2 and not compare["truncado"]
    assert [(c["data_autor"], c["mensagem"]) for c in compare["commits"]] == [
        ("2026-01-05T07:00:00Z", "feat: segundo"),  # fuso -03:00 convertido para UTC
        ("2026-01-06T10:00:00Z", "fix: crash"),     # so a 1a linha da mensagem
    ]
    assert all(len(c["sha"]) == 40 for c in compare["commits"])


def test_tag_ausente_e_404_e_mesma_tag_e_vazia(servidor):
    with abrir(servidor) as clone:
        assert clone.commits_entre("v1.0", "v9.9")["status"] == 404
        assert clone.commits_entre("v9.9", "v1.0")["commits"] == []
        mesma = clone.commits_entre("v1.1", "v1.1")
    assert mesma["status"] == 200 and mesma["commits"] == [] and mesma["total_commits"] == 0


def test_tags_datadas_marca_janela_e_release_associada(servidor):
    releases = [{"tag_name": "v1.1"}, {"tag_name": "v2.0"}]
    with abrir(servidor) as clone:
        resultado = git_local.tags_datadas(clone, "2026-01-02", "2026-01-31", releases)
    por_nome = {t["tag_name"]: t for t in resultado["tags"]}
    assert resultado["status"] == 200
    assert (por_nome["v1.0"]["dentro_janela"], por_nome["v1.0"]["tem_release"]) == (False, False)
    assert (por_nome["v1.1"]["dentro_janela"], por_nome["v1.1"]["tem_release"]) == (True, True)
    assert (por_nome["v2.0"]["dentro_janela"], por_nome["v2.0"]["tem_release"]) == (False, True)
    assert {t["status"] for t in resultado["tags"]} == {"ok"}


def test_fechar_apaga_a_pasta_e_liberta_a_vaga(servidor):
    fabrica = git_local.FabricaClones(servidor["pasta"], simultaneos=1, base=servidor["base"])
    primeiro = fabrica.abrir("o/r")
    assert primeiro.pasta.exists()
    primeiro.fechar()
    assert not primeiro.pasta.exists()
    segundo = fabrica.abrir("o/r")  # travaria para sempre se a vaga nao tivesse sido devolvida
    segundo.fechar()


def test_with_num_clone_ja_aberto_nao_pega_segunda_vaga(servidor):
    fabrica = git_local.FabricaClones(servidor["pasta"], simultaneos=1, base=servidor["base"])
    with fabrica.abrir("o/r") as clone:  # travaria se pedisse outra vaga com simultaneos=1
        assert "v1.0" in clone.tags()
    fabrica.abrir("o/r").fechar()


def test_repositorio_inexistente_vira_erro_git_e_nao_deixa_lixo(servidor):
    fabrica = git_local.FabricaClones(servidor["pasta"], simultaneos=1, base=servidor["base"])
    with pytest.raises(git_local.ErroGit):
        fabrica.abrir("o/nao-existe")
    assert not (servidor["pasta"] / "o__nao-existe").exists()
    fabrica.abrir("o/r").fechar()  # a vaga voltou apesar da falha


def test_pasta_restante_de_execucao_interrompida_e_refeita(servidor):
    sobra = servidor["pasta"] / "o__r"
    sobra.mkdir(parents=True)
    (sobra / "lixo").write_text("x")
    with abrir(servidor) as clone:
        assert "v1.0" in clone.tags()


def test_timeout_e_git_ausente_viram_erro_git(tmp_path):
    def estoura(*a, **kw):
        raise subprocess.TimeoutExpired(cmd="git", timeout=5)

    def ausente(*a, **kw):
        raise FileNotFoundError("git")

    for executar, trecho in ((estoura, "excedeu"), (ausente, "nao encontrado")):
        with pytest.raises(git_local.ErroGit, match=trecho):
            git_local.CloneLocal("o/r", tmp_path / "c", executar=executar).abrir()
        assert not (tmp_path / "c").exists()
