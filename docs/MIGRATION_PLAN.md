# Migration Plan — MicroStrategy to Power BI / Fabric

**Version:** v1.0.0  
**Date:** 2026-03-19  
**Status:** Complete — All 5 sprints done (500 tests passing)

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
