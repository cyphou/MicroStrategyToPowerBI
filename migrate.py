"""
Main script for MicroStrategy to Power BI / Fabric migration

Pipeline:
1. Extract schema + objects from MicroStrategy (via REST API or JSON exports)
2. Generate the Power BI project (.pbip) with TMDL model
3. Generate migration report with per-item fidelity tracking

Supports:
- Single report/dossier migration:  python migrate.py --server URL --project P --dossier D
- Batch migration:                  python migrate.py --server URL --project P --batch
- Assessment only:                  python migrate.py --server URL --project P --assess
- Custom output directory:          python migrate.py ... --output-dir out/
- Deploy to Power BI Service:       python migrate.py ... --deploy WORKSPACE_ID
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
from enum import IntEnum


# ── Structured exit codes ────────────────────────────────────────────

class ExitCode(IntEnum):
    """Structured exit codes for CI/CD integration."""
    SUCCESS = 0
    GENERAL_ERROR = 1
    CONNECTION_FAILED = 2
    EXTRACTION_FAILED = 3
    GENERATION_FAILED = 4
    VALIDATION_FAILED = 5
    ASSESSMENT_FAILED = 6
    BATCH_PARTIAL_FAIL = 7
    AUTH_FAILED = 8
    KEYBOARD_INTERRUPT = 130


# Ensure Unicode output on Windows consoles
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, OSError):
        pass


# ── Structured logging setup ────────────────────────────────────────

logger = logging.getLogger('mstr_to_powerbi')


def setup_logging(verbose=False, log_file=None, quiet=False):
    """Configure structured logging."""
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    fmt = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    datefmt = '%Y-%m-%d %H:%M:%S'

    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        os.makedirs(os.path.dirname(log_file) or '.', exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding='utf-8'))

    logging.basicConfig(level=level, format=fmt, datefmt=datefmt, handlers=handlers)
    if not verbose:
        logging.getLogger('mstr_to_powerbi').setLevel(logging.INFO)


# ── Migration statistics tracker ────────────────────────────────────

class MigrationStats:
    """Tracks statistics across all pipeline steps."""

    def __init__(self):
        # Extraction
        self.project_name = ""
        self.tables = 0
        self.attributes = 0
        self.facts = 0
        self.metrics = 0
        self.derived_metrics = 0
        self.reports = 0
        self.dossiers = 0
        self.cubes = 0
        self.filters = 0
        self.prompts = 0
        self.custom_groups = 0
        self.consolidations = 0
        self.hierarchies = 0
        self.security_filters = 0
        self.freeform_sql = 0
        self.thresholds = 0
        # Generation
        self.tmdl_tables = 0
        self.tmdl_columns = 0
        self.tmdl_measures = 0
        self.tmdl_relationships = 0
        self.tmdl_hierarchies = 0
        self.tmdl_roles = 0
        self.visuals_generated = 0
        self.pages_generated = 0
        self.pbip_path = ""
        # Diagnostics
        self.warnings = []
        self.skipped = []
        self.manual_review = []

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}


_stats = MigrationStats()


def print_header(text):
    """Print a formatted header."""
    print()
    print("=" * 80)
    print(text.center(80))
    print("=" * 80)
    print()


def print_step(step_num, total_steps, text):
    """Print a step indicator."""
    print(f"\n[Step {step_num}/{total_steps}] {text}")
    print("-" * 80)


def run_extraction(args):
    """Run MicroStrategy extraction."""
    global _stats
    print_step(1, 2, "MICROSTRATEGY OBJECTS EXTRACTION")

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'microstrategy_export'))
    try:
        from extract_mstr_data import MstrExtractor

        if args.from_export:
            # Offline mode: load from exported JSON files
            print(f"Source: JSON exports at {args.from_export}")
            extractor = MstrExtractor.from_export(args.from_export)
        else:
            # Online mode: connect to MicroStrategy REST API
            print(f"Server: {args.server}")
            print(f"Project: {args.project}")
            extractor = MstrExtractor(
                server_url=args.server,
                username=args.username,
                password=args.password,
                project_name=args.project,
                auth_mode=getattr(args, 'auth_mode', 'standard'),
            )

        # Run extraction
        if args.report:
            success = extractor.extract_report(args.report)
        elif args.report_id:
            success = extractor.extract_report_by_id(args.report_id)
        elif args.dossier:
            success = extractor.extract_dossier(args.dossier)
        elif args.dossier_id:
            success = extractor.extract_dossier_by_id(args.dossier_id)
        elif getattr(args, 'batch', False):
            success = extractor.extract_all()
        elif getattr(args, 'assess', False):
            success = extractor.extract_schema_only()
        else:
            success = extractor.extract_all()

        if success:
            # Collect extraction counts
            json_dir = os.path.join(os.path.dirname(__file__), 'microstrategy_export')
            for attr, fname in [
                ('tables', 'datasources.json'),
                ('attributes', 'attributes.json'),
                ('facts', 'facts.json'),
                ('metrics', 'metrics.json'),
                ('derived_metrics', 'derived_metrics.json'),
                ('reports', 'reports.json'),
                ('dossiers', 'dossiers.json'),
                ('cubes', 'cubes.json'),
                ('filters', 'filters.json'),
                ('prompts', 'prompts.json'),
                ('custom_groups', 'custom_groups.json'),
                ('consolidations', 'consolidations.json'),
                ('hierarchies', 'hierarchies.json'),
                ('security_filters', 'security_filters.json'),
                ('freeform_sql', 'freeform_sql.json'),
                ('thresholds', 'thresholds.json'),
            ]:
                fpath = os.path.join(json_dir, fname)
                if os.path.exists(fpath):
                    try:
                        with open(fpath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        setattr(_stats, attr, len(data) if isinstance(data, list) else 0)
                    except (json.JSONDecodeError, OSError) as e:
                        logger.debug("Could not load stats from %s: %s", fname, e)

            print("\n✓ Extraction completed successfully")
            return True
        else:
            print("\n✗ Error during extraction")
            return False

    except Exception as e:
        logger.error(f"Extraction failed: {e}", exc_info=True)
        print(f"\n✗ Error during extraction: {str(e)}")
        return False


def run_generation(output_dir=None, report_name=None, culture=None, shared_model=False, no_calendar=False):
    """Run Power BI project generation."""
    global _stats
    print_step(2, 2, "POWER BI PROJECT GENERATION")

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'powerbi_import'))
    try:
        from import_to_powerbi import PowerBIImporter

        importer = PowerBIImporter(source_dir='microstrategy_export/')

        if shared_model:
            result = importer.import_all(
                generate_pbip_flag=True,
                report_name=report_name or _stats.project_name,
                output_dir=output_dir,
                culture=culture,
                no_calendar=no_calendar,
            )
            # Also generate a shared model if requested
            try:
                from powerbi_import.shared_model import generate_shared_model
                converted = importer._load_converted_objects()
                generate_shared_model(converted, output_dir or 'artifacts/',
                                      model_name=report_name or _stats.project_name)
                print("  ✓ Shared semantic model generated")
            except Exception as e:
                logger.warning("Shared model generation failed: %s", e)
        else:
            result = importer.import_all(
                generate_pbip_flag=True,
                report_name=report_name or _stats.project_name,
                output_dir=output_dir,
                culture=culture,
                no_calendar=no_calendar,
            )

        if result:
            print("\n✓ Power BI project generated successfully")
            return True
        else:
            print("\n✗ Error during generation")
            return False

    except Exception as e:
        logger.error(f"Generation failed: {e}", exc_info=True)
        print(f"\n✗ Error during generation: {str(e)}")
        return False


def run_batch_generation(args):
    """Run batch migration: generate one .pbip per report/dossier."""
    global _stats
    print_step(2, 2, "POWER BI BATCH GENERATION")

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'powerbi_import'))
    try:
        from import_to_powerbi import PowerBIImporter

        importer = PowerBIImporter(source_dir='microstrategy_export/')
        converted = importer._load_converted_objects()
        output_dir = args.output_dir or 'artifacts/'
        os.makedirs(output_dir, exist_ok=True)

        reports = converted.get('reports', [])
        dossiers = converted.get('dossiers', [])
        total = len(reports) + len(dossiers)
        succeeded = 0
        failed = 0

        # Generate one project per report
        for i, report in enumerate(reports, 1):
            name = report.get('name', f'Report_{i}')
            obj_data = dict(converted)
            obj_data['reports'] = [report]
            obj_data['dossiers'] = []
            try:
                from powerbi_import.pbip_generator import generate_pbip
                sub_dir = os.path.join(output_dir, _safe_filename(name))
                generate_pbip(obj_data, sub_dir, report_name=name,
                              no_calendar=getattr(args, 'no_calendar', False))
                print(f"  [{i}/{total}] ✓ {name}")
                succeeded += 1
            except Exception as e:
                logger.error("Failed to generate %s: %s", name, e)
                print(f"  [{i}/{total}] ✗ {name}: {e}")
                failed += 1

        # Generate one project per dossier
        for j, dossier in enumerate(dossiers, len(reports) + 1):
            name = dossier.get('name', f'Dossier_{j}')
            obj_data = dict(converted)
            obj_data['reports'] = []
            obj_data['dossiers'] = [dossier]
            try:
                from powerbi_import.pbip_generator import generate_pbip
                sub_dir = os.path.join(output_dir, _safe_filename(name))
                generate_pbip(obj_data, sub_dir, report_name=name,
                              no_calendar=getattr(args, 'no_calendar', False))
                print(f"  [{j}/{total}] ✓ {name}")
                succeeded += 1
            except Exception as e:
                logger.error("Failed to generate %s: %s", name, e)
                print(f"  [{j}/{total}] ✗ {name}: {e}")
                failed += 1

        print(f"\nBatch complete: {succeeded} succeeded, {failed} failed out of {total}")

        if failed > 0 and succeeded > 0:
            return True  # Partial success
        return failed == 0

    except Exception as e:
        logger.error("Batch generation failed: %s", e, exc_info=True)
        print(f"\n✗ Batch generation error: {e}")
        return False


def run_assessment(args):
    """Run pre-migration assessment."""
    from powerbi_import.assessment import assess_project
    from import_to_powerbi import PowerBIImporter

    importer = PowerBIImporter(source_dir='microstrategy_export/')
    converted = importer._load_converted_objects()
    output_dir = args.output_dir or 'artifacts/'

    result = assess_project(converted, output_dir=output_dir)

    summary = result.get("summary", result)
    print()
    print(f"  Overall score:    {result.get('overall_score', 'N/A')}")
    print(f"  Total objects:    {summary['total_objects']}")
    print(f"  Complexity:       {summary['complexity_score']} ({summary['complexity_level']})")
    print(f"  Est. fidelity:    {summary['estimated_fidelity']:.0%}")
    print(f"  Est. effort:      {summary.get('effort_hours', 0):.1f}h")
    print()
    for rec in summary['recommendations']:
        print(f"  • {rec}")


def run_global_assessment_cli(args):
    """Run portfolio-level assessment."""
    from powerbi_import.global_assessment import run_global_assessment

    base_dir = args.global_assess
    output_dir = args.output_dir or 'artifacts/'
    result = run_global_assessment(base_dir, output_dir=output_dir)

    print()
    print(f"  Projects:       {result['total_projects']}")
    print(f"  Total effort:   {result['total_effort_hours']:.1f}h")
    dist = result['score_distribution']
    print(f"  GREEN/YELLOW/RED: {dist['GREEN']}/{dist['YELLOW']}/{dist['RED']}")
    print(f"  Merge clusters: {len(result['merge_clusters'])}")


def run_strategy_cli(args):
    """Show connectivity strategy recommendation."""
    from powerbi_import.strategy_advisor import recommend_strategy
    from import_to_powerbi import PowerBIImporter

    importer = PowerBIImporter(source_dir='microstrategy_export/')
    converted = importer._load_converted_objects()
    fabric = getattr(args, 'fabric', False)

    result = recommend_strategy(converted, fabric_available=fabric)
    print()
    print(f"  Recommended:  {result['recommended']}")
    print(f"  Rationale:    {result['rationale']}")
    if result.get('alternatives'):
        print(f"  Alternatives: {', '.join(result['alternatives'])}")


def run_validation(output_dir):
    """Run post-generation validation."""
    try:
        from powerbi_import.validator import validate_project
        result = validate_project(output_dir)
        if result['valid']:
            print(f"\n  ✓ Validation passed ({result['files_checked']} files checked)")
        else:
            print(f"\n  ⚠ Validation issues ({len(result['errors'])} errors):")
            for err in result['errors'][:5]:
                print(f"    - {err}")
        if result['warnings']:
            print(f"  ⚠ {len(result['warnings'])} warnings")
    except Exception as e:
        logger.debug("Validation skipped: %s", e)


def run_deploy(args):
    """Run deployment to Power BI Service or Fabric."""
    workspace_id = args.deploy
    output_dir = args.output_dir or 'artifacts/'

    print_step(3, 3, "DEPLOYMENT")

    if getattr(args, 'fabric', False):
        try:
            from powerbi_import.deploy.fabric_deployer import deploy_to_fabric
            result = deploy_to_fabric(
                output_dir, workspace_id,
                tenant_id=getattr(args, 'tenant_id', None),
                client_id=getattr(args, 'client_id', None),
                client_secret=getattr(args, 'client_secret', None),
                lakehouse_id=getattr(args, 'lakehouse_id', None),
                direct_lake=getattr(args, 'direct_lake', False),
            )
            print(f"\n✓ Deployed to Fabric: SM={result['semantic_model_id']}")
            return True
        except Exception as e:
            logger.error("Fabric deployment failed: %s", e, exc_info=True)
            print(f"\n✗ Fabric deployment failed: {e}")
            return False
    else:
        try:
            from powerbi_import.deploy.pbi_deployer import deploy_to_service
            result = deploy_to_service(
                output_dir, workspace_id,
                tenant_id=getattr(args, 'tenant_id', None),
                client_id=getattr(args, 'client_id', None),
                client_secret=getattr(args, 'client_secret', None),
                refresh=getattr(args, 'deploy_refresh', False),
            )
            print(f"\n✓ Deployed to Power BI Service: {result['status']}")
            return True
        except Exception as e:
            logger.error("Deployment failed: %s", e, exc_info=True)
            print(f"\n✗ Deployment failed: {e}")
            return False


def _safe_filename(name):
    """Sanitize a name for use as a directory name."""
    import re
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip()


# ── v4.0 feature runners ────────────────────────────────────────


def run_merge(args):
    """Run merge of N project directories into one shared model."""
    from powerbi_import.shared_model import generate_merged_model

    merge_dir = args.merge
    if not os.path.isdir(merge_dir):
        print(f"✗ Merge directory not found: {merge_dir}")
        return

    # Find subdirectories (each is a project)
    project_dirs = [
        os.path.join(merge_dir, d)
        for d in sorted(os.listdir(merge_dir))
        if os.path.isdir(os.path.join(merge_dir, d))
    ]
    if not project_dirs:
        print(f"✗ No project subdirectories found in {merge_dir}")
        return

    print(f"  Merging {len(project_dirs)} projects from {merge_dir}")
    result = generate_merged_model(
        project_dirs, args.output_dir,
        merge_config_path=getattr(args, 'merge_config', None),
    )
    viability = result.get("assessment", {}).get("viability", {})
    print(f"  ✓ Merge complete: score={viability.get('score', 0)} "
          f"rating={viability.get('rating', 'N/A')}")
    print(f"  ✓ Report: {result.get('report_path', '')}")


def run_scorecards(args):
    """Extract scorecards and generate Goals payloads."""
    from microstrategy_export.scorecard_extractor import parse_offline_scorecards
    from powerbi_import.goals_generator import generate_goals

    # Look for scorecards.json in extraction output
    sc_path = os.path.join('microstrategy_export', 'scorecards.json')
    if args.from_export:
        sc_path = os.path.join(args.from_export, 'scorecards.json')

    scorecards = parse_offline_scorecards(sc_path)
    if not scorecards:
        print("  ⚠ No scorecards found — skipping Goals generation")
        return

    goals_dir = os.path.join(args.output_dir, "goals")
    stats = generate_goals(scorecards, goals_dir)
    print(f"  ✓ Generated {stats['goals']} goals from {stats['scorecards']} scorecards")


def run_certification(args):
    """Run post-migration certification."""
    from powerbi_import.certification import certify_migration

    # Load intermediate data
    data = _load_intermediate_data(args)
    result = certify_migration(
        data, args.output_dir,
        threshold=getattr(args, 'certify_threshold', 80),
    )
    verdict = result["verdict"]
    score = result["score"]
    symbol = "✓" if verdict == "CERTIFIED" else "✗"
    print(f"  {symbol} Certification: {verdict} (score={score}%)")


def run_benchmark(args):
    """Run performance benchmark on the generation pipeline."""
    import time
    from powerbi_import.import_to_powerbi import PowerBIImporter

    data = _load_intermediate_data(args)
    print("  Running generation benchmark...")

    start = time.perf_counter()
    importer = PowerBIImporter(source_dir='microstrategy_export/')
    importer.generate(output_dir=args.output_dir)
    elapsed = time.perf_counter() - start

    n_metrics = len(data.get("metrics", [])) + len(data.get("derived_metrics", []))
    n_reports = len(data.get("reports", []))
    n_dossiers = len(data.get("dossiers", []))
    print(f"  ✓ Benchmark: {elapsed:.2f}s for {n_metrics} metrics, "
          f"{n_reports} reports, {n_dossiers} dossiers")


def _load_intermediate_data(args):
    """Load all intermediate JSON files for v4.0 features."""
    import json as _json

    source_dir = 'microstrategy_export/'
    if getattr(args, 'from_export', None):
        source_dir = args.from_export

    data = {}
    for fname in [
        "datasources", "attributes", "facts", "metrics", "derived_metrics",
        "reports", "dossiers", "cubes", "filters", "prompts", "custom_groups",
        "consolidations", "hierarchies", "relationships", "security_filters",
        "freeform_sql", "thresholds", "subtotals",
    ]:
        path = os.path.join(source_dir, f"{fname}.json")
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                data[fname] = _json.load(f)
    return data



def print_summary():
    """Print migration summary."""
    print()
    print("=" * 80)
    print("MIGRATION SUMMARY".center(80))
    print("=" * 80)
    print()
    print(f"  Project:             {_stats.project_name}")
    print()
    print("  EXTRACTION:")
    print(f"    Tables:            {_stats.tables}")
    print(f"    Attributes:        {_stats.attributes}")
    print(f"    Facts:             {_stats.facts}")
    print(f"    Metrics:           {_stats.metrics}")
    print(f"    Derived Metrics:   {_stats.derived_metrics}")
    print(f"    Reports:           {_stats.reports}")
    print(f"    Dossiers:          {_stats.dossiers}")
    print(f"    Cubes:             {_stats.cubes}")
    print(f"    Filters:           {_stats.filters}")
    print(f"    Prompts:           {_stats.prompts}")
    print(f"    Custom Groups:     {_stats.custom_groups}")
    print(f"    Hierarchies:       {_stats.hierarchies}")
    print(f"    Security Filters:  {_stats.security_filters}")
    print()
    print("  GENERATION:")
    print(f"    TMDL Tables:       {_stats.tmdl_tables}")
    print(f"    TMDL Columns:      {_stats.tmdl_columns}")
    print(f"    TMDL Measures:     {_stats.tmdl_measures}")
    print(f"    TMDL Relationships:{_stats.tmdl_relationships}")
    print(f"    Visuals:           {_stats.visuals_generated}")
    print(f"    Pages:             {_stats.pages_generated}")
    print()
    if _stats.pbip_path:
        print(f"  Output: {_stats.pbip_path}")
    if _stats.warnings:
        print(f"\n  ⚠ Warnings: {len(_stats.warnings)}")
        for w in _stats.warnings[:10]:
            print(f"    - {w}")
    if _stats.manual_review:
        print(f"\n  📋 Manual review items: {len(_stats.manual_review)}")
        for m in _stats.manual_review[:10]:
            print(f"    - {m}")
    print()


def build_parser():
    """Build argument parser."""
    parser = argparse.ArgumentParser(
        description='MicroStrategy to Power BI / Fabric Migration Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Migrate a dossier
  python migrate.py --server URL --username admin --password pass --project "Sales" --dossier "Dashboard"

  # Batch migrate all objects in a project
  python migrate.py --server URL --username admin --password pass --project "Sales" --batch

  # Pre-migration assessment
  python migrate.py --server URL --username admin --password pass --project "Sales" --assess

  # Migrate from exported JSON files (offline)
  python migrate.py --from-export ./mstr_exports/ --output-dir /tmp/output
        """,
    )

    # Connection
    conn_group = parser.add_argument_group('MicroStrategy Connection')
    conn_group.add_argument('--server', help='MicroStrategy Library REST API base URL')
    conn_group.add_argument('--username', help='MicroStrategy username')
    conn_group.add_argument('--password', help='MicroStrategy password')
    conn_group.add_argument('--project', help='MicroStrategy project name')
    conn_group.add_argument('--auth-mode', default='standard',
                           choices=['standard', 'ldap', 'saml', 'oauth'],
                           help='Authentication mode (default: standard)')

    # Object selection
    obj_group = parser.add_argument_group('Object Selection')
    obj_group.add_argument('--report', help='Report name to migrate')
    obj_group.add_argument('--report-id', help='Report ID to migrate')
    obj_group.add_argument('--dossier', help='Dossier name to migrate')
    obj_group.add_argument('--dossier-id', help='Dossier ID to migrate')
    obj_group.add_argument('--batch', action='store_true',
                          help='Migrate all reports and dossiers in the project')
    obj_group.add_argument('--folder', help='Limit migration to objects in this folder path')

    # Offline mode
    offline_group = parser.add_argument_group('Offline Mode')
    offline_group.add_argument('--from-export', help='Path to exported JSON files (offline mode)')

    # Output
    out_group = parser.add_argument_group('Output')
    out_group.add_argument('--output-dir', default='artifacts/',
                          help='Output directory for .pbip projects (default: artifacts/)')
    out_group.add_argument('--report-name', help='Override Power BI report name')
    out_group.add_argument('--culture', help='Override culture/locale (e.g., en-US, fr-FR)')
    out_group.add_argument('--no-calendar', action='store_true',
                          help='Do not generate an auto Calendar table (auto-skipped if a date dimension table exists)')

    # Assessment
    assess_group = parser.add_argument_group('Assessment')
    assess_group.add_argument('--assess', action='store_true',
                             help='Run pre-migration assessment without generating output')
    assess_group.add_argument('--global-assess', metavar='DIR',
                             help='Run portfolio-level assessment on a directory of projects')
    assess_group.add_argument('--strategy', action='store_true',
                             help='Show connectivity strategy recommendation (Import/DQ/Composite/DirectLake)')
    assess_group.add_argument('--compare', action='store_true',
                             help='Generate source-vs-output comparison report after migration')

    # Shared model
    shared_group = parser.add_argument_group('Shared Semantic Model')
    shared_group.add_argument('--shared-model', action='store_true',
                             help='Generate a single shared semantic model for the entire project')

    # Incremental migration
    inc_group = parser.add_argument_group('Incremental Migration')
    inc_group.add_argument('--incremental', action='store_true',
                          help='Only migrate objects that changed since last run')
    inc_group.add_argument('--parallel', type=int, default=1, metavar='N',
                          help='Number of parallel workers for extraction/generation (default: 1)')

    # Deployment
    deploy_group = parser.add_argument_group('Deployment')
    deploy_group.add_argument('--deploy', metavar='WORKSPACE_ID',
                             help='Deploy to Power BI Service workspace')
    deploy_group.add_argument('--deploy-refresh', action='store_true',
                             help='Trigger dataset refresh after deployment')
    deploy_group.add_argument('--fabric', action='store_true',
                             help='Deploy to Microsoft Fabric instead of PBI Service')
    deploy_group.add_argument('--tenant-id', help='Azure tenant ID for deployment')
    deploy_group.add_argument('--client-id', help='Azure app client ID for deployment')
    deploy_group.add_argument('--client-secret', help='Azure app client secret for deployment')
    deploy_group.add_argument('--lakehouse-id', help='Fabric lakehouse ID for DirectLake')
    deploy_group.add_argument('--direct-lake', action='store_true',
                             help='Configure DirectLake mode (requires --lakehouse-id)')

    # Logging
    log_group = parser.add_argument_group('Logging')
    log_group.add_argument('--verbose', '-v', action='store_true',
                          help='Enable verbose (DEBUG) logging')
    log_group.add_argument('--quiet', '-q', action='store_true',
                          help='Suppress all output except errors')
    log_group.add_argument('--log-file', help='Write logs to file')

    # Wizard
    parser.add_argument('--wizard', action='store_true',
                       help='Interactive wizard mode (guided step-by-step)')

    # Config file
    parser.add_argument('--config', help='Path to configuration JSON file')

    # Version
    parser.add_argument('--version', action='version', version='%(prog)s 4.0.0')

    # v4.0 features
    v4_group = parser.add_argument_group('v4.0 Features')
    v4_group.add_argument('--merge', metavar='DIR',
                         help='Merge N intermediate-JSON project directories into one shared model')
    v4_group.add_argument('--merge-config', metavar='FILE',
                         help='Path to merge-config.json for conflict resolution rules')
    v4_group.add_argument('--scorecards', action='store_true',
                         help='Extract and convert MicroStrategy scorecards to PBI Goals')
    v4_group.add_argument('--certify', action='store_true',
                         help='Run post-migration certification (PASS/FAIL verdict)')
    v4_group.add_argument('--certify-threshold', type=int, default=80, metavar='PCT',
                         help='Minimum fidelity %% for certification (default: 80)')
    v4_group.add_argument('--benchmark', action='store_true',
                         help='Run performance benchmark on the generation pipeline')

    return parser


def load_config(config_path, args):
    """Load configuration from JSON file and merge with CLI args."""
    if not config_path or not os.path.exists(config_path):
        return args

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # CLI args take precedence over config file
    if not args.server and config.get('server'):
        args.server = config['server']
    if not args.username and config.get('username'):
        args.username = config['username']
    if not args.password and config.get('password'):
        args.password = config['password']
    if not args.project and config.get('project'):
        args.project = config['project']

    return args


def main():
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args()

    # Setup logging
    setup_logging(
        verbose=args.verbose,
        log_file=args.log_file,
        quiet=args.quiet,
    )

    # Interactive wizard mode
    if args.wizard:
        from wizard import run_wizard
        import types
        wizard_answers = run_wizard()
        for k, v in wizard_answers.items():
            setattr(args, k, v)
        # Wizard sets config to None — skip config loading
        args.config = None

    # Load config file if specified
    if args.config:
        args = load_config(args.config, args)

    # Validate required args
    if not args.from_export:
        if not args.server:
            parser.error('--server is required (or use --from-export for offline mode)')
        if not args.project:
            parser.error('--project is required')

    print_header("MicroStrategy → Power BI / Fabric Migration")
    start_time = datetime.now()

    # Global assessment mode (no extraction needed)
    if getattr(args, 'global_assess', None):
        try:
            run_global_assessment_cli(args)
        except Exception as e:
            logger.error("Global assessment failed: %s", e, exc_info=True)
            sys.exit(ExitCode.ASSESSMENT_FAILED)
        sys.exit(ExitCode.SUCCESS)

    # Merge mode (no extraction needed)
    if getattr(args, 'merge', None):
        try:
            run_merge(args)
        except Exception as e:
            logger.error("Merge failed: %s", e, exc_info=True)
            sys.exit(ExitCode.GENERAL_ERROR)
        sys.exit(ExitCode.SUCCESS)

    # Step 1: Extraction
    extraction_ok = run_extraction(args)
    if not extraction_ok:
        print_summary()
        sys.exit(ExitCode.EXTRACTION_FAILED)

    # Assessment-only mode: stop here
    if args.assess:
        try:
            run_assessment(args)
            if getattr(args, 'strategy', False):
                run_strategy_cli(args)
        except Exception as e:
            logger.error("Assessment failed: %s", e, exc_info=True)
            sys.exit(ExitCode.ASSESSMENT_FAILED)
        print_summary()
        print("\n✓ Assessment complete (no output generated)")
        sys.exit(ExitCode.SUCCESS)

    # Strategy-only mode
    if getattr(args, 'strategy', False) and not args.assess:
        try:
            run_strategy_cli(args)
        except Exception as e:
            logger.error("Strategy analysis failed: %s", e, exc_info=True)
            sys.exit(ExitCode.ASSESSMENT_FAILED)
        sys.exit(ExitCode.SUCCESS)

    # Step 2: Generation (batch or single)
    if getattr(args, 'batch', False):
        generation_ok = run_batch_generation(args)
    else:
        generation_ok = run_generation(
            output_dir=args.output_dir,
            report_name=args.report_name,
            culture=args.culture,
            shared_model=getattr(args, 'shared_model', False),
            no_calendar=getattr(args, 'no_calendar', False),
        )
    if not generation_ok:
        print_summary()
        sys.exit(ExitCode.GENERATION_FAILED)

    # Step 3: Validate (automatic)
    run_validation(args.output_dir)

    # Step 3b: Comparison report (optional)
    if getattr(args, 'compare', False):
        try:
            from powerbi_import.comparison_report import generate_comparison_report
            from import_to_powerbi import PowerBIImporter
            importer = PowerBIImporter(source_dir='microstrategy_export/')
            converted = importer._load_converted_objects()
            generate_comparison_report(converted, {}, args.output_dir,
                                       report_name=args.report_name or 'MicroStrategy Report')
            print("  ✓ Comparison report generated")
        except Exception as e:
            logger.warning("Comparison report failed: %s", e)
    # Step 3c: Scorecards → Goals (optional, v4.0)
    if getattr(args, 'scorecards', False):
        try:
            run_scorecards(args)
        except Exception as e:
            logger.warning("Scorecard conversion failed: %s", e)

    # Step 3d: Certification (optional, v4.0)
    if getattr(args, 'certify', False):
        try:
            run_certification(args)
        except Exception as e:
            logger.warning("Certification failed: %s", e)

    # Step 3e: Benchmark (optional, v4.0)
    if getattr(args, 'benchmark', False):
        try:
            run_benchmark(args)
        except Exception as e:
            logger.warning("Benchmark failed: %s", e)
    # Step 4: Deploy (optional)
    if args.deploy:
        deploy_ok = run_deploy(args)
        if not deploy_ok:
            print_summary()
            sys.exit(ExitCode.GENERAL_ERROR)

    elapsed = datetime.now() - start_time
    print_summary()
    print(f"  Total time: {elapsed.total_seconds():.1f}s")

    sys.exit(ExitCode.SUCCESS)


if __name__ == '__main__':
    main()
