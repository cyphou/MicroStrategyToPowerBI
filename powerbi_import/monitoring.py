"""
Monitoring module — metrics export with pluggable backends.

Supports JSON file, Azure Monitor, Prometheus text, and no-op backends.
Strategy pattern: ``MigrationMonitor`` delegates to one of four backends.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------

class _JsonBackend:
    """Writes metrics/events to a JSON file."""

    def __init__(self, output_dir="artifacts"):
        self._output_dir = output_dir
        self._records = []

    def record_metric(self, name, value, **dimensions):
        self._records.append({
            "type": "metric",
            "name": name,
            "value": value,
            "dimensions": dimensions,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def record_event(self, name, **properties):
        self._records.append({
            "type": "event",
            "name": name,
            "properties": properties,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def flush(self):
        if not self._records:
            return
        os.makedirs(self._output_dir, exist_ok=True)
        path = os.path.join(self._output_dir, "monitoring_log.json")
        existing = []
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, OSError):
                existing = []
        existing.extend(self._records)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
        logger.info("Flushed %d monitoring records to %s", len(self._records), path)
        self._records.clear()


class _AzureMonitorBackend:
    """Sends metrics/events to Azure Monitor (requires opencensus or azure-monitor-opentelemetry)."""

    def __init__(self, connection_string=None):
        self._connection_string = connection_string or os.environ.get(
            "APPLICATIONINSIGHTS_CONNECTION_STRING", ""
        )
        self._buffer = []

    def record_metric(self, name, value, **dimensions):
        self._buffer.append({
            "type": "metric",
            "name": name,
            "value": value,
            "dimensions": dimensions,
        })

    def record_event(self, name, **properties):
        self._buffer.append({
            "type": "event",
            "name": name,
            "properties": properties,
        })

    def flush(self):
        if not self._buffer:
            return
        try:
            from opentelemetry import metrics as otel_metrics
            meter = otel_metrics.get_meter("mstr_migration")
            for rec in self._buffer:
                if rec["type"] == "metric":
                    gauge = meter.create_gauge(rec["name"])
                    gauge.set(rec["value"], attributes=rec.get("dimensions", {}))
            logger.info("Flushed %d records to Azure Monitor", len(self._buffer))
        except ImportError:
            logger.warning(
                "Azure Monitor SDK not installed — metrics buffered but not sent. "
                "Install opentelemetry-sdk and azure-monitor-opentelemetry-exporter."
            )
        self._buffer.clear()


class _PrometheusBackend:
    """Writes metrics in Prometheus text exposition format."""

    def __init__(self, output_dir="artifacts"):
        self._output_dir = output_dir
        self._metrics = []

    def record_metric(self, name, value, **dimensions):
        labels = ",".join(f'{k}="{v}"' for k, v in sorted(dimensions.items()))
        label_str = "{" + labels + "}" if labels else ""
        self._metrics.append(f"{name}{label_str} {value}")

    def record_event(self, name, **properties):
        labels = ",".join(f'{k}="{v}"' for k, v in sorted(properties.items()))
        label_str = "{" + labels + "}" if labels else ""
        self._metrics.append(f'{name}_total{label_str} 1')

    def flush(self):
        if not self._metrics:
            return
        os.makedirs(self._output_dir, exist_ok=True)
        path = os.path.join(self._output_dir, "metrics.prom")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(self._metrics) + "\n")
        logger.info("Flushed %d Prometheus metrics to %s", len(self._metrics), path)
        self._metrics.clear()


class _NoneBackend:
    """No-op backend — discards all data silently."""

    def record_metric(self, name, value, **dimensions):
        pass

    def record_event(self, name, **properties):
        pass

    def flush(self):
        pass


# ---------------------------------------------------------------------------
# Backend registry
# ---------------------------------------------------------------------------

_BACKENDS = {
    "json": _JsonBackend,
    "azure": _AzureMonitorBackend,
    "prometheus": _PrometheusBackend,
    "none": _NoneBackend,
}


def get_backend_names():
    """Return supported backend names."""
    return list(_BACKENDS.keys())


# ---------------------------------------------------------------------------
# Facade
# ---------------------------------------------------------------------------

class MigrationMonitor:
    """Unified monitoring facade.

    Usage::

        monitor = MigrationMonitor("json", output_dir="artifacts")
        monitor.record_metric("tables_generated", 12, project="Sales")
        monitor.record_migration("Sales", 3.2, 95.0, 12, 8, 24, 5)
        monitor.flush()
    """

    def __init__(self, backend="none", **kwargs):
        cls = _BACKENDS.get(backend, _NoneBackend)
        self._backend = cls(**kwargs)
        self._start_time = time.monotonic()
        logger.info("Monitoring backend: %s", backend)

    def record_metric(self, name, value, **dimensions):
        """Record a named metric with optional dimensions."""
        self._backend.record_metric(name, value, **dimensions)

    def record_event(self, name, **properties):
        """Record a named event with optional properties."""
        self._backend.record_event(name, **properties)

    def record_migration(self, project_name, duration, fidelity,
                         tables, measures, visuals, pages):
        """Record a completed migration as a batch of metrics."""
        dims = {"project": project_name}
        self._backend.record_metric("migration_duration_seconds", duration, **dims)
        self._backend.record_metric("migration_fidelity_pct", fidelity, **dims)
        self._backend.record_metric("migration_tables", tables, **dims)
        self._backend.record_metric("migration_measures", measures, **dims)
        self._backend.record_metric("migration_visuals", visuals, **dims)
        self._backend.record_metric("migration_pages", pages, **dims)
        self._backend.record_event("migration_completed", project=project_name)

    def flush(self):
        """Flush buffered data to the backend."""
        self._backend.flush()
