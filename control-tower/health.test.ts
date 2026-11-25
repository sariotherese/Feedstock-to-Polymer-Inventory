import { test } from 'node:test';
import assert from 'node:assert/strict';
import { completedMinutes, deviceHealth, expectedLoadDates, loadHealth, modelQueries,
  scheduleHealth, latestJob, jobHealth, expectedPerDay, number } from './health';
import type { Loads } from '../rayfin/functions/src/contracts';

const now = Date.parse('2026-11-23T12:30:25Z');

test('heartbeats distinguish missing, stale, delayed, healthy and future data', () => {
  assert.equal(deviceHealth({ reading_ts: null }, now).tone, 'bad');
  assert.equal(deviceHealth({ reading_ts: '2026-11-23T12:26:00Z' }, now).label, 'Stale');
  assert.equal(deviceHealth({ reading_ts: '2026-11-23T12:28:30' }, now).label, 'Delayed');
  assert.equal(deviceHealth({ reading_ts: '2026-11-23T12:30:00Z' }, now).tone, 'good');
  assert.equal(deviceHealth({ reading_ts: '2026-11-23T12:33:00Z' }, now).label, 'Clock skew');
  assert.equal(number({ value: null }, 'value'), null);
});

test('partial edge minutes are not treated as missing events', () => {
  const rows = ['12:00', '12:01', '12:29', '12:30'].map(minute => ({
    minute: `2026-11-23T${minute}:00Z`, events: 0,
  }));
  assert.deepEqual(completedMinutes(rows, now).map(row => row.minute),
    ['2026-11-23T12:01:00Z', '2026-11-23T12:29:00Z']);
});

test('load contract uses Vietnam refresh boundary, dates and measure grain, not future source_ts', () => {
  assert.equal(expectedLoadDates(Date.parse('2026-11-23T01:14:00Z')).at(-1), 20261122);
  assert.equal(expectedLoadDates(Date.parse('2026-11-23T01:15:00Z')).at(-1), 20261123);
  const load: Loads = {
    checkedAt: new Date(now).toISOString(), duplicateKeys: 0, tables: [],
    daily: expectedLoadDates(now).map(date_key => ({ date_key, row_count: 85 })),
    sources: Object.entries(expectedPerDay).map(([measure_id, count]) => ({
      measure_id, row_count: count * 30, loaded_days: 30, null_values: 0,
      synthetic_source_ts: '2026-11-24T00:00:00Z',
    })),
  };
  assert.equal(loadHealth(load, now).tone, 'good');
  load.daily[0].row_count = 84;
  assert.equal(loadHealth(load, now).tone, 'bad');
  load.daily[0].row_count = 85;
  load.duplicateKeys = 1;
  assert.equal(loadHealth(load, now).tone, 'bad');
  load.duplicateKeys = 0;
  load.sources.pop();
  assert.equal(loadHealth(load, now).tone, 'bad');
});

test('expired schedules and failed latest jobs cannot appear healthy', () => {
  assert.equal(scheduleHealth([{ id: 'a', enabled: true, configuration: {
    endDateTime: '2026-11-22T00:00:00Z', localTimeZoneId: 'SE Asia Standard Time',
  } }], now).label, 'Expired');
  const job = latestJob([
    { id: 'a', status: 'Completed', startTimeUtc: '2026-11-22T00:00:00Z', endTimeUtc: null },
    { id: 'b', status: 'Failed', startTimeUtc: '2026-11-23T00:00:00Z', endTimeUtc: null },
  ]);
  assert.equal(jobHealth(job).tone, 'bad');
  assert.equal(jobHealth(null).tone, 'unknown');
});

test('DAX reuses model measures with common filters and rejects invalid input', () => {
  const queries = modelQueries({ start: '2026-11-01', end: '2026-11-23', shift: 'B' });
  for (const query of Object.values(queries)) {
    assert.match(query, /dim_date\[date_key\] >= 20261101/);
    assert.match(query, /TREATAS\(\{"B"\}, dim_shift\[shift_id\]\)/);
    assert.match(query, /\[Ethylene Yield %\]/);
  }
  assert.throws(() => modelQueries({ start: '2026-02-30', end: '2026-11-23', shift: 'ALL' }));
  assert.throws(() => modelQueries({ start: '2026-11-23', end: '2026-11-01', shift: 'ALL' }));
  assert.throws(() => modelQueries({ start: '2026-11-01', end: '2026-11-23', shift: 'A"}' }));
});
