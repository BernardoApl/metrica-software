# RQ78 — Cache, Rate Limit, Retomada e Retry

Issue: #78. Requisito da seção 7 do enunciado ("Cache local e retomada" e "Tratamento de rate limit e erros").

A base do cliente REST entrou na #80 ([`cliente_rest.py`](../../../codigo-fonte/coleta/cliente_rest.py)). Esta issue revisou essa base contra o enunciado e a documentação do GitHub ([rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api), [boas práticas](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api)) e corrigiu os pontos em que uma coleta longa (300+ repositórios, várias horas, 8 threads) poderia quebrar ou gerar dados errados.

## Como cada requisito é atendido

| Requisito | Implementação |
|---|---|
| Cache em disco | Um JSON por URL em `dados/.cache/lab03_rest/`, nome = SHA-256 da URL. Escrita atômica (arquivo temporário + `replace`): um `Ctrl+C` no meio da gravação não deixa JSON truncado. Arquivo corrompido ou de outra URL é ignorado e a chamada é refeita |
| Retomada | Rodar o mesmo comando de novo lê do cache tudo o que já foi baixado, inclusive as páginas já percorridas de uma paginação interrompida, e só vai à rede a partir do ponto em que parou |
| Rate limit (proativo) | `X-RateLimit-Remaining`/`X-RateLimit-Reset` lidos em toda resposta. Quando restam `margem_cota` requisições ou menos, o cliente dorme até o reset |
| Rate limit (reativo) | 403/429 com `Retry-After`, com `X-RateLimit-Remaining: 0` ou com mensagem de limite secundário: espera e tenta de novo |
| `GET /rate_limit` | Consultado no início do pipeline (não consome cota). Loga a cota disponível e, se ela já estiver zerada, a primeira requisição espera o reset |
| Backoff exponencial | 5xx e falhas de rede: espera 1, 2, 4, 8, 16 s… (até `espera_maxima` = 60 s), 6 tentativas |

## O que mudou nesta issue

1. **Corpo truncado agora é repetido.** `http.client.IncompleteRead` (conexão cortada no meio da resposta) não herda de `OSError`, então escapava do `except` e derrubava a coleta inteira. Agora é tratado como erro temporário, com backoff.
2. **403 de permissão não vai mais para o cache.** O cliente distingue "403 de rate limit" de "403 de permissão" pela mensagem e pelos cabeçalhos. Se um limite secundário viesse sem esses sinais, o 403 seria gravado e o repositório ficaria descartado como `inacessivel` em todas as execuções seguintes. Sem o cache, a próxima execução simplesmente tenta de novo (custa uma chamada).
3. **Esperas de rate limit não gastam tentativas.** Antes, 6 bloqueios seguidos na mesma URL esgotavam as tentativas e abortavam o pipeline. Agora só erros temporários contam como tentativa; os bloqueios têm um teto separado (`MAX_BLOQUEIOS = 10`) para não esperar para sempre.
4. **Margem de cota para execução paralela.** Com `trabalhadores = 8`, até 8 requisições podem estar em voo quando a cota chega a zero, e voltariam como 403. O pipeline cria o cliente com `margem_cota = trabalhadores`, então ele pausa um pouco antes de zerar.
5. **Uma thread dorme, as outras esperam.** A pausa de cota fica sob uma trava: a primeira thread dorme até o reset e as demais seguem depois dela, sem dormir de novo nem gerar várias linhas de log.
6. **Contadores seguros entre threads** (`requisicoes`, `acertos_cache`, `esperas_rate_limit`, `repeticoes`), que agora vão para `resumo_execucao.json` e para a saída do comando.
7. **Teto no backoff** (`espera_maxima`), para que aumentar `tentativas` não gere esperas de minutos.

## Testes

[`codigo-fonte/testes/test_rq78_cliente_rest.py`](../../../codigo-fonte/testes/test_rq78_cliente_rest.py), todos offline (a rede e o relógio são injetados):

- `IncompleteRead` e `RemoteDisconnected` repetidos com backoff;
- sequência do backoff (1, 2, 4, 8, … até o teto) e esgotamento das tentativas;
- três 429 seguidos com `tentativas = 2` ainda terminam com sucesso; bloqueio persistente desiste após o máximo;
- margem de cota, reset já passado e cota zerada informada por `/rate_limit`;
- 8 threads com cota esgotada → uma única espera; 1.600 requisições em 8 threads → contador exato;
- 403 de permissão fora do cache e regravado quando passa a responder 200;
- retomada de uma paginação interrompida: a página 1 sai do cache, só as páginas 2 e 3 vão à rede;
- `/rate_limit`: leitura da cota `core`, sem cache e sem contar como requisição; falha de rede ou 500 → `None`; 401 → erro de autenticação;
- `criar_cliente` do pipeline com `margem_cota` igual ao número de trabalhadores.

```bash
pytest codigo-fonte/testes/test_cliente_rest.py codigo-fonte/testes/test_rq78_cliente_rest.py --cov=cliente_rest --cov-report=term-missing
```

Cobertura de `cliente_rest.py`: 97%.

## Limitações (para Ameaças à Validade)

- O cache não expira. Isso é intencional, porque a janela é fechada, mas significa que uma coleta feita antes do fim da janela congela dados parciais (o pipeline já avisa quando `janela.fim` ≥ hoje).
- A detecção de limite secundário sem cabeçalhos depende do texto da mensagem do GitHub.
