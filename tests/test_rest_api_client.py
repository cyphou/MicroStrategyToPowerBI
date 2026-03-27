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


@pytest.fixture
def real_client():
    """Client with real requests module but mocked session (for retry tests)."""
    import requests as real_requests
    c = MstrRestClient("https://mstr.example.com/MicroStrategyLibrary")
    c.session = MagicMock()
    return c


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


# ── Search API ───────────────────────────────────────────────────

class TestSearchObjects:

    def test_search_single_page(self, client):
        data = {"result": [{"id": "1"}, {"id": "2"}], "totalItems": 2}
        client.session.request.return_value = MockResponse(json_data=data)
        result = client.search_objects(object_type=3)
        assert len(result) == 2

    def test_search_with_name_filter(self, client):
        data = {"result": [{"id": "1", "name": "Sales"}], "totalItems": 1}
        client.session.request.return_value = MockResponse(json_data=data)
        result = client.search_objects(object_type=3, name="Sales")
        assert len(result) == 1
        # Verify name param was passed
        call_kwargs = client.session.request.call_args[1]
        assert "Sales" in str(call_kwargs.get("params", {}))

    def test_search_with_pattern(self, client):
        data = {"result": [{"id": "1"}], "totalItems": 1}
        client.session.request.return_value = MockResponse(json_data=data)
        result = client.search_objects(pattern="Revenue")
        assert len(result) == 1

    def test_search_empty_results(self, client):
        data = {"result": [], "totalItems": 0}
        client.session.request.return_value = MockResponse(json_data=data)
        result = client.search_objects(object_type=3)
        assert result == []

    def test_search_pagination(self, client):
        page1 = {"result": [{"id": "1"}, {"id": "2"}], "totalItems": 3}
        page2 = {"result": [{"id": "3"}], "totalItems": 3}
        client.session.request.side_effect = [
            MockResponse(json_data=page1),
            MockResponse(json_data=page2),
        ]
        result = client.search_objects(object_type=3)
        assert len(result) == 3


# ── Paginated GET ────────────────────────────────────────────────

class TestGetPaginated:

    def test_list_response(self, client):
        client.session.request.return_value = MockResponse(json_data=[{"id": "T1"}])
        result = client._get_paginated(f"{client.base_url}/api/model/tables")
        assert len(result) == 1

    def test_dict_with_data_key(self, client):
        data = {"data": [{"id": "T1"}, {"id": "T2"}], "totalItems": 2}
        client.session.request.return_value = MockResponse(json_data=data)
        result = client._get_paginated(f"{client.base_url}/api/model/tables")
        assert len(result) == 2

    def test_dict_without_data_key(self, client):
        data = {"id": "SINGLE", "name": "Something"}
        client.session.request.return_value = MockResponse(json_data=data)
        result = client._get_paginated(f"{client.base_url}/api/model/tables")
        assert len(result) == 1
        assert result[0]["id"] == "SINGLE"

    def test_paginated_multi_page(self, client):
        page1 = {"data": [{"id": "1"}, {"id": "2"}], "totalItems": 3}
        page2 = {"data": [{"id": "3"}], "totalItems": 3}
        client.session.request.side_effect = [
            MockResponse(json_data=page1),
            MockResponse(json_data=page2),
        ]
        result = client._get_paginated(f"{client.base_url}/api/model/tables")
        assert len(result) == 3


# ── Retry Logic ──────────────────────────────────────────────────

class TestRetryLogic:

    def test_401_raises_immediately(self, real_client):
        real_client.session.request.return_value = MockResponse(
            status_code=401, headers={}
        )
        with pytest.raises(MstrApiError, match="401"):
            real_client._request("GET", f"{real_client.base_url}/api/test")

    def test_429_retries_with_backoff(self, real_client):
        resp_429 = MockResponse(status_code=429, headers={"Retry-After": "0"})
        resp_ok = MockResponse(json_data={"ok": True})
        real_client.session.request.side_effect = [resp_429, resp_ok]
        result = real_client._request("GET", f"{real_client.base_url}/api/test")
        assert result.json() == {"ok": True}
        assert real_client.session.request.call_count == 2

    def test_500_retries(self, real_client):
        resp_500 = MockResponse(status_code=500)
        resp_ok = MockResponse(json_data={})
        real_client.session.request.side_effect = [resp_500, resp_ok]
        result = real_client._request("GET", f"{real_client.base_url}/api/test")
        assert result.status_code == 200

    def test_max_retries_exceeded(self, real_client):
        resp_500 = MockResponse(status_code=500)
        real_client.session.request.return_value = resp_500
        with pytest.raises(Exception):
            real_client._request("GET", f"{real_client.base_url}/api/test")

    def test_connection_error_retries(self, real_client):
        import requests as real_requests
        real_client.session.request.side_effect = [
            real_requests.exceptions.ConnectionError("refused"),
            MockResponse(json_data={}),
        ]
        result = real_client._request("GET", f"{real_client.base_url}/api/test")
        assert result.status_code == 200

    def test_connection_error_max_retries(self, real_client):
        import requests as real_requests
        real_client.session.request.side_effect = real_requests.exceptions.ConnectionError("refused")
        with pytest.raises(real_requests.exceptions.ConnectionError):
            real_client._request("GET", f"{real_client.base_url}/api/test")


# ── Additional API endpoints ─────────────────────────────────────

class TestAdditionalEndpoints:

    def test_get_tables(self, client):
        client.session.request.return_value = MockResponse(json_data=[])
        result = client.get_tables()
        assert isinstance(result, list)

    def test_get_attributes(self, client):
        client.session.request.return_value = MockResponse(json_data=[])
        result = client.get_attributes()
        assert isinstance(result, list)

    def test_get_facts(self, client):
        client.session.request.return_value = MockResponse(json_data=[])
        result = client.get_facts()
        assert isinstance(result, list)

    def test_get_metrics_delegates_to_search(self, client):
        data = {"result": [], "totalItems": 0}
        client.session.request.return_value = MockResponse(json_data=data)
        result = client.get_metrics()
        assert isinstance(result, list)

    def test_get_reports(self, client):
        data = {"result": [], "totalItems": 0}
        client.session.request.return_value = MockResponse(json_data=data)
        result = client.get_reports()
        assert isinstance(result, list)

    def test_get_dossiers(self, client):
        data = {"result": [], "totalItems": 0}
        client.session.request.return_value = MockResponse(json_data=data)
        result = client.get_dossiers()
        assert isinstance(result, list)

    def test_get_cubes(self, client):
        data = {"result": [], "totalItems": 0}
        client.session.request.return_value = MockResponse(json_data=data)
        result = client.get_cubes()
        assert isinstance(result, list)

    def test_get_filters(self, client):
        data = {"result": [], "totalItems": 0}
        client.session.request.return_value = MockResponse(json_data=data)
        result = client.get_filters()
        assert isinstance(result, list)

    def test_get_report_instance(self, client):
        client.session.request.return_value = MockResponse(json_data={"rows": []})
        result = client.get_report_instance("RPT1")
        assert "rows" in result

    def test_get_report_prompts(self, client):
        client.session.request.return_value = MockResponse(json_data=[{"id": "P1"}])
        result = client.get_report_prompts("RPT1")
        assert isinstance(result, list)

    def test_get_dossier_instance(self, client):
        client.session.request.return_value = MockResponse(json_data={"mid": "123"})
        result = client.get_dossier_instance("DOS1")
        assert "mid" in result

    def test_get_user_hierarchies(self, client):
        client.session.request.return_value = MockResponse(json_data=[])
        result = client.get_user_hierarchies()
        assert isinstance(result, list)

    def test_get_cube_definition(self, client):
        client.session.request.return_value = MockResponse(json_data={"id": "C1"})
        result = client.get_cube_definition("C1")
        assert result["id"] == "C1"
