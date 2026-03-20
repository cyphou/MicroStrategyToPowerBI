"""
Microsoft Purview integration for migrated Power BI assets.

Registers semantic models, tables, columns, and measures in a Microsoft
Purview account using the Apache Atlas REST API.  Maps MicroStrategy
security-filter attributes to Purview sensitivity labels and propagates
classification metadata to Power BI columns.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

# ── Sensitivity label mapping ────────────────────────────────────

_DEFAULT_CLASSIFICATION_MAP = {
    # Common MSTR security-filter attribute patterns → Purview labels
    "ssn": "Highly Confidential",
    "social_security": "Highly Confidential",
    "credit_card": "Highly Confidential",
    "salary": "Confidential",
    "compensation": "Confidential",
    "revenue": "Confidential",
    "profit": "Confidential",
    "email": "General",
    "phone": "General",
    "address": "General",
    "name": "General",
}


# ── Purview payload builders ─────────────────────────────────────

def build_purview_entities(data, *, qualified_name_prefix="powerbi://"):
    """Build Apache Atlas entity payloads for Purview registration.

    Args:
        data: dict with intermediate JSON keys (datasources, attributes,
              facts, metrics, derived_metrics, security_filters)
        qualified_name_prefix: URI prefix for qualified names

    Returns:
        dict with {"entities": [...]} suitable for Atlas REST POST
    """
    entities = []

    datasources = data.get("datasources", [])
    attributes = data.get("attributes", [])
    facts = data.get("facts", [])
    metrics = data.get("metrics", [])
    derived_metrics = data.get("derived_metrics", [])
    security_filters = data.get("security_filters", [])

    # Compute classification map from security filters
    classifications = _build_classification_map(security_filters, attributes)

    # Semantic model entity
    sm_qn = f"{qualified_name_prefix}semantic_model"
    entities.append({
        "typeName": "powerbi_semantic_model",
        "attributes": {
            "qualifiedName": sm_qn,
            "name": "Migrated Semantic Model",
            "description": "Auto-generated from MicroStrategy migration",
        },
        "classifications": [],
    })

    # Table entities
    for ds in datasources:
        table_qn = f"{qualified_name_prefix}tables/{ds['name']}"
        entities.append({
            "typeName": "powerbi_table",
            "attributes": {
                "qualifiedName": table_qn,
                "name": ds["name"],
                "description": f"Migrated from warehouse table {ds.get('physical_table', ds['name'])}",
            },
            "relationshipAttributes": {
                "semanticModel": {"qualifiedName": sm_qn},
            },
            "classifications": [],
        })

        # Column entities
        for col in ds.get("columns", []):
            col_qn = f"{qualified_name_prefix}tables/{ds['name']}/columns/{col['name']}"
            col_entity = {
                "typeName": "powerbi_column",
                "attributes": {
                    "qualifiedName": col_qn,
                    "name": col["name"],
                    "dataType": col.get("data_type", "string"),
                },
                "relationshipAttributes": {
                    "table": {"qualifiedName": table_qn},
                },
                "classifications": [],
            }

            # Apply sensitivity labels
            label = classifications.get(col["name"].lower())
            if label:
                col_entity["classifications"].append({
                    "typeName": "Microsoft.Label",
                    "attributes": {"label": label},
                })

            entities.append(col_entity)

    # Measure entities
    for metric in metrics + derived_metrics:
        m_qn = f"{qualified_name_prefix}measures/{metric['name']}"
        entities.append({
            "typeName": "powerbi_measure",
            "attributes": {
                "qualifiedName": m_qn,
                "name": metric["name"],
                "expression": metric.get("expression", ""),
                "description": metric.get("description", ""),
            },
            "relationshipAttributes": {
                "semanticModel": {"qualifiedName": sm_qn},
            },
            "classifications": [],
        })

    logger.info("Built %d Purview entities", len(entities))
    return {"entities": entities}


def build_lineage_edges(graph, *, qualified_name_prefix="powerbi://"):
    """Build Purview lineage process entities from the lineage graph.

    Args:
        graph: LineageGraph instance
        qualified_name_prefix: URI prefix

    Returns:
        dict with {"entities": [...]} of process entities representing lineage edges
    """
    processes = []
    for i, edge in enumerate(graph.edges):
        if edge.relationship == "migrated_to":
            src = graph.get_node(edge.source_id)
            tgt = graph.get_node(edge.target_id)
            if src and tgt:
                processes.append({
                    "typeName": "Process",
                    "attributes": {
                        "qualifiedName": f"{qualified_name_prefix}lineage/process_{i}",
                        "name": f"Migration: {src.name} → {tgt.name}",
                    },
                    "relationshipAttributes": {
                        "inputs": [{"qualifiedName": f"{qualified_name_prefix}{_entity_path(src)}"}],
                        "outputs": [{"qualifiedName": f"{qualified_name_prefix}{_entity_path(tgt)}"}],
                    },
                })
    return {"entities": processes}


def _entity_path(node):
    """Build a qualified-name path segment from a lineage node."""
    if node.layer == "source":
        return f"sources/{node.name}"
    if node.layer.startswith("pbi_table"):
        return f"tables/{node.name}"
    if node.layer == "pbi_column":
        table = node.metadata.get("table", "")
        return f"tables/{table}/columns/{node.name}"
    if node.layer == "pbi_measure":
        return f"measures/{node.name}"
    return f"objects/{node.name}"


def _build_classification_map(security_filters, attributes):
    """Map column names to sensitivity labels based on security filters.

    If a column is protected by a security filter, assign it a label.
    Also applies default pattern-based classification.
    """
    col_labels = {}

    # From security filters: any filtered attribute → Confidential
    attr_by_id = {a["id"]: a for a in attributes}
    for sf in security_filters:
        for target in sf.get("target_attributes", []):
            attr = attr_by_id.get(target.get("id", ""))
            if attr:
                for form in attr.get("forms", []):
                    col = form.get("column_name", "")
                    if col:
                        col_labels[col.lower()] = "Confidential"

    # Default pattern-based classification
    for pattern, label in _DEFAULT_CLASSIFICATION_MAP.items():
        col_labels.setdefault(pattern, label)

    return col_labels


# ── Purview REST API client ──────────────────────────────────────

class PurviewClient:
    """Lightweight client for Microsoft Purview Atlas REST API.

    Requires: pip install requests
    Authentication: managed identity or service principal token.
    """

    def __init__(self, account_name, *, token=None):
        self.account_name = account_name
        self.base_url = f"https://{account_name}.purview.azure.com"
        self._token = token

    def _headers(self):
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def register_entities(self, payload):
        """POST entities to the Atlas bulk API.

        Args:
            payload: dict from build_purview_entities()

        Returns:
            dict with API response or error info
        """
        import requests  # deferred import — optional dependency

        url = f"{self.base_url}/catalog/api/atlas/v2/entity/bulk"
        resp = requests.post(url, headers=self._headers(),
                             json=payload, timeout=60)
        if resp.status_code in (200, 201):
            logger.info("Registered %d entities in Purview",
                        len(payload.get("entities", [])))
            return resp.json()

        logger.error("Purview registration failed: %d %s",
                     resp.status_code, resp.text[:200])
        return {"error": resp.status_code, "message": resp.text[:500]}

    def register_lineage(self, payload):
        """Register lineage process entities."""
        return self.register_entities(payload)


# ── File-based export (offline mode) ────────────────────────────

def export_purview_payload(payload, output_path):
    """Write Purview entity payload to a JSON file for offline review.

    Args:
        payload: dict from build_purview_entities()
        output_path: Path for the output .json file
    """
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2)
    logger.info("Purview payload exported to %s (%d entities)",
                output_path, len(payload.get("entities", [])))
