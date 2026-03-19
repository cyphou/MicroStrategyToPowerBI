# Test Strategy — MicroStrategy to Power BI / Fabric Migration Tool

**Version:** v3.0.0  
**Date:** 2026-03-20  
**Coverage Target:** ≥80% overall, ≥95% expression converter  
**Current:** 623 tests passing

---

## Test Philosophy

1. **Tests validate the intermediate JSON contract** — the 18-file interface between extraction and generation is the single source of truth. Both layers are tested independently against this contract.
2. **No live MicroStrategy server required** — all tests use mock API responses and fixture data. The `MockMstrRestClient` in conftest.py replaces the real REST client.
3. **Expression conversion is the highest-risk area** — parametrized tests cover every function mapping, level metric pattern, derived metric type, and ApplySimple SQL pattern.
4. **Generation output is validated structurally** — TMDL syntax, PBIR schema, and .pbip project structure are verified against expected output snapshots.
5. **Reference project**: TableauToPowerBI has 4,219 tests across 77 files. We target 2,000+ tests at maturity. Current: 623 tests across 15 test files.

---

## Test Infrastructure (Already Built)

### Fixture Data — `tests/fixtures/`

```
tests/fixtures/
├── mstr_api_responses/         # 12 files — mock MicroStrategy REST API responses
│   ├── projects.json           # 2 projects + auth token
│   ├── tables.json             # 6 tables (LU_CUSTOMER, LU_PRODUCT, LU_DATE, FACT_SALES, FACT_INVENTORY, VW_MONTHLY_SUMMARY)
│   ├── attributes.json         # 9 attributes with forms, geo roles, parent-child
│   ├── facts.json              # 5 facts with expressions, aggregation, format strings
│   ├── metrics.json            # 12 metrics (simple/compound/derived/level/ApplySimple)
│   ├── reports.json            # 3 reports (grid, graph, grid+derived)
│   ├── dossiers.json           # 1 dossier, 2 chapters, 3 pages, 11 visualizations
│   ├── cubes.json              # 1 cube with 5 attrs, 4 metrics
│   ├── prompts.json            # 6 prompts (element, value, object, date, expression)
│   ├── security_filters.json   # 3 security filters with user/group assignments
│   ├── hierarchies.json        # 3 hierarchies (Time, Geography, Product)
│   └── search_results.json     # Custom group search result
│
├── intermediate_json/          # 18 files — expected extraction output / generation input
│   ├── datasources.json        # 5 tables
│   ├── attributes.json         # 8 attributes
│   ├── facts.json              # 5 facts
│   ├── metrics.json            # 9 metrics (simple/compound)
│   ├── derived_metrics.json    # 3 derived metrics (Rank, RunningSum, Lag)
│   ├── reports.json            # 2 reports
│   ├── dossiers.json           # 1 dossier
│   ├── cubes.json              # 1 cube
│   ├── relationships.json      # 5 relationships
│   ├── hierarchies.json        # 3 hierarchies
│   ├── security_filters.json   # 2 security filters
│   ├── prompts.json            # 3 prompts
│   ├── freeform_sql.json       # 1 freeform SQL view
│   ├── custom_groups.json      # 1 custom group
│   ├── thresholds.json         # 1 threshold definition
│   ├── subtotals.json          # 2 subtotals
│   ├── filters.json            # empty (placeholder)
│   └── consolidations.json     # empty (placeholder)
│
└── expected_output/            # 4 files — expected generation output (TMDL snapshots)
    ├── LU_CUSTOMER.tmdl        # Table with columns, hierarchy, M partition
    ├── FACT_SALES.tmdl         # Table with hidden columns, 5 measures, M partition
    ├── relationships.tmdl      # 5 relationships
    └── roles.tmdl              # 2 RLS roles
```

**Total: 34 fixture files, 106,798 bytes, all validated.**

### Shared Configuration — `tests/conftest.py`

- `MockMstrRestClient` — full mock of all REST API methods
- 25+ `@pytest.fixture` functions loading each fixture file
- `all_intermediate_json` composite fixture for generation tests
- `output_dir` temporary directory fixture

---

## Test Categories

### 1. Unit Tests — Extraction Layer

Test each extraction module in isolation using mock API responses.

| Test File | Module Under Test | Key Scenarios | Target Count |
|-----------|-------------------|---------------|-------------|
| `test_rest_api_client.py` | `rest_api_client.py` | Auth (4 modes), token refresh, pagination, retry on 429/5xx, SSL, project selection, object search, error handling | 40+ |
| `test_schema_extractor.py` | `schema_extractor.py` | Table column mapping, attribute form extraction (ID/DESC/custom), fact expression parsing, geographic role detection, parent-child relationships, hierarchy level ordering, relationship inference (2 strategies), freeform SQL detection, custom group extraction | 50+ |
| `test_metric_extractor.py` | `metric_extractor.py` | Simple metric parsing, compound metric detection, derived metric classification (subtype check, OLAP keyword scan), expression text extraction (string/dict/token forms), aggregation detection, format string mapping, threshold extraction, folder path extraction | 30+ |
| `test_expression_converter.py` | `expression_converter.py` | **See dedicated section below** | 150+ |
| `test_report_extractor.py` | `report_extractor.py` | Grid row/column extraction, graph type mapping (25+ types), filter qualification parsing, sort extraction, subtotal definitions, page-by fields, threshold extraction, report type classification | 40+ |
| `test_dossier_extractor.py` | `dossier_extractor.py` | Chapter/page structure, 35+ viz type classification, PBI visual mapping (30+ types), data binding (attributes/metrics/rows/columns/color/size), formatting extraction, position extraction, panel stack handling, selector extraction, filter panel extraction, theme extraction, prompt extraction, info window extraction | 50+ |
| `test_advanced_extraction.py` | `cube_extractor.py`, `prompt_extractor.py`, `security_extractor.py` | Cube definition parsing, prompt type classification (6 types), prompt→PBI mapping, security filter expression extraction, user/group assignment parsing, graceful fallback on API errors | 40+ |
| `test_connection_mapper.py` | `connection_mapper.py` | All 15+ DB types → M query generation, freeform SQL → `Value.NativeQuery()`, schema handling, unknown type fallback to ODBC, parameter injection prevention | 30+ |
| `test_extract_orchestrator.py` | `extract_mstr_data.py` | Full extraction pipeline (online mode), offline mode (`from_export`), single report extraction, single dossier extraction, schema-only mode, JSON file writing, error recovery | 20+ |

#### Expression Converter Tests — Deep Dive

This is the highest-risk module (290 LOC, 60+ function mappings, 3 fidelity levels). Tests are organized by category:

| Category | Test Cases | Examples |
|----------|-----------|---------|
| **Aggregation functions** | 10 | `Sum(Revenue)` → `SUM(...)`, `Count(Distinct Customer)` → `DISTINCTCOUNT(...)`, `Median(...)`, `Percentile(...)` |
| **Level metrics** | 15 | `{~+, Year}` → `ALLEXCEPT`, `{!Region}` → `REMOVEFILTERS`, `{^}` → `ALL`, combined `{~+, Year, Region}`, nested level+agg |
| **Derived metrics** | 12 | `Rank(Sum(Revenue)) <Customer>` → `RANKX`, `RunningSum` → approximated, `Lag(x, 1)` → `OFFSET`, `Lead`, `NTile`, `MovingAvg` |
| **Conditional logic** | 8 | `If(cond, a, b)` → `IF(...)`, `Case/When` → `SWITCH(TRUE(), ...)` |
| **Null handling** | 8 | `NullToZero(x)` → `IF(ISBLANK(x), 0, x)`, `ZeroToNull`, `IsNull`, `IsNotNull` |
| **String functions** | 12 | `Concat`, `Length`→`LEN`, `SubStr`→`MID`, `Trim`, `Upper`, `Lower`, `Left`, `Right`, `Position` |
| **Date functions** | 15 | `CurrentDate`→`TODAY`, `Year/Month/Day`, `DaysBetween`→`DATEDIFF`, `MonthsBetween`, `YearsBetween`, `AddDays`, `DateAdd` |
| **Math functions** | 10 | `Power`, `Abs`, `Round`, `Ceiling`→`CEILING(x,1)`, `Floor`, `Ln`, `Log`, `Exp`, `Sqrt` |
| **ApplySimple patterns** | 15 | `CASE WHEN`→`SWITCH`, `COALESCE`→`COALESCE`, `NVL`→`IF(ISBLANK)`, `EXTRACT(YEAR)`→`YEAR(...)`, `TRUNC`→`TRUNC`, `CAST` |
| **ApplyAgg/ApplyComparison** | 5 | Flagged as manual_review |
| **Compound expressions** | 10 | `Revenue - Cost`, nested `NullToZero(Sum(x)/Count(y))`, multi-function chains |
| **Edge cases** | 10 | Empty expression, None input, unknown function, deeply nested, circular reference, very long expression |
| **Fidelity tracking** | 10 | Verify `fidelity` field = "full" / "approximated" / "manual_review", verify `warnings` populated correctly |

**Test pattern: `@pytest.mark.parametrize` with (mstr_expression, expected_dax, expected_fidelity) tuples.**

---

### 2. Unit Tests — Generation Layer

Test each generation module in isolation using intermediate JSON fixtures.

| Test File | Module Under Test | Key Scenarios | Target Count |
|-----------|-------------------|---------------|-------------|
| `test_tmdl_generator.py` | `tmdl_generator.py` | Table generation (column types, hidden keys, format strings), measure generation (DAX expressions, display folders), relationship output (cardinality, cross-filtering), hierarchy output (levels, ordering), RLS roles (filter expressions), calendar auto-table, **snapshot comparison against `expected_output/*.tmdl`** | 80+ |
| `test_visual_generator.py` | `visual_generator.py` | Page mapping (chapter→group, page→page), grid→tableEx/matrix, 30+ graph types→PBI charts, slicer/parameter generation, conditional formatting from thresholds, KPI/gauge/text, layout positioning (scaling), combo charts, data bindings (rows/columns/values/color/size) | 60+ |
| `test_m_query_generator.py` | `m_query_generator.py` | M partition for each table, all 15+ DB type connections, freeform SQL→NativeQuery, schema prefix handling, parameter safety | 35+ |
| `test_migration_report.py` | `migration_report.py` | JSON report structure, HTML report rendering, fidelity counts, per-object status, warning aggregation | 20+ |

---

### 3. Integration Tests

Test the full pipeline end-to-end without a live MicroStrategy server.

| Test File | Scope | What It Verifies |
|-----------|-------|-----------------|
| `test_integration_extraction.py` | Mock API → 18 JSON files | `MstrExtractor.extract_all()` with `MockMstrRestClient` produces all 18 intermediate JSON files with correct structure |
| `test_integration_generation.py` | 18 JSON files → `.pbip` project | `PowerBIImporter.import_all()` against intermediate fixtures produces complete `.pbip` with all expected files |
| `test_integration_pipeline.py` | Mock API → `.pbip` project | Full end-to-end: extract → generate → validate. Runs CLI with `--from-export` pointing at fixtures. |

**Test approach:**
1. Run extraction with `MockMstrRestClient`
2. Verify each of the 18 JSON output files exists and has correct top-level structure
3. Run generation against the output
4. Verify `.pbip` project structure (folders, files, manifests)
5. Validate TMDL syntax (indentation, keywords, required sections)
6. Validate PBIR visual JSON schema
7. Check migration report completeness

---

### 4. Validation Tests

| Test File | Scope | Key Scenarios |
|-----------|-------|---------------|
| `test_validator.py` | `validator.py` | Valid TMDL passes, invalid TMDL caught, valid PBIR passes, invalid visual JSON caught, relationship cycle detection (no cycle passes, cycle caught), DAX reference validation (valid refs pass, broken refs caught), missing required fields detected | 40+ |
| `test_assessment.py` | `assessment.py` | Object count accuracy, complexity scoring (simple project vs complex), unsupported feature detection, fidelity estimation | 20+ |

---

### 5. Snapshot/Regression Tests

**Purpose:** Catch unintended changes to generated output.

**Approach:**
- For each fixture scenario, generate output and compare against `tests/fixtures/expected_output/` files
- Currently 4 snapshot files: `LU_CUSTOMER.tmdl`, `FACT_SALES.tmdl`, `relationships.tmdl`, `roles.tmdl`
- **Expand to:** visual JSON snapshots, M query snapshots, full `.pbip` structure snapshot

**Update workflow:**
1. Run `pytest --snapshot-update` to regenerate snapshots
2. Review diff in git
3. Commit updated snapshots if changes are intentional

---

## Test Organization

```
tests/
├── __init__.py
├── conftest.py                      # Shared fixtures, MockMstrRestClient
├── fixtures/                        # Test data (34 files, see above)
│
├── unit/                            # Unit tests by layer
│   ├── __init__.py
│   ├── extraction/                  # Extraction layer tests
│   │   ├── __init__.py
│   │   ├── test_rest_api_client.py
│   │   ├── test_schema_extractor.py
│   │   ├── test_metric_extractor.py
│   │   ├── test_expression_converter.py  # 150+ parametrized tests
│   │   ├── test_report_extractor.py
│   │   ├── test_dossier_extractor.py
│   │   ├── test_advanced_extraction.py   # cubes, prompts, security
│   │   ├── test_connection_mapper.py
│   │   └── test_extract_orchestrator.py
│   │
│   └── generation/                  # Generation layer tests
│       ├── __init__.py
│       ├── test_tmdl_generator.py
│       ├── test_visual_generator.py
│       ├── test_m_query_generator.py
│       └── test_migration_report.py
│
├── integration/                     # End-to-end pipeline tests
│   ├── __init__.py
│   ├── test_integration_extraction.py
│   ├── test_integration_generation.py
│   └── test_integration_pipeline.py
│
└── validation/                      # Validator and assessment tests
    ├── __init__.py
    ├── test_validator.py
    └── test_assessment.py
```

---

## Coverage Requirements

| Module | Minimum | Rationale |
|--------|---------|-----------|
| `expression_converter.py` | **95%** | Highest risk — every unmapped function = broken measure in PBI |
| `schema_extractor.py` | **90%** | Foundation — wrong columns = broken everything downstream |
| `metric_extractor.py` | **85%** | Classification errors cascade into wrong DAX |
| `tmdl_generator.py` | **90%** | Invalid TMDL = .pbip won't open |
| `visual_generator.py` | **85%** | Wrong visuals are visible to users immediately |
| `connection_mapper.py` | **85%** | Wrong M query = no data |
| All other modules | **80%** | Project minimum |
| **Overall project** | **80%** | Set in `pyproject.toml` `fail_under=80` |

---

## Test Execution

### Local Development

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ -v --cov=microstrategy_export --cov=powerbi_import --cov-report=term-missing

# Run specific test category
python -m pytest tests/unit/extraction/ -v
python -m pytest tests/unit/generation/ -v
python -m pytest tests/integration/ -v

# Run expression converter tests only (high-value)
python -m pytest tests/unit/extraction/test_expression_converter.py -v

# Run with pattern matching
python -m pytest -k "level_metric" -v
python -m pytest -k "apply_simple" -v
```

### CI Pipeline (Future)

```yaml
# GitHub Actions workflow
- pytest tests/unit/ --cov --cov-fail-under=80
- pytest tests/integration/
- pytest tests/validation/
```

---

## Test Writing Guidelines

### Naming Convention

```python
def test_<module>_<function>_<scenario>():
    """Test that <function> handles <scenario> correctly."""

# Examples:
def test_expression_converter_sum_revenue():
def test_expression_converter_level_metric_allexcept():
def test_expression_converter_apply_simple_case_when():
def test_schema_extractor_attribute_forms_with_geo_role():
def test_tmdl_generator_measure_with_format_string():
```

### Parametrized Tests Pattern

```python
@pytest.mark.parametrize("mstr_expr, expected_dax, expected_fidelity", [
    ("Sum(Revenue)", "SUM('FACT_SALES'[REVENUE])", "full"),
    ("NullToZero(Sum(Revenue))", "IF(ISBLANK(SUM('FACT_SALES'[REVENUE])), 0, SUM('FACT_SALES'[REVENUE]))", "full"),
    ("Rank(Sum(Revenue)) <Customer>", "RANKX(ALL('LU_CUSTOMER'), [Total Revenue])", "approximated"),
    ('ApplySimple("DECODE(#1, 1, ''A'', ''B'')", Revenue)', None, "manual_review"),
])
def test_expression_conversion(mstr_expr, expected_dax, expected_fidelity):
    result = convert_mstr_expression_to_dax(mstr_expr, context={})
    assert result["fidelity"] == expected_fidelity
    if expected_dax:
        assert result["dax"] == expected_dax
```

### Fixture Usage Pattern

```python
def test_schema_extractor_tables(mock_client, api_tables):
    """Test table extraction produces correct intermediate format."""
    tables = extract_tables(mock_client)
    assert len(tables) == 6
    customer = next(t for t in tables if t["name"] == "LU_CUSTOMER")
    assert len(customer["columns"]) == 7
    assert customer["connection"]["db_type"] == "sql_server"

def test_tmdl_generator_customer_table(intermediate_datasources, intermediate_attributes):
    """Test TMDL generation for LU_CUSTOMER matches expected output."""
    tmdl = generate_table_tmdl("LU_CUSTOMER", intermediate_datasources, intermediate_attributes)
    expected = (FIXTURES_DIR / "expected_output" / "LU_CUSTOMER.tmdl").read_text()
    assert tmdl.strip() == expected.strip()
```

---

## Test Priority Order

When building tests, follow this order for maximum risk reduction:

| Priority | Tests | Why |
|----------|-------|-----|
| **P0** | `test_expression_converter.py` | Highest complexity, hardest to debug, most user-visible impact |
| **P0** | `test_tmdl_generator.py` | Invalid TMDL = project won't open |
| **P1** | `test_schema_extractor.py` | Foundation for all downstream |
| **P1** | `test_visual_generator.py` | User-visible output quality |
| **P1** | `test_connection_mapper.py` | No data = no value |
| **P2** | `test_metric_extractor.py` | Classification correctness |
| **P2** | `test_report_extractor.py` | Report structure accuracy |
| **P2** | `test_dossier_extractor.py` | Dossier structure accuracy |
| **P2** | `test_m_query_generator.py` | M query correctness |
| **P3** | `test_advanced_extraction.py` | Lower-frequency objects |
| **P3** | `test_rest_api_client.py` | HTTP layer (less business logic) |
| **P3** | Integration tests | Need generation layer first |
| **P3** | Validation tests | Need generation layer first |

---

## Metrics & Reporting

| Metric | Target | Tool |
|--------|--------|------|
| Line coverage | ≥80% overall | `pytest-cov` |
| Expression converter coverage | ≥95% | `pytest-cov` module filter |
| Test count | 800+ at Sprint C, 2000+ at v1.0 | `pytest --co -q | wc -l` |
| Test execution time | <30s for unit tests | `pytest --durations=10` |
| Snapshot drift | 0 unreviewed changes | Git diff on expected_output/ |
