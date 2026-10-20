"""Tags e commits entre releases a partir de um clone git parcial, sem gastar cota da API.

Na coleta da S02 as chamadas mais caras eram as de ``compare`` (uma ou mais
paginas por release) e a consulta de data de cada tag (``/commits/{sha}``): so
nos 18 primeiros repositorios foram 6.932 SHAs de tags. Os mesmos dados saem de
um clone git local:

- ``git fetch --filter=tree:0`` baixa so os objetos de commit (sem arvores nem
  blobs) e so os refs ``refs/tags/*``: o historico da maioria dos projetos leva
  segundos (``kubernetes/kubernetes``: 1.251 tags, 73 MB, 13 s);
- ``git log base..head`` devolve os commits de ``head`` que nao estao em
  ``base``, o mesmo conjunto do ``compare/{base}...{head}`` da API, sem teto de
  paginas e sem truncamento;
- a data de um commit e a de autoria (``%at``), a mesma de ``commit.author.date``.

O clone e anonimo (repositorios publicos), entao o token nunca entra em
``.git/config`` nem na linha de comando. A API continua sendo a fonte de
releases, workflows e runs. Se o clone falhar (rede, timeout, repositorio
removido), quem chama volta a usar o ``compare`` da API para aquele repositorio.

O clone ocupa disco so durante a avaliacao do repositorio: o resultado vai para
o checkpoint e a pasta e apagada em seguida.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable, Optional

from coleta_dora import limites_da_janela

TAMANHO_MENSAGEM = 200
SEPARADOR_CAMPO = "\x1f"
SEPARADOR_COMMIT = "\x1e"
GITHUB = "https://github.com"


class ErroGit(RuntimeError):
    """O git falhou, nao existe ou estourou o tempo limite."""


def _ambiente() -> dict:
    ambiente = dict(os.environ)
    # Nunca perguntar usuario/senha nem consultar o gerenciador de credenciais: repositorio
    # removido ou privado deve falhar rapido, nao ficar esperando alguem no teclado.
    ambiente.update(GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never", GIT_NO_LAZY_FETCH="1",
                    LC_ALL="C")
    return ambiente


def data_iso(epoch: int) -> str:
    """Epoch -> ``AAAA-MM-DDTHH:MM:SSZ`` (o formato de ``commit.author.date`` na API)."""
    return datetime.fromtimestamp(int(epoch), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _remover(pasta: Path) -> None:
    """``rmtree`` que tambem apaga os pacotes somente-leitura do git no Windows."""
    def liberar(funcao, caminho, *_):
        os.chmod(caminho, stat.S_IWRITE)
        funcao(caminho)

    if pasta.exists():
        if sys.version_info >= (3, 12):
            shutil.rmtree(pasta, onexc=liberar)
        else:
            shutil.rmtree(pasta, onerror=liberar)


class CloneLocal:
    """Clone parcial (so commits e tags) de ``nome`` numa pasta temporaria.

    :param base: prefixo da URL; ``https://github.com`` na coleta, ``file://...`` nos testes.
    :param executar: injetavel para testes; por padrao ``subprocess.run``.
    :param trava: semaforo compartilhado que limita quantos clones existem ao mesmo tempo.
    """

    def __init__(self, nome: str, pasta: Path, tempo_limite: float = 900.0,
                 base: str = GITHUB, executar: Callable = subprocess.run,
                 trava: Optional[threading.BoundedSemaphore] = None):
        self.nome = nome
        self.pasta = Path(pasta)
        self.tempo_limite = tempo_limite
        self.base = base.rstrip("/")
        self._executar = executar
        self._trava = trava
        self._com_trava = False
        self._aberto = False
        self._tags: Optional[dict] = None

    # ----------------------------------------------------------------- git
    def _git(self, argumentos: list, entrada: Optional[str] = None,
             tempo_limite: Optional[float] = None) -> str:
        # lowSpeed*: aborta transferencia parada (rede que "pendura") em vez de esperar o limite todo.
        comando = ["git", "-c", "credential.helper=", "-c", "http.lowSpeedLimit=1000",
                   "-c", "http.lowSpeedTime=120", "-c", "core.fsmonitor=false", *argumentos]
        try:
            resultado = self._executar(
                comando, cwd=self.pasta if self.pasta.exists() else None, input=entrada,
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=tempo_limite or self.tempo_limite, env=_ambiente())
        except FileNotFoundError as erro:
            raise ErroGit("git nao encontrado no PATH; instale o git para usar o clone local.") from erro
        except subprocess.TimeoutExpired as erro:
            raise ErroGit("git %s excedeu %.0f s em %s" % (argumentos[0], erro.timeout, self.nome)) from erro
        if resultado.returncode != 0:
            raise ErroGit("git %s falhou em %s: %s" % (
                argumentos[0], self.nome, (resultado.stderr or "").strip()[-300:]))
        return resultado.stdout

    # ------------------------------------------------------------ ciclo de vida
    def abrir(self) -> "CloneLocal":
        if self._aberto:  # ``with fabrica.abrir(...)``: ja aberto, nao pega outra vaga
            return self
        if self._trava is not None:
            self._trava.acquire()
            self._com_trava = True
        try:
            _remover(self.pasta)  # sobra de uma execucao interrompida
            self.pasta.mkdir(parents=True)
            self._git(["init", "--bare", "-q"])
            self._git(["remote", "add", "origin", "%s/%s.git" % (self.base, self.nome)])
            self._git(["fetch", "-q", "--filter=tree:0", "--no-write-fetch-head", "origin",
                       "+refs/tags/*:refs/tags/*"])
        except BaseException:
            self.fechar()
            raise
        self._aberto = True
        return self

    def fechar(self) -> None:
        self._aberto = False
        try:
            _remover(self.pasta)
        finally:
            if self._com_trava:
                self._com_trava = False
                self._trava.release()

    def __enter__(self) -> "CloneLocal":
        return self.abrir()

    def __exit__(self, *_) -> None:
        self.fechar()

    # ------------------------------------------------------------------ dados
    def tags(self) -> dict:
        """``{nome_da_tag: {"sha", "data_autor"}}``; ``sha`` e ``None`` se a tag nao aponta para commit."""
        if self._tags is not None:
            return self._tags
        formato = "%(refname)%09%(objecttype)%09%(objectname)%09%(*objecttype)%09%(*objectname)"
        brutas = {}
        for linha in self._git(["for-each-ref", "--format=" + formato, "refs/tags"]).splitlines():
            ref, tipo, objeto, tipo_final, objeto_final = (linha.split("\t") + [""] * 5)[:5]
            nome = ref[len("refs/tags/"):]
            if tipo == "commit":
                brutas[nome] = objeto
            elif tipo == "tag" and tipo_final == "commit":
                brutas[nome] = objeto_final  # tag anotada: o commit esta um nivel abaixo
            else:
                brutas[nome] = None
        datas = self._datas(sorted({sha for sha in brutas.values() if sha}))
        self._tags = {nome: {"sha": sha, "data_autor": datas.get(sha) if sha else None}
                      for nome, sha in brutas.items()}
        return self._tags

    def _datas(self, shas: list) -> dict:
        if not shas:
            return {}
        saida = self._git(["log", "--no-walk=unsorted", "--stdin", "--format=%H%x09%at"],
                          entrada="\n".join(shas) + "\n")
        datas = {}
        for linha in saida.splitlines():
            sha, _, epoch = linha.partition("\t")
            if epoch.isdigit():
                datas[sha] = data_iso(int(epoch))
        return datas

    def commits_entre(self, base: str, head: str) -> dict:
        """Mesmo formato de ``coleta_dora.coletar_compare``: commits de ``head`` fora de ``base``.

        Tag ausente (apagada ou reescrita) devolve ``status`` 404, como o ``compare`` da API.
        """
        tags = self.tags()
        if not (tags.get(base) or {}).get("sha") or not (tags.get(head) or {}).get("sha"):
            return {"status": 404, "total_commits": None, "commits": [], "truncado": False}
        saida = self._git(["log", "--reverse", "--format=%H%x1f%at%x1f%B%x1e",
                           "refs/tags/%s..refs/tags/%s" % (base, head), "--"])
        commits = []
        for registro in saida.split(SEPARADOR_COMMIT):
            registro = registro.strip("\n")
            if not registro:
                continue
            sha, epoch, mensagem = (registro.split(SEPARADOR_CAMPO, 2) + ["", ""])[:3]
            linhas = mensagem.strip().splitlines()
            commits.append({"sha": sha, "data_autor": data_iso(epoch) if epoch.isdigit() else None,
                            "mensagem": linhas[0][:TAMANHO_MENSAGEM] if linhas else ""})
        return {"status": 200, "total_commits": len(commits), "commits": commits,
                "truncado": False}


class FabricaClones:
    """Cria clones numa pasta comum e limita quantos existem ao mesmo tempo."""

    def __init__(self, pasta: Path, tempo_limite: float = 900.0, simultaneos: int = 2,
                 base: str = GITHUB, executar: Callable = subprocess.run):
        self.pasta = Path(pasta)
        self.tempo_limite = tempo_limite
        self.base = base
        self._executar = executar
        self._trava = threading.BoundedSemaphore(max(1, int(simultaneos)))

    def abrir(self, nome: str) -> CloneLocal:
        return CloneLocal(nome, self.pasta / nome.replace("/", "__"), self.tempo_limite,
                          self.base, self._executar, self._trava).abrir()


def tags_datadas(clone: CloneLocal, inicio, fim, releases: Iterable[dict]) -> dict:
    """Linhas de tags no formato de ``rq75_releases_tags_commits.coletar_tags``, vindas do clone."""
    abertura, fechamento = limites_da_janela(inicio, fim)
    fechamento += timedelta(seconds=1)
    associadas = {r.get("tag_name") for r in releases}
    linhas = []
    for nome, dados in sorted(clone.tags().items()):
        data = None
        if dados["data_autor"]:
            data = datetime.fromisoformat(dados["data_autor"].replace("Z", "+00:00"))
        valido = dados["sha"] is not None and data is not None
        linhas.append({"tag_name": nome, "sha": dados["sha"], "data_autor": dados["data_autor"],
                       "status_commit": 200 if valido else None,
                       "status": "ok" if valido else "indisponivel",
                       "erro": None if valido else "tag sem commit no clone",
                       "tem_release": nome in associadas,
                       "dentro_janela": bool(valido and abertura <= data < fechamento)})
    return {"status": 200, "tags": linhas}
