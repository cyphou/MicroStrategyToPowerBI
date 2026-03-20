# MicroStrategy Example Projects

Four pre-built intermediate JSON projects at increasing complexity levels for testing, demos, and development.

## Complexity Levels

| Level | Tables | Attributes | Facts | Metrics | Reports | Dossiers | Special Features |
|-------|--------|-----------|-------|---------|---------|----------|------------------|
| **Simple** | 1 | 2 | 2 | 3 | 1 grid | 0 | Minimal baseline |
| **Medium** | 3 | 8 | 5 | 10+2 derived | 3 (grid/graph/grid+graph) | 1 (KPIs + charts) | Hierarchies, relationships |
| **Complex** | 6 | 15 | 10 | 18+7 OLAP derived | 5 | 3 | RLS, prompts, thresholds, freeform SQL, custom groups, scorecards |
| **Ultra Complex** | 12 | 30 | 20 | 40+20 OLAP derived | 15 | 8 | Multi-source (Oracle+SQL Server+Snowflake), panel stacks, selectors, info windows, 2 scorecards, freeform SQL, consolidations |

## Directory Structure

Each example contains the standard 18 intermediate JSON files:

```
examples/<level>/
  datasources.json       # Database connections and tables
  attributes.json        # Dimension attributes
  facts.json             # Numeric facts
  metrics.json           # Simple/compound metrics
  derived_metrics.json   # OLAP/derived metrics (Rank, RunningSum, Lag, etc.)
  reports.json           # Grid/graph report definitions
  dossiers.json          # Dashboard definitions
  cubes.json             # Intelligent Cube definitions
  prompts.json           # Prompt → slicer/parameter mappings
  hierarchies.json       # Attribute hierarchies
  relationships.json     # Table relationships
  security_filters.json  # RLS filter definitions
  freeform_sql.json      # Custom SQL pass-through
  filters.json           # Report filters
  consolidations.json    # Consolidation objects
  custom_groups.json     # Custom group definitions
  subtotals.json         # Subtotal configurations
  thresholds.json        # Conditional formatting rules
  scorecards.json        # (complex/ultra_complex only)
```

## Usage

### Run migration on an example

```bash
python migrate.py --input examples/medium/ --output output/medium_pbip/
```

### Run assessment on an example

```bash
python migrate.py --input examples/complex/ --assess
```

### Regenerate examples

```bash
python examples/generate_examples.py
```

## Scenario Details

### Simple — "My First Migration"
Single `ORDERS` table with Product Name, Amount, Quantity. Three basic metrics (Total Sales, Total Quantity, Avg Price) and one grid report. Ideal for quick migration tests.

### Medium — "Sales Analytics"
Classic star schema with Customer, Product, and Sales tables. Includes geographic hierarchy (Region → City → Customer), product hierarchy, 2 derived metrics (Revenue Rank, Running Revenue), 3 report types, and a KPI dossier dashboard.

### Complex — "Enterprise Sales"
Oracle-based star schema with 6 dimension/fact tables. Features: OLAP derived metrics (Rank, RunningSum, Lag, MovingAvg, NTile), row-level security, value/element prompts, thresholds, custom groups (Customer Tier), freeform SQL view, 3 dossiers with various chart types, and a sales performance scorecard.

### Ultra Complex — "Global Enterprise Analytics"
Multi-source (Oracle + SQL Server + Snowflake) implementation with 12 tables covering sales, returns, inventory, web analytics, and marketing. Features: 20 OLAP derived metrics (including ApplyOLAP expressions), panel stacks, selectors, info windows, 2 scorecards with balanced perspectives, 2 freeform SQL views, 3 RLS filters, custom groups with complex expressions, 15 reports, and 8 dossiers.
