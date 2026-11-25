export const DEVICES = `
let expected=datatable(tank_id:string,material:string)
['T-ETH-01','ETHANE','T-ETH-02','ETHANE','T-PRO-01','PROPANE','T-NAP-01','NAPHTHA'];
let recent=TankReadings | where reading_ts > ago(24h) and reading_ts < now()+5m;
let lastReadings=recent | summarize arg_max(reading_ts, *) by tank_id
| project tank_id,reading_ts,level_tons,temperature_c,pressure_barg;
let counts=recent | where reading_ts > ago(15m)
| summarize events15m=count(),last_ingested=max(ingestion_time()) by tank_id;
expected | join kind=leftouter (lastReadings) on tank_id
| join kind=leftouter (counts) on tank_id
| project tank_id,material,reading_ts,level_tons,temperature_c,pressure_barg,
events15m=coalesce(events15m,long(0)),last_ingested
| order by tank_id asc`;

export const TELEMETRY_TREND = `
let timeBuckets=range minute from bin(ago(30m),1m) to bin(now(),1m) step 1m;
let counts=TankReadings | where reading_ts between (ago(30m)..now())
| summarize events=count(),devices=dcount(tank_id) by minute=bin(reading_ts,1m);
timeBuckets | join kind=leftouter (counts) on minute
| project minute,events=coalesce(events,long(0)),devices=coalesce(devices,long(0))
| order by minute asc`;

export const INVALID_READINGS = `
TankReadings | where ingestion_time() > ago(1h)
| where isempty(tank_id) or isnull(reading_ts) or reading_ts > now()+5m
or isnull(level_tons) or level_tons < 0 or isnull(temperature_c) or isnull(pressure_barg)
| count`;

export const LOAD_SOURCES = `
SELECT m.source_system,m.measure_id,m.measure_name,
COUNT_BIG(f.measure_id) AS row_count,COUNT(DISTINCT f.date_key) AS loaded_days,
MAX(f.date_key) AS latest_date_key,CONVERT(varchar(33),MAX(f.source_ts),126) AS synthetic_source_ts,
SUM(CASE WHEN f.measure_id IS NOT NULL AND f.value IS NULL THEN 1 ELSE 0 END) AS null_values
FROM dbo.dim_measure m LEFT JOIN dbo.fact_plant_data f ON m.measure_id=f.measure_id
GROUP BY m.source_system,m.measure_id,m.measure_name ORDER BY m.measure_id`;

export const TABLE_COUNTS = `
SELECT 'fact_plant_data' AS table_name,COUNT_BIG(*) AS row_count FROM dbo.fact_plant_data
UNION ALL SELECT 'dim_date',COUNT_BIG(*) FROM dbo.dim_date
UNION ALL SELECT 'dim_shift',COUNT_BIG(*) FROM dbo.dim_shift
UNION ALL SELECT 'dim_asset',COUNT_BIG(*) FROM dbo.dim_asset
UNION ALL SELECT 'dim_material',COUNT_BIG(*) FROM dbo.dim_material
UNION ALL SELECT 'dim_measure',COUNT_BIG(*) FROM dbo.dim_measure`;

export const DAILY_LOADS = `
SELECT date_key,COUNT_BIG(*) AS row_count FROM dbo.fact_plant_data
GROUP BY date_key ORDER BY date_key`;

export const DUPLICATES = `
SELECT COUNT_BIG(*) AS duplicate_keys FROM (
SELECT date_key,shift_id,asset_id,material_id,measure_id FROM dbo.fact_plant_data
GROUP BY date_key,shift_id,asset_id,material_id,measure_id HAVING COUNT(*)>1
) d`;
