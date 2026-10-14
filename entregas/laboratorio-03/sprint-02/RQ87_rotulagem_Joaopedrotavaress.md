# RQ87 — Rotulagem da amostra-ouro por Joaopedrotavaress

Esta issue corresponde à avaliação manual de Joaopedrotavaress, usando o mesmo sorteio dos avaliadores das issues #85 (`BernardoApl`) e #86 (`bacelete`). Não deve ser feito um novo sorteio individual, nem usados os 100 repositórios do piloto como amostra final. Protocolo completo em [RQ86](RQ86_amostra_ouro.md).

## Situação

**Pendente.** A rotulagem é um julgamento humano independente (seção 6 do enunciado) e depende de duas etapas que ainda não aconteceram:

1. a coleta final da #82 exportar pelo menos 300 repositórios em `dados/lab03_final/`;
2. alguém rodar `gerar` (RQ86) e commitar o sorteio e as três planilhas vazias.

Nenhum rótulo foi preenchido, sugerido ou estimado por IA ou pela heurística: isso invalidaria o kappa de Fleiss (RQ88) e o F1 da heurística (RQ89). A planilha só conta como entrega depois de preenchida à mão e validada.

## Passo a passo quando o sorteio existir

```powershell
git pull
```

1. Abra **apenas** `dados/lab03_final/amostra_ouro/rotulos/rotulos_Joaopedrotavaress.xlsx`. Não use `--sobrescrever` ao retomar o trabalho.
2. Aba `repositorios` (60 linhas): `tipo_projeto` e `entregas_reais`, lendo o README e a página de releases.
3. Aba `releases` (até 300 linhas): `corretiva` (sim/não), lendo as *release notes* (`link_release`) e a lista de commits (`link_commits`). O objetivo **principal** da release é corrigir um defeito recente?
4. Use `observacoes` para justificar casos difíceis; isso ajuda na reunião de consenso (RQ88).
5. Não consulte as planilhas dos colegas, `cfr_entrega_releases.csv` nem a saída da heurística da [RQ89](RQ89_heuristica_corretiva.md) antes de terminar. Não rode a avaliação da RQ89 contra a própria planilha antes de ela estar commitada.
6. Confira e commite referenciando a **própria** issue:

```powershell
python codigo-fonte/validacao/rq86_amostra_ouro.py validar dados/lab03_final/amostra_ouro/rotulos/rotulos_Joaopedrotavaress.xlsx
git add dados/lab03_final/amostra_ouro/rotulos/rotulos_Joaopedrotavaress.xlsx
git commit -m "#87 rotula amostra-ouro de 60 repositorios"
```

A #87 só pode ser considerada concluída após a avaliação manual e a validação da planilha preenchida; este documento não a conclui.
