"""KQL management/query calls authenticated with the current Azure CLI identity."""

import requests

from fabric_client import access_token


class KustoClient:
    def __init__(self, cluster_uri: str, database_id: str) -> None:
        self.uri = cluster_uri.rstrip("/")
        self.database = database_id
        self.session = requests.Session()
        self.session.headers["Authorization"] = "Bearer " + access_token(self.uri)

    def execute(self, query: str) -> dict:
        endpoint = "mgmt" if query.lstrip().startswith(".") else "query"
        response = self.session.post(
            self.uri + "/v1/rest/" + endpoint,
            json={"db": self.database, "csl": query}, timeout=120,
        )
        if not response.ok:
            raise RuntimeError(f"KQL {response.status_code}: {response.text}")
        data = response.json()
        if data.get("error"):
            raise RuntimeError(f"KQL failed: {data['error']}")
        if data.get("Exceptions"):
            raise RuntimeError(f"KQL query exceptions: {data['Exceptions']}")
        return data
