"""Direct Lake model and context-aware snapshot/flow DAX measures."""

from fabric_client import definition
from plant_data import SCHEMAS


def measures() -> list[dict]:
    expressions = {
        "Value": "SUM(fact_plant_data[value])",
        "Total Feed (t)": 'CALCULATE([Value], dim_measure[measure_id] = "FEED")',
        "Ethane Feed (t)": 'CALCULATE([Total Feed (t)], dim_material[material_id] = "ETHANE")',
        "Total Output (t)": 'CALCULATE([Value], dim_measure[measure_id] = "OUTPUT")',
        "Ethylene Output (t)": 'CALCULATE([Total Output (t)], dim_material[material_id] = "ETHYLENE")',
        "Ethylene Yield %": "DIVIDE([Ethylene Output (t)], [Total Feed (t)])",
        "Mass Balance Gap %": "DIVIDE([Total Feed (t)] - [Total Output (t)], [Total Feed (t)])",
        "Ethane Purity %": (
            'DIVIDE(CALCULATE(AVERAGE(fact_plant_data[value]), '
            'dim_measure[measure_id] = "PURITY"), 100)'
        ),
        "Days of Cover": "DIVIDE([Ethane Stock (t)], [Avg Daily Ethane Feed (t)])",
        "Inventory Accuracy %": (
            "VAR Sensor = [Sensor Stock (t)] VAR Book = [Book Stock (t)] "
            "RETURN IF(NOT ISBLANK(Sensor) && NOT ISBLANK(Book) && Book <> 0, "
            "1 - DIVIDE(ABS(Sensor - Book), Book))"
        ),
        "Total Production (t)": 'CALCULATE([Value], dim_measure[measure_id] = "PRODUCTION")',
        "Shipped (t)": 'CALCULATE([Value], dim_measure[measure_id] = "SHIPPED")',
        "FG Days of Stock": "DIVIDE([FG Stock (t)], [Avg Daily Shipped (t)])",
        "Yield 7D Baseline %": (
            "VAR Anchor = MAX(dim_date[date]) "
            "RETURN CALCULATE(AVERAGEX(VALUES(dim_date[date]), [Ethylene Yield %]), "
            "REMOVEFILTERS(dim_date), DATESBETWEEN(dim_date[date], Anchor - 7, Anchor - 1))"
        ),
        "Yield Deviation %": "DIVIDE([Ethylene Yield %] - [Yield 7D Baseline %], [Yield 7D Baseline %])",
    }
    for name, measure, material, end_of_day in [
        ("Ethane Stock (t)", "STOCK_SENSOR", "ETHANE", False),
        ("Sensor Stock (t)", "STOCK_SENSOR", None, True),
        ("Book Stock (t)", "STOCK_BOOK", None, True),
        ("FG Stock (t)", "FG_STOCK", None, False),
    ]:
        filters = f'dim_measure[measure_id] = "{measure}"'
        if material:
            filters += f', dim_material[material_id] = "{material}"'
        if end_of_day:
            expressions[name] = (
                "VAR LatestDay = MAX(dim_date[date_key]) "
                f"RETURN CALCULATE([Value], {filters}, dim_date[date_key] = LatestDay, "
                'REMOVEFILTERS(dim_shift), dim_shift[shift_id] = "C")'
            )
        else:
            expressions[name] = (
                f"VAR LatestStamp = CALCULATE(MAX(fact_plant_data[source_ts]), {filters}) "
                f"RETURN CALCULATE([Value], {filters}, fact_plant_data[source_ts] = LatestStamp)"
            )
    expressions["Avg Daily Ethane Feed (t)"] = (
        "VAR Anchor = MAX(dim_date[date]) "
        "RETURN CALCULATE(AVERAGEX(VALUES(dim_date[date]), [Ethane Feed (t)]), "
        "REMOVEFILTERS(dim_date), DATESBETWEEN(dim_date[date], Anchor - 6, Anchor))"
    )
    expressions["Avg Daily Shipped (t)"] = (
        "AVERAGEX(VALUES(dim_date[date]), [Shipped (t)])"
    )
    return [
        {
            "name": name, "expression": expression,
            "formatString": "0.0%" if name.endswith("%") else (
                "0.0" if "Days" in name else "#,0.0"
            ),
            "displayFolder": "Inventory & Cover" if any(
                w in name for w in ["Stock", "Cover", "Accuracy", "Shipped"]
            ) else "Production & Yield",
            **({"isHidden": True} if name == "Value" else {}),
        }
        for name, expression in expressions.items()
    ]


def model_definition(sql_server: str, sql_database: str) -> dict:
    tables = []
    for table_name, schema in SCHEMAS.items():
        columns = []
        for column_spec in schema.split(", "):
            name, dtype = column_spec.split()
            column = {
                "name": name, "sourceColumn": name,
                "dataType": {"int": "int64", "double": "double", "date": "dateTime",
                             "timestamp": "dateTime", "string": "string"}[dtype],
                "summarizeBy": "none",
            }
            if name.endswith("_id") or name == "date_key" or (
                table_name == "fact_plant_data" and name in {"value", "source_ts"}
            ):
                column["isHidden"] = True
            if table_name == "dim_date" and name == "date":
                column.update(isKey=True, formatString="dd MMM yyyy")
            columns.append(column)
        table = {
            "name": table_name, "columns": columns,
            "partitions": [{
                "name": table_name, "mode": "directLake",
                "source": {"type": "entity", "schemaName": "dbo", "entityName": table_name,
                           "expressionSource": "DatabaseQuery"},
            }],
        }
        if table_name == "dim_date":
            table["dataCategory"] = "Time"
        if table_name == "dim_measure":
            table["measures"] = measures()
        tables.append(table)
    return definition({
        "definition.pbism": {"version": "4.0", "settings": {}},
        "model.bim": {
            "compatibilityLevel": 1604,
            "model": {
                "culture": "en-US", "defaultPowerBIDataSourceVersion": "powerBI_V3",
                "expressions": [{
                    "name": "DatabaseQuery", "kind": "m",
                    "expression": [
                        "let",
                        f'    Source = Sql.Database("{sql_server}", "{sql_database}")',
                        "in", "    Source",
                    ],
                }],
                "tables": tables,
                "relationships": [
                    {"name": "fact_to_" + dim, "fromTable": "fact_plant_data",
                     "fromColumn": key, "toTable": dim, "toColumn": key,
                     "fromCardinality": "many", "toCardinality": "one",
                     "crossFilteringBehavior": "oneDirection", "isActive": True}
                    for dim, key in [
                        ("dim_date", "date_key"), ("dim_shift", "shift_id"),
                        ("dim_asset", "asset_id"), ("dim_material", "material_id"),
                        ("dim_measure", "measure_id"),
                    ]
                ],
            },
        },
    }, "TMSL")
