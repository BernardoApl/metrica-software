# RQ99 — Resultados e Discussão do artigo

Issue: #99. Seções 3 (Resultados) e 4 (Discussão) do artigo (template SBC), em [`entregas/laboratorio-03/artigo/resultados.tex`](../artigo/resultados.tex) e [`discussao.tex`](../artigo/discussao.tex). Uso no Overleaf: `\input{resultados}` e `\input{discussao}` depois de `\input{metodologia}`, com a pasta [`figuras/`](../artigo/figuras) ao lado dos `.tex`. As seções seguem a numeração anunciada no final da introdução (Seção 3: resultados; Seção 4: discussão; Seção 5: ameaças; Seção 6: replicação).

## O que está escrito

| Parte | Conteúdo | Fonte dos números |
|---|---|---|
| 3 (abertura) e tabela `tab:descritivo` | Mediana, Q1–Q3 e classes de cada métrica, com a classe geral C1 | [RQ95](RQ95/RELATORIO.md), [RQ97](RQ97/RELATORIO.md) (CFR (b)) |
| 3.1 RQ01 | Frequência: mediana, cauda, concentração, classes | [RQ91](RQ91/RELATORIO.md) |
| 3.2 RQ02 | *Lead time* (a) e (b), cobertura, comparação pareada, efeito do tamanho da release | [RQ94](RQ94/RELATORIO.md) |
| 3.3 RQ03 | CFR (a) e (b), comparação, o que cada proxy mede, sensibilidade às versões da heurística | [RQ97](RQ97/RELATORIO.md) |
| 3.4 RQ04 | Recuperação, censura, recuperação em até 24 h | [RQ92](RQ92/RELATORIO.md) |
| 3.5 | Classe geral C1 e perfis de velocidade e estabilidade | [RQ95](RQ95/RELATORIO.md) |
| 3.6 RQ05 | Spearman (a) e (b), quartis de frequência, cruzamento de classes | [RQ98](RQ98/RELATORIO.md) |
| 3.8 RQ07 | C1 a C7: % que muda e κ ponderado | [RQ96](RQ96/RELATORIO.md) |
| 4.1 e tabela `tab:hipoteses` | Cada hipótese H1 a H7 frente ao resultado, com veredito | RQ91 a RQ98 (os vereditos de H1 a H5 e H7 são os dos próprios relatórios) |
| 4.2 | O que surpreendeu e por quê (5 achados) | RQ94, RQ95, RQ96, RQ97, RQ98 |
| 4.3 | Implicações para a medição DORA em código aberto | síntese |

Figuras copiadas para `artigo/figuras/` (para o artigo ser autossuficiente no Overleaf): `distribuicoes_c1.png` (RQ95), `cfr_variantes.png` (RQ97) e `dispersao_df_cfr.png` (RQ98).

## Achados que o artigo destaca

1. **CFR (a) e (b) não concordam** (ρ = 0,07; 57,2% mudam de classe) e o nível do CFR (b) depende da heurística (mediana de 18,8% a 43,5% entre as versões v1 a v3). A v1 ignora 39,2% das releases por tag fora do SemVer.
2. **A correlação positiva entre frequência e CFR (b) (ρ = 0,40) é em grande parte aritmética**: quanto mais releases, maior a chance de um *patch* sair em 7 dias. Uma linha de base por permutação dá ρ = 0,59, e o ρ parcial controlando essa linha de base é −0,16. O artigo diz que os dados não confirmam nem contradizem a afirmação do DORA.
3. A classificação geral é limitada pela velocidade (21,1% com velocidade alta contra 85,4% com estabilidade alta).

## Pendências (marcadas com `\apreencher{...}`, busque por `apreencher`)

| Pendência | Depende de |
|---|---|
| Resultados da RQ06 (Seção 3.7) e discussão da H6 (tabela `tab:hipoteses` e Seção 4.3) | issue #93 (RQ06), ainda sem análise na `main` |
| P, R e F1 das versões da heurística e κ de Fleiss entre avaliadores (Seções 3 e 4) | consenso da amostra-ouro (#88) e `rq89_heuristica.py avaliar` (#89); o consenso não está no repositório (só a planilha assistida por IA de um avaliador) |
| Bônus RQ08 | issue #100 (não incluída no texto) |

Fora do escopo desta issue, mas relacionado: a tabela do funil da Metodologia (#90, `tab:funil`) ainda tem a coluna "Final" do funil como `\apreencher`; o funil real está em `dados/lab03_final/funil_selecao.csv`. A janela continua provisória nos CSVs e no texto.

## Verificação

- **Números:** cada valor do texto foi conferido com os `RELATORIO.md`, `resumo.json` e CSVs das RQ91 a RQ98. Os CFR e a correlação foram recalculados de forma independente nas RQ97 e RQ98, com conferência contra `metricas.variantes.cfr_entrega` e contra a coleta.
- **LaTeX:** o `.tex` **não foi compilado** (sem LaTeX nesta máquina, como na #90). Uma verificação por script conferiu chaves e ambientes balanceados, número de colunas de cada linha de tabela, `\ref` com `\label` correspondente e existência dos arquivos de figura.
- **Tamanho:** o limite é de 10 páginas no total. As Seções 3 e 4 têm 4 tabelas, 3 figuras e uma tabela de hipóteses; se o artigo passar do limite ao compilar, o primeiro corte sugerido é a figura `fig:cfr` (`cfr_variantes.png`, resumida no texto da Seção 3.3) e as subseções 3.1 a 3.4, que repetem números da tabela `tab:descritivo`.
