"""Small Fabric REST client using the user's Azure CLI SSO session."""

import base64
import json
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

WORKSPACE_ID = "6d6350e8-6f22-4a8b-b06a-eb4a3b68dd23"
FOLDER_ID = "62e9a35c-6d20-48cb-9b04-7c1af8d74556"
TENANT = "MngEnvMCAP671226.onmicrosoft.com"
ROOT = Path(__file__).resolve().parent
STATE = ROOT / ".fabric"
API = "https://api.fabric.microsoft.com/v1"


def access_token(resource: str = "https://api.fabric.microsoft.com") -> str:
    az = shutil.which("az")
    if az is None:
        raise RuntimeError("Azure CLI is required. Install it and run az login first.")
    result = subprocess.run(
        [az, "account", "get-access-token", "--tenant", TENANT,
         "--resource", resource, "--output", "json"],
        check=True, capture_output=True, text=True,
    )
    return json.loads(result.stdout)["accessToken"]


def definition(parts: dict, format_name: str | None = None) -> dict:
    result = {"parts": [
        {"path": path, "payloadType": "InlineBase64",
         "payload": base64.b64encode(
             (content if isinstance(content, str) else json.dumps(content)).encode("utf-8")
         ).decode("ascii")}
        for path, content in parts.items()
    ]}
    if format_name:
        result["format"] = format_name
    return result


class FabricClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers["Authorization"] = "Bearer " + access_token()
        self.workspace = f"workspaces/{WORKSPACE_ID}"

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = path if path.startswith("https://") else f"{API}/{path}"
        host = urlparse(url).hostname or ""
        if host != "api.fabric.microsoft.com" and not host.endswith(".analysis.windows.net"):
            raise ValueError(f"Unexpected Fabric API host: {host}")
        for attempt in range(6):
            response = self.session.request(method, url, timeout=120, **kwargs)
            if response.status_code == 401 and attempt == 0:
                self.session.headers["Authorization"] = "Bearer " + access_token()
                continue
            if response.status_code == 429 and attempt < 5:
                time.sleep(int(response.headers.get("Retry-After", "30")))
                continue
            if not response.ok:
                raise requests.HTTPError(
                    f"{method} {path}: {response.status_code} {response.text}",
                    response=response,
                )
            return response
        raise RuntimeError(f"Retry limit reached: {method} {path}")

    def operation(self, response: requests.Response) -> dict:
        if response.status_code != 202:
            return response.json() if response.content else {}
        location = response.headers["Location"]
        deadline = time.monotonic() + 1800
        while time.monotonic() < deadline:
            time.sleep(int(response.headers.get("Retry-After", "5")))
            response = self.request("GET", location)
            status = response.json()
            if status["status"] == "Succeeded":
                result = self.request("GET", location.rstrip("/") + "/result")
                return result.json() if result.content else {}
            if status["status"] in {"Failed", "Cancelled"}:
                raise RuntimeError(f"Fabric operation failed: {status}")
        raise TimeoutError(f"Fabric operation did not finish: {location}")

    def list_all(self, path: str) -> list[dict]:
        values = []
        while path:
            data = self.request("GET", path).json()
            values.extend(data["value"])
            path = data.get("continuationUri")
        return values

    def ensure_item(self, name: str, item_type: str, item_definition: dict | None = None,
                    creation_payload: dict | None = None) -> dict:
        matches = [item for item in self.list_all(f"{self.workspace}/items")
                   if item["displayName"] == name and item["type"] == item_type]
        if len(matches) > 1:
            raise RuntimeError(f"Ambiguous item name: {name}")
        if matches:
            item = matches[0]
            if item.get("folderId") != FOLDER_ID:
                raise RuntimeError(f"Refusing to modify {name} outside the target folder")
            print(f"Using {item_type}: {name} ({item['id']})", flush=True)
            if item_definition:
                self.operation(self.request(
                    "POST", f"{self.workspace}/items/{item['id']}/updateDefinition",
                    json={"definition": item_definition},
                ))
            return item
        body = {
            "displayName": name, "type": item_type, "folderId": FOLDER_ID,
            "description": "LSP feedstock demo. Synthetic illustrative data; not operational LSP data.",
        }
        if item_definition:
            body["definition"] = item_definition
        if creation_payload:
            body["creationPayload"] = creation_payload
        item = self.operation(self.request("POST", f"{self.workspace}/items", json=body))
        print(f"Created {item_type}: {name} ({item.get('id')})", flush=True)
        return item

    def start_job(self, item_id: str, job_type: str, body: dict | None = None) -> str:
        response = self.request(
            "POST", f"{self.workspace}/items/{item_id}/jobs/{job_type}/instances",
            **({"json": body} if body else {}),
        )
        return response.headers["Location"]

    def wait_job(self, location: str, timeout: int = 1800) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = self.request("GET", location).json()
            print(f"Job {result['id']}: {result['status']}", flush=True)
            if result["status"] == "Completed":
                return result
            if result["status"] in {"Failed", "Cancelled", "Deduped"}:
                raise RuntimeError(f"Fabric job did not complete successfully: {result}")
            time.sleep(30)
        raise TimeoutError(f"Fabric job still running: {location}")


def save_state(name: str, value: dict) -> None:
    STATE.mkdir(exist_ok=True)
    (STATE / name).write_text(json.dumps(value, indent=2), encoding="utf-8")
