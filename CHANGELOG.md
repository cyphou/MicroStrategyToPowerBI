# Changelog

All notable changes to this project will be documented in this file.

## [3.0.0] — 2026-03-20

### 🚀 v3.0 — Enterprise Assessment, Strategy, Telemetry & Extensibility

Major release adding 11 new modules for enterprise-grade migration assessment, strategy advisory, comparison reporting, and an extensible plugin system.

### Added

**Sprint F: Regression Test Suite**
- `tests/test_regression.py` — 10 regression test classes covering all PBI Desktop bugs fixed in v2.x (format strings, Calendar table, RLS syntax, relationship TMDL, page layout, etc.)

**Sprint G: TMDL Enhancements**
- Format string generation for numeric/currency/percentage measures
- Geographic data category annotations (City, State, Country, PostalCode, Latitude, Longitude)
- Column-level annotations for lineage tracking

**Sprint H: 14-Category Assessment Engine**
- Complete rewrite of `assessment.py` — `CheckItem`/`CategoryResult`/`AssessmentReport` data model
- 14 assessment categories: expressions, visuals, connectors, security, prompts, hierarchies, relationships, data types, formatting, calculated tables, partitions, RLS, aggregations, advanced features
- GREEN/YELLOW/RED scoring with effort estimation in hours
- Connector tier classification
- `server_assessment.py` — Server-wide portfolio assessment with `WorkbookReadiness` and `MigrationWave` planning
- `global_assessment.py` — Multi-project global assessment with pairwise-merge clustering

**Sprint I: Comparison & Telemetry**
- `comparison_report.py` — Side-by-side MSTR↔PBI HTML comparison report
- `visual_diff.py` — Visual type + field coverage analysis (identifies missing columns, measure mismatches)
- `telemetry.py` — Migration run data collection (timings, object counts, fidelity)
- `telemetry_dashboard.py` — Historical aggregation HTML dashboard across runs

**Sprint J: Thin Report Generator**
- `thin_report_generator.py` — Generates lightweight reports referencing a shared semantic model
- Supports remote model ID for Fabric deployment scenarios

**Sprint K: Progress & Plugins**
- `progress.py` — tqdm-based progress bar wrapper with fallback for non-TTY environments
- `plugins.py` — Extension point hook system (pre/post extraction, pre/post generation, custom transformations)

**CLI Enhancements**
- `--global-assess DIR` — Portfolio-wide assessment across multiple project directories
- `--strategy` — Import/DirectQuery/Composite/DirectLake strategy recommendation
- `--compare` — Side-by-side comparison report generation after migration
- `--no-calendar` — Suppress Calendar table generation (when date dimension already exists)
- `strategy_advisor.py` — Automatic mode recommendation with confidence scoring

### Fixed
- `server_assessment.py`: Handle both plain dicts and `(name, report)` tuples in `run_server_assessment()`
- `server_assessment.py`: Return plain dict via `_server_assessment_to_dict()` for JSON serialization
- `server_assessment.py`: `WorkbookReadiness` handles v3 nested report structure (`summary` key)
- `thin_report_generator.py`: Removed unsupported `report_name` kwarg from `generate_all_visuals()` call

### Tests
- 43 new tests in `test_v3_features.py` (assessment categories, server assessment, global assessment, strategy advisor, comparison report, visual diff, telemetry, thin reports, plugins, progress)
- 10 new tests in `test_regression.py`
- **Total: 623 tests passing**

---

## [2.0.0] — 2026-03-19

### 🚀 v2.0 — CI/CD, Wizard, DAX Depth, Performance, Incremental, Dashboard

Major feature release: 7 new phases (F–L) adding production-grade tooling and enterprise capabilities.

### Added

**Phase F: CI/CD + Packaging**
- GitHub Actions CI workflow (`.github/workflows/ci.yml`) — matrix testing on Python 3.9–3.13, Ubuntu+Windows, Ruff linting
- GitHub Actions Release workflow (`.github/workflows/release.yml`) — automated PyPI publish + GitHub Release on tag push
- `ruff.toml` — linter/formatter configuration
- `--version` CLI flag
- Updated `pyproject.toml` with correct GitHub URLs, v2.0.0, `perf` optional dependencies

**Phase G: Interactive Wizard**
- `wizard.py` — guided step-by-step migration wizard (`--wizard` flag)
- 7-step flow: mode → connection → object selection → output → deployment → logging → save config
- Config file generation for reuse (`migration_config.json`)

**Phase H: DAX Depth**
- 30+ new ApplySimple SQL→DAX patterns (ISNULL, IFNULL, NVL2, DECODE, NULLIF, GREATEST, LEAST, CONCAT, SUBSTR, REPLACE, INITCAP, LPAD, INSTR, TO_DATE, TO_CHAR, DATEADD, DATEDIFF, ADD_MONTHS, LAST_DAY, TRUNC with date parts, CAST variants, math patterns, CASE WHEN IS NULL)
- 20+ new function map entries (percentile, correlation, forecast, initcap, datediff, dateadd, quarterstartdate, quarterenddate, number, text, etc.)
- `_handle_additional_functions()` — InitCap→PROPER, DaysInMonth, WeekStartDate, WeekEndDate, LPad, RPad, Reverse

**Phase I: Performance + Scale**
- `microstrategy_export/parallel.py` — thread-pool parallel extraction and generation
- `parallel_extract()` / `parallel_generate()` with configurable worker count
- `stream_json_items()` — lazy JSON loading for large files (>50 MB)
- Optional tqdm progress bars (auto-detected)
- `--parallel N` CLI flag

**Phase J: Incremental Migration**
- `microstrategy_export/incremental.py` — state tracking with SHA-256 hashing
- `MigrationState` class: is_changed, mark_migrated, mark_removed, get_changed_objects, get_stale_objects
- Persistent `migration_state.json` for delta-only re-runs
- `--incremental` CLI flag

**Phase K: Live Integration Testing**
- `tests/cassette_harness.py` — HTTP interaction recorder/player
- `CassetteRecorder` — record, save, load, play API responses
- `MockMstrClient` — drop-in replacement for MstrRestClient using cassettes

**Phase L: Web Dashboard**
- `powerbi_import/dashboard.py` — self-contained interactive HTML dashboard
- Fidelity score gauge, generation stats, type breakdown
- Fidelity heatmap by object type
- Searchable/filterable object table
- Migration timeline (incremental mode)

### Tests
- 70 new tests in `test_v2_features.py` (wizard, DAX depth, parallel, incremental, cassette, dashboard, CLI)
- **Total: 570 tests passing**

---

## [1.0.0] — 2026-03-19

### 🎉 Initial Release — Full Pipeline

Complete MicroStrategy to Power BI migration pipeline: Extract → Generate → Deploy.

### Added

**Extraction Layer** (12 modules, ~2,070 LOC)
- `rest_api_client.py` — MicroStrategy REST API v2 client (standard/LDAP/SAML/OAuth auth, pagination, retry)
- `schema_extractor.py` — Tables, attributes (forms, lookup tables, hierarchies), facts, relationships, custom groups, freeform SQL
- `metric_extractor.py` — Simple, compound, derived, and OLAP metrics with thresholds
- `expression_converter.py` — 60+ MSTR→DAX function mappings, level metrics, derived metrics, ApplySimple patterns
- `report_extractor.py` — Grid/graph report definitions with filters, sorts, subtotals
- `dossier_extractor.py` — Dossier chapters, pages, 35+ visualization types, panel stacks, selectors
- `cube_extractor.py` — Intelligent cube definitions
- `prompt_extractor.py` — 6 prompt types → PBI slicer/parameter mappings
- `security_extractor.py` — Security filters → RLS role definitions
- `connection_mapper.py` — 15+ warehouse types → Power Query M expressions (SQL Server, Oracle, PostgreSQL, MySQL, Snowflake, Databricks, BigQuery, SAP HANA, Teradata, etc.)
- `extract_mstr_data.py` — Online + offline extraction orchestrator, 18 JSON output files
- `migrate.py` — CLI entry point with full argument handling

**Generation Layer** (6 modules, ~1,400 LOC)
- `tmdl_generator.py` — TMDL semantic model: tables, columns (attribute forms + facts), DAX measures, relationships, hierarchies, RLS roles, Calendar auto-table
- `visual_generator.py` — PBIR v4.0 visual JSON: 30+ visualization type mappings, data bindings for 18 visual types, position scaling, formatting, conditional formatting
- `m_query_generator.py` — Power Query M partition expressions via connection mapper
- `pbip_generator.py` — Complete .pbip project assembly: SemanticModel + Report folders, manifests, model.tmdl header
- `migration_report.py` — Per-object fidelity report in JSON + HTML (fidelity score, 4 classification levels)
- `import_to_powerbi.py` — Import orchestrator wiring all generators

**Test Suite** (385 tests)
- 97 visual generator tests (type mappings, data bindings, page layout, PBIR manifest)
- 57 expression converter tests (60+ functions, level metrics, derived metrics)
- 48 TMDL generator tests (tables, columns, measures, relationships, hierarchies, RLS, calendar)
- 45 PBIP assembly tests (scaffold, SemanticModel, Report, migration report, E2E pipeline)
- 28 REST API client tests (auth, API URLs, object constants, error handling)
- 19 M query generator tests (10+ DB types, freeform SQL)
- 15 connection mapper tests
- 15 metric extractor tests (simple/compound/derived, thresholds, format strings)
- 20+ schema extractor tests (attributes, facts, hierarchies, custom groups)
- 15+ report, dossier, and advanced extraction tests

**Documentation**
- README.md with badges, feature table, DAX highlights, visual mapping, architecture tree
- 8 documentation files: Migration Plan, Architecture, Mapping Reference, DAX Reference, Test Strategy, Known Limitations, Migration Checklist, Development Plan
- CONTRIBUTING.md with development workflow
- 6 multi-agent Copilot configurations (.github/agents/)

**Test Fixtures** (34 files)
- MicroStrategy API response fixtures (projects, tables, attributes, facts, metrics, reports, dossiers, cubes, prompts, security filters, hierarchies, search results)
- Intermediate JSON fixtures (all 18 file types)
- Expected output fixtures for validation
