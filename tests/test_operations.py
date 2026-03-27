"""
Tests for v17.0 — Enterprise Operations & Monitoring.

Covers: monitoring.py, sla_tracker.py, alerts_generator.py,
        refresh_generator.py, recovery_report.py.
"""

import json
import os
import tempfile
import time
import unittest

from powerbi_import.monitoring import (
    MigrationMonitor,
    _JsonBackend,
    _AzureMonitorBackend,
    _PrometheusBackend,
    _NoneBackend,
    get_backend_names,
)
from powerbi_import.sla_tracker import (
    SLATracker,
    SLAResult,
    SLAReport,
    DEFAULT_SLA_CONFIG,
)
from powerbi_import.alerts_generator import (
    extract_alerts,
    generate_alert_rules,
    save_alert_rules,
    _normalise_operator,
)
from powerbi_import.refresh_generator import (
    generate_refresh_config,
    generate_subscription_config,
    generate_refresh_json,
    _normalise_day,
    _build_time_slots,
)
from powerbi_import.recovery_report import (
    RecoveryReport,
    CATEGORY_TMDL,
    CATEGORY_VISUAL,
    CATEGORY_DAX,
    CATEGORY_RELATIONSHIP,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    SEVERITY_ERROR,
)


# ===================================================================
# Monitoring
# ===================================================================

class TestGetBackendNames(unittest.TestCase):
    def test_returns_all_four(self):
        names = get_backend_names()
        self.assertIn("json", names)
        self.assertIn("azure", names)
        self.assertIn("prometheus", names)
        self.assertIn("none", names)


class TestJsonBackend(unittest.TestCase):
    def test_record_metric(self):
        be = _JsonBackend()
        be.record_metric("tables", 10, project="Sales")
        self.assertEqual(len(be._records), 1)
        self.assertEqual(be._records[0]["name"], "tables")
        self.assertEqual(be._records[0]["value"], 10)

    def test_record_event(self):
        be = _JsonBackend()
        be.record_event("migration_started", project="HR")
        self.assertEqual(be._records[0]["type"], "event")
        self.assertEqual(be._records[0]["properties"]["project"], "HR")

    def test_flush_writes_json(self):
        with tempfile.TemporaryDirectory() as td:
            be = _JsonBackend(output_dir=td)
            be.record_metric("x", 1)
            be.record_event("y")
            be.flush()
            path = os.path.join(td, "monitoring_log.json")
            self.assertTrue(os.path.exists(path))
            with open(path, "r") as f:
                data = json.load(f)
            self.assertEqual(len(data), 2)

    def test_flush_empty_noop(self):
        with tempfile.TemporaryDirectory() as td:
            be = _JsonBackend(output_dir=td)
            be.flush()
            self.assertFalse(
                os.path.exists(os.path.join(td, "monitoring_log.json"))
            )

    def test_flush_appends(self):
        with tempfile.TemporaryDirectory() as td:
            be = _JsonBackend(output_dir=td)
            be.record_metric("a", 1)
            be.flush()
            be.record_metric("b", 2)
            be.flush()
            with open(os.path.join(td, "monitoring_log.json")) as f:
                data = json.load(f)
            self.assertEqual(len(data), 2)


class TestNoneBackend(unittest.TestCase):
    def test_noop(self):
        be = _NoneBackend()
        be.record_metric("x", 1)
        be.record_event("y")
        be.flush()  # should not raise


class TestPrometheusBackend(unittest.TestCase):
    def test_record_and_flush(self):
        with tempfile.TemporaryDirectory() as td:
            be = _PrometheusBackend(output_dir=td)
            be.record_metric("migration_tables", 12, project="Sales")
            be.record_event("migration_done", project="Sales")
            be.flush()
            path = os.path.join(td, "metrics.prom")
            self.assertTrue(os.path.exists(path))
            content = open(path).read()
            self.assertIn("migration_tables", content)
            self.assertIn("migration_done_total", content)


class TestAzureMonitorBackend(unittest.TestCase):
    def test_buffer(self):
        be = _AzureMonitorBackend()
        be.record_metric("x", 1)
        be.record_event("y")
        self.assertEqual(len(be._buffer), 2)

    def test_flush_without_sdk(self):
        be = _AzureMonitorBackend()
        be.record_metric("x", 1)
        be.flush()  # should warn but not crash
        self.assertEqual(len(be._buffer), 0)


class TestMigrationMonitor(unittest.TestCase):
    def test_default_none_backend(self):
        monitor = MigrationMonitor()
        monitor.record_metric("x", 1)
        monitor.flush()

    def test_json_backend(self):
        with tempfile.TemporaryDirectory() as td:
            monitor = MigrationMonitor("json", output_dir=td)
            monitor.record_metric("tables", 5, proj="A")
            monitor.record_event("started", proj="A")
            monitor.record_migration("Sales", 2.5, 95.0, 10, 5, 20, 3)
            monitor.flush()
            path = os.path.join(td, "monitoring_log.json")
            with open(path) as f:
                data = json.load(f)
            self.assertGreater(len(data), 0)

    def test_unknown_backend_falls_back(self):
        monitor = MigrationMonitor("unknown_backend")
        monitor.record_metric("x", 1)
        monitor.flush()  # NoneBackend — no crash


# ===================================================================
# SLA Tracker
# ===================================================================

class TestSLAResult(unittest.TestCase):
    def test_fully_compliant(self):
        r = SLAResult(name="A", duration_seconds=5.0,
                      fidelity_score=90.0, validation_passed=True)
        self.assertTrue(r.time_compliant)
        self.assertTrue(r.fidelity_compliant)
        self.assertTrue(r.validation_compliant)
        self.assertTrue(r.compliant)

    def test_time_breach(self):
        r = SLAResult(name="B", duration_seconds=120.0, max_duration=60.0)
        self.assertFalse(r.time_compliant)
        self.assertFalse(r.compliant)

    def test_fidelity_breach(self):
        r = SLAResult(name="C", fidelity_score=50.0, min_fidelity=80.0,
                      validation_passed=True)
        self.assertFalse(r.fidelity_compliant)
        self.assertFalse(r.compliant)

    def test_validation_breach(self):
        r = SLAResult(name="D", duration_seconds=1.0, fidelity_score=90.0,
                      validation_passed=False, require_validation=True)
        self.assertFalse(r.validation_compliant)
        self.assertFalse(r.compliant)

    def test_validation_not_required(self):
        r = SLAResult(name="E", validation_passed=False, require_validation=False)
        self.assertTrue(r.validation_compliant)

    def test_to_dict(self):
        r = SLAResult(name="F", duration_seconds=1.5, fidelity_score=95.0,
                      validation_passed=True)
        d = r.to_dict()
        self.assertEqual(d["name"], "F")
        self.assertTrue(d["compliant"])


class TestSLAReport(unittest.TestCase):
    def test_empty_report(self):
        report = SLAReport()
        self.assertEqual(report.total, 0)
        self.assertEqual(report.compliance_rate, 100.0)

    def test_mixed_results(self):
        r1 = SLAResult(name="A", duration_seconds=1, fidelity_score=90,
                       validation_passed=True)
        r2 = SLAResult(name="B", duration_seconds=999, fidelity_score=10,
                       validation_passed=False, max_duration=60)
        report = SLAReport(results=[r1, r2])
        self.assertEqual(report.total, 2)
        self.assertEqual(report.compliant_count, 1)
        self.assertEqual(report.breached_count, 1)
        self.assertEqual(report.compliance_rate, 50.0)

    def test_to_dict(self):
        report = SLAReport(results=[
            SLAResult(name="X", duration_seconds=1, fidelity_score=90,
                      validation_passed=True),
        ])
        d = report.to_dict()
        self.assertEqual(d["total"], 1)
        self.assertEqual(len(d["results"]), 1)


class TestSLATracker(unittest.TestCase):
    def test_start_and_record(self):
        tracker = SLATracker()
        tracker.start("Report A")
        result = tracker.record_result("Report A", fidelity=95.0,
                                       validation_passed=True)
        self.assertIsInstance(result, SLAResult)
        self.assertTrue(result.compliant)

    def test_custom_config(self):
        tracker = SLATracker(config={"max_migration_seconds": 1,
                                     "min_fidelity_score": 99.0})
        tracker.start("X")
        time.sleep(0.01)
        result = tracker.record_result("X", fidelity=50.0)
        self.assertFalse(result.fidelity_compliant)

    def test_get_report(self):
        tracker = SLATracker()
        tracker.start("A")
        tracker.record_result("A", fidelity=100.0)
        tracker.start("B")
        tracker.record_result("B", fidelity=100.0)
        report = tracker.get_report()
        self.assertEqual(report.total, 2)

    def test_no_start_still_works(self):
        tracker = SLATracker()
        result = tracker.record_result("Orphan", fidelity=90.0)
        self.assertEqual(result.duration_seconds, 0.0)

    def test_default_config(self):
        self.assertEqual(DEFAULT_SLA_CONFIG["max_migration_seconds"], 60)
        self.assertEqual(DEFAULT_SLA_CONFIG["min_fidelity_score"], 80.0)


# ===================================================================
# Alerts Generator
# ===================================================================

class TestNormaliseOperator(unittest.TestCase):
    def test_known_operators(self):
        self.assertEqual(_normalise_operator("less_than"), "<")
        self.assertEqual(_normalise_operator("greater_than"), ">")
        self.assertEqual(_normalise_operator("equal"), "=")
        self.assertEqual(_normalise_operator(">="), ">=")

    def test_unknown_passthrough(self):
        self.assertEqual(_normalise_operator("custom_op"), "custom_op")


class TestExtractAlerts(unittest.TestCase):
    def test_from_thresholds(self):
        data = {
            "thresholds": [{
                "report_id": "RPT01",
                "metric_name": "Revenue",
                "conditions": [
                    {"operator": "less_than", "value": 100},
                    {"operator": "greater_than", "value": 500},
                ],
            }],
        }
        alerts = extract_alerts(data)
        self.assertEqual(len(alerts), 2)
        self.assertEqual(alerts[0]["measure"], "Revenue")
        self.assertEqual(alerts[0]["operator"], "<")

    def test_from_metrics(self):
        data = {
            "metrics": [{
                "name": "Profit",
                "thresholds": [{
                    "conditions": [{"operator": ">", "value": 1000}],
                }],
            }],
        }
        alerts = extract_alerts(data)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["source"], "metric_threshold")

    def test_from_prompts(self):
        data = {
            "prompts": [{
                "name": "MinRevenue",
                "type": "numeric",
                "default_value": "500",
                "linked_metric": "Revenue",
            }],
        }
        alerts = extract_alerts(data)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["threshold"], 500.0)
        self.assertEqual(alerts[0]["source"], "prompt")

    def test_empty_data(self):
        self.assertEqual(extract_alerts({}), [])

    def test_prompt_non_numeric_skipped(self):
        data = {
            "prompts": [{
                "name": "TextPrompt",
                "type": "text",
                "default_value": "hello",
            }],
        }
        self.assertEqual(extract_alerts(data), [])

    def test_prompt_invalid_value_skipped(self):
        data = {
            "prompts": [{
                "name": "Bad",
                "type": "numeric",
                "default_value": "not_a_number",
            }],
        }
        self.assertEqual(extract_alerts(data), [])


class TestGenerateAlertRules(unittest.TestCase):
    def test_basic(self):
        alerts = [{"name": "Rev alert", "measure": "Revenue",
                   "operator": ">", "threshold": 100, "source": "threshold"}]
        rules = generate_alert_rules(alerts)
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["id"], "alert_001")
        self.assertTrue(rules[0]["enabled"])

    def test_empty(self):
        self.assertEqual(generate_alert_rules([]), [])

    def test_report_id_preserved(self):
        alerts = [{"name": "X", "measure": "M", "operator": ">",
                   "threshold": 0, "source": "threshold", "report_id": "R1"}]
        rules = generate_alert_rules(alerts)
        self.assertEqual(rules[0]["report_id"], "R1")


class TestSaveAlertRules(unittest.TestCase):
    def test_writes_file(self):
        with tempfile.TemporaryDirectory() as td:
            rules = [{"id": "alert_001", "name": "Test"}]
            path = save_alert_rules(rules, td)
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                data = json.load(f)
            self.assertEqual(len(data), 1)


# ===================================================================
# Refresh Generator
# ===================================================================

class TestNormaliseDay(unittest.TestCase):
    def test_full_name(self):
        self.assertEqual(_normalise_day("monday"), "Monday")

    def test_abbreviated(self):
        self.assertEqual(_normalise_day("fri"), "Friday")

    def test_unknown_capitalised(self):
        self.assertEqual(_normalise_day("custom"), "Custom")


class TestBuildTimeSlots(unittest.TestCase):
    def test_hourly(self):
        slots = _build_time_slots(1, start_hour=6, end_hour=13)
        self.assertEqual(len(slots), 8)  # capped at 8
        self.assertEqual(slots[0], "06:00")

    def test_four_hourly(self):
        slots = _build_time_slots(4)
        self.assertIn("06:00", slots)
        self.assertIn("10:00", slots)


class TestGenerateRefreshConfig(unittest.TestCase):
    def test_empty_schedules_returns_default(self):
        cfg = generate_refresh_config([])
        self.assertTrue(cfg["enabled"])
        self.assertEqual(cfg["frequency"], "Daily")
        self.assertIn("06:00", cfg["times"])

    def test_basic_daily(self):
        schedules = [{"frequency": "daily", "times": ["08:00", "16:00"],
                      "timezone": "America/New_York"}]
        cfg = generate_refresh_config(schedules)
        self.assertEqual(cfg["frequency"], "Daily")
        self.assertEqual(cfg["timezone"], "America/New_York")
        self.assertEqual(len(cfg["times"]), 2)

    def test_weekly_with_days(self):
        schedules = [{"frequency": "weekly",
                      "days": ["monday", "wed", "Friday"],
                      "times": ["09:00"]}]
        cfg = generate_refresh_config(schedules)
        self.assertEqual(cfg["frequency"], "Weekly")
        self.assertIn("Monday", cfg["days"])
        self.assertIn("Wednesday", cfg["days"])

    def test_hourly_generates_time_slots(self):
        schedules = [{"frequency": "hourly", "interval_hours": 2}]
        cfg = generate_refresh_config(schedules)
        self.assertEqual(cfg["frequency"], "Daily")
        self.assertGreater(len(cfg["times"]), 1)

    def test_cache_policy_hint(self):
        schedules = [{"frequency": "daily"}]
        cache = [{"enabled": True, "expiry_minutes": 30}]
        cfg = generate_refresh_config(schedules, cache_policies=cache)
        self.assertEqual(cfg["cacheExpiryMinutes"], 30)

    def test_pro_limit_cap(self):
        schedules = [{"frequency": "hourly", "interval_hours": 1}]
        cfg = generate_refresh_config(schedules)
        self.assertLessEqual(len(cfg["times"]), 8)


class TestGenerateSubscriptionConfig(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(generate_subscription_config([]), [])
        self.assertEqual(generate_subscription_config(None), [])

    def test_basic(self):
        subs = [{"name": "Daily email", "delivery_type": "email",
                 "recipients": ["user@example.com"]}]
        result = generate_subscription_config(subs)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "Daily email")
        self.assertEqual(result[0]["recipients"], ["user@example.com"])


class TestGenerateRefreshJson(unittest.TestCase):
    def test_complete(self):
        result = generate_refresh_json(
            schedules=[{"frequency": "daily", "times": ["07:00"]}],
            subscriptions=[{"name": "Sub1"}],
        )
        self.assertIn("refreshSchedule", result)
        self.assertIn("notifications", result)
        self.assertTrue(result["refreshSchedule"]["enabled"])

    def test_empty(self):
        result = generate_refresh_json()
        self.assertIn("refreshSchedule", result)
        self.assertEqual(result["notifications"], [])


# ===================================================================
# Recovery Report
# ===================================================================

class TestRecoveryReport(unittest.TestCase):
    def test_empty(self):
        rr = RecoveryReport()
        self.assertFalse(rr.has_repairs)
        self.assertEqual(rr.count, 0)

    def test_record_and_query(self):
        rr = RecoveryReport()
        rr.record(CATEGORY_TMDL, "sanitised_name",
                  description="Fixed spaces", severity=SEVERITY_INFO,
                  item_name="Sales Amount", original_value="Sales Amount",
                  repaired_value="Sales_Amount")
        self.assertTrue(rr.has_repairs)
        self.assertEqual(rr.count, 1)

    def test_get_summary(self):
        rr = RecoveryReport()
        rr.record(CATEGORY_TMDL, "fix1", severity=SEVERITY_INFO)
        rr.record(CATEGORY_VISUAL, "fix2", severity=SEVERITY_WARNING)
        rr.record(CATEGORY_TMDL, "fix3", severity=SEVERITY_ERROR)
        summary = rr.get_summary()
        self.assertEqual(summary["total_repairs"], 3)
        self.assertEqual(summary["by_category"]["TMDL"], 2)
        self.assertEqual(summary["by_severity"]["ERROR"], 1)

    def test_get_repairs_filtered(self):
        rr = RecoveryReport()
        rr.record(CATEGORY_TMDL, "a", severity=SEVERITY_INFO)
        rr.record(CATEGORY_DAX, "b", severity=SEVERITY_WARNING)
        self.assertEqual(len(rr.get_repairs(category=CATEGORY_TMDL)), 1)
        self.assertEqual(len(rr.get_repairs(severity=SEVERITY_WARNING)), 1)

    def test_to_dict(self):
        rr = RecoveryReport()
        rr.record(CATEGORY_RELATIONSHIP, "fix", severity=SEVERITY_INFO)
        d = rr.to_dict()
        self.assertIn("summary", d)
        self.assertIn("repairs", d)
        self.assertEqual(len(d["repairs"]), 1)

    def test_save(self):
        with tempfile.TemporaryDirectory() as td:
            rr = RecoveryReport()
            rr.record(CATEGORY_VISUAL, "fix", severity=SEVERITY_INFO)
            path = rr.save(td)
            self.assertTrue(os.path.exists(path))
            with open(path) as f:
                data = json.load(f)
            self.assertEqual(data["summary"]["total_repairs"], 1)

    def test_merge_into(self):
        rr = RecoveryReport()
        rr.record(CATEGORY_TMDL, "fix", severity=SEVERITY_INFO)
        summary = {"tables": 5}
        rr.merge_into(summary)
        self.assertIn("recovery", summary)
        self.assertEqual(summary["recovery"]["summary"]["total_repairs"], 1)

    def test_merge_into_empty_noop(self):
        rr = RecoveryReport()
        summary = {"tables": 5}
        rr.merge_into(summary)
        self.assertNotIn("recovery", summary)

    def test_print_summary_no_repairs(self):
        rr = RecoveryReport()
        rr.print_summary()  # should not raise

    def test_print_summary_with_repairs(self):
        rr = RecoveryReport()
        rr.record(CATEGORY_TMDL, "fix", severity=SEVERITY_ERROR)
        rr.record(CATEGORY_DAX, "fix2", severity=SEVERITY_WARNING)
        rr.print_summary()  # should not raise

    def test_follow_up_field(self):
        rr = RecoveryReport()
        rr.record(CATEGORY_TMDL, "fix", follow_up="Check manually")
        repairs = rr.get_repairs()
        self.assertEqual(repairs[0]["follow_up"], "Check manually")


if __name__ == "__main__":
    unittest.main()
