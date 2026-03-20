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
  deploy/
    fabric_deployer.py  #   Fabric REST API deployment (SM, report, notebooks, pipelines)
    fabric_git.py       #   Push .pbip to Fabric workspace Git repos
    fabric_env.py       #   Fabric environment config + capacity estimation
    pbi_deployer.py     #   Power BI Service deployment
    gateway_config.py   #   On-premises gateway configuration

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

- Reference project: `../TableauToPowerBI/` (v17.0.0, mature architecture)
- Follow the same patterns as TableauToPowerBI wherever applicable
- Zero external dependencies for core logic (only `requests` for REST API)
- All extraction modules return plain dicts/lists serializable to JSON
- Generation modules consume only the intermediate JSON files (decoupled from extraction)
- See `docs/DEVELOPMENT_PLAN.md` for the full sprint roadmap\n- See `docs/MAPPING_REFERENCE.md` for all MSTR→PBI mapping tables

## Multi-Agent Development

6 specialized agents in `.github/agents/` handle domain-specific work:

| Agent | Invoke for | Key files |
|-------|-----------|-----------|
| `@extraction` | REST API, schema/report/dossier extraction | `microstrategy_export/*` |
| `@expression` | MSTR→DAX conversion, function mappings | `expression_converter.py`, `metric_extractor.py` |
| `@generation` | TMDL, visuals, .pbip, M queries, deploy | `powerbi_import/*` |
| `@testing` | Unit tests, fixtures, coverage | `tests/*` |
| `@validation` | Assessment, fidelity scoring, reports | Validation/reporting modules |
| `@orchestrator` | CLI, config, cross-module coordination | `migrate.py`, `docs/`, `pyproject.toml` |

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

## v10.0 Features

- **Property-based testing**: 100+ randomized invariant tests for expression converter, TMDL, visual generator, validator
- **Fuzz testing**: 50+ adversarial input tests (malformed expressions, SQL injection, unicode, nested parens)
- **Test generation from mappings**: Auto-generated parametrized tests from `_FUNCTION_MAP`, `_VIZ_TYPE_MAP`, `_DATA_TYPE_MAP`, `_GEO_ROLE_MAP` (181 test cases)
- **Gap-filling tests**: Comprehensive tests for 20+ under-tested modules (semantic matcher, notebook generator, pipeline generator, dashboard, shared model, etc.)
- **2,073 total tests**: From 885 pre-v10.0 → 2,073 (140% increase)

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
