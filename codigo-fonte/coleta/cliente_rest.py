"""Cliente REST proprio do grupo, com cache em disco, paginacao e rate limit.

Usa apenas ``urllib`` (o enunciado proibe bibliotecas de acesso a API do
GitHub). Cada resposta e gravada em disco, um JSON por URL, antes de ser
devolvida; rodar a coleta de novo depois de uma interrupcao (rate limit, queda
de rede, Ctrl+C) le o cache e continua de onde parou sem repetir chamadas.

Rate limit: os cabecalhos ``X-RateLimit-Remaining``/``X-RateLimit-Reset`` de
cada resposta sao lidos; quando a cota chega a ``margem_cota``, o cliente dorme
ate a renovacao. Com varias threads, so uma dorme e as demais esperam por ela.
``GET /rate_limit`` (que nao consome cota) informa a situacao antes da coleta.
Erros temporarios (5xx, falhas de rede, corpo truncado) sao repetidos com
backoff exponencial 1 s, 2 s, 4 s, 8 s... (limitado a ``espera_maxima``) ate o
limite de tentativas.

RQ78: so respostas definitivas vao para o cache (200, 204, 404, 409, 410, 422,
451). Um 403 sem cabecalhos de rate limit e tratado como falta de permissao,
mas nao e gravado: se for um limite secundario mal identificado, a proxima
execucao tenta de novo em vez de descartar o repositorio para sempre.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator, Optional
from urllib.parse import urlencode

API = "https://api.github.com"
USER_AGENT = "metrica-software-lab03 (script proprio do grupo)"

#: Status que representam respostas definitivas (nao adianta tentar de novo).
STATUS_DEFINITIVOS = frozenset({200, 204, 404, 409, 410, 422, 451})

#: Esperas de rate limit seguidas na mesma URL antes de desistir (nao contam como tentativas).
MAX_BLOQUEIOS = 10


class ErroREST(RuntimeError):
    """Falha que persistiu depois de todas as tentativas."""


class ErroAutenticacaoREST(ErroREST):
    """Token invalido ou expirado (HTTP 401)."""


def proxima_pagina(link: Optional[str]) -> Optional[str]:
    """Extrai a URL ``rel="next"`` do cabecalho ``Link``."""
    for parte in (link or "").split(","):
        encontrado = re.search(r'<([^>]+)>\s*;\s*rel="next"', parte)
        if encontrado:
            return encontrado.group(1)
    return None


def montar_url(caminho: str, parametros: Optional[dict] = None) -> str:
    url = caminho if caminho.startswith("http") else API + caminho
    if parametros:
        url += ("&" if "?" in url else "?") + urlencode(parametros)
    return url


class ClienteREST:
    """GET com cache, backoff exponencial e espera automatica de rate limit.

    :param cache: diretorio do cache; ``None`` desliga o cache (uso em testes).
    :param abrir: injetavel para testes; por padrao ``urllib.request.urlopen``.
    :param dormir: injetavel para testes, evita esperas reais.
    """

    def __init__(
        self,
        token: str,
        cache: Optional[Path],
        tentativas: int = 6,
        espera_inicial: float = 1.0,
        tempo_limite: float = 60.0,
        espera_maxima: float = 60.0,
        margem_cota: int = 0,
        abrir: Callable = urllib.request.urlopen,
        dormir: Callable[[float], None] = time.sleep,
        relogio: Callable[[], float] = time.time,
        registrar: Optional[Callable[[str], None]] = print,
    ):
        if not token:
            raise ErroAutenticacaoREST("Token vazio.")
        self.token = token
        self.cache = Path(cache) if cache is not None else None
        self.tentativas = max(1, tentativas)
        self.espera_inicial = espera_inicial
        self.tempo_limite = tempo_limite
        self.espera_maxima = espera_maxima
        self.margem_cota = max(0, margem_cota)
        self._abrir = abrir
        self._dormir = dormir
        self._relogio = relogio
        self._registrar = registrar
        self.restantes: Optional[int] = None
        self.reinicio: Optional[float] = None
        self.requisicoes = 0
        self.acertos_cache = 0
        self.esperas_rate_limit = 0
        self.repeticoes = 0
        self._trava_contadores = threading.Lock()
        self._trava_cota = threading.Lock()

    def _log(self, mensagem: str) -> None:
        if self._registrar is not None:
            self._registrar(mensagem)

    def _contar(self, contador: str) -> None:
        with self._trava_contadores:
            setattr(self, contador, getattr(self, contador) + 1)

    def espera_de_backoff(self, tentativa: int) -> float:
        """1 s, 2 s, 4 s, 8 s... para a ``tentativa`` 1, 2, 3, 4..., ate ``espera_maxima``."""
        return min(self.espera_maxima, self.espera_inicial * (2 ** (tentativa - 1)))

    # ------------------------------------------------------------------ cache
    def _arquivo_cache(self, url: str) -> Optional[Path]:
        if self.cache is None:
            return None
        chave = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.cache / chave[:2] / (chave + ".json")

    def _ler_cache(self, url: str) -> Optional[dict]:
        arquivo = self._arquivo_cache(url)
        if arquivo is None or not arquivo.exists():
            return None
        try:
            registro = json.loads(arquivo.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None  # arquivo truncado: refaz a chamada
        if registro.get("url") != url:
            return None
        self._contar("acertos_cache")
        return registro

    def _gravar_cache(self, registro: dict) -> None:
        arquivo = self._arquivo_cache(registro["url"])
        if arquivo is None:
            return
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        temporario = arquivo.with_name("%s.%d.%d.tmp" % (arquivo.name, os.getpid(),
                                                          threading.get_ident()))
        temporario.write_text(json.dumps(registro, ensure_ascii=False), encoding="utf-8")
        temporario.replace(arquivo)

    # ------------------------------------------------------------ rate limit
    def _atualizar_cota(self, cabecalhos) -> None:
        try:
            restantes = cabecalhos.get("X-RateLimit-Remaining")
            reinicio = cabecalhos.get("X-RateLimit-Reset")
            if restantes is not None:
                self.restantes = int(restantes)
            if reinicio is not None:
                self.reinicio = float(reinicio)
        except (TypeError, ValueError):
            pass

    def _aguardar_cota(self) -> None:
        """Dorme ate o reset se a ultima resposta informou cota <= ``margem_cota``.

        A trava faz uma unica thread dormir; as outras ficam bloqueadas nela e,
        ao entrar, encontram ``restantes = None`` e seguem sem dormir de novo.
        """
        with self._trava_cota:
            if self.restantes is None or self.restantes > self.margem_cota or not self.reinicio:
                return
            espera = max(0.0, self.reinicio - self._relogio()) + 1.0
            reset = datetime.fromtimestamp(self.reinicio, timezone.utc).strftime("%H:%M:%S UTC")
            self._log("[rate limit] restam %d requisicoes; aguardando %.0f s (reset %s)."
                      % (self.restantes, espera, reset))
            self._contar("esperas_rate_limit")
            self._dormir(espera)
            self.restantes = None

    def consultar_cota(self) -> Optional[dict]:
        """``GET /rate_limit``: nao consome cota e nunca vai para o cache.

        Devolve ``{"limit", "remaining", "reset", "used"}`` da cota ``core`` e
        atualiza o estado interno, ou ``None`` se a consulta falhar.
        """
        try:
            resposta = self._requisitar(API + "/rate_limit")
            core = ((resposta["corpo"] or {}).get("resources") or {}).get("core") or {}
        except urllib.error.HTTPError as erro:
            if erro.code == 401:
                raise ErroAutenticacaoREST("Token rejeitado pelo GitHub (HTTP 401).") from erro
            self._log("[rate limit] /rate_limit respondeu HTTP %d." % erro.code)
            return None
        except (urllib.error.URLError, OSError, http.client.HTTPException,
                json.JSONDecodeError) as erro:
            self._log("[rate limit] nao foi possivel consultar /rate_limit: %s" % erro)
            return None
        if core.get("remaining") is not None:
            self.restantes = int(core["remaining"])
        if core.get("reset") is not None:
            self.reinicio = float(core["reset"])
        return {chave: core.get(chave) for chave in ("limit", "remaining", "reset", "used")}

    def _espera_de_bloqueio(self, erro: urllib.error.HTTPError, padrao: float) -> Optional[float]:
        """Para 403/429: devolve quanto esperar, ou ``None`` se nao for rate limit."""
        cabecalhos = erro.headers or {}
        retry_after = cabecalhos.get("Retry-After")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass
        if cabecalhos.get("X-RateLimit-Remaining") == "0" and cabecalhos.get("X-RateLimit-Reset"):
            return max(0.0, float(cabecalhos["X-RateLimit-Reset"]) - self._relogio()) + 1.0
        corpo = getattr(erro, "_corpo_lido", "")
        if erro.code == 429 or "rate limit" in corpo.lower():
            return max(60.0, padrao)  # limite secundario sem Retry-After
        return None

    # -------------------------------------------------------------- requisicao
    def _requisitar(self, url: str) -> dict:
        requisicao = urllib.request.Request(url, headers={
            "Authorization": "Bearer " + self.token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": USER_AGENT,
        })
        with self._abrir(requisicao, timeout=self.tempo_limite) as resposta:
            status = getattr(resposta, "status", 200)
            texto = resposta.read().decode("utf-8") if status != 204 else ""
            cabecalhos = resposta.headers
        self._atualizar_cota(cabecalhos)
        return {
            "status": status,
            "corpo": json.loads(texto) if texto else None,
            "link": cabecalhos.get("Link", "") or "",
        }

    def get(self, caminho: str, parametros: Optional[dict] = None,
            compactar: Optional[Callable] = None) -> dict:
        """Uma pagina: ``{"url", "status", "corpo", "link", "coletado_em"}``.

        ``compactar`` reduz o corpo antes de grava-lo no cache (ex.: descartar
        os objetos ``repository`` repetidos em cada workflow run). Respostas
        404/409/410/422/451 sao definitivas e tambem ficam no cache; um 403
        de permissao e devolvido, mas nao e gravado.

        Esperas de rate limit nao gastam tentativas: so erros temporarios
        (5xx, rede, corpo truncado) contam para ``tentativas``. Para nao ficar
        preso para sempre, no maximo ``MAX_BLOQUEIOS`` esperas seguidas.
        """
        url = montar_url(caminho, parametros)
        guardado = self._ler_cache(url)
        if guardado is not None:
            return guardado

        ultimo_erro: Optional[Exception] = None
        tentativa = 1
        bloqueios = 0
        while tentativa <= self.tentativas:
            espera = self.espera_de_backoff(tentativa)
            self._aguardar_cota()
            gravar = True
            try:
                self._contar("requisicoes")
                resposta = self._requisitar(url)
            except urllib.error.HTTPError as erro:
                self._atualizar_cota(erro.headers or {})
                try:
                    erro._corpo_lido = erro.read().decode("utf-8", errors="replace")[:500]
                except Exception:  # noqa: BLE001 - diagnostico best-effort
                    erro._corpo_lido = ""
                if erro.code == 401:
                    raise ErroAutenticacaoREST("Token rejeitado pelo GitHub (HTTP 401).") from erro
                if erro.code in STATUS_DEFINITIVOS:
                    resposta = {"status": erro.code, "corpo": None, "link": "",
                                "erro": erro._corpo_lido}
                elif erro.code in (403, 429):
                    bloqueio = self._espera_de_bloqueio(erro, espera)
                    if bloqueio is None:  # 403 de permissao (ex.: Actions desabilitado)
                        resposta = {"status": erro.code, "corpo": None, "link": "",
                                    "erro": erro._corpo_lido}
                        gravar = False
                    else:
                        bloqueios += 1
                        if bloqueios > MAX_BLOQUEIOS:
                            raise ErroREST("HTTP %d (rate limit) persistente em %s"
                                           % (erro.code, url)) from erro
                        self._log("[rate limit] HTTP %d; aguardando %.0f s." % (erro.code, bloqueio))
                        self._contar("esperas_rate_limit")
                        self._dormir(bloqueio)
                        self.restantes = None
                        continue
                else:
                    ultimo_erro = ErroREST("HTTP %d em %s" % (erro.code, url))
                    resposta = None
            except (urllib.error.URLError, OSError, http.client.HTTPException,
                    json.JSONDecodeError) as erro:
                # HTTPException cobre IncompleteRead (corpo cortado no meio), que nao e OSError.
                ultimo_erro = ErroREST("Falha de rede ou JSON invalido em %s: %s" % (url, erro))
                resposta = None

            if resposta is not None:
                if compactar is not None and resposta["corpo"] is not None:
                    resposta["corpo"] = compactar(resposta["corpo"])
                resposta["url"] = url
                resposta["coletado_em"] = datetime.now(timezone.utc).isoformat()
                if gravar:
                    self._gravar_cache(resposta)
                return resposta

            if tentativa < self.tentativas:
                self._log("[tentativa %d/%d] %s; nova tentativa em %.0f s."
                          % (tentativa, self.tentativas, ultimo_erro, espera))
                self._contar("repeticoes")
                self._dormir(espera)
            tentativa += 1
        raise ultimo_erro or ErroREST("Falha desconhecida em %s" % url)

    def paginar(self, caminho: str, parametros: Optional[dict] = None,
                compactar: Optional[Callable] = None,
                max_paginas: Optional[int] = None) -> Iterator[dict]:
        """Segue ``rel="next"`` ate o fim e devolve cada pagina (ver :meth:`get`)."""
        url: Optional[str] = montar_url(caminho, parametros)
        paginas = 0
        while url:
            pagina = self.get(url, compactar=compactar)
            yield pagina
            paginas += 1
            if pagina["status"] != 200 or (max_paginas and paginas >= max_paginas):
                return
            url = proxima_pagina(pagina.get("link"))
