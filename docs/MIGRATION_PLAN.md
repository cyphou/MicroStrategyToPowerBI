# Migration Plan — MicroStrategy to Power BI / Fabric

**Version:** v3.0.0-plan  
**Date:** 2026-03-19  
**Status:** v2.0.0 shipped (570 tests, 15K+ LOC) — v3.0 plan defined below

---

## Current State Assessment

### What Is Done (Phase 1 — Extraction Layer)

| Module | LOC | Status | Coverage |
|--------|-----|--------|----------|
| `rest_api_client.py` | ~195 | **Complete** | Auth (4 modes), pagination, retry, all object APIs |
| `schema_extractor.py` | ~220 | **Complete** | Tables, attributes, facts, hierarchies, relationships, custom groups, freeform SQL |
| `metric_extractor.py` | ~125 | **Complete** | Simple/compound/derived/level/ApplySimple metrics, thresholds |
| `expression_converter.py` | ~290 | **Complete** | 60+ function mappings, level metrics, derived metrics, ApplySimple patterns |
| `report_extractor.py` | ~135 | **Complete** | Grid/graph, filters, sorts, subtotals, page-by, 25+ graph types |
| `dossier_extractor.py` | ~225 | **Complete** | Chapters/pages/vizs, panel stacks, selectors, themes, 35+ viz types |
| `cube_extractor.py` | ~55 | **Complete** | Cube attributes/metrics/filter/refresh policy |
| `prompt_extractor.py` | ~82 | **Complete** | 6 prompt types → PBI slicer/parameter mappings |
| `security_extractor.py` | ~58 | **Complete** | Security filters, user/group assignments |
| `connection_mapper.py` | ~210 | **Complete** | 15+ DB types → Power Query M expressions |
| `extract_mstr_data.py` | ~210 | **Complete** | Online/offline orchestrator, 18 JSON output files |
| `migrate.py` | ~265 | **95%** | CLI, config, logging, stats (deploy/wizard stubs remain) |

**Extraction total: ~2,070 LOC of production logic across 12 files.**

### What Is Done (Phase 2 — Generation Layer)

| Module | LOC | Status | Sprint |
|--------|-----|--------|--------|
| `powerbi_import/tmdl_generator.py` | ~480 | **Complete** | A |
| `powerbi_import/visual_generator.py` | ~470 | **Complete** | B.1 |
| `powerbi_import/m_query_generator.py` | ~55 | **Complete** | A/B.2 |
| `powerbi_import/import_to_powerbi.py` | ~180 | **Complete** | A |

### What Is Not Done (Phase 2 — Generation Layer)

| Module | Status | Purpose |
|--------|--------|---------|
| `powerbi_import/pbip_generator.py` | ~190 | **Complete** | C |
| `powerbi_import/validator.py` | ~380 | **Complete** | D |
| `powerbi_import/assessment.py` | ~230 | **Complete** | D |
| `powerbi_import/migration_report.py` | ~230 | **Complete** | C |
| `powerbi_import/import_to_powerbi.py` | ~160 | **Complete** | C (rewrite) |
| `powerbi_import/shared_model.py` | ~120 | **Complete** | E.6 |
| `powerbi_import/deploy/pbi_deployer.py` | ~210 | **Complete** | E.1 |
| `powerbi_import/deploy/fabric_deployer.py` | ~280 | **Complete** | E.2 |
| `powerbi_import/deploy/gateway_config.py` | ~160 | **Complete** | E.3 |

**Test infrastructure: 34 fixture files + 15 test files, 500 tests passing.**

---

## Execution Plan

### Priorities & Dependencies

```
                 ┌─────────────────┐
                 │  TMDL Generator  │ ◄── Highest priority
                 │  (Sprint A)      │     Foundation for all output
                 └────────┬────────┘
                          │
              ┌───────────┼───────────┐
              │           │           │
              ▼           ▼           ▼
    ┌─────────────┐ ┌──────────┐ ┌──────────────┐
    │ M Query Gen │ │ Visual   │ │ Extraction   │
    │ (Sprint B)  │ │ Generator│ │ Tests        │
    │             │ │(Sprint B)│ │ (Sprint B)   │
    └──────┬──────┘ └────┬─────┘ └──────────────┘
           │              │
           ▼              ▼
    ┌──────────────────────────┐
    │  PBIP Assembly + Report  │
    │  (Sprint C)              │
    └────────────┬─────────────┘
                 │
         ┌───────┼───────┐
         ▼       ▼       ▼
    ┌─────────┐ ┌─────┐ ┌──────────┐
    │Validator│ │E2E  │ │Assessment│
    │(Sprint D)│Tests │ │(Sprint D)│
    └─────────┘ └─────┘ └──────────┘
                 │
                 ▼
    ┌──────────────────────────┐
    │  Deploy + Hardening      │
    │  (Sprint E)              │
    └──────────────────────────┘
```

---

### Sprint A — TMDL Semantic Model Generation ✅ COMPLETE

**Goal:** Generate valid `.tmdl` files from the 18 intermediate JSON files.  
**Agent:** `@generation`  
**Depends on:** Extraction layer (✅ done), test fixtures (✅ done)  
**Blocks:** Everything else in generation layer

| # | Task | File | Details | Est. |
|---|------|------|---------|------|
| A.1 | **Table generation** | `tmdl_generator.py` | Each datasource table → `.tmdl` file with columns. Map MSTR data types → TMDL types (int64, double, string, dateTime, decimal). Hidden key columns from ID forms. | High |
| A.2 | **Column generation** | `tmdl_generator.py` | Attribute forms → columns (ID=hidden key, DESC=display). Fact columns with format strings. Geographic data categories from attribute roles. | High |
| A.3 | **Measure generation** | `tmdl_generator.py` | Metrics → DAX measures. Wire `expression_converter.convert_metric_to_dax()` output. Display folders. Format strings. Handle compound/derived/level metrics. | Very High |
| A.4 | **Relationship generation** | `tmdl_generator.py` | `relationships.json` → `relationship` blocks. Cardinality (manyToOne default). Cross-filtering direction. | Medium |
| A.5 | **Hierarchy generation** | `tmdl_generator.py` | `hierarchies.json` → `hierarchy` blocks with ordered levels inside parent table. | Medium |
| A.6 | **RLS role generation** | `tmdl_generator.py` | `security_filters.json` → `role` definitions with `tablePermission` and DAX filter expressions. | Medium |
| A.7 | **Calendar auto-table** | `tmdl_generator.py` | Detect date columns, generate standard calendar table with Year/Quarter/Month/Day, create relationship. | Low |
| A.8 | **TMDL tests** | `test_tmdl_generator.py` | Validate against `expected_output/*.tmdl` fixtures. 60+ tests. | High |

**Exit criteria:** Running `tmdl_generator.py` against fixture data produces valid TMDL matching expected output files.

---

### Sprint B — Visual Generation + M Queries + Extraction Tests ✅ COMPLETE

Three independent workstreams that can proceed simultaneously.

#### B.1 — Visual Generation

**Agent:** `@generation`

| # | Task | File | Details |
|---|------|------|---------|
| B.1.1 | **Page mapping** | `visual_generator.py` | Dossier chapter → page group, page → report page. Layout scaling to 1280×720. |
| B.1.2 | **Grid → Table/Matrix** | `visual_generator.py` | Row attrs → rows, column attrs → columns, metrics → values. Subtotals → matrix subtotals. |
| B.1.3 | **Graph → Charts** | `visual_generator.py` | 30+ type mappings. Axis bindings, color/size encodings. Combo charts. |
| B.1.4 | **Slicer/Parameter** | `visual_generator.py` | Prompts → slicers/what-if parameters. Filter panels → slicer visuals. |
| B.1.5 | **Conditional formatting** | `visual_generator.py` | Thresholds → color/icon rules on visuals. |
| B.1.6 | **KPI/Gauge/Text** | `visual_generator.py` | Special visual types. |
| B.1.7 | **Visual tests** | `test_visual_generator.py` | 50+ tests for each visual type mapping. |

#### B.2 — M Query Generation

**Agent:** `@generation`

| # | Task | File | Details |
|---|------|------|---------|
| B.2.1 | **M partition writer** | `m_query_generator.py` | Generate M partition expression for each table using `connection_mapper.map_connection_to_m_query()`. |
| B.2.2 | **Freeform SQL** | `m_query_generator.py` | `freeform_sql.json` → `Value.NativeQuery()` partitions. |
| B.2.3 | **M query tests** | `test_m_query_generator.py` | 30+ tests per DB type. |

#### B.3 — Extraction Layer Tests

**Agent:** `@testing`

| # | Task | File | Fixture Data |
|---|------|------|-------------|
| B.3.1 | **REST client tests** | `test_rest_api_client.py` | `projects.json`, mock HTTP responses |
| B.3.2 | **Schema extractor tests** | `test_schema_extractor.py` | `tables.json`, `attributes.json`, `facts.json`, `hierarchies.json` |
| B.3.3 | **Metric extractor tests** | `test_metric_extractor.py` | `metrics.json` |
| B.3.4 | **Expression converter tests** | `test_expression_converter.py` | 100+ parametrized cases from MSTR_TO_DAX_REFERENCE.md |
| B.3.5 | **Report extractor tests** | `test_report_extractor.py` | `reports.json` |
| B.3.6 | **Dossier extractor tests** | `test_dossier_extractor.py` | `dossiers.json` |
| B.3.7 | **Connection mapper tests** | `test_connection_mapper.py` | All 15+ DB types |
| B.3.8 | **Advanced extraction tests** | `test_advanced_extraction.py` | `cubes.json`, `prompts.json`, `security_filters.json`, `search_results.json` |

**Exit criteria:** All extraction modules have ≥80% line coverage. Expression converter has ≥95%.

---

### Sprint C — .pbip Assembly + Migration Report ✅ COMPLETE

**Goal:** Wire everything together into a working `.pbip` project.  
**Agent:** `@generation` + `@orchestrator`  
**Depends on:** Sprints A and B.1/B.2

| # | Task | File | Details |
|---|------|------|---------|
| C.1 | **PBIP scaffold** | `pbip_generator.py` | Create `.pbip`, `.gitignore`, `SemanticModel/` folder (`.platform`, `definition.pbism`), `Report/` folder (PBIR v4.0 `report.json`). Reference TableauToPowerBI patterns. |
| C.2 | **TMDL file writer** | `pbip_generator.py` | Place generated `.tmdl` files in `SemanticModel/definition/tables/`, `relationships.tmdl`, `roles.tmdl`. |
| C.3 | **Visual file writer** | `pbip_generator.py` | Place PBIR visual JSON in `Report/definition/pages/`. |
| C.4 | **import_to_powerbi.py rewrite** | `import_to_powerbi.py` | Replace stub with full orchestration: load JSON → generate TMDL → generate visuals → generate M queries → assemble .pbip → validate. |
| C.5 | **Migration report (JSON)** | `migration_report.py` | Per-object fidelity: fully_migrated / approximated / manual_review / unsupported. |
| C.6 | **Migration report (HTML)** | `migration_report.py` | Summary dashboard, object table, expression details, warnings. |
| C.7 | **Assembly tests** | `test_pbip_assembly.py` | Validate project structure, file presence, TMDL syntax. |

**Exit criteria:** `python migrate.py --from-export tests/fixtures/intermediate_json --output-dir /tmp/test_output` produces a valid `.pbip` that opens in Power BI Desktop.

---

### Sprint D — Validation + Assessment

**Agent:** `@validation`  
**Depends on:** Sprint C

| # | Task | File | Details |
|---|------|------|---------|
| D.1 | **TMDL syntax validator** | `validator.py` | Verify generated TMDL is syntactically correct. |
| D.2 | **PBIR schema validator** | `validator.py` | Verify visual JSON conforms to PBIR v4.0 schema. |
| D.3 | **Relationship cycle detection** | `validator.py` | Graph analysis to prevent invalid circular relationships. |
| D.4 | **DAX reference validation** | `validator.py` | Ensure all measure references resolve to existing measures/columns. |
| D.5 | **Assessment mode** | `assessment.py` | `--assess` flag: object counts, complexity scores, unsupported feature flags, estimated fidelity. |
| D.6 | **E2E integration tests** | `test_integration.py` | Full pipeline: fixture API responses → extract → intermediate JSON → generate → validate .pbip. |
| D.7 | **Validation tests** | `test_validator.py` | 40+ tests for each validation rule. |

**Exit criteria:** `--assess` produces accurate complexity report. Validator catches all known error patterns.

---

### Sprint E — Deploy + Hardening

**Agent:** `@orchestrator` + `@generation`  
**Depends on:** Sprint D

| # | Task | File | Details |
|---|------|------|---------|
| E.1 | **PBI Service deployer** | `deploy/pbi_deployer.py` | Azure AD auth, workspace upload, dataset refresh. |
| E.2 | **Fabric deployer** | `deploy/fabric_deployer.py` | Fabric workspace, DirectLake mode. |
| E.3 | **Gateway config** | `deploy/gateway_config.py` | On-premises connection config. |
| E.4 | **Batch migration** | `migrate.py` | `--batch` with parallel extraction. |
| E.5 | **Expression hardening** | `expression_converter.py` | Nested metrics, OLAP functions, banding, cross-table context. |
| E.6 | **Shared model** | `shared_model.py` | Project-level semantic model + thin reports. |
| E.7 | **Deploy/batch tests** | `test_deployment.py` | Mock deployment, batch mode. |

---

## Sprint-to-Agent Mapping

| Sprint | Primary Agent | Support Agent | Parallel? |
|--------|--------------|---------------|-----------|
| **A** — TMDL Generation | `@generation` | `@expression` | No — critical path |
| **B.1** — Visual Generator | `@generation` | — | Yes (B.1 ∥ B.2 ∥ B.3) |
| **B.2** — M Query Generator | `@generation` | — | Yes |
| **B.3** — Extraction Tests | `@testing` | — | Yes |
| **C** — PBIP Assembly | `@generation` | `@orchestrator` | No — depends on A+B |
| **D** — Validation | `@validation` | `@testing` | No — depends on C |
| **E** — Deploy + Hardening | `@orchestrator` | `@expression` | No — depends on D |

---

## Milestones & Exit Criteria

| Milestone | Sprint | Deliverable | Verification |
|-----------|--------|-------------|-------------|
| **M1 — TMDL Output** | A | Valid `.tmdl` files from intermediate JSON | Compare against `expected_output/*.tmdl` fixtures |
| **M2 — Visual Output** | B.1 | PBIR visual JSON for all 30+ chart types | Schema validation + visual rendering check |
| **M3 — Full .pbip** | C | Working `.pbip` project opens in PBI Desktop | Manual open test + automated structure validation |
| **M4 — Test Coverage** | B.3+D | ≥80% overall, ≥95% expression converter | `pytest --cov` report |
| **M5 — Enterprise Ready** | E | Deployment, batch, shared model | End-to-end batch test with mock server |

---

## Risk Register

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| TMDL format changes in PBI Desktop updates | High | Medium | Pin to TMDL spec version, add format detection |
| PBIR v4.0 visual schema undocumented | High | High | Reference TableauToPowerBI working output, test with PBI Desktop |
| Expression converter gaps for complex ApplySimple | Medium | High | Flag as manual_review, provide SQL in comments |
| Large project scale (10,000+ objects) | Medium | Medium | Streaming extraction, lazy generation |
| REST API version differences (2020 vs 2021+) | Medium | Medium | Version detection + fallback, document minimum version |

---

## Reference Projects

- **TableauToPowerBI** (`../TableauToPowerBI/`): v17.0.0, 4,219 tests, 77 test files. Generation modules can be reused ~60-80%.
- **PBIR v4.0 spec**: Power BI enhanced report format documentation.
- **TMDL spec**: Tabular Model Definition Language documentation.

---
---

# v3.0 Development Plan — Production Hardening & Feature Depth

**Goal:** Bring the tool from beta/fixture-tested to production-grade, closing the gap with the reference TableauToPowerBI (v17.0.0) architecture.

## Gap Analysis vs Reference Project

| Area | MicroStrategyToPBI (v2.0) | TableauToPBI (v17.0) | Gap | Sprint |
|------|--------------------------|---------------------|-----|--------|
| `tmdl_generator.py` | ~850 LOC | 3,779 LOC | Display folders, calculated tables, format strings, annotations, perspectives | G |
| `pbip_generator.py` | ~350 LOC | 3,435 LOC | Theme support, bookmarks, drill-through pages, tooltip pages, mobile layout | G |
| `visual_generator.py` | ~800 LOC | 1,548 LOC | Conditional formatting depth, interactions, drill-down, tooltip config | G |
| `assessment.py` | ~600 LOC | 1,267 LOC | 14-category check model, structured CheckItem/CategoryResult, GREEN/YELLOW/RED scoring, effort estimation | H |
| `server_assessment.py` | ❌ | 484 LOC | Portfolio-level assessment, migration waves, readiness % | H |
| `global_assessment.py` | ❌ | 840 LOC | Cross-project pairwise scoring, merge clustering, heatmap | H |
| `strategy_advisor.py` | ❌ | 334 LOC | Import/DirectQuery/Composite recommendation engine | H |
| `migration_report.py` | ~700 LOC | 458 LOC | Status enum (EXACT/APPROXIMATE/UNSUPPORTED), weighted scoring, letter grade | I |
| `comparison_report.py` | ❌ | 310 LOC | Side-by-side source vs generated HTML comparison | I |
| `visual_diff.py` | ❌ | 387 LOC | Visual type + field coverage analysis | I |
| `merge_assessment.py` | ❌ | 331 LOC | Merge conflict tracking, dedup stats, manifest diff | I |
| `merge_report_html.py` | ❌ | 753 LOC | Comprehensive merge HTML report with overlap bars, RLS section | I |
| `telemetry_dashboard.py` | ❌ | 182 LOC | Historical migration run aggregation dashboard | I |
| `shared_model.py` | ~200 LOC | 2,965 LOC | Full model generation, thin report binding, multi-report support | J |
| `thin_report_generator.py` | ❌ | 452 LOC | Lightweight reports referencing shared model | J |
| `progress.py` | ❌ | 146 LOC | Real-time progress bar for batch | K |
| `plugins.py` | ❌ | 223 LOC | Custom visual/expression plugins | K |

---

## v3.0 Sprint Roadmap

```
  Sprint F          Sprint G           Sprint H           Sprint I            Sprint J           Sprint K
  ┌──────────┐     ┌──────────┐       ┌──────────┐       ┌──────────┐       ┌──────────┐       ┌──────────┐
  │ Real-World│     │ TMDL &   │       │ Assessment│       │ Migration│       │ Shared   │       │ Enterprise│
  │ Testing & │────▶│ Visual   │──────▶│ Engine   │──────▶│ Reports &│──────▶│ Model &  │──────▶│ Features  │
  │ Bug Fixes │     │ Depth    │       │ (Deep)   │       │ Diff     │       │ Thin     │       │ & Polish  │
  └──────────┘     └──────────┘       └──────────┘       └──────────┘       │ Reports  │       └──────────┘
                                                                            └──────────┘
```

---

### Sprint F — Real-World Testing & PBI Desktop Conformance

**Goal:** Validate against real MicroStrategy exports; fix all PBI Desktop load errors.  
**Agent:** `@generation` + `@testing`  
**Priority:** CRITICAL — blocks all other v3.0 work

| # | Task | File(s) | Details |
|---|------|---------|---------|
| F.1 | **Real MSTR export testing** | `tests/fixtures/` | Obtain 3-5 real MicroStrategy project exports (varying complexity). Run full pipeline. Document every PBI Desktop error. |
| F.2 | **TMDL format hardening** | `tmdl_generator.py` | Fix any remaining TMDL syntax errors found in F.1 (multi-line expressions, special characters in names, reserved word escaping). |
| F.3 | **PBIR visual conformance** | `visual_generator.py` | Fix visual JSON issues found in F.1 (missing required properties, invalid enum values, layout overflow). |
| F.4 | **Expression converter gaps** | `expression_converter.py` | Add 15+ new SQL→DAX patterns discovered from real exports. Cover complex CASE WHEN (4+ branches), DECODE, REGEXP patterns. |
| F.5 | **ApplyAgg & ApplyOLAP** | `expression_converter.py` | Implement real conversion for ApplyAgg (custom aggregation) and ApplyOLAP (window functions) instead of `manual_review` stubs. |
| F.6 | **Name sanitization** | `tmdl_generator.py`, `visual_generator.py` | Handle special characters in object names: quotes, brackets, Unicode, reserved TMDL/DAX keywords. |
| F.7 | **Large model stress test** | `tests/` | Test with 100+ tables, 500+ measures, 50+ pages. Profile memory and performance. |
| F.8 | **Regression test suite** | `tests/test_regression.py` | Create regression tests for all 10 PBI Desktop bugs fixed in v2.0.1 (prevents re-introduction). |

**Exit criteria:** 3+ real MSTR exports generate .pbip projects that open cleanly in PBI Desktop with no errors.

---

### Sprint G — TMDL & Visual Generator Depth

**Goal:** Close the feature depth gap with reference project.  
**Agent:** `@generation` + `@expression`

#### G.1 — TMDL Depth (target: ~2,500 LOC)

| # | Task | File | Details |
|---|------|------|---------|
| G.1.1 | **Display folders** | `tmdl_generator.py` | Group measures into display folders based on MSTR metric folders/categories. |
| G.1.2 | **Calculated tables** | `tmdl_generator.py` | MSTR custom groups → DAX calculated tables (`DATATABLE()` or `UNION()`). |
| G.1.3 | **Format strings** | `tmdl_generator.py` | Full MSTR number/date/currency format → TMDL `formatString` conversion. Support `#,##0.00`, `$#,##0`, `0.0%`, date patterns. |
| G.1.4 | **Column annotations** | `tmdl_generator.py` | Preserve MSTR metadata as TMDL annotations (source object ID, original name, migration notes). |
| G.1.5 | **Perspectives** | `tmdl_generator.py` | MSTR report-scoped metrics → TMDL perspectives (hide irrelevant tables/measures per report). |
| G.1.6 | **Calculated columns** | `tmdl_generator.py` | MSTR attribute derived forms → TMDL calculated columns with DAX expressions. |
| G.1.7 | **Data categories** | `tmdl_generator.py` | Expanded geographic/URL/image/barcode data category detection from MSTR attribute roles. |

#### G.2 — Visual Generator Depth (target: ~1,400 LOC)

| # | Task | File | Details |
|---|------|------|---------|
| G.2.1 | **Conditional formatting** | `visual_generator.py` | Full threshold→conditional formatting: color scales, data bars, icon sets, rules-based formatting. |
| G.2.2 | **Drill-through pages** | `visual_generator.py` | MSTR linked dossiers/reports → PBI drill-through pages with filter context. |
| G.2.3 | **Tooltip pages** | `visual_generator.py` | MSTR info windows → PBI tooltip pages (custom report page tooltips). |
| G.2.4 | **Visual interactions** | `visual_generator.py` | MSTR selector targets → PBI visual interaction configuration (filter/highlight/none). |
| G.2.5 | **Bookmarks** | `pbip_generator.py` | MSTR panel stack states → PBI bookmarks. |
| G.2.6 | **Mobile layout** | `pbip_generator.py` | Generate mobile-optimized layout variant for dossier pages. |
| G.2.7 | **Theme support** | `pbip_generator.py` | MSTR dossier themes → PBI report theme JSON (colors, fonts, visual defaults). |
| G.2.8 | **Unsupported viz fallback** | `visual_generator.py` | Improve fallback for box_plot/word_cloud/sankey/network → R/Python visuals or custom visuals instead of tableEx. |

**Exit criteria:** Generated reports match MSTR source layout within 90% fidelity. All conditional formatting renders correctly.

---

### Sprint H — Assessment Engine (Deep)

**Goal:** Build a comprehensive pre-migration assessment engine matching TableauToPowerBI's 14-category model, adapted for MicroStrategy concepts.  
**Agent:** `@validation` + `@orchestrator`  
**Depends on:** Sprint G  
**Reference:** `../TableauToPowerBI/powerbi_import/assessment.py` (1,267 LOC), `server_assessment.py` (484 LOC), `global_assessment.py` (840 LOC), `strategy_advisor.py` (334 LOC)

#### H.1 — Single-Project Assessment Rewrite (target: ~1,200 LOC)

Current `assessment.py` (~600 LOC) covers basic complexity scoring. Rewrite to match the reference project's structured check/category/report model.

| # | Task | File | Details |
|---|------|------|---------|
| H.1.1 | **CheckItem data model** | `assessment.py` | Implement `CheckItem(category, name, severity, detail, recommendation)` + `CategoryResult` + `AssessmentReport` with GREEN/YELLOW/RED scoring. |
| H.1.2 | **Datasource compatibility** | `assessment.py` | Classify each warehouse connection: fully supported (SQL Server, PostgreSQL, MySQL, Snowflake) / partially (Oracle, SAP HANA, Teradata) / unsupported. Map to connection_mapper tiers. |
| H.1.3 | **Expression readiness** | `assessment.py` | Scan all metrics for: ApplySimple (auto-convertible vs manual), ApplyAgg (always manual), ApplyOLAP (partially convertible), nested level metrics (complex), derived metrics (Rank/Lag/Lead fidelity). Flag expression_converter gaps. |
| H.1.4 | **Visual & dossier coverage** | `assessment.py` | Map each dossier visualization type against `_VISUAL_TYPE_MAP` — flag unsupported types (box_plot, sankey, network, word_cloud), count fallbacks to tableEx. |
| H.1.5 | **Filter & prompt complexity** | `assessment.py` | Score prompt types: simple value prompts (easy) vs cascading/linked prompts (hard) vs expression prompts (manual). Count filters with complex expressions. |
| H.1.6 | **Data model complexity** | `assessment.py` | Score based on: table count, relationship count, hierarchy depth, many-to-many relationships, cross-database joins, freeform SQL objects. |
| H.1.7 | **Security & RLS** | `assessment.py` | Assess security filter complexity: simple attribute filters (auto) vs expression-based filters (manual). Count user/group assignments that need manual RLS setup. |
| H.1.8 | **Migration scope & effort** | `assessment.py` | Effort estimation model adapted for MSTR: base hours + per-metric (0.2h) + per-derived-metric (0.5h) + per-ApplySimple (0.3h) + per-ApplyOLAP (0.8h) + per-dossier-page (0.15h) + per-prompt (0.25h) + per-security-filter (0.3h). |
| H.1.9 | **Performance risks** | `assessment.py` | Detect: high-cardinality attributes (>1M values), large fact tables, complex cross-table metrics, heavy OLAP expressions. |
| H.1.10 | **Unsupported features** | `assessment.py` | Flag: consolidations, custom group nesting, document-type reports, transaction services, OLAP Services cubes, distribution services integration. |
| H.1.11 | **HTML assessment report** | `assessment.py` | Generate styled HTML with: summary cards (GREEN/YELLOW/RED), category breakdown, effort estimate, recommendations list, risk flags. |
| H.1.12 | **Assessment tests** | `tests/test_assessment.py` | 40+ tests: scoring logic, category detection, effort estimation, edge cases. |

#### H.2 — Server-Wide Assessment (target: ~500 LOC)

| # | Task | File | Details |
|---|------|------|---------|
| H.2.1 | **Server assessment** | `server_assessment.py` (new) | Portfolio-level assessment: scan N MSTR projects via REST API, assess each, aggregate. |
| H.2.2 | **Migration waves** | `server_assessment.py` | Classify projects into waves: Wave 1 (GREEN + simple) → Wave 2 (YELLOW + moderate) → Wave 3 (RED + complex). |
| H.2.3 | **Connector census** | `server_assessment.py` | Aggregate all warehouse connections across projects. Histogram of connection types, highlight unsupported. |
| H.2.4 | **Readiness percentage** | `server_assessment.py` | Overall readiness score: % of projects that are GREEN, weighted by object count. |
| H.2.5 | **Server HTML report** | `server_assessment.py` | Dashboard: summary cards, connector histogram, migration waves table, per-project detail grid. |
| H.2.6 | **CLI: `--bulk-assess`** | `migrate.py` | `migrate.py --bulk-assess <project_list>` triggers server-wide assessment without extracting. Outputs `server_assessment.json` + `server_assessment.html`. |

#### H.3 — Global Assessment & Merge Clustering (target: ~800 LOC)

| # | Task | File | Details |
|---|------|------|---------|
| H.3.1 | **Project profiles** | `global_assessment.py` (new) | Build `ProjectProfile` for each MSTR project: tables, columns, metrics, relationships, reports, dossiers, cubes, connector types. |
| H.3.2 | **Pairwise scoring** | `global_assessment.py` | N×N comparison matrix: shared tables (fingerprint matching), shared attributes, connector overlap. Score 0-100 per pair. |
| H.3.3 | **Merge clustering** | `global_assessment.py` | BFS clustering (adjacency threshold ≥30): group projects with high shared-table overlap for shared semantic model migration. |
| H.3.4 | **Merge heatmap** | `global_assessment.py` | HTML heatmap: color-coded pairwise scores (green ≥60, yellow 30-59, red <30). |
| H.3.5 | **Cluster recommendations** | `global_assessment.py` | Per-cluster: recommend merge (shared model), partial (selective tables), or separate (independent projects). |
| H.3.6 | **Global HTML report** | `global_assessment.py` | Executive summary, project inventory, heatmap, cluster detail, isolated projects list. |
| H.3.7 | **CLI: `--global-assess`** | `migrate.py` | `migrate.py --batch --global-assess` triggers cross-project analysis after extraction. |

#### H.4 — Strategy Advisor (target: ~350 LOC)

| # | Task | File | Details |
|---|------|------|---------|
| H.4.1 | **Strategy engine** | `strategy_advisor.py` (new) | Recommend data loading strategy: Import Mode vs DirectQuery vs Composite. |
| H.4.2 | **Scoring signals** | `strategy_advisor.py` | 14 signals adapted for MSTR: connector type (PQ-friendly vs DQ-friendly, weight 2), table count, column count, freeform SQL present (weight 2), OLAP expressions detected (weight 2), metric count, prompt complexity, cube vs report mode, relationship density. |
| H.4.3 | **Strategy selection** | `strategy_advisor.py` | Highest score wins; if gap ≤ margin (2) → recommend Composite. Output: `StrategyRecommendation(strategy, import_score, dq_score, signals, summary)`. |
| H.4.4 | **Console output** | `strategy_advisor.py` | Formatted recommendation box with reasoning per signal. |
| H.4.5 | **CLI: `--strategy`** | `migrate.py` | `migrate.py --assess --strategy` includes storage mode recommendation in assessment output. |

**Exit criteria:** `--assess` produces 14-category report with GREEN/YELLOW/RED scoring, effort estimate in hours, and storage mode recommendation. `--bulk-assess` handles N projects with migration waves. `--global-assess` detects merge clusters.

---

### Sprint I — Migration Reports & Visual Diff

**Goal:** Comprehensive post-migration reporting with per-object fidelity tracking, side-by-side comparison, and visual diff — matching the reference project's reporting suite.  
**Agent:** `@validation` + `@generation`  
**Depends on:** Sprint H  
**Reference:** `../TableauToPowerBI/powerbi_import/migration_report.py` (458 LOC), `comparison_report.py` (310 LOC), `visual_diff.py` (387 LOC), `merge_report_html.py` (753 LOC), `merge_assessment.py` (331 LOC)

#### I.1 — Migration Report Rewrite (target: ~500 LOC)

Current `migration_report.py` (~700 LOC) has good fidelity tracking. Enhance to match reference project's structured status model and scoring.

| # | Task | File | Details |
|---|------|------|---------|
| I.1.1 | **Status enum** | `migration_report.py` | Formalize fidelity levels: `EXACT` (100%), `APPROXIMATE` (50%), `PLACEHOLDER` (0%), `UNSUPPORTED` (0%), `SKIPPED` (0%) — with consistent per-object tracking. |
| I.1.2 | **Bulk classification** | `migration_report.py` | Auto-classify all converted objects: `add_metrics()` (scan DAX for manual_review markers), `add_visuals()` (check type mapping), `add_datasources()`, `add_relationships()`, `add_hierarchies()`, `add_prompts()`, `add_security_filters()`. |
| I.1.3 | **DAX classification** | `migration_report.py` | `_classify_dax()`: detect unsupported patterns (ApplyAgg remnants, unresolved references), approximate patterns (placeholder WINDOW, approximated RunningSum), exact (clean DAX). |
| I.1.4 | **Weighted scoring** | `migration_report.py` | Category weights adapted for MSTR: metric (0.30), visual (0.25), datasource (0.15), relationship (0.10), prompt (0.07), security_filter (0.05), hierarchy (0.04), derived_metric (0.04). Letter grade A-F. |
| I.1.5 | **Table mapping** | `migration_report.py` | Source→target table mapping: MSTR table → TMDL table, with column counts, connection type, partition type. |
| I.1.6 | **Enhanced HTML report** | `migration_report.py` | Styled HTML with: fidelity score card, per-category breakdown, unsupported items list with recommendations, table mapping grid, expression conversion details (original→DAX side by side). |
| I.1.7 | **Migration report tests** | `tests/test_migration_report.py` | 30+ tests: classification logic, scoring, edge cases. |

#### I.2 — Comparison Report (target: ~350 LOC)

| # | Task | File | Details |
|---|------|------|---------|
| I.2.1 | **Comparison engine** | `comparison_report.py` (new) | Load MSTR intermediate JSON + generated .pbip artifacts. Match source objects to generated objects by name/ID. |
| I.2.2 | **Report/dossier matching** | `comparison_report.py` | Match MSTR reports/dossiers → PBI pages. Show: matched %, unmatched source objects, extra PBI objects. |
| I.2.3 | **Metric→measure matching** | `comparison_report.py` | Match MSTR metrics → PBI measures. Show original expression vs generated DAX side by side. Highlight differences. |
| I.2.4 | **Datasource matching** | `comparison_report.py` | Match MSTR datasources → PBI tables. Show table/column counts, connection type mapping. |
| I.2.5 | **HTML comparison report** | `comparison_report.py` | Side-by-side HTML: summary cards (matched %, fidelity %), metric conversion table, visual mapping grid, datasource summary. |
| I.2.6 | **Auto-generation** | `pbip_generator.py` | Auto-generate comparison report after every migration (saved alongside .pbip output). |

#### I.3 — Visual Diff (target: ~400 LOC)

| # | Task | File | Details |
|---|------|------|---------|
| I.3.1 | **Visual diff engine** | `visual_diff.py` (new) | Compare MSTR dossier visualizations vs generated PBI visuals: type mapping accuracy, data binding coverage, position deltas. |
| I.3.2 | **Field coverage analysis** | `visual_diff.py` | Per-visual: `coverage_pct = mapped_fields / total_mstr_fields * 100`. Track: category, values, color, size, tooltip, detail bindings. |
| I.3.3 | **Classification** | `visual_diff.py` | Per-visual: `exact` (type matches + all fields mapped), `approx` (type differs or partial fields), `unmapped` (no PBI visual found). |
| I.3.4 | **HTML visual diff** | `visual_diff.py` | Summary cards (total, exact/approx/unmapped, avg coverage %), per-visual diff cards (side-by-side MSTR→PBI), summary table. |
| I.3.5 | **JSON output** | `visual_diff.py` | `generate_visual_diff_json()` for programmatic consumption. |

#### I.4 — Merge Assessment Report (target: ~350 LOC)

| # | Task | File | Details |
|---|------|------|---------|
| I.4.1 | **Merge reporter** | `merge_assessment.py` (new) | JSON + HTML report for shared model merges: merge candidates, measure conflicts, dedup stats, merge score 0-100. |
| I.4.2 | **Merge candidates** | `merge_assessment.py` | Matched tables (fingerprint + column overlap %), conflict detection (same name, different columns). |
| I.4.3 | **Conflict tracking** | `merge_assessment.py` | Measure conflicts (same name, different DAX) + parameter conflicts + relationship duplicates removed. |
| I.4.4 | **Manifest diff** | `merge_assessment.py` | `diff_manifests(old, new)`: compare two merge snapshots — added/removed tables, measures, config changes, score delta. |
| I.4.5 | **Console summary** | `merge_assessment.py` | Formatted box: overview, merge candidates, conflicts, recommendation (merge/partial/separate). |

#### I.5 — Merge Report HTML (target: ~750 LOC)

| # | Task | File | Details |
|---|------|------|---------|
| I.5.1 | **Full merge HTML** | `merge_report_html.py` (new) | Comprehensive merge report: executive summary, source inventory, merged output stats, table matching, measure mapping (tabbed: all/per-project/conflicts), relationship mapping. |
| I.5.2 | **Overlap visualization** | `merge_report_html.py` | Per-table overlap bars (% column match), fingerprint details, conflict highlights. |
| I.5.3 | **RLS section** | `merge_report_html.py` | Security: RLS role expressions from each source project, propagation status, principal format. |
| I.5.4 | **Merge report tests** | `tests/test_merge_report.py` | 20+ tests: merge scoring, conflict detection, manifest diff, HTML generation. |

#### I.6 — Telemetry Dashboard (target: ~400 LOC)

| # | Task | File | Details |
|---|------|------|---------|
| I.6.1 | **Telemetry collector** | `telemetry.py` (new) | Collect migration run data: object counts, conversion rates, error frequencies, timing. Save as `migration_telemetry_<timestamp>.json`. |
| I.6.2 | **Historical dashboard** | `telemetry_dashboard.py` (new) | Aggregate all `migration_report_*.json` files: total runs, avg/min/max fidelity, status distribution, common issues, fidelity trend over time. |
| I.6.3 | **HTML dashboard** | `telemetry_dashboard.py` | Summary cards, fidelity history (last 30 runs, color-coded), per-run table, status histogram, common issues table. |

**Exit criteria:** Every migration produces: `migration_report.json` + `migration_report.html` + `comparison_report.html` + `visual_diff.html`. Merge migrations additionally produce `merge_assessment.html` + `merge_report.html`. Telemetry dashboard aggregates historical runs.

---

### Sprint J — Shared Model & Thin Reports

**Goal:** Enterprise multi-report pattern: one shared semantic model + N thin reports.  
**Agent:** `@generation` + `@orchestrator`  
**Depends on:** Sprint I (merge assessment/reporting needed for shared model decisions)

| # | Task | File | Details |
|---|------|------|---------|
| J.1 | **Shared model rewrite** | `shared_model.py` | Full semantic model generation (currently ~200 LOC → target ~1,500 LOC). Support all tables, measures, relationships, RLS, hierarchies. `definition.pbism` with proper BIM references. |
| J.2 | **Thin report generator** | `thin_report_generator.py` (new) | Generate lightweight `.pbip` reports that reference external shared model via `byConnection` binding. One thin report per MSTR report/dossier. |
| J.3 | **Model/report binding** | `pbip_generator.py` | Wire `definitionFilePath` in report `definition.pbir` to reference shared model. Support both local and workspace references. |
| J.4 | **Multi-project batch** | `migrate.py` | `--shared-model --batch` generates: 1 shared `.pbip` model + N thin report `.pbip` projects, all in a structured folder. |
| J.5 | **Merge report integration** | `merge_report_html.py` | Auto-generate merge report when `--shared-model` combines multiple MSTR projects. |
| J.6 | **Shared model tests** | `tests/test_shared_model.py` | Validate model completeness, thin report binding, batch output structure, merge reporting. |

**Exit criteria:** `migrate.py --batch --shared-model` produces 1 shared model + N thin reports that all open in PBI Desktop and bind correctly. Merge report generated automatically.

---

### Sprint K — Enterprise Features & Polish

**Goal:** Remaining parity with reference project; production polish.  
**Agent:** `@orchestrator` + `@validation`

#### K.1 — Developer Experience

| # | Task | File | Details |
|---|------|------|---------|
| K.1.1 | **Progress tracking** | `progress.py` (new) | Real-time progress bar for batch migrations (tqdm integration). ETA estimation. Per-object status updates. |
| K.1.2 | **Plugin system** | `plugins.py` (new) | Register custom visual mappers, expression converters, or post-processors. YAML config for plugin loading. Start with 2-3 extension points. |

#### K.2 — Robustness

| # | Task | File | Details |
|---|------|------|---------|
| K.2.1 | **Incremental hardening** | `incremental.py` | Full delta tracking: detect changed objects, skip unchanged, merge into existing .pbip output. Manifest-based diffing. |
| K.2.2 | **Parallel optimization** | `parallel.py` | Profile and optimize parallel extraction. Connection pooling, rate limiting per endpoint. |
| K.2.3 | **Error recovery** | `migrate.py` | Checkpoint/resume for interrupted batch migrations. Partial output preservation. |

**Exit criteria:** Full feature parity with TableauToPowerBI v17.0 architecture. 800+ tests.

---

## v3.0 Milestones

| Milestone | Sprint | Deliverable | Verification |
|-----------|--------|-------------|-------------|
| **M6 — Real-World Validated** | F | 3+ real MSTR exports → clean .pbip | PBI Desktop opens without errors |
| **M7 — Feature Depth** | G | Display folders, conditional formatting, drill-through, themes | Visual fidelity ≥90% |
| **M8 — Assessment Suite** | H | 14-category assessment, server-wide analysis, strategy advisor | `--assess` produces GREEN/YELLOW/RED report with effort estimate |
| **M9 — Reporting Suite** | I | Migration report, comparison report, visual diff, merge report, telemetry | Every migration produces 4+ reports automatically |
| **M10 — Enterprise Model** | J | Shared model + thin reports in batch mode | Multi-report .pbip opens with shared model |
| **M11 — Production Ready** | K | Plugins, incremental, progress, error recovery | Feature parity with reference project |

---

## v3.0 Priority Matrix

```
                    HIGH IMPACT
                        │
    Sprint F             │          Sprint H
    Real-World Testing   │       Assessment Engine
    ─────────────────────┼──────────────────────────
    Sprint G             │          Sprint I
    TMDL & Visual Depth  │       Reports & Diff
    ─────────────────────┼──────────────────────────
    Sprint K             │          Sprint J
    Enterprise Polish    │       Shared Model
                        │
                    LOW IMPACT
     ◄── LOW EFFORT ────┼──── HIGH EFFORT ──►
```

**Recommended execution order:** F → G → H → I → J → K (sequential, each builds on the previous)

---

## Assessment & Reporting Architecture (Sprints H + I)

```
                     ┌────────────────────────────────────────────┐
                     │           PRE-MIGRATION (Sprint H)         │
                     │                                            │
  --assess ─────────▶│  assessment.py                             │
                     │    14 categories → GREEN/YELLOW/RED        │
                     │    Effort estimation (hours)               │
                     │    → assessment_report.json + .html        │
                     │                                            │
  --strategy ───────▶│  strategy_advisor.py                       │
                     │    Import vs DirectQuery vs Composite      │
                     │    14 scoring signals                      │
                     │    → console recommendation                │
                     │                                            │
  --bulk-assess ────▶│  server_assessment.py                      │
                     │    N projects → migration waves            │
                     │    Connector census                        │
                     │    → server_assessment.json + .html        │
                     │                                            │
  --global-assess ──▶│  global_assessment.py                      │
                     │    Pairwise scoring → merge clusters       │
                     │    → global_assessment.json + .html        │
                     └────────────────────────────────────────────┘

                     ┌────────────────────────────────────────────┐
                     │          POST-MIGRATION (Sprint I)         │
                     │                                            │
  (auto) ──────────▶│  migration_report.py                        │
                     │    Per-object fidelity (EXACT→UNSUPPORTED) │
                     │    Weighted scoring + letter grade          │
                     │    → migration_report.json + .html         │
                     │                                            │
  (auto) ──────────▶│  comparison_report.py                       │
                     │    MSTR source ↔ PBI output side-by-side   │
                     │    Metric expression comparison             │
                     │    → comparison_report.html                │
                     │                                            │
  (auto) ──────────▶│  visual_diff.py                             │
                     │    Visual type + field coverage analysis    │
                     │    exact / approx / unmapped               │
                     │    → visual_diff.html                      │
                     │                                            │
  --shared-model ──▶│  merge_assessment.py + merge_report_html.py │
                     │    Merge candidates, conflicts, dedup       │
                     │    → merge_assessment.html + merge_report   │
                     │                                            │
  (historical) ────▶│  telemetry_dashboard.py                     │
                     │    Aggregate all runs → trend dashboard    │
                     │    → telemetry_dashboard.html              │
                     └────────────────────────────────────────────┘
```

---

## Updated Risk Register (v3.0)

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Real MSTR exports reveal many unknown edge cases | High | Very High | Sprint F is dedicated to this; time-box to 1 week per export |
| TMDL/PBIR spec changes in PBI Desktop monthly updates | High | Medium | Pin to a specific PBI Desktop version for testing; regression suite |
| Assessment scoring models need calibration from real data | Medium | High | Start with TableauToPowerBI weights, refine based on real MSTR exports |
| Shared model binding format undocumented | Medium | High | Reverse-engineer from TableauToPowerBI output + PBI Desktop |
| ApplyOLAP/ApplyAgg patterns too varied for automatic conversion | Medium | High | Best-effort conversion + detailed `manual_review` comments with original SQL |
| Merge clustering algorithm slow for large project portfolios | Low | Medium | Threshold-based pruning; skip pairs with 0 shared tables |
| Plugin system over-engineering | Low | Medium | Start with 2-3 extension points only; expand based on demand |

---

## Test Target

| Version | Tests | Coverage |
|---------|-------|----------|
| v1.0.0 | 500 | ~80% |
| v2.0.0 | 570 | ~85% |
| **v3.0.0** | **800+** | **≥90%** |
