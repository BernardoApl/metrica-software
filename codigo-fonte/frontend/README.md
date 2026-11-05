# Frontend do experimento de cache

## Issue #101

Seção independente de cenário experimental, pergunta de pesquisa e hipóteses H0/H1. HTML e CSS locais, sem dependências, JavaScript, token ou API. Não implementa as issues #102–#109.

Na raiz do repositório:

```powershell
python -m http.server 8080 --bind 127.0.0.1 --directory codigo-fonte/frontend
```

Acesse http://127.0.0.1:8080. Também é possível abrir `index.html` diretamente. Encerre o servidor com Ctrl+C.

## Conteúdo e decisões

- Cenário: comparação pareada dos tempos da mesma operação com e sem cache, conforme o tema das issues #102–#105.
- Variáveis e tratamentos; convenção `d = tempo_sem_cache - tempo_com_cache`.
- Pergunta bilateral e formulação inicial de H0/H1 para o teste t pareado.
- Detalhamento próprio do Wilcoxon, sem confundir sua hipótese com igualdade de médias.
- Protocolo alinhado à coleta real da #102: agregação do CSV por linguagem, cache de resultado aquecido, 30 pares de lotes de 20 operações, ordem balanceada e três pares de aquecimento separados.
- A página identifica a coleta de 03/11/2026 e distingue registros de entrada, repetições e pares. Não apresenta p-valores nem conclusões estatísticas.
- Âncoras de navegação e seções expansíveis nativas, operáveis por teclado; layout responsivo; foco visível e suporte à preferência por movimento reduzido.

## Integração futura

Os IDs `cenario`, `protocolo`, `pergunta` e `hipoteses` são âncoras estáveis. A #109 pode incorporar o conteúdo de `main` e os estilos no dashboard. A interface mantém a proposta bilateral da #101; a coleta não representa aprovação dessa escolha pelo professor. Antes de testes inferenciais, avaliar os pressupostos e a dependência entre pares que compartilham entrada e ambiente.

Fonte do cenário: [protocolo da #102](../coleta/README_rq102_tempos_cache.md) e [manifesto da coleta](../../dados/experimento_cache/20261103T213612Z_ebe7be6978/execucao.json). A página é estática e descreve essa execução específica; não simula acompanhamento ao vivo. Se o protocolo mudar, atualizar a seção junto com sua documentação.

Não há gráficos nem chamadas a backends nesta entrega. Os expansores servem apenas para explicar o cenário e as hipóteses.

Fontes estatísticas: [SciPy ttest_rel](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_rel.html) e [SciPy wilcoxon](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.wilcoxon.html).

## Issues #108 e #109: G1 e dashboard

`rq109_dashboard.py` executa a #107 e a #108, atualiza o bloco do G1 em `index.html` e abre a página:

```powershell
python codigo-fonte/frontend/rq109_dashboard.py
```

Só o trecho entre os marcadores `G1:INICIO` e `G1:FIM` é gerado; o resto da página continua editável à mão. Use `--sem-abrir` para apenas reconstruir.

### Pendências de integração

- **#104:** salvar os dados em `entregas/experimento-cache/RQ104/pares_simulados.csv`, com as colunas `tempo_sem_cache_ms` e `tempo_com_cache_ms`. Depois, reconstruir o dashboard: o aviso de dados provisórios sai sozinho.
- **#106:** salvar o gráfico em `graficos/g2.svg` e trocar o aviso da seção `testes` em `index.html` pela figura e pelo texto.
- **G2 a G4:** o enunciado pede a mesma cor para cada teste. Proposta: t pareado `#2a78d6` e Wilcoxon `#eb6834`. O G1 usa `#6250d6` (real) e `#1baf7a` (simulado), para não confundir origem dos dados com teste.
