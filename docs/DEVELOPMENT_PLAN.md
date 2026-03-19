# Development Plan — MicroStrategy to Power BI / Fabric Migration Tool

**Version:** v3.0.0 (released)  
**Date:** 2026-03-20  
**Based on:** Tableau to Power BI Migration Tool (v17.0.0 architecture)  
**Current state:** v3.0 complete — 623 tests passing, 11 new modules in v3.0

---

## Overview

This tool automates the migration of **MicroStrategy** reports, dossiers, cubes, and semantic objects to **Power BI / Microsoft Fabric** `.pbip` projects (PBIR v4.0 + TMDL semantic model). It reuses the proven 2-step pipeline architecture from the Tableau→Power BI tool:

```
EXTRACT (MicroStrategy) → Intermediate JSON → GENERATE (Power BI .pbip)
```

### Key Differences from Tableau Migration

| Aspect | Tableau | MicroStrategy |
|--------|---------|---------------|
| **Source format** | `.twb`/`.twbx` XML files | REST API + exported JSON/PDF or `.mstr` project packages |
| **Metadata model** | Datasources, worksheets, dashboards | Attributes, metrics, facts, reports, dossiers, cubes |
| **Expression language** | Tableau calculated fields | MicroStrategy metric expressions (ApplySimple, ApplyAgg, etc.) |
| **Connection** | Embedded in XML | Warehouse connections via Intelligence Server |
| **Semantic layer** | Flat datasource fields | Multi-level schema: Facts → Attributes → Metrics → Filters |
| **Security** | User filters | Security filters + ACLs + privileges |
| **Parameters** | Tableau parameters | Prompts (value, object, hierarchy, expression, date) |
| **Visuals** | Marks on worksheets | Visualizations in dossier chapters/pages |
| **Pre-built objects** | Prep flows | Freeform SQL, custom groups, consolidations |

---

## Architecture

```
              +-------------------------------+
              |           INPUT               |
              |  REST API (Intelligence Server)|
              |  Exported JSON/packages        |
              |  .mstr project files           |
              +---------------+---------------+
                              |
                              v
              +-------------------------------+
              |    STEP 1 - EXTRACTION        |
              |   microstrategy_export/       |
              |                               |
              |  extract_mstr_data.py         |
              |    +-- rest_api_client.py      |
              |    +-- schema_extractor.py     |
              |    +-- metric_extractor.py     |
              |    +-- dossier_extractor.py    |
              |    +-- report_extractor.py     |
              |    +-- cube_extractor.py       |
              |    +-- expression_converter.py |
              |    +-- prompt_extractor.py     |
              |    +-- security_extractor.py   |
              |    +-- connection_mapper.py    |
              +---------------+---------------+
                              |
                              v
              +-------------------------------+
              |      INTERMEDIATE JSON        |
              |  (18 files)                   |
              |                               |
              |  datasources.json  metrics.json|
              |  attributes.json   facts.json  |
              |  filters.json      prompts.json|
              |  reports.json      dossiers.json|
              |  cubes.json        custom_groups|
              |  security_filters  hierarchies |
              |  relationships     thresholds  |
              |  consolidations    freeform_sql|
              |  derived_metrics   subtotals   |
              +---------------+---------------+
                              |
                              v
              +-------------------------------+
              |    STEP 2 - GENERATION        |
              |   powerbi_import/             |
              |   (reused + extended)         |
              |                               |
              |  import_to_powerbi.py         |
              |    +-- pbip_generator.py       |
              |    +-- tmdl_generator.py       |
              |    +-- visual_generator.py     |
              |    +-- dax_expression_gen.py   |
              |    +-- m_query_generator.py    |
              |    +-- validator.py            |
              |    +-- deploy/                 |
              +---------------+---------------+
                              |
                              v
              +-------------------------------+
              |           OUTPUT              |
              |  .pbip Project                |
              |  PBIR v4.0 Report             |
              |  TMDL Semantic Model          |
              |  Migration Report (HTML/JSON) |
              +-------------------------------+
```

---

## Sprint Plan

### Phase 1 — Foundation (Sprints 1-5)

#### Sprint 1 — REST API Client & Project Scaffolding ✨CRITICAL

**Goal:** Establish the MicroStrategy REST API client for connecting to Intelligence Server, authenticating, and discovering projects. Set up the project structure mirroring the Tableau tool.

| # | Item | File(s) | Est. | Details |
|---|------|---------|------|---------|
| 1.1 | **Project scaffolding** | `migrate.py`, `pyproject.toml`, `requirements.txt`, `.gitignore` | Low | Mirror Tableau tool structure: `microstrategy_export/`, `powerbi_import/`, `tests/`, `docs/`, `scripts/`. Reuse `powerbi_import/` modules where possible. |
| 1.2 | **REST API client — authentication** | `microstrategy_export/rest_api_client.py` | High | Support MicroStrategy REST API v2 authentication: Standard (username/password), LDAP, SAML, OAuth. Token management with auto-refresh. Base URL configuration. SSL/TLS options. |
| 1.3 | **REST API client — project discovery** | `microstrategy_export/rest_api_client.py` | Medium | `GET /api/projects` — list all projects. `GET /api/projects/{id}` — project details. Store project metadata (name, ID, description, default language). |
| 1.4 | **REST API client — object search** | `microstrategy_export/rest_api_client.py` | Medium | `GET /api/searches/results` — search for objects by type (report=3, document=55, dossier=55, cube=21, metric=4, attribute=12, filter=1, prompt=10, etc.). Pagination handling. Folder-level recursive discovery. |
| 1.5 | **REST API client — object definition** | `microstrategy_export/rest_api_client.py` | Medium | `GET /api/model/tables`, `GET /api/model/facts`, `GET /api/model/attributes`, `GET /api/model/metrics` — full object definitions via Modeling API. |
| 1.6 | **CLI entry point** | `migrate.py` | Medium | Argument parsing: `--server`, `--username`, `--password`, `--project`, `--report`, `--dossier`, `--batch`, `--output-dir`, `--assess`, `--verbose`, `--deploy`. Structured exit codes. |
| 1.7 | **Configuration file** | `config.example.json` | Low | Server URL, authentication mode, project name, object filters, output preferences, deployment settings. |
| 1.8 | **Tests** | `tests/test_rest_api_client.py` | Medium | 40+ tests: auth flows, token refresh, project listing, object search pagination, error handling, SSL, retry logic. |

---

#### Sprint 2 — Schema Extraction: Attributes, Facts & Tables

**Goal:** Extract the MicroStrategy schema layer — the foundation of every report/dossier. Attributes (dimensions), facts (measures), and warehouse tables map to Power BI's semantic model.

| # | Item | File(s) | Est. | Details |
|---|------|---------|------|---------|
| 2.1 | **Table extraction** | `microstrategy_export/schema_extractor.py` | Medium | `GET /api/model/tables` — extract all warehouse/logical tables: name, physical table name, columns, data types, warehouse connection. Map to `datasources.json`. |
| 2.2 | **Attribute extraction** | `microstrategy_export/schema_extractor.py` | High | `GET /api/model/attributes/{id}` — extract attributes with: attribute forms (ID, DESC, lookup columns), data types, display format, geographical role, sort order, hierarchies, parent-child relationships. Map to `attributes.json`. |
| 2.3 | **Fact extraction** | `microstrategy_export/schema_extractor.py` | Medium | `GET /api/model/facts/{id}` — extract facts with: expressions (column mappings per table), data type, format string, aggregation function (SUM/AVG/COUNT/etc.). Map to `facts.json`. |
| 2.4 | **Hierarchy extraction** | `microstrategy_export/schema_extractor.py` | Medium | Extract user hierarchies and system hierarchies from attribute definitions. Map to `hierarchies.json` — each hierarchy has ordered levels (attributes) with drill-down paths. |
| 2.5 | **Relationship extraction** | `microstrategy_export/schema_extractor.py` | High | Infer relationships from: (a) attribute-to-fact lookup table joins, (b) attribute-to-attribute parent-child links, (c) table-level foreign key mappings. Map to `relationships.json` compatible with TMDL generator. |
| 2.6 | **Warehouse connection mapping** | `microstrategy_export/connection_mapper.py` | Medium | Map MicroStrategy warehouse DB types to Power Query M connection strings: Oracle, SQL Server, PostgreSQL, MySQL, Teradata, Netezza, DB2, Snowflake, Databricks, BigQuery, SAP HANA, ODBC/Generic. |
| 2.7 | **Tests** | `tests/test_schema_extractor.py` | Medium | 50+ tests: attribute form parsing, fact expression mapping, hierarchy ordering, relationship inference, connection string generation. |

---

#### Sprint 3 — Metric Extraction & Expression Conversion ✨CRITICAL

**Goal:** Extract MicroStrategy metrics (calculated measures) and convert MicroStrategy expression language to DAX. This is the most complex mapping layer.

| # | Item | File(s) | Est. | Details |
|---|------|---------|------|---------|
| 3.1 | **Metric expression parser** | `microstrategy_export/expression_converter.py` | Very High | Parse MicroStrategy metric expressions: `Sum(Revenue)`, `Avg(Cost)`, `Count(Distinct OrderID)`, `StDev()`, `Median()`, `Percentile()`. Handle compound metrics: `Revenue - Cost` → `[Revenue] - [Cost]`. |
| 3.2 | **Conditional metric conversion** | `microstrategy_export/expression_converter.py` | High | `If(Condition, TrueExpr, FalseExpr)` → `IF(condition, trueExpr, falseExpr)`. `Case/When` → `SWITCH()`. `ApplySimple` (passthrough SQL) → DAX equivalent or M `Value.NativeQuery()` fallback. |
| 3.3 | **Level metrics (dimensionality)** | `microstrategy_export/expression_converter.py` | Very High | MicroStrategy level metrics (`Sum(Revenue) {~+, Year}`) → DAX: `CALCULATE([Revenue], ALLEXCEPT(Table, Table[Year]))`. Filtering: `{!Region}` → `REMOVEFILTERS(Table[Region])`. Interaction types: `{~+}`, `{~}`, `{!}`, `{^}` → appropriate CALCULATE filter modifiers. |
| 3.4 | **Derived metric conversion** | `microstrategy_export/expression_converter.py` | High | Derived metrics (compound/nested): `RunningSum`, `RunningAvg`, `Rank`, `NTile`, `Lag`, `Lead`, `MovingAvg`, `MovingSum`, `OLAPRank` → DAX window functions or RANKX/EARLIER patterns. |
| 3.5 | **ApplySimple/ApplyAgg/ApplyComparison** | `microstrategy_export/expression_converter.py` | High | `ApplySimple("SQL expression", args)` — passthrough SQL. Convert common patterns to DAX. Flag unconvertible SQL as manual review items. `ApplyAgg`, `ApplyComparison`, `ApplyLogic`, `ApplyOLAP` similarly mapped. |
| 3.6 | **String & date functions** | `microstrategy_export/expression_converter.py` | Medium | `Concat()` → `CONCATENATE()`. `Length()` → `LEN()`. `SubStr()` → `MID()`. `Trim()` → `TRIM()`. `CurrentDate()` → `TODAY()`. `DaysBetween()` → `DATEDIFF()`. `Year()/Month()/Day()` → `YEAR()/MONTH()/DAY()`. `DateAdd()` → `DATEADD()`. 60+ function mappings. |
| 3.7 | **Null handling & type casting** | `microstrategy_export/expression_converter.py` | Medium | `NullToZero()` → `IF(ISBLANK(x), 0, x)`. `IsNull()` → `ISBLANK()`. `IsNotNull()` → `NOT(ISBLANK())`. `CastAs()` → `CONVERT()` / `FORMAT()`. |
| 3.8 | **Metric format strings** | `microstrategy_export/metric_extractor.py` | Medium | Map MicroStrategy number formats (`#,##0.00`, `$#,##0`, `0.0%`, date formats) to DAX format strings. |
| 3.9 | **Tests** | `tests/test_expression_converter.py` | High | 100+ tests: every function mapping, level metrics, derived metrics, ApplySimple patterns, nested expressions, edge cases. |

---

#### Sprint 4 — Report & Dossier Extraction

**Goal:** Extract MicroStrategy reports (grid/graph) and dossiers (interactive dashboards) — the visual layer.

| # | Item | File(s) | Est. | Details |
|---|------|---------|------|---------|
| 4.1 | **Report definition extraction** | `microstrategy_export/report_extractor.py` | High | `GET /api/v2/reports/{id}` — extract report template: grid rows/columns (attributes + metrics), page-by fields, subtotals/grand totals, sort order, metric thresholds (conditional formatting), graph type. Map to `reports.json`. |
| 4.2 | **Report filter extraction** | `microstrategy_export/report_extractor.py` | Medium | Extract report filters: attribute element list filters, metric qualification filters, shortcut-to-report filters, view filters. `GET /api/reports/{id}/instances` for runtime filter state. Map to `filters.json`. |
| 4.3 | **Dossier extraction** | `microstrategy_export/dossier_extractor.py` | Very High | `GET /api/v2/dossiers/{id}/definition` — extract full dossier structure: chapters → pages → visualizations → panels. For each visualization: type (grid, graph, image, text, filter, map), attributes, metrics, filters, thresholds, formatting, target links. Map to `dossiers.json`. |
| 4.4 | **Visualization type mapping** | `microstrategy_export/dossier_extractor.py` | High | Map MicroStrategy visualization types to intermediate JSON: Grid→table, VerticalBar→clusteredColumnChart, HorizontalBar→clusteredBarChart, Line→lineChart, Area→areaChart, Pie→pieChart, Ring→donutChart, Scatter/Bubble→scatterChart, Map→map, TreeMap→treemap, HeatMap→matrix, Waterfall→waterfall, BoxPlot→boxplot, NetworkGraph→custom, KPI→kpi, Gauge→gauge. |
| 4.5 | **Prompt extraction** | `microstrategy_export/prompt_extractor.py` | High | `GET /api/v2/reports/{id}/prompts` or dossier prompts. Types: Value prompt → Power BI slicer/parameter. Object prompt → field parameter. Hierarchy prompt → slicer with hierarchy. Expression prompt → DAX measure parameter. Date prompt → date slicer. Map to `prompts.json`. |
| 4.6 | **Cube/Intelligent Cube extraction** | `microstrategy_export/cube_extractor.py` | Medium | `GET /api/v2/cubes/{id}` — extract cube definition: attributes, metrics, filter. Map to pre-aggregated import mode tables. `GET /api/v2/cubes/{id}/instances` for data preview. |
| 4.7 | **Tests** | `tests/test_report_extractor.py`, `tests/test_dossier_extractor.py` | High | 60+ tests: report grid parsing, filter types, dossier chapter/page/panel structure, viz type mapping, prompt conversion, cube metadata. |

---

#### Sprint 5 — Advanced Object Extraction

**Goal:** Extract remaining MicroStrategy objects that enrich the semantic model.

| # | Item | File(s) | Est. | Details |
|---|------|---------|------|---------|
| 5.1 | **Custom group extraction** | `microstrategy_export/schema_extractor.py` | Medium | Custom groups (user-defined groupings) → DAX `SWITCH()` calculated columns or Power Query M conditional columns. Map name, elements (filter definitions per group element), and display order. |
| 5.2 | **Consolidation extraction** | `microstrategy_export/schema_extractor.py` | Medium | Consolidations (custom aggregation hierarchies) → DAX calculated tables or measures with `CALCULATE` + explicit filter lists. |
| 5.3 | **Threshold extraction** | `microstrategy_export/metric_extractor.py` | Medium | MicroStrategy thresholds (conditional formatting on metrics) → Power BI conditional formatting rules. Color, font, background, icon sets mapped. Map to `thresholds.json`. |
| 5.4 | **Subtotal/Grand total extraction** | `microstrategy_export/report_extractor.py` | Medium | Extract subtotal definitions (Sum, Avg, Count, Min, Max, custom) → TMDL implicit measures or explicit DAX measures. Position (top/bottom). Map to `subtotals.json`. |
| 5.5 | **Freeform SQL extraction** | `microstrategy_export/schema_extractor.py` | Medium | `GET /api/model/tables` with `freeformSql` type — extract SQL text, parameters, warehouse connection. Map to Power Query M `Value.NativeQuery()`. Map to `freeform_sql.json`. |
| 5.6 | **Security filter extraction** | `microstrategy_export/security_extractor.py` | High | Extract security filters (row-level security): filter expression, target attributes, user/group assignments. Map to Power BI RLS roles. Map to `security_filters.json`. |
| 5.7 | **Document extraction** (legacy) | `microstrategy_export/report_extractor.py` | Medium | Legacy MicroStrategy documents (Report Services documents) — extract grid/graph/text components with layout. Flag as legacy with conversion warnings. |
| 5.8 | **Tests** | `tests/test_advanced_extraction.py` | Medium | 40+ tests: custom groups, consolidations, thresholds, subtotals, freeform SQL, security filters, legacy documents. |

---

### Phase 2 — Generation & Conversion (Sprints 6-10)

#### Sprint 6 — Semantic Model Generation (TMDL) ✨CRITICAL

**Goal:** Convert extracted MicroStrategy schema (attributes, facts, metrics) into a TMDL semantic model. This is the core of the Power BI output.

| # | Item | File(s) | Est. | Details |
|---|------|---------|------|---------|
| 6.1 | **Table generation from warehouse tables** | `powerbi_import/tmdl_generator.py` | High | Each MicroStrategy logical table → TMDL table with: columns from attribute forms + fact columns. M partition with Power Query connection to source warehouse. Handle multi-source tables (same attribute from multiple tables). |
| 6.2 | **Column generation from attributes** | `powerbi_import/tmdl_generator.py` | High | Attribute forms → TMDL columns: ID form → hidden key column, DESC form → display column, other forms → additional columns. Data types mapped: MicroStrategy (Integer, Real, Char, VarChar, Date, TimeStamp, BigDecimal, etc.) → TMDL types (int64, double, string, dateTime, decimal). |
| 6.3 | **Measure generation from metrics** | `powerbi_import/tmdl_generator.py` | Very High | Each MicroStrategy metric → TMDL measure with DAX expression (from Sprint 3 converter). Compound/nested metrics resolved. Derived metrics (running/rank/OLAP) → DAX. Format strings applied. Display folders from MicroStrategy folder structure. |
| 6.4 | **Relationship generation** | `powerbi_import/tmdl_generator.py` | High | MicroStrategy attribute-to-fact relationships → TMDL relationships (manyToOne by default). Attribute-to-attribute parent-child → TMDL relationships. Cross-table joins from report definitions. Validate cardinality and cross-filtering. |
| 6.5 | **Hierarchy generation** | `powerbi_import/tmdl_generator.py` | Medium | MicroStrategy hierarchies → TMDL hierarchies with levels. System hierarchies (attribute-based drill paths) + user hierarchies. |
| 6.6 | **Calendar table generation** | `powerbi_import/tmdl_generator.py` | Low | Reuse existing Calendar table generator from Tableau tool. Auto-detect date columns and create relationships. |
| 6.7 | **RLS role generation** | `powerbi_import/tmdl_generator.py` | High | Security filters → TMDL `role` definitions with `tablePermission` and DAX filter expressions. Map `USERPRINCIPALNAME()` patterns. |
| 6.8 | **Tests** | `tests/test_tmdl_generation.py` | High | 80+ tests: table/column/measure generation, relationship mapping, hierarchy creation, RLS roles, calendar table, edge cases. |

---

#### Sprint 7 — Visual Generation (PBIR)

**Goal:** Convert MicroStrategy report grids/graphs and dossier visualizations to Power BI PBIR v4.0 visuals.

| # | Item | File(s) | Est. | Details |
|---|------|---------|------|---------|
| 7.1 | **Dossier → Report page mapping** | `powerbi_import/visual_generator.py` | High | Dossier chapter → PBI report page group. Dossier page → PBI report page. Panel stack → visual group with toggle. Layout: dossier absolute positioning → PBI canvas positioning (scale to 1280×720 or 16:9). |
| 7.2 | **Grid visualization → Table/Matrix** | `powerbi_import/visual_generator.py` | High | MicroStrategy grid → PBI `tableEx` or `matrix`. Row attributes → rows well. Column attributes → columns well. Metrics → values well. Page-by → slicer on same page. Subtotals → matrix subtotals. |
| 7.3 | **Graph visualization → Charts** | `powerbi_import/visual_generator.py` | High | 30+ graph type mappings: VerticalBar→clusteredColumnChart, HorizontalBar→clusteredBarChart, Line→lineChart, Pie→pieChart, Ring→donutChart, Scatter→scatterChart, Bubble→scatterChart, Area→areaChart, Radar→custom, Gauge→gauge, Waterfall→waterfall, BoxPlot→custom, Histogram→clusteredColumnChart. Combo charts. |
| 7.4 | **Filter panel → Slicers** | `powerbi_import/visual_generator.py` | Medium | Dossier filter panels → PBI slicers. Attribute element list → dropdown/list slicer. Metric range → between slicer. Date filter → date range slicer. Multi-select behavior preserved. |
| 7.5 | **Threshold → Conditional formatting** | `powerbi_import/visual_generator.py` | Medium | MicroStrategy thresholds → PBI conditional formatting rules: background color, font color, icon sets, data bars. Condition operators mapped. |
| 7.6 | **Prompt → Parameter/Slicer** | `powerbi_import/visual_generator.py` | High | Value prompt → What-if parameter or slicer. Object prompt → field parameter table. Hierarchy prompt → hierarchy slicer. Required/optional prompt behavior → slicer defaults. |
| 7.7 | **KPI/Gauge/Text visuals** | `powerbi_import/visual_generator.py` | Medium | KPI visualization → PBI `kpi` visual. Gauge → `gauge`. Text/Image/HTML panels → textbox/image visuals. URL actions → drillthrough or web URL. |
| 7.8 | **Tests** | `tests/test_visual_generation.py` | High | 60+ tests: page mapping, grid→table/matrix, graph type conversions, filter→slicer, threshold→formatting, prompt→parameter, layout positioning. |

---

#### Sprint 8 — Power Query M Generation

**Goal:** Generate Power Query M expressions for connecting to the original data warehouses.

| # | Item | File(s) | Est. | Details |
|---|------|---------|------|---------|
| 8.1 | **SQL Server connection** | `powerbi_import/m_query_generator.py` | Medium | Warehouse connection type MSSQL → `Sql.Database()` M expression. Schema + table name. Freeform SQL → `Value.NativeQuery()`. |
| 8.2 | **Oracle connection** | `powerbi_import/m_query_generator.py` | Medium | Oracle warehouse → `Oracle.Database()`. Handle TNS names and connection descriptors. |
| 8.3 | **PostgreSQL connection** | `powerbi_import/m_query_generator.py` | Medium | PostgreSQL → `PostgreSQL.Database()`. |
| 8.4 | **Teradata connection** | `powerbi_import/m_query_generator.py` | Medium | Teradata → `Teradata.Database()`. Common MicroStrategy warehouse. |
| 8.5 | **Snowflake / Databricks / BigQuery** | `powerbi_import/m_query_generator.py` | Medium | Cloud warehouses. `Snowflake.Databases()`, `Databricks.Catalogs()`, `GoogleBigQuery.Database()`. |
| 8.6 | **Generic ODBC/JDBC fallback** | `powerbi_import/m_query_generator.py` | Low | Unknown warehouse types → `Odbc.DataSource()` with DSN or connection string. Warning logged. |
| 8.7 | **Freeform SQL → Value.NativeQuery** | `powerbi_import/m_query_generator.py` | Medium | Freeform SQL tables → `Value.NativeQuery(source, "SELECT ...")`. Parameter substitution for prompted SQL. |
| 8.8 | **Tests** | `tests/test_m_query_generation.py` | Medium | 40+ tests: each connection type, freeform SQL, parameter injection, schema handling. |

---

#### Sprint 9 — .pbip Project Assembly & Migration Report

**Goal:** Assemble the full `.pbip` project and generate a comprehensive migration report.

| # | Item | File(s) | Est. | Details |
|---|------|---------|------|---------|
| 9.1 | **PBIP project generator** | `powerbi_import/pbip_generator.py` | High | Reuse/extend Tableau tool's generator: create `.pbip`, `.gitignore`, SemanticModel folder (`.platform`, `definition.pbism`, TMDL files), Report folder (PBIR v4.0 report.json, pages, visuals). |
| 9.2 | **Report assembly** | `powerbi_import/pbip_generator.py` | High | Wire visual definitions into PBIR report structure. Page ordering from dossier chapters. Visual layout with auto-sizing. Filter pane configuration. |
| 9.3 | **Migration report (JSON)** | `powerbi_import/migration_report.py` | Medium | Per-object fidelity tracking: fully migrated, approximated, manual review, unsupported. Counts: attributes, metrics, reports, dossiers, visuals, filters, prompts. |
| 9.4 | **Migration report (HTML)** | `powerbi_import/migration_report.py` | Medium | Visual HTML report with: summary dashboard, per-object status table, expression conversion details, manual review items, warnings. |
| 9.5 | **Assessment mode** | `powerbi_import/assessment.py` | Medium | `--assess` flag: analyze MicroStrategy project without generating output. Report: object counts, expression complexity scores, unsupported feature flags, estimated migration fidelity. |
| 9.6 | **Artifact validation** | `powerbi_import/validator.py` | Medium | Reuse/extend Tableau tool's validator: TMDL syntax check, PBIR schema validation, relationship cycle detection, DAX reference validation. |
| 9.7 | **Tests** | `tests/test_pbip_assembly.py`, `tests/test_migration_report.py` | Medium | 40+ tests: project structure, report assembly, fidelity tracking, HTML report, assessment mode, validation. |

---

#### Sprint 10 — Deployment & Fabric Integration

**Goal:** Deploy generated `.pbip` projects to Power BI Service and Microsoft Fabric.

| # | Item | File(s) | Est. | Details |
|---|------|---------|------|---------|
| 10.1 | **Power BI Service deployment** | `powerbi_import/deploy/pbi_deployer.py` | High | Reuse Tableau tool's deployer: Azure AD auth (Service Principal / Managed Identity), workspace upload via Power BI REST API, dataset refresh trigger. |
| 10.2 | **Fabric Lakehouse integration** | `powerbi_import/deploy/fabric_deployer.py` | High | Deploy semantic model to Fabric workspace. Configure DirectLake mode if source data is in OneLake. Lakehouse/Warehouse connection generation. |
| 10.3 | **Gateway configuration** | `powerbi_import/deploy/gateway_config.py` | Medium | Generate gateway connection config for on-premises warehouse connections (Oracle, Teradata, SQL Server, etc.). |
| 10.4 | **Batch migration** | `migrate.py` | Medium | `--batch` flag: migrate all reports/dossiers in a MicroStrategy project. Parallel extraction with thread pool. Batch summary report. |
| 10.5 | **Incremental/delta migration** | `migrate.py` | Medium | Track previously migrated objects. Only re-migrate changed objects (compare modification timestamps via REST API). |
| 10.6 | **Tests** | `tests/test_deployment.py` | Medium | 30+ tests: auth flows, workspace upload, Fabric deployment, gateway config, batch mode, incremental tracking. |

---

### Phase 3 — Hardening & Enterprise (Sprints 11-15)

#### Sprint 11 — Expression Converter Hardening

| # | Item | Details |
|---|------|---------|
| 11.1 | **Nested metric resolution** | Resolve metric-within-metric references: `Metric1 = Sum(Revenue)`, `Metric2 = Metric1 / Sum(Cost)` → inline or use DAX variables. |
| 11.2 | **Smart metric (OLAP functions)** | `RunningSum`, `RunningAvg`, `MovingAvg`, `Rank`, `NTile`, `FirstInRange`, `LastInRange` → DAX window functions (WINDOW, OFFSET, INDEX) or RANKX patterns. |
| 11.3 | **Transformation metrics** | `Band()`, `BandNames()`, `Banding()` → DAX `SWITCH(TRUE(), ...)` with range conditions. |
| 11.4 | **Passthrough SQL handling** | `ApplySimple` with database-specific SQL → best-effort DAX conversion. Flag complex SQL as manual review. Common patterns: `CASE WHEN`, `DECODE`, `NVL`, `COALESCE`, `CAST`, `EXTRACT`. |
| 11.5 | **Cross-table metric context** | Metrics spanning multiple tables with different attribute levels → `CALCULATE` with proper `ALLEXCEPT` / `REMOVEFILTERS` combinations. |

#### Sprint 12 — Dossier Advanced Features

| # | Item | Details |
|---|------|---------|
| 12.1 | **Panel stacks** | MicroStrategy panel stacks (tabbed containers) → PBI bookmark navigator or toggle buttons with show/hide bookmarks. |
| 12.2 | **Info windows** | Tooltip visualizations (viz-in-tooltip equivalent) → PBI tooltip pages. |
| 12.3 | **Selector controls** | Attribute element selector, metric selector → PBI slicers, field parameters. |
| 12.4 | **Transaction services** | Write-back grids → flag as unsupported (PBI doesn't support write-back natively). Log for Power Apps embedding alternative. |
| 12.5 | **URL actions & linking** | Dossier links between chapters/pages → PBI drillthrough actions or page navigation buttons. External URL actions preserved. |
| 12.6 | **Dossier themes** | Color palettes, font settings → PBI report theme JSON. |

#### Sprint 13 — Shared Semantic Model & Multi-Report Migration

| # | Item | Details |
|---|------|---------|
| 13.1 | **Project-level shared model** | MicroStrategy project schema (attributes/facts/metrics) → single shared Power BI semantic model. Multiple reports/dossiers → thin reports referencing the shared model. |
| 13.2 | **Report-to-thin-report conversion** | Each migrated report/dossier → thin report with `byPath` or `byConnection` binding to shared semantic model. |
| 13.3 | **Merge assessment** | Analyze all reports in a project: shared vs. unique metrics, attribute overlap, connection commonality. Score merge candidates. |
| 13.4 | **Fabric bundle deployment** | Deploy shared model + all thin reports as an atomic bundle to a Fabric workspace. |

#### Sprint 14 — Testing & Validation

| # | Item | Details |
|---|------|---------|
| 14.1 | **End-to-end integration tests** | Full pipeline tests with realistic MicroStrategy fixtures (mock REST API responses). |
| 14.2 | **Expression converter coverage** | Target 95%+ coverage on all MicroStrategy function mappings. |
| 14.3 | **Visual fidelity tests** | Compare generated PBIR visuals against expected output for each chart type. |
| 14.4 | **Regression test suite** | Snapshot-based tests for generated TMDL, M queries, PBIR visuals. |
| 14.5 | **Performance benchmarks** | Profile extraction + generation for large projects (1000+ objects). |

#### Sprint 15 — Documentation & Polish

| # | Item | Details |
|---|------|---------|
| 15.1 | **MSTR Expression → DAX reference** | Complete mapping document: every MicroStrategy function → DAX equivalent. |
| 15.2 | **MSTR → Power Query M reference** | Connection types, transforms, SQL passthrough mappings. |
| 15.3 | **Migration checklist** | Step-by-step guide for enterprise migrations: assessment → pilot → batch → validation → deployment. |
| 15.4 | **Known limitations** | Transparent documentation of unsupported features and approximations. |
| 15.5 | **FAQ** | Common questions, troubleshooting, workarounds. |
| 15.6 | **Architecture doc** | Pipeline description, module responsibilities, data flow. |

---

## MicroStrategy Object Type → Power BI Mapping Summary

| MicroStrategy Object | Power BI Equivalent | Conversion Approach |
|----------------------|--------------------|--------------------|
| **Attribute** | Column (dimension) | Direct mapping; forms → display/key columns |
| **Fact** | Implicit measure or column | Map to column + DAX measure |
| **Metric** | DAX Measure | Expression conversion |
| **Derived Metric** | DAX Measure (window/rank) | RANKX, WINDOW, VAR patterns |
| **Filter** | Report/page/visual filter | DAX filter expression |
| **Prompt** | Slicer / What-if Parameter | Type-dependent mapping |
| **Report (Grid)** | Table or Matrix visual | Grid layout → visual config |
| **Report (Graph)** | Chart visual | Type mapping (30+ types) |
| **Dossier** | Multi-page Report | Chapter→page group, page→page |
| **Dossier Visualization** | Visual | Type mapping + data binding |
| **Intelligent Cube** | Import mode table | Pre-aggregated data |
| **Custom Group** | Calculated column (SWITCH) | Element conditions → DAX |
| **Consolidation** | Calculated table/measure | Aggregation rules → DAX |
| **Security Filter** | RLS Role | DAX filter expression |
| **Hierarchy** | TMDL Hierarchy | Level ordering |
| **Threshold** | Conditional formatting | Color/icon rules |
| **Freeform SQL** | Value.NativeQuery() | SQL passthrough |
| **Document** (legacy) | Multi-page report | Best-effort layout |
| **Warehouse Connection** | Power Query M source | Connection string mapping |

---

## MicroStrategy Expression → DAX Function Mapping (Core)

| MicroStrategy | DAX | Category |
|---------------|-----|----------|
| `Sum(Fact)` | `SUM(Table[Column])` | Aggregation |
| `Avg(Fact)` | `AVERAGE(Table[Column])` | Aggregation |
| `Count(Attr)` | `COUNT(Table[Column])` | Aggregation |
| `Count(Distinct Attr)` | `DISTINCTCOUNT(Table[Column])` | Aggregation |
| `Min(Fact)` | `MIN(Table[Column])` | Aggregation |
| `Max(Fact)` | `MAX(Table[Column])` | Aggregation |
| `StDev(Fact)` | `STDEV.S(Table[Column])` | Statistics |
| `Median(Fact)` | `MEDIAN(Table[Column])` | Statistics |
| `Percentile(Fact, n)` | `PERCENTILEX.INC(Table, Table[Column], n)` | Statistics |
| `If(cond, a, b)` | `IF(cond, a, b)` | Logic |
| `Case/When` | `SWITCH(TRUE(), ...)` | Logic |
| `NullToZero(x)` | `IF(ISBLANK(x), 0, x)` | Null handling |
| `IsNull(x)` | `ISBLANK(x)` | Null handling |
| `Concat(a, b)` | `CONCATENATE(a, b)` | String |
| `Length(s)` | `LEN(s)` | String |
| `SubStr(s, i, n)` | `MID(s, i, n)` | String |
| `Trim(s)` | `TRIM(s)` | String |
| `Upper(s)` / `Lower(s)` | `UPPER(s)` / `LOWER(s)` | String |
| `CurrentDate()` | `TODAY()` | Date |
| `CurrentDateTime()` | `NOW()` | Date |
| `Year(d)` / `Month(d)` / `Day(d)` | `YEAR(d)` / `MONTH(d)` / `DAY(d)` | Date |
| `DaysBetween(a, b)` | `DATEDIFF(a, b, DAY)` | Date |
| `MonthsBetween(a, b)` | `DATEDIFF(a, b, MONTH)` | Date |
| `DateAdd(d, n, unit)` | `DATEADD(Table[Date], n, unit)` | Date |
| `Power(x, n)` | `POWER(x, n)` | Math |
| `Abs(x)` | `ABS(x)` | Math |
| `Round(x, n)` | `ROUND(x, n)` | Math |
| `Ceiling(x)` | `CEILING(x, 1)` | Math |
| `Floor(x)` | `FLOOR(x, 1)` | Math |
| `Ln(x)` / `Log(x)` | `LN(x)` / `LOG(x)` | Math |
| `Exp(x)` | `EXP(x)` | Math |
| `Rank(metric) {attr}` | `RANKX(ALL(Table), [Metric])` | Analytics |
| `RunningSum(metric) {attr}` | `WINDOW(Table, ...)` or VAR pattern | Analytics |
| `RunningAvg(metric) {attr}` | `WINDOW(Table, ...)` or VAR pattern | Analytics |
| `MovingAvg(metric, n) {attr}` | `WINDOW` or `AVERAGEX(TOPN(...))` | Analytics |
| `Lag(metric, n)` | `OFFSET(Table, -n, ...)` | Analytics |
| `Lead(metric, n)` | `OFFSET(Table, n, ...)` | Analytics |
| `NTile(metric, n)` | `NTILE pattern with RANKX` | Analytics |
| `ApplySimple("SQL", args)` | Manual review / best-effort DAX | Passthrough |
| `Sum(Fact) {~+, Attr}` | `CALCULATE([Measure], ALLEXCEPT(T, T[Col]))` | Level metric |
| `Sum(Fact) {!Attr}` | `CALCULATE([Measure], REMOVEFILTERS(T[Col]))` | Level metric |
| `Sum(Fact) {^}` | `CALCULATE([Measure], ALL(Table))` | Level metric |
| `Band(Metric, n)` | `SWITCH(TRUE(), [M]>=v1, ..., ...)` | Banding |

---

## Visualization Type Mapping

| MicroStrategy Viz | Power BI Visual | Notes |
|-------------------|-----------------|-------|
| Grid | tableEx | Rows/columns/values |
| Cross-tab | matrix | Row/column/value wells |
| Vertical Bar | clusteredColumnChart | |
| Stacked Vertical Bar | stackedColumnChart | |
| Horizontal Bar | clusteredBarChart | |
| Stacked Horizontal Bar | stackedBarChart | |
| Line | lineChart | |
| Area | areaChart | |
| Pie | pieChart | |
| Ring/Donut | donutChart | |
| Scatter | scatterChart | |
| Bubble | scatterChart | Size encoding |
| Combo (Bar+Line) | lineClusteredColumnComboChart | |
| Map (point) | map | |
| Map (area/filled) | filledMap | |
| Treemap | treemap | |
| Heat Map | matrix | Conditional formatting |
| Waterfall | waterfall | |
| Funnel | funnel | |
| Box Plot | Custom visual | |
| Gauge | gauge | |
| KPI | kpi | |
| Word Cloud | wordCloud (AppSource) | |
| Network / Sankey | Custom visual (AppSource) | |
| Histogram | clusteredColumnChart | Binned axis |
| Bullet | Custom visual | |
| Panel Stack | Bookmarks + toggle | |
| Info Window | Tooltip page | |
| Text/Image | textbox / image | |
| HTML Container | textbox (warning) | HTML not supported |
| Filter Panel | Slicer(s) | One slicer per filter |
| Selector Control | Slicer / field parameter | |

---

## Reusable Modules from Tableau Tool

These modules from `TableauToPowerBI/powerbi_import/` can be reused directly or with minor adaptation:

| Module | Reuse Level | Changes Needed |
|--------|-------------|----------------|
| `pbip_generator.py` | High (80%) | Swap Tableau-specific field names for MSTR equivalents |
| `tmdl_generator.py` | Medium (60%) | Major: new schema model (attributes/facts vs. datasource columns) |
| `visual_generator.py` | Medium (60%) | New viz type mapping, MSTR-specific layout |
| `m_query_generator.py` | High (80%) | Add Teradata/Netezza connectors, reuse rest |
| `validator.py` | High (90%) | Reuse relationship/DAX validation as-is |
| `deploy/` | High (95%) | Reuse deployment pipeline almost entirely |
| `migration_report.py` | Medium (70%) | New object types, MSTR-specific categories |
| `assessment.py` | Medium (60%) | New assessment criteria for MSTR objects |
| `shared_model.py` | Medium (50%) | New merge logic for MSTR schema objects |

---

## Milestones

| Milestone | Sprints | Target | Deliverable |
|-----------|---------|--------|-------------|
| **M1 — Proof of Concept** | 1-3 | Sprint 3 | Extracts MSTR schema + converts basic metrics to DAX |
| **M2 — Single Report** | 4-6 | Sprint 6 | Migrates one report/dossier → .pbip (opens in PBI Desktop) |
| **M3 — Full Pipeline** | 7-9 | Sprint 9 | Complete extraction + generation + report + assessment |
| **M4 — Enterprise Ready** | 10-13 | Sprint 13 | Deployment, shared models, batch, security |
| **M5 — Production** | 14-15 | Sprint 15 | Hardened, documented, tested (target: 2000+ tests) |

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| MicroStrategy REST API rate limits | Slow extraction for large projects | Implement caching, batch API calls, pagination |
| Expression conversion gaps | Low fidelity for complex metrics | Flag unsupported patterns, provide manual review guide |
| Dossier layout complexity | Visual positioning differences | Best-effort layout with manual adjustment guide |
| API version differences (10.x vs 11.x vs 2021+) | Missing endpoints | Version detection + fallback paths |
| Large project scale (10,000+ objects) | Memory/time constraints | Streaming extraction, parallel processing |
| ApplySimple SQL diversity | Database-specific SQL not convertible | Classify common patterns, fallback to NativeQuery |
