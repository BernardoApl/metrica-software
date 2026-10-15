"""RQ84: dataset final consolidado e dicionario de dados do LAB03 (secao 7 do enunciado).

    python codigo-fonte/rq84_dataset_final.py                      # consolida e verifica
    python codigo-fonte/rq84_dataset_final.py --somente-dicionario # so gera o dicionario

Entradas (por padrao em ``dados/lab03_final/``):

- ``metricas_repositorios.csv`` e ``resumo_execucao.json`` -- coleta final (RQ82);
- ``rq83/metricas_variantes.csv`` e ``rq83/resumo_rq83.json`` -- metricas nas
  variantes obrigatorias (RQ83), **fonte autoritativa das metricas**;
- opcional: ``amostra_ouro/consenso_repositorios.csv`` (RQ88), de onde vem o
  tipo do projeto rotulado manualmente (fator da RQ 06, so para os 60 da
  amostra-ouro).

Saidas, na mesma pasta:

- ``dataset_final.csv``: uma linha por repositorio, com metadados, fatores da
  RQ 06 (quartis de estrelas, contribuidores e idade; tipo do projeto),
  metricas das RQ 01 a 04 em todas as variantes, classes DORA da combinacao de
  referencia C1 e marcadores de qualidade;
- ``DICIONARIO.md`` e ``dicionario_dados.csv``: nome, tipo, unidade e
  formula/origem de **cada coluna de cada CSV final**, gerados a partir de
  :data:`DEFINICOES` e :data:`ARQUIVOS` (uma unica fonte; o Markdown nao e
  editado a mao);
- ``resumo_rq84.json``: janela, hashes das entradas, divergencias entre a
  coleta e a RQ83, pendencias e a verificacao de cobertura do dicionario.

A verificacao de cobertura le o cabecalho de todo ``*.csv``/``*.csv.gz`` da
pasta e falha se aparecer coluna ou arquivo sem documentacao.

Retornos: 0 = consolidado e documentado; 2 = consolidado com pendencias
(calculo incompleto da RQ83, divergencias ou cobertura); 1 = erro de entrada.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

RAIZ_CODIGO = Path(__file__).resolve().parent
RAIZ_PROJETO = RAIZ_CODIGO.parent
sys.path.insert(0, str(RAIZ_CODIGO))
from metricas import dora  # noqa: E402

PASTA_PADRAO = RAIZ_PROJETO / "dados" / "lab03_final"
#: GitHub logins dos avaliadores da amostra-ouro (RQ85/86/87); colunas por avaliador.
AVALIADORES = ("BernardoApl", "bacelete", "Joaopedrotavaress")
QUARTIS = ("Q1", "Q2", "Q3", "Q4")

# ============================================================== DICIONARIO
# Cada definicao: (tipo, unidade, formula ou origem). Tipos: texto, inteiro,
# real, booleano, data (ISO 8601 UTC), categoria, json.
DEFINICOES = {
    # ----- identificacao e metadados (RQ73/RQ74)
    "nome_completo": ("texto", "—", "`owner/repo` (GraphQL `nameWithOwner`, RQ74). Chave de junção entre os arquivos"),
    "url": ("texto", "—", "GraphQL `url`"),
    "estrelas": ("inteiro", "estrelas", "GraphQL `stargazerCount` na coleta RQ74"),
    "linguagem": ("texto", "—", "GraphQL `primaryLanguage.name` (vazio se o GitHub não detecta)"),
    "criado_em": ("data", "—", "GraphQL `createdAt`"),
    "idade_anos": ("real", "anos", "(data de referência da coleta RQ74 − `criado_em`) ÷ 365,25"),
    "contribuidores_total": ("inteiro", "pessoas", "nº da última página de `GET /contributors?per_page=1&anon=true` (vazio se não coletado)"),
    "branch_padrao": ("texto", "—", "`defaultBranchRef.name`; só esse branch é considerado"),
    "workflows_total": ("inteiro", "workflows", "`total_count` de `GET /actions/workflows`"),
    # ----- RQ 01
    "releases_janela": ("inteiro", "releases", "releases com `draft = false`, `prerelease = false` e `published_at` dentro da janela (deploys, definição principal)"),
    "prereleases_janela": ("inteiro", "releases", "pré-releases publicadas na janela (variante da RQ 07)"),
    "frequencia_deploy_semana": ("real", "releases/semana", "RQ 01: `releases_janela` ÷ (dias da janela ÷ 7)"),
    # ----- RQ 02
    "lead_time_release_mediana_dias": ("real", "dias", "RQ 02 (a): mediana, entre as releases, de `published_at` de R − `commit.author.date` do commit mais antigo de `compare/{anterior}...{R}`"),
    "lead_time_release_q1_dias": ("real", "dias", "1º quartil da distribuição da variante (a) do repositório (interpolação linear, tipo 7)"),
    "lead_time_release_q3_dias": ("real", "dias", "3º quartil da variante (a)"),
    "lead_time_release_iqr_dias": ("real", "dias", "`lead_time_release_q3_dias − lead_time_release_q1_dias`"),
    "lead_time_commit_mediana_dias": ("real", "dias", "RQ 02 (b): mediana, entre **todos** os commits de todas as releases, de `published_at` de R − `commit.author.date`"),
    "lead_time_commit_q1_dias": ("real", "dias", "1º quartil da variante (b)"),
    "lead_time_commit_q3_dias": ("real", "dias", "3º quartil da variante (b)"),
    "lead_time_commit_iqr_dias": ("real", "dias", "`lead_time_commit_q3_dias − lead_time_commit_q1_dias`"),
    "releases_com_lead_time": ("inteiro", "releases", "releases da janela com lead time calculado (entram na variante a)"),
    "commits_com_lead_time": ("inteiro", "commits", "commits que entram na variante (b)"),
    "releases_sem_anterior": ("inteiro", "releases", "primeira release da história do repositório: sem base para o `compare`, ignorada no lead time"),
    "releases_sem_commits": ("inteiro", "releases", "`compare` sem commits novos (ou só com datas posteriores à release), ignorada"),
    "releases_compare_indisponivel": ("inteiro", "releases", "`compare` com 404 (tag apagada/reescrita), 422 ou erro persistente, ignorada"),
    "releases_compare_truncado": ("inteiro", "releases", "`compare` incompleto (limite de páginas ou falha no meio da paginação)"),
    "commits_negativos": ("inteiro", "commits", "commits com `commit.author.date` posterior ao `published_at` da release, descartados das duas variantes"),
    # ----- RQ 03 (a) e RQ 04
    "runs_coletados": ("inteiro", "runs", "runs de `push` no default branch criados na janela, de qualquer `conclusion`"),
    "runs_validos": ("inteiro", "runs", "`runs_falha + runs_sucesso` (push, default branch, janela, conclusão válida)"),
    "runs_falha": ("inteiro", "runs", "`conclusion` ∈ {`failure`, `timed_out`, `startup_failure`}"),
    "runs_sucesso": ("inteiro", "runs", "`conclusion = success`"),
    "cfr_ci": ("real", "fração (0–1)", "RQ 03 (a): `runs_falha ÷ runs_validos`"),
    "recuperacao_mediana_horas": ("real", "horas", "RQ 04: mediana dos episódios completos de todos os workflows; episódio = `updated_at` do sucesso − `run_started_at` da 1ª falha do mesmo workflow"),
    "recuperacao_q1_horas": ("real", "horas", "1º quartil dos episódios completos"),
    "recuperacao_q3_horas": ("real", "horas", "3º quartil dos episódios completos"),
    "recuperacao_iqr_horas": ("real", "horas", "`recuperacao_q3_horas − recuperacao_q1_horas`"),
    "episodios_falha": ("inteiro", "episódios", "total de episódios de falha, incluindo os censurados"),
    "episodios_completos": ("inteiro", "episódios", "episódios usados na mediana (sem censura)"),
    "episodios_censurados": ("inteiro", "episódios", "episódios sem sucesso até o fim da janela (censura à direita)"),
    "episodios_censura_esquerda": ("inteiro", "episódios", "episódios em que o workflow já começa a janela falhando, sem sucesso anterior observado"),
    "proporcao_episodios_censurados": ("real", "fração (0–1)", "`episodios_censurados ÷ episodios_falha`"),
    "intervalos_no_teto": ("inteiro", "intervalos", "intervalos de 1 segundo ainda com ≥ 1.000 runs (coleta de runs incompleta se > 0; RQ77)"),
    # ----- RQ 03 (b)
    "cfr_entrega": ("real", "fração (0–1)", "RQ 03 (b): `releases_falha_cfr ÷ releases_avaliadas_cfr`"),
    "releases_avaliadas_cfr": ("inteiro", "releases", "releases da janela publicadas mais de 7 dias antes do fim da janela (denominador do CFR b)"),
    "releases_falha_cfr": ("inteiro", "releases", "releases seguidas, em até 7 dias (inclusive), por uma release corretiva segundo a heurística"),
    "releases_censuradas_cfr": ("inteiro", "releases", "releases dos últimos 7 dias da janela, fora do denominador do CFR b (censura)"),
    "releases_sem_semver": ("inteiro", "releases", "releases da janela cuja tag não é SemVer `MAJOR.MINOR.PATCH` (a heurística por patch não as reconhece)"),
    "heuristica_cfr_entrega": ("categoria", "—", "versão da heurística de release corretiva usada no CFR (b) (`resumo_rq83.json`; RQ89)"),
    # ----- classes DORA
    "classe_frequencia": ("categoria", "Elite/High/Medium/Low", "tabela de referência da RQ 07 aplicada a `frequencia_deploy_semana`"),
    "classe_lead_time": ("categoria", "Elite/High/Medium/Low", "tabela da RQ 07 aplicada a `lead_time_release_mediana_dias` (variante a, combinação C1)"),
    "classe_cfr": ("categoria", "Elite/High/Medium/Low", "tabela da RQ 07 aplicada a `cfr_ci` (variante a, combinação C1)"),
    "classe_recuperacao": ("categoria", "Elite/High/Medium/Low", "tabela da RQ 07 aplicada a `recuperacao_mediana_horas`"),
    "classe_geral": ("categoria", "Elite/High/Medium/Low", "mediana das notas das quatro classes (Elite=4 … Low=1), arredondada para baixo; vazia se alguma for indefinida"),
    # ----- qualidade
    "calculo_completo": ("booleano", "—", "RQ83: todas as métricas do repositório calculadas sem pendência"),
    "pendencias": ("texto", "—", "RQ83: lista das pendências do repositório (ex.: compare truncado), separadas por `;`"),
    # ----- fatores da RQ 06 (dataset final)
    "estrelas_quartil": ("categoria", "Q1–Q4", "quartil de `estrelas` na amostra final: Q1 se ≤ P25, Q2 se ≤ P50, Q3 se ≤ P75, senão Q4 (empates vão para o quartil inferior)"),
    "contribuidores_quartil": ("categoria", "Q1–Q4", "quartil de `contribuidores_total`, mesma regra; vazio se o valor é ausente"),
    "idade_quartil": ("categoria", "Q1–Q4", "quartil de `idade_anos`, mesma regra"),
    "na_amostra_ouro": ("booleano", "—", "repositório sorteado para a validação manual (RQ86)"),
    "tipo_projeto": ("categoria", "biblioteca_framework/aplicacao_servico/ferramenta_cli/outro", "rótulo de consenso dos 3 avaliadores (RQ88); vazio fora da amostra-ouro"),
    "entregas_reais": ("categoria", "sim/nao/incerto", "consenso (RQ88): as releases representam entregas reais ao usuário?; vazio fora da amostra-ouro"),
    # ----- releases / runs / tags / commits
    "id": ("inteiro", "—", "id do objeto na API do GitHub"),
    "tag_name": ("texto", "—", "tag da release (`tag_name`)"),
    "name": ("texto", "—", "título da release ou nome do workflow (`name`)"),
    "draft": ("booleano", "—", "`draft` da release (rascunho; nunca é deploy)"),
    "prerelease": ("booleano", "—", "`prerelease` da release"),
    "created_at": ("data", "—", "`created_at` do objeto na API"),
    "published_at": ("data", "—", "`published_at` da release (data do deploy)"),
    "target_commitish": ("texto", "—", "branch ou SHA de onde a release foi criada"),
    "dentro_janela": ("booleano", "—", "data de publicação (release) ou de autoria do commit (tag) dentro da janela"),
    "workflow_id": ("inteiro", "—", "id do workflow do run (agrupa os episódios da RQ 04)"),
    "event": ("categoria", "—", "evento que disparou o run; sempre `push`"),
    "head_branch": ("texto", "—", "branch do run; sempre o default branch"),
    "head_sha": ("texto", "—", "SHA do commit do run"),
    "status": ("categoria", "—", "`status` do run (`completed`, `queued`…)"),
    "conclusion": ("categoria", "—", "`conclusion` do run: `success` = sucesso; `failure`/`timed_out`/`startup_failure` = falha; demais = ignorado"),
    "run_attempt": ("inteiro", "tentativas", "nº da tentativa (a API devolve só a última; ameaça à validade, RQ77)"),
    "run_started_at": ("data", "—", "início real da última tentativa do run"),
    "updated_at": ("data", "—", "última atualização do run (fim, para runs concluídos)"),
    "anterior": ("texto", "—", "`tag_name` da release publicada imediatamente antes (base do `compare`)"),
    "sha": ("texto", "—", "SHA do commit"),
    "data_autor": ("data", "—", "`commit.author.date`"),
    "mensagem": ("texto", "—", "1ª linha de `commit.message`, até 200 caracteres"),
    "commits": ("inteiro", "commits", "commits devolvidos pelo `compare` com data de autoria"),
    "truncado": ("booleano", "—", "`compare` incompleto (limite de páginas ou falha no meio)"),
    "lead_time_dias": ("real", "dias", "variante (a) da release: `published_at` − commit mais antigo"),
    "motivo": ("categoria", "—", "motivo do resultado (valores descritos no arquivo)"),
    "erro": ("texto", "—", "mensagem de erro da API, quando houver"),
    # ----- funil e auditoria
    "posicao": ("inteiro", "—", "ordem de avaliação (estrelas decrescentes, entre os aptos no pré-filtro)"),
    "runs_total_informado": ("inteiro", "runs", "`total_count` da busca de runs na janela inteira (satura em intervalos longos)"),
    "etapa": ("texto", "—", "nome da etapa do funil"),
    "criterio": ("texto", "—", "regra aplicada na etapa"),
    "entrada": ("inteiro", "repositórios", "repositórios que chegaram à etapa"),
    "removidos_na_etapa": ("inteiro", "repositórios", "repositórios descartados na etapa"),
    "aprovados": ("inteiro", "repositórios", "`entrada − removidos_na_etapa`"),
    "intervalo": ("texto", "—", "filtro `created` consultado: `AAAA-MM-DD..AAAA-MM-DD` ou com hora UTC"),
    "total_informado": ("inteiro", "runs", "`total_count` da API para o intervalo"),
    "coletados": ("inteiro", "runs", "runs paginados no intervalo (vazio se subdividido sem paginar)"),
    "subdividido": ("booleano", "—", "intervalo dividido ao meio por ter chegado ao teto de 1.000"),
}

#: Variantes de nome por arquivo, quando a mesma coluna muda de sentido.
SOBRESCRITAS = {
    "candidatos_avaliados.csv": {
        "motivo": ("categoria", "—", "`incluido`, `sem_actions`, `poucas_releases`, `poucos_runs`, `runs_acima_do_limite`, `inacessivel`"),
        "releases_janela": ("inteiro", "releases", "releases da janela até a etapa em que o candidato parou"),
        "runs_validos": ("inteiro", "runs", "runs válidos até a etapa em que o candidato parou"),
        "erro": ("texto", "—", "status HTTP, quando `motivo = inacessivel`"),
    },
    "lead_time_releases.csv": {
        "motivo": ("categoria", "—", "por que R ficou sem lead time: `sem_release_anterior`, `sem_commits_novos`, `compare_indisponivel` (vazio se calculado)"),
        "commits_negativos": ("inteiro", "commits", "dos commits da release, quantos têm data posterior a ela (descartados)"),
    },
    "tags.csv": {
        "status": ("categoria", "—", "situação da coleta da tag (`ok` = data do commit obtida)"),
        "status_commit": ("inteiro", "—", "status HTTP de `GET /commits/{sha}`"),
        "dentro_janela": ("booleano", "—", "`data_autor` do commit da tag dentro da janela"),
        "tem_release": ("booleano", "—", "a tag tem release publicada associada"),
    },
    "rq83/cfr_entrega_releases.csv": {
        "censurada": ("booleano", "—", "publicada nos últimos 7 dias da janela: fora do denominador do CFR (b)"),
        "falha": ("booleano", "—", "seguida por release corretiva em até 7 dias (vazio se censurada)"),
        "corretiva_tag": ("texto", "—", "tag da primeira release corretiva encontrada nos 7 dias"),
        "tag_semver": ("booleano", "—", "a tag segue SemVer `MAJOR.MINOR.PATCH`"),
        "heuristica": ("categoria", "—", "versão da heurística de release corretiva (RQ89)"),
    },
    "rq83/episodios_recuperacao.csv": {
        "inicio": ("data", "—", "`run_started_at` da primeira falha do episódio"),
        "fim": ("data", "—", "`updated_at` do sucesso que encerra o episódio (ou fim da janela, se censurado)"),
        "horas": ("real", "horas", "`fim − inicio`"),
        "falhas": ("inteiro", "runs", "falhas no episódio"),
        "censurado": ("booleano", "—", "sem sucesso até o fim da janela (censura à direita)"),
        "censura_esquerda": ("booleano", "—", "workflow já começa a janela falhando"),
    },
}


def _por_avaliador(prefixo: str, descricao: str) -> dict:
    return {"%s_%s" % (prefixo, a): ("categoria", "código", "%s, segundo %s" % (descricao, a))
            for a in AVALIADORES}


def _consenso(prefixo: str, valores: str) -> dict:
    return {
        prefixo + "_consenso": ("categoria", valores, "rótulo de consenso: 3-0 unânime, 2-1 maioria, 1-1-1 decidido em reunião (RQ88)"),
        prefixo + "_origem": ("categoria", "unanime/maioria/reuniao/empate_pendente", "como o consenso foi obtido"),
        prefixo + "_justificativa": ("texto", "—", "justificativa registrada em `decisoes_reuniao.csv` (só `origem = reuniao`)"),
    }


_SORTEIO_REPOS = {
    "id_repositorio": ("texto", "—", "identificador do repositório sorteado (`R01`…`R60`)"),
    "link_repositorio": ("texto", "URL", "página do repositório no GitHub"),
    "link_releases": ("texto", "URL", "página de releases do repositório"),
}
_SORTEIO_RELEASES = {
    "id_release": ("texto", "—", "identificador da release sorteada (`R01-1`…)"),
    "release_anterior": ("texto", "—", "release publicada imediatamente antes (base do `compare`)"),
    "link_release": ("texto", "URL", "página da release (release notes)"),
    "link_commits": ("texto", "URL", "`compare` com a release anterior (lista de commits)"),
}
_DIMENSOES = "`tipo_projeto`, `entregas_reais` ou `corretiva`"

SOBRESCRITAS.update({
    "amostra_ouro/sorteio_repositorios.csv": _SORTEIO_REPOS,
    "amostra_ouro/sorteio_releases.csv": {**_SORTEIO_REPOS, **_SORTEIO_RELEASES},
    "amostra_ouro/consenso_repositorios.csv": {
        **_SORTEIO_REPOS,
        **_por_avaliador("tipo_projeto", "tipo do projeto"),
        **_por_avaliador("entregas_reais", "releases são entregas reais"),
        **_consenso("tipo_projeto", "biblioteca_framework/aplicacao_servico/ferramenta_cli/outro"),
        **_consenso("entregas_reais", "sim/nao/incerto"),
    },
    "amostra_ouro/consenso_releases.csv": {
        **_SORTEIO_REPOS, **_SORTEIO_RELEASES,
        **_por_avaliador("corretiva", "release corretiva"),
        **_consenso("corretiva", "sim/nao"),
    },
    "amostra_ouro/concordancia_fleiss.csv": {
        "dimensao": ("categoria", "—", _DIMENSOES),
        "itens": ("inteiro", "itens", "itens rotulados na dimensão"),
        "avaliadores": ("inteiro", "pessoas", "avaliadores independentes"),
        "kappa_fleiss": ("real", "−1 a 1", "`statsmodels` `aggregate_raters` + `fleiss_kappa(method='fleiss')` sobre os rótulos independentes; vazio se indefinido (todos na mesma categoria)"),
        "interpretacao": ("categoria", "—", "Landis & Koch (1977): pobre, leve, razoavel, moderada, substancial, quase perfeita"),
        "concordancia_total": ("real", "fração (0–1)", "`itens_unanimes ÷ itens`"),
        "itens_unanimes": ("inteiro", "itens", "itens 3-0"),
        "itens_2_1": ("inteiro", "itens", "itens 2-1"),
        "itens_1_1_1": ("inteiro", "itens", "itens 1-1-1"),
        "distribuicao": ("json", "rótulos", "contagem de rótulos por categoria, somando os 3 avaliadores"),
    },
    "amostra_ouro/pendencias_reuniao.csv": {
        "dimensao": ("categoria", "—", _DIMENSOES),
        "id_item": ("texto", "—", "`id_repositorio` ou `id_release`"),
        "obrigatoria": ("booleano", "—", "empate 1-1-1 (precisa de decisão); falso = divergência 2-1 para revisar"),
        "maioria": ("categoria", "código", "rótulo da maioria nos itens 2-1"),
        **{a: ("categoria", "código", "rótulo de %s" % a) for a in AVALIADORES},
    },
    "amostra_ouro/decisoes_reuniao.csv": {
        "dimensao": ("categoria", "—", _DIMENSOES),
        "id_item": ("texto", "—", "`id_repositorio` ou `id_release`"),
        "rotulo": ("categoria", "código ou texto da lista", "rótulo decidido em reunião"),
        "justificativa": ("texto", "—", "motivo da decisão (obrigatório)"),
    },
    "amostra_ouro/avaliacao_heuristica.csv": {
        "versao": ("categoria", "—", "versão da heurística (`metricas/corretiva.py`)"),
        "n": ("inteiro", "releases", "releases com rótulo de consenso"),
        "corretivas_consenso": ("inteiro", "releases", "corretivas segundo o consenso"),
        "corretivas_heuristica": ("inteiro", "releases", "corretivas segundo a heurística"),
        "vp": ("inteiro", "releases", "verdadeiros positivos"),
        "fp": ("inteiro", "releases", "falsos positivos"),
        "fn": ("inteiro", "releases", "falsos negativos"),
        "vn": ("inteiro", "releases", "verdadeiros negativos"),
        "precisao": ("real", "fração (0–1)", "`vp ÷ (vp + fp)` (`precision_recall_fscore_support`, `zero_division=0`)"),
        "recall": ("real", "fração (0–1)", "`vp ÷ (vp + fn)`"),
        "f1": ("real", "fração (0–1)", "`2·P·R ÷ (P + R)`"),
        "sem_mensagens": ("inteiro", "releases", "releases sem mensagens de commit disponíveis (só a tag é avaliada)"),
    },
    "amostra_ouro/erros_heuristica.csv": {
        **_SORTEIO_RELEASES,
        "versao": ("categoria", "—", "versão da heurística"),
        "erro": ("categoria", "—", "`falso_positivo` ou `falso_negativo`"),
        "ev_patch": ("booleano", "—", "evidência: só o patch SemVer aumentou"),
        "ev_mensagens_disponiveis": ("booleano", "—", "evidência: há mensagens de commit do `compare`"),
        "ev_uteis": ("inteiro", "commits", "evidência: commits sem os de merge"),
        "ev_revert_hotfix": ("inteiro", "commits", "evidência: commits com `revert`/`hotfix`"),
        "ev_fix": ("inteiro", "commits", "evidência: commits com `fix`/`fixes`/`fixed`/`bugfix`"),
        "ev_fix_defeito": ("inteiro", "commits", "evidência: `fix` que não é de typo/docs/lint/CI/testes/dependências"),
        "ev_feat": ("inteiro", "commits", "evidência: commits de funcionalidade"),
    },
})

_METRICAS_PIPELINE = (
    "nome_completo", "url", "estrelas", "linguagem", "criado_em", "idade_anos",
    "contribuidores_total", "branch_padrao", "workflows_total", "releases_janela",
    "prereleases_janela", "frequencia_deploy_semana", "runs_coletados", "runs_validos",
    "runs_falha", "runs_sucesso", "cfr_ci", "recuperacao_mediana_horas", "episodios_falha",
    "episodios_completos", "episodios_censurados", "episodios_censura_esquerda",
    "proporcao_episodios_censurados", "intervalos_no_teto", "lead_time_release_mediana_dias",
    "lead_time_commit_mediana_dias", "releases_com_lead_time", "commits_com_lead_time",
    "releases_sem_anterior", "releases_sem_commits", "releases_compare_indisponivel",
    "releases_compare_truncado", "commits_negativos", "classe_frequencia", "classe_lead_time",
    "classe_cfr", "classe_recuperacao", "classe_geral",
)

COLUNAS_DATASET = (
    # identificacao e metadados
    "nome_completo", "url", "estrelas", "linguagem", "criado_em", "idade_anos",
    "contribuidores_total", "branch_padrao", "workflows_total",
    # fatores da RQ 06
    "estrelas_quartil", "contribuidores_quartil", "idade_quartil", "na_amostra_ouro",
    "tipo_projeto", "entregas_reais",
    # RQ 01
    "releases_janela", "prereleases_janela", "frequencia_deploy_semana",
    # RQ 02
    "lead_time_release_mediana_dias", "lead_time_release_q1_dias", "lead_time_release_q3_dias",
    "lead_time_release_iqr_dias", "lead_time_commit_mediana_dias", "lead_time_commit_q1_dias",
    "lead_time_commit_q3_dias", "lead_time_commit_iqr_dias", "releases_com_lead_time",
    "commits_com_lead_time", "releases_sem_anterior", "releases_sem_commits",
    "releases_compare_indisponivel", "releases_compare_truncado", "commits_negativos",
    # RQ 03
    "runs_coletados", "runs_validos", "runs_falha", "runs_sucesso", "cfr_ci",
    "cfr_entrega", "releases_avaliadas_cfr", "releases_falha_cfr", "releases_censuradas_cfr",
    "releases_sem_semver", "heuristica_cfr_entrega",
    # RQ 04
    "recuperacao_mediana_horas", "recuperacao_q1_horas", "recuperacao_q3_horas",
    "recuperacao_iqr_horas", "episodios_falha", "episodios_completos", "episodios_censurados",
    "episodios_censura_esquerda", "proporcao_episodios_censurados",
    # classes DORA (C1) e qualidade
    "classe_frequencia", "classe_lead_time", "classe_cfr", "classe_recuperacao", "classe_geral",
    "intervalos_no_teto", "calculo_completo", "pendencias",
)

#: arquivo (relativo a pasta final) -> (descricao, gerado por, colunas).
ARQUIVOS = {
    "dataset_final.csv": (
        "**Dataset final para a análise (S03)**: uma linha por repositório, com metadados, fatores da RQ 06, métricas das RQ 01 a 04 em todas as variantes, classes DORA da combinação de referência C1 e marcadores de qualidade. Métricas vêm da RQ83; metadados, da coleta",
        "RQ84 `rq84_dataset_final.py`", COLUNAS_DATASET),
    "metricas_repositorios.csv": (
        "métricas calculadas pelo pipeline durante a coleta (uma linha por repositório da amostra)",
        "RQ82/RQ80 `pipeline_dora.py`", _METRICAS_PIPELINE),
    "candidatos_avaliados.csv": (
        "cada candidato avaliado e o motivo do descarte ou da inclusão",
        "RQ82/RQ80 `pipeline_dora.py`",
        ("posicao", "nome_completo", "estrelas", "motivo", "workflows_total", "releases_janela",
         "runs_total_informado", "runs_validos", "erro")),
    "funil_selecao.csv": (
        "funil de seleção: quantos repositórios restaram em cada etapa",
        "RQ82/RQ80 `pipeline_dora.py`",
        ("etapa", "criterio", "entrada", "removidos_na_etapa", "aprovados")),
    "releases.csv": (
        "todas as releases dos repositórios da amostra, inclusive as anteriores à janela (base do `compare`)",
        "RQ82 `GET /repos/{o}/{r}/releases`",
        ("nome_completo", "id", "tag_name", "name", "draft", "prerelease", "created_at",
         "published_at", "target_commitish", "dentro_janela")),
    "workflow_runs.csv.gz": (
        "workflow runs de `push` no default branch, criados na janela (CSV compactado; `pandas.read_csv` lê direto)",
        "RQ82/RQ77 `GET /actions/runs?branch=…&event=push&created=…`",
        ("nome_completo", "id", "workflow_id", "name", "event", "head_branch", "head_sha",
         "status", "conclusion", "run_attempt", "created_at", "run_started_at", "updated_at")),
    "intervalos_runs.csv": (
        "auditoria da coleta de runs: cada intervalo consultado",
        "RQ77 `coleta_dora.coletar_runs`",
        ("nome_completo", "intervalo", "total_informado", "coletados", "subdividido")),
    "lead_time_releases.csv": (
        "lead time de cada release da janela (definição principal)",
        "RQ76 `pipeline_dora.calcular_lead_time`",
        ("nome_completo", "tag_name", "anterior", "published_at", "commits", "commits_negativos",
         "truncado", "lead_time_dias", "motivo")),
    "commits_releases.csv.gz": (
        "commits de cada release, do `compare` com a anterior (CSV compactado)",
        "RQ76 `GET /compare/{anterior}...{R}`",
        ("nome_completo", "tag_name", "anterior", "sha", "data_autor", "mensagem")),
    "tags.csv": (
        "tags dos repositórios da amostra, com a data do commit apontado (variante de deploy da RQ 07)",
        "RQ75 `GET /tags` + `GET /commits/{sha}`",
        ("nome_completo", "tag_name", "sha", "data_autor", "tem_release", "dentro_janela",
         "status", "status_commit", "erro")),
    "rq83/metricas_variantes.csv": (
        "métricas das RQ 01 a 04 em todas as variantes obrigatórias, com quartis",
        "RQ83 `rq83_metricas_variantes.py`",
        ("nome_completo", "releases_janela", "frequencia_deploy_semana",
         "lead_time_release_mediana_dias", "lead_time_commit_mediana_dias",
         "releases_com_lead_time", "commits_com_lead_time", "releases_sem_anterior",
         "releases_sem_commits", "releases_compare_indisponivel", "releases_compare_truncado",
         "commits_negativos", "runs_validos", "runs_falha", "runs_sucesso", "cfr_ci",
         "cfr_entrega", "releases_avaliadas_cfr", "releases_falha_cfr",
         "releases_censuradas_cfr", "releases_sem_semver", "episodios_falha",
         "episodios_completos", "episodios_censurados", "episodios_censura_esquerda",
         "proporcao_episodios_censurados", "lead_time_release_q1_dias",
         "lead_time_release_q3_dias", "lead_time_release_iqr_dias", "lead_time_commit_q1_dias",
         "lead_time_commit_q3_dias", "lead_time_commit_iqr_dias", "recuperacao_mediana_horas",
         "recuperacao_q1_horas", "recuperacao_q3_horas", "recuperacao_iqr_horas",
         "calculo_completo", "pendencias")),
    "rq83/cfr_entrega_releases.csv": (
        "avaliação de cada release da janela no CFR (b)",
        "RQ83 `metricas/variantes.cfr_entrega`",
        ("nome_completo", "tag_name", "published_at", "censurada", "falha", "corretiva_tag",
         "tag_semver", "heuristica")),
    "rq83/episodios_recuperacao.csv": (
        "episódios de falha por workflow (evidência da RQ 04)",
        "RQ83 / RQ79 `metricas/ci.episodios_de_falha`",
        ("nome_completo", "workflow_id", "inicio", "fim", "horas", "falhas", "censurado",
         "censura_esquerda")),
    "amostra_ouro/sorteio_repositorios.csv": (
        "os 60 repositórios sorteados para a validação manual (`random_state=42`)",
        "RQ86 `validacao/rq86_amostra_ouro.py gerar`",
        ("id_repositorio", "nome_completo", "linguagem", "estrelas", "link_repositorio",
         "link_releases")),
    "amostra_ouro/sorteio_releases.csv": (
        "as releases sorteadas (5 por repositório) para rotular como corretiva ou não",
        "RQ86 `validacao/rq86_amostra_ouro.py gerar`",
        ("id_release", "id_repositorio", "nome_completo", "tag_name", "release_anterior",
         "published_at", "link_release", "link_commits")),
    "amostra_ouro/consenso_repositorios.csv": (
        "rótulos dos 3 avaliadores e consenso por repositório",
        "RQ88 `validacao/rq88_concordancia.py`",
        ("id_repositorio", "nome_completo",
         *("tipo_projeto_" + a for a in AVALIADORES), "tipo_projeto_consenso",
         "tipo_projeto_origem", "tipo_projeto_justificativa",
         *("entregas_reais_" + a for a in AVALIADORES), "entregas_reais_consenso",
         "entregas_reais_origem", "entregas_reais_justificativa")),
    "amostra_ouro/consenso_releases.csv": (
        "rótulos dos 3 avaliadores e consenso por release sorteada (referência do F1 da RQ89)",
        "RQ88 `validacao/rq88_concordancia.py`",
        ("id_release", "id_repositorio", "nome_completo", "tag_name", "release_anterior",
         "published_at", *("corretiva_" + a for a in AVALIADORES), "corretiva_consenso",
         "corretiva_origem", "corretiva_justificativa")),
    "amostra_ouro/concordancia_fleiss.csv": (
        "kappa de Fleiss por dimensão rotulada",
        "RQ88 `validacao/rq88_concordancia.py`",
        ("dimensao", "itens", "avaliadores", "kappa_fleiss", "interpretacao",
         "concordancia_total", "itens_unanimes", "itens_2_1", "itens_1_1_1", "distribuicao")),
    "amostra_ouro/pendencias_reuniao.csv": (
        "pauta da reunião de consenso (empates e divergências)",
        "RQ88 `validacao/rq88_concordancia.py`",
        ("dimensao", "id_item", "obrigatoria", *AVALIADORES, "maioria")),
    "amostra_ouro/decisoes_reuniao.csv": (
        "decisões da reunião de consenso (escrito pelo grupo)",
        "grupo, conforme protocolo da RQ88",
        ("dimensao", "id_item", "rotulo", "justificativa")),
    "amostra_ouro/avaliacao_heuristica.csv": (
        "precisão, recall e F1 de cada versão da heurística de release corretiva",
        "RQ89 `validacao/rq89_heuristica.py avaliar`",
        ("versao", "n", "corretivas_consenso", "corretivas_heuristica", "vp", "fp", "fn", "vn",
         "precisao", "recall", "f1", "sem_mensagens")),
    "amostra_ouro/erros_heuristica.csv": (
        "falsos positivos e negativos de cada versão da heurística, com as evidências",
        "RQ89 `validacao/rq89_heuristica.py avaliar`",
        ("versao", "erro", "id_release", "nome_completo", "tag_name", "release_anterior",
         "ev_patch", "ev_mensagens_disponiveis", "ev_uteis", "ev_revert_hotfix", "ev_fix",
         "ev_fix_defeito", "ev_feat", "link_release", "link_commits")),
}


def definicao(arquivo: str, coluna: str) -> Optional[tuple]:
    """(tipo, unidade, formula/origem) da coluna no arquivo, ou ``None`` se nao documentada."""
    return SOBRESCRITAS.get(arquivo, {}).get(coluna) or DEFINICOES.get(coluna)


def linhas_do_dicionario() -> list[dict]:
    linhas = []
    for arquivo, (_, gerado_por, colunas) in ARQUIVOS.items():
        for coluna in colunas:
            tipo, unidade, formula = definicao(arquivo, coluna)
            linhas.append({"arquivo": arquivo, "coluna": coluna, "tipo": tipo,
                           "unidade": unidade, "formula_ou_origem": formula,
                           "gerado_por": gerado_por})
    return linhas


def dicionario_markdown(janela: Optional[dict] = None) -> str:
    janela_txt = ("%s a %s (inclusive; o fim vai até 23:59:59 UTC)"
                  % (janela["inicio"], janela["fim"])) if janela else \
        "ver `resumo_execucao.json` (`config.janela`)"
    partes = [
        "# Dicionário de dados — LAB03 (amostra final)",
        "",
        "> Gerado por `python codigo-fonte/rq84_dataset_final.py` (RQ84) a partir das "
        "definições em `rq84_dataset_final.py`. **Não edite à mão**: altere as definições e "
        "gere de novo. A mesma informação está em `dicionario_dados.csv`.",
        "",
        "- Janela de observação: %s." % janela_txt,
        "- Datas em ISO 8601 UTC. Lead time em **dias**, recuperação em **horas**, CFR como "
        "**fração** de 0 a 1, frequência em **releases por semana**.",
        "- Célula vazia = **indefinido** (não é zero). Ex.: repositório sem falhas tem "
        "recuperação vazia; fora da amostra-ouro, `tipo_projeto` é vazio.",
        "- Mediana e quartis usam interpolação linear (tipo 7).",
        "- Tabela de referência DORA da RQ 07 (cortes fixos da disciplina): frequência ≥ 7/sem "
        "Elite, ≥ 1 High, ≥ 1/mês Medium; lead time < 1 dia Elite, < 7 High, < 30 Medium; "
        "CFR ≤ 15% Elite, ≤ 30% High, ≤ 45% Medium; recuperação < 1 h Elite, < 24 h High, "
        "< 1 semana Medium; o resto é Low.",
        "",
        "## Arquivos",
        "",
        "| Arquivo | Conteúdo | Gerado por |",
        "|---|---|---|",
    ]
    for arquivo, (descricao, gerado_por, _) in ARQUIVOS.items():
        partes.append("| [`%s`](#%s) | %s | %s |" % (arquivo, _ancora(arquivo), descricao,
                                                   gerado_por))
    for arquivo, (descricao, gerado_por, colunas) in ARQUIVOS.items():
        partes += ["", "## `%s`" % arquivo, "", "%s. Gerado por %s." % (descricao, gerado_por),
                   "", "| Coluna | Tipo | Unidade | Fórmula / origem |", "|---|---|---|---|"]
        for coluna in colunas:
            tipo, unidade, formula = definicao(arquivo, coluna)
            partes.append("| `%s` | %s | %s | %s |" % (coluna, tipo, unidade, formula))
    return "\n".join(partes) + "\n"


def _ancora(arquivo: str) -> str:
    return "".join(c for c in arquivo.lower() if c.isalnum() or c in "-_ ").replace(" ", "-")


def escrever_dicionario(pasta: Path, janela: Optional[dict] = None) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "DICIONARIO.md").write_text(dicionario_markdown(janela), encoding="utf-8")
    pd.DataFrame(linhas_do_dicionario()).to_csv(pasta / "dicionario_dados.csv", index=False)


# ======================================================= cobertura do dicionario
def cabecalho(caminho: Path) -> list[str]:
    abrir = gzip.open if caminho.name.endswith(".gz") else open
    with abrir(caminho, "rt", encoding="utf-8", newline="") as arquivo:
        return next(csv.reader(arquivo), [])


def verificar_cobertura(pasta: Path) -> dict:
    """Confere todo CSV da pasta contra o dicionario.

    ``erros``: arquivo sem documentacao ou coluna sem documentacao.
    ``avisos``: coluna documentada que nao aparece no arquivo (ex.: coleta antiga).
    """
    erros, avisos, conferidos = [], [], []
    ignorar = {"dicionario_dados.csv"}
    for caminho in sorted(list(pasta.rglob("*.csv")) + list(pasta.rglob("*.csv.gz"))):
        relativo = caminho.relative_to(pasta).as_posix()
        if relativo in ignorar or relativo.startswith(".") or "/." in relativo:
            continue
        conferidos.append(relativo)
        if relativo not in ARQUIVOS:
            erros.append("%s: arquivo sem documentação no dicionário" % relativo)
            continue
        colunas = cabecalho(caminho)
        documentadas = ARQUIVOS[relativo][2]
        for coluna in colunas:
            if coluna not in documentadas or definicao(relativo, coluna) is None:
                erros.append("%s: coluna `%s` sem documentação" % (relativo, coluna))
        for coluna in documentadas:
            if coluna not in colunas:
                avisos.append("%s: coluna `%s` documentada, mas ausente no arquivo"
                              % (relativo, coluna))
    return {"arquivos_conferidos": conferidos, "erros": erros, "avisos": avisos,
            "completo": not erros}


# ============================================================== consolidacao
def quartil(serie: pd.Series) -> pd.Series:
    """Q1..Q4 pelos cortes P25/P50/P75 (tipo 7); empates no corte vao para o quartil inferior."""
    valores = pd.to_numeric(serie, errors="coerce")
    p25, p50, p75 = valores.quantile([0.25, 0.50, 0.75])

    def rotulo(x):
        if pd.isna(x):
            return None
        if x <= p25:
            return "Q1"
        if x <= p50:
            return "Q2"
        if x <= p75:
            return "Q3"
        return "Q4"

    return valores.map(rotulo)


def _numero(valor) -> Optional[float]:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(numero) else numero


def _sha256(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


COMPARADAS = ("releases_janela", "frequencia_deploy_semana", "runs_validos", "runs_falha",
              "runs_sucesso", "cfr_ci", "lead_time_release_mediana_dias",
              "lead_time_commit_mediana_dias", "recuperacao_mediana_horas")


def divergencias(coleta: pd.DataFrame, rq83: pd.DataFrame, tolerancia: float = 1e-6) -> dict:
    """Repositorios cujo valor da coleta difere do da RQ83, por coluna presente nos dois."""
    juntos = coleta.set_index("nome_completo").join(
        rq83.set_index("nome_completo"), lsuffix="_coleta", rsuffix="_rq83", how="inner")
    resultado = {}
    for coluna in COMPARADAS:
        a, b = coluna + "_coleta", coluna + "_rq83"
        if a not in juntos or b not in juntos:
            continue
        nomes = []
        for nome, x, y in zip(juntos.index, juntos[a], juntos[b]):
            x, y = _numero(x), _numero(y)
            if (x is None) != (y is None) or (x is not None and abs(x - y) > tolerancia):
                nomes.append(nome)
        if nomes:
            resultado[coluna] = nomes
    return resultado


def ler_entradas(pasta: Path, pasta_rq83: Optional[Path] = None) -> dict:
    pasta_rq83 = pasta_rq83 or pasta / "rq83"
    arquivos = {"metricas": pasta / "metricas_repositorios.csv",
                "resumo_coleta": pasta / "resumo_execucao.json",
                "variantes": pasta_rq83 / "metricas_variantes.csv",
                "resumo_rq83": pasta_rq83 / "resumo_rq83.json"}
    faltam = [str(c) for c in arquivos.values() if not c.exists()]
    if faltam:
        raise FileNotFoundError("Faltam: %s. Rode a coleta final (RQ82) e a RQ83 antes."
                                % ", ".join(faltam))
    entradas = {
        "metricas": pd.read_csv(arquivos["metricas"], dtype={"nome_completo": str}),
        "variantes": pd.read_csv(arquivos["variantes"], dtype={"nome_completo": str}),
        "resumo_coleta": json.loads(arquivos["resumo_coleta"].read_text(encoding="utf-8")),
        "resumo_rq83": json.loads(arquivos["resumo_rq83"].read_text(encoding="utf-8")),
        "hashes": {nome: _sha256(c) for nome, c in arquivos.items()},
    }
    consenso = pasta / "amostra_ouro" / "consenso_repositorios.csv"
    sorteio = pasta / "amostra_ouro" / "sorteio_repositorios.csv"
    entradas["consenso"] = pd.read_csv(consenso, dtype=str, keep_default_na=False) \
        if consenso.exists() else None
    entradas["sorteio"] = pd.read_csv(sorteio, dtype=str) if sorteio.exists() else None
    for nome, caminho in (("consenso", consenso), ("sorteio", sorteio)):
        if caminho.exists():
            entradas["hashes"][nome] = _sha256(caminho)
    return entradas


def _janela_rq83(resumo: dict) -> Optional[dict]:
    janela = resumo.get("janela")
    if isinstance(janela, dict):
        return {"inicio": str(janela.get("inicio"))[:10], "fim": str(janela.get("fim"))[:10]}
    return None


def consolidar(entradas: dict) -> tuple[pd.DataFrame, dict]:
    """``(dataset_final, auditoria)`` a partir das entradas lidas."""
    coleta, variantes = entradas["metricas"], entradas["variantes"]
    for nome, tabela in (("metricas_repositorios.csv", coleta),
                         ("rq83/metricas_variantes.csv", variantes)):
        if tabela["nome_completo"].str.casefold().duplicated().any():
            raise ValueError("%s tem repositorios duplicados." % nome)
    so_coleta = sorted(set(coleta["nome_completo"]) - set(variantes["nome_completo"]))
    so_rq83 = sorted(set(variantes["nome_completo"]) - set(coleta["nome_completo"]))
    if so_coleta or so_rq83:
        raise ValueError("Coleta e RQ83 com repositorios diferentes. So na coleta: %s; so na "
                         "RQ83: %s." % (so_coleta[:5], so_rq83[:5]))
    janela = entradas["resumo_coleta"].get("config", {}).get("janela")
    janela_rq83 = _janela_rq83(entradas["resumo_rq83"])
    if janela and janela_rq83 and janela_rq83 != {"inicio": janela["inicio"], "fim": janela["fim"]}:
        raise ValueError("Janela da coleta %s diferente da janela da RQ83 %s." % (janela, janela_rq83))

    metadados = ["nome_completo", "url", "estrelas", "linguagem", "criado_em", "idade_anos",
                 "contribuidores_total", "branch_padrao", "workflows_total",
                 "prereleases_janela", "runs_coletados", "intervalos_no_teto"]
    base = coleta[[c for c in metadados if c in coleta]].set_index("nome_completo")
    dataset = base.join(variantes.set_index("nome_completo"), how="inner").reset_index()
    dataset["heuristica_cfr_entrega"] = entradas["resumo_rq83"].get("heuristica")

    dataset["estrelas_quartil"] = quartil(dataset["estrelas"])
    dataset["contribuidores_quartil"] = quartil(dataset.get("contribuidores_total",
                                                            pd.Series(dtype=float)))
    dataset["idade_quartil"] = quartil(dataset["idade_anos"])

    sorteados = set(entradas["sorteio"]["nome_completo"]) if entradas["sorteio"] is not None else set()
    dataset["na_amostra_ouro"] = dataset["nome_completo"].isin(sorteados)
    tipo, entregas = {}, {}
    if entradas["consenso"] is not None:
        consenso = entradas["consenso"]
        tipo = dict(zip(consenso["nome_completo"], consenso["tipo_projeto_consenso"]))
        entregas = dict(zip(consenso["nome_completo"], consenso["entregas_reais_consenso"]))
    dataset["tipo_projeto"] = dataset["nome_completo"].map(lambda n: tipo.get(n) or None)
    dataset["entregas_reais"] = dataset["nome_completo"].map(lambda n: entregas.get(n) or None)

    classes = [dora.classificar_repositorio(_numero(f), _numero(lt), _numero(cfr), _numero(rec))
               for f, lt, cfr, rec in zip(dataset["frequencia_deploy_semana"],
                                          dataset["lead_time_release_mediana_dias"],
                                          dataset["cfr_ci"],
                                          dataset["recuperacao_mediana_horas"])]
    for coluna in ("classe_frequencia", "classe_lead_time", "classe_cfr", "classe_recuperacao",
                   "classe_geral"):
        dataset[coluna] = [c[coluna] for c in classes]

    for coluna in COLUNAS_DATASET:
        if coluna not in dataset:
            dataset[coluna] = None
    dataset = dataset[list(COLUNAS_DATASET)]
    dataset = dataset.sort_values("nome_completo", key=lambda s: s.str.casefold())
    dataset = dataset.reset_index(drop=True)

    completo = dataset["calculo_completo"].astype(str).str.lower().isin(("true", "1"))
    auditoria = {
        "repositorios": len(dataset),
        "janela": janela,
        "janela_confirmada": entradas["resumo_rq83"].get("janela_confirmada"),
        "heuristica_cfr_entrega": entradas["resumo_rq83"].get("heuristica"),
        "repositorios_com_calculo_incompleto": dataset.loc[~completo, "nome_completo"].tolist(),
        "divergencias_coleta_rq83": divergencias(coleta, variantes),
        "na_amostra_ouro": int(dataset["na_amostra_ouro"].sum()),
        "com_tipo_projeto": int(dataset["tipo_projeto"].notna().sum()),
        "classe_geral": dataset["classe_geral"].value_counts(dropna=False)
                        .rename(lambda k: k if isinstance(k, str) else "indefinida").to_dict(),
        "valores_ausentes": {c: int(dataset[c].isna().sum()) for c in COLUNAS_DATASET
                             if dataset[c].isna().any()},
        "entradas_sha256": entradas["hashes"],
    }
    return dataset, auditoria


def executar(pasta: Path, pasta_rq83: Optional[Path] = None) -> dict:
    entradas = ler_entradas(pasta, pasta_rq83)
    dataset, auditoria = consolidar(entradas)
    temporario = pasta / "dataset_final.csv.tmp"
    dataset.to_csv(temporario, index=False)
    temporario.replace(pasta / "dataset_final.csv")
    escrever_dicionario(pasta, auditoria["janela"])
    cobertura = verificar_cobertura(pasta)
    resumo = {"issue": 84, "gerado_em": datetime.now(timezone.utc).isoformat(), **auditoria,
              "cobertura_dicionario": cobertura,
              "sem_pendencias": (not auditoria["repositorios_com_calculo_incompleto"]
                                 and not auditoria["divergencias_coleta_rq83"]
                                 and cobertura["completo"])}
    (pasta / "resumo_rq84.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2,
                                                       default=str), encoding="utf-8")
    return resumo


def principal(argv=None) -> int:
    parser = argparse.ArgumentParser(description="RQ84: dataset final e dicionario de dados.")
    parser.add_argument("--pasta", type=Path, default=PASTA_PADRAO,
                        help="pasta da amostra final (saida da RQ82)")
    parser.add_argument("--rq83", type=Path, help="pasta da saida da RQ83 (padrao: <pasta>/rq83)")
    parser.add_argument("--somente-dicionario", action="store_true",
                        help="gera DICIONARIO.md e dicionario_dados.csv sem consolidar dados")
    args = parser.parse_args(argv)

    if args.somente_dicionario:
        escrever_dicionario(args.pasta)
        print("Dicionario gerado em %s" % (args.pasta / "DICIONARIO.md"))
        return 0
    try:
        resumo = executar(args.pasta, args.rq83)
    except (FileNotFoundError, ValueError, KeyError) as erro:
        print("Erro: %s" % erro, file=sys.stderr)
        return 1
    print("Dataset final: %d repositorios -> %s" % (resumo["repositorios"],
                                                   args.pasta / "dataset_final.csv"))
    incompletos = resumo["repositorios_com_calculo_incompleto"]
    if incompletos:
        print("- %d repositorio(s) com calculo incompleto na RQ83" % len(incompletos))
    for coluna, nomes in resumo["divergencias_coleta_rq83"].items():
        print("- %s: %d repositorio(s) com valor diferente entre coleta e RQ83"
              % (coluna, len(nomes)))
    for erro in resumo["cobertura_dicionario"]["erros"]:
        print("- dicionario: %s" % erro)
    print("Dicionario: %s (%d arquivos conferidos)"
          % ("completo" if resumo["cobertura_dicionario"]["completo"] else "INCOMPLETO",
             len(resumo["cobertura_dicionario"]["arquivos_conferidos"])))
    return 0 if resumo["sem_pendencias"] else 2


if __name__ == "__main__":
    raise SystemExit(principal())
