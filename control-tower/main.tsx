import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { createRoot } from 'react-dom/client';
import { initEmbeddedAuth, ensureSignedInWithFabric } from '@microsoft/rayfin-auth-provider-fabric';
import { Activity, ArrowDownToLine, ArrowRight, Bell, Boxes, ChartNoAxesCombined,
  Check, ChevronRight, CircleHelp, Database, ExternalLink, Factory, Gauge, GitBranch,
  Layers, LoaderCircle, Radio, RefreshCw, Search, ShieldCheck, TriangleAlert, X } from 'lucide-react';
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { connect, modelRows, type Connection } from './client';
import { completedMinutes, dateInput, deviceHealth, expectedLoadDates, expectedPerDay,
  jobHealth, latestJob, loadHealth, modelQueries, number, scheduleHealth, timestamp,
  type Filters, type Signal, type Tone } from './health';
import type { Job, Row } from '../rayfin/functions/src/contracts';
import './styles.css';

const group = 'https://app.fabric.microsoft.com/groups/6d6350e8-6f22-4a8b-b06a-eb4a3b68dd23';
const links = {
  simulator: `${group}/synapsenotebooks/94decbd2-0715-423d-aaf7-fd64b7eef13b`,
  eventstream: `${group}/eventstreams/bf9063ce-ecfc-4f7d-ab98-efce7775cce6`,
  lakehouse: `${group}/lakehouses/5ba6b711-2d7f-4b59-a57d-2e1f545439a1`,
  pipeline: `${group}/pipelines/48bd9310-d378-4199-87f5-ad10ede833de`,
  model: `${group}/datasets/f265d0ef-7fab-45c3-b640-384cb3608101`,
  report: `${group}/reports/e3a9316e-842a-40f2-867a-0f7e17b48fad/overview`,
  realtime: `${group}/kustodashboards/e73302d3-e8f3-4b84-aaad-5aae8dda8b15`,
  alerts: `${group}/reflexes/4549bc2a-967f-4dff-80af-71b5774bda1b`,
};
type Guide = keyof typeof links;
const guides: Record<Guide, { title: string; description: string; steps: string[]; caution: string }> = {
  simulator: {
    title: 'Restore the IoT heartbeat',
    description: 'The demo producer sends one reading per minute for each of the four tanks, for 60 minutes.',
    steps: [
      'Check the latest simulator run below. If InProgress or queued, do not launch another producer.',
      'If Completed, the 60-minute demonstration has ended normally. Open nb_02_stream_simulator and run it once for another live demonstration.',
      'If Failed, inspect the notebook error and Eventstream connection before retrying.',
      'After starting, wait up to 3 minutes, refresh this tower, and confirm all four heartbeats and completed-minute event counts.',
    ],
    caution: 'Starting a notebook consumes Fabric capacity. Overlapping producers create duplicate events. The tower does not automatically restart jobs.',
  },
  eventstream: {
    title: 'Locate an Eventstream bottleneck',
    description: 'Topology proves configuration, not successful delivery. Eventhouse heartbeats prove events reached the destination.',
    steps: [
      'Confirm the simulator is currently running and has no send errors.',
      'Open es_tank_readings. Inspect source input and destination output metrics, errors and the live data preview.',
      'Input without output points to a transformation or destination problem. No input points to the producer or source connection.',
      'Compare the same completed time window. Expected cadence is 4 events/minute, not a measured sent count.',
    ],
    caution: 'Without producer acknowledgements or sequence IDs, this demo cannot calculate true packet loss or prove upstream completeness.',
  },
  lakehouse: {
    title: 'Investigate an incomplete load',
    description: 'The Lakehouse check reads the existing six Delta tables through their SQL analytics endpoint.',
    steps: [
      'Inspect the date and source grids for missing days, unexpected counts, null values or duplicate fact keys.',
      'Check pl_daily_refresh and its generator notebook activity for the first failed step.',
      'If the pipeline completed but SQL counts are behind, check SQL endpoint metadata synchronization before rerunning.',
      'After resolving the cause, use Fabric run details to perform a controlled retry, then refresh both the model KPIs and load evidence.',
    ],
    caution: 'The demo generator overwrites a rolling 30-day dataset. A pipeline success alone does not prove upstream historian, lab, MES or ERP delivery.',
  },
  pipeline: {
    title: 'Recover the scheduled refresh',
    description: 'pl_daily_refresh orchestrates the synthetic history and semantic-model refresh.',
    steps: [
      'Review the latest run and its activity details, including the failure message. Avoid retrying while a run is active.',
      'Resolve the failing notebook, capacity or model permission issue in Fabric.',
      'If appropriate, rerun the pipeline once. This regenerates the rolling demo history rather than replaying actual enterprise source systems.',
      'Verify 30 expected dates with 85 facts/day and inspect the refreshed model KPIs. Confirm the schedule is enabled and has not expired.',
    ],
    caution: 'The schedule is 07:15 Vietnam time and has a finite end date. Retries consume capacity and replace generated history.',
  },
  model: {
    title: 'Understand the governed KPIs',
    description: 'Every business KPI and historical trend is queried from the existing sm_lsp_feedstock model through a delegated Rayfin connector.',
    steps: [
      'Viewers need Read and Build permissions on the semantic model; a model access error is shown as unavailable, never as zero.',
      'Date and shift controls apply to all model queries, but not to live IoT or the full 30-day load contract.',
      'The original DAX snapshot semantics are preserved: end-of-day book/sensor comparisons use shift C; stocks are not summed over dates.',
      'Days of Cover uses seven-day average ethane feed. Empty filtered periods return blanks. Open the five-page report for deeper analysis.',
    ],
    caution: 'These are demo-data business KPIs, not streaming tank measurements. A successful DAX query proves model access, not refresh freshness.',
  },
  report: {
    title: 'Investigate business impact in Power BI',
    description: 'The tower reuses the report model rather than maintaining a second implementation of its KPIs.',
    steps: [
      'Open rpt_lsp_feedstock for Plant Overview, Feedstock & Days of Cover, Yield, Mass Balance and Finished Goods analysis.',
      'Reapply the desired report slicers; tower filters are local to the model queries in this app.',
      'Low Days of Cover (<15 days) calls for supply planning. A mass gap >2% calls for reconciliation.',
      'Inspect the seeded purity/yield and book-stock anomalies before attributing a change to an ingestion failure.',
    ],
    caution: 'Business exceptions and data-delivery failures are different. Do not retry a successful load to remove an intentional business anomaly.',
  },
  realtime: {
    title: 'Drill into live tank telemetry',
    description: 'The existing real-time dashboard shows the same Eventhouse TankReadings data.',
    steps: [
      'Check the timestamp before interpreting level, temperature or pressure. A retained last value is not a current reading.',
      'Use the dashboard time controls to compare all four tank IDs.',
      'For fresh ethane tanks above -85 C, follow the demonstration alert workflow; stale telemetry must not be interpreted as safe.',
      'Compare ingestion time and device time in this tower to investigate latency or clock skew.',
    ],
    caution: 'The live stream is simulated and must not be used for real plant safety decisions.',
  },
  alerts: {
    title: 'Review alert readiness',
    description: 'The original four Activator rules were deployed stopped, with no recipients. Live rule state is not polled by this tower.',
    steps: [
      'Open act_lsp_alerts and review each saved rule and its real source connection.',
      'Configure an appropriate Teams/email recipient and start a rule only when a delivery demonstration is intended.',
      'Yield-loss notification requires >4% relative loss sustained for six hours; the seeded history does not guarantee a notification.',
      'Stop the rules after the demonstration and confirm recipients and capacity usage.',
    ],
    caution: 'No alert delivery or automatic operational recovery is currently enabled by this tower.',
  },
};

function message(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
function fmt(value: number | null, digits = 0): string {
  return value === null ? '--' : value.toLocaleString('en-US', { maximumFractionDigits: digits, minimumFractionDigits: digits });
}
function time(value: unknown): string {
  const parsed = timestamp(value);
  return parsed === null ? 'Not observed' : new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Ho_Chi_Minh', month: 'short', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  }).format(parsed);
}
function age(value: unknown, now: number): string {
  const parsed = timestamp(value);
  if (parsed === null) return 'No reading';
  const seconds = Math.round((now - parsed) / 1000);
  if (seconds < -60) return `${Math.abs(seconds)}s ahead`;
  if (seconds < 60) return `${Math.max(0, seconds)}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  return `${fmt(seconds / 3600, 1)}h ago`;
}
function Badge({ tone, children }: { tone: Tone; children: ReactNode }) {
  return <span className={`badge ${tone}`}><span className="dot" />{children}</span>;
}
function NativeLink({ to, children, className = '' }: { to: Guide; children: ReactNode; className?: string }) {
  return <a className={`native-link ${className}`} href={links[to]} target="_blank" rel="noopener noreferrer">{children}<ExternalLink size={13} /></a>;
}
interface Resource<T> { data: T | null; loading: boolean; error: string | null }
function useResource<T>(load: () => Promise<T>, tick: number): Resource<T> {
  const [state, set] = useState<Resource<T>>({ data: null, loading: true, error: null });
  useEffect(() => {
    let active = true;
    set(previous => ({ ...previous, loading: true, error: null }));
    load().then(data => { if (active) set({ data, loading: false, error: null }); })
      .catch(error => { if (active) set({ data: null, loading: false, error: message(error) }); });
    return () => { active = false; };
  }, [load, tick]);
  return state;
}
function Evidence<T>({ resource, children }: { resource: Resource<T>; children: ReactNode }) {
  if (resource.error) return <div className="error-box" role="alert"><TriangleAlert size={18} /><div><strong>Evidence unavailable</strong><p>{resource.error}</p><small>Check source access and retry. This is not a healthy or zero-data result.</small></div></div>;
  if (!resource.data) return <div className="loading"><LoaderCircle size={20} className="spin" />Reading Fabric evidence...</div>;
  return <div aria-busy={resource.loading}>{resource.loading && <div className="refresh-note">Refreshing; previous snapshot remains visible.</div>}{children}</div>;
}
function SectionHead({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return <header className="section-head"><div><span className="eyebrow">{eyebrow}</span><h2>{title}</h2></div><div className="section-actions">{children}</div></header>;
}
function Panel({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`panel ${className}`}>{children}</div>;
}
function RunHistory({ title, jobs, guide }: { title: string; jobs: Job[]; guide: Guide }) {
  const current = jobHealth(latestJob(jobs));
  return <div><div className="row spread"><h3>{title}</h3><Badge tone={current.tone}>{current.label}</Badge></div>
    {!jobs.length && <p className="muted">No run history available.</p>}
    {jobs.slice(0, 5).map(job => <div className="job" key={job.id}>
      <span className={`job-icon ${jobHealth(job).tone}`}><GitBranch size={16} /></span>
      <div className="job-body"><strong>{job.status}</strong><small>{time(job.startTimeUtc)} to {job.endTimeUtc ? time(job.endTimeUtc) : 'not ended'}</small>
        <code title={job.id}>{job.id}</code>{job.failureReason?.message && <p className="failure">{job.failureReason.message}</p>}</div>
    </div>)}
    <NativeLink to={guide}>Open run details in Fabric</NativeLink>
  </div>;
}

function ControlTower({ connection }: { connection: Connection }) {
  const { client } = connection;
  const [tick, setTick] = useState(0);
  const [now, setNow] = useState(Date.now);
  const [auto, setAuto] = useState(true);
  const [guide, setGuide] = useState<Guide | null>(null);
  const [selectedDevice, selectDevice] = useState<Row | null>(null);
  const [search, setSearch] = useState('');
  const [onlyExceptions, setOnlyExceptions] = useState(false);
  const [trendMetric, setTrendMetric] = useState<'Yield' | 'Purity' | 'Gap'>('Yield');
  const [filters, setFilters] = useState<Filters>(() => ({
    start: dateInput(Date.now() - 29 * 86400000), end: dateInput(Date.now()), shift: 'ALL',
  }));
  const [draft, setDraft] = useState(filters);
  const [filterError, setFilterError] = useState('');
  const dialog = useRef<HTMLDialogElement>(null);
  const readTelemetry = useCallback(() => client.functions.getTelemetry.invoke(), [client]);
  const readLoads = useCallback(() => client.functions.getLoads.invoke(), [client]);
  const readFabric = useCallback(() => client.functions.getFabricHealth.invoke(), [client]);
  const readModel = useCallback(async () => {
    const queries = modelQueries(filters);
    const query = async (text: string) => {
      const result = await client.connectors.plantmodel.executeQuery({ query: text, resultSetRowCountLimit: 1000 });
      if (result.status !== 'success') throw new Error(`${result.error.category}: ${result.error.message}${result.error.recoveryHint ? ` ${result.error.recoveryHint}` : ''}`);
      return modelRows(result.table);
    };
    const [kpis, trend] = await Promise.all([query(queries.kpis), query(queries.trend)]);
    if (kpis.length !== 1) throw new Error('The model did not return the expected KPI row.');
    return { checkedAt: new Date().toISOString(), kpis: kpis[0], trend };
  }, [client, filters]);
  const telemetry = useResource(readTelemetry, tick);
  const loads = useResource(readLoads, tick);
  const fabric = useResource(readFabric, tick);
  const model = useResource(readModel, tick);

  useEffect(() => {
    const clock = setInterval(() => setNow(Date.now()), 10000);
    const refresh = setInterval(() => {
      if (auto && document.visibilityState === 'visible') setTick(value => value + 1);
    }, 60000);
    return () => { clearInterval(clock); clearInterval(refresh); };
  }, [auto]);
  useEffect(() => {
    if (guide || selectedDevice) dialog.current?.showModal();
    else dialog.current?.close();
  }, [guide, selectedDevice]);

  const t = telemetry.data;
  const f = fabric.data;
  const l = loads.data;
  const m = model.data;
  const loadSignal = l ? loadHealth(l, now) : { tone: 'unknown' as const, label: 'Unavailable', detail: 'Load evidence is not available.' };
  const pipelineSignal = f ? jobHealth(latestJob(f.pipeline)) : { tone: 'unknown' as const, label: 'Unavailable', detail: '' };
  const active = t?.devices.filter(device => deviceHealth(device, now).tone === 'good').length;
  const stale = t?.devices.filter(device => deviceHealth(device, now).tone !== 'good').length;
  const complete = t ? completedMinutes(t.trend, now) : [];
  const lastMinute = complete.at(-1);
  const thinMinutes = complete.filter(row => (number(row, 'devices') ?? 0) < 4).length;
  const busy = [telemetry, loads, fabric, model].some(resource => resource.loading);
  const unavailable = [telemetry, loads, fabric, model].filter(resource => resource.error).length;
  const latestPipeline = f ? latestJob(f.pipeline) : null;
  const schedule = f ? scheduleHealth(f.schedules, now) : null;
  const pending = !t || !l || !f || !m;
  const needsAttention = !!stale || loadSignal.tone === 'bad' ||
    pipelineSignal.tone === 'bad' || pipelineSignal.tone === 'warn' ||
    schedule?.tone === 'bad' || schedule?.tone === 'warn' || !!t?.invalidReadings;
  const overall: Signal = unavailable ? { tone: 'unknown', label: 'Partial visibility', detail: `${unavailable} evidence source(s) unavailable. Resolve access before judging health.` } :
    needsAttention ? { tone: 'warn', label: 'Attention required', detail: 'Delivery or quality checks need investigation. Use the evidence and recovery guides below.' } :
      pending || pipelineSignal.tone === 'unknown' ? { tone: 'unknown', label: 'Incomplete evidence', detail: 'A complete set of Fabric load and run evidence is not yet available.' } :
        { tone: 'good', label: 'Checks passing', detail: 'Monitored Fabric checks pass. External source completeness is not independently measured.' };
  const sourceRows = l?.sources.filter(row => {
    const expected = expectedPerDay[String(row.measure_id)] * 30;
    const exception = number(row, 'row_count') !== expected || number(row, 'loaded_days') !== 30 || number(row, 'null_values') !== 0;
    return (!onlyExceptions || exception) && `${row.source_system} ${row.measure_name}`.toLowerCase().includes(search.toLowerCase());
  }) ?? [];
  const kpis = [
    { name: 'Days of Cover', suffix: 'days', icon: Boxes, note: 'Supply trigger <15 days', tone: (v: number) => v < 15 ? 'warn' : 'good' },
    { name: 'Ethylene Yield %', suffix: '%', icon: Factory, note: 'Ethylene output / total feed', tone: () => 'unknown' },
    { name: 'Mass Balance Gap %', suffix: '%', icon: GitBranch, note: 'Reconcile when >2%', tone: (v: number) => v > 0.02 ? 'warn' : 'good' },
    { name: 'Inventory Accuracy %', suffix: '%', icon: ShieldCheck, note: 'Latest-day sensor vs shift-C book', tone: () => 'unknown' },
    { name: 'Ethane Purity %', suffix: '%', icon: Gauge, note: 'Lab measurement, normalized by DAX', tone: () => 'unknown' },
    { name: 'FG Days of Stock', suffix: 'days', icon: Layers, note: 'Snapshot stock / average shipments', tone: () => 'unknown' },
  ];
  function applyFilters(next: Filters) {
    try { modelQueries(next); setFilters(next); setFilterError(''); }
    catch (error) { setFilterError(message(error)); }
  }
  function closeDialog() { setGuide(null); selectDevice(null); }
  const selected = selectedDevice && t?.devices.find(device => device.tank_id === selectedDevice.tank_id);

  return <div className="app-shell">
    <aside className="sidebar">
      <a href="#overview" className="brand"><div className="brand-mark"><Layers size={24} /></div><div>PLANT<span>CONTROL TOWER</span></div></a>
      <div className="workspace-label">LSP OPERATIONS <span>01</span></div>
      <nav aria-label="Control tower sections">
        <a href="#overview"><Gauge size={18} />Overview</a>
        <a href="#flow"><GitBranch size={18} />Data flow</a>
        <a href="#iot"><Radio size={18} />IoT & Eventstream<span className="nav-count">4</span></a>
        <a href="#loads"><Database size={18} />Load assurance</a>
        <a href="#operations"><Activity size={18} />Operations</a>
        <a href="#business"><ChartNoAxesCombined size={18} />Business insights</a>
      </nav>
      <div className="sidebar-bottom">
        <button onClick={() => setGuide('alerts')}><Bell size={17} />Alert readiness<Badge tone="warn">Setup</Badge></button>
        <button onClick={() => setGuide('model')}><CircleHelp size={17} />Evidence & definitions</button>
        <div className="fabric-label"><span className="fabric-glyph">F</span><div>Microsoft Fabric<small>Rayfin application</small></div></div>
      </div>
    </aside>
    <div className="workspace">
      <div className="topbar"><span className="breadcrumbs">LSP Plant<ChevronRight size={13} /><strong>Feedstock to Polymer</strong></span>
        <span className="topbar-right"><span className="environment-dot" />DEMO ENVIRONMENT<span className="avatar">OP</span></span></div>
      <main>
        <section id="overview">
          <div className="page-heading"><div><div className="eyebrow">OPERATIONS INTELLIGENCE</div><h1>Feedstock to Polymer <span>Control Tower</span></h1>
            <p className="subtitle">From source to decision. Know what arrived, where it stalled, and what to do next.</p></div>
            <NativeLink to="report" className="button primary"><ChartNoAxesCombined size={16} />Open Power BI report</NativeLink></div>
          <div className="demo-notice"><ShieldCheck size={17} /><span><strong>Real Fabric evidence. Synthetic plant data.</strong> Historical historian, LIMS, MES and ERP labels are generated by one notebook, not live enterprise connectors. IoT is a simulated device stream.</span></div>
          <div className="status-toolbar"><div className="row"><Badge tone={overall.tone}>{overall.label}</Badge><span className="muted">All displayed times: Vietnam (UTC+7)</span></div>
            <div className="row"><label className="auto"><input type="checkbox" checked={auto} onChange={event => setAuto(event.target.checked)} />Auto-refresh 60s</label>
              <button className="button secondary" onClick={() => { setNow(Date.now()); setTick(value => value + 1); }} disabled={busy}><RefreshCw size={14} className={busy ? 'spin' : ''} />Refresh</button></div></div>
          <div className="health-grid">
            <div className={`health-tile ${overall.tone}`}><div className="row spread"><span>FABRIC VISIBILITY</span><Activity size={19} /></div><strong>{unavailable ? `${unavailable} unavailable` : pending ? 'Checking...' : '4 evidence paths'}</strong><small>{overall.detail}</small></div>
            <button className={`health-tile ${t ? stale ? 'bad' : 'good' : 'unknown'}`} onClick={() => setGuide('simulator')}><div className="row spread"><span>DEVICE HEARTBEATS</span><Radio size={19} /></div><strong>{t ? `${active} / 4` : '--'}<em>receiving</em></strong><small>{t ? `${stale} delayed, stale or missing. Expected every 60s.` : telemetry.error ? 'Telemetry evidence unavailable' : 'Querying Eventhouse...'}</small></button>
            <button className={`health-tile ${loadSignal.tone}`} onClick={() => setGuide('lakehouse')}><div className="row spread"><span>LAKEHOUSE CONTRACT</span><Database size={19} /></div><strong>{l ? fmt(l.daily.reduce((sum, row) => sum + (number(row, 'row_count') ?? 0), 0)) : '--'}<em>/ 2,550 facts</em></strong><small>{loadSignal.label} - 30 rolling days, 85 facts/day</small></button>
            <button className={`health-tile ${pipelineSignal.tone}`} onClick={() => setGuide('pipeline')}><div className="row spread"><span>LATEST PIPELINE RUN</span><GitBranch size={19} /></div><strong className="text-value">{pipelineSignal.label}</strong><small>{latestPipeline ? `Started ${time(latestPipeline.startTimeUtc)}` : fabric.error ? 'Run history unavailable' : 'Reading job history...'}</small></button>
          </div>
        </section>

        <section id="flow">
          <SectionHead eyebrow="END-TO-END OBSERVABILITY" title="Follow the data, find the bottleneck"><button className="text-button" onClick={() => setGuide('eventstream')}>How to investigate<ArrowRight size={15} /></button></SectionHead>
          <Panel className="flow-panel">
            <div className="flow-label"><span className="lane-tag">BATCH</span><span>Generated historical data</span><span className="muted">07:15 daily refresh</span></div>
            <div className="flow-lane">
              <button className="flow-node" onClick={() => setGuide('lakehouse')}><Factory size={22} /><strong>Source systems</strong><small>Historian / Lab / MES / ERP</small><Badge tone="unknown">Simulated labels</Badge></button><ArrowRight className="flow-arrow" />
              <button className="flow-node" onClick={() => setGuide('pipeline')}><GitBranch size={22} /><strong>Daily pipeline</strong><small>pl_daily_refresh</small><Badge tone={pipelineSignal.tone}>{pipelineSignal.label}</Badge></button><ArrowRight className="flow-arrow" />
              <button className="flow-node" onClick={() => setGuide('lakehouse')}><Database size={22} /><strong>Lakehouse</strong><small>6 existing Delta tables</small><Badge tone={loadSignal.tone}>{loadSignal.label}</Badge></button><ArrowRight className="flow-arrow" />
              <button className="flow-node" onClick={() => setGuide('model')}><Layers size={22} /><strong>Semantic model</strong><small>sm_lsp_feedstock / Direct Lake</small><Badge tone={m ? 'good' : 'unknown'}>{m ? 'Query verified' : 'Not verified'}</Badge></button><ArrowRight className="flow-arrow" />
              <button className="flow-node" onClick={() => setGuide('report')}><ChartNoAxesCombined size={22} /><strong>Power BI</strong><small>Existing five-page report</small><Badge tone="unknown">Open to explore</Badge></button>
            </div>
            <div className="flow-label live-label"><span className="lane-tag live">LIVE</span><span>Simulated tank sensors</span><span className="muted">1 reading / tank / minute</span></div>
            <div className="flow-lane live-lane">
              <button className="flow-node" onClick={() => setGuide('simulator')}><Radio size={22} /><strong>Four tank devices</strong><small>60-minute producer run</small><Badge tone={f ? jobHealth(latestJob(f.simulator)).tone : 'unknown'}>{f ? jobHealth(latestJob(f.simulator)).label : 'Not verified'}</Badge></button><ArrowRight className="flow-arrow" />
              <button className="flow-node" onClick={() => setGuide('eventstream')}><Activity size={22} /><strong>Eventstream</strong><small>{f ? `${f.eventstream.sources} source / ${f.eventstream.destinations} destination` : 'es_tank_readings'}</small><Badge tone="unknown">{f ? 'Topology configured' : 'Not verified'}</Badge></button><ArrowRight className="flow-arrow" />
              <button className="flow-node" onClick={() => setGuide('realtime')}><ArrowDownToLine size={22} /><strong>Eventhouse</strong><small>TankReadings</small><Badge tone={t ? stale ? 'bad' : 'good' : 'unknown'}>{t ? stale ? 'Stale / delayed' : 'Fresh heartbeats' : 'Not verified'}</Badge></button><ArrowRight className="flow-arrow" />
              <button className="flow-node" onClick={() => setGuide('realtime')}><Gauge size={22} /><strong>Real-time dashboard</strong><small>Levels, temperature, pressure</small><Badge tone="unknown">Native drill-through</Badge></button>
            </div>
          </Panel>
        </section>

        <section id="iot">
          <SectionHead eyebrow="REAL-TIME DELIVERY" title="IoT & Eventstream health"><span className="checked">Checked {t ? time(t.checkedAt) : '--'}</span><NativeLink to="realtime">Real-time dashboard</NativeLink></SectionHead>
          <Evidence resource={telemetry}><div className="iot-grid">
            <Panel><div className="panel-title"><div><h3>Events reaching Eventhouse</h3><p>Completed minutes only. Expected cadence, not measured packet loss.</p></div><span className="metric-pill">{lastMinute ? `${fmt(number(lastMinute, 'events'))} / 4` : '--'}<small>last full minute</small></span></div>
              <div className="chart" role="img" aria-label="Tank events received per completed minute, expected four per minute"><ResponsiveContainer width="100%" height="100%"><BarChart data={complete} margin={{ top: 16, right: 12, bottom: 0, left: -28 }}>
                <CartesianGrid strokeDasharray="3 5" vertical={false} stroke="#e8edf2" /><XAxis dataKey="minute" tickFormatter={value => time(value).slice(-8, -3)} tick={{ fontSize: 10 }} minTickGap={35} tickLine={false} axisLine={false} />
                <YAxis allowDecimals={false} domain={[0, (max: number) => Math.max(5, max)]} tick={{ fontSize: 10 }} tickLine={false} axisLine={false} /><Tooltip labelFormatter={value => time(String(value))} /><ReferenceLine y={4} stroke="#e7a647" strokeDasharray="5 4" /><Bar dataKey="events" name="Received events" fill="#087f8c" radius={[3, 3, 0, 0]} maxBarSize={17} />
              </BarChart></ResponsiveContainer></div>
              <div className="chart-footer"><span><i className="legend-dot teal" />Received events <i className="legend-line" />Expected cadence: 4/min</span><span>{thinMinutes} of {complete.length} minutes with &lt;4 distinct tanks</span></div>
            </Panel>
            <Panel><div className="panel-title"><div><h3>Delivery diagnosis</h3><p>Use observed evidence, then act.</p></div><TriangleAlert size={19} className={stale ? 'amber-text' : 'teal-text'} /></div>
              <div className={`diagnosis ${stale ? 'warn' : 'good'}`}><strong>{stale ? `${stale} tank heartbeat(s) need attention` : 'All tank heartbeats are recent'}</strong>
                <p>{stale ? `Producer: ${f ? jobHealth(latestJob(f.simulator)).label : 'not verified'}. A completed 60-minute simulator run normally stops sending. Check the producer before changing Eventstream.` : 'Recent readings are stored in the destination. Producer sent counts are not independently measured.'}</p></div>
              <dl className="diagnostic-list"><div><dt>Invalid readings ingested / 1h</dt><dd className={t?.invalidReadings ? 'red-text' : ''}>{t ? fmt(t.invalidReadings) : '--'}</dd></div><div><dt>Expected devices</dt><dd>4 tanks</dd></div><div><dt>Stale threshold</dt><dd>&gt;180 seconds</dd></div><div><dt>Producer acknowledgements</dt><dd>Not instrumented</dd></div></dl>
              <button className="button primary full" onClick={() => setGuide(stale ? 'simulator' : 'eventstream')}>{stale ? 'Open recovery guide' : 'Inspect delivery path'}<ArrowRight size={15} /></button>
            </Panel>
          </div>
          <div className="device-grid">{t?.devices.map(device => {
            const signal = deviceHealth(device, now);
            return <button className={`device-card ${signal.tone}`} key={String(device.tank_id)} onClick={() => selectDevice(device)}>
              <div className="row spread"><span className="device-symbol"><Boxes size={22} /></span><Badge tone={signal.tone}>{signal.label}</Badge></div>
              <h3>{String(device.tank_id)}</h3><span className="device-material">{String(device.material)}</span>
              <div className="device-value">{fmt(number(device, 'level_tons'), 1)}<small>tons / last observed</small></div>
              <div className="device-conditions"><span>{fmt(number(device, 'temperature_c'), 1)} C</span><span>{fmt(number(device, 'pressure_barg'), 2)} barg</span></div>
              <div className="device-footer"><span><span className={`dot ${signal.tone}`} />{age(device.reading_ts, now)}</span><ChevronRight size={16} /></div>
            </button>;
          })}</div></Evidence>
        </section>

        <section id="loads">
          <SectionHead eyebrow="INGESTION ASSURANCE" title="Did the historical data load?"><span className="checked">SQL checked {l ? time(l.checkedAt) : '--'}</span><NativeLink to="lakehouse">Open Lakehouse</NativeLink></SectionHead>
          <Evidence resource={loads}><Panel>
            <div className="load-summary"><div className="row"><Database size={22} /><div><h3>30-day load contract</h3><p>{loadSignal.detail}</p></div></div><Badge tone={loadSignal.tone}>{loadSignal.label}</Badge></div>
            <div className="table-controls"><label className="search"><Search size={16} /><input placeholder="Find a source or measure..." aria-label="Filter sources" value={search} onChange={event => setSearch(event.target.value)} /></label><label className="auto"><input type="checkbox" checked={onlyExceptions} onChange={event => setOnlyExceptions(event.target.checked)} />Exceptions only</label><span className="muted">All source labels below are simulated</span></div>
            <div className="table-scroll"><table><thead><tr><th>Illustrative source system</th><th>Data product</th><th>Observed / expected</th><th>Dates</th><th>Latest business date</th><th>Load evidence</th><th /></tr></thead><tbody>
              {sourceRows.map(row => {
                const expected = expectedPerDay[String(row.measure_id)] * 30;
                const okay = number(row, 'row_count') === expected && number(row, 'loaded_days') === 30 && number(row, 'null_values') === 0;
                return <tr key={String(row.measure_id)}><td><strong>{String(row.source_system)}</strong><small>Generator notebook, not a direct connector</small></td><td>{String(row.measure_name)}<small>{String(row.measure_id)}</small></td><td><strong>{fmt(number(row, 'row_count'))}</strong><span className="muted"> / {fmt(expected)}</span></td><td>{fmt(number(row, 'loaded_days'))} / 30</td><td>{row.latest_date_key ? String(row.latest_date_key).replace(/(\d{4})(\d{2})(\d{2})/, '$1-$2-$3') : 'Not observed'}</td><td><Badge tone={okay ? 'good' : 'bad'}>{okay ? 'Count verified' : 'Investigate'}</Badge></td><td><button className="icon-button" aria-label={`Investigate ${row.measure_id}`} onClick={() => setGuide('lakehouse')}><ChevronRight size={17} /></button></td></tr>;
              })}
              {!sourceRows.length && <tr><td colSpan={7}>No sources match the current filter.</td></tr>}
            </tbody></table></div>
            <div className="table-footnote"><CircleHelp size={14} />Counts verify the generated data contract, not external source delivery. Synthetic source_ts is not used as an ingestion heartbeat.</div>
          </Panel>
          <div className="load-detail-grid"><Panel><div className="panel-title"><div><h3>Business-date coverage</h3><p>Choose a day to inspect its Power BI KPIs. Each full day must have 85 facts.</p></div><Badge tone={l?.duplicateKeys ? 'bad' : 'good'}>{l ? `${l.duplicateKeys} duplicate keys` : '--'}</Badge></div>
            <div className="date-grid">{expectedLoadDates(now).map(key => {
              const row = l?.daily.find(day => number(day, 'date_key') === key);
              const count = row ? number(row, 'row_count') : null;
              const date = String(key).replace(/(\d{4})(\d{2})(\d{2})/, '$1-$2-$3');
              return <button key={key} className={`date-cell ${count === 85 ? 'good' : 'bad'}`} title={`${date}: ${count ?? 0} / 85 facts; inspect model KPIs`} onClick={() => {
                const next = { ...filters, start: date, end: date };
                setDraft(next); applyFilters(next);
                document.getElementById('business')?.scrollIntoView({ behavior: 'smooth' });
              }}><small>{date.slice(5)}</small><span>{count === 85 ? <Check size={14} /> : <TriangleAlert size={14} />}{count ?? 0}</span></button>;
            })}</div>
          </Panel><Panel><div className="panel-title"><div><h3>Reused Lakehouse tables</h3><p>Live SQL analytics endpoint counts</p></div><Layers size={20} /></div><dl className="table-counts">{l?.tables.map(row => <div key={String(row.table_name)}><dt>{String(row.table_name)}</dt><dd>{fmt(number(row, 'row_count'))}</dd></div>)}</dl></Panel></div></Evidence>
        </section>

        <section id="operations">
          <SectionHead eyebrow="OPERATIONAL RESPONSE" title="Run history & recovery"><span className="checked">Checked {f ? time(f.checkedAt) : '--'}</span><button className="text-button" onClick={() => setGuide('pipeline')}>Recovery guide<ArrowRight size={15} /></button></SectionHead>
          <Evidence resource={fabric}><div className="operations-grid"><Panel><RunHistory title="Daily refresh pipeline" jobs={f?.pipeline ?? []} guide="pipeline" /></Panel><Panel><RunHistory title="IoT stream simulator" jobs={f?.simulator ?? []} guide="simulator" /></Panel><Panel>
            <h3>Automation readiness</h3><div className="readiness-item"><div className="row spread"><strong>Daily refresh</strong>{schedule && <Badge tone={schedule.tone}>{schedule.label}</Badge>}</div><p>{schedule?.detail}</p>
              {f?.schedules.map(s => <small key={s.id}>End: {time(s.configuration.endDateTime)}<br />Zone: {s.configuration.localTimeZoneId}</small>)}</div>
            <div className="readiness-item"><div className="row spread"><strong>Activator notifications</strong><Badge tone="warn">Manual setup</Badge></div><p>Deployment baseline: four rules saved, stopped, recipients unset. Live rule state is not polled.</p><button className="text-button" onClick={() => setGuide('alerts')}>Configure safely<ArrowRight size={14} /></button></div>
            <div className="safe-action"><ShieldCheck size={17} /><small>Recovery links open native Fabric. Your Fabric permissions apply; this app does not execute retries or configuration changes.</small></div>
          </Panel></div></Evidence>
        </section>

        <section id="business">
          <SectionHead eyebrow="POWER BI / GOVERNED MEASURES" title="Business impact, in the same model"><span className="checked">Model checked {m ? time(m.checkedAt) : '--'}</span><NativeLink to="report">Explore full report</NativeLink></SectionHead>
          <form className="filters" onSubmit={event => { event.preventDefault(); applyFilters(draft); }}>
            <label>From<input type="date" value={draft.start} onChange={event => setDraft({ ...draft, start: event.target.value })} required /></label><label>To<input type="date" value={draft.end} onChange={event => setDraft({ ...draft, end: event.target.value })} required /></label>
            <label>Shift<select value={draft.shift} onChange={event => setDraft({ ...draft, shift: event.target.value })}><option value="ALL">All shifts</option><option value="A">Shift A</option><option value="B">Shift B</option><option value="C">Shift C</option></select></label>
            <button className="button primary" type="submit">Apply to model<ArrowRight size={14} /></button><span className="filter-hint">Only the business KPIs & trend are filtered.<br />IoT is live; load assurance always checks 30 days.</span>
          </form>{filterError && <p className="filter-error" role="alert">{filterError}</p>}
          <p className="applied-filters">Applied: {filters.start} to {filters.end} / {filters.shift === 'ALL' ? 'all shifts' : `shift ${filters.shift}`}. Snapshot measures retain their original DAX semantics.</p>
          <Evidence resource={model}>
            <div className="kpi-grid">{kpis.map(kpi => {
              const value = m ? number(m.kpis, kpi.name) : null;
              const tone = value === null ? 'unknown' : kpi.tone(value);
              return <button className={`kpi-card ${tone}`} key={kpi.name} onClick={() => setGuide('model')}>
                <div className="row spread"><span>{kpi.name}</span><kpi.icon size={18} /></div><strong>{fmt(value === null ? null : kpi.suffix === '%' ? value * 100 : value, 1)}<small>{kpi.suffix}</small></strong><p>{value === null ? 'No data in the selected model context' : kpi.note}</p><span className="model-source"><span className="dot" />sm_lsp_feedstock</span>
              </button>;
            })}</div>
            <Panel><div className="panel-title"><div><h3>Trace performance over time</h3><p>Existing DAX measures. Select a metric; use the date and shift controls above.</p></div><div className="segmented" aria-label="Trend metric">{(['Yield', 'Purity', 'Gap'] as const).map(metric => <button key={metric} aria-pressed={trendMetric === metric} className={trendMetric === metric ? 'selected' : ''} onClick={() => setTrendMetric(metric)}>{metric}</button>)}</div></div>
              {!m?.trend.length ? <div className="loading">No model data in this date/shift selection. Choose dates within the loaded coverage.</div> : <div className="business-chart" role="img" aria-label={`${trendMetric} percentage from the existing semantic model by business date`}><ResponsiveContainer width="100%" height="100%"><AreaChart data={m?.trend} margin={{ top: 15, right: 18, left: -10, bottom: 0 }}>
                <defs><linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#0d8c96" stopOpacity={0.22} /><stop offset="100%" stopColor="#0d8c96" stopOpacity={0.01} /></linearGradient></defs>
                <CartesianGrid stroke="#e8edf2" strokeDasharray="3 5" vertical={false} /><XAxis dataKey="date" tickFormatter={value => String(value).slice(5, 10)} tick={{ fontSize: 11 }} minTickGap={30} tickLine={false} axisLine={false} /><YAxis tickFormatter={value => `${fmt(Number(value) * 100, 0)}%`} domain={['auto', 'auto']} tick={{ fontSize: 10 }} tickLine={false} axisLine={false} /><Tooltip labelFormatter={value => String(value).slice(0, 10)} formatter={value => `${fmt(Number(value) * 100, 2)}%`} /><Area type="linear" dataKey={trendMetric} stroke="#087f8c" strokeWidth={2.5} fill="url(#trendFill)" connectNulls={false} isAnimationActive={false} />
              </AreaChart></ResponsiveContainer></div>}
              <div className="business-totals">{['Total Feed (t)', 'Total Output (t)', 'Total Production (t)', 'Shipped (t)', 'Ethane Stock (t)'].map(name => <div key={name}><span>{name}</span><strong>{m ? fmt(number(m.kpis, name), 1) : '--'}</strong></div>)}</div>
            </Panel>
          </Evidence>
        </section>
        <footer className="page-footer"><span><ShieldCheck size={14} />Read-only monitoring. No operational control of real plant equipment.</span><button className="text-button" onClick={() => setGuide('model')}>Evidence, permissions & definitions<ArrowRight size={14} /></button></footer>
      </main>
    </div>
    <dialog ref={dialog} className="detail-dialog" onCancel={closeDialog} onClose={closeDialog}>
      <div className="dialog-top"><span className="eyebrow">{selectedDevice ? 'DEVICE EVIDENCE' : 'OPERATOR PLAYBOOK'}</span><button className="icon-button" onClick={closeDialog} aria-label="Close details"><X size={20} /></button></div>
      {selectedDevice && <div className="dialog-content"><h2>{String(selectedDevice.tank_id)}</h2>{selected ? <>
        <Badge tone={deviceHealth(selected, now).tone}>{deviceHealth(selected, now).label}</Badge><p>{deviceHealth(selected, now).detail}</p>
        <dl className="diagnostic-list"><div><dt>Device timestamp</dt><dd>{time(selected.reading_ts)}</dd></div><div><dt>Last ingestion (15m window)</dt><dd>{time(selected.last_ingested)}</dd></div><div><dt>Device age</dt><dd>{age(selected.reading_ts, now)}</dd></div><div><dt>Events observed / 15m</dt><dd>{fmt(number(selected, 'events15m'))}</dd></div><div><dt>Level / temperature / pressure</dt><dd>{fmt(number(selected, 'level_tons'), 1)} t / {fmt(number(selected, 'temperature_c'), 1)} C / {fmt(number(selected, 'pressure_barg'), 2)} barg</dd></div></dl>
        <p className="muted">Last-observed values may be stale. Missing sent counts mean delivery loss is unknown. The current minute may be incomplete.</p>
      </> : <div className="error-box">Current telemetry evidence is unavailable; the selected device is not assumed healthy.</div>}
        <button className="button primary full" onClick={() => { selectDevice(null); setGuide('simulator'); }}>Investigate producer & delivery<ArrowRight size={15} /></button></div>}
      {guide && <div className="dialog-content"><h2>{guides[guide].title}</h2><p>{guides[guide].description}</p><ol className="playbook">{guides[guide].steps.map(step => <li key={step}>{step}</li>)}</ol><div className="caution"><TriangleAlert size={18} /><p>{guides[guide].caution}</p></div><NativeLink to={guide} className="button primary full">Open existing Fabric artifact</NativeLink>{guide === 'model' && <NativeLink to="report" className="button secondary full">Open Power BI report</NativeLink>}</div>}
    </dialog>
  </div>;
}

function App() {
  const [connection, setConnection] = useState<Connection | null>(null);
  const [signedIn, setSignedIn] = useState(false);
  const [initializing, setInitializing] = useState(true);
  const [signingIn, setSigningIn] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    let current: Connection | null = null;
    let unsubscribe: (() => void) | undefined;
    connect().then(async value => {
      current = value;
      await initEmbeddedAuth(value.client.auth, value.fabricOptions);
      if (!active) { value.client.dispose(); return; }
      setConnection(value);
      setSignedIn(!!value.client.auth.getSession());
      unsubscribe = value.client.auth.onSessionChange(session => setSignedIn(!!session));
    }).catch(cause => { if (active) setError(message(cause)); })
      .finally(() => { if (active) setInitializing(false); });
    return () => { active = false; unsubscribe?.(); current?.client.dispose(); };
  }, []);
  async function signIn() {
    if (!connection) return;
    setError(''); setSigningIn(true);
    try {
      await ensureSignedInWithFabric(connection.client.auth, connection.fabricOptions);
      setSignedIn(true);
    } catch (cause) { setError(message(cause)); }
    finally { setSigningIn(false); }
  }
  if (connection && signedIn && !initializing) return <ControlTower connection={connection} />;
  return <div className="auth-page"><div className="auth-card"><div className="auth-brand"><Layers size={29} /></div><span className="eyebrow">MICROSOFT FABRIC / RAYFIN</span><h1>Plant Control Tower</h1><p>One view of data delivery, live tank telemetry and governed business KPIs.</p><div className="auth-features"><span><Radio size={16} />IoT heartbeat assurance</span><span><Database size={16} />Lakehouse load evidence</span><span><ChartNoAxesCombined size={16} />Existing Power BI model</span></div>
    {error && <div className="error-box" role="alert"><TriangleAlert size={18} /><p>{error}</p></div>}
    {initializing ? <div className="loading"><LoaderCircle size={18} className="spin" />Connecting securely...</div> : connection ? <button className="button primary full" disabled={signingIn} onClick={signIn}>{signingIn ? <LoaderCircle size={18} className="spin" /> : <ShieldCheck size={18} />}{signingIn ? 'Signing in...' : 'Continue with Fabric SSO'}</button> : <button className="button secondary full" onClick={() => window.location.reload()}>Retry configuration</button>}
    <small>Protected application. Sign in with an authorized Fabric account.<br />Read and Build access to sm_lsp_feedstock is required for business KPIs.</small></div></div>;
}

createRoot(document.getElementById('root')!).render(<App />);
