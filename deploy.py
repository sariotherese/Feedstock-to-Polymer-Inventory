"""Deploy the LSP demo into the user-supplied Fabric workspace folder."""

import argparse
import json

from fabric_client import FabricClient, STATE, save_state, definition
from notebook_definitions import generator_notebook


def foundation(client: FabricClient) -> dict:
    items = {}
    items["lh_lsp_plant"] = client.ensure_item("lh_lsp_plant", "Lakehouse")
    items["eh_lsp_plant"] = client.ensure_item("eh_lsp_plant", "Eventhouse")
    items["kqldb_lsp_plant"] = client.ensure_item(
        "kqldb_lsp_plant", "KQLDatabase", definition({
            "DatabaseProperties.json": {
                "databaseType": "ReadWrite",
                "parentEventhouseItemId": items["eh_lsp_plant"]["id"],
            },
            "DatabaseSchema.kql": (
                ".create-merge table TankReadings (reading_ts:datetime, tank_id:string, "
                "level_tons:real, temperature_c:real, pressure_barg:real)\n"
            ),
        }),
    )
    items["nb_01_generate_sample_data"] = client.ensure_item(
        "nb_01_generate_sample_data", "Notebook",
        generator_notebook(items["lh_lsp_plant"]["id"]),
    )
    save_state("items.json", items)
    return items


def realtime(client: FabricClient, items: dict) -> None:
    from kusto_client import KustoClient
    from realtime_definitions import dashboard, eventstream
    from notebook_definitions import simulator_notebook
    database_id = items["kqldb_lsp_plant"]["id"]
    props = client.request("GET", f"{client.workspace}/kqlDatabases/{database_id}").json()["properties"]
    kusto = KustoClient(props["queryServiceUri"], database_id)
    mapping = [
        {"column": name, "Properties": {"Path": "$." + name}}
        for name in ["reading_ts", "tank_id", "level_tons", "temperature_c", "pressure_barg"]
    ]
    kusto.execute(".create-or-alter table TankReadings ingestion json mapping "
                  "'TankReadings_json' '" + json.dumps(mapping) + "'")
    items["es_tank_readings"] = client.ensure_item(
        "es_tank_readings", "Eventstream", eventstream(database_id),
    )
    save_state("items.json", items)
    topology = client.request(
        "GET", f"{client.workspace}/eventstreams/{items['es_tank_readings']['id']}/topology",
    ).json()
    sources = topology["sources"]
    source_id = next(s["id"] for s in sources if s["name"] == "tank_simulator")
    items["nb_02_stream_simulator"] = client.ensure_item(
        "nb_02_stream_simulator", "Notebook",
        simulator_notebook(items["lh_lsp_plant"]["id"], items["es_tank_readings"]["id"], source_id),
    )
    save_state("items.json", items)
    items["rtd_lsp_plant"] = client.ensure_item(
        "rtd_lsp_plant", "KQLDashboard", dashboard(props["queryServiceUri"], database_id),
    )
    save_state("items.json", items)


def analytics(client: FabricClient, items: dict) -> None:
    from semantic_model import model_definition
    from report_definition import report
    props = client.request(
        "GET", f"{client.workspace}/lakehouses/{items['lh_lsp_plant']['id']}",
    ).json()["properties"]["sqlEndpointProperties"]
    items["sm_lsp_feedstock"] = client.ensure_item(
        "sm_lsp_feedstock", "SemanticModel", model_definition(props["connectionString"], "lh_lsp_plant"),
    )
    save_state("items.json", items)
    items["rpt_lsp_feedstock"] = client.ensure_item(
        "rpt_lsp_feedstock", "Report", report(items["sm_lsp_feedstock"]["id"]),
    )
    save_state("items.json", items)


def daily_pipeline(client: FabricClient, items: dict) -> None:
    from datetime import datetime, timedelta, timezone
    from pipeline_definition import pipeline
    connections = [
        c for c in client.list_all("connections")
        if c.get("displayName") == "PowerBIDatasets admin"
        and (c.get("connectionDetails") or {}).get("type") == "PowerBIDatasets"
    ]
    if len(connections) != 1:
        raise RuntimeError("Select a PowerBIDatasets refresh connection; expected 'PowerBIDatasets admin'")
    items["pl_daily_refresh"] = client.ensure_item(
        "pl_daily_refresh", "DataPipeline", pipeline(
            items["nb_01_generate_sample_data"]["id"], items["sm_lsp_feedstock"]["id"],
            connections[0]["id"],
        ),
    )
    save_state("items.json", items)
    path = f"{client.workspace}/items/{items['pl_daily_refresh']['id']}/jobs/Pipeline/schedules"
    schedules = client.list_all(path)
    if not schedules:
        now = datetime.now(timezone.utc)
        result = client.request("POST", path, json={
            "enabled": True,
            "configuration": {
                "type": "Daily", "times": ["07:15"],
                "localTimeZoneId": "SE Asia Standard Time",
                "startDateTime": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "endDateTime": (now + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        }).json()
        save_state("daily-schedule.json", result)
    location = client.start_job(items["pl_daily_refresh"]["id"], "Pipeline")
    save_state("pipeline-job.json", {"location": location})
    save_state("pipeline-result.json", client.wait_job(location))


def alerts(client: FabricClient, items: dict) -> None:
    from alert_definitions import PLANT_SIGNALS, activator
    from realtime_definitions import dashboard
    from fabric_client import WORKSPACE_ID
    from kusto_client import KustoClient
    database_id = items["kqldb_lsp_plant"]["id"]
    props = client.request("GET", f"{client.workspace}/kqlDatabases/{database_id}").json()["properties"]
    kusto = KustoClient(props["queryServiceUri"], database_id)
    location = (
        f"abfss://{WORKSPACE_ID}@onelake.dfs.fabric.microsoft.com/"
        f"{items['lh_lsp_plant']['id']}/Tables/fact_plant_data;impersonate"
    )
    kusto.execute(f".create-or-alter external table PlantHistory kind=delta (h@'{location}')")
    kusto.execute(".create-or-alter function with (folder='LSP Demo') PlantSignals() {\n"
                  + PLANT_SIGNALS + "\n}")
    result = kusto.execute("PlantSignals()")
    save_state("plant-signals-validation.json", result)
    print("Validated PlantSignals:", result["Tables"][0]["Rows"], flush=True)
    items["rtd_lsp_plant"] = client.ensure_item(
        "rtd_lsp_plant", "KQLDashboard", dashboard(props["queryServiceUri"], database_id),
    )
    save_state("items.json", items)
    items["act_lsp_alerts"] = client.ensure_item(
        "act_lsp_alerts", "Reflex", activator(
            database_id, props["queryServiceUri"], items["rtd_lsp_plant"]["id"],
        ),
    )
    save_state("items.json", items)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["foundation", "generate", "analytics", "realtime", "pipeline", "alerts", "stream", "status"])
    args = parser.parse_args()
    client = FabricClient()
    if args.stage == "foundation":
        foundation(client)
    elif args.stage in {"generate", "stream", "analytics", "realtime", "pipeline", "alerts"}:
        items = json.loads((STATE / "items.json").read_text(encoding="utf-8"))
        if args.stage in {"analytics", "realtime", "pipeline", "alerts"}:
            {"analytics": analytics, "realtime": realtime, "pipeline": daily_pipeline,
             "alerts": alerts}[args.stage](client, items)
        else:
            name = "nb_01_generate_sample_data" if args.stage == "generate" else "nb_02_stream_simulator"
            location = client.start_job(items[name]["id"], "RunNotebook")
            save_state(args.stage + "-job.json", {"location": location})
            if args.stage == "generate":
                save_state("generator-result.json", client.wait_job(location))
            else:
                print(f"Stream job started: {location}")
    else:
        print(json.dumps(client.list_all(f"{client.workspace}/items?rootFolderId="
                                        "62e9a35c-6d20-48cb-9b04-7c1af8d74556"), indent=2))


if __name__ == "__main__":
    main()
