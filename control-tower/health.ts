import type { Job, Loads, Row, Schedule } from '../rayfin/functions/src/contracts';

export type Tone = 'good' | 'warn' | 'bad' | 'unknown';
export interface Signal { tone: Tone; label: string; detail: string }

export function number(row: Row, key: string): number | null {
  const value = row[key];
  if (value === null || value === undefined || value === '') return null;
  const parsed = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function timestamp(value: unknown): number | null {
  if (typeof value !== 'string' || !value) return null;
  // Kusto can omit the UTC suffix; its datetime values are always UTC.
  const parsed = Date.parse(/(?:Z|[+-]\d\d:\d\d)$/i.test(value) ? value : `${value}Z`);
  return Number.isFinite(parsed) ? parsed : null;
}

export function deviceHealth(row: Row, now: number): Signal {
  const last = timestamp(row.reading_ts);
  if (last === null) return { tone: 'bad', label: 'No heartbeat', detail: 'No reading found in the last 24 hours.' };
  const seconds = (now - last) / 1000;
  if (seconds < -60) return { tone: 'bad', label: 'Clock skew', detail: 'Device time is over 60 seconds ahead; check the producer clock.' };
  if (seconds > 180) return { tone: 'bad', label: 'Stale', detail: 'No reading for over 3 minutes. Check the simulator, then Eventstream.' };
  if (seconds > 90) return { tone: 'warn', label: 'Delayed', detail: 'Heartbeat is over 90 seconds old (expected every 60 seconds).' };
  return { tone: 'good', label: 'Receiving', detail: 'Recent reading observed in Eventhouse; upstream sent counts are not available.' };
}

export function completedMinutes(rows: Row[], now: number): Row[] {
  const boundary = Math.floor(now / 60000) * 60000;
  // Exclude both the current minute and the clipped first minute of a 30-minute query.
  return rows.filter(row => {
    const time = timestamp(row.minute);
    return time !== null && time >= boundary - 29 * 60000 && time < boundary;
  });
}

export function latestJob(jobs: Job[]): Job | null {
  return [...jobs].sort((a, b) => (timestamp(b.startTimeUtc) ?? 0) - (timestamp(a.startTimeUtc) ?? 0))[0] ?? null;
}

export function jobHealth(job: Job | null): Signal {
  if (!job) return { tone: 'unknown', label: 'No runs', detail: 'No run history returned; no successful load can be confirmed.' };
  if (job.status === 'Completed') return { tone: 'good', label: 'Completed', detail: `Last run ended ${job.endTimeUtc ?? 'without an end timestamp'}.` };
  if (job.status === 'InProgress' || job.status === 'NotStarted') return { tone: 'warn', label: job.status, detail: 'Run is active or queued. Do not start a duplicate run.' };
  return { tone: 'bad', label: job.status, detail: job.failureReason?.message || 'Inspect the run details in Fabric before retrying.' };
}

export function scheduleHealth(schedules: Schedule[], now: number): Signal {
  if (!schedules.length) return { tone: 'warn', label: 'Not scheduled', detail: 'No daily refresh schedule was returned.' };
  const enabled = schedules.filter(s => s.enabled);
  if (!enabled.length) return { tone: 'warn', label: 'Disabled', detail: 'All refresh schedules are disabled.' };
  if (!enabled.some(s => (timestamp(s.configuration.endDateTime) ?? 0) > now)) {
    return { tone: 'bad', label: 'Expired', detail: 'The refresh schedule has ended; extend it in Fabric if the demo is still needed.' };
  }
  return { tone: 'good', label: 'Scheduled', detail: 'Daily at 07:15 Vietnam time. Check the schedule end date before demonstrations.' };
}

export const expectedPerDay: Record<string, number> = {
  STOCK_SENSOR: 12, FEED: 9, OUTPUT: 12, PURITY: 3,
  PRODUCTION: 15, FG_STOCK: 15, SHIPPED: 15, STOCK_BOOK: 4,
};

function dateKey(time: number): number {
  return Number(new Date(time).toISOString().slice(0, 10).replaceAll('-', ''));
}

export function expectedLoadDates(now: number): number[] {
  // The demo refresh starts at 07:15 UTC+7; allow one hour before calling today's load late.
  const local = new Date(now + 7 * 3600000);
  const today = Date.UTC(local.getUTCFullYear(), local.getUTCMonth(), local.getUTCDate());
  const anchor = today - (local.getUTCHours() * 60 + local.getUTCMinutes() < 495 ? 86400000 : 0);
  return Array.from({ length: 30 }, (_, i) => dateKey(anchor - (29 - i) * 86400000));
}

export function loadHealth(load: Loads, now: number): Signal {
  const expected = expectedLoadDates(now);
  const days = new Map(load.daily.map(row => [number(row, 'date_key'), number(row, 'row_count')]));
  const wrongDays = expected.filter(day => days.get(day) !== 85).length;
  const wrongMeasures = Object.entries(expectedPerDay).filter(([id, count]) => {
    const source = load.sources.find(row => row.measure_id === id);
    return !source || number(source, 'row_count') !== count * 30 ||
      number(source, 'loaded_days') !== 30 || number(source, 'null_values') !== 0;
  }).length;
  if (load.duplicateKeys || wrongDays || wrongMeasures || load.daily.length !== 30) {
    return { tone: 'bad', label: 'Load exception', detail: `${wrongDays} expected days incomplete or late; ${wrongMeasures} measure groups outside the 30-day contract; ${load.duplicateKeys} duplicate keys.` };
  }
  return { tone: 'good', label: 'Loaded', detail: 'All 30 expected dates have 85 facts, all 8 measure groups match, and no duplicate keys or null values were found.' };
}

export function dateInput(time: number): string {
  return new Date(time + 7 * 3600000).toISOString().slice(0, 10);
}

function validatedKey(date: string): number {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !Number.isFinite(Date.parse(date)) ||
      new Date(date).toISOString().slice(0, 10) !== date) throw new Error('Choose a valid date.');
  return Number(date.replaceAll('-', ''));
}

export interface Filters { start: string; end: string; shift: string }

export function modelQueries(filters: Filters): { kpis: string; trend: string } {
  const start = validatedKey(filters.start);
  const end = validatedKey(filters.end);
  if (start > end) throw new Error('The start date must be on or before the end date.');
  if (!['ALL', 'A', 'B', 'C'].includes(filters.shift)) throw new Error('Choose a valid shift.');
  const date = `FILTER(ALL(dim_date), dim_date[date_key] >= ${start} && dim_date[date_key] <= ${end})`;
  const shift = filters.shift === 'ALL' ? '' : `, TREATAS({"${filters.shift}"}, dim_shift[shift_id])`;
  return {
    kpis: `EVALUATE CALCULATETABLE(ROW(
      "Days of Cover", [Days of Cover], "Ethylene Yield %", [Ethylene Yield %],
      "Mass Balance Gap %", [Mass Balance Gap %], "Inventory Accuracy %", [Inventory Accuracy %],
      "Ethane Purity %", [Ethane Purity %], "FG Days of Stock", [FG Days of Stock],
      "Total Feed (t)", [Total Feed (t)], "Total Output (t)", [Total Output (t)],
      "Total Production (t)", [Total Production (t)], "Shipped (t)", [Shipped (t)],
      "Ethane Stock (t)", [Ethane Stock (t)]), ${date}${shift})`,
    trend: `EVALUATE SUMMARIZECOLUMNS(dim_date[date], ${date}${shift},
      "Yield", [Ethylene Yield %], "Purity", [Ethane Purity %],
      "Gap", [Mass Balance Gap %]) ORDER BY dim_date[date]`,
  };
}
