"""
Import orchestrator for Power BI project generation.

Loads extracted MicroStrategy JSON files and drives the .pbip project
generation pipeline (TMDL model + PBIR report).
"""

import os
import json
import logging

from powerbi_import.pbip_generator import generate_pbip

logger = logging.getLogger(__name__)


def _load_json(path):
    """Load a JSON file, returning empty list on error."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else [data]
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Could not load %s: %s", path, e)
        return []


class PowerBIImporter:
    """Power BI project importer/generator."""

    # 18 intermediate JSON file keys
    _FILE_MAP = {
        'datasources': 'datasources.json',
        'attributes': 'attributes.json',
        'facts': 'facts.json',
        'metrics': 'metrics.json',
        'derived_metrics': 'derived_metrics.json',
        'reports': 'reports.json',
        'dossiers': 'dossiers.json',
        'cubes': 'cubes.json',
        'filters': 'filters.json',
        'prompts': 'prompts.json',
        'custom_groups': 'custom_groups.json',
        'consolidations': 'consolidations.json',
        'hierarchies': 'hierarchies.json',
        'relationships': 'relationships.json',
        'security_filters': 'security_filters.json',
        'freeform_sql': 'freeform_sql.json',
        'thresholds': 'thresholds.json',
        'subtotals': 'subtotals.json',
    }

    def __init__(self, source_dir=None):
        self.source_dir = source_dir or 'microstrategy_export/'

    def import_all(self, generate_pbip_flag=True, report_name=None,
                   output_dir=None, calendar_start=None, calendar_end=None,
                   culture=None, no_calendar=False):
        """Import all extracted objects and generate Power BI project.

        Args:
            generate_pbip_flag: If True, generates .pbip project
            report_name: Override report name
            output_dir: Output directory
            calendar_start: Start year for Calendar table
            calendar_end: End year for Calendar table
            culture: Culture/locale override

        Returns:
            dict with generation statistics, or False on error
        """
        print("=" * 80)
        print("IMPORT → POWER BI")
        print("=" * 80)
        print()

        # Load all extracted JSON
        converted = self._load_converted_objects()

        if not converted.get('datasources') and not converted.get('attributes'):
            print("Error: No extracted data found")
            return False

        report_name = report_name or 'MicroStrategy Report'
        output_dir = output_dir or 'artifacts/'

        if not generate_pbip_flag:
            return True

        print(f"Generating .pbip project: {report_name}")
        print()

        # Delegate to the pbip_generator which wires TMDL + visuals + scaffold
        stats = generate_pbip(converted, output_dir, report_name=report_name, no_calendar=no_calendar)

        # Print summary
        print()
        print("  Semantic Model:")
        print(f"    Tables:        {stats['tables']}")
        print(f"    Columns:       {stats['columns']}")
        print(f"    Measures:      {stats['measures']}")
        print(f"    Relationships: {stats['relationships']}")
        print(f"    Hierarchies:   {stats['hierarchies']}")
        print(f"    RLS Roles:     {stats['roles']}")
        print()
        print("  Report:")
        print(f"    Pages:         {stats['pages']}")
        print(f"    Visuals:       {stats['visuals']}")
        print(f"    Slicers:       {stats['slicers']}")
        if stats.get('unsupported_visuals'):
            print(f"    Unsupported:   {stats['unsupported_visuals']}")
        print()

        # Write migration summary JSON
        summary = self._build_summary(stats, report_name, output_dir, converted)
        summary_path = os.path.join(output_dir, 'migration_summary.json')
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"  Migration summary: {summary_path}")

        return summary

    def _load_converted_objects(self):
        """Load all intermediate JSON files."""
        obj = {}
        for key, filename in self._FILE_MAP.items():
            path = os.path.join(self.source_dir, filename)
            obj[key] = _load_json(path)
            if obj[key]:
                logger.info("Loaded %d %s", len(obj[key]), key)
        return obj

    def _build_summary(self, stats, report_name, output_dir, converted):
        """Build a migration summary dict."""
        return {
            "report_name": report_name,
            "output_dir": output_dir,
            "tables": stats["tables"],
            "columns": stats["columns"],
            "measures": stats["measures"],
            "relationships": stats["relationships"],
            "hierarchies": stats["hierarchies"],
            "roles": stats["roles"],
            "pages": stats["pages"],
            "visuals": stats["visuals"],
            "slicers": stats["slicers"],
            "unsupported_visuals": stats.get("unsupported_visuals", 0),
            "attributes": len(converted.get("attributes", [])),
            "facts": len(converted.get("facts", [])),
            "metrics": len(converted.get("metrics", [])),
            "reports": len(converted.get("reports", [])),
            "dossiers": len(converted.get("dossiers", [])),
            "security_filters": len(converted.get("security_filters", [])),
            "status": "complete",
            "warnings": stats.get("warnings", []),
        }

