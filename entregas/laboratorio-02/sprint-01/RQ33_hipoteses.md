# RQ33 — Hipóteses, Variáveis e Ameaças à Validade do Experimento

Issue: #33. Etapa correspondente: Passo 1 (Desenho do Experimento) do LAB02.

## Goal (GQM)

Analisar o uso de assistentes de IA generativa na resolução de tarefas de programação, com o propósito de comparar seu efeito frente à codificação manual, com respeito a tempo de resolução, qualidade funcional (defeitos) e qualidade estrutural do código produzido, do ponto de vista do grupo pesquisador, no contexto de katas de dificuldade equivalente resolvidos pelos três integrantes do grupo sob condições controladas (crossover within-subject, time-boxed).

## (A) Hipóteses

**RQ1 — Tempo**

- H0(1): não há diferença entre a mediana do tempo até passar em todos os testes de aceitação ("time-to-green") com assistente de IA e sem assistente de IA.
- H1(1): a mediana do tempo até passar em todos os testes de aceitação com assistente de IA é diferente (menor) da mediana sem assistente de IA.

**RQ2 — Defeitos**

- H0(2): não há diferença entre a taxa de sucesso (% de testes de aceitação passando ao final do time-box) com e sem assistente de IA.
- H1(2): a taxa de sucesso com assistente de IA é diferente (maior) da taxa sem assistente de IA.

**RQ3 — Estrutura do código**

- H0(3): não há diferença entre a complexidade ciclomática média e a duplicação de código (normalizadas por LOC) do código produzido com e sem assistente de IA.
- H1(3): a complexidade ciclomática média e/ou a duplicação de código do código produzido com assistente de IA são diferentes das produzidas sem assistente de IA.

Todos os testes de hipótese serão bicaudais (não assumimos a priori a direção do efeito, embora a expectativa do grupo seja de redução de tempo e de defeitos com IA), usando o teste de Wilcoxon para amostras pareadas (Passo 4), consistente com o desenho within-subject.

## (B) Variáveis dependentes e métricas escolhidas

| RQ | Variável dependente | Métrica primária escolhida | Métrica complementar |
|---|---|---|---|
| RQ1 | Tempo de resolução | Tempo até passar em todos os testes de aceitação ("time-to-green"), em segundos; trial que atinge o time-box (35 min) sem sucesso é registrado como censurado em 2100 s, não descartado | Nº de verificações/interações (`testar`) registradas pelo script de cronometragem — exploratória, não obrigatória |
| RQ2 | Defeitos / qualidade funcional | Taxa de sucesso: % de testes de aceitação passando ao final do time-box | Nº absoluto de testes falhando ao final do tempo |
| RQ3 | Estrutura do código | Complexidade ciclomática média por função (Radon `cc`, já que a linguagem escolhida é Python — CK exige Java) | % de linhas duplicadas (via `jscpd`, já que Radon não cobre duplicação) |
| RQ3 (controle) | Tamanho do código | LOC (linhas de código) do arquivo `solucao.py` ao final do trial — obrigatória para normalizar complexidade/duplicação, pois código gerado por IA pode ser mais verboso | Índice de Manutenibilidade (Radon `mi`) — opcional/aprofundamento |

Justificativa: optamos pelas métricas primárias recomendadas pelo enunciado (time-to-green e taxa de sucesso) por serem mais robustas a diferenças entre katas (a taxa de sucesso normaliza katas com quantidades diferentes de testes; cada um dos 6 katas tem entre 6 e 7 testes, ver [RQ32](RQ32_katas.md)). Como a linguagem do experimento é Python, usamos Radon (não CK, que exige Java) e `jscpd` para duplicação, já que o Radon não cobre essa métrica. Dado o N pequeno (3 integrantes × 6 trials = 18 medições, ou 9 por tratamento), usaremos mediana e IQR nas tabelas descritivas, não média e desvio-padrão.

## (C) Variável independente

Uso ou não do assistente de IA (ChatGPT, versão gratuita) durante a resolução do kata — variável categórica binária (`com_ia` / `sem_ia`), já usada como valor do parâmetro `--tratamento` no script `rq28_cronometragem.py`.

## (D) Tratamentos

- **Tratamento "com_ia":** o participante pode consultar o ChatGPT (versão gratuita, web) livremente durante o trial, mas deve escrever/colar o código no editor manualmente.
- **Tratamento "sem_ia":** o participante resolve o kata sem qualquer assistente de IA generativa, apenas com a documentação oficial da linguagem e o próprio conhecimento.

O mesmo assistente de IA (ChatGPT gratuito) é usado por todos os integrantes do grupo em todos os trials com IA, para manter o tratamento comparável dentro do experimento.

## (E) Objetos experimentais

Os 6 katas autorais descritos em [RQ32 — Seleção e Validação de Katas](RQ32_katas.md), de dificuldade equivalente, implementados em Python, com testes de aceitação automatizados (`unittest`) e tempo estimado de resolução de ~20–25 minutos cada.

## (F) Tipo de projeto experimental

**Crossover / within-subject, contrabalanceado.** Cada um dos 3 integrantes do grupo resolve os 6 katas: 3 com assistente de IA e 3 sem, controlando a variação individual de habilidade (cada participante é seu próprio controle). A ordem de katas e a atribuição kata↔tratamento são contrabalanceadas entre os integrantes (ex.: o integrante 1 resolve os katas 01–03 sem IA e 04–06 com IA; o integrante 2 inverte a atribuição; o integrante 3 usa uma terceira combinação), para que efeito de aprendizado entre katas e ordem de apresentação não fiquem confundidos com o efeito do tratamento.

## (G) Quantidade de medições

3 integrantes × 6 katas = **18 trials no total**, sendo 9 trials com assistente de IA e 9 sem (3 por integrante em cada tratamento). Cada trial gera uma medição de tempo (RQ1), uma medição de taxa de sucesso/testes falhando (RQ2) e uma medição de complexidade ciclomática/duplicação/LOC (RQ3), totalizando 18 observações pareadas por RQ (comparadas via Wilcoxon, pareando por integrante).

## (H) Ameaças à validade

- **Efeito de aprendizado entre katas:** resolver um kata pode ensinar padrões (ex.: manipulação de strings, uso de `unittest`) úteis para o próximo. Mitigado pelo contrabalanceamento da ordem entre integrantes (Passo F) e pela escolha de katas com temas de negócio distintos entre si (frete, senha, contatos, turnos, estoque, cupom), reduzindo a transferência direta de solução entre eles.
- **Familiaridade prévia com a ferramenta de IA:** integrantes com mais experiência prévia em prompting no ChatGPT podem obter ganhos maiores, confundindo o efeito do tratamento com o efeito de habilidade individual no uso da ferramenta. Mitigado parcialmente pelo desenho within-subject (cada participante é comparado consigo mesmo) — mas fica registrado como limitação a discutir no Relatório Final.
- **Vazamento de solução já vista / memorização:** se os katas fossem exercícios clássicos indexados (LeetCode/HackerRank), o ChatGPT poderia reproduzir uma solução memorizada do treinamento em vez de efetivamente raciocinar sobre o problema, inflando artificialmente o ganho do tratamento "com IA". Mitigado ao usar exclusivamente katas autorais do grupo (ver [RQ32](RQ32_katas.md)), com contexto de negócio fictício e sem correspondência direta a problemas famosos.
- **Variação individual de habilidade entre integrantes:** integrantes têm níveis de experiência diferentes em Python. Mitigado pelo desenho crossover/within-subject: cada integrante serve como seu próprio controle (comparação pareada), então a habilidade absoluta de cada um não interfere na comparação entre tratamentos.
- **Efeito de fadiga/hora do dia:** trials realizados em sequência ou em horários muito diferentes do dia podem afetar desempenho de forma não relacionada ao tratamento. Mitigado ao recomendar que cada integrante distribua seus 6 trials em mais de uma sessão, evitando resolver todos em sequência ininterrupta.
- **Validade de constructo do time-box:** 35 minutos pode não ser suficiente para todos os katas na condição "sem IA", gerando muitos trials censurados nessa condição e reduzindo a variância observável. Mitigado ao registrar trials censurados no limite (2100 s) em vez de descartá-los (conforme instrução do laboratório), preservando a comparação mesmo quando o tratamento "sem IA" tem mais censura.
