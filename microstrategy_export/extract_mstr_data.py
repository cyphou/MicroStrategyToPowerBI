"""
MicroStrategy data extraction orchestrator.

Connects to MicroStrategy Intelligence Server via REST API, extracts
schema objects (tables, attributes, facts, metrics) and report/dossier
definitions, and writes intermediate JSON files for the generation layer.
"""

import os
import sys
import json
import logging

logger = logging.getLogger(__name__)

# Output directory for intermediate JSON files
_OUTPUT_DIR = os.path.dirname(__file__)


def _write_json(filename, data):
    """Write data to a JSON file in the output directory."""
    path = os.path.join(_OUTPUT_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info("Wrote %s (%d items)", filename, len(data) if isinstance(data, list) else 1)


class MstrExtractor:
    """MicroStrategy extraction orchestrator.

    Usage:
        extractor = MstrExtractor(server_url, username, password, project_name)
        extractor.extract_all()
    """

    def __init__(self, server_url, username, password, project_name,
                 auth_mode='standard', ssl_verify=True, timeout=120):
        from rest_api_client import MstrRestClient

        self.client = MstrRestClient(
            base_url=server_url,
            ssl_verify=ssl_verify,
            timeout=timeout,
        )
        self.client.authenticate(username, password, auth_mode=auth_mode)
        self.client.select_project(project_name)
        self.project_name = project_name

    @classmethod
    def from_export(cls, export_dir):
        """Create extractor from pre-exported JSON files (offline mode)."""
        instance = cls.__new__(cls)
        instance.client = None
        instance.project_name = os.path.basename(export_dir.rstrip('/\\'))
        instance._export_dir = export_dir
        return instance

    def extract_all(self):
        """Extract all objects from the MicroStrategy project."""
        print(f"Extracting all objects from project: {self.project_name}")

        if self.client is None:
            return self._load_from_export()

        try:
            # Schema extraction
            self._extract_schema()

            # Metric extraction
            self._extract_metrics()

            # Report extraction
            self._extract_reports()

            # Dossier extraction
            self._extract_dossiers()

            # Cube extraction
            self._extract_cubes()

            # Filter extraction
            self._extract_filters()

            # Prompt extraction (from reports + dossiers)
            self._extract_prompts()

            # Security filter extraction
            self._extract_security_filters()

            return True

        except Exception as e:
            logger.error("Extraction failed: %s", e, exc_info=True)
            return False
        finally:
            if self.client:
                self.client.close()

    def extract_schema_only(self):
        """Extract schema objects only (for assessment mode)."""
        try:
            self._extract_schema()
            self._extract_metrics()
            return True
        except Exception as e:
            logger.error("Schema extraction failed: %s", e, exc_info=True)
            return False
        finally:
            if self.client:
                self.client.close()

    def extract_report(self, report_name):
        """Extract a single report by name."""
        try:
            self._extract_schema()
            self._extract_metrics()

            reports = self.client.search_objects(
                object_type=3, name=report_name
            )
            if not reports:
                logger.error("Report '%s' not found", report_name)
                return False

            self._extract_report_definitions(reports[:1])
            return True
        except Exception as e:
            logger.error("Report extraction failed: %s", e, exc_info=True)
            return False
        finally:
            if self.client:
                self.client.close()

    def extract_report_by_id(self, report_id):
        """Extract a single report by ID."""
        try:
            self._extract_schema()
            self._extract_metrics()
            self._extract_report_definitions([{"id": report_id, "name": f"report_{report_id}"}])
            return True
        except Exception as e:
            logger.error("Report extraction failed: %s", e, exc_info=True)
            return False
        finally:
            if self.client:
                self.client.close()

    def extract_dossier(self, dossier_name):
        """Extract a single dossier by name."""
        try:
            self._extract_schema()
            self._extract_metrics()

            dossiers = self.client.search_objects(
                object_type=55, name=dossier_name
            )
            if not dossiers:
                logger.error("Dossier '%s' not found", dossier_name)
                return False

            self._extract_dossier_definitions(dossiers[:1])
            return True
        except Exception as e:
            logger.error("Dossier extraction failed: %s", e, exc_info=True)
            return False
        finally:
            if self.client:
                self.client.close()

    def extract_dossier_by_id(self, dossier_id):
        """Extract a single dossier by ID."""
        try:
            self._extract_schema()
            self._extract_metrics()
            self._extract_dossier_definitions([{"id": dossier_id, "name": f"dossier_{dossier_id}"}])
            return True
        except Exception as e:
            logger.error("Dossier extraction failed: %s", e, exc_info=True)
            return False
        finally:
            if self.client:
                self.client.close()

    # ── Schema extraction ────────────────────────────────────────

    def _extract_schema(self):
        """Extract tables, attributes, facts, hierarchies."""
        from schema_extractor import extract_tables, extract_attributes, extract_facts, extract_hierarchies, extract_custom_groups, extract_freeform_sql

        print("  Extracting tables...")
        tables = extract_tables(self.client)
        _write_json('datasources.json', tables)

        print("  Extracting attributes...")
        attributes = extract_attributes(self.client)
        _write_json('attributes.json', attributes)

        print("  Extracting facts...")
        facts = extract_facts(self.client)
        _write_json('facts.json', facts)

        print("  Extracting hierarchies...")
        hierarchies = extract_hierarchies(self.client)
        _write_json('hierarchies.json', hierarchies)

        print("  Extracting custom groups...")
        custom_groups = extract_custom_groups(self.client)
        _write_json('custom_groups.json', custom_groups)

        print("  Extracting freeform SQL...")
        freeform_sql = extract_freeform_sql(self.client)
        _write_json('freeform_sql.json', freeform_sql)

        # Relationships are inferred from attributes + facts
        from schema_extractor import infer_relationships
        relationships = infer_relationships(attributes, facts, tables)
        _write_json('relationships.json', relationships)

    # ── Metric extraction ────────────────────────────────────────

    def _extract_metrics(self):
        """Extract metrics and thresholds."""
        from metric_extractor import extract_metrics, extract_thresholds

        print("  Extracting metrics...")
        metrics, derived = extract_metrics(self.client)
        _write_json('metrics.json', metrics)
        _write_json('derived_metrics.json', derived)

        # Thresholds are extracted from report/dossier definitions later
        _write_json('thresholds.json', [])

    # ── Report extraction ────────────────────────────────────────

    def _extract_reports(self):
        """Extract all reports."""
        print("  Discovering reports...")
        reports = self.client.get_reports()
        print(f"    Found {len(reports)} reports")
        self._extract_report_definitions(reports)

    def _extract_report_definitions(self, reports):
        """Extract full definitions for a list of reports."""
        from report_extractor import extract_report_definition

        results = []
        prompts = []
        subtotals = []
        for rpt in reports:
            try:
                defn = self.client.get_report_definition(rpt['id'])
                parsed = extract_report_definition(defn, rpt)
                results.append(parsed)

                # Extract prompts
                try:
                    rpt_prompts = self.client.get_report_prompts(rpt['id'])
                    if rpt_prompts:
                        prompts.extend(rpt_prompts)
                except Exception:
                    pass

            except Exception as e:
                logger.warning("Failed to extract report '%s': %s", rpt.get('name', rpt['id']), e)
                results.append({
                    "id": rpt['id'],
                    "name": rpt.get('name', ''),
                    "error": str(e),
                })

        _write_json('reports.json', results)
        if prompts:
            _write_json('prompts.json', prompts)

    # ── Dossier extraction ───────────────────────────────────────

    def _extract_dossiers(self):
        """Extract all dossiers."""
        print("  Discovering dossiers...")
        dossiers = self.client.get_dossiers()
        print(f"    Found {len(dossiers)} dossiers")
        self._extract_dossier_definitions(dossiers)

    def _extract_dossier_definitions(self, dossiers):
        """Extract full definitions for a list of dossiers."""
        from dossier_extractor import extract_dossier_definition

        results = []
        for doss in dossiers:
            try:
                defn = self.client.get_dossier_definition(doss['id'])
                parsed = extract_dossier_definition(defn, doss)
                results.append(parsed)
            except Exception as e:
                logger.warning("Failed to extract dossier '%s': %s", doss.get('name', doss['id']), e)
                results.append({
                    "id": doss['id'],
                    "name": doss.get('name', ''),
                    "error": str(e),
                })

        _write_json('dossiers.json', results)

    # ── Cube extraction ──────────────────────────────────────────

    def _extract_cubes(self):
        """Extract intelligent cubes."""
        from cube_extractor import extract_cube_definition

        print("  Discovering cubes...")
        cubes = self.client.get_cubes()
        print(f"    Found {len(cubes)} cubes")

        results = []
        for cube in cubes:
            try:
                defn = self.client.get_cube_definition(cube['id'])
                parsed = extract_cube_definition(defn, cube)
                results.append(parsed)
            except Exception as e:
                logger.warning("Failed to extract cube '%s': %s", cube.get('name', cube['id']), e)

        _write_json('cubes.json', results)

    # ── Filter extraction ────────────────────────────────────────

    def _extract_filters(self):
        """Extract standalone filters."""
        print("  Extracting filters...")
        filters = self.client.get_filters()
        _write_json('filters.json', filters)

    # ── Prompt extraction ────────────────────────────────────────

    def _extract_prompts(self):
        """Extract prompts (merged from reports + dossiers if not already done)."""
        prompts_path = os.path.join(_OUTPUT_DIR, 'prompts.json')
        if not os.path.exists(prompts_path):
            _write_json('prompts.json', [])

    # ── Security filter extraction ───────────────────────────────

    def _extract_security_filters(self):
        """Extract security filters."""
        from security_extractor import extract_security_filters

        print("  Extracting security filters...")
        sec_filters = extract_security_filters(self.client)
        _write_json('security_filters.json', sec_filters)

    # ── Offline mode ─────────────────────────────────────────────

    def _load_from_export(self):
        """Load pre-exported JSON files into the output directory."""
        import shutil
        export_dir = self._export_dir
        for fname in os.listdir(export_dir):
            if fname.endswith('.json'):
                src = os.path.join(export_dir, fname)
                dst = os.path.join(_OUTPUT_DIR, fname)
                shutil.copy2(src, dst)
                logger.info("Loaded %s from export", fname)
        return True
