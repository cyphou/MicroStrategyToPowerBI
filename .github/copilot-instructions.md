# MicroStrategy to Power BI / Fabric Migration Tool

## Project Overview

This tool automates migration of MicroStrategy reports, dossiers, cubes, and semantic objects to Power BI / Microsoft Fabric `.pbip` projects (PBIR v4.0 + TMDL semantic model).

**Architecture**: 2-step pipeline — Extract (MicroStrategy REST API v2) → 18 intermediate JSON files → Generate (.pbip with PBIR + TMDL).

## Code Style

- Python 3.9+, type hints on public APIs
- Module-level `logger = logging.getLogger(__name__)` in every module
- Private helpers prefixed with `_`
- Constants as module-level `_UPPER_SNAKE` variables
- JSON intermediate files written via `_write_json(filename, data)` pattern

## Architecture

```
microstrategy_export/   # Step 1: Extraction layer (REST API → JSON)
  rest_api_client.py    #   HTTP client (auth, pagination, retry)
  extract_mstr_data.py  #   Orchestrator
  schema_extractor.py   #   Tables, attributes, facts, hierarchies
  metric_extractor.py   #   Simple/compound/derived metrics
  expression_converter.py # MSTR expressions → DAX
  report_extractor.py   #   Report grid/graph definitions
  dossier_extractor.py  #   Dossier chapters/pages/visualizations
  cube_extractor.py     #   Intelligent Cube definitions
  prompt_extractor.py   #   Prompt types → PBI slicer/parameter
  security_extractor.py #   Security filters → RLS
  connection_mapper.py  #   15+ DB types → Power Query M

powerbi_import/         # Step 2: Generation layer (JSON → .pbip)
  import_to_powerbi.py  #   Importer orchestrator
  pbip_generator.py     #   .pbip project assembly
  tmdl_generator.py     #   TMDL semantic model (Import + DirectLake)
  visual_generator.py   #   PBIR v4.0 visual JSON
  m_query_generator.py  #   Power Query M expressions
  lakehouse_generator.py #  Fabric Lakehouse DDL + OneLake shortcuts
  notebook_generator.py #   PySpark ETL notebooks (JDBC, Snowflake, BigQuery)
  pipeline_generator.py #   Data Factory pipeline JSON
  validator.py          #   TMDL/PBIR/DAX validation
  assessment.py         #   14-category pre-migration assessment
  migration_report.py   #   Fidelity report (JSON + HTML)
  dashboard.py          #   Interactive HTML fidelity dashboard
  shared_model.py       #   Shared semantic model generator
  thin_report_generator.py  # Thin reports (shared model ref)
  server_assessment.py  #   Server-wide portfolio assessment
  global_assessment.py  #   Multi-project global assessment
  comparison_report.py  #   Source-vs-output comparison report
  visual_diff.py        #   Visual field coverage analysis
  strategy_advisor.py   #   Import/DQ/Composite/DirectLake advisor
  telemetry.py          #   Migration run data collection
  telemetry_dashboard.py #  Historical run dashboard
  progress.py           #   Progress bar wrapper
  plugins.py            #   Plugin extension system
  ai_converter.py     #   Azure OpenAI LLM fallback for DAX conversion
  semantic_matcher.py  #   Fuzzy column matching + correction learning
  lineage.py          #   Data lineage DAG + impact analysis
  lineage_report.py   #   Interactive HTML lineage visualization
  purview_integration.py # Microsoft Purview asset registration
  governance_report.py #  Pre-migration governance checklist HTML
  monitoring.py       #   Pluggable monitoring (JSON/Azure/Prometheus)
  sla_tracker.py      #   Per-report SLA compliance tracking
  alerts_generator.py #   MSTR thresholds → PBI data-driven alerts
  refresh_generator.py #  Cache/subscription → PBI refresh config
  recovery_report.py  #   Self-healing recovery tracking
  model_templates.py  #   Industry star-schema templates (Healthcare/Finance/Retail)
  dax_recipes.py      #   Curated DAX recipe library (21 measures)
  marketplace.py      #   Versioned pattern registry
  html_template.py    #   Shared CSS/JS report framework
  deploy/
    fabric_deployer.py  #   Fabric REST API deployment (SM, report, notebooks, pipelines)
    fabric_git.py       #   Push .pbip to Fabric workspace Git repos
    fabric_env.py       #   Fabric environment config + capacity estimation
    pbi_deployer.py     #   Power BI Service deployment
    gateway_config.py   #   On-premises gateway configuration

universal_bi/           # Cross-platform federation layer
  schema.py             #   Universal BI schema (platform-agnostic)
  cross_lineage.py      #   Cross-platform lineage + deduplication
  adapters/
    mstr_adapter.py     #   MSTR → Universal BI adapter
    tableau_adapter.py  #   Tableau → Universal BI adapter

migrate.py              # CLI entry point
```

## Key Concepts

- **MicroStrategy semantic layer**: Attributes → columns, Facts → numeric columns, Metrics → DAX measures
- **Expression conversion**: MSTR metric expressions → DAX with _FUNCTION_MAP (60+ entries)
- **18 intermediate JSON files**: datasources, attributes, facts, metrics, derived_metrics, reports, dossiers, cubes, filters, prompts, custom_groups, consolidations, hierarchies, relationships, security_filters, freeform_sql, thresholds, subtotals
- **Visual mapping**: 30+ MSTR viz types → PBI visual types
- **Connection mapping**: 15+ warehouse types → Power Query M expressions

## Build and Test

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
python migrate.py --help
```

## Conventions

- Reference project: `../TableauToPowerBI/` (v27.1.0, mature architecture — 6,818 tests, 96.2% coverage)
- Follow the same patterns as TableauToPowerBI wherever applicable
- Zero external dependencies for core logic (only `requests` for REST API)
- All extraction modules return plain dicts/lists serializable to JSON
- Generation modules consume only the intermediate JSON files (decoupled from extraction)
- See `docs/DEVELOPMENT_PLAN.md` for the full sprint roadmap\n- See `docs/MAPPING_REFERENCE.md` for all MSTR→PBI mapping tables

## Multi-Agent Development

7 specialized agents in `.github/agents/` handle domain-specific work:

| Agent | Invoke for | Key files |
|-------|-----------|----------|
| `@extraction` | REST API, schema/report/dossier extraction | `microstrategy_export/*` |
| `@expression` | MSTR→DAX conversion, function mappings | `expression_converter.py`, `metric_extractor.py` |
| `@generation` | TMDL, visuals, .pbip, M queries, deploy | `powerbi_import/*` |
| `@testing` | Unit tests, fixtures, coverage | `tests/*` |
| `@validation` | Assessment, fidelity scoring, reports | Validation/reporting modules |
| `@orchestrator` | CLI, config, cross-module coordination | `migrate.py`, `docs/`, `pyproject.toml` |
| `@parity` | Gap analysis vs TableauToPowerBI reference | `docs/DEVELOPMENT_PLAN.md` (gap analysis section), all modules |

## v3.0 Features

- **14-category assessment** with GREEN/YELLOW/RED scoring and effort estimation
- **Strategy advisor**: Import/DirectQuery/Composite/DirectLake recommendation
- **Comparison report**: Side-by-side MSTR↔PBI HTML report
- **Visual diff**: Field coverage analysis
- **Telemetry**: Migration run data collection + historical dashboard
- **Thin reports**: Shared model reference reports
- **Plugin system**: Extension hooks for custom transformations
- **Progress bars**: tqdm-based progress tracking
- CLI flags: `--global-assess`, `--strategy`, `--compare`, `--no-calendar`

## v5.0 Features

- **DirectLake TMDL**: Auto-generate `mode: directLake` partitions with Delta table entity references
- **Lakehouse DDL**: Spark SQL `CREATE TABLE ... USING DELTA` scripts from MSTR schema
- **PySpark ETL notebooks**: JDBC/Snowflake/BigQuery/Databricks connectors for Fabric Spark
- **OneLake shortcuts**: Zero-copy ADLS/external data references
- **Data Factory pipelines**: Copy activities + semantic model refresh + notification
- **Fabric Git integration**: Push .pbip to Fabric workspace Git repos
- **Fabric environment config**: Spark pool, JDBC libraries, capacity estimation (F2–F64)
- **Enhanced strategy advisor**: Always recommends DirectLake when Fabric is available
- CLI flags: `--fabric-mode`, `--lakehouse-name`, `--fabric-git`, `--fabric-git-branch`, `--adls-account`, `--adls-container`, `--env-name`

## v7.0 Features

- **AI-assisted expression converter**: Azure OpenAI fallback for unconvertible ApplySimple/ApplyAgg/ApplyOLAP expressions
- **Prompt engineering**: 10 curated few-shot MSTR→DAX examples, DAX grammar rules, confidence scoring
- **DAX syntax validation**: Lightweight validator (balanced parens, no SQL keywords, known function checks)
- **Response caching**: Persistent JSON cache to avoid redundant LLM calls
- **Token budget control**: Configurable per-run token limit with automatic cutoff
- **Semantic field matcher**: Fuzzy column matching with abbreviation expansion (90+ abbreviations), Levenshtein distance, token-overlap scoring
- **Auto-fix suggestions**: Top-N candidate matches for manual-review column references
- **Correction learning**: Persistent correction store that improves matching over time
- **Expression converter integration**: Module-level AI fallback via `set_ai_converter()`
- CLI flags: `--ai-assist`, `--ai-endpoint`, `--ai-key`, `--ai-deployment`, `--ai-budget`

## v6.0 Features

- **Data lineage graph**: In-memory DAG from warehouse tables → MSTR attributes/facts/metrics/reports → PBI tables/columns/measures/visuals
- **Impact analysis**: "What breaks if column X changes?" — transitive upstream/downstream traversal
- **Lineage HTML report**: Interactive D3.js force-directed graph, filterable by layer
- **Lineage JSON export**: Full graph + OpenLineage-compatible format
- **Microsoft Purview integration**: Register semantic models, tables, columns, measures with Apache Atlas REST API
- **Sensitivity classification**: Security-filter attributes → Purview sensitivity labels + pattern-based classification
- **Governance report**: 6-category pre-migration checklist (ownership, classification, RLS, lineage, documentation, readiness) with scoring
- CLI flags: `--lineage`, `--purview ACCOUNT`, `--governance`

## v16.0 Features

- **Fabric constants**: Centralized Spark type map (50+ MSTR→Delta types), TMDL type map, PySpark aggregation map, JDBC driver/URL maps, column sanitization, reserved word detection
- **Fabric naming**: Name sanitization for Lakehouse tables (64-char limit, no spaces), Dataflow/Pipeline/Semantic Model names, collision detection with numeric suffix resolution
- **Calculated column utilities**: Classify MSTR expressions as lakehouse-eligible (PySpark pre-compute) or DAX-only; convert eligible expressions to PySpark `withColumn()` calls with 30+ function mappings
- **Dataflow Gen2 generator**: Generate Fabric Dataflow Gen2 definitions with Power Query M mashup → Lakehouse Delta table destination; 6 connector templates + freeform SQL support
- **DirectLake semantic model generator**: Dedicated generator with expression-less tables, entityName partition bindings, DirectLake-specific properties, relationship TMDL, shared expression for Lakehouse binding
- **Centralized auth**: Azure AD authentication module with Service Principal, Managed Identity, interactive browser flow, token caching + refresh
- **Fabric REST API client**: Generic client with GET/POST/PATCH/DELETE, automatic retry (429/5xx), exponential backoff, pagination, workspace/item CRUD, long-running operation polling
- **Bundle deployer**: Atomic deployment of shared semantic model + N thin reports; rollback on partial failure; post-deployment endorsement (Promoted/Certified); environment-based config loading
- **2,458 total tests**: From 2,354 pre-v16.0 → 2,458 (~104 new Fabric + deploy tests)
- CLI flags: `--deploy-env dev|staging|prod`

## v17.0 Features

- **Pluggable monitoring**: Strategy-pattern `MigrationMonitor` with 4 backends (JSON file, Azure Monitor/OpenTelemetry, Prometheus text exposition, no-op). `record_metric()`, `record_event()`, `record_migration()`, `flush()` API
- **SLA compliance tracking**: `SLATracker` with `start()`/`record_result()` timing, `SLAResult`/`SLAReport` dataclasses, 3-dimension compliance (duration ≤ max, fidelity ≥ min, validation pass), configurable via JSON
- **Alert rule generation**: Extract MSTR thresholds from 3 sources (thresholds, metric-embedded, numeric prompts) → PBI data-driven alert rule definitions with operator normalisation
- **Refresh schedule migration**: Convert MSTR cache/subscription schedules to PBI dataset refresh config. Hourly→daily time slot generation, PBI Pro 8-refresh cap, weekly/monthly day mapping
- **Recovery report**: Self-healing tracker for automatic repairs during generation (sanitised names, unsupported visuals, broken relationships). Category/severity classification, merge into migration summary
- **Enterprise guide**: 8-phase enterprise migration guide (docs/ENTERPRISE_GUIDE.md)
- **2,670 total tests**: From 2,605 pre-v17.0 → 2,670 (65 new enterprise ops tests)
- CLI flags: `--monitor json|azure|prometheus|none`, `--sla-config FILE`, `--alerts`, `--migrate-schedules`

## v18.0 Features

- **Industry model templates**: 3 star-schema skeletons (Healthcare, Finance, Retail) with fact + dimension tables, relationships, measures, hierarchies. `apply_template()` enriches existing tables with missing columns and adds new template tables
- **DAX recipe library**: 21 curated DAX measure recipes across 3 industries (Healthcare 6, Finance 8, Retail 7). Injection + regex replacement modes. `recipes_to_marketplace_format()` bridge to pattern registry
- **Pattern marketplace**: Versioned `PatternRegistry` with `PatternMetadata`/`Pattern` classes. 5 categories (dax_recipe, visual_mapping, m_template, naming_convention, model_template). Semver versioning, directory loading, search by tags/category/name, `apply_dax_recipes()`, `apply_visual_overrides()`, export
- **Shared HTML framework**: Unified CSS/JS for all HTML reports — 17 design-token colours, dark mode, responsive, print styles. 16 HTML builder functions (stat_card, donut_chart, bar_chart, data_table with search/sort, tabs, flow_diagram, etc.)
- **2,752 total tests**: From 2,670 pre-v18.0 → 2,752 (82 new content library tests)
- CLI flags: `--template healthcare|finance|retail`, `--recipes INDUSTRY`, `--marketplace PATH`

## v12.0 Features

- **Universal BI schema**: Platform-agnostic intermediate format with 12 sections (datasources, dimensions, measures, relationships, hierarchies, security_rules, pages, parameters, filters, custom_groups, custom_sql). `empty_schema()`, `validate()`, `merge_schemas()`, `to_mstr_format()` APIs
- **MSTR adapter**: Converts all 18 MSTR intermediate JSONs → universal schema with source_platform provenance tags
- **Tableau adapter**: Converts Tableau intermediate JSONs (datasources with embedded tables/columns/relationships, worksheets, dashboards, calculations, parameters, hierarchies, user_filters, groups, sets, custom_sql) → universal schema. Mark-type → viz-type mapping, shelf → role mapping
- **Cross-platform lineage**: `detect_shared_sources()`, `detect_equivalent_dimensions()`, `detect_equivalent_measures()` with name/table/column similarity scoring. `deduplicate()` removes cross-platform duplicates. `build_lineage()` DAG builder with node types (source, dimension, measure, page, visual)
- **2,802 total tests**: From 2,752 pre-v12.0 → 2,802 (50 new federation tests)
- CLI flags: `--from-tableau DIR`, `--federate`

## v15.0 Features

- **DAX optimizer**: AST-based DAX rewriting with 5 rules — ISBLANK→COALESCE, chained IF→SWITCH (≥3 branches), nested CALCULATE flattening, redundant CALCULATE removal, CALCULATE simplification
- **Time Intelligence injection**: Auto-generate YTD (`TOTALYTD`), PY (`SAMEPERIODLASTYEAR`), YoY% variants for date-based measures via `--auto-time-intelligence`
- **Equivalence tester**: Cross-platform row-level value comparison with configurable numeric tolerance + lightweight SSIM screenshot comparison (no external deps)
- **Regression suite**: Golden snapshot generation/comparison for TMDL, JSON, M, PQ files; SHA-256 hash-based drift detection with manifest tracking; `--snapshot-update` to re-baseline
- **Security validator**: Path traversal detection, ZIP slip prevention, XXE pattern detection, dangerous extension blocking (.exe/.bat/.ps1), sensitive file warnings (.env/.key/.pem)
- **2,354 total tests**: From 2,260 pre-v15.0 → 2,354 (~89 new quality gate tests)
- CLI flags: `--optimize-dax`, `--auto-time-intelligence`, `--snapshot-update`

## v11.0 Features

- **Change detection**: Compare current vs previous intermediate JSON files to detect added/modified/deleted MicroStrategy objects; also supports API-based detection via REST API `modificationTime` polling
- **Drift report**: Compare live PBI output against previous migration baseline to detect manual user edits; generates JSON + HTML conflict report
- **Three-way reconciler**: MSTR source (new) × PBI target (live) × PBI target (baseline) merge engine; auto-applies safe changes, preserves user edits, flags conflicts; dry-run mode
- **Scheduled migration**: Cron-compatible pipeline script: change detection → drift report → reconciliation → reporting; configurable via `migration_schedule.json`
- **2,260 total tests**: From 2,208 pre-v11.0 → 2,260 (52 new migration ops tests)
- CLI flags: `--watch`, `--reconcile`, `--previous-dir`, `--baseline-dir`

## v10.0 Features

- **Property-based testing**: 100+ randomized invariant tests for expression converter, TMDL, visual generator, validator
- **Fuzz testing**: 50+ adversarial input tests (malformed expressions, SQL injection, unicode, nested parens)
- **Test generation from mappings**: Auto-generated parametrized tests from `_FUNCTION_MAP`, `_VIZ_TYPE_MAP`, `_DATA_TYPE_MAP`, `_GEO_ROLE_MAP` (181 test cases)
- **Gap-filling tests**: Comprehensive tests for 20+ under-tested modules (semantic matcher, notebook generator, pipeline generator, dashboard, shared model, etc.)
- **2,073 total tests**: From 885 pre-v10.0 → 2,073 (140% increase)

## v9.0 Features

- **Real-time source detection**: Classify MicroStrategy dashboards as batch/near-realtime/streaming based on refresh policies, cache settings, subscriptions
- **Push dataset generation**: Generate Power BI REST API push dataset definitions with type mapping and retention policies
- **Eventstream integration**: Fabric Real-Time Intelligence Eventstream definitions for streaming data sources
- **Refresh schedule migration**: Map MSTR cache/subscription schedules to PBI dataset refresh configurations with time slot generation
- **2,208 total tests**: From 2,175 pre-v9.0 → 2,208 (33 new streaming tests)
- CLI flags: `--realtime`

## v8.0 Features

- **i18n module**: Core internationalization support with 30+ supported cultures
- **Multi-culture TMDL**: `cultures.tmdl` + `translations.tmdl` with linguisticMetadata and translatedCaption entries for additional locales
- **Locale-aware format strings**: Culture-specific currency symbols, date patterns, number formats (30+ locales)
- **RTL layout support**: Automatic x-coordinate mirroring and `textDirection: RTL` for Arabic/Hebrew/Farsi/Urdu cultures
- **Culture extraction from data**: Auto-detect locale hints from datasource connections, dossier/report language settings
- **Culture TMDL wiring**: Primary culture in model.tmdl `culture:` / `sourceQueryCulture:` lines; additional cultures in separate TMDL files
- **Batch generation cultures**: `--cultures` flag propagated through single and batch generation modes
- CLI flags: `--cultures en-US,fr-FR,de-DE`
- **2,157 total tests**: From 2,073 pre-v8.0 → 2,157 (84 new i18n tests)
- **2,175 total tests**: Bug bash added 18 regression tests covering fixed crash bugs and API contract validation

## Roadmap (v15.0–v19.0) — TableauToPowerBI Parity

New development phases identified via gap analysis against the reference project (v27.1.0):

- **v15.0 DAX Optimization & Quality Gates**: `dax_optimizer.py`, `equivalence_tester.py`, `regression_suite.py`, `security_validator.py`
- **v16.0 Fabric Deep Integration Phase 2**: `dataflow_generator.py`, `fabric_constants.py`, `fabric_naming.py`, `calc_column_utils.py`, `fabric_semantic_model_generator.py`, `deploy/auth.py`, `deploy/client.py`, `deploy/bundle_deployer.py`
- **v17.0 Enterprise Operations & Monitoring**: `monitoring.py`, `sla_tracker.py`, `alerts_generator.py`, `refresh_generator.py`, `recovery_report.py`
- **v18.0 Content Library & Templates**: `model_templates.py`, `dax_recipes.py`, `marketplace.py`, `html_template.py`
- **v19.0 Developer Experience & Extensibility**: `notebook_api.py`, `geo_passthrough.py`, `governance.py`, `deploy/multi_tenant.py`, `Dockerfile`
- See `docs/DEVELOPMENT_PLAN.md` for full gap analysis table and sprint details
