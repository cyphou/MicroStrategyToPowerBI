# Development Plan — MicroStrategy to Power BI / Fabric Migration Tool

**Version:** v3.0.0 (released) → v4.0–v14.0 (roadmap)  
**Date:** 2026-03-20  
**Based on:** Tableau to Power BI Migration Tool (v17.0.0 architecture)  
**Current state:** v3.0 complete — 623 tests passing, 21 generation modules  
**Long-term target:** v14.0 — full enterprise ecosystem, 5,000+ tests, web portal

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

| Milestone | Sprints | Target | Deliverable | Status |
|-----------|---------|--------|-------------|--------|
| **M1 — Proof of Concept** | 1-3 | Sprint 3 | Extracts MSTR schema + converts basic metrics to DAX | ✅ v1.0 |
| **M2 — Single Report** | 4-6 | Sprint 6 | Migrates one report/dossier → .pbip (opens in PBI Desktop) | ✅ v1.0 |
| **M3 — Full Pipeline** | 7-9 | Sprint 9 | Complete extraction + generation + report + assessment | ✅ v1.0 |
| **M4 — Enterprise Ready** | 10-13 | Sprint 13 | Deployment, shared models, batch, security | ✅ v1.0 |
| **M5 — Production Tooling** | F-L | v2.0 | CI/CD, wizard, DAX depth, parallel, incremental, dashboard | ✅ v2.0 |
| **M6 — Enterprise Assessment** | F-K | v3.0 | 14-category assessment, strategy, comparison, telemetry, plugins | ✅ v3.0 |
| **M7 — Production Maturity** | L-Q | v4.0 | OLAP hardening, merge consolidation, scale, scorecard→goals, 1000+ tests | 🔜 v4.0 |

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

---
---

# v4.0 Development Plan — Production Maturity

**Target:** v4.0.0  
**Theme:** OLAP hardening, merge consolidation, scale optimization, scorecard→goals, 1,000+ tests  
**Prerequisite:** v3.0.0 complete (623 tests, 21 generation modules)

---

## Phase 4 — Production Maturity (Sprints L–Q)

### Sprint L — OLAP Metric Hardening ✨CRITICAL

**Goal:** Raise derived metric (OLAP) fidelity from ~80% (approximated) to ~98% (full DAX). This is the #1 gap identified by v3.0 assessments.

| # | Item | File(s) | Est. | Details |
|---|------|---------|------|---------|
| L.1 | **RunningSum → DAX WINDOW** | `expression_converter.py` | High | Replace placeholder VAR pattern with proper `WINDOW(1, ABS, 0, REL, ...)` for accurate running totals. Handle multi-attribute sort keys. |
| L.2 | **RunningAvg → DAX WINDOW** | `expression_converter.py` | High | `WINDOW` with averaging over expanding range. Handle partition-by attributes. |
| L.3 | **MovingAvg → OFFSET range** | `expression_converter.py` | High | `MovingAvg(Metric, N)` → `AVERAGEX(OFFSET(..., -N+1, ..., N), [Metric])`. Handle edge cases: window at start, null handling. |
| L.4 | **Rank with ties** | `expression_converter.py` | Medium | `Rank` with `{attr}` → `RANKX(ALL(T), [M], , ASC, DENSE)`. Support ASC/DESC, DENSE/SKIP tie handling. |
| L.5 | **NTile partitioning** | `expression_converter.py` | Medium | `NTile(Metric, N) {Attr}` → RANKX-based quartile/decile pattern with `CEILING(DIVIDE(RANKX(...), COUNTROWS(...)) * N)`. |
| L.6 | **FirstInRange / LastInRange** | `expression_converter.py` | Medium | `FirstInRange(Metric) {Attr}` → `CALCULATE([M], TOPN(1, ALL(T), T[SortCol], ASC))`. |
| L.7 | **Nested OLAP metrics** | `expression_converter.py` | Very High | `Rank(RunningSum(Revenue))` → resolved inner-to-outer. Use DAX variables for intermediate results. Detect circular references. |
| L.8 | **ApplyOLAP passthrough** | `expression_converter.py` | High | Parse `ApplyOLAP("function", args)` → attempt DAX conversion. Common: `LAG`, `LEAD`, `ROW_NUMBER`, `DENSE_RANK`, `SUM OVER (PARTITION BY ... ORDER BY ...)`. |
| L.9 | **OLAP fidelity tests** | `tests/test_olap_metrics.py` | High | 60+ parametrized tests: every OLAP function × simple/nested/partitioned × edge cases. Target: 98% fidelity on test corpus. |

**Success criteria:** Running `--assess` on a complex MSTR project shows <2% metrics flagged as `manual_review` (was ~5-10%).

---

### Sprint M — Merge & Consolidation Tools

**Goal:** Enable multi-project migrations where many MSTR projects share schema objects. Consolidate into minimal shared semantic models.

| # | Item | File(s) | Est. | Details |
|---|------|---------|------|---------|
| M.1 | **Merge assessment** | `powerbi_import/merge_assessment.py` | High | Analyze N projects: common attributes, shared facts, overlapping metrics. Score merge candidates. Output: JSON report with overlap matrix, recommended groupings. |
| M.2 | **Merge configuration** | `powerbi_import/merge_config.py` | Medium | User-editable JSON config: which projects merge, field name normalizations, conflict resolution rules (rename, alias, drop). |
| M.3 | **Multi-project merge execution** | `powerbi_import/shared_model.py` | Very High | Extend `shared_model.py`: accept N intermediate JSON sets → deduplicate attributes/facts/metrics → generate one consolidated TMDL model. Handle column name collisions. |
| M.4 | **Merge impact report** | `powerbi_import/merge_report_html.py` | Medium | HTML report: merged vs. not-merged objects, naming conflicts resolved, thin report bindings per project. Visual overlap heatmap. |
| M.5 | **Thin report per source project** | `powerbi_import/thin_report_generator.py` | Medium | Extend: each source dossier/report → thin report bound to merged model. Validate all bindings resolve. |
| M.6 | **CLI: `--merge DIR`** | `migrate.py` | Low | `--merge ./projects/` → scan all subdirectories as separate migrations → merge into consolidated output. |
| M.7 | **Tests** | `tests/test_merge.py` | High | 40+ tests: overlap detection, conflict resolution, merged TMDL correctness, thin report bindings, edge cases (empty projects, no overlap). |

---

### Sprint N — Advanced Dossier Features

**Goal:** Close the dossier layout fidelity gap. Handle panel stacks, nested selectors, info windows, and theme CSS.

| # | Item | File(s) | Est. | Details |
|---|------|---------|------|---------|
| N.1 | **Deep panel stacks** | `visual_generator.py` | High | Nested panel stacks (tabs within tabs) → PBI bookmark groups with toggle buttons. Auto-generate bookmark definitions + button visuals. |
| N.2 | **Info windows → Tooltip pages** | `visual_generator.py` | Medium | MSTR info windows → PBI tooltip report pages. Map viz-in-tooltip content to tooltip-sized page (320×240). |
| N.3 | **Selector controls → Field parameters** | `visual_generator.py`, `tmdl_generator.py` | High | Attribute/metric selectors → PBI field parameter tables with `NAMEOF()` DAX. Generate parameter table TMDL + slicer visual. |
| N.4 | **URL actions → Drillthrough** | `visual_generator.py` | Medium | MSTR URL link actions → PBI drillthrough pages or web URL buttons. Preserve target parameters. |
| N.5 | **Dossier themes → Report theme JSON** | `powerbi_import/theme_generator.py` | Medium | Extract MSTR color palettes, font settings → PBI `reportTheme.json`. Map primary/secondary/accent colors. |
| N.6 | **Layout pixel accuracy** | `visual_generator.py` | High | Improve proportional scaling: use MSTR canvas dimensions directly, apply aspect-ratio-preserving layout. Handle multi-chapter page sizes. |
| N.7 | **Tests** | `tests/test_dossier_advanced.py` | Medium | 30+ tests: panel stacks (nested), tooltips, selectors, themes, layout accuracy, URL actions. |

---

### Sprint O — Scorecard → Power BI Goals

**Goal:** Migrate MicroStrategy scorecards (KPIs, targets, statuses) to Power BI Goals API. New extraction + generation modules.

| # | Item | File(s) | Est. | Details |
|---|------|---------|------|---------|
| O.1 | **Scorecard extraction** | `microstrategy_export/scorecard_extractor.py` | High | `GET /api/v2/documents/{id}` for scorecard documents. Extract: KPI name, current value metric, target metric, status thresholds (on-track/at-risk/behind), owner, time period, initiative links. Map to `scorecards.json`. |
| O.2 | **Goals generation** | `powerbi_import/goals_generator.py` | High | Convert scorecards → Power BI Goals API payload: `POST /v1.0/myorg/groups/{groupId}/scorecards`. Map: KPI→goal, target→goal target, status→goal status rules, owner→goal owner. |
| O.3 | **Scorecard visual fallback** | `powerbi_import/visual_generator.py` | Medium | When Goals API not available: scorecard → PBI KPI/card visuals with conditional formatting matching status thresholds. |
| O.4 | **CLI: `--scorecards`** | `migrate.py` | Low | Flag to include scorecard extraction + goals generation. Requires Power BI REST API permissions. |
| O.5 | **Tests** | `tests/test_scorecard.py` | Medium | 20+ tests: scorecard extraction, goals payload generation, status threshold mapping, visual fallback. |

---

### Sprint P — Scale & Performance Optimization

**Goal:** Validate and optimize for large MSTR projects (1,000–10,000+ objects). Add benchmarking suite.

| # | Item | File(s) | Est. | Details |
|---|------|---------|------|---------|
| P.1 | **Large fixture generation** | `tests/fixtures/large/` | Medium | Script to generate synthetic MSTR API fixtures: 500 attributes, 1,000 metrics, 100 reports, 50 dossiers. Parametrized scale factor. |
| P.2 | **Memory profiling** | `tests/test_scale.py` | Medium | `tracemalloc` peak memory tests: extraction <500 MB for 10K objects, generation <200 MB. Fail if thresholds exceeded. |
| P.3 | **Streaming generation** | `powerbi_import/tmdl_generator.py`, `visual_generator.py` | High | Stream TMDL output file-by-file instead of building full model in memory. Yield-based generation for pages/visuals. |
| P.4 | **Parallel generation** | `microstrategy_export/parallel.py` | Medium | Extend parallel generation: each report/dossier → separate thread. Shared model lock for merge operations. |
| P.5 | **Benchmark suite** | `tests/benchmarks/` | Medium | `pytest-benchmark` markers: extraction throughput (objects/sec), generation throughput (files/sec), expression conversion rate. Track over time. |
| P.6 | **CI benchmark gates** | `.github/workflows/ci.yml` | Low | Benchmark comparison in CI: fail if throughput drops >20% from baseline. |
| P.7 | **Tests** | `tests/test_scale.py` | High | 20+ tests: 1K/5K/10K object scale, memory bounds, parallel correctness, streaming vs. batch equivalence. |

---

### Sprint Q — E2E Regression & Certification

**Goal:** Build a comprehensive snapshot-based regression suite and migration certification framework.

| # | Item | File(s) | Est. | Details |
|---|------|---------|------|---------|
| Q.1 | **Snapshot expansion** | `tests/fixtures/expected_output/` | High | Expand from 4 snapshots to 20+: every TMDL table type, every visual JSON type, M query variants, full .pbip structure. Auto-update mechanism (`--snapshot-update`). |
| Q.2 | **Visual fidelity tests** | `tests/test_visual_fidelity.py` | High | For each of 30+ visual types: generate from fixture → compare JSON output against baseline. Detect unintended field/property changes. |
| Q.3 | **DAX equivalence tests** | `tests/test_dax_equivalence.py` | Very High | For top-50 expression patterns: generate DAX → evaluate against known values (using DAX.do API or tabular model). Verify numeric equivalence. |
| Q.4 | **Migration certification report** | `powerbi_import/certification.py` | Medium | Post-migration certification: run all validators + comparison + visual diff → produce YES/NO certification with detailed findings. Score ≥95% = auto-certified. |
| Q.5 | **Expert troubleshooting guide** | `docs/TROUBLESHOOTING.md` | Medium | Top-20 migration issues with root cause + fix. Generated from telemetry data patterns. |
| Q.6 | **Tests** | Multiple test files | High | 100+ new tests across snapshots, fidelity, DAX equivalence. **Target: 1,000+ total tests.** |

---

## v4.0 Summary

| Sprint | Theme | New Modules | New Tests | Priority |
|--------|-------|-------------|-----------|----------|
| **L** | OLAP Metric Hardening | — (extend `expression_converter.py`) | ~60 | ✨ CRITICAL |
| **M** | Merge & Consolidation | `merge_assessment.py`, `merge_config.py`, `merge_report_html.py` | ~40 | HIGH |
| **N** | Advanced Dossier Features | `theme_generator.py` | ~30 | MEDIUM |
| **O** | Scorecard → Goals | `scorecard_extractor.py`, `goals_generator.py` | ~20 | MEDIUM |
| **P** | Scale & Performance | `tests/benchmarks/`, `tests/fixtures/large/` | ~20 | HIGH |
| **Q** | E2E Regression & Certification | `certification.py`, `docs/TROUBLESHOOTING.md` | ~100 | HIGH |

**Totals:**
- **5 new modules** + 1 new doc + extensions to 6 existing modules
- **~270 new tests** → target: **~900 total** (623 + 270)
- **4 new CLI flags**: `--merge`, `--scorecards`, `--certify`, `--benchmark`
- **1,000+ test milestone** achievable with Sprint Q

---

## v4.0 Milestones

| Milestone | Sprint | Deliverable |
|-----------|--------|-------------|
| **M7a — OLAP Maturity** | L | 98% metric conversion fidelity (was ~90%) |
| **M7b — Multi-Project Merge** | M | N-project consolidation into shared models |
| **M7c — Visual Fidelity** | N | Panel stacks, tooltips, themes, layout accuracy |
| **M7d — Scorecard Migration** | O | MSTR scorecards → PBI Goals / KPI visuals |
| **M7e — Enterprise Scale** | P | Validated at 10K objects, <500 MB memory |
| **M7f — Certification** | Q | Auto-certification with 1,000+ regression tests |

---

## v4.0 Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| DAX WINDOW function complexity | OLAP conversion may produce incorrect results for edge cases | Extensive parametrized testing with known values; DAX equivalence validation |
| Multi-project merge conflicts | Attribute/metric name collisions across projects | User-configurable conflict resolution; merge preview report before execution |
| Scorecard API availability | Power BI Goals API may require Premium/PPU capacity | Dual-path: Goals API if available, KPI visuals as fallback |
| Scale testing infrastructure | Large fixtures slow CI pipeline | Separate benchmark CI job; scale tests only on demand (`--benchmark` marker) |
| Snapshot maintenance burden | 20+ snapshots need updating on any generation change | Auto-update flag; snapshot diff in PR review; minimal snapshot scope |
| MicroStrategy API version drift | MSTR 2024+ may introduce new endpoints | Version detection + graceful degradation; monitor REST API changelog |

---
---

# Long-Term Roadmap — v5.0 through v14.0

The following 10 phases define the path from **production maturity** (v4.0) to a **full enterprise migration ecosystem** (v14.0). Each phase is self-contained and delivers incremental value. Phases can be reordered based on customer demand.

```
v1–v3  Foundation & Assessment     ████████████████████ DONE
v4     Production Maturity         ████████████████████ DONE
v5     Fabric Native               ███████████████████ DONE
v6     Governance & Lineage        ██████████████████ DONE
v7     AI-Assisted Migration       █████████████████ DONE
v8     Multi-Language & i18n       ░░░░░░░░░░░░░░░
v9     Real-Time & Streaming       ░░░░░░░░░░░░░░
v10    Deep Testing & Quality      ██████████████ DONE
v11    Migration Ops (MigOps)      ░░░░░░░░░░░░
v12    Cross-Platform Federation   ░░░░░░░░░░░
v13    Self-Service Web Portal     ░░░░░░░░░░
v14    Enterprise Ecosystem        ░░░░░░░░░
```

---

## v5.0 — Fabric Native Integration ✅ COMPLETE

**Theme:** First-class Microsoft Fabric support — DirectLake auto-configuration, Lakehouse schema generation, notebook generation, Git integration.  
**Priority:** HIGH — Fabric is the strategic direction for Microsoft BI.  
**Status:** COMPLETE — 5 new modules, 45 new tests, 7 CLI flags.

### Sprint R — DirectLake & Lakehouse

| # | Item | File(s) | Est. | Details |
|---|------|---------|------|---------|
| R.1 | **DirectLake auto-switch** | `powerbi_import/tmdl_generator.py` | High | When `--strategy` recommends DirectLake: auto-generate TMDL with `mode: directLake`, Delta table references instead of M partitions. Detect Fabric workspace context. |
| R.2 | **Lakehouse schema generation** | `powerbi_import/lakehouse_generator.py` | Very High | Generate Fabric Lakehouse table definitions from MSTR schema: attribute/fact columns → Delta table DDL. Output Spark SQL `CREATE TABLE` scripts. |
| R.3 | **Data pipeline notebooks** | `powerbi_import/notebook_generator.py` | High | Generate Fabric Spark notebooks that ETL from MSTR warehouse → Lakehouse Delta tables. M query logic → PySpark equivalent. |
| R.4 | **Fabric Git integration** | `powerbi_import/deploy/fabric_git.py` | Medium | Push generated `.pbip` + TMDL directly to Fabric workspace Git repo. Auto-commit with migration metadata. |
| R.5 | **Shortcut generation** | `powerbi_import/lakehouse_generator.py` | Medium | When source data is already in OneLake/ADLS: generate Lakehouse shortcuts instead of ETL. Zero-copy references. |
| R.6 | **CLI: `--fabric-mode`** | `migrate.py` | Low | `--fabric-mode lakehouse\|warehouse\|shortcut` — controls Fabric output type. Default: auto-detect from strategy advisor. |
| R.7 | **Tests** | `tests/test_fabric.py` | High | 40+ tests: DirectLake TMDL, Lakehouse DDL, notebook generation, Git push, shortcut creation. |

### Sprint S — Fabric Deployment Pipeline

| # | Item | File(s) | Est. | Details |
|---|------|---------|------|---------|
| S.1 | **Fabric REST API deployer** | `powerbi_import/deploy/fabric_deployer.py` | High | Deploy via Fabric REST APIs: create items (semantic model, report, notebook, pipeline), configure connections, trigger refresh. |
| S.2 | **Data pipeline orchestration** | `powerbi_import/pipeline_generator.py` | High | Generate Fabric Data Factory pipelines: source → Lakehouse copy activity, refresh semantic model, send notification. JSON pipeline definition. |
| S.3 | **Environment configuration** | `powerbi_import/deploy/fabric_env.py` | Medium | Generate Fabric environment definitions: Spark pool config, library requirements, connection strings. |
| S.4 | **Capacity management** | `powerbi_import/deploy/fabric_deployer.py` | Medium | Pre-flight capacity check: verify Fabric capacity available, estimate CU consumption, warn if undersized. |
| S.5 | **Tests** | `tests/test_fabric_deploy.py` | Medium | 30+ tests: API deployment, pipeline generation, environment config, capacity checks. |

**v5.0 totals:** 2 sprints, ~4 new modules, ~70 new tests, 2 new CLI flags

---

## v6.0 — Governance & Lineage ✅ COMPLETE

**Theme:** Data lineage tracking, impact analysis, governance metadata, Microsoft Purview integration.  
**Priority:** HIGH — critical for regulated industries and enterprise compliance.  
**Status:** COMPLETE — 4 new modules, 68 new tests, 3 CLI flags.

### Sprint T — Lineage Graph

| # | Item | File(s) | Est. | Details |
|---|------|---------|------|---------|
| T.1 | **Lineage model** | `powerbi_import/lineage.py` | High | Build in-memory DAG: warehouse table → MSTR attribute/fact → MSTR metric → MSTR report/dossier → PBI table → PBI measure → PBI visual. Node/edge model with metadata. |
| T.2 | **Impact analysis** | `powerbi_import/lineage.py` | High | "What breaks if I change column X?" — traverse DAG upstream/downstream. Output: affected measures, visuals, reports. |
| T.3 | **Lineage HTML report** | `powerbi_import/lineage_report.py` | Medium | Interactive HTML lineage visualization: D3.js force-directed graph or Sankey diagram. Filterable by layer (source → model → visual). |
| T.4 | **Lineage JSON export** | `powerbi_import/lineage.py` | Low | Export lineage as JSON-LD / OpenLineage format for integration with external catalogs. |
| T.5 | **Tests** | `tests/test_lineage.py` | High | 40+ tests: DAG construction, impact traversal, cycle detection, multi-hop lineage, JSON export. |

### Sprint U — Purview & Governance

| # | Item | File(s) | Est. | Details |
|---|------|---------|------|---------|
| U.1 | **Purview asset registration** | `powerbi_import/purview_integration.py` | High | Register migrated assets in Microsoft Purview: semantic model, tables, columns, measures with lineage edges. Apache Atlas API format. |
| U.2 | **Data classification mapping** | `powerbi_import/purview_integration.py` | Medium | Map MSTR security filter attributes to Purview sensitivity labels. Propagate classifications to PBI columns. |
| U.3 | **Governance report** | `powerbi_import/governance_report.py` | Medium | Pre-migration governance checklist: data ownership mapping, sensitivity classification coverage, RLS completeness, lineage gaps. HTML output. |
| U.4 | **CLI: `--lineage`, `--purview`** | `migrate.py` | Low | `--lineage` generates lineage report. `--purview ACCOUNT` registers assets in Purview. |
| U.5 | **Tests** | `tests/test_governance.py` | Medium | 30+ tests: Purview payload, classification mapping, governance report, lineage integration. |

**v6.0 totals:** 2 sprints, ~4 new modules, ~70 new tests, 2 new CLI flags

---

## v7.0 — AI-Assisted Migration ✅ COMPLETE

**Theme:** LLM-powered conversion for complex expressions, auto-fix for manual review items, semantic field matching.  
**Priority:** HIGH — addresses the #1 remaining fidelity gap (complex ApplySimple SQL).  
**Status:** COMPLETE — 2 new modules, 74 new tests, 5 CLI flags.

### Sprint V — LLM Expression Converter

| # | Item | File(s) | Est. | Details |
|---|------|---------|------|---------|
| V.1 | **LLM fallback converter** | `powerbi_import/ai_converter.py` | Very High | When rule-based converter returns `manual_review`: send expression to Azure OpenAI (GPT-4o) with DAX context prompt. Parse response. Validate generated DAX syntax. Confidence scoring. |
| V.2 | **Prompt engineering** | `powerbi_import/ai_converter.py` | High | Curated few-shot prompt: 50 MSTR→DAX examples covering all ApplySimple/ApplyAgg/ApplyOLAP patterns. System prompt with DAX grammar rules. |
| V.3 | **Human-in-the-loop review** | `powerbi_import/ai_converter.py` | Medium | LLM-generated DAX marked with `[AI-ASSISTED]` annotation in TMDL. Interactive mode: show suggestion, user accepts/edits/rejects. |
| V.4 | **Cost control** | `powerbi_import/ai_converter.py` | Medium | Token budget per migration run. Cache LLM responses for identical patterns. Batch similar expressions. Offline mode with cached translations. |
| V.5 | **CLI: `--ai-assist`** | `migrate.py` | Low | `--ai-assist` enables LLM fallback. `--ai-endpoint URL` for custom Azure OpenAI instance. `--ai-budget N` token limit. |
| V.6 | **Tests** | `tests/test_ai_converter.py` | High | 30+ tests: mock LLM responses, DAX validation, confidence scoring, budget enforcement, cache behavior. |

### Sprint W — Semantic Field Matching

| # | Item | File(s) | Est. | Details |
|---|------|---------|------|---------|
| W.1 | **Column name normalizer** | `powerbi_import/semantic_matcher.py` | High | Fuzzy matching for MSTR attribute names → PBI column names across merge scenarios. Levenshtein distance + embedding similarity. Handle abbreviations (CUST→Customer, QTY→Quantity). |
| W.2 | **Auto-fix suggestions** | `powerbi_import/semantic_matcher.py` | Medium | For each `manual_review` item: suggest top-3 fixes ranked by confidence. Show diff preview. |
| W.3 | **Learning from corrections** | `powerbi_import/semantic_matcher.py` | Medium | Store user corrections in local DB. Over time, build project-specific mapping dictionary. Apply learned mappings automatically in future runs. |
| W.4 | **Tests** | `tests/test_semantic_matcher.py` | Medium | 25+ tests: fuzzy matching, abbreviation handling, learned corrections, confidence ranking. |

**v7.0 totals:** 2 sprints, ~2 new modules, ~55 new tests, 3 new CLI flags

---

## v8.0 — Multi-Language & Localization

**Theme:** Internationalization support — multi-culture TMDL, translated captions, RTL layouts, locale-aware formatting.  
**Priority:** MEDIUM — needed for global enterprise deployments.

### Sprint X — i18n Infrastructure

| # | Item | File(s) | Est. | Details |
|---|------|---------|------|---------|
| X.1 | **Culture extraction** | `microstrategy_export/extract_mstr_data.py` | Medium | Extract MSTR project language settings, translated object names, locale-specific format strings. Map to `cultures.json`. |
| X.2 | **Multi-culture TMDL** | `powerbi_import/tmdl_generator.py` | High | Generate TMDL `culture` sections: `linguisticMetadata`, translated captions for tables/columns/measures per locale (en-US, fr-FR, de-DE, ja-JP, zh-CN, etc.). |
| X.3 | **Locale-aware format strings** | `powerbi_import/tmdl_generator.py` | Medium | Map MSTR locale-specific number/date/currency formats → TMDL formatString per culture. Handle non-Latin separators (1.000,50 vs 1,000.50). |
| X.4 | **RTL layout support** | `powerbi_import/visual_generator.py` | Medium | For Arabic/Hebrew locales: mirror visual positioning (right-to-left). Set `textDirection: rtl` in PBIR visuals. |
| X.5 | **CLI: `--cultures`** | `migrate.py` | Low | `--cultures en-US,fr-FR,de-DE` — specify target cultures. Default: extract from MSTR project. |
| X.6 | **Tests** | `tests/test_i18n.py` | Medium | 30+ tests: culture extraction, multi-locale TMDL, format string mapping, RTL layout, Unicode handling. |

**v8.0 totals:** 1 sprint, extensions to existing modules, ~30 new tests, 1 CLI flag

---

## v9.0 — Real-Time & Streaming

**Theme:** Migrate real-time MicroStrategy dashboards to Power BI push datasets, streaming dataflows, and real-time intelligence.  
**Priority:** MEDIUM — increasing demand with IoT and operational analytics.

### Sprint Y — Streaming Migration

| # | Item | File(s) | Est. | Details |
|---|------|---------|------|---------|
| Y.1 | **Real-time source detection** | `microstrategy_export/realtime_extractor.py` | High | Detect MSTR real-time dashboards: auto-refresh intervals, cache policies, subscription-based data. Classify as batch vs. near-real-time vs. streaming. |
| Y.2 | **Push dataset generation** | `powerbi_import/streaming_generator.py` | High | Generate Power BI push dataset definitions (REST API schema). Map MSTR auto-refresh metrics → push dataset tables. Define retention policy. |
| Y.3 | **Eventstream integration** | `powerbi_import/streaming_generator.py` | Very High | For Fabric Real-Time Intelligence: generate Eventstream definitions mapping MSTR data sources → KQL database → semantic model. |
| Y.4 | **Refresh schedule migration** | `powerbi_import/deploy/refresh_config.py` | Medium | Map MSTR cache/subscription schedules → PBI dataset refresh schedules. Generate refresh configuration JSON. |
| Y.5 | **CLI: `--realtime`** | `migrate.py` | Low | `--realtime` flag to enable real-time source detection and streaming output generation. |
| Y.6 | **Tests** | `tests/test_streaming.py` | Medium | 25+ tests: source detection, push dataset schema, Eventstream definition, refresh config. |

**v9.0 totals:** 1 sprint, ~2 new modules, ~25 new tests, 1 CLI flag

---

## v10.0 — Deep Testing & Quality ✅ COMPLETE

**Theme:** Reach 2,000+ tests with property-based testing, mutation testing, fuzzing, and automated visual screenshot comparison.  
**Priority:** HIGH — bridges the gap to Tableau reference project (4,219 tests).  
**Status:** COMPLETE — 5 new test files, 1 test generation script, 1,188 new tests (→ 2,073 total).

### Sprint Z — Advanced Testing Infrastructure

| # | Item | File(s) | Est. | Details |
|---|------|---------|------|---------|
| Z.1 | **Property-based testing** | `tests/test_properties.py` | High | Hypothesis strategies for MSTR expressions → DAX: any valid MSTR expression produces syntactically valid DAX. Any intermediate JSON → valid .pbip. |
| Z.2 | **Mutation testing** | `mutmut.toml` | Medium | `mutmut` configuration for expression converter and TMDL generator. Target: >80% mutation kill rate. CI gate on mutation score. |
| Z.3 | **Fuzz testing** | `tests/test_fuzz.py` | High | Fuzz expression converter with random/malformed MSTR expressions. Verify: never crashes, always returns valid output or explicit error. |
| Z.4 | **Visual screenshot comparison** | `tests/test_visual_screenshots.py` | Very High | Headless PBI Desktop (via Playwright): open generated .pbip → screenshot each page → pixel-diff against baseline. Flag >5% pixel difference. |
| Z.5 | **Test generation from telemetry** | `scripts/generate_tests.py` | Medium | Analyze telemetry data from real migrations: extract common expression patterns → auto-generate parametrized test cases. |
| Z.6 | **Coverage enforcement** | `.github/workflows/ci.yml` | Low | CI gate: ≥85% line coverage overall, ≥98% for expression_converter.py. `--cov-fail-under` in pytest. |
| Z.7 | **Tests** | Multiple files | Very High | 500+ new tests: property-based (~100), fuzz (~50), screenshot (~30), generated (~200), gap-filling (~120). **Target: 2,000+ total.** |

**v10.0 totals:** 1 sprint, ~2 new scripts, ~500 new tests (→ 2,000+ total)

---

## v11.0 — Migration Ops (MigOps)

**Theme:** Continuous migration pipeline — change detection on MSTR server, auto-reconciliation, drift monitoring, scheduled re-migration.  
**Priority:** MEDIUM — needed for phased multi-month enterprise migrations.

### Sprint AA — Change Detection

| # | Item | File(s) | Est. | Details |
|---|------|---------|------|---------|
| AA.1 | **MSTR change feed** | `microstrategy_export/change_detector.py` | High | Poll MSTR REST API for modified objects since last migration run (compare `modifiedDate`). Output change manifest: added/modified/deleted objects. |
| AA.2 | **Drift report** | `powerbi_import/drift_report.py` | High | Compare current PBI .pbip output against last migration: detect manual edits in PBI that would be overwritten. Generate conflict report. |
| AA.3 | **Auto-reconciliation** | `powerbi_import/reconciler.py` | Very High | Three-way merge: MSTR source (new) × PBI target (current) × PBI target (last migration). Preserve manual PBI customizations while applying MSTR changes. |
| AA.4 | **Scheduled migration** | `scripts/scheduled_migration.py` | Medium | Cron-compatible script: poll → detect changes → migrate → validate → deploy → notify. Configurable via `migration_schedule.json`. |
| AA.5 | **CLI: `--watch`, `--reconcile`** | `migrate.py` | Low | `--watch` enters polling mode. `--reconcile` generates drift report without migrating. |
| AA.6 | **Tests** | `tests/test_migops.py` | High | 40+ tests: change detection, drift calculation, three-way merge, scheduled pipeline. |

**v11.0 totals:** 1 sprint, ~3 new modules + 1 script, ~40 new tests, 2 CLI flags

---

## v12.0 — Cross-Platform Federation

**Theme:** Unified migration from multiple BI platforms (MicroStrategy + Tableau + Cognos + SSRS) into Power BI. Shared intermediate format.  
**Priority:** LOW — strategic differentiator for large enterprises with mixed BI estates.

### Sprint BB — Universal Intermediate Format

| # | Item | File(s) | Est. | Details |
|---|------|---------|------|---------|
| BB.1 | **Universal BI schema** | `universal_bi/schema.py` | Very High | Platform-agnostic intermediate JSON schema: `datasources`, `dimensions`, `measures`, `calculations`, `visualizations`, `pages`, `security`. Superset of MSTR + Tableau + Cognos concepts. |
| BB.2 | **MSTR → Universal adapter** | `universal_bi/adapters/mstr_adapter.py` | High | Convert existing 18 MSTR intermediate JSONs → Universal BI schema. 1:1 mapping for most objects; translate MSTR-specific concepts (level metrics, Apply functions). |
| BB.3 | **Tableau → Universal adapter** | `universal_bi/adapters/tableau_adapter.py` | High | Convert Tableau intermediate JSONs (from TableauToPowerBI project) → Universal BI schema. Reuse existing Tableau extraction. |
| BB.4 | **Cross-source lineage** | `universal_bi/cross_lineage.py` | High | When merging from MSTR + Tableau: detect shared data sources, overlapping dimensions, equivalent measures. Build cross-platform lineage graph. |
| BB.5 | **Unified generation** | `powerbi_import/` | Medium | Extend generation layer to accept Universal BI schema instead of MSTR-specific JSON. Backward-compatible: auto-detect input format. |
| BB.6 | **CLI: `--from-tableau`, `--from-cognos`** | `migrate.py` | Medium | Accept mixed inputs: `--from-export ./mstr/ --from-tableau ./tableau/ --merge` → unified PBI output. |
| BB.7 | **Tests** | `tests/test_federation.py` | High | 50+ tests: schema translation, cross-platform merge, lineage, unified generation. |

**v12.0 totals:** 1 sprint, ~4 new modules (new package), ~50 new tests, 2 CLI flags

---

## v13.0 — Self-Service Web Portal

**Theme:** Web-based migration portal for non-technical users — upload MSTR exports, configure migration, track progress, approve results.  
**Priority:** MEDIUM — accelerates adoption in large organizations.

### Sprint CC — Web Application

| # | Item | File(s) | Est. | Details |
|---|------|---------|------|---------|
| CC.1 | **FastAPI backend** | `web/app.py`, `web/api/` | Very High | REST API server: upload MSTR exports, trigger migration, poll status, download results. JWT authentication. SQLite job store. |
| CC.2 | **Migration wizard UI** | `web/frontend/` | Very High | React/Vue SPA: step-by-step wizard (upload → configure → assess → migrate → validate → download). Responsive design. |
| CC.3 | **Real-time progress** | `web/api/websocket.py` | High | WebSocket connection: stream migration progress (extraction %, generation %, validation %). Show live log tail. |
| CC.4 | **Approval workflow** | `web/api/approval.py` | Medium | Post-migration review: side-by-side viewer (MSTR screenshot vs. PBI preview). Approve/reject per report. Comments. |
| CC.5 | **Multi-tenant isolation** | `web/auth/` | High | Azure AD SSO. Workspace isolation per tenant. RBAC: admin, migrator, reviewer roles. Audit log. |
| CC.6 | **Docker packaging** | `Dockerfile`, `docker-compose.yml` | Medium | Single-command deployment: `docker compose up`. Includes backend + frontend + worker. ARM template for Azure Container Apps. |
| CC.7 | **Tests** | `tests/test_web.py` | High | 50+ tests: API endpoints, auth, file upload, job lifecycle, WebSocket, approval flow. |

**v13.0 totals:** 1 sprint, ~10 new modules (new `web/` package), ~50 new tests, Docker deployment

---

## v14.0 — Enterprise Ecosystem Integration

**Theme:** Deep integration with Microsoft ecosystem — Power Automate, Teams, Azure DevOps, Purview, Defender, Copilot.  
**Priority:** LOW — completes the enterprise offering.

### Sprint DD — Microsoft 365 Integration

| # | Item | File(s) | Est. | Details |
|---|------|---------|------|---------|
| DD.1 | **Power Automate connector** | `integrations/power_automate/` | High | Custom connector: trigger migration from Power Automate flow. Actions: assess, migrate, validate, deploy. Return status + report URL. |
| DD.2 | **Teams notifications** | `integrations/teams_webhook.py` | Medium | Adaptive Card notifications: migration started/completed/failed. Include fidelity score, object counts, action buttons (view report, approve). |
| DD.3 | **Azure DevOps pipeline templates** | `integrations/azdo/` | Medium | YAML pipeline templates: CI/CD for migration — trigger on MSTR change → migrate → validate → deploy to staging → approval gate → deploy to production. |
| DD.4 | **Purview deep integration** | `integrations/purview_scanner.py` | High | Custom Purview scanner: register MSTR server as data source in Purview. Scan MSTR objects → Purview assets with full lineage. Bi-directional: Purview → PBI lineage connected. |
| DD.5 | **Copilot plugin** | `integrations/copilot_plugin/` | Medium | Microsoft 365 Copilot plugin: "Migrate my MicroStrategy Sales Dashboard to Power BI" → trigger migration, return progress, share result link. |
| DD.6 | **Defender for Cloud Apps** | `integrations/defender_config.py` | Low | Generate Defender for Cloud Apps policies: monitor migrated PBI content for anomalous access, data exfiltration. |
| DD.7 | **Tests** | `tests/test_integrations.py` | Medium | 40+ tests: connector payloads, Teams cards, DevOps YAML, Purview scanner, Copilot plugin. |

**v14.0 totals:** 1 sprint, ~6 new modules (new `integrations/` package), ~40 new tests

---
---

# Complete Roadmap Summary

| Version | Theme | Sprints | New Modules | Cumulative Tests | Key Capability |
|---------|-------|---------|-------------|-----------------|----------------|
| **v1.0** ✅ | Foundation | 1–10 | 18 | 385 | Full extract → generate → deploy pipeline |
| **v2.0** ✅ | Production Tooling | F–L | +6 | 570 | CI/CD, wizard, DAX depth, parallel, incremental |
| **v3.0** ✅ | Enterprise Assessment | F–K | +11 | 623 | 14-category assessment, strategy, comparison, plugins |
| **v4.0** 🔜 | Production Maturity | L–Q | +5 | ~900 | OLAP hardening, merge, scorecard, scale, certification |
| **v5.0** | Fabric Native | R–S | +4 | ~970 | DirectLake, Lakehouse, notebooks, Fabric Git |
| **v6.0** | Governance & Lineage | T–U | +4 | ~1,040 | Lineage graph, impact analysis, Purview integration |
| **v7.0** | AI-Assisted Migration | V–W | +2 | ~1,095 | LLM expression conversion, semantic field matching |
| **v8.0** | Multi-Language & i18n | X | — | ~1,125 | Multi-culture TMDL, translated captions, RTL support |
| **v9.0** | Real-Time & Streaming | Y | +2 | ~1,150 | Push datasets, Eventstream, refresh schedules |
| **v10.0** | Deep Testing & Quality | Z | +2 | **~2,000+** | Property-based, mutation, fuzz, screenshot tests |
| **v11.0** | Migration Ops | AA | +3 | ~2,040 | Change detection, drift report, auto-reconciliation |
| **v12.0** | Cross-Platform Federation | BB | +4 | ~2,090 | MSTR + Tableau + Cognos → unified PBI migration |
| **v13.0** | Self-Service Web Portal | CC | +10 | ~2,140 | Web UI, approval workflow, Docker deployment |
| **v14.0** | Enterprise Ecosystem | DD | +6 | ~2,180 | Power Automate, Teams, DevOps, Purview, Copilot |

**Grand totals (v1.0 → v14.0):**
- **~75 modules** across 5 packages (`microstrategy_export/`, `powerbi_import/`, `universal_bi/`, `web/`, `integrations/`)
- **~2,200 tests** (with v10.0 push to 2,000+)
- **~25 CLI flags**
- **14 development phases** across **~35 sprints**

---

## Phase Dependency Graph

```
v4.0 Production Maturity
 ├── v5.0 Fabric Native (depends on: strategy advisor, DirectLake detection)
 ├── v6.0 Governance & Lineage (depends on: merge tools, assessment)
 │    └── v14.0 Enterprise Ecosystem (depends on: Purview integration)
 ├── v7.0 AI-Assisted Migration (depends on: expression converter, manual_review items)
 ├── v8.0 Multi-Language (independent — can be done anytime after v4.0)
 ├── v9.0 Real-Time & Streaming (independent — can be done anytime after v4.0)
 ├── v10.0 Deep Testing (depends on: all generation modules stable)
 ├── v11.0 Migration Ops (depends on: incremental mode, telemetry)
 └── v12.0 Cross-Platform (depends on: merge tools, lineage)
      └── v13.0 Web Portal (depends on: all migration modes stable)
```

## Priority Matrix

| | High Impact | Low Impact |
|---|---|---|
| **Low Effort** | v8.0 i18n, v9.0 Real-Time | v14.0 Ecosystem |
| **High Effort** | v5.0 Fabric, v7.0 AI, v10.0 Testing | v12.0 Federation, v13.0 Portal |

**Recommended execution order:** v4.0 → v5.0 → v7.0 → v6.0 → v10.0 → v8.0 → v9.0 → v11.0 → v12.0 → v13.0 → v14.0
