"""RQ83/RQ89: estatisticas e CFR de entrega por heuristica de release corretiva.

A heuristica e um proxy automatico, validado contra a amostra-ouro (RQ89).
As versoes ficam em ``metricas.corretiva``; a padrao e ``HEURISTICA_PADRAO``.
Nao consulta a API nem utiliza rotulos da amostra-ouro.
"""
from datetime import timedelta

from metricas import corretiva
from metricas.ci import data_utc
from metricas.corretiva import SEMVER, corretiva_patch, versao  # noqa: F401 (API da RQ83)
from metricas.lead_time import e_deploy

HEURISTICA = corretiva.HEURISTICA_PADRAO


def resumo(valores):
    """Mediana, Q1, Q3 e IQR com interpolacao linear (tipo 7)."""
    valores = sorted(valores)
    if not valores:
        return dict(n=0, mediana=None, q1=None, q3=None, iqr=None)

    def quantil(p):
        pos = (len(valores) - 1) * p
        inferior = int(pos)
        superior = min(inferior + 1, len(valores) - 1)
        return valores[inferior] + (valores[superior] - valores[inferior]) * (pos - inferior)

    q1, q3 = quantil(.25), quantil(.75)
    return dict(n=len(valores), mediana=quantil(.5), q1=q1, q3=q3, iqr=q3-q1)


def cfr_entrega(releases, inicio, fim, heuristica=None, mensagens_por_release=None):
    """Uma falha por release seguida de patch em ate 7 dias (inclusive).

    A corretiva e identificada contra a release publicada imediatamente
    anterior. Qualquer corretiva nos 7 dias seguintes e evidencia; a release
    original conta uma unica vez. Ultimos 7 dias ficam fora do denominador.

    ``heuristica`` e o nome de uma versao de ``corretiva.HEURISTICAS`` (padrao:
    ``HEURISTICA``). ``mensagens_por_release`` mapeia ``tag_name`` para as
    mensagens dos commits entre a release anterior e ela; sem entrada, so a tag vale.
    """
    heuristica = heuristica or HEURISTICA
    mensagens_por_release = mensagens_por_release or {}
    inicio, fim = data_utc(inicio), data_utc(fim)
    deploys = sorted((r for r in releases if e_deploy(r) and data_utc(r['published_at']) <= fim),
                     key=lambda r: (data_utc(r['published_at']), int(r.get('id') or 0)))
    corretivas = []
    for i, r in enumerate(deploys):
        if i and corretiva.classificar(heuristica, deploys[i-1]['tag_name'], r['tag_name'],
                                       mensagens_por_release.get(r['tag_name'])):
            corretivas.append(r)
    detalhes = []
    for r in deploys:
        data = data_utc(r['published_at'])
        if data < inicio:
            continue
        censurada = data + timedelta(days=7) > fim
        evidencias = [c for c in corretivas
                      if data < data_utc(c['published_at']) <= data + timedelta(days=7)]
        detalhes.append(dict(tag_name=r['tag_name'], published_at=r['published_at'],
                             censurada=censurada, falha=None if censurada else bool(evidencias),
                             corretiva_tag=evidencias[0]['tag_name'] if evidencias else None,
                             tag_semver=versao(r['tag_name']) is not None, heuristica=heuristica))
    avaliadas = [r for r in detalhes if not r['censurada']]
    falhas = sum(r['falha'] for r in avaliadas)
    return dict(cfr_entrega=falhas / len(avaliadas) if avaliadas else None,
                releases_avaliadas_cfr=len(avaliadas), releases_falha_cfr=falhas,
                releases_censuradas_cfr=len(detalhes)-len(avaliadas),
                releases_sem_semver=sum(not r['tag_semver'] for r in detalhes), detalhes=detalhes)
