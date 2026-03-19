# Contributing

Thanks for your interest in contributing to the MicroStrategy to Power BI migration tool!

## Getting Started

```bash
git clone https://github.com/cyphou/MicroStrategyToPowerBI.git
cd MicroStrategyToPowerBI
pip install -r requirements.txt
pip install -e ".[dev]"
python -m pytest tests/ -q
```

## Development Workflow

1. **Create a branch** from `main` for your feature or fix
2. **Write tests first** — see [docs/TEST_STRATEGY.md](docs/TEST_STRATEGY.md) for guidelines
3. **Run the full suite** before submitting: `python -m pytest tests/ -v`
4. **Keep changes focused** — one feature or fix per PR

## Code Style

- Python 3.9+, type hints on public APIs
- Module-level `logger = logging.getLogger(__name__)` in every module
- Private helpers prefixed with `_`
- Constants as module-level `_UPPER_SNAKE` variables
- JSON intermediate files written via `_write_json(filename, data)` pattern

## Architecture

The project follows a **2-step pipeline**:

1. **Extract** (`microstrategy_export/`) — MicroStrategy REST API → 18 intermediate JSON files
2. **Generate** (`powerbi_import/`) — JSON → `.pbip` project (PBIR v4.0 + TMDL)

Extraction and generation are **fully decoupled** — generation modules only consume intermediate JSON.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full design.

## Multi-Agent Development

6 specialized Copilot agents handle domain-specific work. When opening a PR, tag the relevant agent:

| Agent | Domain |
|-------|--------|
| `@extraction` | REST API, schema/report/dossier extraction |
| `@expression` | MSTR→DAX conversion, function mappings |
| `@generation` | TMDL, visuals, .pbip, M queries, deployment |
| `@testing` | Unit tests, fixtures, coverage |
| `@validation` | Assessment, fidelity scoring, reports |
| `@orchestrator` | CLI, config, cross-module coordination |

## Testing

- All new code must have tests
- Target **≥80% line coverage** overall, **≥95%** for expression converter
- Use fixtures in `tests/fixtures/` — never call real APIs in tests
- Run coverage: `python -m pytest tests/ --cov --cov-report=html`

## Commit Messages

Use conventional commits:

```
feat: add Snowflake connection mapping
fix: handle string dataType in attribute forms
test: add deeper metric extractor tests
docs: update DAX reference with OLAP functions
```
