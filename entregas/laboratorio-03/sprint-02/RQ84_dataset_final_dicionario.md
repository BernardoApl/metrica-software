# RQ84 — Dataset Final e Dicionário de Dados

Issue: #84. Entrega da Lab03S02: "Dataset em .csv com dicionário de dados" e o requisito da seção 7 ("cada coluna dos CSVs finais é documentada com nome, tipo, unidade e fórmula ou origem na API").

## Execução

Depois da coleta final (RQ82) e do cálculo das variantes (RQ83):

```bash
python codigo-fonte/rq84_dataset_final.py
```

| Código | Significado |
|---|---|
| 0 | dataset consolidado, sem pendências, dicionário cobrindo todos os CSVs |
| 2 | consolidado, mas com pendências: cálculo incompleto na RQ83, divergência entre coleta e RQ83, ou coluna/arquivo sem documentação |
| 1 | entrada ausente ou inconsistente (repositórios diferentes entre coleta e RQ83, janelas diferentes, duplicados) |

Só o dicionário, sem dados: `python codigo-fonte/rq84_dataset_final.py --somente-dicionario`.

## `dados/lab03_final/dataset_final.csv`

Uma linha por repositório da amostra final, ordenada por nome. É **o** arquivo que as análises da S03 (RQ 01 a 07) devem ler.

| Bloco | Colunas | Origem |
|---|---|---|
| Identificação e metadados | `nome_completo`, `url`, `estrelas`, `linguagem`, `criado_em`, `idade_anos`, `contribuidores_total`, `branch_padrao`, `workflows_total` | coleta (RQ74/RQ82) |
| Fatores da RQ 06 | `estrelas_quartil`, `contribuidores_quartil`, `idade_quartil` (Q1–Q4), `tipo_projeto`, `entregas_reais`, `na_amostra_ouro` | quartis calculados aqui; tipo do projeto do consenso da RQ88 |
| RQ 01 | `releases_janela`, `prereleases_janela`, `frequencia_deploy_semana` | RQ83 |
| RQ 02 | lead time (a) e (b): mediana, Q1, Q3, IQR, mais as contagens de releases ignoradas | RQ83 |
| RQ 03 | `cfr_ci` (a), `cfr_entrega` (b), contagens, `heuristica_cfr_entrega` | RQ83 |
| RQ 04 | recuperação: mediana, Q1, Q3, IQR, episódios e censura | RQ83 |
| Classes DORA (C1) | `classe_frequencia`, `classe_lead_time` (a), `classe_cfr` (a), `classe_recuperacao`, `classe_geral` | calculadas aqui com `metricas/dora.py` |
| Qualidade | `intervalos_no_teto`, `calculo_completo`, `pendencias` | coleta e RQ83 |

### Decisões

- **A RQ83 é a fonte autoritativa das métricas.** O pipeline também calcula frequência, CFR (a), recuperação e lead time durante a coleta. Esses valores são **comparados** com os da RQ83 e cada divergência vai para `resumo_rq84.json` (`divergencias_coleta_rq83`), sem ser escondida. Na amostra piloto, as duas fontes concordaram em todos os 100 repositórios.
- **Quartis** pelos cortes P25/P50/P75 (interpolação linear, a mesma da RQ83). Um valor igual ao corte fica no quartil inferior. Valor ausente fica sem quartil.
- **Tipo do projeto** só existe para os 60 repositórios da amostra-ouro (rótulo manual). Fora dela, o campo fica **vazio**, e não "outro". A RQ 06 com esse fator deve usar só os 60.
- **Classes DORA** da combinação de referência C1 (release, lead time a, CFR a), pela tabela fixa da disciplina. `classe_geral` fica vazia quando alguma das quatro métricas é indefinida.
- Célula vazia significa **indefinido**, nunca zero.

## Dicionário de dados

- [`dados/lab03_final/DICIONARIO.md`](../../../dados/lab03_final/DICIONARIO.md), legível;
- [`dados/lab03_final/dicionario_dados.csv`](../../../dados/lab03_final/dicionario_dados.csv), para máquina (`arquivo`, `coluna`, `tipo`, `unidade`, `formula_ou_origem`, `gerado_por`).

Cobre **22 arquivos e 307 colunas**: os CSVs da coleta (RQ75/76/77/80/82), da RQ83, da amostra-ouro (RQ86, RQ88, RQ89) e o `dataset_final.csv`. Os dois arquivos são **gerados** a partir das definições em [`rq84_dataset_final.py`](../../../codigo-fonte/rq84_dataset_final.py) e não devem ser editados à mão.

### Como o dicionário se mantém atualizado

1. **Na execução:** depois de consolidar, o script lê o cabeçalho de **todo** `*.csv`/`*.csv.gz` de `dados/lab03_final/` e acusa arquivo ou coluna sem documentação (código 2). Colunas documentadas que não aparecem no arquivo viram aviso, o que acontece, por exemplo, com uma coleta antiga.
2. **Nos testes:** o dicionário é comparado com as constantes de colunas de cada RQ (`pipeline_dora.COLUNAS_*`, `rq75 COLUNAS`, `rq86 COLUNAS_*`), com as saídas reais da RQ88 e da RQ89 e com os arquivos reais da coleta piloto. Se alguém mudar uma coluna exportada sem atualizar o dicionário, o CI quebra.

O dicionário antigo da piloto (`dados/lab03/DICIONARIO.md`) continua no lugar, com um aviso apontando para o oficial.

## `resumo_rq84.json`

Janela, se ela já foi confirmada, a heurística do CFR (b), repositórios com cálculo incompleto, divergências entre coleta e RQ83, nº na amostra-ouro e com tipo do projeto, distribuição da `classe_geral`, valores ausentes por coluna, SHA-256 das entradas e o relatório de cobertura do dicionário.

## Testes

[`codigo-fonte/testes/test_rq84_dataset_final.py`](../../../codigo-fonte/testes/test_rq84_dataset_final.py) (29 testes, cobertura de 97%):

- dicionário: toda coluna tem tipo, unidade e fórmula; igualdade com as colunas exportadas por cada RQ; cobertura das saídas reais da RQ88, da RQ89 e da coleta piloto; arquivo ou coluna nova sem documentação é apontada; pastas ocultas (cache) ignoradas;
- quartis: cortes, empates e ausentes;
- consolidação: classes DORA (C1), quartis, tipo do projeto vindo do consenso, divergência entre coleta e RQ83 reportada (e o valor da RQ83 prevalece), cálculo incompleto deixa a `classe_geral` vazia, recusa repositórios diferentes, janelas diferentes e duplicados;
- execução real sobre a piloto: 100 repositórios, quartis 25/25/25/25, nenhuma divergência;
- CLI: códigos 0, 1 e 2 e `--somente-dicionario`.

## Correção de integração RQ88 → RQ89

Ao montar o dicionário apareceu um problema entre a RQ88 e a RQ89. O `consenso_releases.csv` da RQ88 tem a coluna `corretiva_consenso`, mas `rq89_heuristica.py` só procurava `corretiva`, `consenso` ou `consenso_corretiva`. Com isso, `rq89_heuristica.py avaliar` falharia no caminho padrão assim que o consenso existisse. A RQ89 passou a aceitar `corretiva_consenso`, e um teste novo (`test_consenso_da_rq88_e_lido_pela_rq89`) liga a saída real da RQ88 à leitura da RQ89.

## Situação

O dicionário oficial já está gerado. O `dataset_final.csv` real depende da amostra final (RQ82) e da RQ83 rodada sobre ela. O ensaio com a piloto (coleta `dados/lab03` + `dados/rq83_piloto`) funcionou de ponta a ponta, com saída 2 porque a piloto não tem lead time. Esse ensaio **não** foi commitado como dataset final.
