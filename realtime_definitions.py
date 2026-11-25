"""Eventstream topology and live KQL dashboard definition."""

import uuid

from fabric_client import WORKSPACE_ID, definition


def uid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "lsp-feedstock-demo/" + name))


def eventstream(database_id: str) -> dict:
    return definition({
        "eventstream.json": {
            "sources": [{"name": "tank_simulator", "type": "CustomEndpoint", "properties": {}}],
            "destinations": [{
                "name": "TankReadings", "type": "Eventhouse",
                "properties": {
                    "dataIngestionMode": "DirectIngestion",
                    "workspaceId": WORKSPACE_ID, "itemId": database_id,
                    "tableName": "TankReadings", "connectionName": "lsp_tank_readings",
                    "mappingRuleName": "TankReadings_json",
                },
                "inputNodes": [{"name": "es_tank_readings-stream"}],
            }],
            "operators": [],
            "streams": [{
                "name": "es_tank_readings-stream", "type": "DefaultStream",
                "properties": {}, "inputNodes": [{"name": "tank_simulator"}],
            }],
            "compatibilityLevel": "1.1",
        },
        "eventstreamProperties.json": {"retentionTimeInDays": 1, "eventThroughputLevel": "Low"},
    })


QUERIES = {
    "Latest level per tank": (
        "TankReadings | where reading_ts > ago(1d)\n"
        "| summarize arg_max(reading_ts, level_tons, temperature_c, pressure_barg) by tank_id\n"
        "| order by tank_id asc"
    ),
    "Level trend - last 24 hours": (
        "TankReadings | where reading_ts between (ago(24h) .. now())\n"
        "| summarize level_tons=avg(level_tons) by tank_id, bin(reading_ts, 15m)\n"
        "| render timechart"
    ),
    "Temperature trend": (
        "TankReadings | where reading_ts between (ago(24h) .. now())\n"
        "| summarize temperature_c=avg(temperature_c) by tank_id, bin(reading_ts, 5m)\n"
        "| render timechart"
    ),
    "Tanks below minimum level": (
        "let limits=datatable(tank_id:string,min_level_tons:real)"
        "['T-ETH-01',8000,'T-ETH-02',8000,'T-PRO-01',5000,'T-NAP-01',8000];\n"
        "TankReadings | where reading_ts > ago(5m)\n"
        "| summarize arg_max(reading_ts, *) by tank_id\n"
        "| join kind=inner limits on tank_id\n"
        "| where level_tons < min_level_tons\n"
        "| project tank_id,level_tons,min_level_tons,reading_ts"
    ),
}


def dashboard(cluster_uri: str, database_id: str) -> dict:
    page_id, source_id = uid("dashboard-page"), uid("dashboard-source")
    alert_page_id = uid("dashboard-alert-page")
    tiles, queries = [], []
    dashboard_queries = list(QUERIES.items()) + [("Alert signals - synthetic data", "PlantSignals()")]
    for index, (title, query) in enumerate(dashboard_queries):
        query_id = uid("query-" + str(index))
        alert_setup = index == len(QUERIES)
        trend = index in (1, 2)
        options = {
            "hideLegend": False, "legendLocation": "bottom",
            "xColumn": "reading_ts", "yColumns": [
                "level_tons" if index == 1 else "temperature_c"],
            "seriesColumns": ["tank_id"], "xAxisScale": "linear",
            "multipleYAxes": {"base": {
                "id": "-1", "label": "", "columns": [],
                "yAxisMaximumValue": None, "yAxisMinimumValue": None,
                "yAxisScale": "linear", "horizontalLines": [],
            }, "additional": [], "showMultiplePanels": False},
        } if trend else {"table__enableRenderLinks": False}
        tiles.append({
            "id": uid("tile-" + str(index)), "title": title,
            "visualType": "timechart" if trend else "table",
            "pageId": alert_page_id if alert_setup else page_id,
            "layout": {"x": 0 if alert_setup else (index % 2) * 12,
                       "y": 0 if alert_setup else (index // 2) * 7,
                       "width": 12, "height": 7},
            "queryRef": {"kind": "query", "queryId": query_id},
            "visualOptions": options,
        })
        queries.append({
            "id": query_id, "text": query, "usedVariables": [],
            "dataSource": {"kind": "inline", "dataSourceId": source_id},
        })
    return definition({"RealTimeDashboard.json": {
        "$schema": "https://pbiadx.powerbi.com/static/d/schema/52/dashboard.json",
        "schema_version": "52", "title": "rtd_lsp_plant",
        "autoRefresh": {"enabled": True, "minInterval": "1m"},
        "pages": [{"id": page_id, "name": "Live plant - synthetic data"},
                  {"id": alert_page_id, "name": "Alert setup"}],
        "tiles": tiles, "queries": queries, "parameters": [], "baseQueries": [],
        "dataSources": [{
            "id": source_id, "name": "kqldb_lsp_plant", "clusterUri": cluster_uri,
            "database": database_id, "kind": "manual-kusto", "scopeId": "kusto",
        }],
    }})
