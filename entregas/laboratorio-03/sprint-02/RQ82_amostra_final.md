# RQ82 — Coleta completa e amostra de 300+ repositórios

## Execução

Configure `GITHUB_TOKEN` no ambiente ou no `.env` da raiz e execute:

```powershell
python codigo-fonte/rq82_amostra_final.py --config config/rq82_amostra_final.json
```

A configuração usa os 8.000 candidatos com metadados, selecionados por estrelas,
até atingir 300 aprovados. Mantém no mínimo 5 releases publicadas, não draft e
não pré-release, e 50 runs válidos de push no default branch dentro da janela.
Não reduz os critérios para atingir a meta. Se os candidatos acabarem antes,
a auditoria registra `meta_nao_atingida` e o comando retorna 2.

A janela herdada é **01/10/2025 a 30/09/2026**, ainda provisória. A issue #82
não contém descrição que confirme as datas. A coleta pode ser executada nessa
janela, mas `amostra_final_validada` permanece falsa enquanto
`janela_confirmada` não for verdadeira com respaldo do professor.

## Coleta e retomada

- Reutiliza o cliente REST/cache da RQ78 e o pipeline de seleção e métricas.
- Mantém o limite operacional de 20.000 runs do piloto: repositórios acima
  desse limite são excluídos por inteiro e contabilizados no funil. Isso
  restringe a amostra e deve ser mencionado como limitação do estudo.
  Os aprovados não têm seus runs cortados. Comparações de commits não têm
  limite de páginas na configuração final.
- Complementa os aprovados com tags e datas de autoria dos commits (RQ75).
- Salva um checkpoint comprimido por repositório em
  `dados/.cache/rq82_repositorios/`. A identificação inclui configuração,
  candidatos e código, evitando mistura de janelas e versões.
- Reutiliza checkpoints íntegros na retomada. Falhas de acesso, tags incompletas
  e comparações truncadas/indisponíveis são reavaliadas. O cache HTTP segue as
  regras da RQ78; respostas definitivas como 404 exigem outro diretório de cache
  para verificar eventual recuperação do recurso.
- HTTP 401 em compare interrompe a execução, sem ser tratado como release
  ausente. O token nunca entra nos arquivos de resultados.
- A amostra anterior de 100, em `dados/lab03/`, permanece preservada.

As consultas podem exigir várias renovações de cota da API. Interromper e
executar o mesmo comando reaproveita os dados já coletados.

## Consolidação em `dados/lab03_final/`

São gerados os CSVs do pipeline (métricas, candidatos avaliados, releases,
workflow runs comprimidos, intervalos auditados, lead times e commits
comprimidos), `funil_selecao.csv`, `tags.csv` e `resumo_execucao.json`.
O arquivo `validacao_rq82.json` é a referência para a conclusão da #82:

- pelo menos 300 repositórios únicos, atendendo aos critérios;
- quantidade final do funil igual à amostra;
- idade e contribuidores presentes;
- ausência de teto de runs, compare truncado/indisponível e tags incompletas;
- commits com SHA e data de autoria;
- janela confirmada.

Pendências não são ocultadas nem substituídas por zero. `meta_atingida` indica
apenas quantidade; não substitui `amostra_final_validada`.
Retornos: 0 = validada; 2 = consolidada com pendências; 1 = erro operacional;
130 = interrupção. Os checkpoints permanecem disponíveis em caso de erro.

## Redução do tempo de coleta (clone git parcial)

A coleta por API levava mais de 14 h: só nos 18 primeiros repositórios eram 6.932 consultas de data de tag (`/commits/{sha}`), além de uma ou mais páginas de `compare` por release. Agora (`commits_via_git: true`):

- **Tags e commits entre releases** vêm de um clone git parcial anônimo (`git fetch --filter=tree:0`, só `refs/tags/*`; `codigo-fonte/coleta/git_local.py`). `git log base..head` devolve o mesmo conjunto de commits do `compare/{base}...{head}`, sem teto de páginas, e a data de autoria é a mesma (`%at`, em UTC). O clone leva de 2 a 15 s por repositório, é apagado logo após a avaliação e não usa o token nem a cota da API. Se o clone falhar, aquele repositório volta ao `compare` (a coluna `fonte_commits` registra a origem; nos 300 aprovados foi sempre `git`).
- **Equivalência verificada** contra a API real em 4 repositórios (`nvm-sh/nvm`, `toeverything/AFFiNE`, `laravel/laravel`, `shadcn-ui/ui`): 29 de 29 comparações com SHAs, datas e mensagens idênticos.
- **Corte antecipado do limite de 20.000 runs.** A soma do `total_count` da primeira página de cada mês (que a coleta pede de qualquer forma, vindo do cache) é um limite inferior do total real: nos 1.200 pares repositório-mês da S01 nunca passou do coletado. Se a soma já passa de 20.000, o repositório é descartado sem baixar até 200 páginas. O resultado do funil é o mesmo; só se evita o desperdício de cota.
- **Sem supervisão.** Erro temporário da API (5xx, rede) não derruba mais a execução: o repositório é refeito em nova passada (`--passadas`, padrão 3) e, se persistir, a auditoria acusa `falha_temporaria_persistente`. O log traz a hora de cada linha.

**Execução de 20/10/2026** (cache da S01 aproveitado para os ~272 primeiros candidatos): 778 candidatos avaliados, 300 aprovados em ~2 h 20 min, 9.870 requisições à API (14.903 respostas do cache), nenhuma espera de rate limit. O restante do tempo é a paginação de workflow runs, que só existe pela API. Funil: 8.000 → 7.519 (pré-filtro) → 707 com Actions → 381 com ≥ 5 releases → 350 sob o limite de 20.000 runs → **300** com ≥ 50 runs válidos. `validacao_rq82.json`: única pendência `janela_nao_confirmada`.

A fonte dos commits mudou da S01 (API, `limite_paginas_compare = 20`) para a S02 (git, sem limite): mencione na Metodologia e nas ameaças à validade.

## Testes

### Otimizacao da consulta de tags

A coleta reaproveita a data de autoria de commits ja recebidos nas comparacoes
entre releases quando o SHA da tag coincide exatamente. Datas ausentes,
invalidas, sem fuso ou conflitantes continuam exigindo a consulta individual.
Todas as tags e paginas continuam sendo percorridas. Nao se alteram a ordem
dos candidatos, os criterios, a janela, os limites ou a meta de 300.

Na verificacao inicial de 18 repositorios coletados, 1.486 dos 6.932 SHAs de
tags ja tinham a mesma data nas comparacoes: cerca de 21% das consultas
individuais dessa etapa podem ser evitadas. Esse percentual nao representa
reducao garantida do tempo total, que tambem inclui runs, compares e esperas
pela cota. O cache HTTP existente permanece reutilizavel; o hash de codigo
dos checkpoints continua protegendo a retomada entre versoes.

```powershell
.\.venv\Scripts\python.exe -m pytest codigo-fonte/testes/test_rq82.py codigo-fonte/testes/test_pipeline_dora.py codigo-fonte/testes/test_rq76_compare.py codigo-fonte/testes/test_rq75.py -q
```

39 testes passaram na implementação inicial. Fixtures sintéticas validam o
limiar 299/300, duplicação, janela provisória, metadados ausentes, truncamento,
retomada, isolamento de configuração e propagação de falhas de autenticação.
Essas fixtures não constituem a amostra real nem são exportadas para `dados/`.
