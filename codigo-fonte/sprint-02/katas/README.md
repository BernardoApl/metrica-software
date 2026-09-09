# Katas do LAB02

Seis katas autorais em Python, de dificuldade equivalente (~20–25 minutos cada para um solucionador experiente), usados no experimento com/sem assistente de IA. Nenhum deles é um exercício clássico indexado (LeetCode/HackerRank/Codewars) — foram escritos especificamente para este experimento, para reduzir o risco de o assistente de IA "reconhecer" e reproduzir uma solução já vista em treinamento em vez de efetivamente ajudar.

| Kata | Tema | Pasta |
|---|---|---|
| 01 | Frete progressivo por peso/distância | `kata01_frete_progressivo/` |
| 02 | Validação de senha corporativa | `kata02_senha_corporativa/` |
| 03 | Deduplicação de contatos | `kata03_deduplicador_contatos/` |
| 04 | Detecção de conflitos de turnos | `kata04_escalonador_turnos/` |
| 05 | Conversão de unidades de estoque (grafo) | `kata05_conversor_estoque/` |
| 06 | Validação de cupom fiscal (checksum fictício) | `kata06_cupom_fiscal/` |

## Estrutura de cada kata

```
kataNN_nome/
├── enunciado.md      # especificação do problema
├── solucao.py         # stub a ser preenchido durante o trial (levanta NotImplementedError)
└── testes/
    └── test_solucao.py  # testes de aceitação (unittest)
```

## Como rodar os testes de aceitação de um kata

Na raiz do projeto:

```powershell
python -m unittest discover -s codigo-fonte/sprint-02/katas/kata01_frete_progressivo/testes
```

Ou, seguindo o formato usado pelo script de cronometragem da RQ28 (`--diretorio` apontando para a pasta do kata e `--testes` executando a partir dali):

```powershell
python codigo-fonte/sprint-02/rq28_cronometragem.py --participante integrante1 --kata kata01 --tratamento com_ia --issue 32 --diretorio codigo-fonte/sprint-02/katas/kata01_frete_progressivo --testes python -m unittest discover -s testes
```

## Validação de dificuldade comparável

Todos os katas seguem o mesmo padrão: uma única função pura (sem I/O, sem estado externo), recebendo tipos simples (`str`, `float`, `list`, `dict`) e cobrindo de 6 a 7 casos de teste (caminho feliz, casos de borda e pelo menos uma condição de erro/validação). Cada implementação de referência foi escrita e executada contra os testes durante a preparação (ver commits desta pasta) para garantir que os testes são consistentes e resolvíveis dentro do time-box de 35 minutos.
