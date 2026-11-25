"""Stopped Activator rules. Recipients must be configured before enabling delivery."""

import json

from fabric_client import WORKSPACE_ID, definition
from realtime_definitions import uid

PLANT_SIGNALS = """
let f = materialize(external_table('PlantHistory')
    | extend shift_date=make_datetime(toint(date_key / 10000),
                                     toint(date_key / 100) % 100, toint(date_key % 100)));
let last_day = toscalar(f | summarize max(shift_date));
let last_key = toscalar(f | summarize max(date_key));
let daily = materialize(f | summarize
    feed=sumif(value, measure_id == 'FEED'),
    output=sumif(value, measure_id == 'OUTPUT'),
    ethane_feed=sumif(value, measure_id == 'FEED' and material_id == 'ETHANE'),
    ethylene=sumif(value, measure_id == 'OUTPUT' and material_id == 'ETHYLENE')
    by date_key, shift_date | extend ethylene_yield=ethylene/feed);
let baseline = toscalar(daily | where shift_date between ((last_day - 7d) .. (last_day - 1d))
    | summarize avg(ethylene_yield));
let avg_feed = toscalar(daily | where shift_date between ((last_day - 6d) .. last_day)
    | summarize avg(ethane_feed));
let latest_stock_ts = toscalar(f | where measure_id == 'STOCK_SENSOR' and material_id == 'ETHANE'
    | summarize max(source_ts));
let stock = toscalar(f | where measure_id == 'STOCK_SENSOR' and material_id == 'ETHANE'
    and source_ts == latest_stock_ts | summarize sum(value));
let temperature = toscalar(TankReadings | where reading_ts > ago(5m) and tank_id startswith 'T-ETH'
    | summarize arg_max(reading_ts, temperature_c) by tank_id | summarize max(temperature_c));
daily | where date_key == last_key
| project reading_ts=now(), plant_id='LSP', days_of_cover=stock/avg_feed,
          yield_loss_pct=1.0-ethylene_yield/baseline,
          mass_balance_gap_pct=(feed-output)/feed,
          ethane_temperature_c=temperature
""".strip()

RULES = [
    ("Low days of cover", "days_of_cover", "IsLessThan", 15.0, 0,
     "TeamsMessage", "Supply & Operations", "Days of feedstock cover below 15"),
    ("Yield drop", "yield_loss_pct", "IsGreaterThan", 0.04, 21600000,
     "TeamsMessage", "Process Engineering", "Cracker yield 4% below target for 6 hours"),
    ("Mass balance gap", "mass_balance_gap_pct", "IsGreaterThan", 0.02, 0,
     "EmailMessage", "Operations & Finance", "Cracker mass balance gap exceeds 2%"),
    ("Tank temperature", "ethane_temperature_c", "IsGreaterThan", -85.0, 0,
     "TeamsMessage", "Control Room", "Ethane tank temperature above -85 C"),
]


def activator(database_id: str, cluster_uri: str, dashboard_id: str) -> dict:
    container_id, source_id = uid("alert-container"), uid("alert-source")
    event_id, object_id = uid("alert-event"), uid("alert-object")
    parent = {"targetUniqueIdentifier": container_id}
    object_ref = {"targetUniqueIdentifier": object_id}
    entities = []

    def entity(key: str, kind: str, payload: dict) -> None:
        entities.append({"uniqueIdentifier": key, "type": kind, "payload": payload})

    def arg(name: str, value, dtype: str = "string") -> dict:
        return {"name": name, "type": dtype, "value": value}

    def row(name: str, kind: str, arguments: list[dict]) -> dict:
        return {"name": name, "kind": kind, "arguments": arguments}

    def step(name: str, rows: list[dict], salt: str) -> dict:
        return {"name": name, "id": uid(salt + name), "rows": rows}

    def reference(name: str, kind: str, key: str) -> dict:
        return {"name": name, "kind": kind, "type": "complex",
                "arguments": [arg("entityId", key)]}

    def instance(template: str, steps: list[dict]) -> str:
        return json.dumps({"templateId": template, "templateVersion": "1.3.1", "steps": steps})

    entity(container_id, "container-v1", {"name": "LSP plant alerts", "type": "kqlQueries"})
    entity(source_id, "kqlSource-v1", {
        "name": "Plant signals - latest shift and live ethane temperature",
        "parentContainer": parent,
        "runSettings": {"executionIntervalInSeconds": 60},
        "query": {"queryString": "PlantSignals()"},
        "eventhouseItem": {"databaseName": database_id, "clusterHostName": cluster_uri},
        "eventTimeSettings": {"ingestionDelayInSeconds": 0, "timeFieldName": "reading_ts"},
        "queryParameters": [],
        "metadata": {"workspaceId": WORKSPACE_ID, "dashboardId": dashboard_id,
                     "visualId": uid("tile-4")},
    })
    entity(event_id, "timeSeriesView-v1", {
        "name": "Plant signal events", "parentContainer": parent,
        "definition": {"type": "Event", "instance": instance("SourceEvent", [
            step("SourceEventStep", [row("SourceSelector", "SourceReference",
                                        [arg("entityId", source_id)])], "source"),
        ])},
    })
    entity(object_id, "timeSeriesView-v1", {
        "name": "LSP Plant", "parentContainer": parent, "definition": {"type": "Object"},
    })
    identity_id, tuple_id, split_id = (
        uid("alert-plant-id"), uid("alert-identity"), uid("alert-split"),
    )
    entity(identity_id, "timeSeriesView-v1", {
        "name": "plant_id", "parentContainer": parent, "parentObject": object_ref,
        "definition": {"type": "Attribute", "instance": instance("IdentityPartAttribute", [
            step("IdPartStep", [row("TypeAssertion", "TypeAssertion", [
                arg("op", "Text"), arg("format", ""),
            ])], "plant-id"),
        ])},
    })
    entity(tuple_id, "timeSeriesView-v1", {
        "name": "Plant identity", "parentContainer": parent, "parentObject": object_ref,
        "definition": {"type": "Attribute", "instance": instance("IdentityTupleAttribute", [
            step("IdStructureStep", [row("IdPart", "IdPart", [
                reference("idPart", "AttributeReference", identity_id),
            ])], "plant-identity"),
        ])},
    })
    entity(split_id, "timeSeriesView-v1", {
        "name": "Signals by plant", "parentContainer": parent, "parentObject": object_ref,
        "definition": {"type": "Event", "instance": instance("SplitEvent", [
            step("SplitEventStep", [
                row("EventSelector", "Event", [reference("event", "EventReference", event_id)]),
                row("FieldIdMapping", "FieldIdMapping", [
                    arg("fieldName", "plant_id"), reference("idPart", "AttributeReference", identity_id),
                ]),
                row("SplitEventOptions", "EventOptions", [arg("isAuthoritative", True, "boolean")]),
            ], "split"),
        ])},
    })
    for name, column, comparison, threshold, duration, action, audience, headline in RULES:
        attribute_id = uid("attribute-" + column)
        entity(attribute_id, "timeSeriesView-v1", {
            "name": column, "parentContainer": parent, "parentObject": object_ref,
            "definition": {"type": "Attribute", "instance": instance("BasicEventAttribute", [
                step("EventSelectStep", [
                    row("EventSelector", "Event", [reference("event", "EventReference", split_id)]),
                    row("EventFieldSelector", "EventField", [arg("fieldName", column)]),
                ], column),
                step("EventComputeStep", [row("TypeAssertion", "TypeAssertion", [
                    arg("op", "Number"), arg("format", ""),
                ])], column),
            ])},
        })
        detection = [
            row("NumberValueCondition", "NumberValueCondition", [
                arg("op", comparison), arg("threshold", threshold, "number"),
            ]),
        ]
        if duration:
            detection.append(row("SustainedPeriodOption", "SustainedPeriodOption", [
                arg("period", duration, "timeSpan"),
            ]))
        else:
            detection.append(row("OccurrenceOption", "EachTime", []))
        recipients = {"name": "sentTo" if action == "EmailMessage" else "recipients",
                      "type": "array", "values": []}
        headline_arg = {"name": "headline", "type": "array",
                        "values": [{"type": "string", "value": headline}]}
        actions = [
            arg("messageLocale", "en-us"), recipients, headline_arg,
            {"name": "optionalMessage", "type": "array", "values": [{
                "type": "string", "value": f"SYNTHETIC DEMO. Intended audience: {audience}.",
            }]},
            {"name": "additionalInformation", "type": "array", "values": []},
        ]
        if action == "EmailMessage":
            actions.extend([
                {"name": "copyTo", "type": "array", "values": []},
                {"name": "bCCTo", "type": "array", "values": []},
                {"name": "subject", "type": "array",
                 "values": [{"type": "string", "value": headline}]},
            ])
        entity(uid("rule-" + name), "timeSeriesView-v1", {
            "name": name, "parentContainer": parent, "parentObject": object_ref,
            "definition": {"type": "Rule", "instance": instance("AttributeTrigger", [
                step("ScalarSelectStep", [
                    row("AttributeSelector", "Attribute",
                        [reference("attribute", "AttributeReference", attribute_id)]),
                ], name),
                step("ScalarDetectStep", detection, name),
                step("ActStep", [row("EmailBinding" if action == "EmailMessage" else "TeamsBinding",
                                     action, actions)], name),
            ]), "settings": {"shouldRun": False, "shouldApplyRuleOnUpdate": False}},
        })
    return definition({"ReflexEntities.json": entities})
