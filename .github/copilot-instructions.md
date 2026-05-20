<!-- Copilot instructions for the MicroStrategy to Power BI migration project -->

# Project: MicroStrategy to Power BI Migration

Automated migration of MicroStrategy artifacts to Power BI format.

## Architecture — Pipeline

```
MicroStrategy source → [microstrategy_export] → Extraction → [output, powerbi_import, test_output, test_output_nocal] → Power BI
```

## Project Structure

- **Source / Extraction**: `microstrategy_export/`
- **Target / Generation**: `output/`, `powerbi_import/`, `test_output/`, `test_output_nocal/`
- **Tests**: `tests/` (46 test files)
- **Docs**: `docs/`

## Key Modules

- **Extraction**:
  - `microstrategy_export\__init__.py`
  - `microstrategy_export\change_detector.py`
  - `microstrategy_export\connection_mapper.py`
  - `microstrategy_export\cube_extractor.py`
  - `microstrategy_export\dossier_extractor.py`
  - `microstrategy_export\expression_converter.py`
  - `microstrategy_export\extract_mstr_data.py`
  - `microstrategy_export\incremental.py`
  - `microstrategy_export\metric_extractor.py`
  - `microstrategy_export\parallel.py`
  - `microstrategy_export\prompt_extractor.py`
  - `microstrategy_export\realtime_extractor.py`
  - `microstrategy_export\report_extractor.py`
  - `microstrategy_export\rest_api_client.py`
  - `microstrategy_export\schema_extractor.py`
  - ... and 2 more
- **Generation**:
  - `examples\generate_examples.py`
  - `powerbi_import\__init__.py`
  - `powerbi_import\ai_converter.py`
  - `powerbi_import\alerts_generator.py`
  - `powerbi_import\assessment.py`
  - `powerbi_import\calc_column_utils.py`
  - `powerbi_import\certification.py`
  - `powerbi_import\comparison_report.py`
  - `powerbi_import\dashboard.py`
  - `powerbi_import\dataflow_generator.py`
  - `powerbi_import\dax_optimizer.py`
  - `powerbi_import\dax_recipes.py`
  - `powerbi_import\deploy\__init__.py`
  - `powerbi_import\deploy\auth.py`
  - `powerbi_import\deploy\bundle_deployer.py`
  - ... and 53 more
- **Orchestration**:
  - `migrate.py`
  - `wizard.py`
- **Utilities**:
  - `scripts\scheduled_migration.py`
  - `universal_bi\__init__.py`
  - `universal_bi\adapters\__init__.py`
  - `universal_bi\adapters\mstr_adapter.py`
  - `universal_bi\adapters\tableau_adapter.py`
  - `universal_bi\cross_lineage.py`
  - `universal_bi\schema.py`

## Hard Constraints

1. **Read before write** — never assume file contents from memory
2. **Test after every change** — run `pytest tests/ --tb=short -q`
3. **No duplicate functions** — always search for an existing name before creating one
4. **Git hygiene** — commit only when tests pass, conventional messages (`feat:`, `fix:`, `test:`, `docs:`)

## Multi-Agent Architecture

This project uses a specialized agent architecture. See `docs/AGENTS.md` for the full
architecture diagram and `.github/agents/` for per-agent definitions.

## Workflow Rules

### 1. Plan Before Build
- For multi-step work, create a plan before starting
- If something goes sideways, STOP and re-plan

### 2. Read Before Write
- **Always read target code before editing**
- Read `copilot-instructions.md` at session start for project rules

### 3. Testing Contract
- Run `pytest tests/ --tb=short -q` after EVERY implementation change
- If tests fail → fix them before reporting completion
- New features **require** new tests
- Never weaken test assertions to make tests pass

### 4. Scope Discipline
- Only modify files directly related to the task
- No drive-by refactors
- Prefer the smallest change that solves the problem
