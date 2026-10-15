# RQ83 — Métricas DORA nas variantes obrigatórias

Implementa o cálculo offline das RQ 01 a 04 do enunciado do LAB03. A issue
#83 tem apenas o título, sem descrição adicional. Esta etapa usa a amostra
selecionada anteriormente: não busca candidatos, não altera a coleta da #82
e não produz rótulos humanos da #85 nem análise de sensibilidade da RQ 07.

## Executar

Após a exportação da amostra final pela #82, na raiz do projeto:

```powershell
python codigo-fonte/rq83_metricas_variantes.py
```

Entrada padrão: `dados/lab03_final/`. Saída: `dados/lab03_final/rq83/`.
Não exige token ou conexão ao GitHub. As datas vêm do `resumo_execucao.json`
da coleta, evitando calcular métricas com outra janela por engano.

Arquivos de entrada obrigatórios:

- `resumo_execucao.json` e `metricas_repositorios.csv`;
- `releases.csv` e `workflow_runs.csv.gz`;
- `lead_time_releases.csv` e `commits_releases.csv.gz`.

Sem esses arquivos, a execução normal falha com uma mensagem indicando
o que falta. Para diagnosticar uma coleta antiga sem dados de lead time:

```powershell
python codigo-fonte/rq83_metricas_variantes.py --entrada dados/lab03 --saida dados/rq83_piloto --permitir-parcial
```

O modo parcial mantém lead time ausente (célula vazia), registra as
pendências e retorna 2. Não transforma ausência de dados em zero.

## Definições

| Métrica | Cálculo |
|---|---|
| Frequência | Releases publicadas, sem draft/pré-release, divididas pelas semanas da janela inclusiva |
| Lead time (a) | Mediana do tempo entre o commit mais antigo e a publicação de cada release |
| Lead time (b) | Mediana dos tempos de todos os commits de todas as releases; não é mediana de medianas |
| CFR (a), CI | Falhas / (falhas + sucessos), somente `push` no default branch e conclusões válidas |
| CFR (b), entrega | Releases seguidas por uma corretiva em até sete dias / releases avaliáveis |
| Recuperação | Mediana dos episódios completos por workflow, do início da primeira falha ao fim do sucesso seguinte |

Lead time é medido em dias; recuperação em horas; CFR é uma fração entre
0 e 1. A release anterior ao início da janela pode servir como base do
compare. Primeira release sem anterior e commits com tempos negativos
seguem as regras e contadores da RQ76. Compare ausente, truncado ou com
commits incompletos fica fora do lead time e gera pendência explícita.
Os valores restantes são parciais, identificados por `calculo_completo=False`.

Cada distribuição de lead time e recuperação traz mediana, Q1, Q3 e IQR.
Os quartis usam interpolação linear (tipo 7). Distribuições vazias resultam
em valores ausentes; uma única observação tem IQR zero. O resumo entre
repositórios inclui `n` e usa os valores disponíveis, devendo ser lido junto
das pendências, principalmente quando houver cálculos parciais.

### Heurística de release corretiva

Versão `patch_semver_v1`: a release é corretiva quando, em relação à release
publicada imediatamente anterior, mantém major/minor e aumenta o patch.
Aceita `v` opcional e metadados de build; rejeita downgrade, versão igual,
pré-release e tags sem três componentes SemVer válidos. Não usa mensagens
de commit nesta versão (o enunciado permite patch **e/ou** mensagens).

Uma release original falha se houver pelo menos uma dessas corretivas
posteriores em até sete dias, inclusive; várias corretivas não multiplicam
a contagem da original. Cada ocorrência fica auditável no CSV de releases.
Releases com menos de sete dias de observação até o fim da janela são
censuradas e excluídas do denominador, mesmo que já exista uma corretiva.
Se nenhuma release for avaliável, CFR fica ausente.

Essa heurística é um proxy, não uma constatação de falha em produção.
Tags não SemVer não produzem evidência de patch e são contabilizadas em
`releases_sem_semver`; projetos com outros esquemas podem ter falhas
subestimadas. A validação manual da heurística permanece pendente e não é
substituída pelos testes automatizados. Não foram preenchidos rótulos humanos.

### Recuperação e censura

Reutiliza a RQ79 para agrupar episódios por workflow, preservando censura
à direita e à esquerda. Um sucesso cujo `updated_at` ultrapassa o fim da
janela não fecha o episódio dentro dela. Episódios censurados são exportados
com seus marcadores e não entram na mediana. A proporção de censura à
direita e a quantidade de censuras à esquerda são informadas separadamente.

## Saídas e auditoria

- `metricas_variantes.csv`: uma linha por repositório, métricas, contagens,
  quartis, censura e pendências;
- `cfr_entrega_releases.csv`: avaliação e primeira corretiva identificada
  para cada release da janela;
- `episodios_recuperacao.csv`: evidência dos episódios por workflow;
- `resumo_rq83.json`: janela, hashes SHA-256 das entradas, regra usada,
  resumo das métricas e pendências.

Os dados de entrada permanecem preservados. O script verifica duplicatas,
colunas obrigatórias, divergências de contagens e alteração dos arquivos
durante a leitura. Não utiliza o número de estrelas para reordenar a seleção
nem exclui repositórios por causa de métricas ausentes.

Retornos: 0 = cálculo completo; 2 = cálculo com pendências; 1 = erro de entrada
ou execução. `calculo_completo` não confirma a janela com o professor, não
valida a heurística manualmente e não comprova a amostra final de 300.
Essas condições continuam separadas no resumo e na auditoria da #82.

## Verificação em 14/10/2026

105 testes passaram, cobrindo a #83 e as métricas existentes de CI, lead time
e DORA. Fixtures sintéticas ficam somente nos testes.

```powershell
.\.venv\Scripts\python.exe -m pytest codigo-fonte/testes/test_rq83.py codigo-fonte/testes/test_metricas_ci.py codigo-fonte/testes/test_metricas_lead_time.py codigo-fonte/testes/test_metricas_dora.py -q
```

A execução real do piloto gerou resultados em `dados/rq83_piloto/` para
100 repositórios: frequência e ambos os CFRs calculados para os 100,
recuperação com mediana disponível para 93, e lead time ausente para todos
por falta dos arquivos `lead_time_releases.csv` e `commits_releases.csv.gz`.
Esse resultado é **parcial**, não a entrega definitiva da amostra de 300.
A janela herdada (01/10/2025 a 30/09/2026) continua provisória.
