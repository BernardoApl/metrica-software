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
