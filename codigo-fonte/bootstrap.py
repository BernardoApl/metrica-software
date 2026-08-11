"""Configuracao dos caminhos de importacao do projeto.

A estrutura de pastas definida pelo grupo usa ``consulta-graphql``, com hifen,
que nao e um identificador Python valido e portanto nao pode ser importado como
pacote. Em vez de renomear a estrutura ja acordada, cada subdiretorio de
``codigo-fonte`` e adicionado ao ``sys.path``, de modo que os modulos sejam
importaveis pelo proprio nome do arquivo (``import cliente_github``).

Uso, a partir de qualquer script executavel do projeto::

    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from bootstrap import configurar_caminhos

    configurar_caminhos()
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ_CODIGO = Path(__file__).resolve().parent
RAIZ_PROJETO = RAIZ_CODIGO.parent
DIRETORIO_DADOS = RAIZ_PROJETO / "dados"

SUBDIRETORIOS = ("consulta-graphql", "coleta", "analise")


def configurar_caminhos() -> None:
    """Coloca os subdiretorios de ``codigo-fonte`` no ``sys.path``."""
    for nome in SUBDIRETORIOS:
        caminho = str(RAIZ_CODIGO / nome)
        if caminho not in sys.path:
            sys.path.insert(0, caminho)
