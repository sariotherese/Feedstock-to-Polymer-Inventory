"""Deterministic, synthetic plant data from LSP_Fabric_Demo_Build_Spec.pdf."""

from datetime import date, datetime, time, timedelta
import random

SCHEMAS = {
    "dim_date": "date_key int, date date, year int, month int, day int, week int, day_name string",
    "dim_shift": "shift_id string, shift_name string, start_time string, end_time string",
    "dim_asset": "asset_id string, asset_name string, asset_type string, capacity_tons double, min_level_tons double, max_level_tons double",
    "dim_material": "material_id string, material_name string, material_type string, product_family string, application string",
    "dim_measure": "measure_id string, measure_name string, unit string, source_system string",
    "fact_plant_data": "date_key int, shift_id string, asset_id string, material_id string, measure_id string, value double, source_ts timestamp",
}

ASSETS = [
    ("T-ETH-01", "Ethane Tank 1", "Tank", 55000.0, 8000.0, 52000.0),
    ("T-ETH-02", "Ethane Tank 2", "Tank", 55000.0, 8000.0, 52000.0),
    ("T-PRO-01", "Propane Tank 1", "Tank", 40000.0, 5000.0, 38000.0),
    ("T-NAP-01", "Naphtha Tank 1", "Tank", 60000.0, 8000.0, 57000.0),
    ("CRK-01", "Olefins Cracker", "Cracker", 1350000.0, None, None),
    ("HDPE-01", "HDPE Plant", "Polymer Plant", None, None, None),
    ("LLDPE-01", "LLDPE Plant", "Polymer Plant", None, None, None),
    ("PP-01", "PP Plant", "Polymer Plant", None, None, None),
    ("WH-01", "Finished Goods Warehouse", "Warehouse", None, None, None),
]
MATERIALS = [
    ("ETHANE", "Ethane", "Feedstock", "Ethane", None),
    ("PROPANE", "Propane", "Feedstock", "Propane", None),
    ("NAPHTHA", "Naphtha", "Feedstock", "Naphtha", None),
    ("ETHYLENE", "Ethylene", "Intermediate", "Ethylene", None),
    ("PROPYLENE", "Propylene", "Intermediate", "Propylene", None),
    ("BUTADIENE", "1,3-Butadiene", "Intermediate", "Butadiene", None),
    ("OTHERS", "Other cracker products", "Byproduct", "Others", "Fuel gas, pyrolysis gasoline, etc."),
    ("HDPE-BM", "HDPE Blow Molding", "Polymer", "HDPE", "Bottles and containers"),
    ("HDPE-PI", "HDPE Pipe", "Polymer", "HDPE", "Water and gas pipes"),
    ("LLDPE-FM", "LLDPE Film", "Polymer", "LLDPE", "Packaging and agri film"),
    ("PP-IM", "PP Injection", "Polymer", "PP", "Food containers and auto parts"),
    ("PP-RA", "PP Raffia", "Polymer", "PP", "Woven sacks"),
]
MEASURES = [
    ("STOCK_SENSOR", "Tank stock (sensor, end of shift)", "tons", "Plant historian"),
    ("FEED", "Cracker feed", "tons", "Plant historian / DCS"),
    ("OUTPUT", "Cracker output", "tons", "Plant historian / DCS"),
    ("PURITY", "Feedstock purity", "%", "LIMS (lab)"),
    ("PRODUCTION", "Polymer production", "tons", "MES"),
    ("FG_STOCK", "Finished goods stock (end of shift)", "tons", "Warehouse system"),
    ("SHIPPED", "Finished goods shipped", "tons", "Warehouse system / ERP"),
    ("STOCK_BOOK", "ERP book stock (end of day)", "tons", "ERP"),
]
TANK_MATERIAL = {
    "T-ETH-01": "ETHANE", "T-ETH-02": "ETHANE",
    "T-PRO-01": "PROPANE", "T-NAP-01": "NAPHTHA",
}
BASE_FEED = {"ETHANE": 2740.0 / 3, "PROPANE": 587.0 / 3, "NAPHTHA": 587.0 / 3}
YIELDS = {"ETHANE": (0.78, 0.03, 0.02), "PROPANE": (0.40, 0.16, 0.03),
          "NAPHTHA": (0.30, 0.15, 0.05)}


def polymer_production(ethylene: float, propylene: float) -> dict[str, float]:
    return {
        "HDPE-BM": ethylene * 0.97 * 0.55 * 0.60,
        "HDPE-PI": ethylene * 0.97 * 0.55 * 0.40,
        "LLDPE-FM": ethylene * 0.97 * 0.45,
        "PP-IM": propylene * 0.97 * 0.50,
        "PP-RA": propylene * 0.97 * 0.50,
    }


def generate(end_date: date | None = None, seed: int = 42) -> dict[str, list[tuple]]:
    rng = random.Random(seed)
    end_date = end_date or date.today()
    start = end_date - timedelta(days=29)
    tables = {
        "dim_date": [], "dim_shift": [
            ("A", "Morning", "06:00", "14:00"),
            ("B", "Afternoon", "14:00", "22:00"),
            ("C", "Night", "22:00", "06:00"),
        ],
        "dim_asset": list(ASSETS), "dim_material": list(MATERIALS),
        "dim_measure": list(MEASURES), "fact_plant_data": [],
    }
    stocks = {"T-ETH-01": 35000.0, "T-ETH-02": 25000.0,
              "T-PRO-01": 20000.0, "T-NAP-01": 30000.0}
    base_outputs = [sum(BASE_FEED[m] * YIELDS[m][i] for m in BASE_FEED) for i in range(3)]
    fg = {grade: tons * 9 for grade, tons in polymer_production(*base_outputs[:2]).items()}
    refilled_ethane = False

    for day_index in range(1, 31):
        current = start + timedelta(days=day_index - 1)
        key = int(current.strftime("%Y%m%d"))
        tables["dim_date"].append((key, current, current.year, current.month, current.day,
                                   current.isocalendar().week, current.strftime("%A")))
        for shift, end_hour, day_offset in [("A", 14, 0), ("B", 22, 0), ("C", 6, 1)]:
            stamp = datetime.combine(current + timedelta(days=day_offset), time(end_hour))

            def emit(asset: str, material: str, measure: str, value: float) -> None:
                tables["fact_plant_data"].append(
                    (key, shift, asset, material, measure, float(value), stamp)
                )

            feeds = {m: v * rng.uniform(0.97, 1.03) for m, v in BASE_FEED.items()}
            for material, tons in feeds.items():
                emit("CRK-01", material, "FEED", tons)
            outputs = [sum(feeds[m] * YIELDS[m][i] for m in feeds) for i in range(3)]
            if day_index in (25, 26):
                outputs[0] -= feeds["ETHANE"] * YIELDS["ETHANE"][0] * 0.04
            others = sum(feeds.values()) - sum(outputs)
            if day_index == 27:
                others -= sum(feeds.values()) * 0.03
            for material, tons in zip(
                ["ETHYLENE", "PROPYLENE", "BUTADIENE", "OTHERS"], outputs + [others]
            ):
                emit("CRK-01", material, "OUTPUT", tons)
            purity = rng.uniform(93.7, 94.3) if day_index in (25, 26) else rng.uniform(97.5, 99.0)
            emit("CRK-01", "ETHANE", "PURITY", purity)

            # Balanced withdrawal keeps both ethane tanks above their minimum levels.
            ethane_total = stocks["T-ETH-01"] + stocks["T-ETH-02"]
            for tank in ("T-ETH-01", "T-ETH-02"):
                stocks[tank] -= feeds["ETHANE"] * stocks[tank] / ethane_total
            if sum(stocks[t] for t in ("T-ETH-01", "T-ETH-02")) < 25000 and not refilled_ethane:
                stocks["T-ETH-01"] += 25000
                stocks["T-ETH-02"] += 25000
                refilled_ethane = True
            for tank, material in [("T-PRO-01", "PROPANE"), ("T-NAP-01", "NAPHTHA")]:
                stocks[tank] -= feeds[material]
                asset = next(a for a in ASSETS if a[0] == tank)
                if stocks[tank] < asset[4] + 2000:
                    stocks[tank] = asset[3] * 0.90
            for tank, stock in stocks.items():
                emit(tank, TANK_MATERIAL[tank], "STOCK_SENSOR", stock)
                if shift == "C":
                    multiplier = 1.03 if day_index == 28 and "ETH" in tank else rng.uniform(0.995, 1.005)
                    emit(tank, TANK_MATERIAL[tank], "STOCK_BOOK", stock * multiplier)

            for grade, tons in polymer_production(*outputs[:2]).items():
                plant = "HDPE-01" if grade.startswith("HDPE") else (
                    "LLDPE-01" if grade.startswith("LLDPE") else "PP-01"
                )
                shipped = tons * rng.uniform(0.95, 1.0)
                fg[grade] += tons - shipped
                emit(plant, grade, "PRODUCTION", tons)
                emit("WH-01", grade, "SHIPPED", shipped)
                emit("WH-01", grade, "FG_STOCK", fg[grade])
    return tables
