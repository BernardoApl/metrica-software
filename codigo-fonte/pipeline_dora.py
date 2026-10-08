"""RQ80: pipeline DORA do LAB03, executado com um unico comando.

    python codigo-fonte/pipeline_dora.py --config config/pipeline.json

Etapas:

1. candidatos e metadados (RQ73/RQ74). Se o CSV de metadados configurado nao
   existir, os scripts ``rq73_coletar_candidatos.py`` e
   ``rq74_metadados_repositorios.py`` sao executados antes;
2. pre-filtro sem API: metadados ok, nao e fork, nao esta arquivado/desabilitado/
   vazio e tem default branch;
3. em ordem decrescente de estrelas, cada candidato passa por: usa GitHub
   Actions -> >= 5 releases publicadas na janela -> >= 50 workflow runs validos
   no default branch. As chamadas mais caras (runs mes a mes) so acontecem para
   quem passou pelas anteriores. A avaliacao para quando a meta de repositorios
   e atingida. Repositorios com mais runs na janela do que
   ``limite_runs_por_repositorio`` tem a coleta interrompida ao passar do
   limite (custo de API) e sao descartados; o descarte aparece no funil;
4. calculo das metricas (frequencia de deploy, CFR de CI, tempo de recuperacao
   e classes DORA) e exportacao de CSVs + funil de selecao.

Todas as respostas da API ficam em cache (``diretorio_cache``): interrompido
por rate limit, queda de rede ou Ctrl+C, basta rodar o mesmo comando de novo.
O token e lido de ``GITHUB_TOKEN`` (ou ``.env``), nunca do repositorio.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import subprocess
import sys
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Optional

RAIZ_CODIGO = Path(__file__).resolve().parent
RAIZ_PROJETO = RAIZ_CODIGO.parent
sys.path.insert(0, str(RAIZ_CODIGO))
from bootstrap import configurar_caminhos  # noqa: E402

configurar_caminhos()
from cliente_github import ErroAutenticacao, obter_token  # noqa: E402
from cliente_rest import ClienteREST, ErroREST  # noqa: E402
import coleta_dora  # noqa: E402
from metricas import ci, dora, lead_time  # noqa: E402

CONFIG_PADRAO = {
    "janela": {"inicio": "2025-10-01", "fim": "2026-09-30"},
    "meta_repositorios": 100,
    "criterios": {"minimo_releases": 5, "minimo_runs_validos": 50},
    "limite_runs_por_repositorio": 20000,
    "limite_paginas_compare": 20,
    "trabalhadores": 4,
    "candidatos": {
        "limite_busca": 8000,
        "saida_busca": "dados/rq73_candidatos_8000.json",
        "metadados": "dados/rq74_metadados_candidatos_8000.csv",
    },
    "diretorio_cache": "dados/.cache/lab03_rest",
    "diretorio_saida": "dados/lab03",
}

INCLUIDO = "incluido"
MOTIVOS_PRE_FILTRO = {
    "metadados_indisponiveis": "metadados RQ74 com status diferente de ok",
    "fork": "repositorio e fork",
    "arquivado_ou_desabilitado": "repositorio arquivado, desabilitado ou vazio",
    "sem_default_branch": "sem default branch",
}

COLUNAS_AVALIACAO = ("posicao", "nome_completo", "estrelas", "motivo", "workflows_total",
                     "releases_janela", "runs_total_informado", "runs_validos", "erro")
COLUNAS_METRICAS = (
    "nome_completo", "url", "estrelas", "linguagem", "criado_em", "idade_anos",
    "contribuidores_total", "branch_padrao", "workflows_total",
    "releases_janela", "prereleases_janela", "frequencia_deploy_semana",
    "runs_coletados", "runs_validos", "runs_falha", "runs_sucesso", "cfr_ci",
    "recuperacao_mediana_horas", "episodios_falha", "episodios_completos",
    "episodios_censurados", "episodios_censura_esquerda", "proporcao_episodios_censurados",
    "intervalos_no_teto",
    "lead_time_release_mediana_dias", "lead_time_commit_mediana_dias",
    "releases_com_lead_time", "commits_com_lead_time", "releases_sem_anterior",
    "releases_sem_commits", "releases_compare_indisponivel", "releases_compare_truncado",
    "commits_negativos",
    "classe_frequencia", "classe_lead_time", "classe_cfr", "classe_recuperacao", "classe_geral",
)
COLUNAS_RELEASES = ("nome_completo", *coleta_dora.CAMPOS_RELEASE, "dentro_janela")
COLUNAS_RUNS = ("nome_completo", *coleta_dora.CAMPOS_RUN)
COLUNAS_FUNIL = ("etapa", "criterio", "entrada", "removidos_na_etapa", "aprovados")
COLUNAS_INTERVALOS = ("nome_completo", "intervalo", "total_informado", "coletados", "subdividido")
COLUNAS_LEAD_TIME = ("nome_completo", "tag_name", "anterior", "published_at", "commits",
                     "commits_negativos", "truncado", "lead_time_dias", "motivo")
COLUNAS_COMMITS = ("nome_completo", "tag_name", "anterior", *coleta_dora.CAMPOS_COMMIT)


# ---------------------------------------------------------------- configuracao
def _mesclar(base: dict, extra: dict) -> dict:
    resultado = dict(base)
    for chave, valor in extra.items():
        if isinstance(valor, dict) and isinstance(resultado.get(chave), dict):
            resultado[chave] = _mesclar(resultado[chave], valor)
        else:
            resultado[chave] = valor
    return resultado


def carregar_config(caminho: Optional[Path]) -> dict:
    config = CONFIG_PADRAO
    if caminho is not None:
        config = _mesclar(CONFIG_PADRAO, json.loads(Path(caminho).read_text(encoding="utf-8")))
    inicio = coleta_dora.para_data(config["janela"]["inicio"])
    fim = coleta_dora.para_data(config["janela"]["fim"])
    if fim < inicio:
        raise ValueError("janela.fim anterior a janela.inicio")
    if config["meta_repositorios"] < 1:
        raise ValueError("meta_repositorios precisa ser positiva")
    return config


def caminho_projeto(relativo: str) -> Path:
    caminho = Path(relativo)
    return caminho if caminho.is_absolute() else RAIZ_PROJETO / caminho


# ------------------------------------------------------------------ candidatos
def preparar_candidatos(config: dict, executar=subprocess.run) -> Path:
    """Garante o CSV de metadados, rodando RQ73 e RQ74 se ele ainda nao existir."""
    metadados = caminho_projeto(config["candidatos"]["metadados"])
    if metadados.exists():
        return metadados
    busca = caminho_projeto(config["candidatos"]["saida_busca"])
    coleta = RAIZ_CODIGO / "coleta"
    if not busca.with_suffix(".csv").exists():
        executar([sys.executable, str(coleta / "rq73_coletar_candidatos.py"),
                  "--limite", str(config["candidatos"]["limite_busca"]),
                  "--saida", str(busca)], check=True)
    executar([sys.executable, str(coleta / "rq74_metadados_repositorios.py"),
              "--entrada", str(busca.with_suffix(".csv")),
              "--saida", str(metadados.with_suffix(".json"))], check=True)
    return metadados


def _inteiro(valor) -> int:
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return 0


def ler_candidatos(caminho: Path) -> list[dict]:
    with Path(caminho).open(encoding="utf-8", newline="") as arquivo:
        candidatos = list(csv.DictReader(arquivo))
    vistos = set()
    unicos = []
    for candidato in sorted(candidatos, key=lambda c: (-_inteiro(c.get("estrelas")),
                                                      (c.get("nome_completo") or "").casefold())):
        chave = (candidato.get("nome_completo") or candidato.get("nome_solicitado") or "").casefold()
        if chave and chave not in vistos:
            vistos.add(chave)
            unicos.append(candidato)
    return unicos


def _verdadeiro(valor) -> bool:
    return str(valor).strip().lower() in ("true", "1", "sim")


def motivo_pre_filtro(candidato: dict) -> Optional[str]:
    if candidato.get("status_metadados", candidato.get("status")) != "ok":
        return "metadados_indisponiveis"
    if _verdadeiro(candidato.get("fork")):
        return "fork"
    if any(_verdadeiro(candidato.get(c)) for c in ("arquivado", "desabilitado", "vazio")):
        return "arquivado_ou_desabilitado"
    if not (candidato.get("branch_padrao") or "").strip():
        return "sem_default_branch"
    return None


# ------------------------------------------------------------------- avaliacao
def avaliar_repositorio(cliente, candidato: dict, config: dict) -> dict:
    """Aplica os criterios da mais barata para a mais cara e coleta o necessario."""
    nome = candidato["nome_completo"]
    branch = candidato["branch_padrao"]
    inicio, fim = config["janela"]["inicio"], config["janela"]["fim"]
    criterios = config["criterios"]
    avaliacao = {"nome_completo": nome, "estrelas": _inteiro(candidato.get("estrelas"))}

    workflows = coleta_dora.contar_workflows(cliente, nome)
    avaliacao["workflows_total"] = workflows["total"]
    if workflows["status"] != 200:
        return dict(avaliacao, motivo="inacessivel", erro="workflows HTTP %s" % workflows["status"])
    if not workflows["total"]:
        return dict(avaliacao, motivo="sem_actions")

    coleta_releases = coleta_dora.coletar_releases(cliente, nome, inicio, fim)
    if coleta_releases["status"] != 200:
        return dict(avaliacao, motivo="inacessivel",
                    erro="releases HTTP %s" % coleta_releases["status"])
    validas = coleta_dora.releases_validas(coleta_releases["releases"])
    avaliacao["releases_janela"] = len(validas)
    if len(validas) < criterios["minimo_releases"]:
        return dict(avaliacao, motivo="poucas_releases")

    total = coleta_dora.total_de_runs(cliente, nome, branch, inicio, fim)
    avaliacao["runs_total_informado"] = total["total"]
    if total["status"] != 200:
        return dict(avaliacao, motivo="inacessivel", erro="runs HTTP %s" % total["status"])
    if total["total"] < criterios["minimo_runs_validos"]:
        return dict(avaliacao, motivo="poucos_runs", runs_validos=None)

    try:
        coleta_runs = coleta_dora.coletar_runs(cliente, nome, branch, inicio, fim,
                                               config.get("limite_runs_por_repositorio"))
    except coleta_dora.LimiteDeRunsExcedido:
        return dict(avaliacao, motivo="runs_acima_do_limite")
    except coleta_dora.ErroColeta as erro:
        return dict(avaliacao, motivo="inacessivel", erro=str(erro))
    abertura, fechamento = coleta_dora.limites_da_janela(inicio, fim)
    metricas = ci.metricas_ci_repositorio(coleta_runs["runs"], branch, abertura, fechamento)
    avaliacao["runs_validos"] = metricas["runs_validos"]
    if metricas["runs_validos"] < criterios["minimo_runs_validos"]:
        return dict(avaliacao, motivo="poucos_runs")

    frequencia = dora.frequencia_de_deploy(len(validas), coleta_dora.semanas_da_janela(inicio, fim))
    lead = calcular_lead_time(cliente, nome, coleta_releases["releases"], config)
    # Combinacao de referencia (C1 da RQ 07): lead time (a), por release.
    classes = dora.classificar_repositorio(
        frequencia, lead["metricas"]["lead_time_release_mediana_dias"], metricas["cfr_ci"],
        metricas["recuperacao_mediana_horas"])
    linha = {
        "nome_completo": nome,
        "url": candidato.get("url"),
        "estrelas": avaliacao["estrelas"],
        "linguagem": candidato.get("linguagem"),
        "criado_em": candidato.get("criado_em"),
        "idade_anos": candidato.get("idade_anos"),
        "contribuidores_total": candidato.get("contribuidores_total"),
        "branch_padrao": branch,
        "workflows_total": workflows["total"],
        "releases_janela": len(validas),
        "prereleases_janela": len(coleta_dora.releases_validas(
            coleta_releases["releases"], incluir_prerelease=True)) - len(validas),
        "frequencia_deploy_semana": frequencia,
        "runs_coletados": len(coleta_runs["runs"]),
        "intervalos_no_teto": len(coleta_runs["teto_atingido"]),
        **metricas,
        **lead["metricas"],
        **{k: v for k, v in classes.items() if k in COLUNAS_METRICAS},
    }
    return dict(avaliacao, motivo=INCLUIDO, metricas=linha,
                releases=coleta_releases["releases"], runs=coleta_runs["runs"],
                intervalos=coleta_runs["intervalos"], lead_time=lead["releases"],
                commits=lead["commits"])


def calcular_lead_time(cliente, nome: str, releases: list[dict], config: dict) -> dict:
    """RQ76: ``compare`` de cada release da janela com a anterior e lead time (a) e (b).

    Um ``compare`` que falha mesmo depois das tentativas do cliente (ex.: 5xx
    persistente em comparacoes enormes) nao derruba o repositorio: a release
    conta como ``compare_indisponivel`` e, como a falha nao vai para o cache, a
    proxima execucao tenta de novo.
    """
    avaliacoes, commits = [], []
    for anterior, release in lead_time.pares_de_releases(releases):
        compare = None
        if anterior is not None:
            try:
                compare = coleta_dora.coletar_compare(cliente, nome, anterior["tag_name"],
                                                      release["tag_name"],
                                                      config.get("limite_paginas_compare"))
            except ErroREST:
                compare = {"status": None, "commits": []}
        avaliacao = lead_time.avaliar_release(release, anterior, compare)
        avaliacoes.append(avaliacao)
        for commit in (compare or {}).get("commits") or []:
            commits.append(dict(commit, tag_name=release["tag_name"],
                                anterior=avaliacao["anterior"]))
    return {"metricas": lead_time.metricas_lead_time(avaliacoes),
            "releases": [{k: v for k, v in a.items() if k != "lead_times_commits"}
                         for a in avaliacoes],
            "commits": commits}


def executar(cliente, candidatos: list[dict], config: dict,
             registrar: Callable[[str], None] = print) -> dict:
    """Avalia os aptos em ordem de estrelas ate a meta.

    Com ``trabalhadores > 1`` os proximos candidatos sao avaliados em paralelo
    (ate ``4 * trabalhadores`` enfileirados),
    mas os resultados sao consumidos estritamente na ordem de estrelas: a
    amostra e o funil saem identicos aos de uma execucao sequencial. Candidatos
    adiantados depois de a meta ser atingida sao descartados (contam como nao
    avaliados); as respostas deles ficam no cache.
    """
    meta = config["meta_repositorios"]
    pre_filtrados = []
    aptos = []
    for candidato in candidatos:
        motivo = motivo_pre_filtro(candidato)
        if motivo:
            pre_filtrados.append((candidato, motivo))
        else:
            aptos.append(candidato)

    avaliacoes, amostra, releases, runs, intervalos = [], [], [], [], []
    lead_times, commits = [], []
    trabalhadores = max(1, int(config.get("trabalhadores") or 1))
    executor = ThreadPoolExecutor(max_workers=trabalhadores)
    pendentes: deque = deque()
    proximo = 0
    try:
        while len(amostra) < meta and (pendentes or proximo < len(aptos)):
            # Enfileira alem dos trabalhadores para que um repositorio lento na
            # frente da fila nao deixe os demais ociosos.
            while proximo < len(aptos) and len(pendentes) < trabalhadores * 4:
                pendentes.append(executor.submit(avaliar_repositorio, cliente, aptos[proximo], config))
                proximo += 1
            avaliacao = pendentes.popleft().result()
            avaliacao["posicao"] = len(avaliacoes) + 1
            avaliacoes.append(avaliacao)
            if avaliacao["motivo"] == INCLUIDO:
                amostra.append(avaliacao["metricas"])
                nome = avaliacao["nome_completo"]
                releases.extend(dict(r, nome_completo=nome) for r in avaliacao["releases"])
                runs.extend(dict(r, nome_completo=nome) for r in avaliacao["runs"])
                intervalos.extend(dict(i, nome_completo=nome)
                                  for i in avaliacao.get("intervalos", []))
                lead_times.extend(dict(l, nome_completo=nome)
                                  for l in avaliacao.get("lead_time", []))
                commits.extend(dict(c, nome_completo=nome) for c in avaliacao.get("commits", []))
            registrar("[%d/%d aprovados | candidato %d] %s: %s"
                      % (len(amostra), meta, avaliacao["posicao"], avaliacao["nome_completo"],
                         avaliacao["motivo"]))
    finally:
        executor.shutdown(wait=True, cancel_futures=True)

    return {
        "funil": montar_funil(len(candidatos), pre_filtrados, len(aptos), avaliacoes, config),
        "avaliacoes": avaliacoes,
        "pre_filtrados": pre_filtrados,
        "amostra": amostra,
        "releases": releases,
        "runs": runs,
        "intervalos": intervalos,
        "lead_time": lead_times,
        "commits": commits,
    }


def montar_funil(total: int, pre_filtrados: list, aptos: int, avaliacoes: list[dict],
                 config: dict) -> list[dict]:
    criterios = config["criterios"]
    etapas = [{"etapa": "candidatos_iniciais", "criterio": "candidatos com metadados RQ74",
               "entrada": total, "removidos_na_etapa": 0, "aprovados": total}]

    def adicionar(etapa, criterio, removidos):
        entrada = etapas[-1]["aprovados"]
        etapas.append({"etapa": etapa, "criterio": criterio, "entrada": entrada,
                       "removidos_na_etapa": removidos, "aprovados": entrada - removidos})

    adicionar("metadados_validos_e_ativos",
              "status ok; nao e fork; nao arquivado/desabilitado/vazio; com default branch",
              len(pre_filtrados))
    adicionar("avaliados_ate_a_meta",
              "candidatos avaliados, por estrelas, ate atingir %d repositorios"
              % config["meta_repositorios"], aptos - len(avaliacoes))
    motivos = [a["motivo"] for a in avaliacoes]
    adicionar("api_acessivel", "workflows, releases e runs acessiveis pela API",
              motivos.count("inacessivel"))
    adicionar("usa_github_actions", "actions/workflows com total_count > 0",
              motivos.count("sem_actions"))
    adicionar("minimo_releases", ">= %d releases publicadas (nao draft, nao pre-release) na janela"
              % criterios["minimo_releases"], motivos.count("poucas_releases"))
    adicionar("limite_operacional_runs",
              "ate %s workflow runs de push no default branch na janela (custo de coleta)"
              % config.get("limite_runs_por_repositorio"), motivos.count("runs_acima_do_limite"))
    adicionar("minimo_runs", ">= %d workflow runs validos (push, default branch) na janela"
              % criterios["minimo_runs_validos"], motivos.count("poucos_runs"))
    return etapas


# ------------------------------------------------------------------ exportacao
def _formatar(valor):
    if isinstance(valor, float):
        return round(valor, 6)
    return valor


def salvar_csv(caminho: Path, linhas, colunas, comprimir: bool = False) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_name(caminho.name + ".tmp")
    abrir = gzip.open if comprimir else open
    with abrir(temporario, "wt", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=colunas, extrasaction="ignore")
        escritor.writeheader()
        for linha in linhas:
            escritor.writerow({k: _formatar(v) for k, v in linha.items()})
    temporario.replace(caminho)


def exportar(resultado: dict, config: dict, cliente=None) -> Path:
    saida = caminho_projeto(config["diretorio_saida"])
    salvar_csv(saida / "funil_selecao.csv", resultado["funil"], COLUNAS_FUNIL)
    avaliados = list(resultado["avaliacoes"])
    salvar_csv(saida / "candidatos_avaliados.csv", avaliados, COLUNAS_AVALIACAO)
    salvar_csv(saida / "metricas_repositorios.csv", resultado["amostra"], COLUNAS_METRICAS)
    salvar_csv(saida / "releases.csv", resultado["releases"], COLUNAS_RELEASES)
    salvar_csv(saida / "workflow_runs.csv.gz", resultado["runs"], COLUNAS_RUNS, comprimir=True)
    salvar_csv(saida / "intervalos_runs.csv", resultado.get("intervalos", []), COLUNAS_INTERVALOS)
    salvar_csv(saida / "lead_time_releases.csv", resultado.get("lead_time", []), COLUNAS_LEAD_TIME)
    salvar_csv(saida / "commits_releases.csv.gz", resultado.get("commits", []), COLUNAS_COMMITS,
               comprimir=True)
    resumo = {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "repositorios_na_amostra": len(resultado["amostra"]),
        "meta_atingida": len(resultado["amostra"]) >= config["meta_repositorios"],
        "candidatos_avaliados": len(avaliados),
        "requisicoes_api": getattr(cliente, "requisicoes", None),
        "respostas_do_cache": getattr(cliente, "acertos_cache", None),
        "esperas_rate_limit": getattr(cliente, "esperas_rate_limit", None),
        "repeticoes_por_erro_temporario": getattr(cliente, "repeticoes", None),
        "pre_filtro": {motivo: sum(1 for _, m in resultado["pre_filtrados"] if m == motivo)
                       for motivo in MOTIVOS_PRE_FILTRO},
    }
    (saida / "resumo_execucao.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    return saida


def criar_cliente(token: str, config: dict, registrar: Callable[[str], None] = print,
                  **kwargs) -> ClienteREST:
    """RQ78: cliente com cache e margem de cota igual ao numero de trabalhadores.

    Com N threads, ate N requisicoes podem estar em voo quando a cota chega a
    zero; pausar com N restantes evita que elas voltem como HTTP 403.
    """
    trabalhadores = max(1, int(config.get("trabalhadores") or 1))
    cliente = ClienteREST(token, caminho_projeto(config["diretorio_cache"]),
                          margem_cota=trabalhadores, registrar=registrar, **kwargs)
    cota = cliente.consultar_cota()
    if cota and cota.get("remaining") is not None:
        reset = datetime.fromtimestamp(float(cota["reset"] or 0), timezone.utc)
        registrar("[rate limit] cota inicial: %s de %s requisicoes (renova as %s UTC)."
                  % (cota["remaining"], cota["limit"], reset.strftime("%H:%M:%S")))
    return cliente


def principal(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Pipeline DORA do LAB03 (RQ80).")
    parser.add_argument("--config", type=Path, default=RAIZ_PROJETO / "config" / "pipeline.json")
    parser.add_argument("--token", help="Opcional; por padrao usa GITHUB_TOKEN ou .env.")
    args = parser.parse_args(argv)

    try:
        config = carregar_config(args.config)
        if coleta_dora.para_data(config["janela"]["fim"]) >= date.today():
            print("[aviso] a janela termina hoje ou no futuro; o cache congelaria dados parciais.")
        token = obter_token(args.token)
        metadados = preparar_candidatos(config)
        cliente = criar_cliente(token, config)
        resultado = executar(cliente, ler_candidatos(metadados), config)
    except (ErroAutenticacao, ErroREST, OSError, ValueError, subprocess.CalledProcessError) as erro:
        print("Erro: %s" % erro, file=sys.stderr)
        print("Rode o mesmo comando de novo para retomar a partir do cache.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrompido. Rode o mesmo comando de novo para retomar do cache.", file=sys.stderr)
        return 130

    saida = exportar(resultado, config, cliente)
    print("\nFunil de selecao:")
    for etapa in resultado["funil"]:
        print("  %-28s %6d -> %6d" % (etapa["etapa"], etapa["entrada"], etapa["aprovados"]))
    print("Amostra: %d repositorios. Arquivos em %s" % (len(resultado["amostra"]), saida))
    print("Requisicoes a API: %d | respostas do cache: %d | esperas de rate limit: %d | "
          "repeticoes por erro temporario: %d"
          % (cliente.requisicoes, cliente.acertos_cache, cliente.esperas_rate_limit,
             cliente.repeticoes))
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
