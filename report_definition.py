"""Five-page PBIR report with native visuals bound to the Direct Lake measures."""

from fabric_client import WORKSPACE_ID, definition

BASE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
MEASURE_TABLE = "dim_measure"


def field(table: str, column: str, measure: bool = False) -> dict:
    return {("Measure" if measure else "Column"): {
        "Expression": {"SourceRef": {"Entity": table}}, "Property": column,
    }}


def projection(table: str, column: str, measure: bool = False) -> dict:
    return {"field": field(table, column, measure),
            "queryRef": f"{table}.{column}", "nativeQueryRef": column}


def literal(value: str) -> dict:
    return {"expr": {"Literal": {"Value": "'" + value.replace("'", "''") + "'"}}}


def visual(name: str, kind: str, title: str, x: int, y: int, w: int, h: int,
           roles: dict[str, list[dict]] | None = None) -> dict:
    result = {
        "$schema": BASE + "visualContainer/2.5.0/schema.json", "name": name,
        "position": {"x": x, "y": y, "width": w, "height": h, "z": 0, "tabOrder": 0},
        "visual": {
            "visualType": kind,
            "visualContainerObjects": {
                "title": [{"properties": {
                    "show": {"expr": {"Literal": {"Value": "true"}}},
                    "text": literal(title), "fontFamily": literal("Segoe UI Semibold"),
                    "fontSize": {"expr": {"Literal": {"Value": "12D"}}},
                }}],
                "background": [{"properties": {
                    "show": {"expr": {"Literal": {"Value": "true"}}},
                    "color": {"solid": {"color": literal("#FFFFFF")}},
                    "transparency": {"expr": {"Literal": {"Value": "0D"}}},
                }}],
            },
            "drillFilterOtherVisuals": True,
        },
    }
    if roles:
        result["visual"]["query"] = {
            "queryState": {role: {"projections": values} for role, values in roles.items()}
        }
    return result


def report(model_id: str) -> dict:
    pages = [
        ("overview", "Plant Overview"),
        ("feedstock", "Feedstock & Days of Cover"),
        ("yield", "Yield"),
        ("balance", "Mass Balance & Inventory Accuracy"),
        ("goods", "Finished Goods"),
    ]
    parts = {
        "definition.pbir": {
            "version": "4.0", "datasetReference": {"byConnection": {
                "connectionString": (
                    f"Data Source=powerbi://api.powerbi.com/v1.0/myorg/smec-dataplatform-e5;"
                    f"Initial Catalog={model_id};Integrated Security=ClaimsToken"
                ),
                "pbiServiceModelId": None, "pbiModelVirtualServerName": "sobe_wowvirtualserver",
                "pbiModelDatabaseName": model_id, "name": "EntityDataSource",
                "connectionType": "pbiServiceXmlaStyleLive",
            }},
        },
        "definition/version.json": {
            "$schema": BASE + "versionMetadata/1.0.0/schema.json", "version": "2.0.0",
        },
        "definition/report.json": {
            "$schema": BASE + "report/2.0.0/schema.json", "themeCollection": {},
            "settings": {"useStylableVisualContainerHeader": True,
                         "exportDataMode": "AllowSummarized", "defaultDrillFilterOtherVisuals": True},
        },
        "definition/pages/pages.json": {
            "$schema": BASE + "pagesMetadata/1.0.0/schema.json",
            "pageOrder": [name for name, title in pages], "activePageName": "overview",
        },
    }

    def add(page: str, item: dict) -> None:
        parts[f"definition/pages/{page}/visuals/{item['name']}/visual.json"] = item

    def m(name: str) -> dict:
        return projection(MEASURE_TABLE, name, True)

    for page_name, title in pages:
        parts[f"definition/pages/{page_name}/page.json"] = {
            "$schema": BASE + "page/2.0.0/schema.json",
            "name": page_name, "displayName": title,
            "displayOption": "FitToPage", "width": 1280, "height": 720,
            "objects": {"background": [{"properties": {
                "color": {"solid": {"color": literal("#EEF3F8")}},
                "transparency": {"expr": {"Literal": {"Value": "0D"}}},
            }}]},
        }
        heading = visual(page_name + "_heading", "textbox", title, 24, 12, 1000, 76)
        heading["visual"]["objects"] = {"general": [{"properties": {"paragraphs": [
            {"textRuns": [{"value": "LSP  |  " + title, "textStyle": {
                "fontFamily": "Segoe UI Semibold", "fontSize": "23pt", "color": "#13334C",
            }}]},
            {"textRuns": [{"value": "FEEDSTOCK TO POLYMER  /  SYNTHETIC ILLUSTRATIVE DATA",
                          "textStyle": {"fontFamily": "Segoe UI", "fontSize": "10pt",
                                        "color": "#546E7A"}}]},
        ]}}]}
        heading["visual"]["visualContainerObjects"]["title"] = [
            {"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}
        ]
        add(page_name, heading)
        add(page_name, visual(page_name + "_date", "slicer", "Date", 1010, 12, 246, 76,
                              {"Values": [projection("dim_date", "date")]}))

    for index, name in enumerate([
        "Days of Cover", "Ethylene Yield %", "Mass Balance Gap %", "Inventory Accuracy %"
    ]):
        add("overview", visual("kpi_" + str(index), "card", name, 24 + index * 314, 106,
                               296, 150, {"Values": [m(name)]}))
    add("overview", visual("overview_yield", "lineChart", "Yield & feedstock quality",
                           24, 278, 608, 408, {
                               "Category": [projection("dim_date", "date")],
                               "Y": [m("Ethylene Yield %"), m("Ethane Purity %")],
                           }))
    add("overview", visual("overview_cover", "lineChart", "Days of ethane cover",
                           650, 278, 606, 408, {
                               "Category": [projection("dim_date", "date")],
                               "Y": [m("Days of Cover")],
                           }))
    add("feedstock", visual("stock_trend", "lineChart", "Ethane stock by tank (t)",
                            24, 110, 815, 280, {
                                "Category": [projection("dim_date", "date")],
                                "Y": [m("Ethane Stock (t)")],
                                "Series": [projection("dim_asset", "asset_name")],
                            }))
    add("feedstock", visual("feed_mix", "stackedAreaChart", "Cracker feed mix (t)",
                            24, 410, 815, 276, {
                                "Category": [projection("dim_date", "date")],
                                "Y": [m("Total Feed (t)")],
                                "Series": [projection("dim_material", "material_name")],
                            }))
    add("feedstock", visual("shift", "slicer", "Shift", 860, 110, 396, 200,
                            {"Values": [projection("dim_shift", "shift_name")]}))
    add("feedstock", visual("ethane_stock", "card", "Latest ethane stock (t)", 860, 330, 396, 160,
                            {"Values": [m("Ethane Stock (t)")]}))
    add("feedstock", visual("cover", "card", "Days of cover", 860, 510, 396, 176,
                            {"Values": [m("Days of Cover")]}))
    add("yield", visual("yield_purity", "lineChart", "Ethylene yield vs ethane purity",
                        24, 110, 1232, 370, {
                            "Category": [projection("dim_date", "date")],
                            "Y": [m("Ethylene Yield %"), m("Ethane Purity %")],
                        }))
    add("yield", visual("yield_daily", "tableEx", "Daily yield, purity & trailing baseline",
                        24, 500, 1232, 186, {
                            "Values": [projection("dim_date", "date"), m("Ethylene Yield %"),
                                       m("Ethane Purity %"), m("Yield 7D Baseline %"),
                                       m("Yield Deviation %")],
                        }))
    add("balance", visual("balance_gap", "lineChart", "Cracker mass balance gap",
                          24, 110, 1232, 260, {
                              "Category": [projection("dim_date", "date")],
                              "Y": [m("Mass Balance Gap %")],
                          }))
    add("balance", visual("stock_comparison", "clusteredColumnChart",
                          "Latest shift-C sensor vs ERP book stock by tank (t)",
                          24, 390, 815, 296, {
                              "Category": [projection("dim_asset", "asset_name")],
                              "Y": [m("Sensor Stock (t)"), m("Book Stock (t)")],
                          }))
    add("balance", visual("accuracy", "card", "Inventory accuracy",
                          860, 390, 396, 296, {"Values": [m("Inventory Accuracy %")]}))
    goods = parts["definition/pages/goods/page.json"]
    goods["filterConfig"] = {"filters": [{
        "name": "polymer_only", "field": field("dim_material", "material_type"),
        "type": "Categorical", "filter": {
            "Version": 2, "From": [{"Name": "m", "Entity": "dim_material", "Type": 0}],
            "Where": [{"Condition": {"In": {
                "Expressions": [{"Column": {
                    "Expression": {"SourceRef": {"Source": "m"}}, "Property": "material_type",
                }}],
                "Values": [[{"Literal": {"Value": "'Polymer'"}}]],
            }}}],
        },
    }]}
    add("goods", visual("fg_stock", "clusteredColumnChart", "Finished goods stock by family (t)",
                        24, 110, 608, 290, {
                            "Category": [projection("dim_material", "product_family")],
                            "Y": [m("FG Stock (t)")],
                        }))
    add("goods", visual("fg_days", "clusteredColumnChart", "Finished goods days of stock",
                        650, 110, 606, 290, {
                            "Category": [projection("dim_material", "product_family")],
                            "Y": [m("FG Days of Stock")],
                        }))
    add("goods", visual("fg_grades", "tableEx", "Family & grade detail",
                        24, 420, 1232, 266, {
                            "Values": [projection("dim_material", "product_family"),
                                       projection("dim_material", "material_name"),
                                       m("FG Stock (t)"), m("FG Days of Stock"), m("Shipped (t)")],
                        }))
    return definition(parts, "PBIR")
