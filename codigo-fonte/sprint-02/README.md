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
