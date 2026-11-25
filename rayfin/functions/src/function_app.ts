import { UserDataFunctions, UserThrownError, AudienceType, type RayfinContext } from '@microsoft/fabric-user-data-functions';
import sql from 'mssql';
import type { Row, Telemetry, Loads, FabricHealth, Job, Schedule } from './contracts.js';
import { DEVICES, TELEMETRY_TREND, INVALID_READINGS, LOAD_SOURCES,
  TABLE_COUNTS, DAILY_LOADS, DUPLICATES } from './queries.js';

const udf = new UserDataFunctions();
const workspace = '6d6350e8-6f22-4a8b-b06a-eb4a3b68dd23';
const cluster = 'https://trd-mvvjt2s3q8pm91pu1b.z0.kusto.fabric.microsoft.com';
const database = '13e252db-4acb-4794-adee-17c12386f200';
const api = `https://api.fabric.microsoft.com/v1/workspaces/${workspace}`;

async function getJson<T>(url: string, token: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init, signal: AbortSignal.timeout(45000),
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
  });
  if (!response.ok) {
    console.error('Control tower upstream error', new URL(url).pathname, response.status);
    throw new UserThrownError(`Upstream request failed (${response.status}); check source permissions or service health.`);
  }
  return response.json() as Promise<T>;
}

interface KqlResponse {
  Tables: { TableName: string; Columns: { ColumnName: string }[]; Rows: unknown[][] }[];
  error?: { message?: string };
  Exceptions?: unknown[];
}

async function kql(query: string, token: string): Promise<Row[]> {
  const result = await getJson<KqlResponse>(`${cluster}/v1/rest/query`, token, {
    method: 'POST', body: JSON.stringify({ db: database, csl: query }),
  });
  if (result.error || result.Exceptions?.length) throw new UserThrownError('KQL query failed. Inspect the Eventhouse query history.');
  const status = result.Tables?.find(t => t.TableName === 'QueryStatus');
  const severity = status?.Columns.findIndex(column => column.ColumnName === 'Severity') ?? -1;
  if (status?.Rows.some(row => (severity >= 0 && typeof row[severity] === 'number' && Number(row[severity]) <= 2) ||
      row.some(value => value === 'Error' || value === 'PartialQueryFailure'))) {
    throw new UserThrownError('KQL returned a partial query failure; telemetry is unavailable.');
  }
  const table = result.Tables?.[0];
  if (!table) throw new UserThrownError('KQL returned no result table.');
  return table.Rows.map(row => Object.fromEntries(table.Columns.map((c, i) => {
    const v = row[i];
    if (v !== null && typeof v !== 'string' && typeof v !== 'number' && typeof v !== 'boolean') {
      throw new UserThrownError(`Unexpected KQL value in ${c.ColumnName}`);
    }
    return [c.ColumnName, v ?? null];
  })));
}

udf.func('getTelemetry', async (
  ctx: RayfinContext<Record<string, never>, AudienceType.Sql>,
): Promise<Telemetry> => {
  // This Eventhouse accepts the SQL audience; custom audiences require a separate item identity.
  const token = ctx.Tokens.Sql;
  const [devices, trend, invalid] = await Promise.all([
    kql(DEVICES, token), kql(TELEMETRY_TREND, token), kql(INVALID_READINGS, token),
  ]);
  const invalidReadings = invalid[0]?.Count;
  if (typeof invalidReadings !== 'number') throw new UserThrownError('KQL did not return a valid quality-check count.');
  return { checkedAt: new Date().toISOString(), devices, trend, invalidReadings };
}, []);

udf.func('getLoads', async (
  ctx: RayfinContext<Record<string, never>, AudienceType.Sql>,
): Promise<Loads> => {
  const pool = new sql.ConnectionPool({
    server: 'vfrrjffjjzjenhckml4ac23ygq-5bigg3jcn6fuvmdk5nfdw2g5em.datawarehouse.fabric.microsoft.com',
    // SQL routes by the analytics endpoint's catalog ID, not the parent Lakehouse ID.
    database: '64862655-d4a4-4ca6-b7a1-c9f1457c6a02',
    options: { encrypt: true, trustServerCertificate: false },
    connectionTimeout: 30000, requestTimeout: 45000,
    authentication: { type: 'azure-active-directory-access-token', options: { token: ctx.Tokens.Sql } },
  });
  try {
    await pool.connect();
    const sources = await pool.request().query<Row>(LOAD_SOURCES);
    const tables = await pool.request().query<Row>(TABLE_COUNTS);
    const daily = await pool.request().query<Row>(DAILY_LOADS);
    const duplicates = await pool.request().query<{ duplicate_keys: number }>(DUPLICATES);
    return { checkedAt: new Date().toISOString(), sources: sources.recordset,
      tables: tables.recordset, daily: daily.recordset,
      duplicateKeys: Number(duplicates.recordset[0].duplicate_keys) };
  } catch (error) {
    if (error instanceof sql.ConnectionError || error instanceof sql.RequestError) {
      console.error('Lakehouse SQL monitoring failed', error.code);
      throw new UserThrownError(`Lakehouse SQL ${error.code}: ${error.message}`);
    }
    throw error;
  } finally {
    await pool.close();
  }
}, []);

async function list<T>(path: string, token: string): Promise<T[]> {
  let url: string | undefined = `${api}/${path}`;
  const values: T[] = [];
  for (let page = 0; url && page < 10; page++) {
    const parsed = new URL(url);
    if (parsed.origin !== 'https://api.fabric.microsoft.com' ||
        !parsed.pathname.startsWith(`/v1/workspaces/${workspace}/`)) {
      throw new UserThrownError('Unexpected Fabric continuation URL.');
    }
    const data: { value: T[]; continuationUri?: string } = await getJson(url, token);
    values.push(...data.value);
    url = data.continuationUri;
  }
  if (url) throw new UserThrownError('Fabric pagination limit reached. Results are incomplete.');
  return values;
}

udf.func('getFabricHealth', async (
  ctx: RayfinContext<Record<string, never>, AudienceType.Fabric>,
): Promise<FabricHealth> => {
  const token = ctx.Tokens.Fabric;
  const [simulator, pipeline, schedules, topology] = await Promise.all([
    list<Job>('items/94decbd2-0715-423d-aaf7-fd64b7eef13b/jobs/instances', token),
    list<Job>('items/48bd9310-d378-4199-87f5-ad10ede833de/jobs/instances', token),
    list<Schedule>('items/48bd9310-d378-4199-87f5-ad10ede833de/jobs/Pipeline/schedules', token),
    getJson<{ sources: unknown[]; destinations: unknown[] }>(
      `${api}/eventstreams/bf9063ce-ecfc-4f7d-ab98-efce7775cce6/topology`, token),
  ]);
  const recent = (jobs: Job[]) => jobs.sort((a, b) =>
    Date.parse(b.startTimeUtc) - Date.parse(a.startTimeUtc)).slice(0, 10);
  return { checkedAt: new Date().toISOString(), simulator: recent(simulator),
    pipeline: recent(pipeline), schedules,
    eventstream: { name: 'es_tank_readings', sources: topology.sources.length,
      destinations: topology.destinations.length } };
}, []);
