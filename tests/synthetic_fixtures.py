"""
Synthetic fixture generator for scale and performance testing.

Generates large intermediate JSON datasets to exercise the generation
pipeline at scale (100+ tables, 1000+ metrics, 50+ reports).
"""

import json
import os
import random
import string

_DATA_TYPES = ["integer", "varchar", "decimal", "date", "datetime", "boolean"]
_AGG_TYPES = ["sum", "avg", "count", "min", "max", "distinctcount"]
_VIZ_TYPES = [
    "grid", "crosstab", "vertical_bar", "line", "pie", "scatter",
    "combo", "area", "treemap", "gauge", "kpi", "map",
]


def generate_synthetic_project(output_dir, *, n_tables=100, n_attrs_per_table=8,
                                n_facts_per_table=4, n_metrics=500,
                                n_derived=200, n_reports=30, n_dossiers=20):
    """Generate a synthetic intermediate JSON project for benchmarking.

    Args:
        output_dir: Where to write JSON files.
        n_tables: Number of tables/datasources.
        n_attrs_per_table: Attributes per table.
        n_facts_per_table: Facts per table.
        n_metrics: Number of simple metrics.
        n_derived: Number of derived metrics.
        n_reports: Number of reports.
        n_dossiers: Number of dossiers.

    Returns:
        dict with counts of generated objects.
    """
    os.makedirs(output_dir, exist_ok=True)

    table_names = [f"Table_{i:03d}" for i in range(n_tables)]
    all_attrs = []
    all_facts = []
    datasources = []

    for t_idx, tname in enumerate(table_names):
        columns = []
        t_attrs = []
        t_facts = []

        for a_idx in range(n_attrs_per_table):
            attr_name = f"Attr_{tname}_{a_idx:02d}"
            col_name = f"col_{attr_name.lower()}"
            t_attrs.append({
                "id": f"attr_{t_idx}_{a_idx}",
                "name": attr_name,
                "table_name": tname,
                "forms": [{"category": "ID", "column_name": col_name, "data_type": "integer"}],
            })
            columns.append({"name": col_name, "dataType": "integer"})
            all_attrs.append(t_attrs[-1])

        for f_idx in range(n_facts_per_table):
            fact_name = f"Fact_{tname}_{f_idx:02d}"
            col_name = f"col_{fact_name.lower()}"
            t_facts.append({
                "id": f"fact_{t_idx}_{f_idx}",
                "name": fact_name,
                "table_name": tname,
                "column_name": col_name,
                "data_type": "decimal",
            })
            columns.append({"name": col_name, "dataType": "decimal"})
            all_facts.append(t_facts[-1])

        datasources.append({
            "name": tname,
            "tables": [{"name": tname}],
            "columns": columns,
            "connection_type": "odbc",
            "connection_string": f"DSN=Benchmark;Database=test",
        })

    # Metrics
    metrics = []
    for m_idx in range(n_metrics):
        t_idx = m_idx % n_tables
        f_idx = m_idx % n_facts_per_table
        metrics.append({
            "id": f"metric_{m_idx}",
            "name": f"Metric_{m_idx:04d}",
            "metric_type": "simple",
            "aggregation": random.choice(_AGG_TYPES),
            "column_ref": all_facts[t_idx * n_facts_per_table + f_idx]["name"],
            "expression": "",
        })

    # Derived metrics
    derived = []
    for d_idx in range(n_derived):
        src = metrics[d_idx % n_metrics]["name"]
        derived.append({
            "id": f"derived_{d_idx}",
            "name": f"Derived_{d_idx:04d}",
            "metric_type": "derived",
            "expression": random.choice([
                f"RunningSum([{src}])",
                f"Rank([{src}])",
                f"Lag([{src}], 1)",
                f"MovingAvg([{src}], 3)",
                f"[{src}] / [{metrics[(d_idx + 1) % n_metrics]['name']}]",
            ]),
        })

    # Reports
    reports = []
    for r_idx in range(n_reports):
        t_idx = r_idx % n_tables
        row_attrs = [{"name": all_attrs[t_idx * n_attrs_per_table + i]["name"], "type": "attribute"}
                     for i in range(min(3, n_attrs_per_table))]
        rpt_metrics = [{"name": metrics[(r_idx * 3 + j) % n_metrics]["name"]}
                       for j in range(min(5, n_metrics))]
        reports.append({
            "id": f"report_{r_idx}",
            "name": f"Report_{r_idx:03d}",
            "report_type": "grid_graph",
            "grid": {"rows": row_attrs, "columns": []},
            "graph": {"type": "vertical_bar", "attributes_on_axis": row_attrs, "metrics_on_axis": rpt_metrics},
            "metrics": rpt_metrics,
        })

    # Dossiers
    dossiers = []
    for d_idx in range(n_dossiers):
        pages = []
        for p_idx in range(random.randint(2, 6)):
            vizs = []
            for v_idx in range(random.randint(3, 8)):
                t_idx = (d_idx * 10 + v_idx) % n_tables
                vizs.append({
                    "key": _random_id(),
                    "viz_type": random.choice(_VIZ_TYPES),
                    "name": f"Viz_{d_idx}_{p_idx}_{v_idx}",
                    "data": {
                        "attributes": [{"name": all_attrs[t_idx * n_attrs_per_table]["name"]}],
                        "metrics": [{"name": metrics[(d_idx * 5 + v_idx) % n_metrics]["name"]}],
                    },
                    "position": {"x": v_idx * 300, "y": 0, "width": 280, "height": 350},
                })
            pages.append({
                "key": _random_id(),
                "name": f"Page_{p_idx}",
                "visualizations": vizs,
                "selectors": [],
                "layout": {"width": 1920, "height": 1080},
            })
        dossiers.append({
            "id": f"dossier_{d_idx}",
            "name": f"Dossier_{d_idx:03d}",
            "chapters": [{"name": "Chapter 1", "pages": pages}],
        })

    # Relationships (chain tables)
    relationships = []
    for i in range(min(n_tables - 1, 50)):
        relationships.append({
            "from_table": table_names[i],
            "from_column": datasources[i]["columns"][0]["name"],
            "to_table": table_names[i + 1],
            "to_column": datasources[i + 1]["columns"][0]["name"],
            "cardinality": "many_to_one",
        })

    # Write all files
    data = {
        "datasources": datasources,
        "attributes": all_attrs,
        "facts": all_facts,
        "metrics": metrics,
        "derived_metrics": derived,
        "reports": reports,
        "dossiers": dossiers,
        "cubes": [],
        "filters": [],
        "prompts": [],
        "custom_groups": [],
        "consolidations": [],
        "hierarchies": [],
        "relationships": relationships,
        "security_filters": [],
        "freeform_sql": [],
        "thresholds": [],
        "subtotals": [],
    }

    for key, value in data.items():
        path = os.path.join(output_dir, f"{key}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(value, f, indent=2, ensure_ascii=False)

    return {
        "tables": n_tables,
        "attributes": len(all_attrs),
        "facts": len(all_facts),
        "metrics": n_metrics,
        "derived_metrics": n_derived,
        "reports": n_reports,
        "dossiers": n_dossiers,
        "relationships": len(relationships),
    }


def _random_id():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
