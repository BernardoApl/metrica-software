"""Cliente HTTP proprio para a API GraphQL do GitHub.

O enunciado do laboratorio proibe bibliotecas de terceiros que consultem a API
do GitHub, entao este modulo usa apenas a biblioteca padrao (``urllib``), sem
nenhuma dependencia externa -- nem mesmo ``requests``.

Responsabilidades: autenticacao, envio da consulta, tratamento de erros HTTP e
GraphQL, e respeito ao limite de requisicoes (rate limit).
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Optional

ENDPOINT = "https://api.github.com/graphql"
USER_AGENT = "metrica-software-lab01 (script proprio do grupo)"

#: Variaveis de ambiente consultadas, em ordem de precedencia.
VARIAVEIS_TOKEN = ("GITHUB_TOKEN", "GH_TOKEN")


class ErroGitHub(RuntimeError):
    """Erro generico na comunicacao com a API do GitHub."""


class ErroAutenticacao(ErroGitHub):
    """Token ausente, invalido ou sem permissao. Nao adianta tentar de novo."""


class ErroConsultaGraphQL(ErroGitHub):
    """A API respondeu 200 mas devolveu erros de GraphQL sem dados utilizaveis."""

    def __init__(self, mensagem: str, erros: list):
        super().__init__(mensagem)
        self.erros = erros


class ErroLimiteRequisicoes(ErroGitHub):
    """Limite de requisicoes esgotado e nao recuperado dentro das tentativas."""


def _mensagem_de_erro(erro) -> str:
    """Extrai a mensagem de um item de ``errors``, que nem sempre e um dicionario."""
    if isinstance(erro, dict):
        return str(erro.get("message", erro))
    return str(erro)


def _ler_arquivo_env(caminho: Path) -> dict:
    """Le um arquivo ``.env`` simples (``CHAVE=valor`` por linha)."""
    valores = {}
    try:
        conteudo = caminho.read_text(encoding="utf-8")
    except OSError:
        return valores

    for linha in conteudo.splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        valores[chave.strip()] = valor.strip().strip("'\"")
    return valores


def obter_token(explicito: Optional[str] = None, raiz_projeto: Optional[Path] = None) -> str:
    """Resolve o token de acesso do GitHub.

    Ordem de precedencia: argumento explicito, variavel de ambiente
    (``GITHUB_TOKEN`` ou ``GH_TOKEN``), arquivo ``.env`` na raiz do projeto.

    :raises ErroAutenticacao: se nenhuma das fontes fornecer um token.
    """
    if explicito:
        return explicito.strip()

    for variavel in VARIAVEIS_TOKEN:
        valor = os.environ.get(variavel)
        if valor and valor.strip():
            return valor.strip()

    if raiz_projeto is None:
        raiz_projeto = Path(__file__).resolve().parents[2]
    do_env = _ler_arquivo_env(raiz_projeto / ".env")
    for variavel in VARIAVEIS_TOKEN:
        valor = do_env.get(variavel)
        if valor:
            return valor

    raise ErroAutenticacao(
        "Token do GitHub nao encontrado. Defina a variavel de ambiente GITHUB_TOKEN, "
        "crie um arquivo .env na raiz do projeto com GITHUB_TOKEN=... "
        "ou passe --token na linha de comando. "
        "Gere o token em https://github.com/settings/tokens (basta o escopo public_repo)."
    )


class ClienteGitHub:
    """Executa consultas GraphQL contra a API do GitHub, com repeticao automatica.

    :param token: token de acesso pessoal.
    :param tentativas: numero maximo de tentativas por consulta.
    :param espera_inicial: base, em segundos, do recuo exponencial.
    :param tempo_limite: tempo limite de cada requisicao HTTP, em segundos.
    :param registrar: funcao de log; recebe uma string. Use ``None`` para silenciar.
    :param dormir: injetavel para testes, evita esperas reais.
    """

    def __init__(
        self,
        token: str,
        endpoint: str = ENDPOINT,
        tentativas: int = 4,
        espera_inicial: float = 2.0,
        tempo_limite: float = 30.0,
        registrar: Optional[Callable[[str], None]] = print,
        dormir: Callable[[float], None] = time.sleep,
    ):
        if not token:
            raise ErroAutenticacao("Token vazio.")
        self.token = token
        self.endpoint = endpoint
        self.tentativas = max(1, tentativas)
        self.espera_inicial = espera_inicial
        self.tempo_limite = tempo_limite
        self._registrar = registrar
        self._dormir = dormir
        #: Ultimo bloco ``rateLimit`` recebido, util para diagnostico.
        self.ultimo_rate_limit = None

    def _log(self, mensagem: str) -> None:
        if self._registrar is not None:
            self._registrar(mensagem)

    def _requisitar(self, corpo: bytes) -> dict:
        """Faz um POST e devolve o JSON decodificado. Levanta excecao em erro HTTP."""
        requisicao = urllib.request.Request(
            self.endpoint,
            data=corpo,
            method="POST",
            headers={
                "Authorization": "Bearer %s" % self.token,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            },
        )
        with urllib.request.urlopen(requisicao, timeout=self.tempo_limite) as resposta:
            texto = resposta.read().decode("utf-8")
        return json.loads(texto)

    def _espera_por_cabecalho(self, erro: urllib.error.HTTPError) -> Optional[float]:
        """Extrai dos cabecalhos quanto tempo esperar antes de tentar de novo."""
        retry_after = erro.headers.get("Retry-After") if erro.headers else None
        if retry_after:
            try:
                return float(retry_after)
            except (TypeError, ValueError):
                pass

        restantes = erro.headers.get("x-ratelimit-remaining") if erro.headers else None
        reinicio = erro.headers.get("x-ratelimit-reset") if erro.headers else None
        if restantes == "0" and reinicio:
            try:
                return max(0.0, float(reinicio) - time.time()) + 1.0
            except (TypeError, ValueError):
                pass
        return None

    def executar(self, consulta: str, variaveis: dict) -> dict:
        """Executa a consulta e devolve o campo ``data`` da resposta.

        Erros transitorios (5xx, timeout, limite de requisicoes) sao repetidos
        com recuo exponencial. Erros de autenticacao e erros de GraphQL sem dado
        utilizavel sao propagados imediatamente.

        Quando a resposta traz ``data`` parcial junto de ``errors`` -- caso em
        que um repositorio isolado falhou mas os demais vieram --, os erros sao
        apenas registrados e os dados sao devolvidos, para nao perder a coleta
        inteira por um no defeituoso.
        """
        corpo = json.dumps({"query": consulta, "variables": variaveis}).encode("utf-8")
        ultimo_erro = None

        for tentativa in range(1, self.tentativas + 1):
            espera = self.espera_inicial * (2 ** (tentativa - 1))

            try:
                resposta = self._requisitar(corpo)
            except urllib.error.HTTPError as erro:
                if erro.code == 401:
                    raise ErroAutenticacao(
                        "Token rejeitado pelo GitHub (HTTP 401). Verifique se ele e valido "
                        "e nao expirou."
                    ) from erro
                if erro.code in (403, 429):
                    sugerida = self._espera_por_cabecalho(erro)
                    espera = sugerida if sugerida is not None else espera
                    ultimo_erro = ErroLimiteRequisicoes(
                        "Limite de requisicoes atingido (HTTP %d)." % erro.code
                    )
                elif 500 <= erro.code < 600:
                    ultimo_erro = ErroGitHub("Erro no servidor do GitHub (HTTP %d)." % erro.code)
                else:
                    detalhe = ""
                    try:
                        detalhe = erro.read().decode("utf-8", errors="replace")[:500]
                    except Exception:  # noqa: BLE001 - diagnostico best-effort
                        pass
                    raise ErroGitHub("Erro HTTP %d na API do GitHub. %s" % (erro.code, detalhe)) from erro
            except (urllib.error.URLError, OSError, json.JSONDecodeError) as erro:
                # OSError cobre socket.timeout, que so virou alias de TimeoutError
                # a partir do Python 3.10.
                ultimo_erro = ErroGitHub("Falha de rede ou resposta invalida: %s" % erro)
            else:
                dados = resposta.get("data")
                erros = resposta.get("errors") or []

                if dados and isinstance(dados.get("rateLimit"), dict):
                    self.ultimo_rate_limit = dados["rateLimit"]

                if erros and not dados:
                    tipos = {str(e.get("type", "")).upper() for e in erros if isinstance(e, dict)}
                    if "RATE_LIMITED" in tipos:
                        ultimo_erro = ErroLimiteRequisicoes("Limite de requisicoes do GraphQL atingido.")
                    else:
                        mensagens = "; ".join(_mensagem_de_erro(e) for e in erros)
                        raise ErroConsultaGraphQL("A consulta GraphQL falhou: %s" % mensagens, erros)
                else:
                    if erros:
                        self._log(
                            "[aviso] A resposta veio com %d erro(s) de GraphQL, mas com dados "
                            "parciais utilizaveis: %s"
                            % (len(erros), "; ".join(_mensagem_de_erro(e) for e in erros))
                        )
                    if not dados:
                        ultimo_erro = ErroGitHub("A API respondeu sem o campo 'data'.")
                    else:
                        return dados

            if tentativa < self.tentativas:
                self._log(
                    "[tentativa %d/%d] %s Nova tentativa em %.1fs."
                    % (tentativa, self.tentativas, ultimo_erro, espera)
                )
                self._dormir(espera)

        raise ultimo_erro or ErroGitHub("Falha desconhecida ao consultar a API do GitHub.")
