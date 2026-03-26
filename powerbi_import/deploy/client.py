"""
Generic Fabric REST API client.

Provides authenticated HTTP operations against the Fabric REST API
(``https://api.fabric.microsoft.com/v1``) with:
- Automatic retry with exponential backoff (429 / 5xx)
- Pagination (continuationToken)
- Diagnostic logging
"""

import json
import logging
import time

import requests

logger = logging.getLogger(__name__)

_API_BASE = "https://api.fabric.microsoft.com/v1"
_MAX_RETRIES = 5
_BACKOFF_BASE = 2  # seconds


# ── Public API ───────────────────────────────────────────────────


class FabricClient:
    """Authenticated client for the Fabric REST API.

    Args:
        token: Bearer access token.
        base_url: Override API base URL (for testing/sovereign clouds).
    """

    def __init__(self, token, *, base_url=None):
        self._token = token
        self._base = (base_url or _API_BASE).rstrip("/")
        self._session = None

    # ── HTTP verbs ───────────────────────────────────────────────

    def get(self, path, *, params=None):
        """GET request with retry and pagination support."""
        return self._request("GET", path, params=params)

    def post(self, path, *, body=None):
        """POST request with retry."""
        return self._request("POST", path, body=body)

    def patch(self, path, *, body=None):
        """PATCH request with retry."""
        return self._request("PATCH", path, body=body)

    def delete(self, path):
        """DELETE request with retry."""
        return self._request("DELETE", path)

    # ── Paginated list helper ────────────────────────────────────

    def list_items(self, path, *, params=None):
        """Paginated GET that yields all items across pages."""
        items = []
        next_params = dict(params or {})

        while True:
            data = self.get(path, params=next_params)
            items.extend(data.get("value", []))
            token = data.get("continuationToken")
            if not token:
                break
            next_params["continuationToken"] = token

        return items

    # ── Workspace operations ─────────────────────────────────────

    def list_workspaces(self):
        """List all accessible workspaces."""
        return self.list_items("/workspaces")

    def get_workspace(self, workspace_id):
        """Get workspace details."""
        return self.get(f"/workspaces/{workspace_id}")

    def create_workspace(self, display_name, *, capacity_id=None,
                         description=None):
        """Create a new workspace."""
        body = {"displayName": display_name}
        if capacity_id:
            body["capacityId"] = capacity_id
        if description:
            body["description"] = description
        return self.post("/workspaces", body=body)

    # ── Item operations ──────────────────────────────────────────

    def list_workspace_items(self, workspace_id, *, item_type=None):
        """List items in a workspace, optionally filtered by type."""
        params = {}
        if item_type:
            params["type"] = item_type
        return self.list_items(f"/workspaces/{workspace_id}/items",
                               params=params)

    def create_item(self, workspace_id, display_name, item_type, *,
                    definition=None, description=None):
        """Create a Fabric item (SemanticModel, Report, Notebook, etc.)."""
        body = {
            "displayName": display_name,
            "type": item_type,
        }
        if description:
            body["description"] = description
        if definition:
            body["definition"] = definition
        return self.post(f"/workspaces/{workspace_id}/items", body=body)

    def update_item(self, workspace_id, item_id, *, display_name=None,
                    description=None):
        """Update item metadata."""
        body = {}
        if display_name:
            body["displayName"] = display_name
        if description:
            body["description"] = description
        return self.patch(f"/workspaces/{workspace_id}/items/{item_id}",
                          body=body)

    def delete_item(self, workspace_id, item_id):
        """Delete a Fabric item."""
        return self.delete(f"/workspaces/{workspace_id}/items/{item_id}")

    def update_item_definition(self, workspace_id, item_id, definition):
        """Update an item's definition (content payload)."""
        return self.post(
            f"/workspaces/{workspace_id}/items/{item_id}/updateDefinition",
            body={"definition": definition},
        )

    # ── Long-running operation polling ───────────────────────────

    def poll_operation(self, operation_url, *, timeout=300, interval=5):
        """Poll a long-running operation until completion or timeout."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            data = self.get(operation_url)
            status = data.get("status", "").lower()
            if status in ("succeeded", "completed"):
                return data
            if status in ("failed", "cancelled"):
                logger.error("Operation failed: %s", data)
                return data
            time.sleep(interval)
        logger.warning("Operation timed out after %ds", timeout)
        return {"status": "timeout"}

    # ── Internal HTTP machinery ──────────────────────────────────

    def _request(self, method, path, *, params=None, body=None):
        """Execute an HTTP request with retry and backoff."""
        url = f"{self._base}{path}" if path.startswith("/") else path
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                resp = requests.request(
                    method, url,
                    headers=headers,
                    params=params,
                    json=body,
                    timeout=60,
                )
                # Retry on throttle or transient server errors
                if resp.status_code == 429 or resp.status_code >= 500:
                    retry_after = int(resp.headers.get("Retry-After", _BACKOFF_BASE ** attempt))
                    logger.warning(
                        "%s %s → %d, retry in %ds (attempt %d/%d)",
                        method, path, resp.status_code, retry_after,
                        attempt, _MAX_RETRIES,
                    )
                    time.sleep(retry_after)
                    continue

                resp.raise_for_status()

                if resp.status_code == 204 or not resp.content:
                    return {}
                return resp.json()

            except requests.exceptions.ConnectionError as exc:
                if attempt < _MAX_RETRIES:
                    wait = _BACKOFF_BASE ** attempt
                    logger.warning(
                        "Connection error on %s %s, retry in %ds: %s",
                        method, path, wait, exc,
                    )
                    time.sleep(wait)
                else:
                    raise

        raise RuntimeError(f"Exhausted {_MAX_RETRIES} retries for {method} {path}")
