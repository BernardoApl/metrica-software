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
- Operação, aquecimento, ordem, unidade de tempo, quantidade de pares e protocolo ainda precisam ser definidos. Não há tempos, amostra, p-valores ou conclusão inventados.
- Âncoras de navegação e seções expansíveis nativas, operáveis por teclado; layout responsivo; foco visível e suporte à preferência por movimento reduzido.

## Integração futura

Os IDs `cenario`, `pergunta` e `hipoteses` são âncoras estáveis. A #109 pode incorporar o conteúdo de `main` e os estilos no dashboard. Antes da coleta, confirmar o protocolo e a alternativa estatística com o grupo; a interface apresenta uma proposta bilateral, não uma decisão já registrada no enunciado. O estado “Protocolo em definição” só deve mudar mediante evidência da configuração real.

Não há gráficos nem chamadas a backends nesta entrega. Os expansores servem apenas para explicar o cenário e as hipóteses.

Fontes estatísticas: [SciPy ttest_rel](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_rel.html) e [SciPy wilcoxon](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.wilcoxon.html).
