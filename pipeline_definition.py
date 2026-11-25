"""Daily generation followed by a native, transactional semantic model refresh."""

from fabric_client import WORKSPACE_ID, definition


def pipeline(notebook_id: str, model_id: str, connection_id: str) -> dict:
    return definition({"pipeline-content.json": {"properties": {"activities": [
        {
            "name": "Generate sample plant data", "type": "TridentNotebook",
            "dependsOn": [],
            "policy": {"timeout": "0.01:00:00", "retry": 1,
                       "retryIntervalInSeconds": 60, "secureOutput": False, "secureInput": False},
            "typeProperties": {"notebookId": notebook_id, "workspaceId": WORKSPACE_ID},
        },
        {
            "name": "Refresh Direct Lake model", "type": "PBISemanticModelRefresh",
            "dependsOn": [{"activity": "Generate sample plant data",
                           "dependencyConditions": ["Succeeded"]}],
            "policy": {"timeout": "0.01:00:00", "retry": 1,
                       "retryIntervalInSeconds": 60, "secureOutput": False, "secureInput": False},
            "typeProperties": {
                "method": "post", "waitOnCompletion": True,
                "commitMode": "Transactional", "operationType": "SemanticModelRefresh",
                "groupId": WORKSPACE_ID, "datasetId": model_id,
            },
            "externalReferences": {"connection": connection_id},
        },
    ]}}})
