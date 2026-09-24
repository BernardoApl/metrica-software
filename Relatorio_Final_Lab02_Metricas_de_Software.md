# Relatório Final - LAB02 Métricas de Software

## Resumo Executivo

Este relatório consolida o experimento do LAB02 sobre o uso de assistentes de IA generativa na resolução de katas de programação em Python. O objetivo é comparar os tratamentos `com_ia` e `sem_ia` em três dimensões:

- RQ1: tempo de resolução até os testes passarem;
- RQ2: sucesso funcional e defeitos observados;
- RQ3: estrutura do código produzido (complexidade ciclomática, LOC, duplicação, índice de manutenibilidade).

Com os dados atuais, os três integrantes (Arthur, bblop, João Pedro) têm pelo menos um par completo (`com_ia` + `sem_ia`) com tempo e métricas estáticas, permitindo rodar o teste de Wilcoxon pareado nas três RQs pela primeira vez. Nenhuma das três RQs rejeitou H0 (não há evidência estatística de diferença entre os tratamentos) — resultado esperado dado o N extremamente pequeno (3 pares) e discutido em detalhe na Seção 7. A coleta ainda não está completa: faltam 3 dos 12 trials planejados (Issues #34, #35, #40) e há 2 trials com o rótulo de tratamento divergente do planejado (Issues #41, #49), pendentes de confirmação com os responsáveis.

## 1. Contexto e Objetivo

O experimento segue o desenho definido na [RQ33](entregas/laboratorio-02/sprint-01/RQ33_hipoteses.md): comparar tarefas de programação resolvidas com e sem assistente de IA (ChatGPT, versão gratuita), usando katas autorais e testes automatizados, em um desenho crossover/within-subject contrabalanceado (cada participante é seu próprio controle). A linguagem usada é Python, com coleta de tempo pelo script de cronometragem (RQ28) e métricas estruturais extraídas do arquivo `solucao.py` final de cada trial (RQ30, via Radon).

**Nota de escopo:** a RQ33 originalmente planejou 6 katas × 3 integrantes = 18 trials. Na execução, o grupo convergiu para um desenho de 4 katas (frete progressivo, cálculo de estacionamento, deduplicador de contatos, tarifa de energia) × 3 integrantes = 12 trials, refletido no plano de Issues usado pela RQ50 (auditoria). As hipóteses, variáveis e ameaças à validade da RQ33 continuam válidas; apenas a quantidade de objetos experimentais mudou.

### Hipóteses (RQ33)

- **H0(1)/H1(1):** não há diferença / há diferença (menor) na mediana do tempo até passar nos testes, com IA vs. sem IA.
- **H0(2)/H1(2):** não há diferença / há diferença (maior) na taxa de sucesso, com IA vs. sem IA.
- **H0(3)/H1(3):** não há diferença / há diferença na complexidade ciclomática e/ou duplicação (normalizadas por LOC), com IA vs. sem IA.

Todos os testes são bicaudais, via Wilcoxon pareado (amostras dependentes, desenho within-subject).

## 2. Fontes de Dados

| Fonte | Arquivo | Papel no relatório |
|---|---|---|
| RQ28 | `dados/lab02_rq28_tempos.csv` | Tempo, status, tratamento, participante, kata |
| RQ30 | `dados/lab02_rq30_metricas_estaticas.csv` | Complexidade, LOC, MI e duplicação por trial |
| RQ50 | `dados/lab02_rq50_auditoria.json` | Auditoria de cobertura vs. plano de Issues |
| RQ57 | `dados/lab02_rq57_dataset_unificado.csv` / `lab02_rq57_resumo_tratamento.csv` | Dataset unificado e resumo por participante/tratamento |
| RQ51/52/53 | `dados/lab02_rq5{1,2,3}_wilcoxon_*.json` | Testes de hipótese (Wilcoxon pareado) para RQ1, RQ2, RQ3 |
| RQ44/RQ54 | `dados/lab02_rq44_comparacao_metricas.csv` / `lab02_rq54_consolidacao_tratamento.csv` | Comparação descritiva (mediana/IQR) por kata e por tratamento |
| RQ58 | `dados/rq58_dashboard_inicial.png` | Dashboard visual |

## 3. Estado Atual da Coleta

Auditoria (RQ50) contra o plano de 12 trials esperados (4 katas × 3 integrantes):

- **6 trials OK** (rastreáveis e consistentes com o plano);
- **3 trials divergentes:**
  - Issue #41 (João, kata02): registrada como `sem_ia`, esperado `com_ia`;
  - Issue #49 (João, kata04): registrada como `com_ia`, esperado `sem_ia`;
  - Issue #42 (João, kata03): trial com sucesso, mas ainda sem RQ30 vinculada;
- **3 trials faltando:** Issue #34 (bblop, kata01 com_ia), Issue #35 (bblop, kata02 sem_ia), Issue #40 (João, kata01 com_ia).

Resumo por participante/tratamento (RQ57):

| Participante | Tratamento | Trials | RQ30 vinculada | Mediana tempo (s) | Taxa sucesso | Mediana complex./LOC | Mediana MI |
|---|---|---:|---:|---:|---:|---:|---:|
| Arthur | com_ia | 2 | 2 | 1.71 | 1.0 | 0.163 | 55.18 |
| Arthur | sem_ia | 2 | 2 | 787.29 | 1.0 | 0.205 | 48.29 |
| bblop | com_ia | 2 | 2 | 35.13 | 1.0 | 0.304 | 51.81 |
| bblop | sem_ia | 5 | 2 | 0.28 | 1.0 | 0.159 | 57.83 |
| João Pedro | com_ia | 1 | 1 | 72.25 | 1.0 | 0.194 | 53.45 |
| João Pedro | sem_ia | 2 | 1 | 974.08 | 1.0 | 0.125 | 62.22 |

Duplicação de código (`jscpd`) **não foi medida em nenhum trial** (indisponível no ambiente de coleta) — RQ3 fica restrita a complexidade/LOC/MI.

## 4. Metodologia Sintética

Cada trial foi cronometrado pela RQ28 (`--tratamento com_ia|sem_ia`, time-box de 35 min, comando de aceitação `python -m unittest discover -s testes`). Ao final de cada trial bem-sucedido, a RQ30 mede complexidade ciclomática (Radon `cc`), LOC/SLOC/LLOC (Radon `raw`) e índice de manutenibilidade (Radon `mi`) sobre o `solucao.py` final. A RQ57 junta RQ28+RQ30 por `trial_id`, calcula `duracao_efetiva_segundos`, `sucesso_binario` e `complexidade_por_loc` (controle de tamanho). A RQ51/52/53 rodam Wilcoxon pareado por participante (cada um comparado consigo mesmo entre tratamentos), consistente com o desenho within-subject da RQ33.

## 5. Resultados por RQ

### RQ1 — Tempo de Resolução

- **3 pares completos** (Arthur, bblop, João Pedro).
- Mediana `com_ia` = 35.13 s | Mediana `sem_ia` = 787.29 s.
- Wilcoxon: W+ = 1.0, W− = 5.0, p = 0.5000 → **não rejeita H0** (sem evidência estatística de diferença).
- Effect size (rank-biserial) = −0.67, sugerindo tendência a favor de `com_ia` ser mais rápido, mas **não significativa** com n=3.

### RQ2 — Sucesso e Defeitos

- **3 pares completos**, mas **todos os 14 trials registrados terminaram com sucesso** (taxa de sucesso = 100% em ambos os tratamentos).
- Wilcoxon: dados insuficientes — todas as diferenças pareadas são zero, o teste não tem variância para detectar.
- Isso é consistente com o desenho: como só trials bem-sucedidos chegam ao repositório (o solucao.py final só é commitado quando passa), a RQ2 tal como coletada hoje não discrimina entre tratamentos. Uma medição mais informativa exigiria registrar também trials censurados/malsucedidos, que hoje não aparecem no CSV.

### RQ3 — Estrutura do Código

- **complexidade_por_loc:** 3 pares completos. Mediana `com_ia` = 0.194 | Mediana `sem_ia` = 0.159. Wilcoxon p = 0.5000 → **não rejeita H0**.
- **duplicação:** 0 pares (métrica nunca coletada) — **RQ3 fica sem resposta para essa métrica** até a equipe medir duplicação em pelo menos um trial por tratamento e por participante.
- LOC mediano de controle: `com_ia` = 32.0, `sem_ia` = 27.5 (próximos, não há indício de verbosidade sistematicamente maior num tratamento).

## 6. Dashboard

Gerado pela RQ58 a partir do dataset unificado da RQ57: `dados/rq58_dashboard_inicial.png`. Compara tempo, taxa de sucesso e métricas estáticas medianas entre tratamentos e participantes.

## 7. Discussão

Nenhuma das três RQs mostrou diferença estatisticamente significativa entre `com_ia` e `sem_ia`. Isso deve ser interpretado com cautela, não como "IA não faz diferença":

1. **N extremamente pequeno.** Com apenas 3 pares por RQ, o teste de Wilcoxon tem poder estatístico muito baixo — o menor p-valor possível com n=3 já é 0.25, então a ausência de significância era praticamente esperada antes mesmo de rodar o teste. Os resultados devem ser lidos como **preliminares**, não conclusivos.
2. **Qualidade heterogênea dos dados de tempo.** Os trials `sem_ia` do bblop têm mediana de 0.28 s — tempos incompatíveis com escrever uma solução do zero (o próprio enunciado estima 20–25 min). A investigação do histórico do Git mostra que o código dessas katas já existia, commitado, antes da execução desses trials — ou seja, esses registros medem "tempo para rodar `testar` num código pronto", não "tempo para resolver o kata sem IA". Isso distorce diretamente o resultado da RQ1 (o par do bblop é o único dos três em que `sem_ia` aparece mais rápido que `com_ia`, na direção oposta da hipótese e da tendência dos outros dois participantes). Recomendamos que o grupo trate esses trials como uma ameaça à validade adicional a documentar, e que a Issue #35 (ainda pendente) seja coletada com um trial `sem_ia` genuíno.
3. **RQ2 sem variância observável**, pelo desenho atual de coleta (só sucessos chegam ao CSV) — ver Seção 5.
4. **Duplicação nunca medida** — RQ3 responde apenas parcialmente (via complexidade/LOC), a métrica de duplicação prevista na RQ33 segue em aberto.

## 8. Limitações Atuais

- 3 dos 12 trials planejados ainda não foram coletados (Issues #34, #35, #40).
- 2 trials têm tratamento divergente do plano de Issues, pendente de confirmação com o responsável (#41, #49 — João Pedro).
- Os trials `sem_ia` do bblop na kata02/kata04 têm validade questionável (ver Seção 7, item 2).
- Duplicação de código (`jscpd`) não foi medida em nenhum trial (ambiente sem Node.js/`npx` no momento da coleta).
- RQ2 não discrimina entre tratamentos porque apenas trials bem-sucedidos estão no dataset.
- N pequeno (3 pares por RQ) limita fortemente o poder estatístico; todos os resultados são preliminares.

## 9. Próximos Passos

1. Completar as Issues #34, #35, #40 (comandos já compartilhados com o grupo).
2. Confirmar com o João Pedro se #41/#49 são erro de rótulo ou refletem o trabalho real, e corrigir o CSV se for erro.
3. Medir duplicação (`jscpd`) em ao menos um trial por tratamento/participante, se houver Node.js disponível.
4. Reexecutar RQ57 → RQ51/RQ52/RQ53 → RQ58 após as coletas acima.
5. Registrar a mudança de desenho de 6→4 katas na documentação da RQ32/RQ33, para manter a metodologia reproduzível.

## 10. Repositório

Link do repositório: https://github.com/BernardoApl/metrica-software
