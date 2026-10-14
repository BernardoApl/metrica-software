"""RQ83: estatisticas e CFR de entrega pela heuristica patch SemVer v1.

A heuristica e um proxy automatico, ainda sujeito a validacao manual.
Nao consulta a API nem utiliza rotulos da amostra-ouro.
"""
from datetime import timedelta
import re

from metricas.ci import data_utc
from metricas.lead_time import e_deploy

HEURISTICA = 'patch_semver_v1'
SEMVER = re.compile(r'^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$')


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


def versao(tag):
    m = SEMVER.fullmatch(tag or '')
    return tuple(map(int, m.groups())) if m else None


def corretiva_patch(anterior, atual):
    """Mesmo major/minor e patch maior; nao aceita prerelease nem downgrade."""
    a, b = versao(anterior), versao(atual)
    return bool(a and b and a[:2] == b[:2] and b[2] > a[2])


def cfr_entrega(releases, inicio, fim):
    """Uma falha por release seguida de patch em ate 7 dias (inclusive).

    A corretiva e identificada contra a release publicada imediatamente
    anterior. Qualquer corretiva nos 7 dias seguintes e evidencia; a release
    original conta uma unica vez. Ultimos 7 dias ficam fora do denominador.
    """
    inicio, fim = data_utc(inicio), data_utc(fim)
    deploys = sorted((r for r in releases if e_deploy(r) and data_utc(r['published_at']) <= fim),
                     key=lambda r: (data_utc(r['published_at']), int(r.get('id') or 0)))
    corretivas = []
    for i, r in enumerate(deploys):
        if i and corretiva_patch(deploys[i-1]['tag_name'], r['tag_name']):
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
                             tag_semver=versao(r['tag_name']) is not None, heuristica=HEURISTICA))
    avaliadas = [r for r in detalhes if not r['censurada']]
    falhas = sum(r['falha'] for r in avaliadas)
    return dict(cfr_entrega=falhas / len(avaliadas) if avaliadas else None,
                releases_avaliadas_cfr=len(avaliadas), releases_falha_cfr=falhas,
                releases_censuradas_cfr=len(detalhes)-len(avaliadas),
                releases_sem_semver=sum(not r['tag_semver'] for r in detalhes), detalhes=detalhes)
