# Architecture — MicroStrategy to Power BI / Fabric Migration Tool

## Pipeline Overview

The migration follows a **2-step pipeline**: Extraction (from MicroStrategy) → Generation (Power BI .pbip).

```mermaid
flowchart LR
    subgraph Input
        SRV["☁️ MicroStrategy Server<br/>(REST API v2)"]
        EXP["📁 JSON Exports<br/>(offline mode)"]
    end

    subgraph "Step 1 — Extraction"
        CLI["rest_api_client.py<br/>MstrRestClient"]
        EXT["extract_mstr_data.py<br/>MstrExtractor"]
        SCH["schema_extractor.py<br/>extract_schema()"]
        MET["metric_extractor.py<br/>extract_metrics()"]
        DSR["dossier_extractor.py<br/>extract_dossier()"]
        RPT["report_extractor.py<br/>extract_report()"]
        CUB["cube_extractor.py<br/>extract_cube()"]
        PRM["prompt_extractor.py<br/>extract_prompts()"]
        SEC["security_extractor.py<br/>extract_security()"]
        CNX["connection_mapper.py<br/>map_connections()"]
        EXC["expression_converter.py<br/>convert_mstr_to_dax()"]
    end

    subgraph "Intermediate JSON (18 files)"
        JSON["datasources.json<br/>attributes.json<br/>facts.json<br/>metrics.json<br/>hierarchies.json<br/>relationships.json<br/>reports.json<br/>dossiers.json<br/>cubes.json<br/>filters.json<br/>prompts.json<br/>custom_groups.json<br/>consolidations.json<br/>thresholds.json<br/>freeform_sql.json<br/>security_filters.json<br/>derived_metrics.json<br/>subtotals.json"]
    end

    subgraph "Step 2 — Generation"
        IMP["import_to_powerbi.py<br/>PowerBIImporter"]
        PBIP["pbip_generator.py<br/>PBIPGenerator"]
        TMDL["tmdl_generator.py<br/>generate_tmdl()"]
        VIS["visual_generator.py<br/>VisualGenerator"]
        MQG["m_query_generator.py<br/>MQueryGenerator"]
        VAL["validator.py<br/>ArtifactValidator"]
        DEP["deploy/<br/>PBI/Fabric deployer"]
    end

    subgraph Output
        PROJ[".pbip Project<br/>PBIR v4.0 Report<br/>TMDL Semantic Model"]
    end

    SRV --> CLI
    EXP --> EXT
    CLI --> EXT
    EXT --> SCH
    EXT --> MET
    EXT --> DSR
    EXT --> RPT
    EXT --> CUB
    EXT --> PRM
    EXT --> SEC
    EXT --> CNX
    SCH --> EXC
    MET --> EXC
    EXT --> JSON
    JSON --> IMP
    IMP --> PBIP
    PBIP --> TMDL
    PBIP --> VIS
    PBIP --> MQG
    IMP --> VAL
    PBIP --> PROJ
    PROJ --> DEP
```

---

## Module Responsibilities

### Extraction Layer (`microstrategy_export/`)

| Module | Responsibility |
|--------|----------------|
| `rest_api_client.py` | HTTP client for MicroStrategy REST API v2. Authentication (Standard, LDAP, SAML, OAuth). Token management. Pagination. Rate limiting. Retry logic. |
| `extract_mstr_data.py` | Top-level orchestrator. Discovers project objects, delegates to specialized extractors, writes intermediate JSON files. |
| `schema_extractor.py` | Extracts attributes (with forms), facts (with expressions), logical tables, warehouse tables, hierarchies, custom groups, consolidations, freeform SQL. |
| `metric_extractor.py` | Extracts metric definitions (simple, compound, derived/OLAP), thresholds (conditional formatting), format strings. |
| `expression_converter.py` | Parses MicroStrategy expression syntax and converts to DAX. Handles aggregations, level metrics, derived metrics, functions, ApplySimple SQL passthrough. |
| `report_extractor.py` | Extracts report templates (grid rows/columns, metrics, filters, sorts), report graphs, subtotals, legacy documents. |
| `dossier_extractor.py` | Extracts dossier structure: chapters → pages → visualizations → data bindings.  Panel stacks, filter panels, selector controls, info windows. |
| `cube_extractor.py` | Extracts Intelligent Cube definitions: attributes, metrics, filters. Used for import-mode tables. |
| `prompt_extractor.py` | Extracts prompts: value, object, hierarchy, expression, date. Maps to Power BI slicers/parameters. |
| `security_extractor.py` | Extracts security filters (row-level security) with filter expressions and user/group assignments. |
| `connection_mapper.py` | Maps MicroStrategy warehouse connection types to Power Query M connection expressions. |
| `scorecard_extractor.py` | Extracts MicroStrategy scorecards (objectives, KPIs, perspectives) for PBI Goals conversion. |
| `realtime_extractor.py` | Classifies MicroStrategy dashboards as batch/near-realtime/streaming based on refresh policies, cache settings, subscriptions. |
| `incremental.py` | Incremental extraction: delta detection for changed objects since last extraction run. |
| `parallel.py` | Parallel extraction workers for concurrent object retrieval. |
| `change_detector.py` | Compares current vs previous intermediate JSON files to detect added/modified/deleted objects. |

### Generation Layer (`powerbi_import/` — 39 modules)

| Module | Responsibility |
|--------|----------------|
| `import_to_powerbi.py` | Loads intermediate JSON files and orchestrates generation pipeline. |
| `pbip_generator.py` | Creates `.pbip` project directory structure: `.pbip` file, `.gitignore`, SemanticModel (TMDL), Report (PBIR v4.0). |
| `tmdl_generator.py` | Generates TMDL semantic model: tables (from warehouse tables), columns (from attribute forms + fact columns), measures (from metrics), relationships, hierarchies, RLS roles, Calendar table. Format strings, geographic roles, annotations. Supports Import + DirectLake modes. |
| `visual_generator.py` | Generates PBIR v4.0 visuals: maps dossier visualizations / report grids+graphs to Power BI visual types with data bindings. |
| `m_query_generator.py` | Generates Power Query M expressions for warehouse connections. Handles 15+ database types + freeform SQL passthrough. |
| `validator.py` | Validates generated artifacts: TMDL syntax, PBIR schema, relationship cycles, DAX references, column type compatibility. |
| `assessment.py` | 14-category pre-migration assessment: CheckItem/CategoryResult/AssessmentReport model. GREEN/YELLOW/RED scoring with effort estimation in hours. |
| `migration_report.py` | Generates migration report (JSON + HTML): per-object status, expression conversion details, warnings, manual review items. |
| `dashboard.py` | Interactive HTML fidelity dashboard: fidelity gauge, type breakdown, heatmap, searchable object table. |
| `shared_model.py` | Shared semantic model: merges all project schema into one model with thin reports per dossier. |
| `thin_report_generator.py` | Thin reports referencing a shared semantic model. PBIR `byPath` or `byConnection` bindings. |
| `merge_assessment.py` | Merge assessment report (JSON + HTML) for multi-project merge scenarios. |
| `merge_config.py` | Per-table merge rules for conflict resolution during multi-project merge. |
| `merge_report_html.py` | Interactive HTML dashboard for merge assessment results. |
| `server_assessment.py` | Server-wide portfolio assessment: `WorkbookReadiness`, `MigrationWave` planning across multiple projects. |
| `global_assessment.py` | Multi-project global assessment with pairwise-merge clustering and consolidated scoring. |
| `comparison_report.py` | Side-by-side MSTR↔PBI HTML comparison report for post-migration validation. |
| `visual_diff.py` | Visual type + field coverage analysis: identifies missing columns, measure mismatches, layout differences. |
| `strategy_advisor.py` | Import/DirectQuery/Composite/DirectLake mode recommendation with confidence scoring. Always recommends DirectLake when Fabric is available. |
| `fabric_constants.py` | Centralized Spark type map (50+ MSTR→Delta types), TMDL type map, PySpark aggregation map, JDBC driver/URL maps, column sanitization, reserved word detection. |
| `fabric_naming.py` | Name sanitization for Lakehouse tables (64-char limit, no spaces), Dataflow/Pipeline/Semantic Model names. Collision detection with numeric suffix resolution. |
| `fabric_semantic_model_generator.py` | Dedicated DirectLake semantic model generator: expression-less tables with entityName partition bindings, DirectLake-specific model properties, relationship TMDL, shared expression for Lakehouse binding. |
| `dataflow_generator.py` | Generate Fabric Dataflow Gen2 definitions: Power Query M mashup → Lakehouse Delta table destination. 6 connector templates + freeform SQL support. |
| `calc_column_utils.py` | Classify MSTR expressions as lakehouse-eligible (PySpark pre-compute) or DAX-only. Convert eligible expressions to PySpark `withColumn()` calls. 30+ function mappings. |
| `lakehouse_generator.py` | Fabric Lakehouse DDL: `CREATE TABLE ... USING DELTA` scripts from MSTR schema. OneLake shortcuts for zero-copy ADLS/external data. |
| `notebook_generator.py` | PySpark ETL notebooks: JDBC/Snowflake/BigQuery/Databricks connectors for Fabric Spark. |
| `pipeline_generator.py` | Data Factory pipeline JSON: copy activities + semantic model refresh + notification. |
| `ai_converter.py` | Azure OpenAI LLM fallback for unconvertible expressions. 10 few-shot examples, DAX syntax validation, response caching, token budget. |
| `semantic_matcher.py` | Fuzzy column matching with abbreviation expansion (90+ abbreviations), Levenshtein distance, token-overlap scoring. Correction learning with persistent store. |
| `dax_optimizer.py` | AST-based DAX rewriting: ISBLANK→COALESCE, IF→SWITCH, nested CALCULATE flattening, redundant CALCULATE removal. Time Intelligence injection (YTD, PY, YoY%). |
| `i18n.py` | Multi-language support: 30+ cultures, TMDL `cultures.tmdl` + `translations.tmdl`, locale-aware format strings, RTL layout for Arabic/Hebrew/Farsi/Urdu. |
| `streaming_generator.py` | Push dataset definitions, Fabric Eventstream definitions, refresh schedule migration from MSTR cache/subscription policies. |
| `lineage.py` | Data lineage DAG: warehouse tables → MSTR attributes/facts/metrics/reports → PBI tables/columns/measures/visuals. Impact analysis. |
| `lineage_report.py` | Interactive D3.js force-directed lineage HTML graph, filterable by layer. OpenLineage-compatible JSON export. |
| `purview_integration.py` | Microsoft Purview asset registration via Apache Atlas REST API. Sensitivity classification for security-filter attributes. |
| `governance_report.py` | 6-category pre-migration governance checklist: ownership, classification, RLS, lineage, documentation, readiness. |
| `drift_report.py` | Compare live PBI output against previous migration baseline to detect manual user edits. JSON + HTML conflict report. |
| `reconciler.py` | Three-way merge engine: MSTR source × PBI target (live) × PBI target (baseline). Auto-applies safe changes, preserves user edits, flags conflicts. Dry-run mode. |
| `equivalence_tester.py` | Cross-platform value comparison with configurable numeric tolerance + SSIM-based screenshot comparison. |
| `regression_suite.py` | Golden snapshot generation/comparison. SHA-256 hash-based drift detection with manifest tracking. |
| `security_validator.py` | Path traversal detection, ZIP slip prevention, XXE pattern detection, dangerous extension blocking (.exe/.bat/.ps1), sensitive file warnings. |
| `certification.py` | Post-migration certification: PASS/FAIL verdict based on configurable fidelity threshold. |
| `goals_generator.py` | MicroStrategy scorecards → PBI Goals JSON conversion. |
| `theme_generator.py` | Theme extraction and generation for PBIR report styling. |
| `telemetry.py` | Migration run data collection: timings, object counts, fidelity scores per run. |
| `telemetry_dashboard.py` | Historical aggregation HTML dashboard across multiple migration runs. |
| `progress.py` | tqdm-based progress bar wrapper with fallback for non-TTY environments. |
| `plugins.py` | Extension point hook system: pre/post extraction, pre/post generation, custom transformation plugins. |

### Deployment Layer (`powerbi_import/deploy/`)

| Module | Responsibility |
|--------|----------------|
| `auth.py` | Centralized Azure AD authentication: Service Principal, Managed Identity, interactive browser flow. Token caching + automatic refresh. |
| `client.py` | Generic Fabric REST API client: GET/POST/PATCH/DELETE with automatic retry (429/5xx), exponential backoff, pagination, workspace/item CRUD, long-running operation polling. |
| `bundle_deployer.py` | Atomic bundle deployment: shared semantic model + N thin reports as a single unit. Rollback on partial failure. Post-deployment endorsement (Promoted/Certified). Environment-based config loading. |
| `fabric_deployer.py` | Fabric REST API deployment: semantic models, reports, notebooks, pipelines. |
| `fabric_git.py` | Push .pbip to Fabric workspace Git repos. |
| `fabric_env.py` | Fabric environment config: Spark pool size, JDBC libraries, capacity estimation (F2–F64). |
| `pbi_deployer.py` | Power BI Service deployment via REST API. |
| `gateway_config.py` | On-premises data gateway mapping and configuration. |
| `refresh_config.py` | Refresh schedule migration from MSTR cache/subscription policies to PBI dataset refresh. |

---

## Data Flow: MicroStrategy Concepts → Power BI Concepts

```
MicroStrategy                      Power BI
─────────────                      ────────
Project                    →       Workspace
  └─ Schema                →       Semantic Model
       ├─ Tables           →       TMDL Tables (with M partitions)
       ├─ Attributes       →       Columns (dimension)
       │    └─ Forms       →       Key column + display column
       ├─ Facts            →       Columns + implicit measures
       ├─ Metrics          →       DAX Measures
       │    ├─ Simple      →       SUM/AVG/COUNT DAX
       │    ├─ Compound    →       Nested DAX measures
       │    ├─ Derived     →       RANKX/WINDOW/OFFSET DAX
       │    └─ Level       →       CALCULATE + ALLEXCEPT DAX
       ├─ Hierarchies      →       TMDL Hierarchies
       ├─ Relationships    →       TMDL Relationships
       └─ Security Filters →       TMDL RLS Roles
  └─ Reports               →       Report Pages (thin reports)
       ├─ Grid             →       Table/Matrix visual
       ├─ Graph            →       Chart visual (type mapped)
       ├─ Filters          →       Report/page/visual filters
       ├─ Prompts          →       Slicers / what-if parameters
       └─ Thresholds       →       Conditional formatting
  └─ Dossiers              →       Multi-page Reports
       ├─ Chapters         →       Page groups
       ├─ Pages            →       Report pages
       ├─ Visualizations   →       Visuals (type mapped)
       ├─ Panel Stacks     →       Bookmark navigator
       ├─ Filter Panels    →       Slicers
       └─ Selectors        →       Slicers / field parameters
  └─ Cubes                 →       Import-mode tables
  └─ Warehouse Connections →       Power Query M data sources
```

---

## Key Design Decisions

1. **REST API first**: Primary extraction via MicroStrategy REST API v2 (Modeling API + Report/Dossier API). Offline JSON export as fallback.

2. **Intermediate JSON**: Same pattern as Tableau tool — extraction produces JSON files that generation consumes. Enables debugging and manual inspection.

3. **Expression conversion**: MicroStrategy expressions are more complex than Tableau (level metrics, Apply functions). Dedicated converter with extensive test coverage.

4. **Schema-centric model**: MicroStrategy has a stronger semantic layer than Tableau. The Power BI model mirrors this: attributes→columns, facts→columns, metrics→measures.

5. **Reuse generation layer**: The `powerbi_import/` layer is adapted from the Tableau tool. TMDL generator, visual generator, and deployment modules are extended rather than rewritten.

---

## Multi-Agent Development Architecture

Development is organized around 6 specialized Copilot agents (`.github/agents/`):

```
                    ┌──────────────────┐
                    │   Orchestrator   │
                    │  (migrate.py,    │
                    │   CLI, config,   │
                    │   coordination)  │
                    └────────┬─────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
  ┌───────▼───────┐  ┌──────▼──────┐  ┌───────▼───────┐
  │  Extraction   │  │ Expression  │  │  Generation   │
  │ microstrategy │  │ converter,  │  │ powerbi_import│
  │  _export/*    │  │ metric_ext  │  │ tmdl, visual, │
  │ REST API→JSON │  │ MSTR→DAX    │  │ pbip, deploy  │
  └───────┬───────┘  └──────┬──────┘  └───────┬───────┘
          │                  │                  │
          └──────────────────┼──────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                                     │
  ┌───────▼───────┐                    ┌───────▼───────┐
  │    Testing    │                    │  Validation   │
  │   tests/*    │                    │  assessment,  │
  │  pytest,     │                    │  fidelity,    │
  │  fixtures    │                    │  reporting    │
  └──────────────┘                    └───────────────┘
```

### Agent → Module Mapping

| Agent | Modules Owned | When to Use |
|-------|--------------|-------------|
| **Orchestrator** | `migrate.py`, `config.example.json`, `docs/`, `pyproject.toml` | CLI changes, config, cross-module integration, sprint planning |
| **Extraction** | `microstrategy_export/*` (all 16 files) | REST API client, schema/report/dossier/cube extraction, real-time detection, change detection, JSON output |
| **Expression** | `expression_converter.py`, `metric_extractor.py`, `ai_converter.py`, `semantic_matcher.py`, `dax_optimizer.py` | MSTR→DAX conversion, function mappings, AI-assisted fallback, DAX optimization |
| **Generation** | `powerbi_import/*` (39 modules + `deploy/` subpackage) | TMDL, visuals, pbip, M queries, Fabric-native generation, Dataflow Gen2, DirectLake, deployment |
| **Testing** | `tests/*` (35 test files, 2,458 tests) | Unit, integration, property-based, fuzz, regression tests |
| **Validation** | Validation/assessment/reporting modules | Pre-migration assessment, post-gen validation, fidelity scoring, equivalence testing, security validation |
| **Parity** | Gap analysis, roadmap modules | Gap analysis vs TableauToPowerBI reference, sprint planning for parity |

### Parallel Execution

Agents can work in parallel when their tasks don't share module boundaries:
- Extraction + Generation (once JSON schema is stable)
- Expression works across both layers (shared conversion logic)
- Testing + any feature agent (TDD pattern)
- Validation + Generation (post-generation checks)
