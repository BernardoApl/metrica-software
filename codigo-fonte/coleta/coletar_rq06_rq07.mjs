import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, "..", "..");
const QUERY_PATH = path.join(ROOT, "codigo-fonte", "consulta-graphql", "query_rq06_rq07.graphql");
const DEFAULT_OUTPUT_DIR = path.join(ROOT, "dados");
const GRAPHQL_URL = "https://api.github.com/graphql";

function parseArgs(argv) {
  const args = {
    limit: 100,
    batchSize: 100,
    query: "stars:>1000 archived:false fork:false sort:stars-desc",
    outputDir: DEFAULT_OUTPUT_DIR,
    inputJson: null,
    pauseSeconds: 1,
    help: false,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    const next = () => {
      if (i + 1 >= argv.length) {
        throw new Error(`Valor ausente para ${arg}`);
      }
      i += 1;
      return argv[i];
    };

    if (arg === "--help" || arg === "-h") args.help = true;
    else if (arg === "--limit") args.limit = Number.parseInt(next(), 10);
    else if (arg === "--batch-size") args.batchSize = Number.parseInt(next(), 10);
    else if (arg === "--query") args.query = next();
    else if (arg === "--output-dir") args.outputDir = path.resolve(next());
    else if (arg === "--input-json") args.inputJson = path.resolve(next());
    else if (arg === "--pause-seconds") args.pauseSeconds = Number.parseFloat(next());
    else throw new Error(`Argumento desconhecido: ${arg}`);
  }

  return args;
}

function printHelp() {
  console.log(`Coleta e calcula RQ06 e RQ07 usando GitHub GraphQL.

Uso:
  node codigo-fonte/coleta/coletar_rq06_rq07.mjs [opcoes]

Opcoes:
  --limit <n>          Quantidade de repositorios. Padrao: 100
  --batch-size <n>     Tamanho da pagina GraphQL, entre 1 e 100. Padrao: 100
  --query <texto>      Busca no formato aceito pelo GitHub.
  --output-dir <dir>   Diretorio de saida. Padrao: dados/
  --input-json <file>  Usa JSON ja coletado em vez de chamar a API.
  --pause-seconds <n>  Pausa entre paginas. Padrao: 1
  --help              Mostra esta ajuda.

Sem --input-json, configure GITHUB_TOKEN antes de executar.`);
}

function parseGithubDate(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function daysSince(value, reference) {
  const date = parseGithubDate(value);
  if (!date) return null;
  return Math.floor((reference.getTime() - date.getTime()) / 86_400_000);
}

function sleep(seconds) {
  return new Promise((resolve) => setTimeout(resolve, seconds * 1000));
}

async function graphqlRequest(query, variables, token) {
  const response = await fetch(GRAPHQL_URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      Accept: "application/vnd.github+json",
      "User-Agent": "metrica-software-rq06-rq07",
    },
    body: JSON.stringify({ query, variables }),
  });

  const text = await response.text();
  let payload;
  try {
    payload = JSON.parse(text);
  } catch {
    throw new Error(`Resposta invalida do GitHub GraphQL: ${text}`);
  }

  if (!response.ok) {
    throw new Error(`GitHub GraphQL HTTP ${response.status}: ${text}`);
  }

  return payload;
}

async function collectRepositories({ limit, query: queryString, batchSize, pauseSeconds }, token) {
  const query = await readFile(QUERY_PATH, "utf8");
  const repositories = [];
  let after = null;
  let rateLimit = null;

  while (repositories.length < limit) {
    const first = Math.min(batchSize, limit - repositories.length);
    const payload = await graphqlRequest(query, { queryString, first, after }, token);

    if (payload.errors) {
      throw new Error(JSON.stringify(payload.errors, null, 2));
    }

    const search = payload.data.search;
    rateLimit = payload.data.rateLimit ?? null;
    repositories.push(...search.nodes.filter(Boolean));

    if (!search.pageInfo.hasNextPage) break;
    after = search.pageInfo.endCursor;
    if (pauseSeconds > 0) await sleep(pauseSeconds);
  }

  return { repositories: repositories.slice(0, limit), rateLimit };
}

function flattenRepositories(repositories, reference) {
  return repositories.map((repo) => {
    const totalIssues = repo.issues.totalCount;
    const closedIssues = repo.closedIssues.totalCount;
    const ratio = totalIssues === 0 ? null : closedIssues / totalIssues;
    const language = repo.primaryLanguage?.name ?? "Sem linguagem primaria";

    return {
      repositorio: repo.nameWithOwner,
      url: repo.url,
      linguagem_primaria: language,
      issues_total: totalIssues,
      issues_fechadas: closedIssues,
      rq06_razao_issues_fechadas_total: ratio,
      rq02_pull_requests_aceitos: repo.mergedPullRequests.totalCount,
      rq03_total_releases: repo.releases.totalCount,
      rq04_updated_at: repo.updatedAt,
      rq04_dias_desde_ultima_atualizacao: daysSince(repo.updatedAt, reference),
    };
  });
}

function numericValues(rows, field) {
  return rows.map((row) => row[field]).filter((value) => value !== null && value !== undefined);
}

function average(values) {
  if (values.length === 0) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function median(values) {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 1) return sorted[middle];
  return (sorted[middle - 1] + sorted[middle]) / 2;
}

function groupRq07ByLanguage(rows) {
  const grouped = new Map();
  for (const row of rows) {
    const key = row.linguagem_primaria;
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(row);
  }

  return [...grouped.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([language, languageRows]) => {
      const prs = numericValues(languageRows, "rq02_pull_requests_aceitos");
      const releases = numericValues(languageRows, "rq03_total_releases");
      const days = numericValues(languageRows, "rq04_dias_desde_ultima_atualizacao");

      return {
        linguagem_primaria: language,
        quantidade_repositorios: languageRows.length,
        rq02_prs_aceitos_media: average(prs),
        rq02_prs_aceitos_mediana: median(prs),
        rq02_prs_aceitos_min: prs.length ? Math.min(...prs) : null,
        rq02_prs_aceitos_max: prs.length ? Math.max(...prs) : null,
        rq03_releases_media: average(releases),
        rq03_releases_mediana: median(releases),
        rq03_releases_min: releases.length ? Math.min(...releases) : null,
        rq03_releases_max: releases.length ? Math.max(...releases) : null,
        rq04_dias_desde_atualizacao_media: average(days),
        rq04_dias_desde_atualizacao_mediana: median(days),
        rq04_dias_desde_atualizacao_min: days.length ? Math.min(...days) : null,
        rq04_dias_desde_atualizacao_max: days.length ? Math.max(...days) : null,
      };
    });
}

function csvEscape(value) {
  if (value === null || value === undefined) return "";
  const text = String(value);
  if (/[",\r\n]/.test(text)) return `"${text.replaceAll('"', '""')}"`;
  return text;
}

async function writeCsv(filePath, rows) {
  if (rows.length === 0) {
    await writeFile(filePath, "", "utf8");
    return;
  }

  const headers = Object.keys(rows[0]);
  const lines = [
    headers.join(","),
    ...rows.map((row) => headers.map((header) => csvEscape(row[header])).join(",")),
  ];
  await writeFile(filePath, `${lines.join("\n")}\n`, "utf8");
}

async function writeOutputs(outputDir, rawRepositories, flatRows, rq07Rows, metadata) {
  await mkdir(outputDir, { recursive: true });

  const rawJson = path.join(outputDir, "repositorios_rq06_rq07.json");
  const rq06Csv = path.join(outputDir, "rq06_razao_issues.csv");
  const rq07Csv = path.join(outputDir, "rq07_metricas_por_linguagem.csv");
  const rq07DetailCsv = path.join(outputDir, "rq07_repositorios_com_metricas_base.csv");

  await writeFile(
    rawJson,
    JSON.stringify(
      {
        metadata,
        repositories: rawRepositories,
        rows: flatRows,
        rq07_by_language: rq07Rows,
      },
      null,
      2,
    ),
    "utf8",
  );

  await writeCsv(
    rq06Csv,
    flatRows.map((row) => ({
      repositorio: row.repositorio,
      linguagem_primaria: row.linguagem_primaria,
      issues_fechadas: row.issues_fechadas,
      issues_total: row.issues_total,
      rq06_razao_issues_fechadas_total: row.rq06_razao_issues_fechadas_total,
    })),
  );
  await writeCsv(rq07Csv, rq07Rows);
  await writeCsv(rq07DetailCsv, flatRows);

  return { rawJson, rq06Csv, rq07Csv, rq07DetailCsv };
}

async function loadFromInput(filePath) {
  const content = (await readFile(filePath, "utf8")).replace(/^\uFEFF/, "");
  const payload = JSON.parse(content);
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload.repositories)) return payload.repositories;
  throw new Error("JSON de entrada deve ser uma lista ou conter a chave 'repositories'.");
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    printHelp();
    return;
  }

  if (!Number.isInteger(args.limit) || args.limit < 1) {
    throw new Error("--limit deve ser maior que zero.");
  }
  if (!Number.isInteger(args.batchSize) || args.batchSize < 1 || args.batchSize > 100) {
    throw new Error("--batch-size deve estar entre 1 e 100.");
  }

  const reference = new Date();
  let repositories;
  let rateLimit = null;

  if (args.inputJson) {
    repositories = await loadFromInput(args.inputJson);
  } else {
    const token = process.env.GITHUB_TOKEN;
    if (!token) {
      throw new Error("Configure a variavel de ambiente GITHUB_TOKEN ou use --input-json.");
    }
    const collected = await collectRepositories(args, token);
    repositories = collected.repositories;
    rateLimit = collected.rateLimit;
  }

  const flatRows = flattenRepositories(repositories, reference);
  const rq07Rows = groupRq07ByLanguage(flatRows);
  const metadata = {
    generated_at: reference.toISOString(),
    limit: args.limit,
    query: args.query,
    repository_count: repositories.length,
    rate_limit: rateLimit,
    rq06: "issues fechadas / total de issues; valor nulo quando total = 0",
    rq07: "agrupamento por linguagem primaria de RQ02, RQ03 e RQ04",
  };

  const outputs = await writeOutputs(args.outputDir, repositories, flatRows, rq07Rows, metadata);
  console.log(`Repositorios processados: ${flatRows.length}`);
  for (const [label, filePath] of Object.entries(outputs)) {
    console.log(`${label}: ${filePath}`);
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
