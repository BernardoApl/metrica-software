"""RQ74: coleta metadados atuais dos repositorios selecionados, com retomada."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlsplit
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap import DIRETORIO_DADOS, configurar_caminhos

configurar_caminhos()
from cliente_github import ClienteGitHub, ErroGitHub
from cliente_github import ErroAutenticacao, ErroLimiteRequisicoes, obter_token


CAMPOS = """
    id nameWithOwner url description homepageUrl
    createdAt updatedAt pushedAt stargazerCount forkCount diskUsage
    isFork isArchived isDisabled isEmpty visibility hasIssuesEnabled
    owner { login }
    primaryLanguage { name }
    licenseInfo { spdxId }
    defaultBranchRef { name }
    issues { totalCount }
    issuesFechadas: issues(states: CLOSED) { totalCount }
    pullRequests { totalCount }
    prsAceitos: pullRequests(states: MERGED) { totalCount }
    releases { totalCount }
"""
MAPA = {
    "id_github": "id", "nome_completo": "nameWithOwner", "url": "url",
    "descricao": "description", "homepage": "homepageUrl",
    "criado_em": "createdAt", "atualizado_em": "updatedAt", "ultimo_push_em": "pushedAt",
    "estrelas": "stargazerCount", "forks": "forkCount", "tamanho_kb": "diskUsage",
    "fork": "isFork", "arquivado": "isArchived", "desabilitado": "isDisabled",
    "vazio": "isEmpty", "visibilidade": "visibility", "issues_habilitadas": "hasIssuesEnabled",
}
ANINHADOS = {
    "proprietario": ("owner", "login"), "linguagem": ("primaryLanguage", "name"),
    "licenca_spdx": ("licenseInfo", "spdxId"), "branch_padrao": ("defaultBranchRef", "name"),
    "issues_total": ("issues", "totalCount"), "issues_fechadas": ("issuesFechadas", "totalCount"),
    "prs_total": ("pullRequests", "totalCount"), "prs_aceitos": ("prsAceitos", "totalCount"),
    "releases_total": ("releases", "totalCount"),
}
COLUNAS = ("nome_solicitado", "status", "coletado_em", "erro", *MAPA, *ANINHADOS,
           "status_metadados", "referencia_idade", "idade_dias", "idade_anos",
           "contribuidores_total", "status_contribuidores", "contribuidores_coletado_em",
           "contribuidores_erro")


def esperar(segundos):
    """Espera interruptivel, informando progresso sem encerrar a coleta."""
    while segundos > 0:
        print("Rate limit: aguardando %.0f segundos." % segundos, flush=True)
        intervalo = min(30, segundos)
        time.sleep(intervalo)
        segundos -= intervalo


def data_utc(texto):
    valor = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    if valor.tzinfo is None:
        raise ValueError("Data deve incluir fuso horario, por exemplo 2026-10-06T00:00:00Z.")
    return valor.astimezone(timezone.utc)


def calcular_idade(criado_em, referencia):
    dias = (data_utc(referencia) - data_utc(criado_em)).total_seconds() / 86400
    if dias < 0:
        raise ValueError("Criacao posterior a referencia de idade.")
    return round(dias, 6), round(dias / 365.25, 6)


def contar_contribuidores(status, corpo, link):
    if status == 204:
        return 0
    if not isinstance(corpo, list) or len(corpo) > 1:
        raise ValueError("Resposta inesperada para contributors?per_page=1.")
    ultima = re.search(r'<([^>]+)>;\s*rel="last"', link or "")
    if ultima:
        parametros = parse_qs(urlsplit(ultima.group(1)).query)
        pagina = int(parametros["page"][0])
        if parametros.get("per_page") != ["1"] or pagina < 1 or not corpo:
            raise ValueError("Paginacao de contribuidores inconsistente.")
        return pagina
    if 'rel="next"' in (link or ""):
        raise ValueError("Resposta paginada sem ultima pagina; contagem desconhecida.")
    return len(corpo)


class ClienteMetadados(ClienteGitHub):
    """Preserva erros parciais que o cliente comum apenas registra no console."""

    erros_graphql = ()

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("dormir", esperar)
        super().__init__(*args, **kwargs)

    def executar(self, consulta, variaveis):
        limite = self.ultimo_rate_limit or {}
        if limite.get("remaining") == 0 and limite.get("resetAt"):
            self._dormir(max(0, data_utc(limite["resetAt"]).timestamp() - time.time()) + 1)
        return super().executar(consulta, variaveis)

    def _requisitar(self, corpo):
        resposta = super()._requisitar(corpo)
        self.erros_graphql = resposta.get("errors") or []
        return resposta

    def contribuidores(self, nome):
        url = "https://api.github.com/repos/%s/contributors?per_page=1&anon=true" % nome
        for tentativa in range(self.tentativas):
            espera = 2 ** tentativa
            try:
                req = urllib.request.Request(url, headers={
                    "Authorization": "Bearer " + self.token,
                    "User-Agent": "metrica-software-rq74",
                    "Accept": "application/vnd.github+json",
                })
                with urllib.request.urlopen(req, timeout=self.tempo_limite) as resposta:
                    status = resposta.status
                    corpo = json.loads(resposta.read()) if status != 204 else []
                    link = resposta.headers.get("Link", "")
                    restantes = resposta.headers.get("X-RateLimit-Remaining")
                    reset = resposta.headers.get("X-RateLimit-Reset")
                total = contar_contribuidores(status, corpo, link)
                # Cache apenas da evidencia de contagem, sem nomes/emails de pessoas.
                return dict(total=total, url=url, http_status=status, link=link,
                            itens_primeira_pagina=len(corpo), coletado_em=agora(),
                            rate_limit_remaining=restantes, rate_limit_reset=reset)
            except urllib.error.HTTPError as erro:
                if erro.code == 401:
                    raise ErroAutenticacao("Token rejeitado pelo GitHub (HTTP 401).") from erro
                sugerida = self._espera_por_cabecalho(erro)
                if erro.code == 429 or (erro.code == 403 and sugerida is not None):
                    espera = sugerida if sugerida is not None else 60
                elif erro.code == 403:
                    mensagem = erro.read().decode("utf-8", errors="replace").lower()
                    if "secondary rate limit" in mensagem or "abuse" in mensagem:
                        espera = 60
                    else:
                        raise ErroGitHub("Contribuidores indisponiveis (HTTP 403).") from erro
                elif erro.code < 500:
                    raise ErroGitHub("Contribuidores indisponiveis (HTTP %d)." % erro.code) from erro
                falha = "HTTP %d" % erro.code
            except (OSError, ValueError) as erro:
                falha = str(erro)
            if tentativa + 1 < self.tentativas:
                self._dormir(espera)
        raise ErroGitHub("Falha ao coletar contribuidores: " + falha)


def agora():
    return datetime.now(timezone.utc).isoformat()


def ler_selecao(caminho):
    nomes = []
    vistos = set()
    with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
        leitor = csv.DictReader(arquivo)
        if "nome_completo" not in (leitor.fieldnames or []):
            raise ValueError("CSV sem coluna nome_completo.")
        for numero, linha in enumerate(leitor, 2):
            nome = (linha.get("nome_completo") or "").strip()
            if not re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+", nome):
                raise ValueError("Nome owner/repo invalido na linha %d." % numero)
            if nome.casefold() not in vistos:
                nomes.append(nome)
                vistos.add(nome.casefold())
    if not nomes:
        raise ValueError("A selecao esta vazia.")
    return nomes


def montar_consulta(nomes):
    variaveis, declaracoes, blocos = {}, [], []
    for i, nome in enumerate(nomes):
        owner, repo = nome.split("/")
        declaracoes.extend(["$o%d: String!" % i, "$n%d: String!" % i])
        variaveis.update({"o%d" % i: owner, "n%d" % i: repo})
        blocos.append("r%d: repository(owner: $o%d, name: $n%d) { %s }" % (i, i, i, CAMPOS))
    consulta = "query MetadadosRQ74(%s) { rateLimit { cost remaining resetAt } %s }" % (
        ", ".join(declaracoes), "\n".join(blocos))
    return consulta, variaveis


def normalizar(nome, no, erros=()):
    registro = dict.fromkeys(COLUNAS)
    registro.update(nome_solicitado=nome, coletado_em=agora(), bruto=no)
    if not isinstance(no, dict):
        registro.update(status="indisponivel", erro="Repositorio ausente ou inacessivel na resposta.")
    else:
        registro.update({destino: no.get(origem) for destino, origem in MAPA.items()})
        registro.update({destino: (no.get(pai) or {}).get(filho)
                         for destino, (pai, filho) in ANINHADOS.items()})
        faltantes = [campo for campo in MAPA.values() if campo not in no]
        for pai, filho in ANINHADOS.values():
            if pai not in no or (no[pai] is not None and filho not in no[pai]):
                faltantes.append(pai)
        obrigatorios = ("id", "nameWithOwner", "url", "createdAt", "updatedAt",
                        "stargazerCount", "forkCount", "owner", "issues", "issuesFechadas",
                        "pullRequests", "prsAceitos", "releases")
        faltantes.extend(campo for campo in obrigatorios if no.get(campo) is None)
        for pai in ("issues", "issuesFechadas", "pullRequests", "prsAceitos", "releases"):
            total = (no.get(pai) or {}).get("totalCount")
            if type(total) is not int or total < 0:
                faltantes.append(pai)
        registro["status"] = "incompleto" if faltantes else "ok"
        registro["erro"] = "Campos ausentes: " + ", ".join(sorted(set(faltantes))) if faltantes else None
    if erros:
        registro["status"] = "erro_graphql"
        registro["erro"] = "; ".join(str(e.get("message", "Erro GraphQL")) for e in erros)
    registro["status_metadados"] = registro["status"]
    registro["status_contribuidores"] = "pendente"
    return registro


def preparar_estado(nomes, entrada, saida, referencia=None):
    sha = hashlib.sha256(entrada.read_bytes()).hexdigest()
    if saida.exists():
        estado = json.loads(saida.read_text(encoding="utf-8"))
        meta = estado["metadados"]
        if (meta.get("selecao_sha256") != sha or meta.get("campos_graphql") != CAMPOS
                or [r["nome_solicitado"] for r in estado["repositorios"]] != nomes):
            raise ValueError("Saida existente pertence a outra selecao/esquema. Use --saida com outro nome.")
        anterior = meta.get("referencia_idade", meta["iniciado_em"])
        if referencia and data_utc(referencia) != data_utc(anterior):
            raise ValueError("Referencia de idade diferente do checkpoint. Use outra saida.")
        estado["metadados"]["referencia_idade"] = anterior
    else:
        estado = {"metadados": {"issue": 74, "fonte": "https://api.github.com/graphql",
                          "entrada": str(entrada.resolve()), "selecao_sha256": sha,
                          "campos_graphql": CAMPOS, "iniciado_em": agora(),
                          "referencia_idade": referencia or agora()},
            "repositorios": [dict(nome_solicitado=nome, status="pendente") for nome in nomes]}
    meta = estado["metadados"]
    data_utc(meta["referencia_idade"])
    meta.update(versao_esquema=2, fonte_contribuidores="GitHub REST contributors?per_page=1&anon=true")
    for r in estado["repositorios"]:
        r.setdefault("status_metadados", r["status"])
        r.setdefault("status_contribuidores", "pendente")
    atualizar_derivados(estado)
    return estado


def atualizar_derivados(estado):
    for r in estado["repositorios"]:
        r.setdefault("status_metadados", r["status"])
        r.setdefault("status_contribuidores", "pendente")
        r["referencia_idade"] = estado["metadados"].get("referencia_idade")
        r["idade_dias"] = r["idade_anos"] = None
        if r.get("criado_em") and r["referencia_idade"]:
            try:
                r["idade_dias"], r["idade_anos"] = calcular_idade(r["criado_em"], r["referencia_idade"])
            except ValueError:
                pass
        r["status"] = ("ok" if r["status_metadados"] == "ok"
                       and r["status_contribuidores"] == "ok" and r["idade_dias"] is not None
                       else "incompleto")


def substituir_com_retentativa(temporario, destino):
    """Tolera bloqueios breves do arquivo por indexadores/antivirus no Windows."""
    for tentativa in range(6):
        try:
            temporario.replace(destino)
            return
        except PermissionError:
            if tentativa == 5:
                raise
            time.sleep(0.2 * (tentativa + 1))


def salvar(estado, saida):
    atualizar_derivados(estado)
    registros = estado["repositorios"]
    ok = sum(r["status"] == "ok" for r in registros)
    estado["metadados"].update(atualizado_em=agora(), total=len(registros),
                                 coletados_ok=ok, pendentes_ou_falhos=len(registros) - ok,
                                 concluido=ok == len(registros))
    saida.parent.mkdir(parents=True, exist_ok=True)
    temporario = saida.with_suffix(".json.tmp")
    temporario.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")
    substituir_com_retentativa(temporario, saida)
    csv_saida = saida.with_suffix(".csv")
    csv_temporario = csv_saida.with_suffix(".csv.tmp")
    with csv_temporario.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS, extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(registros)
    substituir_com_retentativa(csv_temporario, csv_saida)


def coletar(cliente, estado, saida, tamanho_lote=10):
    if not 1 <= tamanho_lote <= 20:
        raise ValueError("O tamanho do lote deve estar entre 1 e 20.")
    pendentes = [i for i, r in enumerate(estado["repositorios"])
                 if r.get("status_metadados", r["status"]) != "ok"]
    salvar(estado, saida)
    for inicio in range(0, len(pendentes), tamanho_lote):
        indices = pendentes[inicio:inicio + tamanho_lote]
        nomes = [estado["repositorios"][i]["nome_solicitado"] for i in indices]
        consulta, variaveis = montar_consulta(nomes)
        cliente.erros_graphql = []
        try:
            dados = cliente.executar(consulta, variaveis)
        except (ErroAutenticacao, ErroLimiteRequisicoes):
            raise
        except ErroGitHub as erro:
            for i, nome in zip(indices, nomes):
                estado["repositorios"][i] = dict(nome_solicitado=nome, status="erro_coleta",
                                                coletado_em=agora(), erro=str(erro))
            salvar(estado, saida)
            raise
        for alias, (i, nome) in enumerate(zip(indices, nomes)):
            erros = [e for e in cliente.erros_graphql
                     if not e.get("path") or e["path"][0] == "r%d" % alias]
            estado["repositorios"][i] = normalizar(nome, dados.get("r%d" % alias), erros)
        estado["metadados"]["rate_limit"] = cliente.ultimo_rate_limit
        salvar(estado, saida)
        print("RQ74: %d/%d com metadados gerais; %d completos incluindo contribuidores." % (
            sum(r.get("status_metadados") == "ok" for r in estado["repositorios"]),
            len(estado["repositorios"]), estado["metadados"]["coletados_ok"]), flush=True)
    return estado


def complementar_contribuidores(cliente, estado, saida, trabalhadores=1):
    if not 1 <= trabalhadores <= 4:
        raise ValueError("Use entre 1 e 4 trabalhadores para contribuidores.")
    pendentes = [r for r in estado["repositorios"]
                 if r.get("status_metadados") == "ok" and r.get("status_contribuidores") != "ok"]

    def consultar(registro):
        try:
            return cliente.contribuidores(registro["nome_completo"]), None
        except ErroAutenticacao:
            raise
        except ErroGitHub as erro:
            return None, str(erro)

    # So a thread principal altera o checkpoint. No maximo 25 respostas ficam
    # em memoria entre gravacoes; interrupcoes normais tambem salvam no finally.
    with ThreadPoolExecutor(max_workers=trabalhadores) as executor:
        for inicio in range(0, len(pendentes), 25):
            lote = pendentes[inicio:inicio + 25]
            reinicio = None
            try:
                for registro, (evidencia, erro) in zip(lote, executor.map(consultar, lote)):
                    if erro is not None:
                        registro.update(status_contribuidores="erro", contribuidores_total=None,
                                        contribuidores_erro=erro, contribuidores_coletado_em=agora())
                        registro.pop("contribuidores_evidencia", None)
                    else:
                        registro.update(status_contribuidores="ok", contribuidores_total=evidencia["total"],
                                        contribuidores_coletado_em=evidencia["coletado_em"],
                                        contribuidores_erro=None, contribuidores_evidencia=evidencia)
                        if evidencia.get("rate_limit_remaining") == "0" and evidencia.get("rate_limit_reset"):
                            reinicio = max(reinicio or 0, float(evidencia["rate_limit_reset"]))
            finally:
                salvar(estado, saida)
            print("Contribuidores: %d/%d completos; %d/%d pendencias processadas nesta execucao." % (
                estado["metadados"]["coletados_ok"], len(estado["repositorios"]),
                inicio + len(lote), len(pendentes)), flush=True)
            if reinicio:
                cliente._dormir(max(0, reinicio - time.time()) + 1)


def principal(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entrada", type=Path, default=DIRETORIO_DADOS / "repositorios_selecionados.csv")
    parser.add_argument("--saida", type=Path, default=DIRETORIO_DADOS / "rq74_metadados_repositorios.json")
    parser.add_argument("--tamanho-lote", type=int, choices=range(1, 21), default=10)
    parser.add_argument("--trabalhadores-contribuidores", type=int, choices=range(1, 5), default=1)
    parser.add_argument("--referencia-idade", help="Data ISO 8601 com fuso; padrao: inicio da coleta.")
    parser.add_argument("--somente-cache", action="store_true", help="Atualiza derivados sem acessar a API.")
    args = parser.parse_args(argv)
    try:
        if args.saida.suffix.lower() != ".json":
            raise ValueError("A saida deve terminar em .json; o CSV e gerado ao lado.")
        if args.entrada.resolve() in (args.saida.resolve(), args.saida.with_suffix(".csv").resolve()):
            raise ValueError("A saida nao pode sobrescrever a selecao.")
        nomes = ler_selecao(args.entrada)
        estado = preparar_estado(nomes, args.entrada, args.saida, args.referencia_idade)
        salvar(estado, args.saida)
        if not args.somente_cache and any(r["status"] != "ok" for r in estado["repositorios"]):
            cliente = ClienteMetadados(obter_token())
            coletar(cliente, estado, args.saida, args.tamanho_lote)
            complementar_contribuidores(cliente, estado, args.saida, args.trabalhadores_contribuidores)
        else:
            salvar(estado, args.saida)
        return 0 if estado["metadados"]["concluido"] else 1
    except (OSError, ValueError, KeyError, ErroGitHub) as erro:
        print("[erro] %s" % erro, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrompido. Reexecute o comando para retomar os lotes salvos.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(principal())
