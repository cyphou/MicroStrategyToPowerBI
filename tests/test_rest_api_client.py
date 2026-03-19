"""Tests for MicroStrategy REST API client module."""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from microstrategy_export.rest_api_client import (
    MstrRestClient,
    MstrApiError,
    OBJECT_TYPE_REPORT,
    OBJECT_TYPE_METRIC,
    OBJECT_TYPE_ATTRIBUTE,
    OBJECT_TYPE_FACT,
    OBJECT_TYPE_DOSSIER,
    OBJECT_TYPE_CUBE,
)


class MockResponse:
    """Mock requests.Response."""

    def __init__(self, json_data=None, status_code=200, headers=None):
        self._json = json_data or {}
        self.status_code = status_code
        self.headers = headers or {}
        self.cookies = MagicMock()
        self.text = str(json_data)

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


@pytest.fixture
def client():
    """Create a client with mocked requests session."""
    with patch("microstrategy_export.rest_api_client.requests") as mock_req:
        mock_session = MagicMock()
        mock_req.Session.return_value = mock_session
        c = MstrRestClient("https://mstr.example.com/MicroStrategyLibrary")
        c.session = mock_session
        yield c


# ── Client Initialization ────────────────────────────────────────

class TestClientInit:

    def test_base_url_trailing_slash_stripped(self):
        with patch("microstrategy_export.rest_api_client.requests"):
            c = MstrRestClient("https://mstr.example.com/Library/")
            assert c.base_url == "https://mstr.example.com/Library"

    def test_default_timeout(self):
        with patch("microstrategy_export.rest_api_client.requests"):
            c = MstrRestClient("https://mstr.example.com/Library")
            assert c.timeout == 120

    def test_custom_timeout(self):
        with patch("microstrategy_export.rest_api_client.requests"):
            c = MstrRestClient("https://mstr.example.com/Library", timeout=60)
            assert c.timeout == 60

    def test_max_retries_default(self):
        with patch("microstrategy_export.rest_api_client.requests"):
            c = MstrRestClient("https://mstr.example.com/Library")
            assert c.max_retries == 3

    def test_no_auth_token_initially(self):
        with patch("microstrategy_export.rest_api_client.requests"):
            c = MstrRestClient("https://mstr.example.com/Library")
            assert c.auth_token is None

    def test_no_project_initially(self):
        with patch("microstrategy_export.rest_api_client.requests"):
            c = MstrRestClient("https://mstr.example.com/Library")
            assert c.project_id is None
            assert c.project_name is None


# ── Authentication ───────────────────────────────────────────────

class TestAuthentication:

    def test_authenticate_standard(self, client):
        mock_resp = MockResponse(
            json_data={},
            headers={"X-MSTR-AuthToken": "test-token-123"}
        )
        client.session.request.return_value = mock_resp
        client.authenticate("admin", "password", "standard")
        assert client.auth_token == "test-token-123"

    def test_authenticate_ldap(self, client):
        mock_resp = MockResponse(
            json_data={},
            headers={"X-MSTR-AuthToken": "ldap-token"}
        )
        client.session.request.return_value = mock_resp
        client.authenticate("admin", "password", "ldap")
        assert client.auth_token == "ldap-token"

    def test_close_clears_token(self, client):
        client.auth_token = "some-token"
        client.session.request.return_value = MockResponse()
        client.close()
        assert client.auth_token is None


# ── Select Project ───────────────────────────────────────────────

class TestSelectProject:

    def test_select_existing_project(self, client):
        projects = [
            {"id": "proj1", "name": "Tutorial"},
            {"id": "proj2", "name": "Production"},
        ]
        client.session.request.return_value = MockResponse(json_data=projects)
        result = client.select_project("Tutorial")
        assert result["id"] == "proj1"
        assert client.project_id == "proj1"
        assert client.project_name == "Tutorial"

    def test_select_project_case_insensitive(self, client):
        projects = [{"id": "proj1", "name": "MyProject"}]
        client.session.request.return_value = MockResponse(json_data=projects)
        result = client.select_project("myproject")
        assert result["id"] == "proj1"

    def test_select_missing_project_raises(self, client):
        projects = [{"id": "proj1", "name": "Other"}]
        client.session.request.return_value = MockResponse(json_data=projects)
        with pytest.raises(ValueError, match="not found"):
            client.select_project("NonExistent")


# ── API URLs ─────────────────────────────────────────────────────

class TestApiUrls:

    def test_list_projects_url(self, client):
        client.session.request.return_value = MockResponse(json_data=[])
        client.list_projects()
        call_args = client.session.request.call_args
        assert "/api/projects" in call_args[0][1]

    def test_get_tables_url(self, client):
        resp = MockResponse(json_data=[])
        client.session.request.return_value = resp
        client.get_tables()
        call_args = client.session.request.call_args
        assert "/api/model/tables" in call_args[0][1]

    def test_get_attribute_url(self, client):
        client.session.request.return_value = MockResponse(json_data={})
        client.get_attribute("ATTR123")
        call_args = client.session.request.call_args
        assert "/api/model/attributes/ATTR123" in call_args[0][1]

    def test_get_fact_url(self, client):
        client.session.request.return_value = MockResponse(json_data={})
        client.get_fact("FACT123")
        call_args = client.session.request.call_args
        assert "/api/model/facts/FACT123" in call_args[0][1]

    def test_get_metric_url(self, client):
        client.session.request.return_value = MockResponse(json_data={})
        client.get_metric("METRIC123")
        call_args = client.session.request.call_args
        assert "/api/model/metrics/METRIC123" in call_args[0][1]

    def test_get_report_definition_url(self, client):
        client.session.request.return_value = MockResponse(json_data={})
        client.get_report_definition("RPT123")
        call_args = client.session.request.call_args
        assert "/api/v2/reports/RPT123" in call_args[0][1]

    def test_get_dossier_definition_url(self, client):
        client.session.request.return_value = MockResponse(json_data={})
        client.get_dossier_definition("DOS123")
        call_args = client.session.request.call_args
        assert "/api/v2/dossiers/DOS123/definition" in call_args[0][1]


# ── Object Type Constants ────────────────────────────────────────

class TestObjectTypeConstants:

    def test_report_type(self):
        assert OBJECT_TYPE_REPORT == 3

    def test_metric_type(self):
        assert OBJECT_TYPE_METRIC == 4

    def test_attribute_type(self):
        assert OBJECT_TYPE_ATTRIBUTE == 12

    def test_fact_type(self):
        assert OBJECT_TYPE_FACT == 13

    def test_cube_type(self):
        assert OBJECT_TYPE_CUBE == 21

    def test_dossier_type(self):
        assert OBJECT_TYPE_DOSSIER == 55


# ── MstrApiError ─────────────────────────────────────────────────

class TestMstrApiError:

    def test_error_message(self):
        err = MstrApiError(404, "Not found")
        assert "404" in str(err)
        assert "Not found" in str(err)

    def test_error_with_ticket_id(self):
        err = MstrApiError(500, "Internal error", ticket_id="TICKET-123")
        assert err.ticket_id == "TICKET-123"
        assert err.status_code == 500

    def test_error_inherits_exception(self):
        err = MstrApiError(429, "Rate limited")
        assert isinstance(err, Exception)
