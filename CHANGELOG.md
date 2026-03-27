# Changelog

All notable changes to this project will be documented in this file.

## [19.0.0] — 2026-03-27

### 🚀 v12.0 — Cross-Platform Federation (Sprint BB)

Universal BI schema for federated migration from MicroStrategy + Tableau (+ future Cognos/SSRS) into unified Power BI output.

### Added

**Sprint BB: Cross-Platform Federation**
- `universal_bi/schema.py` — Platform-agnostic intermediate schema (12 sections: datasources, dimensions, measures, relationships, hierarchies, security_rules, pages, parameters, filters, custom_groups, custom_sql). `empty_schema()`, `validate()`, `merge_schemas()`, `to_mstr_format()` APIs
- `universal_bi/adapters/mstr_adapter.py` — MicroStrategy → Universal BI adapter: converts all 18 MSTR intermediate JSON files into universal schema with `source_platform` provenance tags
- `universal_bi/adapters/tableau_adapter.py` — Tableau → Universal BI adapter: converts Tableau intermediate JSONs (datasources, worksheets, dashboards, calculations, parameters, hierarchies, user_filters, groups, sets, custom_sql) with mark-type → viz-type mapping and shelf → role mapping
- `universal_bi/cross_lineage.py` — Cross-platform lineage and deduplication: `detect_shared_sources()`, `detect_equivalent_dimensions()`, `detect_equivalent_measures()` with name/table/column similarity scoring, `deduplicate()` with configurable thresholds, `build_lineage()` DAG builder, `lineage_summary()` aggregation

**CLI Enhancements**
- `--from-tableau DIR` — Path to Tableau intermediate JSON directory for federation
- `--federate` — Enable cross-platform merge with deduplication and lineage
- Version bumped to 19.0.0

**Pipeline Wiring**
- Federation step (Step 1b) runs after extraction, before generation
- Converts MSTR data → universal schema, optionally merges Tableau data
- Deduplication removes duplicate dimensions/measures across platforms
- Writes unified intermediate files back for standard generation pipeline

### Tests
- 50 new tests in `test_federation.py`:
  - Schema: 8 tests (empty, validate, merge with dedup, to_mstr_format roundtrip)
  - MSTR adapter: 11 tests (all section conversions, empty input)
  - Tableau adapter: 12 tests (datasources, dimensions, measures, relationships, pages, parameters, hierarchies, security, custom groups/sql)
  - Cross-lineage: 11 tests (shared sources, equivalent dimensions/measures, dedup, lineage graph, summary)
  - Integration: 2 tests (end-to-end federation pipeline, JSON serialization roundtrip)
  - Full federation: end-to-end MSTR + Tableau → merge → dedup → validate → generate
- **2,802 total tests** (from 2,752 pre-v12.0)

## [18.0.0] — 2026-03-27

### 🚀 v18.0 — Content Library & Templates (Sprint III)

Industry-specific semantic model templates, curated DAX recipe library, versioned pattern marketplace, and a unified HTML report framework.

### Added

**Sprint III: Content Library**
- `powerbi_import/model_templates.py` — 3 industry star-schema skeletons (Healthcare, Finance, Retail) with fact + dimension tables, relationships, measures, hierarchies. `list_templates()`, `get_template()`, `apply_template()` API — enriches existing tables with template columns, adds missing tables
- `powerbi_import/dax_recipes.py` — 21 curated DAX measure recipes across 3 industries (Healthcare 6, Finance 8, Retail 7). `apply_recipes()` with injection + regex replacement modes, `recipes_to_marketplace_format()` bridge
- `powerbi_import/marketplace.py` — Versioned pattern registry: `PatternMetadata`, `Pattern`, `PatternRegistry` classes. 5 categories (dax_recipe, visual_mapping, m_template, naming_convention, model_template). Semver versioning, `load()` from directory, `search()` by tags/category/name, `apply_dax_recipes()`, `apply_visual_overrides()`, `export()` API
- `powerbi_import/html_template.py` — Unified CSS/JS framework: 17 design-token colour constants, `get_report_css()` (dark mode, responsive, print), `get_report_js()` (toggleSection, switchTab, filterTable, sortTable), 16 HTML builder functions (stat_card, stat_grid, section, card, badge, fidelity_bar, donut_chart, bar_chart, data_table, tab_bar, tab_content, flow_diagram, cmd_box)
- `examples/marketplace/` — 3 sample marketplace patterns: `revenue_ytd.json`, `yoy_growth_percent.json`, `custom_map_override.json`

**CLI Enhancements**
- `--template healthcare|finance|retail` — Apply industry semantic model template
- `--recipes INDUSTRY` — Inject DAX recipes for specified industry
- `--marketplace PATH` — Load pattern marketplace from directory
- Version bumped to 18.0.0

**Pipeline Wiring**
- Content library step runs after DAX optimization (Step 3f¾)
- Template application enriches existing tables, adds missing schema elements
- DAX recipe injection adds curated measures to semantic model
- Marketplace overrides applied to visual type map and measure definitions

### Tests
- 82 new tests in `test_content_library.py`:
  - Model templates: 12 tests (list, get, deep copy, apply with empty/existing/rels/hierarchies)
  - DAX recipes: 15 tests (counts, structure, injection, skip, overwrite, replacement, marketplace bridge)
  - Marketplace: 21 tests (register, versioning, search, load dir, apply DAX/visual, export, to_dict)
  - HTML template: 34 tests (esc, CSS/JS, open/close, stat_card, grid, section, card, badge, fidelity_bar, donut, bar, table, tabs, flow, cmd_box, constants)
- **2,752 total tests** (from 2,670 pre-v18.0)

## [17.0.0] — 2026-03-27

### 🚀 v17.0 — Enterprise Operations & Monitoring (Sprint II)

Pluggable monitoring backends, SLA compliance tracking, alert rule generation, refresh schedule migration, and self-healing recovery reports.

### Added

**Sprint II: Enterprise Operations**
- `powerbi_import/monitoring.py` — Strategy-pattern monitoring with 4 pluggable backends: JSON file, Azure Monitor (OpenTelemetry), Prometheus text exposition, and no-op. `MigrationMonitor` facade with `record_metric()`, `record_event()`, `record_migration()`, `flush()` API
- `powerbi_import/sla_tracker.py` — Per-report SLA compliance tracking: `SLATracker` with `start()`/`record_result()` timing, 3-dimension compliance (duration, fidelity, validation). `SLAResult` and `SLAReport` dataclasses with `compliance_rate` property. Configurable via JSON config file
- `powerbi_import/alerts_generator.py` — Extract MSTR thresholds from 3 sources (thresholds.json, metrics with embedded thresholds, numeric prompts) and convert to PBI data-driven alert rule definitions. Operator normalisation, `extract_alerts()`, `generate_alert_rules()`, `save_alert_rules()` API
- `powerbi_import/refresh_generator.py` — Convert MSTR cache/subscription schedules to PBI dataset refresh configuration. Handles hourly→daily conversion with time slots, PBI Pro 8-refresh cap, weekly/monthly day mapping, cache policy hints. `generate_refresh_config()`, `generate_subscription_config()`, `generate_refresh_json()` API
- `powerbi_import/recovery_report.py` — Self-healing recovery tracker: `RecoveryReport` class recording automatic repairs during generation (sanitised names, unsupported visuals, broken relationships). Category/severity classification, `save()`, `merge_into()`, `print_summary()` API
- `docs/ENTERPRISE_GUIDE.md` — 8-phase enterprise migration guide covering Discovery, Infrastructure, Pilot, Bulk Migration, Validation, Deployment, Monitoring, and Ongoing Maintenance

**CLI Enhancements**
- `--monitor json|azure|prometheus|none` — Enable migration monitoring with specified backend
- `--sla-config FILE` — Path to SLA configuration JSON file
- `--alerts` — Generate PBI data-driven alert rules from MSTR thresholds
- `--migrate-schedules` — Convert MSTR cache/subscription schedules to PBI refresh config
- Version bumped to 17.0.0

**Pipeline Wiring**
- Monitoring + SLA tracker initialised before extraction, flushed after deployment
- Alert generation auto-runs after validation (Step 3i)
- Refresh schedule migration runs as Step 3j
- Recovery report saved automatically when repairs exist (Step 3k)
- SLA report saved as `sla_report.json` with compliance rate display

### Tests
- 65 new tests in `test_operations.py`:
  - Monitoring: 13 tests (4 backends + facade + flush + append + fallback)
  - SLA tracker: 14 tests (SLAResult compliance combos, SLAReport aggregation, SLATracker lifecycle)
  - Alerts: 12 tests (3-source extraction, operator normalisation, rule generation, persistence)
  - Refresh: 14 tests (daily/weekly/hourly/cache, day normalisation, time slots, Pro limit cap)
  - Recovery: 12 tests (record, summary, filter, save, merge_into, print_summary, follow_up)
- **Total: 2,670 tests passing**

---

## [16.0.0] — 2026-03-26

### 🚀 v16.0 — Fabric Deep Integration Phase 2 (Sprints GG–HH)

Full Fabric-native generation — dedicated DirectLake generator, Dataflow Gen2, proper naming/sanitization, centralized auth, REST API client, atomic bundle deployment.

### Added

**Sprint GG: Fabric Generation Deep Dive**
- `powerbi_import/fabric_constants.py` — Centralized Spark type map (50+ MSTR→Delta types), TMDL type map, PySpark aggregation map, JDBC driver/URL maps, column sanitization, reserved word detection. Single source of truth for all Fabric generators
- `powerbi_import/fabric_naming.py` — Name sanitization for Lakehouse tables (64-char limit, no spaces, leading-digit fix), Dataflow/Pipeline/Semantic Model names. Collision detection with automatic numeric suffix resolution
- `powerbi_import/calc_column_utils.py` — Classify MSTR expressions as `lakehouse`-eligible (PySpark pre-compute) or `dax_only` (must remain DAX). Convert eligible expressions to PySpark `withColumn()` calls. 30+ PySpark function mappings
- `powerbi_import/dataflow_generator.py` — Generate Fabric Dataflow Gen2 definitions: Power Query M mashup → Lakehouse Delta table destination. 6 connector templates (SQL Server, PostgreSQL, Oracle, MySQL, Snowflake, BigQuery) + freeform SQL support
- `powerbi_import/fabric_semantic_model_generator.py` — Dedicated DirectLake semantic model generator: expression-less tables with entityName partition bindings, DirectLake-specific model properties, relationship TMDL, shared expression for Lakehouse binding

**Sprint HH: Deployment Infrastructure**
- `powerbi_import/deploy/auth.py` — Centralized Azure AD authentication: Service Principal, Managed Identity, interactive browser flow. Token caching + automatic refresh
- `powerbi_import/deploy/client.py` — Generic Fabric REST API client: GET/POST/PATCH/DELETE with automatic retry (429/5xx), exponential backoff, pagination, workspace/item CRUD, long-running operation polling
- `powerbi_import/deploy/bundle_deployer.py` — Atomic bundle deployment: shared semantic model + N thin reports as a single unit. Rollback on partial failure. Post-deployment endorsement (Promoted/Certified). Environment-based config loading

**CLI Enhancements**
- `--deploy-env dev|staging|prod` — Select deployment environment configuration
- Version bumped to 16.0.0

### Tests
- ~104 new tests across 2 test files:
  - `test_fabric_deep.py` (~55 tests): Spark type maps, TMDL types, column sanitization, table/item naming, collision resolution, expression classification, PySpark conversion, Dataflow Gen2 generation, DirectLake model generation
  - `test_deploy_infra.py` (~49 tests): auth flows (credential/SP/MI/cache), REST client (retry/pagination/CRUD), bundle deployment (success/dry-run/rollback/endorsement), config loading, CLI flag validation
- **Total: 2,458 tests passing**

---

## [15.0.0] — 2026-03-27

### 🚀 v15.0 — DAX Optimization & Quality Gates (Sprints EE–FF)

AST-based DAX optimization, cross-platform equivalence testing, snapshot regression suite, and security hardening.

### Added

**Sprint EE: DAX Optimizer**
- `powerbi_import/dax_optimizer.py` — AST-based DAX optimization with 5 rewrite rules:
  - `ISBLANK→COALESCE`: `IF(ISBLANK(x), default, x)` → `COALESCE(x, default)`
  - `Chained IF→SWITCH`: ≥3 IF branches → `SWITCH(TRUE(), ...)`
  - `CALCULATE simplification`: nested `CALCULATE(CALCULATE(...))` → single `CALCULATE`
  - `Redundant CALCULATE removal`: `CALCULATE(expr)` with no filters → `expr`
  - Time Intelligence injection: auto-generate YTD (`TOTALYTD`), PY (`SAMEPERIODLASTYEAR`), YoY% variants for date-based measures
  - Optimization report: patterns applied, before/after stats

**Sprint FF: Equivalence Testing, Regression Suite & Security**
- `powerbi_import/equivalence_tester.py` — Cross-platform value comparison with configurable numeric tolerance + SSIM-based screenshot comparison (lightweight, no external deps)
- `powerbi_import/regression_suite.py` — Golden snapshot generation/comparison for TMDL, JSON, M, PQ files. SHA-256 hash-based drift detection with manifest tracking
- `powerbi_import/security_validator.py` — Path traversal detection, ZIP slip prevention, XXE pattern detection, dangerous extension blocking (.exe/.bat/.ps1/etc), sensitive file warnings (.env/.key/.pem)

**CLI Enhancements**
- `--optimize-dax` — Enable DAX optimization pass (default off to preserve 1:1 fidelity)
- `--auto-time-intelligence` — Inject Time Intelligence variants for date-based measures
- `--snapshot-update` — Re-baseline regression snapshots
- Version bumped to 15.0.0

### Tests
- ~89 new tests across 2 test files:
  - `test_dax_optimizer.py` (~40 tests): ISBLANK→COALESCE, IF→SWITCH, CALCULATE simplification, nested CALCULATE flattening, redundant CALCULATE removal, Time Intelligence injection, optimize_measures integration, format_report
  - `test_quality_gates.py` (~49 tests): value comparison (positional + keyed, tolerance, NaN, None), screenshot SSIM, snapshot generation/comparison/drift/update, path validation, XXE detection, ZIP slip, project output scanning
- **Total: 2,354 tests passing**

---

## [11.0.0] — 2026-03-26

### 🚀 v11.0 — Migration Ops (Sprint AA)

Continuous migration pipeline with change detection, drift monitoring, three-way reconciliation, and scheduled re-migration support.

### Added

**Sprint AA: Change Detection & Reconciliation**
- `microstrategy_export/change_detector.py` — Compare current vs previous intermediate JSON files to detect added, modified, and deleted MicroStrategy objects. Also supports API-based detection via `modificationTime` polling. Produces a structured change manifest
- `powerbi_import/drift_report.py` — Compare current live PBI output against previous migration baseline to detect manual user edits. Generates JSON + HTML drift report with conflict highlighting
- `powerbi_import/reconciler.py` — Three-way merge engine: MSTR source (new) × PBI target (live) × PBI target (baseline). Auto-applies safe changes, preserves user edits, flags conflicts. Supports dry-run mode
- `scripts/scheduled_migration.py` — Cron-compatible pipeline: change detection → drift report → reconciliation → reporting. Configurable via `migration_schedule.json`

**CLI Enhancements**
- `--watch` — Detect changes between current and previous extraction (produces change manifest + drift report)
- `--reconcile` — Three-way reconcile preserving manual PBI edits while applying upstream MSTR changes
- `--previous-dir DIR` — Path to previous extraction output (for change detection)
- `--baseline-dir DIR` — Path to previous migration output baseline (for reconciliation)
- Version bumped to 11.0.0

### Tests
- 52 new tests in `test_migops.py` covering:
  - Change detector (17 tests): no changes, added/modified/deleted objects, multiple types, missing dirs, malformed JSON, hash determinism, index fallback, manifest round-trip, timestamps, complex scenarios
  - API-based detection (3 tests): mock client, no changes, error handling
  - Drift report (13 tests): no drift, modified/added/deleted files, untracked extensions, nested files, HTML output, empty/nonexistent dirs, file hash helpers
  - Reconciler (14 tests): source changed/unchanged, user edited, both changed, identical changes, new/removed files, user-only files, dry run, file copy verification, complex multi-file scenario
  - Scheduled migration (4 tests): config loading, overrides, missing config, end-to-end pipeline
  - Integration (1 test): full change → drift → reconcile pipeline
- **Total: 2,260 tests passing**

---

## [9.0.0] — 2026-03-26

### 🚀 v9.0 — Real-Time & Streaming (Sprint Y)

Detects real-time MicroStrategy dashboards and generates Power BI push dataset, Fabric Eventstream, and refresh schedule definitions.

### Added

**Sprint Y: Real-Time Source Detection & Streaming Generation**
- `microstrategy_export/realtime_extractor.py` — Analyse dossiers, reports, and cubes for refresh policies, cache settings, subscriptions, and auto-refresh intervals. Classify each object as `batch`, `near_realtime`, or `streaming`
- `powerbi_import/streaming_generator.py` — Generate Power BI push dataset definitions (REST API schema), Fabric Eventstream definitions (KQL database → semantic model), and refresh schedules for near-real-time objects
- `powerbi_import/deploy/refresh_config.py` — Generate Power BI dataset refresh configuration payloads (REST API format) with proper time slot generation for frequent, daily, or push-based refresh strategies

**CLI Enhancements**
- `--realtime` — Detect real-time sources and generate push dataset / Eventstream / refresh schedule definitions
- Version bumped to 9.0.0

### Tests
- 33 new tests in `test_streaming.py` covering:
  - Real-time source detection (16 tests): batch/near-realtime/streaming classification, boundary cases, schedule info parsing, subscription detection, event-based flags, mixed objects
  - Streaming generator (8 tests): push dataset generation, column type mapping, Eventstream definitions, refresh schedules, summary output
  - Refresh config (8 tests): batch/near-realtime/streaming configs, time slot generation, default intervals
  - Integration (1 test): full pipeline end-to-end
- **Total: 2,208 tests passing**

---

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
