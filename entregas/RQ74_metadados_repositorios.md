# RQ74 — Coletar Metadados dos Repositórios

Issue: https://github.com/BernardoApl/metrica-software/issues/74

A issue possui apenas título. Revisada conforme o LAB03 (Mineração de Métricas
DORA), esta implementação coleta estrelas, linguagem, contribuidores e idade,
além dos metadados auxiliares. Adota a seleção existente
em `dados/repositorios_selecionados.csv` como população de entrada. Não refaz
a busca dos mais populares, não muda os filtros e não altera o snapshot LAB01.

## Coleta original de metadados GraphQL

Coleta realizada em 06/10/2026, entre 16:53:37 e 17:02:08 (America/Sao_Paulo;
19:53:37–20:02:08 UTC). Foram coletados **973 de 973 repositórios**, todos com
`status=ok` no esquema original, sem pendências. Há 973 IDs GitHub distintos e oito nomes alterados
em relação à seleção original. A ordem e a cobertura da seleção foram
conferidas, assim como todos os campos exportados entre JSON e CSV, o hash da
entrada e as relações issues fechadas ≤ totais e PRs aceitos ≤ totais.

Na primeira entrega, os seis testes da RQ74 e os três testes da seleção passaram. A execução real
validou a consulta GraphQL e o tratamento de repositórios renomeados. Estes
metadados representam uma nova coleta; não substituem as métricas históricas
do snapshot usado na seleção.

A revisão preserva essa coleta como `status_metadados` e acrescenta a etapa
REST de contribuidores. No esquema 2, `status=ok` exige metadados GraphQL,
contribuidores e idade válidos. Contagens globais de releases e issues são
descritivas e **não comprovam elegibilidade DORA na janela de 12 meses**.
Filtros de Actions, releases e runs continuam fora do escopo da #74.

## Executar

Configure `GITHUB_TOKEN` ou `GH_TOKEN` no ambiente, ou `GITHUB_TOKEN=...` no
arquivo `.env` da raiz (ignorado pelo Git). Não versione a credencial.

```powershell
python codigo-fonte/coleta/rq74_metadados_repositorios.py
```

São gerados `dados/rq74_metadados_repositorios.json` e
`dados/rq74_metadados_repositorios.csv`. Reexecutar o mesmo comando retoma os
registros pendentes/falhos e preserva os completos. Para uma nova coleta do
zero, informe outro destino, por exemplo `--saida dados/rq74_nova_coleta.json`.
`--entrada` aceita outro CSV com coluna `nome_completo`; `--tamanho-lote` aceita
de 1 a 20 repositórios por requisição (padrão 10). Nomes duplicados são
consultados uma vez, sem distinção entre maiúsculas e minúsculas.

Checkpoints antigos são atualizados sem repetir a consulta GraphQL: calculam-se
as idades e buscam-se somente contribuidores pendentes. A referência de idade
é fixa: início da coleta original, ou `--referencia-idade` em ISO 8601 com fuso
numa nova coleta. A retomada recusa mudança da referência. Ela não substitui
a janela de observação do DORA, que é definida pelo professor.
`--somente-cache` permite atualizar os campos derivados sem rede e retorna 1
enquanto houver campos pendentes.

## Dados e rastreabilidade

Consulta GraphQL por `owner/repo`, usando o cliente HTTP do projeto e apenas
biblioteca padrão. Campos baseados na
[documentação oficial do GitHub](https://docs.github.com/en/graphql/reference/repos#repository).

| Grupo | Campos |
|---|---|
| Identidade | Nome solicitado, nome atual, ID estável, URL, proprietário |
| Descrição | Descrição, homepage, linguagem primária, licença SPDX |
| Datas UTC | Criação, atualização de metadados, último push, instante de coleta |
| Popularidade | Estrelas e forks |
| Estado | Fork, arquivado, desabilitado, vazio, visibilidade, issues habilitadas |
| Estrutura | Branch padrão e tamanho em KB informado pela API |
| Contagens | Issues totais/fechadas, PRs totais/aceitos e releases |
| Características LAB03 | Contribuidores incluindo anônimos; idade em dias e anos |

Contribuidores são contados pelo endpoint REST `contributors?per_page=1&anon=true`,
usando a última página do cabeçalho `Link` (uma pessoa/entrada por página).
Sem paginação, conta-se a lista retornada; HTTP 204 corresponde a zero.
Falhas HTTP, paginação ambígua e erros de rede geram valor ausente, nunca zero.
A evidência salva inclui URL, status HTTP, Link, tamanho da primeira página e
instante da consulta; nomes e emails de contribuidores não são persistidos.
Essa é a contagem de entradas retornada pelo GitHub, incluindo anônimos, e não
uma deduplicação própria de pessoas nem apenas contribuidores ativos na janela.
O endpoint pode ter dados em cache e falhar em repositórios grandes; essas
limitações devem ser consideradas na análise. Referência:
[List repository contributors](https://docs.github.com/en/rest/repos/repos#list-repository-contributors).

`updatedAt` e `pushedAt` são distintos. Contagens de issues não incluem PRs.
Conexões usam `totalCount`, sem listar ou truncar itens. Ausência legítima de
linguagem/licença/branch/último push é nula, não zero. Repositórios renomeados
mantêm o nome da seleção ao lado do nome retornado pela API.

O JSON preserva resposta bruta por repositório, consulta de campos, hash SHA-256
do CSV de seleção, horários, rate limit e totais. CSV tem uma linha por nome
selecionado único, inclusive pendências/falhas. `status=ok` indica resposta
completa; os demais estados não devem ser usados como coleta completa.
Resultados são salvos a cada lote com substituição atômica por arquivo; se o
CSV ficar desatualizado após interrupção entre gravações, reexecutar o comando
o reconstrói a partir do JSON. A retomada pode abranger instantes diferentes,
explicitados em `coletado_em` por registro.

Rate limit provoca espera automática conforme `Retry-After` ou reset da cota,
em intervalos interruptíveis de até 30 segundos. Falhas transitórias têm
retentativas limitadas com backoff exponencial. Falhas de autenticação ou
esgotamento das retentativas resultam em código 1, preservando dados anteriores.
Erros de contribuidores são salvos por repositório e não apagam os metadados
GraphQL; na próxima execução somente entradas pendentes/falhas são consultadas.
Código 0 significa todos completos; Ctrl+C retorna 130.

## Dicionário dos campos CSV

Valores ausentes são células vazias no CSV e `null` no JSON. Contagens abaixo
representam o estado consultado, não contagens restritas à janela DORA.

| Coluna(s) | Tipo / unidade | Origem ou definição |
|---|---|---|
| `nome_solicitado` | texto | `nome_completo` da seleção |
| `status` | categoria | `ok` somente se GraphQL, contribuidores e idade estão completos; senão `incompleto` |
| `status_metadados` | categoria | Resultado da consulta GraphQL: ok, pendente, incompleto, indisponivel, erro_graphql ou erro_coleta |
| `coletado_em` | datetime UTC | Instante da coleta GraphQL daquele registro |
| `erro` | texto opcional | Diagnóstico GraphQL |
| `id_github` | texto | Repository.id |
| `nome_completo` | texto | Repository.nameWithOwner atual |
| `url` | URL | Repository.url |
| `descricao` | texto opcional | Repository.description |
| `homepage` | URL opcional | Repository.homepageUrl |
| `criado_em` | datetime UTC | Repository.createdAt |
| `atualizado_em` | datetime UTC | Repository.updatedAt |
| `ultimo_push_em` | datetime UTC opcional | Repository.pushedAt |
| `estrelas` | inteiro / estrelas | Repository.stargazerCount |
| `forks` | inteiro / forks | Repository.forkCount |
| `tamanho_kb` | inteiro / KB | Repository.diskUsage |
| `fork`, `arquivado`, `desabilitado`, `vazio` | booleano | isFork, isArchived, isDisabled, isEmpty, respectivamente |
| `visibilidade` | categoria | Repository.visibility |
| `issues_habilitadas` | booleano | Repository.hasIssuesEnabled |
| `proprietario` | texto | owner.login |
| `linguagem` | texto opcional | primaryLanguage.name |
| `licenca_spdx` | texto opcional | licenseInfo.spdxId |
| `branch_padrao` | texto opcional | defaultBranchRef.name |
| `issues_total`, `issues_fechadas` | inteiro / issues | issues.totalCount, totalCount com states=CLOSED |
| `prs_total`, `prs_aceitos` | inteiro / PRs | pullRequests.totalCount, totalCount com states=MERGED |
| `releases_total` | inteiro / releases | releases.totalCount; sem filtragem temporal |
| `referencia_idade` | datetime UTC | Referência fixada no checkpoint |
| `idade_dias` | decimal / dias | (referência − createdAt).total_seconds() / 86400; seis casas decimais |
| `idade_anos` | decimal / anos | Dias não arredondados / 365,25; seis casas decimais |
| `contribuidores_total` | inteiro / entradas | Contagem REST incluindo anônimos |
| `status_contribuidores` | categoria | ok, pendente ou erro |
| `contribuidores_coletado_em` | datetime UTC | Instante da consulta/tentativa REST |
| `contribuidores_erro` | texto opcional | Diagnóstico REST |

## Verificar

```powershell
python -B -m unittest discover -s codigo-fonte/testes -p test_rq74.py
```

Os testes usam respostas sintéticas isoladas e cobrem renomeação, campos nulos,
erros parciais, retomada, exportação, mudança de seleção, migração de checkpoint,
idade, contagem por paginação e espera de rate limit. Esses dados não são
gravados como dataset real. A implementação só produz o dataset final após
execução autenticada contra o GitHub.
