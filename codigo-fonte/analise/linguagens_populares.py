"""Lista de referencia de "linguagens mais populares" usada pela RQ05.

O enunciado exige definir e referenciar explicitamente a fonte usada para
"linguagens mais populares" e manter a mesma referencia ao longo de todo o
laboratorio (Lab01, secao Parte 1, RQ05).

Fonte escolhida: **GitHub Octoverse 2025**. A populacao analisada e composta por
repositorios do GitHub, entao rankear a popularidade pelo relatorio do proprio
GitHub mantem a mesma populacao e o mesmo construto (uso real por
desenvolvedores). Indices como o TIOBE medem presenca em buscadores, vagas e
cursos, o que e um construto diferente.

A lista fica em ``recursos/linguagens_populares.json`` -- versionada, datada e
com URL -- para que o dado da referencia seja auditavel e nao fique escondido
dentro do codigo.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

CAMINHO_PADRAO = Path(__file__).resolve().parent / "recursos" / "linguagens_populares.json"


class ReferenciaLinguagens:
    """Ranking de linguagens populares carregado do arquivo de referencia.

    A comparacao com o nome vindo da API do GitHub e feita sem diferenciar
    maiusculas de minusculas, mas o nome preservado no resultado da RQ05 e
    sempre o que a API devolveu, nunca o da lista de referencia.
    """

    def __init__(self, dados: dict):
        linguagens = dados.get("linguagens") or []
        if not linguagens:
            raise ValueError("O arquivo de referencia nao contem nenhuma linguagem.")

        self.fonte = dados.get("fonte", "")
        self.edicao = str(dados.get("edicao", ""))
        self.titulo = dados.get("titulo", "")
        self.url = dados.get("url", "")
        self.publicado_em = dados.get("publicado_em", "")
        self.acessado_em = dados.get("acessado_em", "")
        self.metrica = dados.get("metrica", "")
        self.justificativa = dados.get("justificativa", "")
        self.linguagens = list(linguagens)
        self._rank_por_nome = {
            nome.strip().casefold(): posicao for posicao, nome in enumerate(self.linguagens, start=1)
        }

    @classmethod
    def carregar(cls, caminho: Optional[Path] = None) -> "ReferenciaLinguagens":
        caminho = Path(caminho) if caminho else CAMINHO_PADRAO
        with open(caminho, "r", encoding="utf-8") as arquivo:
            return cls(json.load(arquivo))

    def rank(self, linguagem: Optional[str]) -> Optional[int]:
        """Posicao (base 1) da linguagem no ranking, ou ``None`` se ausente."""
        if not linguagem:
            return None
        return self._rank_por_nome.get(linguagem.strip().casefold())

    def e_popular(self, linguagem: Optional[str]) -> bool:
        return self.rank(linguagem) is not None

    def descrever(self) -> dict:
        """Metadados da referencia, gravados na saida da coleta para auditoria."""
        return {
            "fonte": self.fonte,
            "edicao": self.edicao,
            "titulo": self.titulo,
            "url": self.url,
            "publicado_em": self.publicado_em,
            "acessado_em": self.acessado_em,
            "metrica": self.metrica,
            "justificativa": self.justificativa,
            "quantidade_linguagens": len(self.linguagens),
            "linguagens": list(self.linguagens),
        }

    def __len__(self) -> int:
        return len(self.linguagens)
