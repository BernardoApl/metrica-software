"""RQ73: amplia candidatos populares por faixas de estrelas, sem filtros DORA."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap import DIRETORIO_DADOS, configurar_caminhos

configurar_caminhos()
from cliente_github import ClienteGitHub, ErroGitHub, ErroAutenticacao, obter_token
from rq74_metadados_repositorios import agora, esperar


COLUNAS = ("id_github", "nome_completo", "url", "estrelas", "linguagem",
           "branch_padrao", "criado_em", "arquivado", "fork", "coletado_em")


def salvar_json(caminho, dados):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    temporario.replace(caminho)


def salvar_csv(caminho, linhas, colunas):
    temporario = caminho.with_suffix(".csv.tmp")
    with temporario.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=colunas, extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(linhas)
    temporario.replace(caminho)


class BuscaGitHub(ClienteGitHub):
    def __init__(self, token, cache, **kwargs):
        kwargs.setdefault("dormir", esperar)
        super().__init__(token, **kwargs)
        self.cache = cache
        self.proxima_requisicao = 0

    def buscar(self, consulta, pagina=1):
        url = "https://api.github.com/search/repositories?" + urlencode({
            "q": consulta, "sort": "stars", "order": "desc", "per_page": 100, "page": pagina})
        caminho = self.cache / (hashlib.sha256(url.encode()).hexdigest() + ".json")
        if caminho.exists():
            salvo = json.loads(caminho.read_text(encoding="utf-8"))
            if salvo["url"] != url:
                raise ValueError("Cache pertence a outra consulta.")
            return salvo
        for tentativa in range(self.tentativas):
            atraso = self.proxima_requisicao - time.time()
            if atraso > 0:
                self._dormir(atraso)
            espera = 2 ** tentativa
            try:
                req = urllib.request.Request(url, headers={
                    "Authorization": "Bearer " + self.token,
                    "Accept": "application/vnd.github+json", "User-Agent": "metrica-software-rq73"})
                with urllib.request.urlopen(req, timeout=self.tempo_limite) as resposta:
                    dados = json.loads(resposta.read())
                    headers = {campo: resposta.headers.get(campo) for campo in (
                        "Link", "X-RateLimit-Remaining", "X-RateLimit-Reset")}
                if dados.get("incomplete_results"):
                    raise ValueError("Busca retornou incomplete_results=true; repetir sem assumir cobertura.")
                if not isinstance(dados.get("items"), list) or type(dados.get("total_count")) is not int:
                    raise ValueError("Resposta de busca invalida.")
                if headers["X-RateLimit-Remaining"] == "0" and headers["X-RateLimit-Reset"]:
                    self.proxima_requisicao = float(headers["X-RateLimit-Reset"]) + 1
                salvo = dict(url=url, coletado_em=agora(), cabecalhos=headers, resposta=dados)
                salvar_json(caminho, salvo)
                return salvo
            except urllib.error.HTTPError as erro:
                if erro.code == 401:
                    raise ErroAutenticacao("Token rejeitado pelo GitHub (HTTP 401).") from erro
                sugerida = self._espera_por_cabecalho(erro)
                if erro.code in (403, 429):
                    espera = sugerida if sugerida is not None else 60
                elif erro.code < 500:
                    raise ErroGitHub("Busca falhou (HTTP %d)." % erro.code) from erro
                falha = "HTTP %d" % erro.code
            except (OSError, ValueError) as erro:
                falha = str(erro)
            if tentativa + 1 < self.tentativas:
                self._dormir(espera)
        raise ErroGitHub("Falha na busca: " + falha)


def coletar(cliente, limite=4000, minimo_estrelas=1000, ao_salvar=None):
    if limite < 1 or minimo_estrelas < 0:
        raise ValueError("Limite deve ser positivo e minimo de estrelas nao negativo.")
    base = "is:public stars:>%d" % minimo_estrelas
    raiz = cliente.buscar(base)
    resultado = {"metadados": dict(issue=73, tipo="candidatos_nao_validados_para_DORA",
                 criterio=base, limite_solicitado=limite, iniciado_em=raiz["coletado_em"],
                 total_informado_pela_busca=raiz["resposta"]["total_count"],
                 registros_examinados=0, duplicados=0, rejeitados=0, particoes=[],
                 concluido=False), "repositorios": []}
    meta = resultado["metadados"]
    vistos, nomes = set(), set()

    def emitir():
        resultado["repositorios"].sort(key=lambda r: (-r["estrelas"], r["nome_completo"].casefold()))
        meta.update(total_coletado=len(vistos), atualizado_em=agora(),
                    meta_atingida=len(vistos) >= limite)
        if ao_salvar:
            ao_salvar(resultado)

    def adicionar(pagina):
        for repo in pagina["resposta"]["items"]:
            if len(vistos) >= limite:
                break
            meta["registros_examinados"] += 1
            ident, nome, estrelas = repo.get("id"), repo.get("full_name"), repo.get("stargazers_count")
            if (type(ident) is not int or not nome or type(estrelas) is not int
                    or estrelas <= minimo_estrelas or repo.get("private") is not False):
                meta["rejeitados"] += 1
                continue
            if ident in vistos or nome.casefold() in nomes:
                meta["duplicados"] += 1
                continue
            vistos.add(ident)
            nomes.add(nome.casefold())
            resultado["repositorios"].append(dict(
                id_github=ident, nome_completo=nome, url=repo.get("html_url"), estrelas=estrelas,
                linguagem=repo.get("language"), branch_padrao=repo.get("default_branch"),
                criado_em=repo.get("created_at"), arquivado=repo.get("archived"),
                fork=repo.get("fork"), coletado_em=pagina["coletado_em"]))
        emitir()

    def visitar(inferior, superior, primeira=None):
        if len(vistos) >= limite:
            return
        consulta = "is:public stars:%d..%d" % (inferior, superior)
        primeira = primeira or cliente.buscar(consulta)
        total = primeira["resposta"]["total_count"]
        if total > 1000:
            if inferior == superior:
                raise ErroGitHub("Mais de 1000 repositorios com %d estrelas; subdivisao adicional necessaria." % inferior)
            meio = (inferior + superior) // 2
            visitar(meio + 1, superior)
            visitar(inferior, meio)
            return
        meta["particoes"].append(dict(consulta=consulta, total_informado=total))
        adicionar(primeira)
        for pagina in range(2, math.ceil(total / 100) + 1):
            if len(vistos) >= limite:
                break
            resposta = cliente.buscar(consulta, pagina)
            if resposta["resposta"]["total_count"] > 1000:
                raise ErroGitHub("Faixa cresceu acima de 1000 durante a coleta. Use novo cache.")
            adicionar(resposta)

    if raiz["resposta"]["items"]:
        maximo = raiz["resposta"]["items"][0]["stargazers_count"]
        visitar(minimo_estrelas + 1, maximo)
    meta["concluido"] = True
    emitir()
    return resultado


def exportar(resultado, saida):
    salvar_json(saida, resultado)
    salvar_csv(saida.with_suffix(".csv"), resultado["repositorios"], COLUNAS)
    meta = resultado["metadados"]
    examinados = meta["registros_examinados"]
    validos = examinados - meta["rejeitados"]
    unicos = validos - meta["duplicados"]
    funil = [
        dict(etapa="registros_examinados", entrada=examinados, removidos=0, restantes=examinados),
        dict(etapa="publicos_dentro_do_criterio_com_identidade_valida", entrada=examinados,
             removidos=meta["rejeitados"], restantes=validos),
        dict(etapa="candidatos_unicos", entrada=validos, removidos=meta["duplicados"], restantes=unicos),
    ]
    salvar_csv(saida.with_name(saida.stem + "_funil.csv"), funil,
               ("etapa", "entrada", "removidos", "restantes"))
    print("RQ73: %d candidatos unicos salvos." % unicos, flush=True)


def principal(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limite", type=int, default=4000)
    parser.add_argument("--minimo-estrelas", type=int, default=1000)
    parser.add_argument("--cache", type=Path, default=DIRETORIO_DADOS / ".cache" / "rq73_busca")
    parser.add_argument("--saida", type=Path, default=DIRETORIO_DADOS / "rq73_candidatos.json")
    args = parser.parse_args(argv)
    try:
        if args.saida.suffix.lower() != ".json":
            raise ValueError("Informe uma saida .json; CSV e funil sao gerados ao lado.")
        cliente = BuscaGitHub(obter_token(), args.cache)
        resultado = coletar(cliente, args.limite, args.minimo_estrelas,
                            lambda r: exportar(r, args.saida))
        return 0 if resultado["metadados"]["meta_atingida"] else 1
    except (ValueError, OSError, ErroGitHub) as erro:
        print("[erro] %s" % erro, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrompido. Reexecute para aproveitar as respostas em cache.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(principal())
