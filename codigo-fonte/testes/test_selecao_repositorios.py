import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analise"))

import selecao_repositorios as selecao


def repositorio(**ajustes):
    base = {
        "nome_completo": "org/projeto",
        "url": "https://github.com/org/projeto",
        "estrelas": 10,
        "presente_na_busca_graphql": True,
        "presente_na_busca_rest": True,
        "rq01_idade_anos": 2.0,
        "rq02_pull_requests_aceitos": 4,
        "rq03_total_releases": 1,
        "rq04_dias_desde_ultima_atualizacao": 3.0,
        "rq04_status": "ok",
    }
    base.update(ajustes)
    return base


class TestSelecaoRepositorios(unittest.TestCase):
    def test_funil_exclui_apenas_em_sua_etapa(self):
        validos, funil = selecao.selecionar([
            repositorio(nome_completo="org/valido", estrelas=30),
            repositorio(nome_completo="org/ausente-rest", presente_na_busca_rest=False),
            repositorio(nome_completo="", url="https://github.com/org/sem-nome"),
            repositorio(nome_completo="org/sem-metrica", rq03_total_releases=None),
            repositorio(nome_completo="org/data-futura", rq04_status="data_futura"),
        ])

        self.assertEqual([item["nome_completo"] for item in validos], ["org/valido"])
        self.assertEqual([item["aprovados"] for item in funil], [5, 4, 3, 1])
        self.assertEqual([item["removidos_na_etapa"] for item in funil], [0, 1, 1, 2])

    def test_campos_opcionais_ausentes_nao_excluem(self):
        validos, _ = selecao.selecionar([
            repositorio(rq05_linguagem_primaria=None, rq06_razao_fechadas_total=None),
        ])
        self.assertEqual(len(validos), 1)

    def test_limite_mantem_os_mais_estrelados(self):
        validos, funil = selecao.selecionar([
            repositorio(nome_completo="org/menor", estrelas=10),
            repositorio(nome_completo="org/maior", estrelas=50),
        ], limite=1)
        self.assertEqual([item["nome_completo"] for item in validos], ["org/maior"])
        self.assertEqual(funil[-1]["aprovados"], 1)


if __name__ == "__main__":
    unittest.main()
