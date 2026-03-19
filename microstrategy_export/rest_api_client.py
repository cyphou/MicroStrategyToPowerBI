"""
MicroStrategy REST API Client

Handles authentication, session management, and API calls to MicroStrategy
Intelligence Server via the REST API v2.

Supported auth modes: standard, ldap, saml, oauth
"""

import logging
import time
import json
from urllib.parse import urljoin

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger(__name__)


# MicroStrategy object type IDs
OBJECT_TYPE_FILTER = 1
OBJECT_TYPE_REPORT = 3
OBJECT_TYPE_METRIC = 4
OBJECT_TYPE_PROMPT = 10
OBJECT_TYPE_ATTRIBUTE = 12
OBJECT_TYPE_FACT = 13
OBJECT_TYPE_TABLE = 15
OBJECT_TYPE_CUBE = 21
OBJECT_TYPE_DOSSIER = 55
OBJECT_TYPE_DOCUMENT = 55


class MstrApiError(Exception):
    """MicroStrategy API error with status code and message."""

    def __init__(self, status_code, message, ticket_id=None):
        self.status_code = status_code
        self.ticket_id = ticket_id
        super().__init__(f"HTTP {status_code}: {message}")


class MstrRestClient:
    """MicroStrategy REST API v2 client.

    Usage:
        client = MstrRestClient("https://mstr.company.com/MicroStrategyLibrary")
        client.authenticate("admin", "password")
        projects = client.list_projects()
        client.close()
    """

    def __init__(self, base_url, ssl_verify=True, timeout=120, max_retries=3):
        if requests is None:
            raise ImportError(
                "The 'requests' library is required. Install it with: pip install requests"
            )

        self.base_url = base_url.rstrip('/')
        self.ssl_verify = ssl_verify
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.verify = ssl_verify
        self.auth_token = None
        self.cookies = None
        self.project_id = None
        self.project_name = None

    def authenticate(self, username, password, auth_mode='standard'):
        """Authenticate with MicroStrategy and obtain session token."""
        login_mode_map = {
            'standard': 1,
            'ldap': 16,
            'saml': 1048576,
            'oauth': 65536,
        }
        login_mode = login_mode_map.get(auth_mode, 1)

        url = f"{self.base_url}/api/auth/login"
        body = {
            "username": username,
            "password": password,
            "loginMode": login_mode,
        }

        resp = self._request('POST', url, json=body, auth_required=False)
        self.auth_token = resp.headers.get('X-MSTR-AuthToken')
        self.cookies = resp.cookies
        self.session.headers.update({'X-MSTR-AuthToken': self.auth_token})
        logger.info("Authenticated successfully as '%s'", username)

    def close(self):
        """Close the session and logout."""
        if self.auth_token:
            try:
                url = f"{self.base_url}/api/auth/logout"
                self._request('POST', url)
            except Exception:
                pass
            self.auth_token = None

    def select_project(self, project_name):
        """Select a project by name."""
        projects = self.list_projects()
        for p in projects:
            if p.get('name', '').lower() == project_name.lower():
                self.project_id = p['id']
                self.project_name = p['name']
                self.session.headers['X-MSTR-ProjectID'] = self.project_id
                logger.info("Selected project: %s (%s)", self.project_name, self.project_id)
                return p
        raise ValueError(f"Project '{project_name}' not found. Available: {[p['name'] for p in projects]}")

    # ── Project APIs ──────────────────────────────────────────────

    def list_projects(self):
        """List all projects."""
        url = f"{self.base_url}/api/projects"
        resp = self._request('GET', url)
        return resp.json()

    # ── Modeling APIs ─────────────────────────────────────────────

    def get_tables(self):
        """Get all tables in the project schema."""
        url = f"{self.base_url}/api/model/tables"
        return self._get_paginated(url)

    def get_table(self, table_id):
        """Get table definition by ID."""
        url = f"{self.base_url}/api/model/tables/{table_id}"
        resp = self._request('GET', url)
        return resp.json()

    def get_attributes(self):
        """Get all attributes in the project schema."""
        url = f"{self.base_url}/api/model/attributes"
        return self._get_paginated(url)

    def get_attribute(self, attribute_id):
        """Get attribute definition by ID (including forms)."""
        url = f"{self.base_url}/api/model/attributes/{attribute_id}"
        resp = self._request('GET', url)
        return resp.json()

    def get_facts(self):
        """Get all facts in the project schema."""
        url = f"{self.base_url}/api/model/facts"
        return self._get_paginated(url)

    def get_fact(self, fact_id):
        """Get fact definition by ID."""
        url = f"{self.base_url}/api/model/facts/{fact_id}"
        resp = self._request('GET', url)
        return resp.json()

    def get_user_hierarchies(self):
        """Get all user hierarchies."""
        url = f"{self.base_url}/api/model/hierarchies"
        return self._get_paginated(url)

    # ── Metric APIs ──────────────────────────────────────────────

    def get_metrics(self):
        """Get all metrics via search."""
        return self.search_objects(object_type=OBJECT_TYPE_METRIC)

    def get_metric(self, metric_id):
        """Get metric definition by ID."""
        url = f"{self.base_url}/api/model/metrics/{metric_id}"
        resp = self._request('GET', url)
        return resp.json()

    # ── Report APIs ──────────────────────────────────────────────

    def get_reports(self):
        """Get all reports via search."""
        return self.search_objects(object_type=OBJECT_TYPE_REPORT)

    def get_report_definition(self, report_id):
        """Get report definition."""
        url = f"{self.base_url}/api/v2/reports/{report_id}"
        resp = self._request('GET', url)
        return resp.json()

    def get_report_instance(self, report_id, offset=0, limit=1000):
        """Execute a report and get results."""
        url = f"{self.base_url}/api/v2/reports/{report_id}/instances"
        body = {"offset": offset, "limit": limit}
        resp = self._request('POST', url, json=body)
        return resp.json()

    def get_report_prompts(self, report_id):
        """Get prompts for a report."""
        url = f"{self.base_url}/api/v2/reports/{report_id}/prompts"
        resp = self._request('GET', url)
        return resp.json()

    # ── Dossier APIs ─────────────────────────────────────────────

    def get_dossiers(self):
        """Get all dossiers via search."""
        return self.search_objects(object_type=OBJECT_TYPE_DOSSIER)

    def get_dossier_definition(self, dossier_id):
        """Get dossier definition (chapters, pages, visualizations)."""
        url = f"{self.base_url}/api/v2/dossiers/{dossier_id}/definition"
        resp = self._request('GET', url)
        return resp.json()

    def get_dossier_instance(self, dossier_id):
        """Create a dossier instance for data retrieval."""
        url = f"{self.base_url}/api/v2/dossiers/{dossier_id}/instances"
        resp = self._request('POST', url)
        return resp.json()

    # ── Cube APIs ────────────────────────────────────────────────

    def get_cubes(self):
        """Get all cubes via search."""
        return self.search_objects(object_type=OBJECT_TYPE_CUBE)

    def get_cube_definition(self, cube_id):
        """Get cube definition."""
        url = f"{self.base_url}/api/v2/cubes/{cube_id}"
        resp = self._request('GET', url)
        return resp.json()

    # ── Filter APIs ──────────────────────────────────────────────

    def get_filters(self):
        """Get all filters via search."""
        return self.search_objects(object_type=OBJECT_TYPE_FILTER)

    # ── Search API ───────────────────────────────────────────────

    def search_objects(self, object_type=None, name=None, pattern=None,
                       root_folder=None, limit=1000):
        """Search for objects in the project."""
        url = f"{self.base_url}/api/searches/results"
        params = {"limit": limit}
        if object_type is not None:
            params['type'] = object_type
        if name:
            params['name'] = name
        if pattern:
            params['pattern'] = 4  # Contains
            params['name'] = pattern
        if root_folder:
            params['root'] = root_folder

        results = []
        offset = 0
        while True:
            params['offset'] = offset
            resp = self._request('GET', url, params=params)
            data = resp.json()
            batch = data.get('result', [])
            results.extend(batch)
            total = data.get('totalItems', len(batch))
            offset += len(batch)
            if offset >= total or not batch:
                break

        return results

    # ── Internal helpers ─────────────────────────────────────────

    def _request(self, method, url, auth_required=True, **kwargs):
        """Execute an HTTP request with retry logic."""
        kwargs.setdefault('timeout', self.timeout)

        for attempt in range(self.max_retries):
            try:
                resp = self.session.request(method, url, **kwargs)

                if resp.status_code == 401 and auth_required:
                    raise MstrApiError(401, "Authentication failed or session expired")
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get('Retry-After', 5))
                    logger.warning("Rate limited (429). Retrying after %ds...", retry_after)
                    time.sleep(retry_after)
                    continue
                if resp.status_code >= 500:
                    if attempt < self.max_retries - 1:
                        wait = 2 ** attempt
                        logger.warning("Server error %d. Retrying in %ds...", resp.status_code, wait)
                        time.sleep(wait)
                        continue

                resp.raise_for_status()
                return resp

            except requests.exceptions.ConnectionError as e:
                if attempt < self.max_retries - 1:
                    wait = 2 ** attempt
                    logger.warning("Connection error. Retrying in %ds... (%s)", wait, e)
                    time.sleep(wait)
                    continue
                raise

        raise MstrApiError(0, f"Max retries ({self.max_retries}) exceeded for {method} {url}")

    def _get_paginated(self, url, limit=1000):
        """Handle paginated GET responses for Modeling API."""
        params = {"limit": limit, "offset": 0}
        results = []
        while True:
            resp = self._request('GET', url, params=params)
            data = resp.json()

            # Modeling API returns list directly or {"data": [...], "totalItems": N}
            if isinstance(data, list):
                results.extend(data)
                break
            elif 'data' in data:
                results.extend(data['data'])
                total = data.get('totalItems', len(results))
                params['offset'] += len(data['data'])
                if params['offset'] >= total or not data['data']:
                    break
            else:
                results.append(data)
                break

        return results
