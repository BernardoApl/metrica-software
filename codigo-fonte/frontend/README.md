# Frontend do experimento de cache

## Dashboard final (#117)

As sete seções pedidas no enunciado, nesta ordem: 1. Cenário (`#cenario` a `#hipoteses`), 2. Os dados (G1), 3. Como os testes funcionam (G2), 4. Erro tipo I (G3), 5. Poder (G4), 6. Resultados reais (tabela) e 7. Conclusão. Um único comando reconstrói tudo a partir dos resultados salvos e abre a página:

```powershell
python codigo-fonte/frontend/rq109_dashboard.py
```

`rq117_g3_q3.py` completa o G3 com o erro tipo I de cada situação simulada: a Q1 (#110) ao lado das situações da Q3 (#116), com a linha de 5%, e três painéis com o erro tipo I por número de pares (10 a 50). O bloco fica entre os marcadores `G3Q3:INICIO` e `G3Q3:FIM`, abaixo do bloco da #111. Cores dos testes iguais às do G2, G3 e G4: t pareado `#2a78d6`, Wilcoxon `#eb6834`. No celular, os painéis viram uma coluna e o gráfico de barras rola na horizontal.

## Conclusão e recomendação (#115)

A seção `#conclusao` (7) fecha o dashboard, na ordem pedida pelo enunciado:

- **Antes de simular × o que encontramos**: dois cartões lado a lado. A expectativa fica na constante `EXPECTATIVA` de `rq115_conclusao.py` (o grupo pode editar o texto); os achados vêm da Q1 (#110) e da Q2/Q3 (#113). Um veredito diz se a simulação confirmou a expectativa e o que explica a diferença.
- **Comparação das hipóteses**: tabela com a H0 de cada teste (média μ<sub>d</sub> = 0 × simetria em 0), estatística, p-valor, decisão e tamanho do efeito nos dados reais (rotinas da #105, via #112).
- **Recomendação**: qual teste usar no cenário e quando a escolha mudaria. A regra é explícita e roda sobre os números salvos: escolhe o cenário simulado mais parecido com os dados reais (|assimetria| ≥ 1 → assimetria) e recomenda o teste mais poderoso nele, desde que o erro tipo I não passe de 10% (2 × α). Hoje: t pareado (cenário assimetria, erro tipo I 8,0% contra 21,8% do Wilcoxon).
- **Tamanho da amostra e importância prática** (expansível) e **principal limitação**.

```powershell
python codigo-fonte/frontend/rq115_conclusao.py
```

Lê os resultados salvos (não refaz simulações), substitui somente o bloco entre `CONCLUSAO:INICIO` e `CONCLUSAO:FIM` e participa do `rq109_dashboard.py`.

## G4 — Poder (#114)

A seção `#poder` mostra as curvas de poder da #113: quatro painéis SVG estáticos (base, amostra pequena, outliers e assimetria), cada um com o t pareado (`#2a78d6`) e o Wilcoxon pareado (`#eb6834`) — as mesmas cores do G2 e do G3. Linha cheia: α = 0,05; linha fina tracejada: α = 0,01 (pergunta 12 da apresentação). Referências tracejadas em 5% (erro tipo I) e 80% (poder usual). Eixo x: tamanho do efeito d<sub>z</sub>; eixo y: rejeições de H0 (%). Cada ponto tem um `<title>` com o valor, o IC 95% e o δ em ms, mostrado ao passar o mouse, sem JavaScript.

Abaixo dos painéis há um texto gerado a partir dos números (qual teste detecta melhor e onde a vantagem muda de lado), uma tabela-resumo por cenário (erro tipo I, d<sub>z</sub> para 80% de poder e quem detecta melhor) e uma explicação expansível de como os cenários foram construídos.

```powershell
python codigo-fonte/frontend/rq114_g4.py
```

Lê `entregas/experimento-cache/RQ113/resultados.json` e não refaz as simulações (cerca de 2 minutos; rode `python codigo-fonte/analise/rq113_poder.py` para isso). Valida as proporções contra as contagens e os intervalos, e substitui somente o bloco entre `G4:INICIO` e `G4:FIM`. Também participa do `rq109_dashboard.py`.

## Resultados reais (#112)

A seção `#resultados-reais` apresenta os 30 pares reais da #102: tempos médios,
estatísticas t(29) e W+, p-valores sem arredondamento para zero, Cohen d_z,
correlação rank-biserial, IC 95% da diferença média e estimador de Hodges–Lehmann.
Inclui decisões bilaterais a alfa 0,05 e ressalvas sobre normalidade, simetria,
independência e tendência temporal. Não usa dados simulados como evidência real.

```powershell
python codigo-fonte/frontend/rq112_resultados_reais.py
```

O gerador valida os arquivos da coleta pela #103 e aplica as funções existentes
da #105. Atualiza somente os marcadores `REAIS:INICIO` e `REAIS:FIM`; também
participa da reconstrução por `rq109_dashboard.py`. Funciona sem JavaScript.
Em telas pequenas, as tabelas do G3 e dos resultados reais passam a apresentar
cada teste em um bloco com rótulos, sem esconder p-valores ou efeitos fora da tela.
No desktop, a comparação continua em colunas. As explicações expansíveis são
operáveis por teclado. Selos distinguem simulação sob H0 de coleta real, e a
decisão resumida dos testes é gerada a partir dos resultados, não de texto fixo.

O G3 também cruza as rejeições com os p-valores do CSV da #110, em vez de
confiar apenas no resumo. Os três tempos médios usam seis casas decimais em ms
para não apresentar o tempo sem cache e a diferença média como valores iguais
por arredondamento. Essa formatação não representa precisão física adicional.

## G3 — Erro Tipo I (#111)

A seção `#erro-tipo-i` apresenta as taxas dos testes t e Wilcoxon da #110,
com barras partindo de zero, linha de referência de 5%, IC binomial de 95%
e tabela acessível. Mantém as cores dos testes no G2. Funciona também sem
JavaScript e por abertura direta do HTML.

Para atualizar somente o G3 após uma execução da #110:

```powershell
python codigo-fonte/frontend/rq111_g3.py
```

O comando valida a conclusão sob H0, alfa 5%, taxas, intervalos e hashes dos
artefatos. Substitui somente o bloco entre `G3:INICIO` e `G3:FIM`, preservando
as demais seções. A reconstrução por `rq109_dashboard.py` também atualiza o G3,
sem refazer as simulações. Se a entrada estiver ausente ou inválida, falha
explicitamente antes de substituir o gráfico.

As hastes representam incerteza Monte Carlo, não dispersão dos tempos ou
poder dos testes. A tabela usa quatro casas nos intervalos para distinguir
o limite inferior de 5,0035% do t pareado da referência de 5%.

## Issue #101

Seção independente de cenário experimental, pergunta de pesquisa e hipóteses H0/H1. HTML e CSS locais, sem dependências, JavaScript, token ou API. Não implementa as issues #102–#109.

Na raiz do repositório:

```powershell
python -m http.server 8080 --bind 127.0.0.1 --directory codigo-fonte/frontend
```

Acesse http://127.0.0.1:8080. Também é possível abrir `index.html` diretamente. Encerre o servidor com Ctrl+C.

## Conteúdo e decisões

- Cenário: comparação pareada dos tempos da mesma operação com e sem cache, conforme o tema das issues #102–#105.
- Variáveis e tratamentos; convenção `d = tempo_sem_cache - tempo_com_cache`.
- Pergunta bilateral e formulação inicial de H0/H1 para o teste t pareado.
- Detalhamento próprio do Wilcoxon, sem confundir sua hipótese com igualdade de médias.
- Protocolo alinhado à coleta real da #102: agregação do CSV por linguagem, cache de resultado aquecido, 30 pares de lotes de 20 operações, ordem balanceada e três pares de aquecimento separados.
- A página identifica a coleta de 03/11/2026 e distingue registros de entrada, repetições e pares. Não apresenta p-valores nem conclusões estatísticas.
- Âncoras de navegação e seções expansíveis nativas, operáveis por teclado; layout responsivo; foco visível e suporte à preferência por movimento reduzido.

## Integração futura

Os IDs `cenario`, `protocolo`, `pergunta` e `hipoteses` são âncoras estáveis. A #109 pode incorporar o conteúdo de `main` e os estilos no dashboard. A interface mantém a proposta bilateral da #101; a coleta não representa aprovação dessa escolha pelo professor. Antes de testes inferenciais, avaliar os pressupostos e a dependência entre pares que compartilham entrada e ambiente.

Fonte do cenário: [protocolo da #102](../coleta/README_rq102_tempos_cache.md) e [manifesto da coleta](../../dados/experimento_cache/20261103T213612Z_ebe7be6978/execucao.json). A página é estática e descreve essa execução específica; não simula acompanhamento ao vivo. Se o protocolo mudar, atualizar a seção junto com sua documentação.

Não há gráficos nem chamadas a backends nesta entrega. Os expansores servem apenas para explicar o cenário e as hipóteses.

Fontes estatísticas: [SciPy ttest_rel](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_rel.html) e [SciPy wilcoxon](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.wilcoxon.html).

## Issues #108 e #109: G1 e dashboard

`rq109_dashboard.py` executa a #107 e a #108, atualiza o bloco do G1 em `index.html` e abre a página:

```powershell
python codigo-fonte/frontend/rq109_dashboard.py
```

Só o trecho entre os marcadores `G1:INICIO` e `G1:FIM` é gerado; o resto da página continua editável à mão. Use `--sem-abrir` para apenas reconstruir.

### Integração

- **#104:** o gerador grava `entregas/experimento-cache/RQ104/pares_simulados.csv` (amostra do cenário observado), lido pela #107; o aviso de dados provisórios saiu do G1.
- **#106:** o G2 é interativo (SVG desenhado por `g2.js` a partir de `dados/g2.js`), em vez de um `graficos/g2.svg` estático; ver a seção abaixo.
- **Cores:** t pareado `#2a78d6` e Wilcoxon `#eb6834` em G2 a G4. O G1 usa `#6250d6` (real) e `#1baf7a` (simulado), para não confundir origem dos dados com teste.

## Issue #106 — G2: distribuições sob H0, regiões de rejeição e p-valores

Seção `#testes` ("3 Como os testes funcionam"), desenhada em SVG por `g2.js` (JavaScript puro, sem bibliotecas nem CDN). Os dados vêm de `dados/g2.js`, gerado por [`rq106_dados_g2.py`](../analise/rq106_dados_g2.py) a partir das RQ104 (amostras simuladas) e RQ105 (testes). É um `.js` que atribui `window.G2_DADOS`, então a página também abre por `file://`.

O `rq109_dashboard.py` já roda as RQ104, RQ105 e RQ106 antes do G1. Para regenerar só o G2:

```powershell
python codigo-fonte/analise/rq104_gerador_simulacao.py
python codigo-fonte/analise/rq105_testes_pareados.py
python codigo-fonte/analise/rq106_dados_g2.py
```

O que o G2 mostra, em dois painéis lado a lado:

- **t pareado**: densidade da t de Student com 29 gl (H0), região de rejeição bilateral |t| > 2,045 sombreada em cinza e limitada por linhas tracejadas, a área do p-valor (|T| ≥ |t obs|) preenchida na cor do teste e o t observado como linha vertical. Quando o t observado sai do eixo [−5, 5], ele é indicado na borda com uma seta.
- **Wilcoxon pareado**: distribuição exata de W+ sob H0 (permutação dos sinais, condicionada aos postos da amostra, inclusive postos médios), região de rejeição W+ ≤ 137 ou W+ ≥ 328, área do p-valor (as duas caudas a partir do W+ observado e do seu espelho) e W+ observado.

Um seletor troca a amostra de exemplo: simulada com H0 verdadeira (padrão, em que as áreas do p-valor são visíveis), simulada no cenário observado e dados reais. Nas duas últimas, as estatísticas ficam no extremo e o texto explica que a área do p-valor é pequena demais para aparecer. Abaixo dos painéis há um texto gerado para a amostra escolhida (o que cada teste compara, onde fica a região de rejeição, o que o p-valor significa e o que não significa) e uma tabela com estatística, região de rejeição, p-valor e decisão. Passar o mouse mostra o valor e a densidade/probabilidade do ponto.

Cores fixas por teste, para reutilizar em G1, G3 e G4: `--cor-t: #2a78d6` (t pareado) e `--cor-w: #eb6834` (Wilcoxon pareado), definidas em `styles.css` (classes `.serie-t` e `.serie-w`).
