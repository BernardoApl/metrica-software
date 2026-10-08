"""RQ78: cache, rate limit, retomada e retry do cliente REST (sem rede).

Complementa ``test_cliente_rest.py`` com os casos que a RQ78 reforcou: corpo
truncado, teto do backoff, esperas de rate limit que nao gastam tentativas,
403 de permissao fora do cache, margem de cota com varias threads e a consulta
a ``/rate_limit``.
"""

import http.client
import sys
import threading
from pathlib import Path
from urllib.error import URLError

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "coleta"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cliente_rest
import pipeline_dora
from cliente_rest import ClienteREST, ErroAutenticacaoREST, ErroREST
from test_cliente_rest import Abridor, Resposta, cliente, erro_http

COTA = {"resources": {"core": {"limit": 5000, "remaining": 4321, "reset": 1600, "used": 679}}}


# ------------------------------------------------------------------- retry
def test_corpo_truncado_e_repetido_como_erro_temporario(tmp_path):
    abridor = Abridor(http.client.IncompleteRead(b"{\"parcial"), Resposta({"ok": True}))
    c, esperas = cliente(tmp_path, abridor)
    assert c.get("/x")["corpo"] == {"ok": True}
    assert esperas == [1]
    assert c.repeticoes == 1


def test_conexao_derrubada_pelo_servidor_e_repetida(tmp_path):
    abridor = Abridor(http.client.RemoteDisconnected("fechou"), Resposta([]))
    c, esperas = cliente(tmp_path, abridor)
    assert c.get("/x")["corpo"] == []
    assert esperas == [1]


def test_backoff_dobra_ate_o_teto(tmp_path):
    c, esperas = cliente(tmp_path, Abridor(*[erro_http(500)] * 6), tentativas=6,
                         espera_maxima=5)
    with pytest.raises(ErroREST):
        c.get("/x")
    assert esperas == [1, 2, 4, 5, 5]
    assert c.repeticoes == 5


def test_espera_de_backoff_e_exponencial():
    c = ClienteREST("t", None, espera_inicial=1, espera_maxima=60, registrar=None)
    assert [c.espera_de_backoff(n) for n in range(1, 9)] == [1, 2, 4, 8, 16, 32, 60, 60]


# -------------------------------------------------------------- rate limit
def test_esperas_de_rate_limit_nao_gastam_tentativas(tmp_path):
    bloqueios = [erro_http(429, {"Retry-After": "42"}) for _ in range(3)]
    c, esperas = cliente(tmp_path, Abridor(*bloqueios, Resposta([7])), tentativas=2)
    assert c.get("/x")["corpo"] == [7]
    assert esperas == [42.0, 42.0, 42.0]
    assert c.esperas_rate_limit == 3
    assert c.repeticoes == 0


def test_rate_limit_persistente_desiste_depois_do_maximo(tmp_path, monkeypatch):
    monkeypatch.setattr(cliente_rest, "MAX_BLOQUEIOS", 2)
    bloqueios = [erro_http(429, {"Retry-After": "1"}) for _ in range(3)]
    c, esperas = cliente(tmp_path, Abridor(*bloqueios))
    with pytest.raises(ErroREST, match="persistente"):
        c.get("/x")
    assert len(esperas) == 2


def test_rate_limit_seguido_de_erro_temporario(tmp_path):
    abridor = Abridor(erro_http(429, {"Retry-After": "30"}), erro_http(502), Resposta([1]))
    c, esperas = cliente(tmp_path, abridor)
    assert c.get("/x")["corpo"] == [1]
    assert esperas == [30.0, 1]


def test_margem_de_cota_pausa_antes_de_zerar(tmp_path):
    quase = {"X-RateLimit-Remaining": "3", "X-RateLimit-Reset": "1100"}
    c, esperas = cliente(tmp_path, Abridor(Resposta([1], cabecalhos=quase), Resposta([2])),
                         margem_cota=4)
    c.get("/a")
    c.get("/b")
    assert esperas == [101.0]
    assert c.esperas_rate_limit == 1


def test_sem_margem_nao_pausa_com_cota_sobrando(tmp_path):
    quase = {"X-RateLimit-Remaining": "3", "X-RateLimit-Reset": "1100"}
    c, esperas = cliente(tmp_path, Abridor(Resposta([1], cabecalhos=quase), Resposta([2])))
    c.get("/a")
    c.get("/b")
    assert esperas == []


def test_reset_ja_passado_espera_so_um_segundo(tmp_path):
    esgotada = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "900"}
    c, esperas = cliente(tmp_path, Abridor(Resposta([1], cabecalhos=esgotada), Resposta([2])))
    c.get("/a")
    c.get("/b")
    assert esperas == [1.0]


def test_varias_threads_com_cota_esgotada_dormem_uma_vez_so(tmp_path):
    c, esperas = cliente(tmp_path, Abridor())
    c.restantes, c.reinicio = 0, 1200.0
    barreira = threading.Barrier(8)

    def aguardar():
        barreira.wait()
        c._aguardar_cota()

    threads = [threading.Thread(target=aguardar) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert esperas == [201.0]
    assert c.restantes is None


def test_contador_de_requisicoes_e_seguro_entre_threads(tmp_path):
    c = ClienteREST("t", None, abrir=lambda *_a, **_k: Resposta([]), dormir=lambda _: None,
                    registrar=None)

    def varias():
        for _ in range(200):
            c.get("/x")

    threads = [threading.Thread(target=varias) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert c.requisicoes == 1600


# ------------------------------------------------------- cache e retomada
def test_403_de_permissao_nao_fica_no_cache(tmp_path):
    proibido = erro_http(403, corpo=b'{"message": "Resource not accessible by integration"}')
    abridor = Abridor(proibido, Resposta({"total_count": 2}))
    c, _ = cliente(tmp_path, abridor)
    assert c.get("/repos/o/r/actions/workflows")["status"] == 403
    assert not list((tmp_path / "cache").rglob("*.json"))
    # Proxima execucao (retomada): tenta de novo e, se agora der certo, grava.
    novo, _ = cliente(tmp_path, abridor)
    assert novo.get("/repos/o/r/actions/workflows")["corpo"] == {"total_count": 2}
    assert len(list((tmp_path / "cache").rglob("*.json"))) == 1


def test_retomada_continua_de_onde_parou_na_paginacao(tmp_path):
    proxima = {"Link": '<https://api.github.com/x?page=2>; rel="next"'}
    terceira = {"Link": '<https://api.github.com/x?page=3>; rel="next"'}
    # Primeira execucao: pagina 1 ok, pagina 2 cai a rede em todas as tentativas.
    primeira = Abridor(Resposta([1], cabecalhos=proxima), *[URLError("queda")] * 2)
    c, _ = cliente(tmp_path, primeira, tentativas=2)
    with pytest.raises(ErroREST):
        list(c.paginar("/x"))
    # Segunda execucao: pagina 1 sai do cache; so as paginas 2 e 3 vao a rede.
    segunda = Abridor(Resposta([2], cabecalhos=terceira), Resposta([3]))
    novo, _ = cliente(tmp_path, segunda)
    assert [p["corpo"] for p in novo.paginar("/x")] == [[1], [2], [3]]
    assert segunda.urls == ["https://api.github.com/x?page=2", "https://api.github.com/x?page=3"]
    assert novo.acertos_cache == 1


def test_cache_de_outra_url_com_mesmo_arquivo_e_ignorado(tmp_path):
    c, _ = cliente(tmp_path, Abridor(Resposta([1]), Resposta([2])))
    c.get("/x")
    arquivo = next((tmp_path / "cache").rglob("*.json"))
    arquivo.write_text('{"url": "https://api.github.com/outra", "corpo": [9]}', encoding="utf-8")
    assert c.get("/x")["corpo"] == [2]


# ------------------------------------------------------------ /rate_limit
def test_consultar_cota_le_core_sem_cache_e_sem_contar(tmp_path):
    abridor = Abridor(Resposta(COTA))
    c, _ = cliente(tmp_path, abridor)
    assert c.consultar_cota() == {"limit": 5000, "remaining": 4321, "reset": 1600, "used": 679}
    assert abridor.urls == ["https://api.github.com/rate_limit"]
    assert (c.restantes, c.reinicio) == (4321, 1600.0)
    assert c.requisicoes == 0
    assert not (tmp_path / "cache").exists()


def test_consultar_cota_com_falha_de_rede_devolve_none(tmp_path):
    c, _ = cliente(tmp_path, Abridor(URLError("sem rede")))
    assert c.consultar_cota() is None
    assert c.restantes is None


def test_consultar_cota_com_http_500_devolve_none(tmp_path):
    c, _ = cliente(tmp_path, Abridor(erro_http(500)))
    assert c.consultar_cota() is None


def test_consultar_cota_com_token_invalido_levanta(tmp_path):
    c, _ = cliente(tmp_path, Abridor(erro_http(401)))
    with pytest.raises(ErroAutenticacaoREST):
        c.consultar_cota()


def test_cota_esgotada_no_inicio_pausa_a_primeira_requisicao(tmp_path):
    esgotada = {"resources": {"core": {"limit": 5000, "remaining": 0, "reset": 1500, "used": 5000}}}
    c, esperas = cliente(tmp_path, Abridor(Resposta(esgotada), Resposta([1])))
    c.consultar_cota()
    assert c.get("/x")["corpo"] == [1]
    assert esperas == [501.0]


# --------------------------------------------------------------- pipeline
def test_pipeline_cria_cliente_com_margem_igual_aos_trabalhadores(tmp_path):
    mensagens = []
    config = dict(pipeline_dora.CONFIG_PADRAO, trabalhadores=8,
                  diretorio_cache=str(tmp_path / "cache"))
    c = pipeline_dora.criar_cliente("token-teste", config, registrar=mensagens.append,
                                    abrir=Abridor(Resposta(COTA)), dormir=lambda _: None)
    assert c.margem_cota == 8
    assert c.cache == tmp_path / "cache"
    assert c.restantes == 4321
    assert any("4321 de 5000" in m for m in mensagens)


def test_pipeline_segue_se_rate_limit_estiver_indisponivel(tmp_path):
    config = dict(pipeline_dora.CONFIG_PADRAO, diretorio_cache=str(tmp_path / "cache"))
    c = pipeline_dora.criar_cliente("token-teste", config, registrar=lambda _: None,
                                    abrir=Abridor(URLError("sem rede")), dormir=lambda _: None)
    assert c.restantes is None
