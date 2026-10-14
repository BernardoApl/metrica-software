# RQ86 — Rotular Amostra-Ouro de 60 Repositórios

Issue: #86 (avaliador `bacelete`). As issues #85 (`BernardoApl`) e #87 (`Joaopedrotavaress`) são a mesma tarefa para os outros dois avaliadores. Seção 6 do enunciado, passos 1 e 2.

A rotulagem é **manual e independente**: o kappa de Fleiss (RQ88) e o F1 da heurística (RQ89) só têm valor se cada integrante julgar sozinho, sem consultar os outros e sem ver a saída da heurística. O código desta issue sorteia a amostra, gera as planilhas e confere o preenchimento. **Ele não rotula nada.**

## Ferramenta

[`codigo-fonte/validacao/rq86_amostra_ouro.py`](../../../codigo-fonte/validacao/rq86_amostra_ouro.py), com dois comandos.

### 1. `gerar`: rodar uma única vez, para o grupo inteiro

```bash
python codigo-fonte/validacao/rq86_amostra_ouro.py gerar
```

- **Entrada:** `dados/lab03_final/metricas_repositorios.csv` e `releases.csv`, a amostra final da RQ82. Sem eles o comando para e indica como gerá-los.
- **60 repositórios:** `df.sample(n=60, random_state=42)`, como no enunciado, sobre a amostra **ordenada por nome**. Assim a ordem das linhas do CSV não muda o sorteio.
- **5 releases por repositório**, com a mesma semente, entre as releases da definição principal de deploy (publicada, não draft, não pré-release, dentro da janela) **que têm release anterior**. A primeira release da história fica de fora, porque sem anterior não há lista de commits para ler. Se um repositório tiver menos de 5 elegíveis, entram todas e o comando avisa.
- **Saída** em `dados/lab03_final/amostra_ouro/`:

| Arquivo | Conteúdo |
|---|---|
| `sorteio_repositorios.csv` | os 60 sorteados (`R01`…`R60`), com linguagem, estrelas e links |
| `sorteio_releases.csv` | as releases sorteadas (`R01-1`…), com a release anterior e os links |
| `rotulos/rotulos_BernardoApl.xlsx` | planilha do avaliador da #85 |
| `rotulos/rotulos_bacelete.xlsx` | planilha do avaliador da #86 |
| `rotulos/rotulos_Joaopedrotavaress.xlsx` | planilha do avaliador da #87 |

O sorteio é reproduzível: com a mesma entrada e a mesma semente, os CSVs saem idênticos, e os testes verificam isso. Para não apagar rótulos por acidente, `gerar` **se recusa a regravar planilhas existentes**. A opção `--sobrescrever` existe, mas apaga o que já foi rotulado.

### 2. `validar`: cada avaliador, antes de commitar a sua planilha

```bash
python codigo-fonte/validacao/rq86_amostra_ouro.py validar dados/lab03_final/amostra_ouro/rotulos/rotulos_bacelete.xlsx
```

Lista as células vazias, os valores fora das listas e as linhas alteradas, removidas ou reordenadas em relação ao sorteio. Termina com código 0 só quando a planilha está completa.

## A planilha

Três abas:

- **`instrucoes`:** regras do protocolo e a definição de cada categoria, iguais para os três avaliadores.
- **`repositorios`** (60 linhas): link do repositório e das releases. Colunas a preencher (em amarelo, com lista suspensa):
  - `tipo_projeto`: biblioteca/framework · aplicação/serviço · ferramenta CLI · outro;
  - `entregas_reais` (as releases representam entregas reais ao usuário?): sim · não · incerto.
- **`releases`** (até 300 linhas): tag, release anterior, data, link da release (*release notes*) e link do `compare` com a anterior (lista de commits). Coluna a preencher: `corretiva` (o objetivo principal é corrigir um defeito recente?): sim · não.
- Todas as abas têm uma coluna `observacoes` livre, para justificar casos difíceis. Ela ajuda na reunião de consenso.

**Cegueira em relação à heurística:** a planilha não mostra classificação SemVer, nem mensagens de commit, nem qualquer saída da RQ89. O que o avaliador vê é o que a página do GitHub mostra.

Na leitura, as respostas são normalizadas (maiúsculas e acentos não importam: "Não", "nao" e "NÃO" valem o mesmo) e convertidas em códigos (`biblioteca_framework`, `aplicacao_servico`, `ferramenta_cli`, `outro`, `sim`, `nao`, `incerto`). A RQ88 usa a mesma função `ler_planilha`.

## Protocolo

1. Uma pessoa roda `gerar` sobre a amostra final e commita o sorteio e as três planilhas vazias, todos no mesmo commit.
2. Cada avaliador preenche **apenas a sua** planilha, sozinho, sem ver as dos outros nem a heurística.
3. Cada avaliador roda `validar` e commita a planilha preenchida referenciando a **própria** issue (#85, #86 ou #87).
4. Só depois que as três estiverem commitadas: concordância (Fleiss) e consenso na RQ88.

## Testes

[`codigo-fonte/testes/test_rq86_amostra_ouro.py`](../../../codigo-fonte/testes/test_rq86_amostra_ouro.py) (35 testes, sem rede):

- o sorteio é exatamente `df.sample(n=60, random_state=42)` sobre a amostra ordenada; não depende da ordem do CSV; outra semente gera outro sorteio; amostra pequena ou com duplicados é recusada;
- releases: draft, pré-release, fora da janela e primeira da história não são sorteadas; release anterior fora da janela vale; sorteio reproduzível;
- links com tags de monorepo (`@scope/pkg@1.0.0`) e com espaço;
- planilha: abas, listas suspensas, links clicáveis e ausência de colunas da heurística;
- `gerar` não sobrescreve rótulos; `validar` aponta célula vazia, valor inválido, linha alterada e sorteio ausente;
- normalização dos rótulos (acentos, maiúsculas, código ou texto da lista).

Nova dependência: `openpyxl` (leitura e escrita de `.xlsx`), adicionada ao `requirements.txt`.

## Situação

A amostra final de 300 (RQ82) ainda não foi commitada em `dados/lab03_final/`, então o sorteio oficial ainda não foi feito. Um ensaio com a amostra piloto de 100 (`--entrada dados/lab03`) gerou 60 repositórios e 300 releases, todos os repositórios com 5 releases elegíveis. Esse ensaio **não** foi commitado e não deve ser rotulado: a amostra-ouro tem de sair da amostra final.
