# RQ75 — Coletar releases, tags e commits entre releases

O coletor `codigo-fonte/coleta/rq75_releases_tags_commits.py` usa a amostra
selecionada em `dados/lab03/metricas_repositorios.csv` por padrão. A lista de
8.000 candidatos não é tratada como amostra elegível. Reutiliza o cliente REST
da RQ78 e a coleta paginada de comparações da RQ76, sem PyGithub.

## Executar e retomar

Com `GITHUB_TOKEN` no ambiente ou no `.env` da raiz:

```powershell
python codigo-fonte/coleta/rq75_releases_tags_commits.py
```

Para validar apenas um repositório já presente na amostra:

```powershell
python codigo-fonte/coleta/rq75_releases_tags_commits.py --repositorio nvm-sh/nvm --saida dados/lab03/rq75_validacao
```

A janela vem de `config/pipeline.json`, atualmente **provisória**, de
2025-10-01 a 2026-09-30. Não é apresentada como confirmação das datas do
professor. O aviso é preservado no resumo. Mudanças de janela ou entrada
exigem outra `--saida`; uma nova fotografia da API também exige outro `--cache`.

Respostas são armazenadas em `dados/.cache/rq75/`. Cada repositório concluído
tem checkpoint JSON; execuções interrompidas reaproveitam os checkpoints
completos e o cache das consultas. Registros incompletos são tentados novamente.
Respostas HTTP definitivas (por exemplo, 404) permanecem no cache conforme a
RQ78; para verificar se esse recurso voltou a existir, use outro `--cache`.

## Regras e rastreabilidade

- Releases: segue toda a paginação, sem presumir ordem por `published_at`.
  Mantém o histórico anterior à janela para identificar a base correta.
  `created_at` não substitui a ausência de publicação.
- Tags: segue todas as páginas e consulta `/commits/{sha}`. A data usada é
  `commit.author.date`, inclusive para tags sem release. Não usa a data de
  criação do objeto de tag anotada. Tags que apontam ao mesmo SHA reaproveitam
  a consulta. `tem_release` indica associação a qualquer release coletada,
  inclusive pré-release; não significa deploy válido.
- Commits: compara cada release publicada, não draft e não pré-release da
  janela com a anterior em ordem cronológica. A base pode estar fora da janela.
  A primeira release da história fica marcada `sem_release_anterior`.
- Comparações: usa paginação de 100 commits até o fim, sem o teto operacional
  de 20 páginas usado por padrão na RQ76. Preserva SHA, data de autoria e a
  primeira linha da mensagem, limitada a 200 caracteres conforme a RQ76.
  Falhas e comparações incompletas aparecem na auditoria; não viram zero commits.
- Os dois dias extremos da janela são inclusivos, também para frações de segundo.
  Tags e comparações não comprovam que o commit pertença ao default branch;
  branches de manutenção, tags movidas, rebases e monorepos são limitações.

## Saídas em `dados/lab03/rq75/`

| Arquivo | Conteúdo |
|---|---|
| `releases.csv` | Histórico coletado, flags de publicação e marcação da janela |
| `tags.csv` | Tag, SHA, data de autoria, associação a release, janela e status |
| `comparacoes.csv` | Release, base, status, total esperado/coletado e truncamento |
| `commits.csv.gz` | Commits associados a cada par de releases; um SHA pode aparecer em vários pares |
| `repositorios/*.json` | Checkpoints com os dados e status de cada repositório |
| `resumo.json` | Janela, hash da entrada, nomes solicitados, contagens e conclusão |

O retorno é 0 quando todos os repositórios solicitados estão completos, 1 em
erro ou incompletude e 130 em interrupção. A coleta não calcula novas métricas
nem altera os filtros de inclusão da amostra; as métricas de lead time continuam
na RQ76. O pipeline existente também utiliza a correção de paginação de releases.

## Validação

```powershell
.\.venv\Scripts\python.exe -m pytest codigo-fonte/testes/test_rq75.py codigo-fonte/testes/test_coleta_dora.py codigo-fonte/testes/test_rq76_compare.py codigo-fonte/testes/test_pipeline_dora.py -q
```

Os 42 testes do comando acima passaram. Usam fixtures sintéticas isoladas, incluindo releases fora de ordem,
tags repetidas, SHA compartilhado, 301 commits, primeira release, base fora da
janela, truncamento, falhas HTTP, exportação e retomada de checkpoint.

A tentativa real de validação em 08/10/2026 foi rejeitada pelo GitHub com
HTTP 401. Portanto, ainda não há coleta real concluída da RQ75 nesta execução.

Referências: [releases](https://docs.github.com/en/rest/releases/releases#list-releases),
[tags](https://docs.github.com/en/rest/repos/repos#list-repository-tags),
[commits e compare](https://docs.github.com/en/rest/commits/commits#compare-two-commits).
