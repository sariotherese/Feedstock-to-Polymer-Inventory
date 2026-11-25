# Feedstock-to-Polymer Inventory & Yield

Microsoft Fabric demo built from `LSP_Fabric_Demo_Build_Spec.pdf`.
**All production, inventory, laboratory and telemetry data is synthetic, not LSP operational data.**

## Open the deployed demo

Workspace: **smec-dataplatform-e5**, folder
**LSP - SCG Chemicals / Feedstock to Polymer Inventory**.
The existing folder linked in the request was used; no duplicate typo-named folder was created.

- [Workspace folder](https://app.fabric.microsoft.com/groups/6d6350e8-6f22-4a8b-b06a-eb4a3b68dd23/list?experience=fabric-developer&subfolderId=108886)
- [Five-page Power BI report](https://app.fabric.microsoft.com/groups/6d6350e8-6f22-4a8b-b06a-eb4a3b68dd23/reports/e3a9316e-842a-40f2-867a-0f7e17b48fad/overview)
- [Live tank dashboard](https://app.fabric.microsoft.com/groups/6d6350e8-6f22-4a8b-b06a-eb4a3b68dd23/kustodashboards/e73302d3-e8f3-4b84-aaad-5aae8dda8b15)
- [Activator rules](https://app.fabric.microsoft.com/groups/6d6350e8-6f22-4a8b-b06a-eb4a3b68dd23/reflexes/4549bc2a-967f-4dff-80af-71b5774bda1b)
- [Rayfin operations control tower](https://soft-vine-b99f07e159-westus.webapp.fabricapps.net)

### Deployed items

| Name | Type | Item ID |
| --- | --- | --- |
| lh_lsp_plant | Lakehouse | 5ba6b711-2d7f-4b59-a57d-2e1f545439a1 |
| eh_lsp_plant | Eventhouse | d8488b65-21b8-45c7-afe7-d46267f0b2f1 |
| kqldb_lsp_plant | KQL database | 13e252db-4acb-4794-adee-17c12386f200 |
| nb_01_generate_sample_data | Notebook | 9b4394a4-6357-4701-9698-d64c0c69aede |
| sm_lsp_feedstock | Direct Lake semantic model | f265d0ef-7fab-45c3-b640-384cb3608101 |
| rpt_lsp_feedstock | Power BI report | e3a9316e-842a-40f2-867a-0f7e17b48fad |
| es_tank_readings | Eventstream | bf9063ce-ecfc-4f7d-ab98-efce7775cce6 |
| nb_02_stream_simulator | Notebook | 94decbd2-0715-423d-aaf7-fd64b7eef13b |
| rtd_lsp_plant | Real-Time Dashboard | e73302d3-e8f3-4b84-aaad-5aae8dda8b15 |
| pl_daily_refresh | Data pipeline | 48bd9310-d378-4199-87f5-ad10ede833de |
| act_lsp_alerts | Activator / Reflex | 4549bc2a-967f-4dff-80af-71b5774bda1b |
| app_lsp_control_tower | Fabric App / Rayfin | 8b9fa8d8-fded-4eb0-9382-bf9d2c9bce78 |

Fabric also creates the Lakehouse SQL analytics endpoint and an empty default KQL database
named `eh_lsp_plant`. Live telemetry goes to **kqldb_lsp_plant**, not that default database.

## Rayfin operations control tower

The [protected Fabric-hosted application](https://soft-vine-b99f07e159-westus.webapp.fabricapps.net)
is saved in the same workspace folder as the original eleven demo artifacts.
Sign in using Fabric SSO. There is no separate application database, copied business
dataset, embedded credential, or anonymous data API.

### What the operations manager can do

- Follow separate batch and IoT flow diagrams. Select a stage for its evidence,
  failure-isolation steps, and a link to the **existing** Fabric artifact.
- Monitor the four expected tank IDs, latest level/temperature/pressure, heartbeat age,
  15-minute observed counts and ingestion timestamps. Select a tank for details.
- Inspect 29 fully observed minute buckets against the expected four events/minute.
  The current minute and the clipped first minute are excluded from completeness comparisons.
- Search historical source labels, show exceptions, inspect the six existing table
  counts, and check the rolling contract: 30 dates, 85 facts/day, eight measure groups,
  no null measures and no duplicate compound fact keys.
- Select a business-date coverage cell to investigate that day in the model KPIs.
- Inspect actual pipeline/simulator run status, failures, timestamps and refresh
  schedule expiry. Recovery playbooks explain safe retries and their overwrite/capacity impact.
- Filter business KPIs and trends by date and shift, switch yield/purity/mass-gap
  trends, or open the original five-page Power BI report.

All six KPI cards, historical trends and five supporting totals call the existing
`sm_lsp_feedstock` **DAX measures**, through the delegated semantic-model connector.
Snapshot, shift-C reconciliation and seven-day-cover semantics are unchanged.
Tower filters affect only its business-model queries, not the live IoT window, the
30-day load contract, or the separate native report's slicers.

### Evidence and operating limits

- The application refreshes every 60 seconds while visible; manual refresh is also
  available. Every evidence section has a check time and fails independently.
  Unavailable evidence is displayed explicitly, never replaced with zeros or mock success.
- A device is delayed after 90 seconds, stale after 180 seconds, and has clock skew
  if its timestamp is over 60 seconds ahead. No observation in the 24-hour lookup
  window is a missing heartbeat. Last-observed values are **not** presented as current
  measurements when stale.
- Eventstream topology is configuration evidence only. Eventhouse queries establish
  that readings reached the destination. Expected cadence is not a producer sent
  counter: real packet loss and upstream completeness cannot be proven without
  producer acknowledgements/sequence IDs.
- Historian, DCS, LIMS, MES, warehouse and ERP are **illustrative source labels**.
  One notebook generates their historical data. SQL counts prove that generated
  data loaded, not that enterprise systems delivered it. Synthetic `source_ts` can
  be in the future and is not used as an ingestion heartbeat.
- The expected daily load advances at **08:15 Vietnam time**, allowing one hour
  after the 07:15 pipeline schedule. The simulator is a bounded 60-minute job,
  not a permanently running service. Check active jobs before starting another run.
- A successful model query proves query access, not refresh freshness. Business
  anomalies and delivery failures are separate: do not retry a successful pipeline
  simply to remove a seeded business exception.
- Recovery actions open native Fabric and use the operator's native permissions.
  The tower does not automatically retry, modify configuration or control equipment.
  Activator was deployed stopped with no recipients; its live rule state is not
  polled by this app.

### Permissions and implementation

Grant app users access to the Fabric app and **Read + Build** on the existing semantic
model. Share the application only with operators authorized to see this plant's data.
The read-only monitoring Functions use the **app item owner's** resource permissions,
not the viewer's delegated permissions. Their endpoints, queries and target item IDs
are fixed server-side; callers cannot supply arbitrary queries or resource URLs.

- Frontend: [React control tower](control-tower/main.tsx), typed Rayfin 2.0.1 client,
  Fabric brokered SSO, Recharts and responsive layouts.
- Backend: [monitoring Functions](rayfin/functions/src/function_app.ts) and
  [fixed diagnostic queries](rayfin/functions/src/queries.ts).
- Lakehouse SQL uses the SQL analytics endpoint catalog
  `64862655-d4a4-4ca6-b7a1-c9f1457c6a02`, **not** the parent Lakehouse GUID.
- Eventhouse queries use the platform's built-in `Sql` audience, which this Fabric
  Kusto endpoint accepts. This was checked against the real endpoint and deployed
  runtime. The custom-audience route is not used: it requires a separate item identity.
- SQL/Kusto/Fabric resource tokens remain server-side. Only the public Rayfin
  publishable key and app coordinates are in the frontend.

### Build, test and redeploy

Use **Node.js 24 LTS** (Rayfin 2.0.1 supports 20/22/24, not 26). From the repository
root, in PowerShell:

```powershell
npm ci
npm --prefix rayfin\functions ci
npx rayfin functions init
npm test
npm run build
npx rayfin login --tenant 941463a9-4ea9-4652-9c4a-62f8016b7834
npx rayfin up --workspace-id 6d6350e8-6f22-4a8b-b06a-eb4a3b68dd23 --item-name app_lsp_control_tower --yes
npx rayfin up status
```

`functions init` preserves the implementation and regenerates the frontend function
types. Never edit generated function or connector schemas manually. Deployment
coordinates are generated in ignored local environment/registry files. On a fresh
clone, `rayfin up` provisions/resolves the backend coordinates before building the UI;
run the standalone frontend build after those coordinates exist. Keep encrypted CLI
token storage enabled and serialize CLI deployments rather than running concurrent
cache-writing commands. Functions deployments have a two-minute cooldown.

Focused tests cover stale/missing/future heartbeats, incomplete edge minutes,
Vietnam load-date boundaries, failed runs, expired schedules, load-contract violations
and validated shared DAX filters. For acceptance, also sign in to the **deployed**
app, verify all four evidence paths, select a date with a seeded mass-gap anomaly,
inspect a tank and recovery guide, and verify unavailable evidence cannot appear healthy.

## Before presenting

1. Open the report. Its pages are Plant Overview; Feedstock & Days of Cover; Yield;
   Mass Balance & Inventory Accuracy; Finished Goods.
2. In `nb_02_stream_simulator`, choose **Run all** about five minutes before the live section.
   First confirm no previous simulator run is still active. Default runtime is **60 minutes**,
   sending one event per tank per minute for four tanks. The temperature anomaly is off.
   The initial deployment's live run is temporary, not a continuously running IoT service.
3. Open the live dashboard and enable live refresh if paused. Its main page has four tiles:
   latest levels, 24-hour level trends, temperature trends, and tanks below minimum level.
   The separate **Alert setup** page exposes `PlantSignals()` for native Activator source management.
4. Use the date slicers to show the injected historical anomalies. Dates move when
   the generator runs; anomalies are always days 25-28 of the 30-day window.
5. To demonstrate delivery of an alert, complete the recipient setup below first.
   Do not present an historical chart anomaly as a notification that was actually sent.

### Alert delivery: deliberately requires configuration

All four rules are persisted with their conditions and actions, but **stopped with empty
recipient lists**. Notification delivery has not been tested or enabled.
Activator will show "Recipient is required" until real recipients are selected.

| Rule | Condition | Intended action |
| --- | --- | --- |
| Low days of cover | Days of Cover < 15 | Teams: Supply & Operations |
| Yield drop | Relative yield loss > 0.04 against preceding 7 daily yields, sustained 6 hours | Teams: Process Engineering |
| Mass balance gap | Mass Balance Gap > 0.02 | Email: Operations & Finance |
| Tank temperature | Fresh ethane tank temperature > -85 C | Teams: Control Room |

To enable:

1. Open Activator, expand **LSP plant alerts / LSP Plant**, and select each rule.
2. In **Definition / Action**, choose the approved recipients. The audience names above
   are business roles, not pre-existing Teams channels or email addresses.
   Use the appropriate Teams channel action if the demo needs channel delivery.
3. Save without starting; use **Send me a test action** only after confirming the destination.
4. Inspect **Plant signal events / Manage source**: status should be **Connected**, query
   `PlantSignals()`, frequency one minute. It uses `reading_ts` as event time.
5. Start only the rules needed for the demo. Check Live feed and History for actual actions.
   Stop rules after the demonstration to avoid repeated synthetic alerts.

`PlantSignals()` reads the latest historical shift-date, not a replay of earlier anomalies.
Its read-only Delta external table `PlantHistory` references the existing narrow fact table;
it does not create another Lakehouse/gold table. Temperature uses only ethane readings
from the last five minutes and is null when that telemetry is stale.

**Specification caveats:** a 4% reduction in the ethane-origin ethylene yield produces only
about a 3.4% reduction in the overall ethylene yield because other feeds also contribute.
The generator preserves the specified 4% ethane-origin change and the rule preserves the
specified 4% overall threshold. Therefore the historical purity anomaly does not guarantee
a yield alert. Historical dates also are not replayed for six hours. Show the real saved rule,
or agree a separate controlled scenario before promising a live yield notification.
The optional simulator setting `inject_temperature_alert = True` can demonstrate the
temperature rule with approved recipients; it is never enabled by default.

The storyline's Copilot / Data Agent "What changed?" step depends on tenant/capacity
availability and separate setup. No Data Agent was created or Copilot answer verified.
The five-page report does show the lab-purity/yield correlation without that dependency.

## Refresh and cost controls

- `pl_daily_refresh` successfully runs `nb_01_generate_sample_data`, then waits for a
  transactional refresh of `sm_lsp_feedstock`.
- An enabled daily schedule runs at **07:15 Vietnam time** (`SE Asia Standard Time`, UTC+7).
  Its initial expiry is **2026-12-23**, 30 days after deployment. Extend it intentionally
  if needed, or disable it from the pipeline schedule settings after the demo.
- Model refresh reuses the workspace's existing **PowerBIDatasets admin** connection.
  Keep that connection authorized; no credentials were copied into the repository.
- Generating data overwrites all six demo Delta tables with a newly anchored 30-day window.
  It does not update production systems. Do not repoint these names at operational tables.
- Eventhouse, Eventstream and the connected Activator source can consume capacity
  independently of the notebook schedule, even with notification rules stopped.
  Stop the simulator and rules, reduce the source's query frequency in **Manage source**,
  and review Fabric Capacity Metrics. Remove unneeded demo items deliberately when finished.
  No shared workspace, capacity, or unrelated item is automatically stopped or deleted.

## Data/model decisions

- Exactly one fact (`fact_plant_data`) and five dimensions (`dim_date`, `dim_shift`,
  `dim_asset`, `dim_material`, `dim_measure`). Seed 42; 30 dates; 85 facts/day; 2,550 facts.
- Fact grain: `(date_key, shift_id, asset_id, material_id, measure_id)`, with `value`
  and `source_ts`. Stock snapshots are not additive over time.
- Shift C's date key is the shift-starting day; its end timestamp is 06:00 the following
  morning. The current day's future end-of-shift values are explicitly synthetic.
- Five active, many-to-one, single-direction relationships; marked date table;
  hidden fact value and keys; all six tables use Direct Lake.
- Measures live in `dim_measure`: a measure named `Value` cannot share the fact table
  with its case-insensitively conflicting `value` column. The required fact schema is unchanged.
- Raw purity is 97.5-99.0 (about 94 on anomaly days). The DAX measure divides by 100
  before percent formatting so the chart displays 98%, not 9,800%.
- Latest-snapshot measures use the latest timestamp in context; sensor/book comparison
  uses the latest date's shift C. Days of Cover uses seven-day average daily ethane feed.
- The opening 60,000-ton stock is about 22 days **before consumption**.
  The first day's closing cover is about 20.9 days; latest cover is about 10.06 days.
  This is not a current all-green 22-day snapshot.

At initial verification on 2026-11-23, the historical window was 2026-10-25 to 2026-11-23:
purity/yield drop on Nov 18-19, exactly 3% mass gap on Nov 20, and +3% ethane book-stock
discrepancy on Nov 21. Daily rolling refresh moves these dates forward.

## Source and redeployment

- [Data generator](plant_data.py) and [notebook definitions](notebook_definitions.py)
- [Direct Lake model and DAX](semantic_model.py), [report](report_definition.py)
- [Eventstream/dashboard](realtime_definitions.py), [stream producer](stream_simulator.py)
- [Pipeline](pipeline_definition.py), [alert rules and KQL](alert_definitions.py)
- [Cloud validation](validate_demo.py), [local tests](tests)

Prerequisites: Python 3.11+, Azure CLI, Fabric capacity and workspace write permissions;
access to the existing semantic-model refresh connection. Authentication uses the
user's Azure CLI SSO cache; endpoint keys are retrieved only in notebook memory.

```powershell
python -m pip install -r requirements.txt
az login --tenant MngEnvMCAP671226.onmicrosoft.com --allow-no-subscriptions --scope https://api.fabric.microsoft.com/.default --output none

python deploy.py foundation
python deploy.py generate
python deploy.py analytics
python deploy.py realtime
python deploy.py alerts
python deploy.py pipeline
python deploy.py stream
```

The commands target only the workspace/folder IDs in [fabric_client.py](fabric_client.py).
Existing exact-name/type matches outside the target folder are refused.
Rerunning definition stages **replaces demo definitions**, including custom report edits
and alert recipients/settings. Back up intentional edits before redeploying.
Do not run `stream` twice concurrently.

Non-secret deployment IDs, job locations and validation results are stored in the ignored
`.fabric` directory. A fresh checkout should follow the full command order above to
reconstruct that local state.

### Verification

```powershell
python -m unittest discover -s tests -v
python -m compileall -q .
python validate_demo.py
```

Cloud validation requires at least two fresh readings per tank, the populated local
deployment state, and a completed pipeline run. It checks:

- all 11 named items in the target folder and exactly six Delta tables;
- Direct Lake partitions and five single-direction relationships;
- 2,550 facts and all 30 days of DAX KPIs against deterministic ground truth;
- five report pages, four executable dashboard queries, four live tanks and one-minute cadence;
- KQL alert KPIs against DAX, all four persisted thresholds, the six-hour yield duration,
  empty recipients and stopped rules;
- successful pipeline execution and the enabled 07:15 schedule.

All five report pages and all four live dashboard tiles were also opened in Fabric.
Alert condition/duration rendering was inspected in Activator; actual notification
delivery remains a recipient-dependent handover step.
