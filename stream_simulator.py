"""HTTPS producer for the Fabric Eventstream custom endpoint; secrets stay in memory."""

import base64
import hashlib
import hmac
import json
import random
import time
from datetime import datetime, timezone
from urllib.parse import quote, urlparse

import requests


def send_reading(connection: dict, reading: dict) -> None:
    parts = dict(p.split("=", 1) for p in
                 connection["accessKeys"]["primaryConnectionString"].split(";") if p)
    namespace = connection["fullyQualifiedNamespace"]
    if not namespace.endswith(".servicebus.windows.net"):
        raise ValueError("Expected a Microsoft Event Hubs namespace")
    uri = f"https://{namespace}/{quote(connection['eventHubName'], safe='')}"
    expiry = str(int(time.time()) + 600)
    encoded_uri = quote(uri, safe="")
    signature = quote(base64.b64encode(hmac.new(
        parts["SharedAccessKey"].encode("utf-8"),
        f"{encoded_uri}\n{expiry}".encode("utf-8"), hashlib.sha256,
    ).digest()).decode("ascii"), safe="")
    authorization = (f"SharedAccessSignature sr={encoded_uri}&sig={signature}&se={expiry}"
                     f"&skn={quote(parts['SharedAccessKeyName'], safe='')}")
    response = requests.post(
        uri + "/messages", headers={"Authorization": authorization,
                                    "Content-Type": "application/json"},
        data=json.dumps(reading), timeout=30,
    )
    if not response.ok:
        # Do not include the connection string or request headers in an exception.
        raise RuntimeError(f"Eventstream send failed: HTTP {response.status_code}")


def simulate(connection: dict, levels: dict[str, float], minutes: int = 60,
             interval_seconds: int = 60, inject_temperature_alert: bool = False) -> int:
    if minutes < 1 or interval_seconds < 1:
        raise ValueError("minutes and interval_seconds must be positive")
    rng = random.Random(42)
    sent = 0
    for minute in range(minutes):
        started = time.monotonic()
        for tank in sorted(levels):
            ethane = tank.startswith("T-ETH")
            temperature = rng.uniform(-89.5, -88.5) if ethane else (
                rng.uniform(-42.5, -41.5) if tank == "T-PRO-01" else rng.uniform(27.5, 28.5)
            )
            if inject_temperature_alert and tank == "T-ETH-01" and minute >= 3:
                temperature = -84.5
            reading = {
                "reading_ts": datetime.now(timezone.utc).isoformat(),
                "tank_id": tank, "level_tons": round(levels[tank], 3),
                "temperature_c": round(temperature, 3),
                "pressure_barg": round(rng.uniform(0.08, 0.12), 4),
            }
            send_reading(connection, reading)
            sent += 1
            consumption = 2740 / 2 / 1440 if ethane else 587 / 1440
            levels[tank] = max(0.0, levels[tank] - consumption * interval_seconds / 60)
        print(f"Minute {minute + 1}: sent {len(levels)} tank readings", flush=True)
        if minute + 1 < minutes:
            time.sleep(max(0.0, interval_seconds - (time.monotonic() - started)))
    return sent
