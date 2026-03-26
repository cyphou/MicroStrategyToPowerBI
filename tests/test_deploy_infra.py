"""
Tests for v16.0 Sprint HH — Deployment Infrastructure.

Covers: deploy/auth.py, deploy/client.py, deploy/bundle_deployer.py,
        deploy config loading, --deploy-env CLI flag.
"""

import json
import os
import shutil
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

from powerbi_import.deploy.auth import (
    get_token,
    get_fabric_token,
    get_pbi_token,
    clear_cache,
    _token_cache,
    _FABRIC_SCOPE,
    _PBI_SCOPE,
)
from powerbi_import.deploy.client import FabricClient, _API_BASE
from powerbi_import.deploy.bundle_deployer import (
    deploy_bundle,
    load_deploy_config,
    _load_manifest,
    _read_definition,
    _list_report_dirs,
)


# ── Helpers ──────────────────────────────────────────────────────

def _write(directory, filename, content):
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, filename), "w", encoding="utf-8") as f:
        f.write(content)


class _FakeToken:
    """Mimics azure.identity token result."""
    def __init__(self, token="fake-token", expires_on=None):
        self.token = token
        self.expires_on = expires_on or (time.time() + 3600)


class _FakeCredential:
    def get_token(self, scope):
        return _FakeToken()


# ═══════════════════════════════════════════════════════════════════
# Auth Tests
# ═══════════════════════════════════════════════════════════════════

class TestAuthCredential(unittest.TestCase):
    """HH.1: Credential-based auth."""

    def setUp(self):
        clear_cache()

    def test_explicit_credential(self):
        cred = _FakeCredential()
        token = get_token(credential=cred)
        self.assertEqual(token, "fake-token")

    def test_token_cached(self):
        cred = _FakeCredential()
        t1 = get_token(credential=cred)
        t2 = get_token(credential=cred)
        self.assertEqual(t1, t2)
        self.assertIn(_FABRIC_SCOPE, _token_cache)

    def test_clear_cache(self):
        cred = _FakeCredential()
        get_token(credential=cred)
        clear_cache()
        self.assertEqual(len(_token_cache), 0)

    def test_fabric_token_shortcut(self):
        cred = _FakeCredential()
        token = get_fabric_token(credential=cred)
        self.assertEqual(token, "fake-token")

    def test_pbi_token_shortcut(self):
        cred = _FakeCredential()
        token = get_pbi_token(credential=cred)
        self.assertEqual(token, "fake-token")

    def test_no_credentials_raises(self):
        # Patch out all fallback methods to return None
        with patch("powerbi_import.deploy.auth._get_interactive_token", return_value=None):
            with self.assertRaises(RuntimeError):
                get_token()

    def test_expired_cache_refreshes(self):
        _token_cache[_FABRIC_SCOPE] = {
            "token": "old", "expires_on": time.time() - 100,
        }
        cred = _FakeCredential()
        token = get_token(credential=cred)
        self.assertEqual(token, "fake-token")

    def test_service_principal_fallback(self):
        with patch("powerbi_import.deploy.auth._get_service_principal_token",
                    return_value="sp-token"):
            token = get_token(tenant_id="t", client_id="c", client_secret="s")
            self.assertEqual(token, "sp-token")

    def test_managed_identity_fallback(self):
        with patch("powerbi_import.deploy.auth._get_managed_identity_token",
                    return_value="mi-token"):
            token = get_token(managed_identity=True)
            self.assertEqual(token, "mi-token")


# ═══════════════════════════════════════════════════════════════════
# Fabric Client Tests
# ═══════════════════════════════════════════════════════════════════

class TestFabricClient(unittest.TestCase):
    """HH.2: REST API client."""

    def _mock_response(self, *, status_code=200, json_data=None, content=b"ok"):
        resp = MagicMock()
        resp.status_code = status_code
        resp.headers = {}
        resp.content = content
        resp.json.return_value = json_data or {}
        resp.raise_for_status.return_value = None
        return resp

    @patch("powerbi_import.deploy.client.requests.request")
    def test_get(self, mock_req):
        mock_req.return_value = self._mock_response(json_data={"id": "123"})
        client = FabricClient("token123")
        result = client.get("/workspaces/ws1")
        self.assertEqual(result["id"], "123")

    @patch("powerbi_import.deploy.client.requests.request")
    def test_post(self, mock_req):
        mock_req.return_value = self._mock_response(json_data={"id": "new"})
        client = FabricClient("token123")
        result = client.post("/items", body={"name": "Test"})
        self.assertEqual(result["id"], "new")

    @patch("powerbi_import.deploy.client.requests.request")
    def test_delete_204(self, mock_req):
        mock_req.return_value = self._mock_response(status_code=204, content=b"")
        client = FabricClient("token123")
        result = client.delete("/items/1")
        self.assertEqual(result, {})

    @patch("powerbi_import.deploy.client.requests.request")
    def test_retry_on_429(self, mock_req):
        # First call 429, second succeeds
        resp_429 = self._mock_response(status_code=429)
        resp_429.headers = {"Retry-After": "0"}
        resp_ok = self._mock_response(json_data={"ok": True})
        mock_req.side_effect = [resp_429, resp_ok]
        client = FabricClient("token")
        result = client.get("/test")
        self.assertTrue(result["ok"])
        self.assertEqual(mock_req.call_count, 2)

    @patch("powerbi_import.deploy.client.requests.request")
    def test_list_items_pagination(self, mock_req):
        page1 = self._mock_response(json_data={
            "value": [{"id": "1"}], "continuationToken": "ct1"})
        page2 = self._mock_response(json_data={
            "value": [{"id": "2"}]})
        mock_req.side_effect = [page1, page2]
        client = FabricClient("token")
        items = client.list_items("/workspaces/ws/items")
        self.assertEqual(len(items), 2)

    @patch("powerbi_import.deploy.client.requests.request")
    def test_create_workspace(self, mock_req):
        mock_req.return_value = self._mock_response(json_data={"id": "ws-new"})
        client = FabricClient("token")
        result = client.create_workspace("TestWS", capacity_id="cap1")
        self.assertEqual(result["id"], "ws-new")

    @patch("powerbi_import.deploy.client.requests.request")
    def test_create_item(self, mock_req):
        mock_req.return_value = self._mock_response(json_data={"id": "item1"})
        client = FabricClient("token")
        result = client.create_item("ws1", "Model", "SemanticModel")
        self.assertEqual(result["id"], "item1")

    @patch("powerbi_import.deploy.client.requests.request")
    def test_custom_base_url(self, mock_req):
        mock_req.return_value = self._mock_response(json_data={})
        client = FabricClient("token", base_url="https://custom.api.com/v1")
        client.get("/test")
        call_args = mock_req.call_args
        self.assertIn("custom.api.com", call_args[1].get("url", call_args[0][1]))


# ═══════════════════════════════════════════════════════════════════
# Bundle Deployer Tests
# ═══════════════════════════════════════════════════════════════════

class TestBundleDeployer(unittest.TestCase):
    """HH.3: Atomic bundle deployment."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Create bundle structure
        sm_dir = os.path.join(self.tmpdir, "shared_model")
        _write(sm_dir, "model.tmdl", "table Foo")
        rep_a = os.path.join(self.tmpdir, "reports", "Report_A")
        rep_b = os.path.join(self.tmpdir, "reports", "Report_B")
        _write(rep_a, "report.json", '{}')
        _write(rep_b, "report.json", '{}')
        # Manifest
        _write(self.tmpdir, "manifest.json", json.dumps({
            "semantic_model_name": "SharedModel",
            "description": "Test bundle",
        }))

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _mock_client(self):
        client = MagicMock()
        client.create_item.side_effect = [
            {"id": "sm-1"},   # semantic model
            {"id": "rpt-1"},  # Report_A
            {"id": "rpt-2"},  # Report_B
        ]
        return client

    def test_successful_deployment(self):
        client = self._mock_client()
        result = deploy_bundle(client, "ws-1", self.tmpdir)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["semantic_model_id"], "sm-1")
        self.assertEqual(len(result["report_ids"]), 2)
        self.assertFalse(result["rollback"])

    def test_dry_run(self):
        client = MagicMock()
        result = deploy_bundle(client, "ws-1", self.tmpdir, dry_run=True)
        self.assertEqual(result["status"], "succeeded")
        client.create_item.assert_not_called()
        self.assertEqual(result["semantic_model_id"], "dry-run-sm-id")

    def test_rollback_on_failure(self):
        client = MagicMock()
        # SM succeeds, first report fails
        client.create_item.side_effect = [
            {"id": "sm-1"},
            Exception("API error"),
        ]
        result = deploy_bundle(client, "ws-1", self.tmpdir)
        self.assertEqual(result["status"], "failed")
        self.assertTrue(result["rollback"])
        client.delete_item.assert_called()

    def test_endorsement_applied(self):
        client = self._mock_client()
        deploy_bundle(client, "ws-1", self.tmpdir, endorsement="Promoted")
        # Should call post for endorsement (sm + 2 reports = 3 calls)
        endorse_calls = [c for c in client.post.call_args_list
                         if "endorsement" in str(c)]
        self.assertEqual(len(endorse_calls), 3)

    def test_load_manifest(self):
        manifest = _load_manifest(self.tmpdir)
        self.assertEqual(manifest["semantic_model_name"], "SharedModel")

    def test_load_manifest_missing(self):
        manifest = _load_manifest(tempfile.mkdtemp())
        self.assertEqual(manifest, {})

    def test_read_definition(self):
        sm_dir = os.path.join(self.tmpdir, "shared_model")
        defn = _read_definition(sm_dir)
        self.assertIsNotNone(defn)
        self.assertIn("parts", defn)

    def test_read_definition_nonexistent(self):
        defn = _read_definition("/nonexistent")
        self.assertIsNone(defn)

    def test_list_report_dirs(self):
        reports_dir = os.path.join(self.tmpdir, "reports")
        dirs = _list_report_dirs(reports_dir)
        self.assertEqual(len(dirs), 2)

    def test_list_report_dirs_nonexistent(self):
        dirs = _list_report_dirs("/nonexistent")
        self.assertEqual(dirs, [])


# ═══════════════════════════════════════════════════════════════════
# Deploy Config Tests
# ═══════════════════════════════════════════════════════════════════

class TestDeployConfig(unittest.TestCase):
    """HH.4: Environment-based configuration."""

    def setUp(self):
        self.config_dir = tempfile.mkdtemp()
        _write(self.config_dir, "dev.json", json.dumps({
            "workspace_id": "ws-dev",
            "capacity_id": "cap-dev",
        }))
        _write(self.config_dir, "prod.json", json.dumps({
            "workspace_id": "ws-prod",
            "capacity_id": "cap-prod",
        }))

    def tearDown(self):
        shutil.rmtree(self.config_dir)

    def test_load_dev_config(self):
        config = load_deploy_config(self.config_dir, "dev")
        self.assertEqual(config["workspace_id"], "ws-dev")

    def test_load_prod_config(self):
        config = load_deploy_config(self.config_dir, "prod")
        self.assertEqual(config["workspace_id"], "ws-prod")

    def test_missing_config(self):
        config = load_deploy_config(self.config_dir, "staging")
        self.assertEqual(config, {})


# ═══════════════════════════════════════════════════════════════════
# CLI Flag Tests
# ═══════════════════════════════════════════════════════════════════

class TestDeployEnvCLI(unittest.TestCase):
    """HH.5: --deploy-env argument."""

    def test_deploy_env_accepted(self):
        from migrate import build_parser
        parser = build_parser()
        args = parser.parse_args([
            "--from-export", "test/",
            "--deploy-env", "dev",
        ])
        self.assertEqual(args.deploy_env, "dev")

    def test_deploy_env_prod(self):
        from migrate import build_parser
        parser = build_parser()
        args = parser.parse_args([
            "--from-export", "test/",
            "--deploy-env", "prod",
        ])
        self.assertEqual(args.deploy_env, "prod")

    def test_deploy_env_invalid(self):
        from migrate import build_parser
        parser = build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["--from-export", "test/", "--deploy-env", "invalid"])

    def test_version_is_16(self):
        from migrate import build_parser
        parser = build_parser()
        for action in parser._actions:
            if hasattr(action, 'version') and action.version:
                assert "16.0.0" in action.version
                return
        self.fail("No version action found")


if __name__ == "__main__":
    unittest.main()
