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
- See `docs/DEVELOPMENT_PLAN.md` for the 15-sprint roadmap
- See `docs/MAPPING_REFERENCE.md` for all MSTR→PBI mapping tables

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
- Generation modules consume only the intermediate JSON files (decoupled from extraction)
- See `docs/DEVELOPMENT_PLAN.md` for the 15-sprint roadmap
- See `docs/MAPPING_REFERENCE.md` for all MSTR→PBI mapping tables
