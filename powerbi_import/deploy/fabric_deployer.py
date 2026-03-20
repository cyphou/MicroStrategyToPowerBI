"""
Microsoft Fabric deployer.

Deploys a generated .pbip project to a Fabric workspace, optionally
configuring DirectLake mode for lakehouse-backed semantic models.

Requires: ``azure-identity`` and ``requests`` packages.
"""

import base64
import json
import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

_FABRIC_API_BASE = "https://api.fabric.microsoft.com/v1"
_SCOPE = "https://api.fabric.microsoft.com/.default"


# ── Public API ───────────────────────────────────────────────────


def deploy_to_fabric(project_dir, workspace_id, *,
                     credential=None, tenant_id=None,
                     client_id=None, client_secret=None,
                     display_name=None,
                     lakehouse_id=None,
                     direct_lake=False):
    """Deploy a .pbip project to a Fabric workspace.

    Args:
        project_dir: Path to generated .pbip root directory.
        workspace_id: Target Fabric workspace ID.
        credential: An ``azure.identity`` credential object.
        tenant_id: Azure tenant ID (service-principal auth).
        client_id: Client ID.
        client_secret: Client secret.
        display_name: Override display name.
        lakehouse_id: Fabric lakehouse for DirectLake binding.
        direct_lake: If True, convert import model to DirectLake.

    Returns:
        dict with ``semantic_model_id``, ``report_id``, ``status``.
    """

    token = _get_access_token(
        credential=credential,
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    name = display_name or _infer_display_name(project_dir)
    logger.info("Deploying '%s' to Fabric workspace %s", name, workspace_id)

    # Create semantic model item
    sm_id = _create_semantic_model(workspace_id, name, project_dir, headers)

    # Create report item
    report_id = _create_report(workspace_id, name, sm_id, project_dir, headers)

    result = {
        "semantic_model_id": sm_id,
        "report_id": report_id,
        "status": "succeeded",
        "workspace_id": workspace_id,
    }

    # Optionally configure DirectLake
    if direct_lake and lakehouse_id:
        _configure_direct_lake(workspace_id, sm_id, lakehouse_id, headers)
        result["direct_lake"] = True

    # Deploy Fabric-native artifacts if present
    fabric_dir = os.path.join(project_dir, "fabric")
    if os.path.isdir(fabric_dir):
        # Notebooks
        for fname in os.listdir(fabric_dir):
            if fname.endswith(".ipynb"):
                try:
                    nb_id = _create_notebook(workspace_id, fname[:-6], fabric_dir, headers)
                    result.setdefault("notebooks", []).append(nb_id)
                except Exception as e:
                    logger.warning("Notebook deployment failed for %s: %s", fname, e)

        # Pipeline
        pipeline_path = os.path.join(fabric_dir, "pipeline.json")
        if os.path.isfile(pipeline_path):
            try:
                pl_id = _create_pipeline(workspace_id, name, pipeline_path, headers)
                result["pipeline_id"] = pl_id
            except Exception as e:
                logger.warning("Pipeline deployment failed: %s", e)

    logger.info("Fabric deployment complete: SM=%s, Report=%s", sm_id, report_id)
    return result


# ── Authentication ───────────────────────────────────────────────


def _get_access_token(*, credential=None, tenant_id=None,
                      client_id=None, client_secret=None):
    """Obtain a bearer token for Fabric API."""
    if credential is not None:
        return credential.get_token(_SCOPE).token

    if tenant_id and client_id and client_secret:
        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": _SCOPE,
        }
        resp = requests.post(token_url, data=payload, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"Fabric auth failed ({resp.status_code}): {resp.text}")
        return resp.json()["access_token"]

    try:
        from azure.identity import DefaultAzureCredential
        return DefaultAzureCredential().get_token(_SCOPE).token
    except Exception as exc:
        raise RuntimeError(
            "No credentials provided and DefaultAzureCredential failed."
        ) from exc


# ── Item creation ────────────────────────────────────────────────


def _create_semantic_model(workspace_id, name, project_dir, headers):
    """Create a semantic model item in Fabric."""

    url = f"{_FABRIC_API_BASE}/workspaces/{workspace_id}/items"
    # Read TMDL definition files
    definition = _read_semantic_model_definition(project_dir, name)

    payload = {
        "displayName": f"{name}",
        "type": "SemanticModel",
        "definition": {
            "parts": definition,
        },
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    if resp.status_code not in (200, 201, 202):
        raise RuntimeError(f"Semantic model creation failed ({resp.status_code}): {resp.text}")

    # Handle long-running operation
    if resp.status_code == 202:
        item_id = _poll_long_running(resp, headers)
    else:
        item_id = resp.json().get("id", "")

    logger.info("Semantic model created: %s", item_id)
    return item_id


def _create_report(workspace_id, name, sm_id, project_dir, headers):
    """Create a report item linked to the semantic model."""

    url = f"{_FABRIC_API_BASE}/workspaces/{workspace_id}/items"
    definition = _read_report_definition(project_dir, name)

    payload = {
        "displayName": f"{name}",
        "type": "Report",
        "definition": {
            "parts": definition,
        },
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    if resp.status_code not in (200, 201, 202):
        raise RuntimeError(f"Report creation failed ({resp.status_code}): {resp.text}")

    if resp.status_code == 202:
        item_id = _poll_long_running(resp, headers)
    else:
        item_id = resp.json().get("id", "")

    logger.info("Report created: %s", item_id)
    return item_id


# ── DirectLake configuration ────────────────────────────────────


def _configure_direct_lake(workspace_id, sm_id, lakehouse_id, headers):
    """Patch a semantic model to use DirectLake mode."""

    logger.info("Configuring DirectLake for SM %s → Lakehouse %s", sm_id, lakehouse_id)
    url = (
        f"{_FABRIC_API_BASE}/workspaces/{workspace_id}"
        f"/semanticModels/{sm_id}/directLake"
    )
    payload = {
        "lakehouseId": lakehouse_id,
    }
    resp = requests.patch(url, headers=headers, json=payload, timeout=30)
    if resp.status_code not in (200, 202, 204):
        logger.warning("DirectLake config failed (%d): %s", resp.status_code, resp.text)
    else:
        logger.info("DirectLake configured successfully")


# ── Definition readers ───────────────────────────────────────────


def _read_semantic_model_definition(project_dir, name):
    """Read TMDL files and package as Fabric definition parts."""

    sm_dir = None
    for entry in os.listdir(project_dir):
        if entry.endswith(".SemanticModel") and os.path.isdir(os.path.join(project_dir, entry)):
            sm_dir = os.path.join(project_dir, entry)
            break

    if not sm_dir:
        raise RuntimeError("No .SemanticModel folder found in project")

    parts = []
    for root, _dirs, files in os.walk(sm_dir):
        for fname in files:
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, sm_dir).replace("\\", "/")
            with open(full, "rb") as f:
                content = f.read()
            parts.append({
                "path": rel,
                "payload": base64.b64encode(content).decode("ascii"),
                "payloadType": "InlineBase64",
            })

    return parts


def _read_report_definition(project_dir, name):
    """Read PBIR files and package as Fabric definition parts."""

    rpt_dir = None
    for entry in os.listdir(project_dir):
        if entry.endswith(".Report") and os.path.isdir(os.path.join(project_dir, entry)):
            rpt_dir = os.path.join(project_dir, entry)
            break

    if not rpt_dir:
        raise RuntimeError("No .Report folder found in project")

    parts = []
    for root, _dirs, files in os.walk(rpt_dir):
        for fname in files:
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, rpt_dir).replace("\\", "/")
            with open(full, "rb") as f:
                content = f.read()
            parts.append({
                "path": rel,
                "payload": base64.b64encode(content).decode("ascii"),
                "payloadType": "InlineBase64",
            })

    return parts


def _infer_display_name(project_dir):
    """Infer display name from .pbip file."""
    for f in os.listdir(project_dir):
        if f.endswith(".pbip"):
            return os.path.splitext(f)[0]
    return "MicroStrategy Migration"


# ── Long-running operation polling ───────────────────────────────


def _poll_long_running(response, headers, max_wait=300):
    """Poll a Fabric long-running operation."""

    location = response.headers.get("Location") or response.headers.get("Operation-Location")
    if not location:
        # Try to get the item ID from the response body
        data = response.json() if response.text else {}
        return data.get("id", "")

    start = time.monotonic()
    while time.monotonic() - start < max_wait:
        resp = requests.get(location, headers=headers, timeout=30)
        if resp.status_code != 200:
            time.sleep(3)
            continue

        data = resp.json()
        status = data.get("status", "")
        if status in ("Succeeded", "Completed"):
            return data.get("resourceId", data.get("id", ""))
        if status in ("Failed", "Cancelled"):
            raise RuntimeError(f"Operation failed: {data}")

        time.sleep(3)

    raise RuntimeError(f"Operation timed out after {max_wait}s")


# ── Fabric-native item deployment ────────────────────────────────


def _create_notebook(workspace_id, name, fabric_dir, headers):
    """Create a Notebook item in Fabric."""
    nb_path = os.path.join(fabric_dir, f"{name}.ipynb")
    with open(nb_path, "rb") as f:
        content = f.read()

    url = f"{_FABRIC_API_BASE}/workspaces/{workspace_id}/items"
    payload = {
        "displayName": name,
        "type": "Notebook",
        "definition": {
            "parts": [{
                "path": "notebook-content.ipynb",
                "payload": base64.b64encode(content).decode("ascii"),
                "payloadType": "InlineBase64",
            }],
        },
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    if resp.status_code not in (200, 201, 202):
        raise RuntimeError(f"Notebook creation failed ({resp.status_code}): {resp.text}")

    if resp.status_code == 202:
        item_id = _poll_long_running(resp, headers)
    else:
        item_id = resp.json().get("id", "")

    logger.info("Notebook created: %s (%s)", name, item_id)
    return item_id


def _create_pipeline(workspace_id, name, pipeline_path, headers):
    """Create a Data Pipeline item in Fabric."""
    with open(pipeline_path, "rb") as f:
        content = f.read()

    url = f"{_FABRIC_API_BASE}/workspaces/{workspace_id}/items"
    payload = {
        "displayName": f"{name}-Pipeline",
        "type": "DataPipeline",
        "definition": {
            "parts": [{
                "path": "pipeline-content.json",
                "payload": base64.b64encode(content).decode("ascii"),
                "payloadType": "InlineBase64",
            }],
        },
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    if resp.status_code not in (200, 201, 202):
        raise RuntimeError(f"Pipeline creation failed ({resp.status_code}): {resp.text}")

    if resp.status_code == 202:
        item_id = _poll_long_running(resp, headers)
    else:
        item_id = resp.json().get("id", "")

    logger.info("Pipeline created: %s (%s)", name, item_id)
    return item_id
