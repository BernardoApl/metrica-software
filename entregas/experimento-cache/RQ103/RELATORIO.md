# RQ103 — Dados reais e parâmetros da simulação

Coleta de origem: `20261103T213612Z_ebe7be6978`. Foram validados 30 pares, sem exclusões. Aquecimentos não integram esta análise.

## Estatísticas descritivas

Tempos em ms por operação no lote; desvio padrão amostral (n − 1). Quartis por interpolação linear. A razão sem/com é adimensional.

| Série | Média | Desvio padrão | Mediana | Q1 | Q3 | Mínimo | Máximo |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| sem_cache | 6.0001027 | 1.3183162 | 5.6236475 | 5.19496 | 6.21237 | 4.305485 | 10.557155 |
| com_cache | 0.00049116667 | 7.93691e-05 | 0.000495 | 0.0004475 | 0.00054625 | 0.00034 | 0.00069 |
| diferenca | 5.9996115 | 1.3182967 | 5.6230975 | 5.19439 | 6.2118438 | 4.305095 | 10.556665 |
| razao | 12406.67 | 2793.7702 | 11961.112 | 10440.337 | 13498.222 | 7543.8406 | 21545.214 |

## Leitura dos dados

A diferença mediana sem − com foi 5.6230975 ms. A mediana das razões individuais foi 11961.112. Esses valores descrevem apenas esta execução local; não demonstram significância estatística nem um ganho universal de cache.

O cache retorna uma referência em memória enquanto o recálculo abre e agrega o CSV inteiro. O custo de preencher o cache está fora do tratamento com cache. O custo do laço pesa proporcionalmente mais nesse tratamento muito curto.

### Ordem e evolução da execução

| Tratamento | Mediana na primeira metade | Mediana na segunda metade | Correlação entre posição e tempo |
| --- | ---: | ---: | ---: |
| sem_cache | 6.23775 | 5.19153 | -0.7596863511516833 |
| com_cache | 0.00055 | 0.000455 | -0.3653239221568689 |

Medianas por tratamento que iniciou o par:

| Primeiro tratamento | Sem cache (ms) | Com cache (ms) | Diferença (ms) |
| --- | ---: | ---: | ---: |
| sem_cache | 5.99836 | 0.000515 | 5.997785 |
| com_cache | 5.387455 | 0.000495 | 5.38701 |

As comparações por metade e ordem são diagnósticos descritivos, não testes causais. A ordem balanceada reduz um fator de confusão, mas não garante independência ou estabilidade temporal.

### Valores extremos

- sem_cache: pares fora das cercas de 1,5 × IQR: [1, 2, 3]. Todos foram mantidos.
- com_cache: pares fora das cercas de 1,5 × IQR: []. Todos foram mantidos.

## Estratégia escolhida para a #104

Usar distribuição empírica dos pares, estratificada pela ordem inicial. Sortear pares completos com reposição e probabilidade uniforme dentro de cada estrato, preservando a quantidade original por ordem. Assim os tempos permanecem positivos e a associação dos tratamentos é preservada nos pares de origem, sem impor normalidade ou sortear marginais independentes.

`parametros_simulacao.json` contém os dois tempos de cada par, as quantidades por estrato, unidade, origem e semente sugerida 104. A semente só terá efeito na implementação do gerador da #104; esta entrega não gera dados simulados.

A distribuição empírica possui suporte limitado aos valores observados e não prevê extremos novos. A estratégia não preserva a sequência temporal; serve à simulação descritiva deste cenário, não à inferência populacional. Se a próxima etapa exigir estudar dependência temporal, será necessário definir um modelo por blocos ou coletar sessões independentes. Esta configuração também não gera uma distribuição sob H0: esse objetivo exige um procedimento específico.

## Limitações e rastreabilidade

Os 300 repositórios são registros de uma única entrada. Os pares repetem essa entrada no mesmo ambiente e os tempos representam médias de 20 operações; não tratar as repetições como observações independentes. O cache do sistema operacional não foi desativado. Não generalizar para API, banco, cache frio ou outras máquinas.

A análise exige coleta concluída e consistente, verifica hashes dos cinco artefatos e cruza pares com medições brutas, ordens, unidades e contadores do cache. Falhas interrompem a calibração; nada é excluído silenciosamente. Hashes fornecem rastreabilidade, não autenticação contra adulteração deliberada.

Não há teste de hipótese, p-valor ou conclusão sobre rejeitar H0 nesta entrega. Consulte `resumo.json` para MAD, IQR, correlações e hashes completos.
