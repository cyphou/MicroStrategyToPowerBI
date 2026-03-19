"""
Shared pytest fixtures for MicroStrategy to Power BI migration tests.

Provides:
- Mock MicroStrategy REST API client
- Pre-loaded API response fixtures
- Pre-loaded intermediate JSON fixtures
- Temporary output directories
"""

import json
import os
import pathlib
import pytest

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"
API_RESPONSES_DIR = FIXTURES_DIR / "mstr_api_responses"
INTERMEDIATE_DIR = FIXTURES_DIR / "intermediate_json"
EXPECTED_OUTPUT_DIR = FIXTURES_DIR / "expected_output"


# ── Helper to load JSON fixture ──────────────────────────────────

def _load_json(path):
    """Load and parse a JSON fixture file."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


# ── API Response Fixtures ────────────────────────────────────────

@pytest.fixture
def api_projects():
    """MicroStrategy projects API response."""
    return _load_json(API_RESPONSES_DIR / "projects.json")


@pytest.fixture
def api_tables():
    """MicroStrategy tables API response."""
    return _load_json(API_RESPONSES_DIR / "tables.json")


@pytest.fixture
def api_attributes():
    """MicroStrategy attributes API response (list + details)."""
    return _load_json(API_RESPONSES_DIR / "attributes.json")


@pytest.fixture
def api_facts():
    """MicroStrategy facts API response (list + details)."""
    return _load_json(API_RESPONSES_DIR / "facts.json")


@pytest.fixture
def api_metrics():
    """MicroStrategy metrics API response (list + details)."""
    return _load_json(API_RESPONSES_DIR / "metrics.json")


@pytest.fixture
def api_reports():
    """MicroStrategy reports API response (list + definitions)."""
    return _load_json(API_RESPONSES_DIR / "reports.json")


@pytest.fixture
def api_dossiers():
    """MicroStrategy dossiers API response (list + definitions)."""
    return _load_json(API_RESPONSES_DIR / "dossiers.json")


@pytest.fixture
def api_cubes():
    """MicroStrategy cubes API response (list + definitions)."""
    return _load_json(API_RESPONSES_DIR / "cubes.json")


@pytest.fixture
def api_prompts():
    """MicroStrategy prompts API response."""
    return _load_json(API_RESPONSES_DIR / "prompts.json")


@pytest.fixture
def api_security_filters():
    """MicroStrategy security filters API response."""
    return _load_json(API_RESPONSES_DIR / "security_filters.json")


@pytest.fixture
def api_hierarchies():
    """MicroStrategy hierarchies API response."""
    return _load_json(API_RESPONSES_DIR / "hierarchies.json")


@pytest.fixture
def api_search_results():
    """MicroStrategy search results (custom groups etc.)."""
    return _load_json(API_RESPONSES_DIR / "search_results.json")


# ── Intermediate JSON Fixtures ───────────────────────────────────

@pytest.fixture
def intermediate_datasources():
    """Extracted datasources intermediate JSON."""
    return _load_json(INTERMEDIATE_DIR / "datasources.json")


@pytest.fixture
def intermediate_attributes():
    """Extracted attributes intermediate JSON."""
    return _load_json(INTERMEDIATE_DIR / "attributes.json")


@pytest.fixture
def intermediate_facts():
    """Extracted facts intermediate JSON."""
    return _load_json(INTERMEDIATE_DIR / "facts.json")


@pytest.fixture
def intermediate_metrics():
    """Extracted metrics intermediate JSON."""
    return _load_json(INTERMEDIATE_DIR / "metrics.json")


@pytest.fixture
def intermediate_derived_metrics():
    """Extracted derived metrics intermediate JSON."""
    return _load_json(INTERMEDIATE_DIR / "derived_metrics.json")


@pytest.fixture
def intermediate_reports():
    """Extracted reports intermediate JSON."""
    return _load_json(INTERMEDIATE_DIR / "reports.json")


@pytest.fixture
def intermediate_dossiers():
    """Extracted dossiers intermediate JSON."""
    return _load_json(INTERMEDIATE_DIR / "dossiers.json")


@pytest.fixture
def intermediate_cubes():
    """Extracted cubes intermediate JSON."""
    return _load_json(INTERMEDIATE_DIR / "cubes.json")


@pytest.fixture
def intermediate_relationships():
    """Extracted relationships intermediate JSON."""
    return _load_json(INTERMEDIATE_DIR / "relationships.json")


@pytest.fixture
def intermediate_hierarchies():
    """Extracted hierarchies intermediate JSON."""
    return _load_json(INTERMEDIATE_DIR / "hierarchies.json")


@pytest.fixture
def intermediate_security_filters():
    """Extracted security filters intermediate JSON."""
    return _load_json(INTERMEDIATE_DIR / "security_filters.json")


@pytest.fixture
def intermediate_prompts():
    """Extracted prompts intermediate JSON."""
    return _load_json(INTERMEDIATE_DIR / "prompts.json")


@pytest.fixture
def intermediate_freeform_sql():
    """Extracted freeform SQL intermediate JSON."""
    return _load_json(INTERMEDIATE_DIR / "freeform_sql.json")


@pytest.fixture
def intermediate_custom_groups():
    """Extracted custom groups intermediate JSON."""
    return _load_json(INTERMEDIATE_DIR / "custom_groups.json")


@pytest.fixture
def intermediate_thresholds():
    """Extracted thresholds intermediate JSON."""
    return _load_json(INTERMEDIATE_DIR / "thresholds.json")


@pytest.fixture
def intermediate_subtotals():
    """Extracted subtotals intermediate JSON."""
    return _load_json(INTERMEDIATE_DIR / "subtotals.json")


# ── Composite Fixtures ───────────────────────────────────────────

@pytest.fixture
def all_intermediate_json(tmp_path):
    """Copy all intermediate JSON files to a temp dir (simulates extraction output).

    Returns the path to the temp directory containing all 18 JSON files.
    """
    for json_file in INTERMEDIATE_DIR.glob("*.json"):
        dest = tmp_path / json_file.name
        dest.write_text(json_file.read_text(encoding='utf-8'), encoding='utf-8')
    return tmp_path


# ── Mock REST API Client ─────────────────────────────────────────

class MockMstrRestClient:
    """Mock MicroStrategy REST API client for testing.

    Returns fixture data instead of making real API calls.
    """

    def __init__(self):
        self._tables = _load_json(API_RESPONSES_DIR / "tables.json")
        self._attr_data = _load_json(API_RESPONSES_DIR / "attributes.json")
        self._fact_data = _load_json(API_RESPONSES_DIR / "facts.json")
        self._metric_data = _load_json(API_RESPONSES_DIR / "metrics.json")
        self._report_data = _load_json(API_RESPONSES_DIR / "reports.json")
        self._dossier_data = _load_json(API_RESPONSES_DIR / "dossiers.json")
        self._cube_data = _load_json(API_RESPONSES_DIR / "cubes.json")
        self._prompt_data = _load_json(API_RESPONSES_DIR / "prompts.json")
        self._hierarchy_data = _load_json(API_RESPONSES_DIR / "hierarchies.json")
        self._search_data = _load_json(API_RESPONSES_DIR / "search_results.json")

        self.base_url = "https://mstr-test.company.com/MicroStrategyLibrary"
        self.auth_token = "test-token-12345"
        self.project_id = "B7CA92F04B9FAE8D941C3E9B7E0CD754"
        self.project_name = "MicroStrategy Tutorial"

    def authenticate(self, username, password, auth_mode='standard'):
        pass

    def close(self):
        pass

    def select_project(self, project_name):
        return {"id": self.project_id, "name": project_name}

    def list_projects(self):
        return _load_json(API_RESPONSES_DIR / "projects.json")["projects"]

    def get_tables(self):
        return self._tables

    def get_table(self, table_id):
        for t in self._tables:
            if t["id"] == table_id:
                return t
        return {}

    def get_attributes(self):
        return self._attr_data["list"]

    def get_attribute(self, attr_id):
        return self._attr_data["details"].get(attr_id, {})

    def get_facts(self):
        return self._fact_data["list"]

    def get_fact(self, fact_id):
        return self._fact_data["details"].get(fact_id, {})

    def get_metrics(self):
        return self._metric_data["list"]

    def get_metric(self, metric_id):
        return self._metric_data["details"].get(metric_id, {})

    def get_user_hierarchies(self):
        return self._hierarchy_data

    def get_reports(self):
        return self._report_data["list"]

    def get_report_definition(self, report_id):
        return self._report_data["definitions"].get(report_id, {})

    def get_report_prompts(self, report_id):
        return self._prompt_data

    def get_dossiers(self):
        return self._dossier_data["list"]

    def get_dossier_definition(self, dossier_id):
        return self._dossier_data["definitions"].get(dossier_id, {})

    def get_cubes(self):
        return self._cube_data["list"]

    def get_cube_definition(self, cube_id):
        return self._cube_data["definitions"].get(cube_id, {})

    def get_filters(self):
        return []

    def search_objects(self, object_type=None, name=None, pattern=None,
                       root_folder=None, limit=1000):
        if object_type == 47:  # Security filters
            return _load_json(API_RESPONSES_DIR / "security_filters.json")
        if object_type == 1 and pattern == "":
            return self._search_data
        return []


@pytest.fixture
def mock_client():
    """Provides a mock MicroStrategy REST API client loaded with fixtures."""
    return MockMstrRestClient()


@pytest.fixture
def output_dir(tmp_path):
    """Provides a temporary output directory for generated files."""
    out = tmp_path / "output"
    out.mkdir()
    return out
