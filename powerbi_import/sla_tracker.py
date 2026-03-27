"""
SLA tracker — per-report Service Level Agreement compliance.

Tracks migration duration, fidelity score, and validation pass/fail
against configurable thresholds.  Produces a ``SLAReport`` with an
overall compliance rate.
"""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_SLA_CONFIG = {
    "max_migration_seconds": 60,
    "min_fidelity_score": 80.0,
    "require_validation_pass": True,
    "alert_on_breach": True,
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SLAResult:
    """Result of one tracked item against SLA thresholds."""

    name: str
    duration_seconds: float = 0.0
    fidelity_score: float = 0.0
    validation_passed: bool = False
    max_duration: float = 60.0
    min_fidelity: float = 80.0
    require_validation: bool = True

    @property
    def time_compliant(self):
        return self.duration_seconds <= self.max_duration

    @property
    def fidelity_compliant(self):
        return self.fidelity_score >= self.min_fidelity

    @property
    def validation_compliant(self):
        if not self.require_validation:
            return True
        return self.validation_passed

    @property
    def compliant(self):
        return (self.time_compliant
                and self.fidelity_compliant
                and self.validation_compliant)

    def to_dict(self):
        return {
            "name": self.name,
            "duration_seconds": round(self.duration_seconds, 3),
            "fidelity_score": round(self.fidelity_score, 2),
            "validation_passed": self.validation_passed,
            "time_compliant": self.time_compliant,
            "fidelity_compliant": self.fidelity_compliant,
            "validation_compliant": self.validation_compliant,
            "compliant": self.compliant,
        }


@dataclass
class SLAReport:
    """Aggregate SLA compliance report."""

    results: list = field(default_factory=list)

    @property
    def total(self):
        return len(self.results)

    @property
    def compliant_count(self):
        return sum(1 for r in self.results if r.compliant)

    @property
    def breached_count(self):
        return self.total - self.compliant_count

    @property
    def compliance_rate(self):
        if self.total == 0:
            return 100.0
        return round(100.0 * self.compliant_count / self.total, 2)

    def to_dict(self):
        return {
            "total": self.total,
            "compliant": self.compliant_count,
            "breached": self.breached_count,
            "compliance_rate": self.compliance_rate,
            "results": [r.to_dict() for r in self.results],
        }


# ---------------------------------------------------------------------------
# Tracker
# ---------------------------------------------------------------------------

class SLATracker:
    """Tracks SLA compliance across multiple items.

    Usage::

        tracker = SLATracker()
        tracker.start("Sales Report")
        # ... migration work ...
        result = tracker.record_result("Sales Report", fidelity=92.0,
                                       validation_passed=True)
        report = tracker.get_report()
    """

    def __init__(self, config=None):
        cfg = dict(DEFAULT_SLA_CONFIG)
        if config:
            cfg.update(config)
        self._max_duration = cfg["max_migration_seconds"]
        self._min_fidelity = cfg["min_fidelity_score"]
        self._require_validation = cfg["require_validation_pass"]
        self._alert_on_breach = cfg["alert_on_breach"]
        self._timers = {}  # name → monotonic start
        self._results = []

    def start(self, name):
        """Start timing an item."""
        self._timers[name] = time.monotonic()

    def record_result(self, name, fidelity=100.0, validation_passed=True):
        """Record completion and evaluate SLA compliance.

        Returns:
            SLAResult for the tracked item.
        """
        start = self._timers.pop(name, None)
        duration = (time.monotonic() - start) if start is not None else 0.0

        result = SLAResult(
            name=name,
            duration_seconds=duration,
            fidelity_score=fidelity,
            validation_passed=validation_passed,
            max_duration=self._max_duration,
            min_fidelity=self._min_fidelity,
            require_validation=self._require_validation,
        )
        self._results.append(result)

        if not result.compliant and self._alert_on_breach:
            breaches = []
            if not result.time_compliant:
                breaches.append(f"duration {result.duration_seconds:.1f}s > {self._max_duration}s")
            if not result.fidelity_compliant:
                breaches.append(f"fidelity {result.fidelity_score:.1f}% < {self._min_fidelity}%")
            if not result.validation_compliant:
                breaches.append("validation failed")
            logger.warning("SLA breach for '%s': %s", name, "; ".join(breaches))

        return result

    def get_report(self):
        """Return an SLAReport over all tracked items."""
        return SLAReport(results=list(self._results))
