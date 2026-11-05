# Frontend do experimento de cache

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

## Issue #106 — G2: distribuições sob H0, regiões de rejeição e p-valores

Seção `#testes` ("05 Como os testes funcionam"), desenhada em SVG por `g2.js` (JavaScript puro, sem bibliotecas nem CDN). Os dados vêm de `dados/g2.js`, gerado por [`rq106_dados_g2.py`](../analise/rq106_dados_g2.py) a partir das RQ104 (amostras simuladas) e RQ105 (testes). É um `.js` que atribui `window.G2_DADOS`, então a página também abre por `file://`.

Para regenerar os dados (depois de mudar a RQ104 ou a RQ105):

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
