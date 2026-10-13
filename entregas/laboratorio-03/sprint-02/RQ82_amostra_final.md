# RQ82 — Coleta completa e amostra de 300+ repositórios

## Execução

Configure `GITHUB_TOKEN` no ambiente ou no `.env` da raiz e execute:

```powershell
python codigo-fonte/rq82_amostra_final.py --config config/rq82_amostra_final.json
```

A configuração usa os 8.000 candidatos com metadados, selecionados por estrelas,
até atingir 300 aprovados. Mantém no mínimo 5 releases publicadas, não draft e
não pré-release, e 50 runs válidos de push no default branch dentro da janela.
Não reduz os critérios para atingir a meta. Se os candidatos acabarem antes,
a auditoria registra `meta_nao_atingida` e o comando retorna 2.

A janela herdada é **01/10/2025 a 30/09/2026**, ainda provisória. A issue #82
não contém descrição que confirme as datas. A coleta pode ser executada nessa
janela, mas `amostra_final_validada` permanece falsa enquanto
`janela_confirmada` não for verdadeira com respaldo do professor.

## Coleta e retomada

- Reutiliza o cliente REST/cache da RQ78 e o pipeline de seleção e métricas.
- Mantém o limite operacional de 20.000 runs do piloto: repositórios acima
  desse limite são excluídos por inteiro e contabilizados no funil. Isso
  restringe a amostra e deve ser mencionado como limitação do estudo.
  Os aprovados não têm seus runs cortados. Comparações de commits não têm
  limite de páginas na configuração final.
- Complementa os aprovados com tags e datas de autoria dos commits (RQ75).
- Salva um checkpoint comprimido por repositório em
  `dados/.cache/rq82_repositorios/`. A identificação inclui configuração,
  candidatos e código, evitando mistura de janelas e versões.
- Reutiliza checkpoints íntegros na retomada. Falhas de acesso, tags incompletas
  e comparações truncadas/indisponíveis são reavaliadas. O cache HTTP segue as
  regras da RQ78; respostas definitivas como 404 exigem outro diretório de cache
  para verificar eventual recuperação do recurso.
- HTTP 401 em compare interrompe a execução, sem ser tratado como release
  ausente. O token nunca entra nos arquivos de resultados.
- A amostra anterior de 100, em `dados/lab03/`, permanece preservada.

As consultas podem exigir várias renovações de cota da API. Interromper e
executar o mesmo comando reaproveita os dados já coletados.

## Consolidação em `dados/lab03_final/`

São gerados os CSVs do pipeline (métricas, candidatos avaliados, releases,
workflow runs comprimidos, intervalos auditados, lead times e commits
comprimidos), `funil_selecao.csv`, `tags.csv` e `resumo_execucao.json`.
O arquivo `validacao_rq82.json` é a referência para a conclusão da #82:

- pelo menos 300 repositórios únicos, atendendo aos critérios;
- quantidade final do funil igual à amostra;
- idade e contribuidores presentes;
- ausência de teto de runs, compare truncado/indisponível e tags incompletas;
- commits com SHA e data de autoria;
- janela confirmada.

Pendências não são ocultadas nem substituídas por zero. `meta_atingida` indica
apenas quantidade; não substitui `amostra_final_validada`.
Retornos: 0 = validada; 2 = consolidada com pendências; 1 = erro operacional;
130 = interrupção. Os checkpoints permanecem disponíveis em caso de erro.

## Testes

```powershell
.\.venv\Scripts\python.exe -m pytest codigo-fonte/testes/test_rq82.py codigo-fonte/testes/test_pipeline_dora.py codigo-fonte/testes/test_rq76_compare.py codigo-fonte/testes/test_rq75.py -q
```

39 testes passaram na implementação inicial. Fixtures sintéticas validam o
limiar 299/300, duplicação, janela provisória, metadados ausentes, truncamento,
retomada, isolamento de configuração e propagação de falhas de autenticação.
Essas fixtures não constituem a amostra real nem são exportadas para `dados/`.
