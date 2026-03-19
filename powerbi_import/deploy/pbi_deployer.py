"""
Power BI Service deployer.

Uploads a generated .pbip project to a Power BI workspace using the
Power BI REST API v1 with Azure AD / Entra ID authentication.

Requires: ``azure-identity`` and ``requests`` packages.
"""

import json
import logging
import os
import time
import zipfile
from io import BytesIO

import requests

logger = logging.getLogger(__name__)

_PBI_API_BASE = "https://api.powerbi.com/v1.0/myorg"
_SCOPE = "https://analysis.windows.net/powerbi/api/.default"

# Upload chunk size: 4 MB
_CHUNK_SIZE = 4 * 1024 * 1024


# ── Public API ───────────────────────────────────────────────────


def deploy_to_service(project_dir, workspace_id, *,
                      credential=None, tenant_id=None,
                      client_id=None, client_secret=None,
                      display_name=None, refresh=False):
    """Deploy a .pbip project to Power BI Service.

    Args:
        project_dir: Path to generated .pbip root directory.
        workspace_id: Target Power BI workspace / group ID.
        credential: An ``azure.identity`` credential object (optional).
        tenant_id: Azure tenant ID (for service-principal auth).
        client_id: Azure app registration client ID.
        client_secret: Client secret (for service-principal auth).
        display_name: Override display name in the workspace.
        refresh: If True, trigger a dataset refresh after import.

    Returns:
        dict with ``import_id``, ``dataset_id``, ``report_id``, ``status``.

    Raises:
        RuntimeError: On auth or upload failure.
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

    # Build in-memory zip of the project
    pbip_zip = _create_project_zip(project_dir)

    name = display_name or _infer_display_name(project_dir)
    logger.info("Deploying '%s' to workspace %s", name, workspace_id)

    # Initiate import
    import_url = (
        f"{_PBI_API_BASE}/groups/{workspace_id}/imports"
        f"?datasetDisplayName={requests.utils.quote(name)}"
        "&nameConflict=CreateOrOverwrite"
    )
    resp = requests.post(
        import_url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/octet-stream",
        },
        data=pbip_zip,
        timeout=120,
    )
    if resp.status_code not in (200, 201, 202):
        raise RuntimeError(f"Import failed ({resp.status_code}): {resp.text}")

    import_info = resp.json()
    import_id = import_info.get("id", "")
    logger.info("Import started: %s", import_id)

    # Poll for completion
    result = _poll_import(workspace_id, import_id, token)

    # Optionally refresh dataset
    if refresh and result.get("dataset_id"):
        _trigger_refresh(workspace_id, result["dataset_id"], token)
        result["refresh_triggered"] = True

    return result


# ── Authentication ───────────────────────────────────────────────


def _get_access_token(*, credential=None, tenant_id=None,
                      client_id=None, client_secret=None):
    """Obtain a bearer token for the Power BI REST API."""
    if credential is not None:
        # Use the provided azure-identity credential
        token_resp = credential.get_token(_SCOPE)
        return token_resp.token

    if tenant_id and client_id and client_secret:
        # Service-principal authentication via MSAL/requests
        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": _SCOPE,
        }
        resp = requests.post(token_url, data=payload, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"Auth failed ({resp.status_code}): {resp.text}")
        return resp.json()["access_token"]

    # Try DefaultAzureCredential
    try:
        from azure.identity import DefaultAzureCredential
        cred = DefaultAzureCredential()
        return cred.get_token(_SCOPE).token
    except Exception as exc:
        raise RuntimeError(
            "No credentials provided and DefaultAzureCredential failed. "
            "Supply --tenant-id + --client-id + --client-secret, "
            "or install azure-identity and sign in via 'az login'."
        ) from exc


# ── Project packaging ────────────────────────────────────────────


def _create_project_zip(project_dir):
    """Create an in-memory .zip of the .pbip project."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(project_dir):
            for fname in files:
                full = os.path.join(root, fname)
                arcname = os.path.relpath(full, project_dir)
                zf.write(full, arcname)
    return buf.getvalue()


def _infer_display_name(project_dir):
    """Infer display name from the .pbip file."""
    for f in os.listdir(project_dir):
        if f.endswith(".pbip"):
            return os.path.splitext(f)[0]
    return "MicroStrategy Migration"


# ── Import polling ───────────────────────────────────────────────


def _poll_import(workspace_id, import_id, token, max_wait=300):
    """Poll import status until complete or timeout."""

    url = f"{_PBI_API_BASE}/groups/{workspace_id}/imports/{import_id}"
    headers = {"Authorization": f"Bearer {token}"}

    start = time.monotonic()
    while time.monotonic() - start < max_wait:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code != 200:
            logger.warning("Poll failed (%d): %s", resp.status_code, resp.text)
            time.sleep(5)
            continue

        data = resp.json()
        state = data.get("importState", "")
        if state == "Succeeded":
            datasets = data.get("datasets", [])
            reports = data.get("reports", [])
            return {
                "import_id": import_id,
                "status": "succeeded",
                "dataset_id": datasets[0]["id"] if datasets else None,
                "report_id": reports[0]["id"] if reports else None,
            }
        if state == "Failed":
            raise RuntimeError(f"Import failed: {data}")

        logger.debug("Import state: %s — waiting...", state)
        time.sleep(3)

    raise RuntimeError(f"Import timed out after {max_wait}s")


# ── Dataset refresh ──────────────────────────────────────────────


def _trigger_refresh(workspace_id, dataset_id, token):
    """Trigger a dataset refresh."""

    url = f"{_PBI_API_BASE}/groups/{workspace_id}/datasets/{dataset_id}/refreshes"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    resp = requests.post(url, headers=headers, json={}, timeout=30)
    if resp.status_code not in (200, 202):
        logger.warning("Refresh trigger failed (%d): %s", resp.status_code, resp.text)
    else:
        logger.info("Dataset refresh triggered for %s", dataset_id)
