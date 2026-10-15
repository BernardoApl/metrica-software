"""RQ89: heuristicas de release corretiva (CFR de entrega, RQ 03 b).

Uma release e **corretiva** quando seu objetivo principal e corrigir um defeito
recente. O GitHub nao informa isso, entao o grupo usa heuristicas sobre dois
sinais ja coletados na RQ75/RQ76:

- a **tag**: so o numero de *patch* mudou em relacao a release anterior
  (``2.3.0 -> 2.3.1``);
- as **mensagens** dos commits do ``compare`` entre a release anterior e a
  release avaliada (primeira linha, ate 200 caracteres).

Cada versao da heuristica e uma funcao pura das *evidencias* extraidas por
:func:`evidencias`, o que permite avaliar varias versoes contra a amostra-ouro
(``validacao/rq89_heuristica.py``) sem refazer a leitura dos dados e explicar
cada erro. Para incluir uma nova versao, escreva a funcao e registre-a em
:data:`HEURISTICAS`; o historico de versoes e F1 vai para o artigo.

Nao ha acesso a rede nem a rotulos humanos neste modulo.
"""

from __future__ import annotations

import re
from typing import Callable, Iterable, Optional

SEMVER = re.compile(r'^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)'
                    r'(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$')

#: ``revert`` e ``hotfix`` indicam, quase sempre, desfazer ou consertar algo recente.
_REVERT_HOTFIX = re.compile(r'\b(?:revert(?:s|ed|ing)?|hot-?fix(?:es)?)\b', re.IGNORECASE)
#: ``fix``, ``fixes``, ``fixed``, ``bugfix``... (``\b`` evita ``prefix`` e ``fixture``).
_FIX = re.compile(r'\b(?:fix(?:es|ed|ing)?|bug-?fix(?:es)?)\b', re.IGNORECASE)
#: Correcoes que nao tocam o comportamento entregue ao usuario (docs, CI, testes...).
_FIX_TRIVIAL = re.compile(
    r'\b(?:typos?|spelling|docs?|documentation|readme|changelog|comments?|lint(?:ing|er)?|'
    r'format(?:ting)?|style|whitespace|ci|workflows?|tests?|specs?|flaky|'
    r'deps?|dependenc(?:y|ies)|build|badges?)\b', re.IGNORECASE)
_FEATURE = re.compile(
    r'^(?:feat|feature)(?:\([^)]*\))?!?:|'
    r'\b(?:add(?:s|ed)?|implement(?:s|ed)?|introduce[sd]?|support(?:s|ed)?|new feature)\b',
    re.IGNORECASE)
_MERGE = re.compile(r'^merge\b', re.IGNORECASE)


def versao(tag: Optional[str]) -> Optional[tuple]:
    """``(major, minor, patch)`` de uma tag SemVer estrita, ou ``None``."""
    m = SEMVER.fullmatch(tag or '')
    return tuple(map(int, m.groups())) if m else None


def corretiva_patch(anterior: Optional[str], atual: Optional[str]) -> bool:
    """Mesmo major/minor e patch maior; nao aceita pre-release nem downgrade."""
    a, b = versao(anterior), versao(atual)
    return bool(a and b and a[:2] == b[:2] and b[2] > a[2])


def evidencias(anterior: Optional[str], atual: Optional[str],
               mensagens: Optional[Iterable[str]] = None) -> dict:
    """Sinais usados pelas heuristicas para a release ``atual``.

    :param mensagens: primeira linha dos commits entre ``anterior`` e ``atual``;
        ``None`` quando o ``compare`` nao esta disponivel (so a tag vale).
    :returns: ``patch`` (bool), ``mensagens_disponiveis`` (bool) e contagens de
        commits ``uteis`` (sem merges), ``revert_hotfix``, ``fix`` (qualquer
        ``fix``), ``fix_defeito`` (``fix`` que nao e docs/CI/teste/dependencia)
        e ``feat`` (commits de funcionalidade que nao sao correcao).
    """
    resultado = dict(patch=corretiva_patch(anterior, atual),
                     mensagens_disponiveis=mensagens is not None,
                     uteis=0, revert_hotfix=0, fix=0, fix_defeito=0, feat=0)
    for mensagem in mensagens or ():
        mensagem = (mensagem or '').strip()
        if not mensagem or _MERGE.match(mensagem):
            continue
        resultado['uteis'] += 1
        if _REVERT_HOTFIX.search(mensagem):
            resultado['revert_hotfix'] += 1
        elif _FIX.search(mensagem):
            resultado['fix'] += 1
            if not _FIX_TRIVIAL.search(mensagem):
                resultado['fix_defeito'] += 1
        elif _FEATURE.search(mensagem):
            resultado['feat'] += 1
    resultado['fix'] += resultado['revert_hotfix']
    return resultado


# ----------------------------------------------------------------------- versoes
def patch_semver_v1(ev: dict) -> bool:
    """v1: so o patch mudou (nao usa mensagens)."""
    return ev['patch']


def patch_ou_mensagem_v2(ev: dict) -> bool:
    """v2: patch **ou** qualquer commit com ``revert``, ``hotfix`` ou ``fix``.

    E a leitura literal do enunciado ("e/ou"). Tende a ter recall alto e
    precisao baixa: releases de funcionalidades quase sempre carregam algum ``fix``.
    """
    return ev['patch'] or ev['fix'] > 0


def correcao_de_defeito_v3(ev: dict) -> bool:
    """v3: exige correcao de defeito de verdade, nao qualquer ``fix``.

    - ``revert``/``hotfix`` em algum commit basta;
    - sem commit ``fix`` de defeito (descartados typo, docs, CI, testes e
      dependencias), nao e corretiva, mesmo com patch;
    - com ``fix`` de defeito, e corretiva se o patch mudou **ou** se ao menos
      metade dos commits uteis e ``fix`` de defeito e nao ha commit de funcionalidade;
    - sem mensagens disponiveis, vale so o patch.
    """
    if not ev['mensagens_disponiveis']:
        return ev['patch']
    if ev['revert_hotfix']:
        return True
    if not ev['fix_defeito']:
        return False
    return ev['patch'] or (ev['feat'] == 0 and 2 * ev['fix_defeito'] >= ev['uteis'])


#: Versoes avaliaveis, da mais antiga para a mais recente.
HEURISTICAS: dict[str, Callable[[dict], bool]] = {
    'patch_semver_v1': patch_semver_v1,
    'patch_ou_mensagem_v2': patch_ou_mensagem_v2,
    'correcao_de_defeito_v3': correcao_de_defeito_v3,
}

#: Versao usada no CFR (b) ate a validacao manual indicar outra (F1 >= 0,70).
HEURISTICA_PADRAO = 'patch_semver_v1'


def classificar(nome: str, anterior: Optional[str], atual: Optional[str],
                mensagens: Optional[Iterable[str]] = None) -> bool:
    """Aplica a versao ``nome`` da heuristica a uma release."""
    if nome not in HEURISTICAS:
        raise ValueError('Heuristica desconhecida: %r (use uma de %s)'
                         % (nome, ', '.join(HEURISTICAS)))
    return bool(HEURISTICAS[nome](evidencias(anterior, atual, mensagens)))
