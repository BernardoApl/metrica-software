# RQ102 — Coleta automatizada com e sem cache

O backend executa uma coleta real por linha de comando, usando apenas a biblioteca padrão do Python. A issue #102 não especifica a operação: a implementação adota como cenário inicial a leitura e agregação do CSV de metadados dos repositórios por linguagem (quantidade de repositórios e soma de estrelas). Essa escolha deve ser considerada ao interpretar os dados, sem extrapolar para consultas de rede ou banco de dados.

## Executar

Na raiz do projeto:

```powershell
python codigo-fonte/coleta/rq102_tempos_cache.py
```

Para configurar o experimento:

```powershell
python codigo-fonte/coleta/rq102_tempos_cache.py --entrada dados/lab03_final/metricas_repositorios.csv --saida dados/experimento_cache --pares 30 --repeticoes 20 --aquecimentos 3 --semente 102
```

Cada execução cria uma pasta exclusiva, sem sobrescrever coletas anteriores. Não precisa de token, acesso à rede ou dependências adicionais. A entrada deve conter `nome_completo`, `linguagem` e `estrelas`, com nomes únicos e estrelas inteiras não negativas. Linguagem vazia é agrupada como `Sem linguagem`.

## Protocolo

1. Salva uma cópia da entrada e seu SHA-256; todas as operações usam essa cópia.
2. Calcula o resultado de referência e registra o ambiente e o código utilizado.
3. Executa três pares de aquecimento, exportados separadamente e excluídos da amostra principal.
4. Executa 30 pares, cada um com dois lotes de 20 operações. A ordem é balanceada (15 começam sem cache e 15 com cache) e embaralhada com semente 102. Para números ímpares, a diferença é de um par.
5. Antes de cada par, cria um cache vazio e o preenche uma vez. Esse custo é registrado separadamente. No tratamento `sem_cache`, abre e agrega o CSV a cada repetição; em `com_cache`, reutiliza o resultado imutável já armazenado em memória.
6. Cronometra cada lote com `time.perf_counter_ns()` e divide pelo número de repetições. Confere todas as respostas após parar o relógio, mantendo erros e divergências registrados.

O aquecimento prévio também beneficia o cache de arquivos do sistema operacional. Portanto, **sem cache significa sem cache de resultado da aplicação**, não disco frio. O resultado com cache representa hits; o custo de preenchimento não integra esse tempo. Não há atrasos artificiais nem tempos simulados.

A unidade observacional é o par de lotes sobre o mesmo CSV. As 20 repetições reduzem o peso do cronômetro, mas não são 20 amostras independentes. Os 300 repositórios são registros da entrada, não 300 observações de tempo. A semente reproduz a ordem, não os tempos. Carga da máquina, escalonamento e coleta de lixo podem influenciar a medição; o custo do laço e armazenamento das respostas está incluído em ambos os tratamentos. O retorno de uma referência em memória é muito curto, por isso o overhead pesa especialmente no cache.

## Arquivos e contrato de consumo

| Arquivo | Conteúdo |
| --- | --- |
| `entrada.csv` | Cópia exata do conjunto utilizado |
| `resultado.json` | Referência: triplas de linguagem, quantidade e estrelas |
| `execucao.json` | Parâmetros, ordem, ambiente, resolução do relógio, hashes, status e contagens |
| `aquecimentos.csv` | Dois tratamentos por par de aquecimento, fora da amostra |
| `tempos.csv` | Dois registros por par medido, duração total, tempo por operação, hits/misses e erros |
| `pares.csv` | Um registro por par, tempos em ms, diferença `sem_cache - com_cache` e validade |

`tempo_ms` é a média por operação no lote; `duracao_total_ns` é o tempo do lote. `aquecimento_cache_ns` é o custo único de preenchimento anterior ao par, repetido nas duas linhas apenas como contexto: não somar as duas ocorrências. `cache_hits` e `cache_misses` excluem esse preenchimento; no tratamento com cache são esperados 20 hits e zero misses. O tratamento sem cache ignora o objeto de cache e registra zero para ambos.

Consuma uma execução somente após verificar `execucao.json`, os hashes e o status. `concluida` indica todos os pares válidos; `concluida_com_erros` mantém pares inválidos com campos de tempo/diferença vazios onde aplicável. `erro`, `interrompida` ou `em_andamento` não representam uma coleta completa. Filtre `valido=True` apenas com documentação das exclusões; não substitua falhas por zero nem misture aquecimento com amostra. Interrupções preservam os pares já gravados, mas não garantem o par em andamento; uma nova execução inicia outra pasta.

`resultado_sha256` usa a serialização canônica do resultado; os hashes em `artefatos_sha256` correspondem aos bytes dos arquivos. São verificações distintas.

## Evidência de execução

A execução [20261103T213612Z_ebe7be6978](../../dados/experimento_cache/20261103T213612Z_ebe7be6978/execucao.json) utilizou os 300 repositórios existentes: 30 pares válidos, 60 registros principais e 6 registros de aquecimento. Os resultados são medições locais deste ambiente. Esta entrega não realiza testes de hipótese, simulação ou integração do dashboard, previstos nas próximas issues.

## Validação

```powershell
python -m pytest codigo-fonte/testes/test_rq102_tempos_cache.py -q
```

21 casos verificam balanceamento, cache e limpeza, unidades com relógio controlado, divergências intermediárias, erros, exportação, hashes, entradas inválidas e interrupção. Os dados artificiais desses testes não são a coleta real.

Referência do relógio: [documentação oficial de perf_counter_ns](https://docs.python.org/3.12/library/time.html#time.perf_counter_ns). A representação em nanossegundos não implica precisão efetiva de um nanossegundo; a resolução é registrada no manifesto.
