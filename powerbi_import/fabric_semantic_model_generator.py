"""
Fabric DirectLake semantic model generator.

Dedicated generator for DirectLake-mode semantic models that bind
directly to Lakehouse Delta tables.  Unlike the ``tmdl_generator.py``
``direct_lake=True`` flag (which is a thin wrapper), this module
produces:

- Expression-less tables with ``entityName`` partition bindings
- DirectLake-specific model properties
- Proper fallback annotations for DirectQuery
- Relationship definitions referencing Delta table keys
"""

import json
import logging
import os

from powerbi_import.fabric_constants import map_tmdl_type, sanitize_column_name
from powerbi_import.fabric_naming import sanitize_table_name

logger = logging.getLogger(__name__)


# ── Public API ───────────────────────────────────────────────────


def generate_direct_lake_model(data, output_dir, *,
                               lakehouse_name=None,
                               lakehouse_id=None,
                               workspace_id=None):
    """Generate a full DirectLake semantic model (TMDL files).

    Args:
        data: dict with intermediate JSON data (datasources, metrics,
              derived_metrics, relationships, freeform_sql).
        output_dir: Directory for TMDL output.
        lakehouse_name: Fabric Lakehouse name.
        lakehouse_id: Fabric Lakehouse item ID.
        workspace_id: Fabric workspace ID.

    Returns:
        dict with generation stats.
    """
    model_dir = os.path.join(output_dir, "definition", "model")
    tables_dir = os.path.join(model_dir, "tables")
    os.makedirs(tables_dir, exist_ok=True)

    datasources = data.get("datasources", [])
    metrics = data.get("metrics", [])
    derived_metrics = data.get("derived_metrics", [])
    relationships = data.get("relationships", [])
    freeform_sql = data.get("freeform_sql", [])

    # ── model.tmdl ───────────────────────────────────────────────
    model_lines = _build_model_tmdl(
        lakehouse_name=lakehouse_name,
        lakehouse_id=lakehouse_id,
        workspace_id=workspace_id,
    )
    _write(os.path.join(model_dir, "model.tmdl"), "\n".join(model_lines))

    # ── expression.tmdl (shared expression for Lakehouse binding) ─
    expr_lines = _build_expression_tmdl(
        lakehouse_name=lakehouse_name,
        lakehouse_id=lakehouse_id,
        workspace_id=workspace_id,
    )
    _write(os.path.join(model_dir, "expression.tmdl"), "\n".join(expr_lines))

    # ── per-table .tmdl files ────────────────────────────────────
    table_count = 0
    for ds in datasources:
        lines = _build_table_tmdl(ds, metrics, derived_metrics,
                                  lakehouse_name=lakehouse_name)
        table_name = sanitize_table_name(ds.get("physical_table") or ds["name"])
        _write(os.path.join(tables_dir, f"{table_name}.tmdl"), "\n".join(lines))
        table_count += 1

    for ffs in freeform_sql:
        lines = _build_freeform_table_tmdl(ffs, lakehouse_name=lakehouse_name)
        table_name = sanitize_table_name(ffs["name"])
        _write(os.path.join(tables_dir, f"{table_name}.tmdl"), "\n".join(lines))
        table_count += 1

    # ── relationships.tmdl ───────────────────────────────────────
    if relationships:
        rel_lines = _build_relationships_tmdl(relationships)
        _write(os.path.join(model_dir, "relationships.tmdl"), "\n".join(rel_lines))

    logger.info(
        "Generated DirectLake semantic model: %d tables, %d relationships",
        table_count, len(relationships),
    )
    return {
        "tables_generated": table_count,
        "relationships": len(relationships),
        "measures": len(metrics) + len(derived_metrics),
        "mode": "directLake",
        "model_dir": model_dir,
    }


# ── model.tmdl ───────────────────────────────────────────────────


def _build_model_tmdl(*, lakehouse_name=None, lakehouse_id=None,
                      workspace_id=None):
    """Build model.tmdl content for DirectLake."""
    lines = [
        "model Model",
        "\tculture: en-US",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        "\tsourceQueryCulture: en-US",
        "",
        "\tannotation __PBI_TimeIntelligenceEnabled = 0",
        "",
    ]
    if lakehouse_name:
        lines.append(f"\tannotation LakehouseName = {lakehouse_name}")
    if lakehouse_id:
        lines.append(f"\tannotation LakehouseId = {lakehouse_id}")
    if workspace_id:
        lines.append(f"\tannotation WorkspaceId = {workspace_id}")
    return lines


def _build_expression_tmdl(*, lakehouse_name=None, lakehouse_id=None,
                           workspace_id=None):
    """Build the shared expression for Lakehouse data source binding."""
    lh = lakehouse_name or "Lakehouse"
    lines = [
        f'expression DatabaseQuery = let',
        f'\tdatabase = Sql.Database("placeholder", "{lh}")',
        f'in',
        f'\tdatabase',
        f'',
        f'\tannotation PBI_NavigationStepName = Navigation',
        f'\tannotation PBI_ResultType = Table',
    ]
    if lakehouse_id:
        lines.append(f"\tannotation LakehouseId = {lakehouse_id}")
    if workspace_id:
        lines.append(f"\tannotation WorkspaceId = {workspace_id}")
    return lines


# ── Table TMDL ───────────────────────────────────────────────────


def _build_table_tmdl(ds, metrics, derived_metrics, *, lakehouse_name=None):
    """Build a DirectLake table TMDL from a datasource dict."""
    table_name = ds.get("physical_table") or ds["name"]
    display_name = ds["name"]
    columns = ds.get("columns", [])

    lines = [f"table {display_name}"]
    lines.append(f"\tlineageTag: {_tag(display_name)}")
    lines.append("")

    # Columns
    for col in columns:
        col_name = col["name"]
        tmdl_type = map_tmdl_type(col.get("data_type", "string"))
        lines.append(f"\tcolumn {col_name}")
        lines.append(f"\t\tdataType: {tmdl_type}")
        lines.append(f"\t\tlineageTag: {_tag(f'{display_name}_{col_name}')}")
        lines.append(f"\t\tsummarizeBy: none")
        lines.append(f"\t\tsourceColumn: {col_name}")
        lines.append("")

    # Measures from metrics for this table
    table_metrics = [m for m in metrics
                     if m.get("table", "") == display_name]
    table_derived = [m for m in derived_metrics
                     if m.get("table", "") == display_name]

    for m in table_metrics + table_derived:
        expr = m.get("expression", m.get("dax_expression", ""))
        lines.append(f"\tmeasure {m['name']} = {expr}")
        lines.append(f"\t\tlineageTag: {_tag(m['name'])}")
        if m.get("format_string"):
            lines.append(f"\t\tformatString: {m['format_string']}")
        lines.append("")

    # DirectLake partition
    entity_name = sanitize_table_name(table_name)
    lines.append(f"\tpartition {display_name} = entity")
    lines.append("\t\tmode: directLake")
    lines.append(f"\t\tentityName: {entity_name}")
    lines.append(f"\t\tschemaName: dbo")
    if lakehouse_name:
        lines.append(f"\t\tannotation LakehouseName = {lakehouse_name}")
    lines.append("")

    return lines


def _build_freeform_table_tmdl(ffs, *, lakehouse_name=None):
    """Build a DirectLake table for a freeform SQL source."""
    table_name = ffs["name"]
    columns = ffs.get("columns", [])

    lines = [f"table {table_name}"]
    lines.append(f"\tlineageTag: {_tag(table_name)}")
    lines.append("")

    for col in columns:
        col_name = col["name"]
        tmdl_type = map_tmdl_type(col.get("data_type", "string"))
        lines.append(f"\tcolumn {col_name}")
        lines.append(f"\t\tdataType: {tmdl_type}")
        lines.append(f"\t\tlineageTag: {_tag(f'{table_name}_{col_name}')}")
        lines.append(f"\t\tsummarizeBy: none")
        lines.append(f"\t\tsourceColumn: {col_name}")
        lines.append("")

    entity_name = sanitize_table_name(table_name)
    lines.append(f"\tpartition {table_name} = entity")
    lines.append("\t\tmode: directLake")
    lines.append(f"\t\tentityName: {entity_name}")
    lines.append(f"\t\tschemaName: dbo")
    if lakehouse_name:
        lines.append(f"\t\tannotation LakehouseName = {lakehouse_name}")
    lines.append("")

    return lines


# ── Relationships ────────────────────────────────────────────────


def _build_relationships_tmdl(relationships):
    """Build relationships.tmdl content."""
    lines = []
    for i, rel in enumerate(relationships):
        from_table = rel.get("from_table", "")
        from_col = rel.get("from_column", "")
        to_table = rel.get("to_table", "")
        to_col = rel.get("to_column", "")
        cardinality = rel.get("cardinality", "manyToOne")

        rel_id = _tag(f"rel_{from_table}_{to_table}_{i}")
        lines.append(f"relationship {rel_id}")
        lines.append(f"\tcrossFilteringBehavior: singleDirection")
        lines.append(f"\tfromCardinality: {_from_cardinality(cardinality)}")
        lines.append(f"\tfromColumn: {from_table}.{from_col}")
        lines.append(f"\ttoColumn: {to_table}.{to_col}")
        lines.append("")
    return lines


# ── Helpers ──────────────────────────────────────────────────────


def _tag(name):
    """Generate a deterministic lineage tag from a name."""
    import hashlib
    return hashlib.md5(name.encode()).hexdigest()[:16]


def _from_cardinality(card):
    """Map relationship cardinality string to TMDL enum."""
    mapping = {
        "manyToOne": "many",
        "oneToMany": "one",
        "manyToMany": "many",
        "oneToOne": "one",
    }
    return mapping.get(card, "many")


def _write(path, content):
    """Write text content to a file, creating directories as needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
