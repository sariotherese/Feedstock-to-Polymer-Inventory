"""Fabric notebook sources; no external repository imports needed in Fabric."""

from pathlib import Path

from fabric_client import WORKSPACE_ID, definition


def notebook(cells: list[tuple[str, str]], lakehouse_id: str) -> dict:
    return definition({"notebook-content.ipynb": {
        "nbformat": 4, "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {"display_name": "Synapse PySpark", "language": "python",
                           "name": "synapse_pyspark"},
            "language_info": {"name": "python"},
            "dependencies": {"lakehouse": {
                "default_lakehouse": lakehouse_id,
                "default_lakehouse_name": "lh_lsp_plant",
                "default_lakehouse_workspace_id": WORKSPACE_ID,
                "known_lakehouses": [{"id": lakehouse_id}],
            }},
        },
        "cells": [
            dict(cell_type=kind, metadata={}, source=source.splitlines(keepends=True),
                 **({"outputs": [], "execution_count": None} if kind == "code" else {}))
            for kind, source in cells
        ],
    }}, "ipynb")


def generator_notebook(lakehouse_id: str) -> dict:
    source = Path(__file__).with_name("plant_data.py").read_text(encoding="utf-8")
    write = '''
from datetime import datetime
from zoneinfo import ZoneInfo

tables = generate(datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date())
spark.conf.set("spark.sql.session.timeZone", "Asia/Ho_Chi_Minh")
spark.conf.set("spark.sql.parquet.vorder.enabled", "true")
for name, rows in tables.items():
    df = spark.createDataFrame(rows, SCHEMAS[name])
    df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(name)
    print(f"{name}: {spark.table(name).count()} rows")

fact = spark.table("fact_plant_data")
assert fact.count() == 2550, "Expected exactly 85 fact rows per day"
assert fact.select("date_key", "shift_id", "asset_id", "material_id", "measure_id").distinct().count() == 2550
assert len(tables) == 6
display(spark.sql("""
SELECT date_key,
       SUM(CASE WHEN measure_id='FEED' THEN value ELSE 0 END) AS feed_tons,
       SUM(CASE WHEN measure_id='OUTPUT' THEN value ELSE 0 END) AS output_tons,
       AVG(CASE WHEN measure_id='PURITY' THEN value END) AS ethane_purity_pct
FROM fact_plant_data GROUP BY date_key ORDER BY date_key
"""))
'''
    return notebook([
        ("markdown", "# Feedstock-to-Polymer Inventory & Yield\n"
         "Synthetic illustrative data, not LSP operational data. Seed 42; 30 shift-dates "
         "ending today in Vietnam. Shift C ends at 06:00 the following day. "
         "The last shift is simulated, not a claim of actual completed production."),
        ("code", source), ("code", write),
    ], lakehouse_id)


def simulator_notebook(lakehouse_id: str, eventstream_id: str, source_id: str) -> dict:
    source = Path(__file__).with_name("stream_simulator.py").read_text(encoding="utf-8")
    connect = f'''
import notebookutils
from pyspark.sql import functions as F
from pyspark.sql.window import Window

token = notebookutils.credentials.getToken("pbi")
response = requests.get(
    "https://api.fabric.microsoft.com/v1/workspaces/{WORKSPACE_ID}"
    "/eventstreams/{eventstream_id}/sources/{source_id}/connection",
    headers={{"Authorization": "Bearer " + token}}, timeout=60)
response.raise_for_status()
connection = response.json()
del token, response
latest = (spark.table("fact_plant_data")
          .filter(F.col("measure_id") == "STOCK_SENSOR")
          .withColumn("rn", F.row_number().over(
              Window.partitionBy("asset_id").orderBy(F.col("source_ts").desc())))
          .filter("rn = 1").select("asset_id", "value").collect())
levels = {{r["asset_id"]: r["value"] for r in latest}}
assert len(levels) == 4, "Run nb_01_generate_sample_data first"
count = simulate(connection, levels, minutes=int(minutes),
                 inject_temperature_alert=bool(inject_temperature_alert))
del connection
notebookutils.notebook.exit(f"Sent {{count}} synthetic tank readings")
'''
    result = notebook([
        ("markdown", "# Live synthetic tank readings\n"
         "Four readings every minute, continuing from the latest sensor snapshots. "
         "Default runtime: 60 minutes; rerun for a demo session. No keys are persisted. "
         "The optional temperature anomaly is OFF by default."),
        ("code", "minutes = 60\ninject_temperature_alert = False\n"),
        ("code", source), ("code", connect),
    ], lakehouse_id)
    import base64
    import json
    content = json.loads(base64.b64decode(result["parts"][0]["payload"]))
    content["cells"][1]["metadata"]["tags"] = ["parameters"]
    return definition({"notebook-content.ipynb": content}, "ipynb")
