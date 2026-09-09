# RQ32 — Seleção e Validação de Katas com Testes Automatizados

Issue: #32. Etapa correspondente: Passo 2 (Preparação do Experimento) do LAB02.

## Katas selecionados

Foram criados **6 katas autorais** (número par, permitindo divisão exata pela metade entre trials com e sem assistente de IA), em Python:

1. Frete progressivo por peso/distância;
2. Validação de senha corporativa;
3. Deduplicação de contatos;
4. Detecção de conflitos de turnos;
5. Conversão de unidades de estoque (busca em grafo);
6. Validação de cupom fiscal (checksum fictício).

Arquivos: `codigo-fonte/sprint-02/katas/` (um subdiretório por kata, com `enunciado.md`, `solucao.py` e `testes/test_solucao.py`). Detalhes de execução em `codigo-fonte/sprint-02/katas/README.md`.

## Por que autorais, e não exercícios de plataformas conhecidas

O enunciado do laboratório aponta como ameaça à validade o risco de **memorização**: se os katas forem exercícios muito conhecidos (clássicos de LeetCode/HackerRank), o assistente de IA pode reproduzir uma solução já vista em seu treinamento, em vez de efetivamente ajudar a resolver o problema — o que inflaria artificialmente o ganho do tratamento "com IA". Por isso, optamos por escrever problemas próprios, com contexto de negócio fictício (frete, RH, estoque, cupons fiscais), evitando formulações padrão de algoritmos clássicos (ex.: não é "validar CPF real", é um checksum inventado para este experimento).

## Critério de dificuldade equivalente

Todos os 6 katas seguem o mesmo padrão estrutural, para que a comparação de tempo entre trials não seja distorcida por katas de dificuldades muito diferentes:

- uma única função pura por kata (sem I/O, sem estado externo, sem dependências externas);
- entrada com tipos simples (`str`, `float`, `list`, `dict`) e saída determinística;
- entre 6 e 7 casos de teste por kata, cobrindo caminho feliz, casos de borda e ao menos uma validação de erro;
- tempo estimado de resolução por um solucionador experiente: **~20–25 minutos**, compatível com o time-box de 35 minutos por trial definido no laboratório.

## Validação dos testes automatizados

Para cada um dos 6 katas foi escrita e executada uma implementação de referência contra a suíte de testes de aceitação (`testes/test_solucao.py`), confirmando que:

- os testes passam com uma solução correta (nenhum falso negativo);
- os testes cobrem os casos de borda descritos no enunciado (valores limítrofes de faixas, entradas inválidas, empates);
- os testes são executáveis isoladamente via `python -m unittest discover -s testes`, no formato exigido pelo script de cronometragem da RQ28 (`--diretorio <pasta-do-kata> --testes python -m unittest discover -s testes`).

## Compatibilidade com a execução do experimento (RQ28)

A pasta `testes/` de cada kata é o alvo esperado pelo parâmetro `-s testes` do comando de aceitação usado pelo script `rq28_cronometragem.py`, e o `solucao.py` de cada kata é o arquivo que o participante deve editar durante o trial (o stub levanta `NotImplementedError`, garantindo que os testes falhem até que o kata seja de fato resolvido).
