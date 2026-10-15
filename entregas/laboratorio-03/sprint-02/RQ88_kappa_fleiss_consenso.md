# RQ88 — Kappa de Fleiss e Consenso da Validação Manual

Issue: #88. Seção 6 do enunciado, passos 3 (concordância entre os três avaliadores) e 4 (consenso e protocolo de desempate). Usa as planilhas preenchidas nas issues #85, #86 e #87 (ver [RQ86](RQ86_amostra_ouro.md)).

## Execução

Depois que os três avaliadores commitarem as planilhas preenchidas:

```bash
python codigo-fonte/validacao/rq88_concordancia.py
```

| Código de saída | Significado |
|---|---|
| 0 | kappa calculado e consenso completo |
| 2 | kappa calculado, mas há empates 1-1-1 sem decisão da reunião (ver protocolo) |
| 1 | alguma planilha ausente ou incompleta, ou `decisoes_reuniao.csv` inválido |

As planilhas passam pelo mesmo `validar` da RQ86 antes do cálculo: com uma célula vazia ou um valor fora da lista, nada é calculado.

## Concordância: kappa de Fleiss

Para cada uma das três dimensões (`tipo_projeto`, `entregas_reais`, `corretiva`):

- **kappa de Fleiss** com `aggregate_raters` + `fleiss_kappa(method="fleiss")` do statsmodels, como indica o enunciado. Todas as categorias possíveis entram na tabela, inclusive as que ninguém usou;
- **% de itens unânimes**, e quantos itens ficaram 2-1 e 1-1-1;
- **interpretação de Landis & Koch** (1977): < 0 pobre; até 0,20 leve; até 0,40 razoável; até 0,60 moderada; até 0,80 substancial; acima disso, quase perfeita;
- **distribuição** dos rótulos por categoria.

O kappa é calculado sobre os rótulos **independentes**. As decisões da reunião de consenso não o alteram, e há um teste que garante isso.

**Kappa indefinido.** Se todos os itens de uma dimensão caírem na mesma categoria (ex.: os três marcam "sim" em todos os `entregas_reais`), a concordância esperada é 1 e o kappa vira 0/0. O script registra `kappa_fleiss` vazio em vez de inventar um número. No artigo, isso deve ser relatado como "concordância total, kappa indefinido".

**Conferência do cálculo:** o teste reproduz o exemplo clássico de Fleiss (10 itens, 14 avaliadores, 5 categorias → κ = 0,210) e compara o resultado com uma implementação manual da fórmula em 50 matrizes aleatórias.

## Protocolo de desempate (registrado conforme o enunciado)

| Situação entre os 3 avaliadores | Rótulo de consenso | `origem` |
|---|---|---|
| 3-0 | o rótulo unânime | `unanime` |
| 2-1 | maioria simples | `maioria` |
| 1-1-1 (só possível em `tipo_projeto` e `entregas_reais`) | decidido em **reunião dos três** | `reuniao` |

1. Rodar o script uma primeira vez. Ele gera `pendencias_reuniao.csv`, a **pauta da reunião**:
   - `obrigatoria = True`: empates 1-1-1, que precisam de decisão;
   - `obrigatoria = False`: divergências 2-1, que já têm consenso pela maioria, mas podem ser revistas se o grupo concluir que a maioria errou.
2. Na reunião, os três discutem cada item da pauta, relendo o README, as release notes e os commits.
3. Registrar cada decisão em `dados/lab03_final/amostra_ouro/decisoes_reuniao.csv`:

   ```csv
   dimensao,id_item,rotulo,justificativa
   tipo_projeto,R07,ferramenta CLI,"README e releases distribuem só o binário de linha de comando"
   entregas_reais,R31,não,"releases automáticas diárias sem changelog"
   ```

   `rotulo` aceita o texto da lista ou o código. A `justificativa` é obrigatória. O script recusa item inexistente, rótulo inválido e item repetido.
4. Rodar o script de novo: com todos os empates decididos, ele termina com código 0.

Decisões de reunião sobre itens 2-1 ficam com `origem = reuniao` e a justificativa no CSV, para que a seção de Metodologia possa relatar quantas maiorias foram revistas.

## Saídas (em `dados/lab03_final/amostra_ouro/`)

| Arquivo | Conteúdo |
|---|---|
| `concordancia_fleiss.csv` | uma linha por dimensão: itens, avaliadores, `kappa_fleiss`, `interpretacao`, `concordancia_total`, `itens_unanimes`, `itens_2_1`, `itens_1_1_1`, `distribuicao` (JSON) |
| `concordancia_fleiss.json` | o mesmo, mais o protocolo, `empates_sem_decisao`, `consenso_completo` e a contagem de `origem` por dimensão |
| `consenso_repositorios.csv` | 60 repositórios: rótulo de cada avaliador (`tipo_projeto_<login>`, `entregas_reais_<login>`), `*_consenso`, `*_origem` e `*_justificativa`. O `tipo_projeto_consenso` é o fator **tipo do projeto** da RQ 06 |
| `consenso_releases.csv` | releases sorteadas: rótulo de cada avaliador, `corretiva_consenso`, `corretiva_origem` e `corretiva_justificativa`. É a referência para precisão, recall e F1 da heurística (RQ89) |
| `pendencias_reuniao.csv` | pauta da reunião (empates obrigatórios e divergências 2-1) |
| `decisoes_reuniao.csv` | escrito pelo grupo: decisões da reunião |

Os rótulos vêm como códigos: `biblioteca_framework`, `aplicacao_servico`, `ferramenta_cli`, `outro`, `sim`, `nao`, `incerto`.

## Código e testes

- [`codigo-fonte/validacao/rq88_concordancia.py`](../../../codigo-fonte/validacao/rq88_concordancia.py)
- [`codigo-fonte/testes/test_rq88_concordancia.py`](../../../codigo-fonte/testes/test_rq88_concordancia.py) (32 testes, cobertura de 99%):
  - kappa: exemplo de Fleiss, fórmula manual, concordância perfeita (κ = 1), kappa indefinido, categoria não usada;
  - faixas de Landis & Koch, inclusive os limites (0,20; 0,21; …);
  - consenso: 3-0, 2-1, 1-1-1; decisão de reunião resolvendo empate e revendo maioria; decisões inválidas recusadas;
  - fluxo completo com três planilhas preenchidas: pauta, decisões, CSVs de consenso e códigos de saída;
  - o kappa não muda depois das decisões da reunião; planilha incompleta ou ausente impede o cálculo.

Nova dependência: `statsmodels`, adicionada ao `requirements.txt`.

## Para o artigo (Metodologia e Ameaças à validade)

- Reportar o κ das três dimensões com a interpretação, o nº de itens 2-1 e 1-1-1, e quantos consensos vieram de reunião.
- Um κ baixo em `corretiva` ou `entregas_reais` indica que o **próprio critério** é ambíguo. Segundo o enunciado, isso é um achado a discutir, e não um erro a esconder.

## Situação

Os resultados reais dependem das três planilhas preenchidas, que por sua vez dependem do sorteio sobre a amostra final (RQ82 → RQ86). Todo o fluxo foi exercitado com planilhas sintéticas nos testes.
