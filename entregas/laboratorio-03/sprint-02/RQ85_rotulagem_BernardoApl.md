# RQ85 — Rotulagem da amostra-ouro por BernardoApl

Esta issue corresponde à avaliação manual de BernardoApl, usando o mesmo
sorteio dos avaliadores das issues #86 e #87. Não deve ser feito um novo
sorteio individual, nem usados os 100 repositórios do piloto como amostra final.

## Preparação

A coleta #82 precisa exportar pelo menos 300 repositórios em
`dados/lab03_final/`. Em seguida, executam-se as métricas e o gerador comum:

```powershell
python codigo-fonte/rq83_metricas_variantes.py
python codigo-fonte/validacao/rq86_amostra_ouro.py gerar
```

O gerador já implementado sorteia 60 repositórios e até cinco releases por
repositório, com semente 42, e cria as três planilhas com o mesmo conjunto
de itens. Se as planilhas já existirem, devem ser preservadas: não usar
`--sobrescrever` para retomar o trabalho.

A planilha desta issue será:

`dados/lab03_final/amostra_ouro/rotulos/rotulos_BernardoApl.xlsx`

## Preenchimento manual

Preencha apenas sua planilha, independentemente dos demais avaliadores:

- Aba `repositorios`: tipo principal de projeto e se as releases representam
  entregas reais ao usuário, consultando README e releases.
- Aba `releases`: se a finalidade principal é corrigir um defeito recente,
  consultando as release notes e os commits indicados nos links.
- Use `observacoes` para registrar justificativas e casos difíceis.

Use as listas de respostas existentes. Não altere identificadores, links ou
ordem das linhas. Não consulte os rótulos dos colegas nem os resultados
automáticos de `cfr_entrega_releases.csv` antes de terminar: a validação
humana precisa ser independente da heurística que será avaliada.

Rótulos sugeridos por IA não constituem a avaliação humana independente e
não devem ser registrados como se tivessem sido produzidos pelo avaliador.

## Conferir o preenchimento

```powershell
python codigo-fonte/validacao/rq86_amostra_ouro.py validar dados/lab03_final/amostra_ouro/rotulos/rotulos_BernardoApl.xlsx
```

O validador informa células vazias, respostas inválidas e diferenças em
relação ao sorteio original. A #85 só pode ser considerada concluída após
a avaliação manual e a validação da planilha preenchida; gerar o arquivo
vazio não conclui a issue.

## Situação em 14/10/2026

A execução da #83 foi tentada e informou ausência dos arquivos finais da
#82. A coleta da #82 continua ativa. A planilha oficial depende dessa
exportação; nenhum rótulo humano foi preenchido automaticamente.
