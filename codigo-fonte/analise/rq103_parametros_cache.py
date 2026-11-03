"""RQ103: descreve a coleta real da RQ102 e define a simulação empírica pareada."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics as stats
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
COLETA = RAIZ / 'dados/experimento_cache/20261103T213612Z_ebe7be6978'
SAIDA = RAIZ / 'entregas/experimento-cache/RQ103'
ARQUIVOS = ('entrada.csv', 'resultado.json', 'aquecimentos.csv', 'tempos.csv', 'pares.csv')
TRATAMENTOS = ('sem_cache', 'com_cache')


def exigir(condicao, mensagem):
    if not condicao:
        raise ValueError(mensagem)


def sha(caminho):
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def ler_csv(caminho):
    with caminho.open(encoding='utf-8-sig', newline='') as arquivo:
        return list(csv.DictReader(arquivo))


def numero(valor):
    x = float(valor)
    exigir(math.isfinite(x), 'Tempo não finito.')
    return x


def proximo(a, b):
    return math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-12)


def carregar(pasta):
    """Falha antes de publicar saídas se a coleta estiver incompleta ou incoerente."""
    pasta = Path(pasta)
    meta = json.loads((pasta / 'execucao.json').read_text(encoding='utf-8'))
    exigir(meta['schema_version'] == 1 and meta['status'] == 'concluida',
           'Use uma coleta RQ102 concluída, sem pares inválidos.')
    exigir(meta['operacao'] == 'csv_agrupar_linguagem_v1', 'Operação não suportada.')
    for nome in ARQUIVOS:
        exigir(sha(pasta / nome) == meta['artefatos_sha256'][nome], f'Hash divergente: {nome}')
    exigir(sha(pasta / 'entrada.csv') == meta['entrada_sha256'], 'Hash da entrada divergente.')
    pares, bruto = ler_csv(pasta / 'pares.csv'), ler_csv(pasta / 'tempos.csv')
    n = meta['parametros']['pares']
    repeticoes = meta['parametros']['repeticoes_por_tratamento']
    exigir(isinstance(n, int) and n >= 2 and repeticoes >= 1, 'Parâmetros inválidos.')
    exigir(len(pares) == n == meta['pares_concluidos'] == meta['pares_validos'], 'Contagem de pares divergente.')
    exigir(len(bruto) == 2 * n and len(meta['plano']) == n, 'Contagem de tratamentos divergente.')
    indice = {}
    for r in bruto:
        chave = (int(r['par_id']), r['tratamento'])
        exigir(chave not in indice, 'Tratamento duplicado.')
        indice[chave] = r
    saida = []
    for i, p in enumerate(pares, 1):
        exigir(int(p['par_id']) == i and p['valido'] == 'True', 'Par ausente, duplicado ou inválido.')
        exigir(p['execucao_id'] == meta['execucao_id'], 'Execução divergente.')
        ordem = meta['plano'][i - 1]
        exigir(sorted(ordem) == sorted(TRATAMENTOS) and p['ordem_primeiro'] == ordem[0], 'Ordem divergente.')
        valores = {}
        for tratamento in TRATAMENTOS:
            r = indice[(i, tratamento)]
            exigir(r['status'] == 'ok' and not r['erro'], 'Medição com erro.')
            exigir(r['execucao_id'] == meta['execucao_id'] and r['entrada_sha256'] == meta['entrada_sha256'], 'Origem divergente.')
            exigir(r['resultado_sha256'] == meta['resultado_sha256'], 'Resultado divergente.')
            exigir(int(r['ordem']) == ordem.index(tratamento) + 1, 'Ordem bruta divergente.')
            exigir(int(r['concluidas']) == int(r['repeticoes']) == repeticoes, 'Lote incompleto.')
            hits = repeticoes if tratamento == 'com_cache' else 0
            exigir(int(r['cache_hits']) == hits and int(r['cache_misses']) == 0, 'Cache incompatível com o protocolo.')
            tempo = numero(p[f'tempo_{tratamento}_ms'])
            total = numero(r['duracao_total_ns'])
            exigir(tempo > 0 and total > 0, 'Tempos devem ser positivos para esta calibração.')
            exigir(proximo(tempo, numero(r['tempo_ms'])) and
                   proximo(tempo, total / repeticoes / 1e6) and
                   proximo(tempo * 1e6, numero(r['tempo_por_operacao_ns'])), 'Unidade ou tempo divergente.')
            valores[tratamento] = tempo
        diferenca = valores['sem_cache'] - valores['com_cache']
        exigir(proximo(diferenca, numero(p['diferenca_ms'])), 'Diferença pareada divergente.')
        saida.append(dict(par_id=i, ordem_primeiro=ordem[0], **valores,
                          diferenca=diferenca, razao=valores['sem_cache'] / valores['com_cache']))
    exigir(abs(sum(p['ordem_primeiro'] == 'sem_cache' for p in saida) * 2 - n) <= 1,
           'Ordem não balanceada.')
    return meta, saida


def quantil(valores, q):
    v = sorted(valores)
    posicao = (len(v) - 1) * q
    baixo = int(posicao)
    alto = min(baixo + 1, len(v) - 1)
    return v[baixo] + (v[alto] - v[baixo]) * (posicao - baixo)


def descrever(valores):
    q1, mediana, q3 = [quantil(valores, q) for q in (.25, .5, .75)]
    iqr = q3 - q1
    extremos = [i + 1 for i, x in enumerate(valores) if x < q1 - 1.5 * iqr or x > q3 + 1.5 * iqr]
    return dict(n=len(valores), media=stats.mean(valores), desvio_padrao_amostral=stats.stdev(valores),
                minimo=min(valores), q1=q1, mediana=mediana, q3=q3, maximo=max(valores),
                iqr=iqr, mad=stats.median(abs(x - mediana) for x in valores),
                pares_fora_cercas_iqr=extremos)


def correlacao(x, y):
    # Uma série constante não tem correlação definida, em vez de correlação zero.
    return stats.correlation(x, y) if len(x) >= 2 and len(set(x)) > 1 and len(set(y)) > 1 else None


def analisar(pasta):
    meta, pares = carregar(pasta)
    series = {nome: [p[nome] for p in pares] for nome in (*TRATAMENTOS, 'diferenca', 'razao')}
    descritivas = {nome: descrever(v) for nome, v in series.items()}
    meio = len(pares) // 2
    diagnosticos = dict(
        correlacao_pearson_pareada=correlacao(series['sem_cache'], series['com_cache']),
        correlacao_ordinal_tempo={k: correlacao(list(range(1, len(v) + 1)), v) for k, v in series.items() if k in TRATAMENTOS},
        medianas_por_ordem={ordem: {k: stats.median(p[k] for p in pares if p['ordem_primeiro'] == ordem)
                                  for k in (*TRATAMENTOS, 'diferenca')} for ordem in TRATAMENTOS},
        medianas_por_metade={k: dict(primeira=stats.median(v[:meio]), segunda=stats.median(v[meio:]))
                            for k, v in series.items() if k in TRATAMENTOS})
    origem = dict(execucao_id=meta['execucao_id'], manifesto_sha256=sha(Path(pasta) / 'execucao.json'),
                  artefatos_sha256=meta['artefatos_sha256'], entrada_sha256=meta['entrada_sha256'],
                  coletor_sha256=meta['coletor_sha256'], analise_sha256=sha(Path(__file__)),
                  ambiente_coleta=meta['ambiente'])
    resumo = dict(schema_version=1, origem=origem, unidade_tempos='ms por operação no lote',
                  pares_validos=len(pares), pares_excluidos=0, descritivas=descritivas, diagnosticos=diagnosticos)
    parametros = dict(schema_version=1, origem=origem, metodo='reamostragem_empirica_pareada_estratificada_v1',
        finalidade='Simulação descritiva do cenário observado; não é distribuição sob H0.',
        unidade='ms por operação no lote', tamanho_amostra_pares=len(pares), semente_sugerida=104,
        algoritmo='Para cada estrato, sortear com reposição índices uniformes de pares completos; manter os dois tempos juntos. Embaralhar a lista final com o mesmo gerador inicializado uma única vez.',
        estratos=[dict(ordem_primeiro=ordem, quantidade=sum(p['ordem_primeiro'] == ordem for p in pares),
                       pares=[dict(par_id_origem=p['par_id'], tempo_sem_cache_ms=p['sem_cache'],
                                   tempo_com_cache_ms=p['com_cache']) for p in pares if p['ordem_primeiro'] == ordem])
                  for ordem in TRATAMENTOS],
        restricoes=['Não sortear os tratamentos separadamente.', 'Não incluir aquecimentos ou remover extremos automaticamente.',
                    'Não adicionar ruído nem impor distribuição normal sem nova justificativa.',
                    'A reamostragem não preserva dependência temporal nem cria novas evidências independentes.',
                    'Tempos simulados não são novas medições reais; identificar sua origem.'])
    return resumo, parametros


def relatorio(resumo):
    d, diag = resumo['descritivas'], resumo['diagnosticos']
    linhas = ['# RQ103 — Dados reais e parâmetros da simulação', '',
        f"Coleta de origem: `{resumo['origem']['execucao_id']}`. Foram validados {resumo['pares_validos']} pares, sem exclusões. Aquecimentos não integram esta análise.", '',
        '## Estatísticas descritivas', '',
        'Tempos em ms por operação no lote; desvio padrão amostral (n − 1). Quartis por interpolação linear. A razão sem/com é adimensional.', '',
        '| Série | Média | Desvio padrão | Mediana | Q1 | Q3 | Mínimo | Máximo |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for nome, s in d.items():
        linhas.append('| ' + nome + ' | ' + ' | '.join(f'{s[k]:.8g}' for k in ('media', 'desvio_padrao_amostral', 'mediana', 'q1', 'q3', 'minimo', 'maximo')) + ' |')
    linhas += ['', '## Leitura dos dados', '',
        f"A diferença mediana sem − com foi {d['diferenca']['mediana']:.8g} ms. A mediana das razões individuais foi {d['razao']['mediana']:.8g}. Esses valores descrevem apenas esta execução local; não demonstram significância estatística nem um ganho universal de cache.", '',
        'O cache retorna uma referência em memória enquanto o recálculo abre e agrega o CSV inteiro. O custo de preencher o cache está fora do tratamento com cache. O custo do laço pesa proporcionalmente mais nesse tratamento muito curto.', '',
        '### Ordem e evolução da execução', '',
        '| Tratamento | Mediana na primeira metade | Mediana na segunda metade | Correlação entre posição e tempo |',
        '| --- | ---: | ---: | ---: |']
    for nome in TRATAMENTOS:
        m = diag['medianas_por_metade'][nome]
        linhas.append(f"| {nome} | {m['primeira']:.8g} | {m['segunda']:.8g} | {diag['correlacao_ordinal_tempo'][nome]} |")
    linhas += ['', 'Medianas por tratamento que iniciou o par:', '',
               '| Primeiro tratamento | Sem cache (ms) | Com cache (ms) | Diferença (ms) |',
               '| --- | ---: | ---: | ---: |']
    for ordem, m in diag['medianas_por_ordem'].items():
        linhas.append(f"| {ordem} | {m['sem_cache']:.8g} | {m['com_cache']:.8g} | {m['diferenca']:.8g} |")
    linhas += ['', 'As comparações por metade e ordem são diagnósticos descritivos, não testes causais. A ordem balanceada reduz um fator de confusão, mas não garante independência ou estabilidade temporal.', '',
               '### Valores extremos', '']
    for nome in TRATAMENTOS:
        linhas.append(f"- {nome}: pares fora das cercas de 1,5 × IQR: {d[nome]['pares_fora_cercas_iqr']}. Todos foram mantidos.")
    linhas += ['', '## Estratégia escolhida para a #104', '',
        'Usar distribuição empírica dos pares, estratificada pela ordem inicial. Sortear pares completos com reposição e probabilidade uniforme dentro de cada estrato, preservando a quantidade original por ordem. Assim os tempos permanecem positivos e a associação dos tratamentos é preservada nos pares de origem, sem impor normalidade ou sortear marginais independentes.', '',
        '`parametros_simulacao.json` contém os dois tempos de cada par, as quantidades por estrato, unidade, origem e semente sugerida 104. A semente só terá efeito na implementação do gerador da #104; esta entrega não gera dados simulados.', '',
        'A distribuição empírica possui suporte limitado aos valores observados e não prevê extremos novos. A estratégia não preserva a sequência temporal; serve à simulação descritiva deste cenário, não à inferência populacional. Se a próxima etapa exigir estudar dependência temporal, será necessário definir um modelo por blocos ou coletar sessões independentes. Esta configuração também não gera uma distribuição sob H0: esse objetivo exige um procedimento específico.', '',
        '## Limitações e rastreabilidade', '',
        'Os 300 repositórios são registros de uma única entrada. Os pares repetem essa entrada no mesmo ambiente e os tempos representam médias de 20 operações; não tratar as repetições como observações independentes. O cache do sistema operacional não foi desativado. Não generalizar para API, banco, cache frio ou outras máquinas.', '',
        'A análise exige coleta concluída e consistente, verifica hashes dos cinco artefatos e cruza pares com medições brutas, ordens, unidades e contadores do cache. Falhas interrompem a calibração; nada é excluído silenciosamente. Hashes fornecem rastreabilidade, não autenticação contra adulteração deliberada.', '',
        'Não há teste de hipótese, p-valor ou conclusão sobre rejeitar H0 nesta entrega. Consulte `resumo.json` para MAD, IQR, correlações e hashes completos.', '']
    return '\n'.join(linhas)


def executar(entrada, saida):
    resumo, parametros = analisar(entrada)
    saida = Path(saida)
    exigir(not saida.exists() or not any(saida.iterdir()), 'Saída já contém arquivos; escolha outra pasta para preservar a análise anterior.')
    saida.mkdir(parents=True, exist_ok=True)
    for nome, valor in [('resumo.json', resumo), ('parametros_simulacao.json', parametros)]:
        (saida / nome).write_text(json.dumps(valor, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    (saida / 'RELATORIO.md').write_text(relatorio(resumo), encoding='utf-8')
    return resumo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--entrada', type=Path, default=COLETA)
    parser.add_argument('--saida', type=Path, default=SAIDA)
    args = parser.parse_args()
    try:
        resumo = executar(args.entrada, args.saida)
    except (ValueError, OSError, KeyError, TypeError, csv.Error) as exc:
        parser.exit(1, f'Análise não concluída: {exc}\n')
    print(f"RQ103: {resumo['pares_validos']} pares analisados; saídas em {args.saida}")


if __name__ == '__main__':
    main()
