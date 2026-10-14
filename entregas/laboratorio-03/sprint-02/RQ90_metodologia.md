# RQ90 — Metodologia do artigo

Issue: #90. Seção 2 do artigo (template SBC), em [`entregas/laboratorio-03/artigo/metodologia.tex`](../artigo/metodologia.tex). Uso no Overleaf: `\input{metodologia}` depois de `\input{introducao}`.

## O que está escrito

Visão geral; fonte de dados e coleta (REST/GraphQL próprios, teto de 1.000 resultados, cache, rate limit, backoff, testes e CI); seleção e funil; definições operacionais (tabela); métricas e variantes das RQ01 a RQ04 com as decisões do grupo (primeira release, `compare` indisponível, commits com data posterior à release, censura à direita e à esquerda); heurística de release corretiva (v1, v2, v3); validação manual (sorteio com semente 42, três avaliadores independentes e cegos, kappa de Fleiss, consenso, P/R/F1); análise estatística planejada (RQ05 a RQ07).

## O que depende dos colegas ou do professor

Nenhum número foi inventado. Os pontos abaixo estão no `.tex` como `\apreencher{...}` (busque por `apreencher`):

| Pendência | Depende de |
|---|---|
| Coluna "Final" do funil (Tabela 1) | coleta final de 300+ repositórios (#82). A coluna "Piloto" usa o funil real da Sprint 01 (`dados/lab03/funil_selecao.csv`) |
| Janela oficial | confirmação do professor (a janela 01/10/2025 a 30/09/2026 é provisória) |
| P, R e F1 de cada versão da heurística | rótulos humanos (#85, #86, #87), consenso (#88) e `rq89_heuristica.py avaliar` (#89) |
| Kappa de Fleiss por dimensão e tamanho do consenso | consolidação do consenso (#88) |
| Protocolo de desempate | decisão registrada na #88 |

Quando a #88 definir o protocolo, ajustar também o texto da subseção de validação manual se ele diferir do descrito (por exemplo, maioria simples para dois a um).

## Verificação

O `.tex` não foi compilado (sem LaTeX nesta máquina); foram conferidos o balanceamento de chaves e de ambientes. Compilar no Overleaf junto com a introdução e checar que o artigo continua dentro do limite de 10 páginas.
