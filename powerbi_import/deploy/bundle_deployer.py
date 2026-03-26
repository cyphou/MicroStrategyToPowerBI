"""
Fabric bundle deployer.

Atomic deployment of a shared semantic model + N thin reports as a
single unit.  Supports:
- Dependency ordering (semantic model first, then reports)
- Rollback on partial failure (delete created items)
- Post-deployment endorsement (Promoted / Certified)

Uses ``deploy.client.FabricClient`` for all REST calls.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)


# ── Public API ───────────────────────────────────────────────────


def deploy_bundle(client, workspace_id, bundle_dir, *,
                  endorsement=None, dry_run=False):
    """Deploy a migration bundle to a Fabric workspace.

    Bundle directory structure::

        bundle_dir/
            shared_model/       # TMDL semantic model
            reports/            # One subfolder per thin report
                Report_A/
                Report_B/
            manifest.json       # Optional bundle manifest

    Args:
        client: A ``FabricClient`` instance (authenticated).
        workspace_id: Target Fabric workspace ID.
        bundle_dir: Path to the bundle directory.
        endorsement: ``"Promoted"`` or ``"Certified"`` (optional).
        dry_run: If True, log actions but don't actually deploy.

    Returns:
        dict with ``status``, ``semantic_model_id``, ``report_ids``,
        ``rollback`` flag.
    """
    manifest = _load_manifest(bundle_dir)
    sm_dir = os.path.join(bundle_dir, "shared_model")
    reports_dir = os.path.join(bundle_dir, "reports")

    created_items = []
    result = {
        "status": "pending",
        "semantic_model_id": None,
        "report_ids": [],
        "rollback": False,
    }

    try:
        # Step 1: Deploy shared semantic model
        sm_name = manifest.get("semantic_model_name", "SharedModel")
        logger.info("Deploying semantic model '%s'", sm_name)

        if dry_run:
            logger.info("[DRY RUN] Would create semantic model '%s'", sm_name)
            sm_id = "dry-run-sm-id"
        else:
            sm_resp = client.create_item(
                workspace_id, sm_name, "SemanticModel",
                definition=_read_definition(sm_dir),
                description=manifest.get("description", ""),
            )
            sm_id = sm_resp.get("id", "")
            created_items.append(sm_id)

        result["semantic_model_id"] = sm_id

        # Step 2: Deploy thin reports
        report_dirs = _list_report_dirs(reports_dir)
        for rdir in report_dirs:
            report_name = os.path.basename(rdir)
            logger.info("Deploying report '%s'", report_name)

            if dry_run:
                logger.info("[DRY RUN] Would create report '%s'", report_name)
                result["report_ids"].append("dry-run-report-id")
            else:
                r_resp = client.create_item(
                    workspace_id, report_name, "Report",
                    definition=_read_definition(rdir),
                    description=f"Thin report referencing {sm_name}",
                )
                r_id = r_resp.get("id", "")
                created_items.append(r_id)
                result["report_ids"].append(r_id)

        # Step 3: Endorsement
        if endorsement and not dry_run:
            _apply_endorsement(client, workspace_id, sm_id, endorsement)
            for r_id in result["report_ids"]:
                _apply_endorsement(client, workspace_id, r_id, endorsement)

        result["status"] = "succeeded"
        logger.info(
            "Bundle deployed: 1 semantic model + %d reports",
            len(result["report_ids"]),
        )

    except Exception as exc:
        logger.error("Bundle deployment failed: %s", exc)
        result["status"] = "failed"

        # Rollback: delete any items created so far
        if not dry_run and created_items:
            logger.warning("Rolling back %d created items", len(created_items))
            for item_id in reversed(created_items):
                try:
                    client.delete_item(workspace_id, item_id)
                    logger.info("Rolled back item %s", item_id)
                except Exception as rb_exc:
                    logger.error("Rollback failed for %s: %s", item_id, rb_exc)
            result["rollback"] = True

    return result


# ── Manifest & definitions ───────────────────────────────────────


def _load_manifest(bundle_dir):
    """Load bundle manifest.json, or return defaults."""
    path = os.path.join(bundle_dir, "manifest.json")
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _read_definition(item_dir):
    """Read all files in an item directory and build a definition payload."""
    if not os.path.isdir(item_dir):
        return None

    parts = []
    for root, _dirs, files in os.walk(item_dir):
        for fname in files:
            fpath = os.path.join(root, fname)
            rel = os.path.relpath(fpath, item_dir).replace("\\", "/")
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            parts.append({
                "path": rel,
                "payload": content,
                "payloadType": "InlineBase64",
            })
    return {"parts": parts} if parts else None


def _list_report_dirs(reports_dir):
    """List subdirectories in the reports folder."""
    if not os.path.isdir(reports_dir):
        return []
    return sorted(
        os.path.join(reports_dir, d)
        for d in os.listdir(reports_dir)
        if os.path.isdir(os.path.join(reports_dir, d))
    )


# ── Endorsement ──────────────────────────────────────────────────


def _apply_endorsement(client, workspace_id, item_id, endorsement):
    """Apply Promoted or Certified endorsement to an item."""
    try:
        client.post(
            f"/workspaces/{workspace_id}/items/{item_id}/endorsement",
            body={"endorsement": endorsement},
        )
        logger.info("Applied %s endorsement to %s", endorsement, item_id)
    except Exception as exc:
        logger.warning("Endorsement failed for %s: %s", item_id, exc)


# ── Environment config loading ───────────────────────────────────


def load_deploy_config(config_dir, env_name):
    """Load environment-specific deployment configuration.

    Looks for ``{env_name}.json`` in the config directory.

    Args:
        config_dir: Directory containing config files.
        env_name: Environment name (e.g., ``dev``, ``staging``, ``prod``).

    Returns:
        dict with workspace_id, capacity_id, gateway_id, etc.
    """
    path = os.path.join(config_dir, f"{env_name}.json")
    if not os.path.isfile(path):
        logger.warning("Config file not found: %s", path)
        return {}
    with open(path, "r", encoding="utf-8") as f:
        config = json.load(f)
    logger.info("Loaded deploy config for environment '%s'", env_name)
    return config
