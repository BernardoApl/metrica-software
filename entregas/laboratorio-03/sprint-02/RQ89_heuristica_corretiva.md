# RQ89 — Heurística de releases corretivas: implementação, refinamento e P/R/F1

Issue: #89. Seção 6 do enunciado, passo 5, e RQ 03 (b). Depende do consenso da amostra-ouro (RQ88), que depende dos rótulos humanos das issues #85, #86 e #87.

## O que está pronto

| Peça | Arquivo |
|---|---|
| Versões da heurística (funções puras, sem rede) | [`codigo-fonte/metricas/corretiva.py`](../../../codigo-fonte/metricas/corretiva.py) |
| Plug no CFR de entrega (`--heuristica`) | [`metricas/variantes.py`](../../../codigo-fonte/metricas/variantes.py), [`rq83_metricas_variantes.py`](../../../codigo-fonte/rq83_metricas_variantes.py) |
| Avaliação P/R/F1 contra o consenso | [`codigo-fonte/validacao/rq89_heuristica.py`](../../../codigo-fonte/validacao/rq89_heuristica.py) |
| Testes (valores calculados à mão) | [`testes/test_rq89_heuristica.py`](../../../codigo-fonte/testes/test_rq89_heuristica.py) |

## O que **não** está pronto: o F1 real

O F1 só existe depois que (1) a amostra final de 300 (RQ82) for coletada, (2) o sorteio da RQ86 for feito, (3) os três avaliadores rotularem sozinhos (#85, #86, #87) e (4) o consenso sair (RQ88). Nenhum número de precisão, recall ou F1 foi inventado: **as versões abaixo ainda não têm F1 medido** e a versão padrão do CFR (b) continua `patch_semver_v1`. Os testes usam apenas fixtures sintéticas.

## Sinais e versões

Uma release R é avaliada em relação à release publicada imediatamente anterior (a mesma "anterior" do lead time e do sorteio da RQ86). Os sinais são a tag e a primeira linha dos commits do `compare` (coluna `mensagem` de `commits_releases.csv.gz`).

Evidências extraídas por `corretiva.evidencias`:

| Evidência | Significado |
|---|---|
| `patch` | mesmo major/minor, patch maior (SemVer estrito; sem pré-release, sem downgrade) |
| `uteis` | commits sem os de merge |
| `revert_hotfix` | commits com `revert`/`hotfix` |
| `fix` | commits com `fix`/`fixes`/`fixed`/`bugfix` (inclui os de `revert_hotfix`) |
| `fix_defeito` | `fix` que **não** fala de typo, docs, README, lint, formatação, CI, testes ou dependências |
| `feat` | commits de funcionalidade (`feat:`, `add`, `implement`, `support`…) que não são correção |

| Versão | Regra | Expectativa antes dos dados |
|---|---|---|
| `patch_semver_v1` | só o patch mudou | precisão razoável em projetos SemVer; recall baixo em projetos que corrigem em minor ou não usam SemVer |
| `patch_ou_mensagem_v2` | patch **ou** algum commit com `revert`/`hotfix`/`fix` (leitura literal do enunciado) | recall alto, precisão baixa: releases de funcionalidade quase sempre carregam algum `fix` |
| `correcao_de_defeito_v3` | `revert`/`hotfix` basta; senão exige `fix_defeito` e (patch **ou** ≥ metade dos commits úteis são `fix_defeito` sem nenhum commit de funcionalidade); sem mensagens, vale só a tag | tenta recuperar a precisão da v2 sem perder o recall; é uma hipótese, não um resultado |

Cada versão nova entra em `corretiva.HEURISTICAS` e é avaliada junto com as anteriores. **Limitações conhecidas:** não lê as *release notes* (o corpo da release não é coletado) nem o diff; commits com mensagem em outro idioma ou sem convenção escapam; `fix` em *squash merges* depende do título do PR.

## Como avaliar e refinar

Com o consenso da RQ88 num CSV (`id_release`, `corretiva` = sim/não), por padrão em `dados/lab03_final/amostra_ouro/consenso_releases.csv`:

```powershell
python codigo-fonte/validacao/rq89_heuristica.py avaliar --consenso dados/lab03_final/amostra_ouro/consenso_releases.csv
```

Também aceita a planilha `.xlsx` de um avaliador, para uma checagem **preliminar** com os próprios rótulos (nunca como resultado final: o enunciado exige o consenso).

Saídas em `dados/lab03_final/amostra_ouro/`:

- `avaliacao_heuristica.csv` e `.json`: uma linha por versão, com VP/FP/FN/VN, precisão, recall e F1 (classe positiva = corretiva, `sklearn.metrics.precision_recall_fscore_support`) e quantas releases ficaram sem mensagens;
- `erros_heuristica.csv`: cada falso positivo e falso negativo de cada versão, com as evidências e os links da release e do `compare`, para ler os erros e propor a próxima versão.

Código de saída: 0 se a melhor versão tem F1 ≥ 0,70; 2 se nenhuma tem (refinar e reavaliar, como manda o enunciado); 1 em erro de entrada.

Ciclo de refinamento: rodar → ler `erros_heuristica.csv` → escrever `correcao_de_defeito_v4` (etc.) em `corretiva.py` com teste → rodar de novo → registrar **todas** as versões e seus F1 no artigo. Quando uma versão atingir 0,70, trocar `HEURISTICA_PADRAO` e recalcular o CFR (b):

```powershell
python codigo-fonte/rq83_metricas_variantes.py --heuristica correcao_de_defeito_v3
```

O resumo `resumo_rq83.json` registra o nome da heurística usada. Cuidado ao refinar: ajustar regras olhando os próprios erros da amostra de 60 superestima o F1 (sobreajuste). O artigo deve dizer que o F1 final é otimista por esse motivo.

## Testes

```powershell
python -m pytest codigo-fonte/testes/test_rq89_heuristica.py -q
```

41 testes, sem rede: evidências (`fix` vs. `prefix`/`fixture`, merges ignorados, fixes triviais), cada versão em casos de borda (sem mensagens, tag não SemVer, exatamente metade dos commits), o CFR com mensagens, a propagação da escolha pelo `rq83`, e a avaliação com uma tabela VP/FP/FN/VN calculada à mão (v1: P=R=F1=0,5; v2: P=4/7, R=1, F1=8/11; v3: 1). Cobertura do módulo `metricas` mantida acima de 80 % (`corretiva.py` com 100 %). A suíte completa passou (369 testes).
