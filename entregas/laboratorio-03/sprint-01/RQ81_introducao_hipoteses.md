# RQ81 — Introdução e Hipóteses Informais do Artigo

Issue: #81. É a seção 1 do artigo do LAB03 (template SBC). A versão em LaTeX, pronta para colar no Overleaf, está em [`../artigo/introducao.tex`](../artigo/introducao.tex), e as referências em [`../artigo/referencias.bib`](../artigo/referencias.bib).

As hipóteses abaixo foram registradas **antes da análise dos dados**. Elas servem de base para a seção de Discussão (Lab03S03), na qual cada uma será confrontada com os resultados. Não devem ser editadas depois que os resultados forem vistos; se alguma for revista, a revisão vai como nota datada.

---

## 1. Introdução

Medir o desempenho de entrega de software é um problema antigo da engenharia de software. Nos últimos anos ele ganhou um vocabulário comum com as métricas DORA (*DevOps Research and Assessment*). Popularizadas pelo livro *Accelerate* [Forsgren et al. 2018] e atualizadas anualmente pelos relatórios *State of DevOps*, elas descrevem a entrega em duas dimensões. A **velocidade** é medida pela frequência de deploy e pelo *lead time for changes*. A **estabilidade** é medida pela taxa de falha das mudanças (*change failure rate*, CFR) e pelo tempo de recuperação após um deploy com falha. Um dos achados mais citados dessa linha de pesquisa é que velocidade e estabilidade **não** seriam um *trade-off*: as equipes de melhor desempenho iriam bem nas duas dimensões ao mesmo tempo [DORA 2024].

Esses resultados vêm, na maior parte, de **questionários** respondidos por profissionais de empresas. Em projetos open-source, os dados de entrega são públicos e podem ser **minerados**: releases, *commits* e execuções de integração contínua (CI) no GitHub Actions ficam registrados com data e resultado. O GitHub, porém, não registra "deploys em produção" nem "falhas em produção". Cada métrica DORA precisa então ser aproximada por um **proxy**. Uma release publicada faz o papel de deploy, e uma execução de CI com falha, ou uma release corretiva logo em seguida, faz o papel de falha. Proxies podem enganar. Uma biblioteca que publica uma release por mês não está "deployando" nada; quem faz isso são os usuários dela. Um *workflow* de CI vermelho indica falha de pipeline, e não necessariamente um defeito que chegou ao usuário.

Este trabalho minera as métricas DORA de repositórios open-source populares que usam CI/CD com GitHub Actions. Ele tem dois objetivos. O primeiro é **descrever** o desempenho de entrega desses projetos sob as definições operacionais comuns da disciplina: janela de 12 meses, *default branch*, releases não-*draft* e execuções disparadas por `push`. O segundo é **avaliar o quanto essas medidas são confiáveis**. Para isso, (i) validamos as heurísticas automáticas contra uma amostra rotulada manualmente por três avaliadores independentes e (ii) medimos o quanto a classificação DORA de cada repositório muda quando a definição operacional muda (análise de sensibilidade). Assim, a pergunta deixa de ser apenas "qual é o valor da métrica?" e passa a incluir "o quanto podemos confiar nesse valor?".

As questões de pesquisa são:

- **RQ 01.** Qual a frequência de deploys dos repositórios populares que usam CI/CD?
- **RQ 02.** Qual o tempo entre um *commit* e seu respectivo deploy (*lead time*), por release e por *commit*?
- **RQ 03.** Qual a taxa de falha das mudanças entregues, pelo proxy de CI e pelo proxy de entrega?
- **RQ 04.** Qual o tempo de recuperação após uma execução de CI/CD com falha?
- **RQ 05.** Repositórios com maior frequência de deploy apresentam maior ou menor taxa de falha?
- **RQ 06.** Quais características dos repositórios estão associadas a um melhor desempenho DORA?
- **RQ 07.** O quanto a classificação DORA de um repositório depende da definição operacional escolhida?

O pipeline de coleta foi escrito pelo grupo, sem bibliotecas de acesso à API do GitHub. Ele é executável com um único comando, tem cache e retomada, é coberto por testes automatizados que rodam no próprio GitHub Actions do grupo e será replicado por outro grupo da turma. O restante do artigo está organizado assim: a Seção 2 descreve a metodologia; a Seção 3 apresenta os resultados por RQ; a Seção 4 discute as hipóteses frente aos resultados; a Seção 5 trata das ameaças à validade; e a Seção 6 relata a replicação cruzada.

## 1.1 Hipóteses informais

Para cada RQ registramos o que **esperamos** encontrar e por quê. São hipóteses informais: orientam a leitura dos resultados, mas não são testes de hipótese formais, com exceção da RQ 05 e da RQ 06, que têm teste estatístico associado.

**H1 (RQ 01 — frequência de deploy).** Esperamos uma mediana da ordem de **uma release a cada uma ou duas semanas** (≈ 0,5 a 1 release/semana), o que coloca a maioria dos repositórios nas faixas **Medium** e **High**. A distribuição deve ter uma cauda longa à direita, com poucos repositórios Elite (≥ 7/semana), em geral projetos com releases automatizadas, como *nightlies* e *monorepos* que publicam um pacote por componente. *Por quê:* o critério de inclusão (≥ 5 releases na janela) já descarta os projetos que quase nunca publicam. Mesmo assim, projetos open-source costumam agrupar mudanças em versões, porque cada release tem custo para quem a consome (changelog, compatibilidade, atualização de dependências).

**H2 (RQ 02 — lead time).** Esperamos que a variante **(a) por release** tenha mediana na faixa de **semanas** (Medium, possivelmente Low, ≥ 30 dias, em muitos repositórios) e que a variante **(b) por commit** seja **sistematicamente menor**, na faixa de **dias** (High/Medium). *Por quê:* a variante (a) é definida pelo commit **mais antigo** da release. Basta um commit "esquecido", seja de um *branch* de longa duração, seja um *cherry-pick* ou um *rebase* que preservou a data de autoria, para o lead time daquela release explodir. A variante (b) dilui esse commit entre todos os demais. Esperamos também que a diferença entre (a) e (b) cresça com o tamanho das releases, medido em número de commits.

**H3 (RQ 03 — taxa de falha).**
- **(a) Proxy de CI:** esperamos CFR mediano entre **10% e 25%** (Elite/High). As falhas de pipeline são relativamente comuns em repositórios ativos, por testes instáveis (*flaky*), dependências externas e quebras corrigidas no commit seguinte. Ainda assim, o *default branch* costuma ser protegido por CI nos *pull requests*, o que filtra boa parte das quebras antes do `push`.
- **(b) Proxy de entrega:** esperamos CFR mediano **menor que o de CI**, entre **5% e 15%** (Elite), mas com variação maior entre repositórios. Uma release seguida por um *patch* em até 7 dias acontece, mas não na maioria das releases.
- Esperamos **correlação fraca** entre (a) e (b) (|ρ| < 0,3). As duas variantes medem fenômenos diferentes: uma, a fragilidade do pipeline; a outra, defeitos que escaparam até a release.

**H4 (RQ 04 — tempo de recuperação).** Esperamos uma mediana de **algumas horas**, entre 1 hora e 1 dia (High). Em projetos ativos, uma quebra no *default branch* bloqueia todos os colaboradores e tende a ser corrigida pelo próprio autor no mesmo dia. A distribuição deve ser muito assimétrica, com uma cauda de episódios de dias ou semanas em *workflows* secundários (documentação, *benchmarks*, *lint*) que ficam quebrados sem bloquear ninguém. Esperamos uma proporção de episódios **censurados** pequena (< 10%), porém concentrada justamente nesses *workflows* secundários.

**H5 (RQ 05 — velocidade × estabilidade).** Esperamos **ausência de trade-off**: correlação de Spearman próxima de zero ou **levemente negativa** entre frequência de deploy e CFR (b), o que concordaria com a afirmação do DORA. Para o CFR (a), esperamos correlação próxima de zero. Repositórios que publicam com mais frequência tendem a ter mais automação de testes e de release, o que deve compensar o maior número de mudanças. Ressalva: uma correlação fraca em open-source não implica relação causal e pode ser explicada por fatores de confusão, como tamanho da equipe e maturidade do projeto.

**H6 (RQ 06 — características associadas ao desempenho).**
- **Número de contribuidores:** repositórios no quartil superior devem ter **maior frequência de deploy** e **menor tempo de recuperação**, porque há mais pessoas para corrigir uma quebra. O CFR (a) também deve ser **maior**, porque mais commits concorrentes e mais *workflows* dão mais oportunidades de falha.
- **Tipo do projeto:** **bibliotecas/frameworks** devem ter lead time maior e frequência menor que **ferramentas CLI** e **aplicações**, porque seus usuários exigem estabilidade de API e versões mais espaçadas.
- **Linguagem principal:** esperamos diferenças significativas na frequência de deploy (ecossistemas como JavaScript/TypeScript e Go, com publicação automatizada de pacotes, tendem a lançar com mais frequência). Mesmo assim, os efeitos devem ser **pequenos a médios** (ε² < 0,06 na maioria dos testes) e várias diferenças devem perder significância após a correção de Holm.
- **Popularidade (estrelas):** esperamos efeito **desprezível**. Estrelas medem interesse acumulado, e não a dinâmica atual de desenvolvimento.

**H7 (RQ 07 — sensibilidade à definição operacional).** Esperamos que a classificação DORA seja **frágil**: que **pelo menos 30%** dos repositórios mudem de categoria geral entre a combinação de referência (C1: release, lead time (a), CFR (a)) e as alternativas, e que o kappa de Cohen ponderado fique na faixa **razoável a moderada** (0,2 a 0,6). Incluir pré-releases ou usar tags como unidade de deploy deve **inflar** a frequência de deploy, sobretudo em projetos com *release candidates* e *nightlies*. Trocar o lead time (a) pelo (b) deve **melhorar** a classe de lead time de muitos repositórios. Se H7 se confirmar, as conclusões das RQ 01 a 06 devem ser lidas como condicionais à definição escolhida, e não como propriedades absolutas dos projetos.

---

### Referências citadas nesta seção

- Forsgren, N.; Humble, J.; Kim, G. *Accelerate: The Science of Lean Software and DevOps*. IT Revolution, 2018.
- DORA. *Accelerate State of DevOps Report 2024*. Google Cloud, 2024. Ver também o [guia das métricas](https://dora.dev/guides/dora-metrics-four-keys/) e o [histórico das métricas](https://dora.dev/insights/dora-metrics-history/).
