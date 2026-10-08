"""RQ80: cache, paginacao, rate limit e backoff do cliente REST (sem rede)."""

import io
import json
import sys
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "coleta"))
import cliente_rest
from cliente_rest import ClienteREST, ErroAutenticacaoREST, ErroREST, proxima_pagina


class Resposta:
    def __init__(self, corpo, status=200, cabecalhos=None):
        self.status = status
        self._texto = json.dumps(corpo).encode() if corpo is not None else b""
        self.headers = Message()
        for chave, valor in (cabecalhos or {}).items():
            self.headers[chave] = valor

    def read(self):
        return self._texto

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def erro_http(codigo, cabecalhos=None, corpo=b""):
    mensagem = Message()
    for chave, valor in (cabecalhos or {}).items():
        mensagem[chave] = valor
    return HTTPError("https://api.github.com/x", codigo, "erro", mensagem, io.BytesIO(corpo))


class Abridor:
    """Devolve respostas (ou levanta erros) na ordem, registrando as URLs pedidas."""

    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.urls = []

    def __call__(self, requisicao, timeout=None):
        self.urls.append(requisicao.full_url)
        assert requisicao.get_header("Authorization") == "Bearer token-teste"
        resposta = self.respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta


def cliente(tmp_path, abridor, **kwargs):
    esperas = []
    kwargs.setdefault("relogio", lambda: 1000.0)
    c = ClienteREST("token-teste", tmp_path / "cache", abrir=abridor,
                    dormir=esperas.append, registrar=None, **kwargs)
    return c, esperas


def test_proxima_pagina_le_cabecalho_link():
    link = ('<https://api.github.com/x?page=2>; rel="next", '
            '<https://api.github.com/x?page=5>; rel="last"')
    assert proxima_pagina(link) == "https://api.github.com/x?page=2"
    assert proxima_pagina('<https://api.github.com/x?page=1>; rel="prev"') is None
    assert proxima_pagina(None) is None


def test_token_vazio_e_rejeitado(tmp_path):
    with pytest.raises(ErroAutenticacaoREST):
        ClienteREST("", tmp_path)


def test_cache_evita_segunda_requisicao_e_sobrevive_a_novo_cliente(tmp_path):
    abridor = Abridor(Resposta({"total_count": 3}))
    c, _ = cliente(tmp_path, abridor)
    primeira = c.get("/repos/o/r/actions/workflows", {"per_page": 1})
    assert primeira["corpo"] == {"total_count": 3}
    assert c.get("/repos/o/r/actions/workflows", {"per_page": 1})["corpo"] == {"total_count": 3}
    novo, _ = cliente(tmp_path, Abridor())  # nenhuma resposta disponivel: tem que vir do cache
    assert novo.get("/repos/o/r/actions/workflows", {"per_page": 1})["corpo"] == {"total_count": 3}
    assert len(abridor.urls) == 1
    assert novo.acertos_cache == 1


def test_cache_corrompido_refaz_a_chamada(tmp_path):
    abridor = Abridor(Resposta([1]), Resposta([2]))
    c, _ = cliente(tmp_path, abridor)
    c.get("/x")
    for arquivo in (tmp_path / "cache").rglob("*.json"):
        arquivo.write_text("{truncado", encoding="utf-8")
    assert c.get("/x")["corpo"] == [2]


def test_compactar_reduz_o_que_vai_para_o_cache(tmp_path):
    c, _ = cliente(tmp_path, Abridor(Resposta({"a": 1, "b": 2})))
    assert c.get("/x", compactar=lambda corpo: {"a": corpo["a"]})["corpo"] == {"a": 1}
    gravado = next((tmp_path / "cache").rglob("*.json")).read_text(encoding="utf-8")
    assert '"b"' not in gravado


def test_paginacao_segue_link_ate_o_fim(tmp_path):
    abridor = Abridor(
        Resposta([1, 2], cabecalhos={"Link": '<https://api.github.com/x?page=2>; rel="next"'}),
        Resposta([3]),
    )
    c, _ = cliente(tmp_path, abridor)
    paginas = [p["corpo"] for p in c.paginar("/x", {"per_page": 2})]
    assert paginas == [[1, 2], [3]]
    assert abridor.urls == ["https://api.github.com/x?per_page=2", "https://api.github.com/x?page=2"]


def test_paginacao_respeita_maximo_de_paginas(tmp_path):
    proxima = {"Link": '<https://api.github.com/x?page=2>; rel="next"'}
    c, _ = cliente(tmp_path, Abridor(Resposta([1], cabecalhos=proxima)))
    assert len(list(c.paginar("/x", max_paginas=1))) == 1


def test_erro_5xx_repete_com_backoff_exponencial(tmp_path):
    abridor = Abridor(erro_http(502), erro_http(503), URLError("queda"), Resposta({"ok": True}))
    c, esperas = cliente(tmp_path, abridor)
    assert c.get("/x")["corpo"] == {"ok": True}
    assert esperas == [1, 2, 4]


def test_erro_persistente_esgota_tentativas(tmp_path):
    c, esperas = cliente(tmp_path, Abridor(*[erro_http(500)] * 3), tentativas=3)
    with pytest.raises(ErroREST):
        c.get("/x")
    assert esperas == [1, 2]
    assert not list((tmp_path / "cache").rglob("*.json"))


def test_401_nao_e_repetido(tmp_path):
    c, _ = cliente(tmp_path, Abridor(erro_http(401)))
    with pytest.raises(ErroAutenticacaoREST):
        c.get("/x")


def test_404_e_definitivo_e_fica_no_cache(tmp_path):
    abridor = Abridor(erro_http(404, corpo=b'{"message": "Not Found"}'))
    c, esperas = cliente(tmp_path, abridor)
    assert c.get("/repos/o/sumiu/releases")["status"] == 404
    assert c.get("/repos/o/sumiu/releases")["status"] == 404
    assert esperas == [] and len(abridor.urls) == 1


def test_403_de_rate_limit_espera_ate_o_reset(tmp_path):
    bloqueio = erro_http(403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1300"})
    c, esperas = cliente(tmp_path, Abridor(bloqueio, Resposta([])))
    assert c.get("/x")["corpo"] == []
    assert esperas == [301.0]


def test_429_com_retry_after(tmp_path):
    c, esperas = cliente(tmp_path, Abridor(erro_http(429, {"Retry-After": "42"}), Resposta([])))
    c.get("/x")
    assert esperas == [42.0]


def test_limite_secundario_sem_cabecalho_espera_ao_menos_um_minuto(tmp_path):
    erro = erro_http(403, corpo=b'{"message": "You have exceeded a secondary rate limit"}')
    c, esperas = cliente(tmp_path, Abridor(erro, Resposta([])))
    c.get("/x")
    assert esperas == [60.0]


def test_403_de_permissao_nao_e_rate_limit(tmp_path):
    erro = erro_http(403, corpo=b'{"message": "Repository access blocked"}')
    c, esperas = cliente(tmp_path, Abridor(erro))
    assert c.get("/x")["status"] == 403
    assert esperas == []


def test_cota_zerada_em_resposta_ok_pausa_antes_da_proxima(tmp_path):
    esgotada = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1100"}
    c, esperas = cliente(tmp_path, Abridor(Resposta([1], cabecalhos=esgotada), Resposta([2])))
    c.get("/a")
    assert esperas == []
    c.get("/b")
    assert esperas == [101.0]


def test_sem_cache_nao_grava_nada(tmp_path):
    c = ClienteREST("token-teste", None, abrir=Abridor(Resposta([1]), Resposta([1])),
                    dormir=lambda _: None, registrar=None)
    c.get("/x")
    c.get("/x")
    assert c.requisicoes == 2


def test_resposta_204_sem_corpo(tmp_path):
    c, _ = cliente(tmp_path, Abridor(Resposta(None, status=204)))
    assert c.get("/x")["corpo"] is None


def test_montar_url_preserva_query_existente():
    assert cliente_rest.montar_url("/x?a=1", {"b": 2}) == "https://api.github.com/x?a=1&b=2"
    assert cliente_rest.montar_url("https://api.github.com/y") == "https://api.github.com/y"
