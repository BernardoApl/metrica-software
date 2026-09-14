# RQ30 - Preparar Ambiente e Script de Métricas Estáticas

Issue: #30. Etapa correspondente: Passo 2 (Preparação do Experimento) do LAB02.

## Objetivo

Preparar o ambiente e o script de coleta das métricas estruturais (RQ3) sobre o `solucao.py` final de cada trial: complexidade ciclomática, LOC e duplicação de código.

## Ferramentas escolhidas

Conforme justificado em [RQ33 — Hipóteses, Variáveis e Ameaças à Validade](RQ33_hipoteses.md), a linguagem do experimento é Python, então:

- **Radon** (`cc`, `raw`, `mi`) para complexidade ciclomática, LOC e Índice de Manutenibilidade — CK não se aplica, pois exige Java.
- **jscpd** para percentual de linhas duplicadas — Radon não cobre duplicação.

## Artefatos implementados

- `codigo-fonte/sprint-02/rq30_metricas_estaticas.py`: mede complexidade (Radon `cc`), LOC/SLOC/LLOC (Radon `raw`), Índice de Manutenibilidade (Radon `mi`) e duplicação (`jscpd`) de um arquivo, e acrescenta o resultado a um CSV.
- `codigo-fonte/sprint-02/test_rq30.py`: testes offline das métricas e da gravação do CSV, com o `jscpd` mockado.
- `requirements.txt`: fixa a dependência Python (`radon`).
- `codigo-fonte/sprint-02/README.md`: instruções de preparação do ambiente e de uso do script.

## Preparação do ambiente

- Radon é dependência Python do projeto: `pip install -r requirements.txt`.
- jscpd é uma ferramenta Node.js chamada sob demanda via `npx --yes jscpd`, sem exigir instalação global; requer apenas Node.js/npm no PATH.
- Quando `npx`/`jscpd` não está disponível (ou com a flag `--sem-duplicacao`), o script continua calculando complexidade, LOC e MI normalmente e marca a duplicação como indisponível (`duplicacao_disponivel=False`) em vez de falhar a coleta.

## Metricas coletadas por medicao

| Métrica | Origem | Coluna no CSV |
|---|---|---|
| Complexidade ciclomática média/máxima | Radon `cc_visit` | `complexidade_media`, `complexidade_maxima` |
| LOC / SLOC / LLOC | Radon `raw.analyze` | `loc`, `sloc`, `lloc` |
| Índice de Manutenibilidade (opcional/aprofundamento) | Radon `mi_visit` | `indice_manutenibilidade` |
| Percentual de linhas duplicadas | `jscpd` | `duplicacao_percentual` (com `duplicacao_disponivel` indicando se a medição foi possível) |

## Como executar

Na raiz do projeto, ao final de um trial (depois de rodar a RQ28):

```powershell
python codigo-fonte/sprint-02/rq30_metricas_estaticas.py --participante integrante1 --kata kata01 --tratamento com_ia --issue 30 --arquivo caminho/do/kata/solucao.py
```

## Critério de aceite

A RQ30 é considerada atendida quando:

- os testes automatizados da RQ30 passam;
- o script produz complexidade, LOC e MI para um `solucao.py` válido;
- a ausência de `jscpd`/Node.js não impede a coleta das demais métricas;
- o CSV gerado é compatível com o schema validado pela [RQ31](RQ31_validacao_metricas_estaticas.md).
