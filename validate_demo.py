"""Verify deployed data, Direct Lake measures, report, stream, dashboard, and pipeline."""

import base64
import json
import math
from collections import defaultdict
from datetime import date, datetime, timezone

import requests

from fabric_client import FabricClient, FOLDER_ID, STATE, WORKSPACE_ID, access_token, save_state
from kusto_client import KustoClient
from plant_data import SCHEMAS, generate
from realtime_definitions import QUERIES
from alert_definitions import RULES


def decode_parts(response: dict) -> dict[str, str]:
    return {p["path"]: base64.b64decode(p["payload"]).decode("utf-8")
            for p in response["definition"]["parts"]}


def dax(model_id: str, query: str) -> list[dict]:
    response = requests.post(
        f"https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}/datasets/{model_id}/executeQueries",
        headers={"Authorization": "Bearer " + access_token("https://analysis.windows.net/powerbi/api")},
        json={"queries": [{"query": query}], "serializerSettings": {"includeNulls": True}},
        timeout=120,
    )
    response.raise_for_status()
    result = response.json()
    if "error" in result or "error" in result["results"][0]:
        raise RuntimeError(f"DAX failed: {result}")
    return result["results"][0]["tables"][0]["rows"]


def validate() -> dict:
    client = FabricClient()
    items = json.loads((STATE / "items.json").read_text(encoding="utf-8"))
    report = {}
    for name, item in items.items():
        actual = client.request("GET", f"{client.workspace}/items/{item['id']}").json()
        assert actual["displayName"] == name, name
        assert actual["folderId"] == FOLDER_ID, f"{name}: wrong folder"
    report["items_in_target_folder"] = len(items)

    lakehouse = items["lh_lsp_plant"]["id"]
    tables = client.request("GET", f"{client.workspace}/lakehouses/{lakehouse}/tables").json()["data"]
    assert {t["name"] for t in tables} == set(SCHEMAS), tables
    assert all(t["format"] == "delta" for t in tables)
    report["delta_tables"] = [t["name"] for t in tables]

    model_id = items["sm_lsp_feedstock"]["id"]
    raw = client.operation(client.request(
        "POST", f"{client.workspace}/semanticModels/{model_id}/getDefinition?format=TMSL",
    ))
    model = json.loads(decode_parts(raw)["model.bim"])["model"]
    assert len(model["tables"]) == 6 and len(model["relationships"]) == 5
    assert all(t["partitions"][0]["mode"] == "directLake" for t in model["tables"])
    # TMSL omits TOM defaults (many-to-one, single-direction, active).
    assert all(r.get("crossFilteringBehavior", "oneDirection") == "oneDirection"
               for r in model["relationships"])
    report["direct_lake_tables"] = 6
    report["single_direction_relationships"] = 5

    rows = dax(model_id, """
EVALUATE SUMMARIZECOLUMNS(dim_date[date],
    "Feed", [Total Feed (t)], "Output", [Total Output (t)],
    "EthaneFeed", [Ethane Feed (t)], "Yield", [Ethylene Yield %],
    "Purity", [Ethane Purity %], "Gap", [Mass Balance Gap %],
    "Accuracy", [Inventory Accuracy %], "Cover", [Days of Cover],
    "EthaneStock", [Ethane Stock (t)], "SensorStock", [Sensor Stock (t)],
    "BookStock", [Book Stock (t)], "FGStock", [FG Stock (t)])
ORDER BY dim_date[date]
""")
    assert len(rows) == 30
    ground_truth = generate(date.fromisoformat(rows[-1]["dim_date[date]"][:10]))
    by_day = defaultdict(list)
    for fact in ground_truth["fact_plant_data"]:
        by_day[fact[0]].append(fact)
    for index, row in enumerate(rows):
        key = int(row["dim_date[date]"][:10].replace("-", ""))
        facts = by_day[key]

        def total(measure: str, material: str | None = None, shift: str | None = None) -> float:
            return sum(f[5] for f in facts if f[4] == measure
                       and (material is None or f[3] == material)
                       and (shift is None or f[1] == shift))

        expected = {
            "Feed": total("FEED"), "Output": total("OUTPUT"),
            "EthaneFeed": total("FEED", "ETHANE"),
            "Yield": total("OUTPUT", "ETHYLENE") / total("FEED"),
            "Purity": total("PURITY") / 3 / 100,
            "Gap": 0.03 if index == 26 else 0,
            "EthaneStock": total("STOCK_SENSOR", "ETHANE", "C"),
            "SensorStock": total("STOCK_SENSOR", shift="C"),
            "BookStock": total("STOCK_BOOK", shift="C"),
            "FGStock": total("FG_STOCK", shift="C"),
        }
        expected["Accuracy"] = 1 - abs(expected["SensorStock"] - expected["BookStock"]) / expected["BookStock"]
        preceding = rows[max(0, index - 6):index + 1]
        avg_ethane = sum(r["[EthaneFeed]"] for r in preceding) / len(preceding)
        expected["Cover"] = expected["EthaneStock"] / avg_ethane
        for name, value in expected.items():
            assert math.isclose(row[f"[{name}]"], value, rel_tol=1e-9, abs_tol=1e-8), (
                key, name, row[f"[{name}]"], value
            )
    assert rows[24]["[Purity]"] < 0.945 and rows[25]["[Purity]"] < 0.945
    count = dax(model_id, 'EVALUATE ROW("FactRows", COUNTROWS(fact_plant_data))')
    assert count[0]["[FactRows]"] == 2550
    report["fact_rows"] = 2550
    report["daily_kpis_verified_against_seed_42"] = 30
    report["anomaly_dates"] = {
        "purity_yield_drop": [r["dim_date[date]"][:10] for r in rows[24:26]],
        "mass_balance_gap_3pct": rows[26]["dim_date[date]"][:10],
        "ethane_erp_book_plus_3pct": rows[27]["dim_date[date]"][:10],
    }

    raw_report = client.operation(client.request(
        "POST", f"{client.workspace}/reports/{items['rpt_lsp_feedstock']['id']}/getDefinition",
    ))
    parts = decode_parts(raw_report)
    pages = [json.loads(v)["displayName"] for k, v in parts.items() if k.endswith("/page.json")]
    assert len(pages) == 5
    report["report_pages"] = pages

    database_id = items["kqldb_lsp_plant"]["id"]
    props = client.request("GET", f"{client.workspace}/kqlDatabases/{database_id}").json()["properties"]
    kusto = KustoClient(props["queryServiceUri"], database_id)
    for title, query in QUERIES.items():
        kusto.execute(query)
    raw_dashboard = client.operation(client.request(
        "POST", f"{client.workspace}/items/{items['rtd_lsp_plant']['id']}/getDefinition",
    ))
    dashboard = json.loads(decode_parts(raw_dashboard)["RealTimeDashboard.json"])
    live_page = next(p["id"] for p in dashboard["pages"]
                     if p["name"] == "Live plant - synthetic data")
    assert len([t for t in dashboard["tiles"] if t["pageId"] == live_page]) == 4
    query_by_id = {q["id"]: q["text"] for q in dashboard["queries"]}
    signal_tile, = [t for t in dashboard["tiles"]
                    if query_by_id[t["queryRef"]["queryId"]] == "PlantSignals()"]
    telemetry = kusto.execute("""
TankReadings | where reading_ts > ago(1h)
| sort by tank_id asc, reading_ts asc | serialize
| extend step=iff(tank_id == prev(tank_id),
                  datetime_diff('second', reading_ts, prev(reading_ts)), long(null))
| summarize Readings=count(), Latest=max(reading_ts), MinStep=min(step), MaxStep=max(step)
    by tank_id
""")["Tables"][0]["Rows"]
    assert len(telemetry) == 4
    for tank, readings, latest, min_step, max_step in telemetry:
        assert readings >= 2, (tank, readings)
        assert min_step is not None and 55 <= min_step <= max_step <= 65, (tank, min_step, max_step)
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(latest)).total_seconds()
        assert 0 <= age < 180, (tank, "stale telemetry", age)
    report["live_tank_readings"] = telemetry
    report["kql_tiles_executed"] = 4
    signals = kusto.execute("PlantSignals()")["Tables"][0]["Rows"]
    assert len(signals) == 1
    assert math.isclose(signals[0][2], rows[-1]["[Cover]"], rel_tol=1e-9)
    baseline = sum(row["[Yield]"] for row in rows[-8:-1]) / 7
    assert math.isclose(signals[0][3], 1 - rows[-1]["[Yield]"] / baseline, abs_tol=1e-9)
    assert math.isclose(signals[0][4], rows[-1]["[Gap]"], abs_tol=1e-9)
    report["kql_alert_cover_matches_dax"] = True

    raw_alerts = client.operation(client.request(
        "POST", f"{client.workspace}/items/{items['act_lsp_alerts']['id']}/getDefinition",
    ))
    entities = json.loads(decode_parts(raw_alerts)["ReflexEntities.json"])
    source = next(e["payload"] for e in entities if e["type"] == "kqlSource-v1")
    assert source["query"]["queryString"] == "PlantSignals()"
    assert source["eventhouseItem"]["databaseName"] == database_id
    assert source["eventTimeSettings"]["timeFieldName"] == "reading_ts"
    assert source["runSettings"]["executionIntervalInSeconds"] == 60
    assert source["metadata"]["dashboardId"] == items["rtd_lsp_plant"]["id"]
    assert source["metadata"]["visualId"] == signal_tile["id"]
    rules = {e["payload"]["name"]: e["payload"]["definition"] for e in entities
             if e["payload"].get("definition", {}).get("type") == "Rule"}
    assert set(rules) == {r[0] for r in RULES}
    for name, column, comparison, threshold, duration, action, audience, headline in RULES:
        rule = rules[name]
        assert rule["settings"]["shouldRun"] is False
        assert rule["settings"]["shouldApplyRuleOnUpdate"] is False
        steps = {s["name"]: s["rows"] for s in json.loads(rule["instance"])["steps"]}
        detection = {r["kind"]: r["arguments"] for r in steps["ScalarDetectStep"]}
        condition = {a["name"]: a["value"] for a in detection["NumberValueCondition"]}
        assert condition == {"op": comparison, "threshold": threshold}, (name, condition)
        if duration:
            assert detection["SustainedPeriodOption"] == [
                {"name": "period", "type": "timeSpan", "value": duration},
            ]
        binding, = steps["ActStep"]
        assert binding["kind"] == action
        recipients = [a for a in binding["arguments"]
                      if a["name"] in {"recipients", "sentTo", "copyTo", "bCCTo"}]
        assert recipients and all(not a["values"] for a in recipients), name
    report["activator_rules_verified_stopped_without_recipients"] = list(rules)
    report["yield_alert_sustained_hours"] = 6

    pipeline_location = json.loads((STATE / "pipeline-job.json").read_text())["location"]
    job = client.request("GET", pipeline_location).json()
    assert job["status"] == "Completed", job
    report["pipeline_job_status"] = job["status"]
    report["pipeline_job_id"] = job["id"]
    schedules = client.list_all(
        f"{client.workspace}/items/{items['pl_daily_refresh']['id']}/jobs/Pipeline/schedules",
    )
    assert any(s["enabled"] and s["configuration"]["times"] == ["07:15"] for s in schedules)
    report["daily_schedule"] = schedules[0]["configuration"]
    save_state("validation.json", report)
    return report


if __name__ == "__main__":
    print(json.dumps(validate(), indent=2))
