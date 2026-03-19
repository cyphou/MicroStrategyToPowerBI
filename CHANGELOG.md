# Changelog

All notable changes to this project will be documented in this file.

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
