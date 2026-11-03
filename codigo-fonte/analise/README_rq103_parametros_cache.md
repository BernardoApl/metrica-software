# RQ103 — Analisar dados reais e definir parâmetros da simulação

Implementação em `rq103_parametros_cache.py`, somente com biblioteca padrão do Python (3.10+). Usa a coleta real concluída da #102, sem novas chamadas de API e sem alterar os arquivos de origem.

## Executar

Na raiz do projeto, escolha uma pasta de saída nova:

```powershell
python codigo-fonte/analise/rq103_parametros_cache.py --saida dados/.cache/rq103_reanalise
```

Para analisar outra coleta compatível:

```powershell
python codigo-fonte/analise/rq103_parametros_cache.py --entrada dados/experimento_cache/ID_DA_EXECUCAO --saida dados/.cache/rq103_outra_coleta
```

Sem argumentos, usa a coleta `20261103T213612Z_ebe7be6978` e o destino `entregas/experimento-cache/RQ103`. Esse destino já contém a análise entregue: o programa recusa sobrescrevê-lo. Também recusa execuções incompletas, tempos não finitos ou não positivos, arquivos com hash divergente e incoerências entre pares e registros brutos. Não há exclusão silenciosa nem mistura automática de execuções.

## Entregas

- [RELATORIO.md](../../entregas/experimento-cache/RQ103/RELATORIO.md): análise escrita, tabelas, interpretação, escolha do modelo e limitações.
- [resumo.json](../../entregas/experimento-cache/RQ103/resumo.json): média, desvio padrão amostral, mediana, quartis, mínimo, máximo, IQR, MAD e diagnósticos por ordem/metade.
- [parametros_simulacao.json](../../entregas/experimento-cache/RQ103/parametros_simulacao.json): contrato versionado para a #104, com pares completos, estratos, quantidades, unidade e rastreabilidade.

## Decisão de modelagem

Foi escolhida a reamostragem empírica de pares completos, estratificada pela ordem inicial. É uma calibração descritiva: utiliza os valores observados sem supor normalidade e mantém a associação entre os tempos de cada par. Média e desvio padrão também são exportados como estatísticas, mas não são parâmetros de uma normal assumida.

Na coleta atual existem 15 pares em cada estrato; a configuração propõe gerar 15 pares por estrato, totalizando 30. A futura #104 deve inicializar um gerador uma vez com a semente sugerida 104, sortear índices uniformes com reposição dentro de cada estrato, copiar os dois tempos juntos e embaralhar a lista final com o mesmo gerador. Deve registrar sua implementação e identificar os dados como simulados. A #103 não executa esse algoritmo.

Há queda descritiva nos tempos durante a coleta, especialmente sem cache (correlação de Pearson entre posição e tempo aproximadamente −0,76). Isso não prova uma causa nem independência entre pares. O modelo proposto reproduz a distribuição agregada e a composição por ordem, mas não a dependência temporal. Não deve ser usado como justificativa de significância, como distribuição sob H0 ou como substituto de sessões independentes. Simular mais valores não aumenta a evidência empírica original.

## Validação

```powershell
python -m pytest codigo-fonte/testes/test_rq103_parametros_cache.py codigo-fonte/testes/test_rq102_tempos_cache.py -q
```

40 casos passaram (19 da #103 e 21 da #102). A #103 verifica estatísticas conhecidas, preservação dos pares e estratos, determinismo da configuração, proteção contra sobrescrita, hashes e rejeição de inconsistências mesmo quando o hash do arquivo foi atualizado. A coleta usada na análise contém 30 pares válidos e nenhuma exclusão.
