# RQ73 — Ampliação dos candidatos

Esta etapa amplia a base para 4.000 candidatos públicos com mais de 1.000
estrelas. Os candidatos são buscados por popularidade decrescente. Não se trata
da amostra final elegível para as métricas DORA: os filtros de releases e
workflow runs na janela do LAB03 são uma etapa posterior.

## Execução

Com `GITHUB_TOKEN` configurado no ambiente ou no `.env` da raiz:

```powershell
python codigo-fonte/coleta/rq73_coletar_candidatos.py --limite 4000
python -m unittest discover -s codigo-fonte/testes -p test_rq73_candidatos.py
```

O coletor divide recursivamente as faixas de estrelas que ultrapassam o limite
de 1.000 resultados da API Search. Percorre primeiro as faixas superiores e
pagina cada faixa com até 100 resultados por página. Descarta duplicações por
ID ou nome completo e valida visibilidade pública e quantidade de estrelas.
Se uma única quantidade de estrelas reunir mais de 1.000 repositórios, a
execução sinaliza erro em vez de assumir cobertura completa.

As respostas ficam em `dados/.cache/rq73_busca/`, ignorado pelo Git. Reexecutar
o mesmo comando reutiliza esse cache. Para uma nova coleta, informe outro
diretório com `--cache`. Limites de requisições são respeitados com espera
automática. Respostas incompletas não entram no cache.

## Artefatos

- `dados/rq73_candidatos.json`: candidatos, datas e critérios da coleta,
  faixas consultadas, contagens e indicação de alcance da meta.
- `dados/rq73_candidatos.csv`: os mesmos candidatos em formato tabular.
- `dados/rq73_candidatos_funil.csv`: registros examinados, rejeições e
  deduplicação desta ampliação, até o limite solicitado.

O funil contabiliza os registros efetivamente examinados, não todo o universo
indicado pela busca. Os arquivos anteriores de seleção permanecem separados.
Estrelas e posições podem mudar durante a coleta; a API não oferece uma
fotografia transacional do ranking. O cache registra as respostas consultadas.

Referência: [GitHub REST Search](https://docs.github.com/en/rest/search/search#search-repositories).

## Resultado da execução

Coleta concluída em 06/10/2026 (horário de Brasília), entre 23:49 e 23:55:
4.000 candidatos únicos, sem duplicações ou rejeições nos registros examinados.
O candidato com menor popularidade nesta coleta tinha 13.165 estrelas.
As datas dos artefatos estão em UTC (07/10/2026).

Validação: oito testes automatizados aprovados; JSON e CSV com os mesmos
4.000 IDs, nomes únicos, ordenação decrescente por estrelas e total final do
funil consistente. A elegibilidade DORA ainda não foi avaliada nesta lista.
