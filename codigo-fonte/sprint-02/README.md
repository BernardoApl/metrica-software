# RQ28 — Cronometragem e coleta de tempo

Registra o tempo de resolução dos katas do LAB02, com e sem IA. Usa Python sem dependências externas.

## Como executar

Na raiz do projeto:

```powershell
python codigo-fonte/sprint-02/rq28_cronometragem.py --participante integrante1 --kata kata01 --tratamento com_ia --issue 28 --diretorio caminho/do/kata --testes python -m unittest discover -s testes
```

Substitua os dados pelos da tentativa e informe sua Issue individual. Use `sem_ia` para o tratamento manual. A opção `--testes` deve ficar por último; o comando deve executar todos os testes de aceitação e retornar zero somente se todos passarem.

## Uso do cronômetro

- **Enter:** inicia a tentativa, sem pausa.
- **testar:** executa os testes; código zero antes do limite encerra com sucesso.
- **tempo:** mostra o tempo restante.
- **sair ou Ctrl+C:** registra uma interrupção.

O limite é **35 minutos**, podendo ser reduzido com `--limite-minutos 20`. Ao esgotar o tempo, a tentativa é registrada como censurada no limite. Pare de editar ao encerramento.

## Dados salvos

Cada tentativa é acrescentada a `dados/lab02_rq28_tempos.csv`, com participante, kata, tratamento, Issue, horários, duração e resultado: sucesso, limite atingido, interrupção ou erro de execução.

Use `--saida caminho.csv` para mudar o arquivo. Em execuções simultâneas, use um CSV por participante. O registro ocorre ao encerrar; prefira `sair` ou Ctrl+C a fechar o terminal à força.

## RQ29 - Validacao dos trials e piloto

Valide o CSV real da RQ28 antes da analise:

```powershell
python codigo-fonte/sprint-02/rq29_validar_trials.py --csv dados/lab02_rq28_tempos.csv
```

Execute o piloto sintetico da coleta, sem misturar com os trials reais:

```powershell
python codigo-fonte/sprint-02/rq29_validar_trials.py --piloto --saida-piloto dados/lab02_rq29_piloto.csv
```

## RQ30 — Ambiente e script de métricas estáticas (RQ3)

Mede, para o `solucao.py` final de um trial: complexidade ciclomática média e máxima (Radon `cc`), LOC/SLOC/LLOC (Radon `raw`), Índice de Manutenibilidade (Radon `mi`) e percentual de linhas duplicadas (`jscpd`), conforme decidido em [RQ33 — Hipóteses, Variáveis e Ameaças à Validade](../../entregas/laboratorio-02/sprint-01/RQ33_hipoteses.md).

### Preparar o ambiente

- **Radon** (Python): `pip install -r requirements.txt`.
- **jscpd** (Node.js, usado só para duplicação): não precisa instalar globalmente — o script chama `npx --yes jscpd` sob demanda. Requer Node.js/npm no PATH. Se `npx` não estiver disponível, use `--sem-duplicacao`: as demais métricas continuam sendo calculadas normalmente.

### Como executar

Na raiz do projeto, ao final de um trial (depois de rodar a RQ28):

```powershell
python codigo-fonte/sprint-02/rq30_metricas_estaticas.py --participante integrante1 --kata kata01 --tratamento com_ia --issue 30 --arquivo caminho/do/kata/solucao.py
```

Use `--trial-id` com o `trial_id` gerado pela RQ28 para cruzar tempo, defeitos e métricas estáticas do mesmo trial. Use `--sem-duplicacao` para pular o `jscpd` (ex.: ambiente sem Node.js). Os limiares do `jscpd` podem ser ajustados com `--min-linhas` e `--min-tokens` (padrão: 3 e 20, mais sensíveis do que o padrão do `jscpd` porque os katas são arquivos curtos de uma única função).

### Dados salvos

Cada medição é acrescentada a `dados/lab02_rq30_metricas_estaticas.csv`. Quando a duplicação não pode ser medida, `duplicacao_disponivel` fica `False` e os campos de duplicação ficam vazios, em vez de interromper a coleta das demais métricas.

## RQ31 - Validação das métricas estáticas e piloto sobre os katas

Valide o CSV real da RQ30 antes da análise:

```powershell
python codigo-fonte/sprint-02/rq31_validar_metricas.py --csv dados/lab02_rq30_metricas_estaticas.csv
```

Execute o piloto sobre o `solucao.py` atual dos 6 katas reais (sem depender de um trial resolvido), para validar o script de ponta a ponta:

```powershell
python codigo-fonte/sprint-02/rq31_validar_metricas.py --piloto --saida-piloto dados/lab02_rq31_piloto.csv
```

Adicione `--sem-duplicacao` ao piloto em um ambiente sem Node.js/`jscpd`.

## RQ43 (Inovação) — Validar integridade e rastreabilidade dos dados reais dos trials

Cruza os dados reais da RQ28 (`dados/lab02_rq28_tempos.csv`) com as evidências complementares do
experimento: diretório do kata, `solucao.py`, registro de prompt/interação para trials `com_ia` e medição
estática da RQ30 quando o trial foi concluído com sucesso.

Antes de rodar a RQ43, colete a RQ30 para cada trial real bem-sucedido:

```powershell
python codigo-fonte/sprint-02/rq30_metricas_estaticas.py --participante <nome> --kata <kata> --tratamento <com_ia|sem_ia> --issue <issue> --trial-id <trial_id> --arquivo <pasta-do-kata>/solucao.py --sem-duplicacao
```

Depois execute:

```powershell
python codigo-fonte/sprint-02/rq43_validar_rastreabilidade_trials.py
```

A validação gera:

- `dados/lab02_rq43_integridade_trials.csv`: uma linha por trial, com flags de rastreabilidade.
- `dados/lab02_rq43_integridade_trials.json`: relatório completo com resumo, erros e alertas.

O status só fica OK quando o CSV da RQ28 é válido, o CSV da RQ30 existe e é válido, cada `trial_id`
de métricas aponta para um trial real, e cada trial bem-sucedido tem diretório, `solucao.py`, prompt
quando `com_ia` e medição RQ30 correspondente.

## RQ44 (Inovação) — Coletar e comparar complexidade, LOC e duplicação das soluções

Consolida o CSV da RQ30 (`dados/lab02_rq30_metricas_estaticas.csv`) em uma comparação por kata e por
tratamento (`com_ia` vs `sem_ia`), usando mediana e IQR — não média/desvio-padrão — para as três métricas
do RQ3 (complexidade ciclomática média, LOC, % de duplicação), consistente com a robustez estatística
recomendada para o N pequeno do LAB02.

### Como executar

Depois de rodar a RQ30 para os trials que você quer comparar (ex.: RQ40 — kata01 com IA, RQ41 — kata02 com IA):

```powershell
python codigo-fonte/sprint-02/rq30_metricas_estaticas.py --participante <nome> --kata kata01_frete_progressivo --tratamento com_ia --issue 40 --arquivo codigo-fonte/sprint-02/katas/kata01_frete_progressivo/solucao.py
python codigo-fonte/sprint-02/rq30_metricas_estaticas.py --participante <nome> --kata kata02_senha_corporativa --tratamento com_ia --issue 41 --arquivo codigo-fonte/sprint-02/katas/kata02_senha_corporativa/solucao.py
python codigo-fonte/sprint-02/rq44_comparar_metricas.py
```

Use `--sem-grafico` para pular a geração do PNG (dispensa `matplotlib`). A comparação é salva em
`dados/lab02_rq44_comparacao_metricas.csv` e o gráfico em `dados/rq44_comparacao_metricas.png`.

## RQ54 (RQ3) — Consolidar complexidade, LOC e duplicação por tratamento

Complementa a RQ44: em vez de agrupar por kata e tratamento, consolida **todos os katas** de cada
tratamento (`com_ia` vs `sem_ia`) em uma única linha, com mediana e IQR de complexidade ciclomática
média, LOC e percentual de duplicação — uma visão geral da RQ3 (o uso de assistente de IA altera a
complexidade ou a duplicação do código produzido?).

### Como executar

Depois de rodar a RQ30 para os trials que você quer consolidar:

```powershell
python codigo-fonte/sprint-02/rq54_consolidar_metricas_tratamento.py
```

Use `--entrada caminho.csv` para outro CSV de entrada, `--saida-csv`/`--saida-grafico` para mudar os
destinos, e `--sem-grafico` para pular o PNG (dispensa `matplotlib`).

### Dados salvos

A consolidação é salva em `dados/lab02_rq54_consolidacao_tratamento.csv` e o gráfico em
`dados/rq54_consolidacao_tratamento.png`.
