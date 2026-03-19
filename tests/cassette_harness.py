"""
Test cassette recorder and player for MicroStrategy REST API.

Records real API responses to JSON files for deterministic replay
in CI/CD pipelines without a live MicroStrategy server.
"""

import json
import os
import hashlib
import logging

logger = logging.getLogger(__name__)

_CASSETTES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "cassettes")


class CassetteRecorder:
    """Record HTTP interactions for later replay.

    Usage (recording):
        recorder = CassetteRecorder("test_my_scenario")
        recorder.record("GET", "/api/model/tables", response_data)
        recorder.save()

    Usage (playback):
        cassette = CassetteRecorder.load("test_my_scenario")
        data = cassette.play("GET", "/api/model/tables")
    """

    def __init__(self, name):
        self.name = name
        self.interactions = []

    def record(self, method, path, response_body, status_code=200, headers=None):
        """Record a single API interaction."""
        self.interactions.append({
            "request": {
                "method": method.upper(),
                "path": path,
            },
            "response": {
                "status_code": status_code,
                "headers": headers or {},
                "body": response_body,
            },
        })

    def save(self):
        """Persist recorded interactions to a cassette file."""
        os.makedirs(_CASSETTES_DIR, exist_ok=True)
        path = os.path.join(_CASSETTES_DIR, f"{self.name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "name": self.name,
                "interactions": self.interactions,
            }, f, indent=2, ensure_ascii=False)
        logger.info("Saved cassette: %s (%d interactions)", self.name, len(self.interactions))

    @classmethod
    def load(cls, name):
        """Load a cassette from disk."""
        path = os.path.join(_CASSETTES_DIR, f"{name}.json")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Cassette not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        instance = cls(name)
        instance.interactions = data.get("interactions", [])
        return instance

    def play(self, method, path):
        """Find and return the recorded response for a request.

        Returns:
            dict with "status_code", "headers", "body" keys
        """
        method = method.upper()
        for interaction in self.interactions:
            req = interaction["request"]
            if req["method"] == method and req["path"] == path:
                return interaction["response"]
        raise KeyError(f"No recorded interaction for {method} {path}")

    @property
    def request_count(self):
        return len(self.interactions)


class MockMstrClient:
    """A mock REST client that replays from cassettes.

    Drop-in replacement for MstrRestClient during integration tests.
    """

    def __init__(self, cassette_name):
        self.cassette = CassetteRecorder.load(cassette_name)
        self._index = 0

    def _replay(self, method, path):
        """Get recorded response body."""
        resp = self.cassette.play(method, path)
        return resp["body"]

    def get_reports(self):
        return self._replay("GET", "/api/reports")

    def get_report_definition(self, report_id):
        return self._replay("GET", f"/api/reports/{report_id}")

    def get_dossiers(self):
        return self._replay("GET", "/api/dossiers")

    def get_dossier_definition(self, dossier_id):
        return self._replay("GET", f"/api/dossiers/{dossier_id}")

    def get_cubes(self):
        return self._replay("GET", "/api/cubes")

    def get_cube_definition(self, cube_id):
        return self._replay("GET", f"/api/cubes/{cube_id}")

    def search_objects(self, **kwargs):
        return self._replay("GET", "/api/searches/results")

    def get_filters(self):
        return self._replay("GET", "/api/filters")

    def close(self):
        pass
