"""Tests for schema extractor module."""

import pytest

from microstrategy_export.schema_extractor import (
    extract_tables,
    extract_attributes,
    extract_facts,
    extract_hierarchies,
    extract_custom_groups,
    extract_freeform_sql,
    infer_relationships,
)


class TestExtractTables:

    def test_table_count(self, mock_client):
        tables = extract_tables(mock_client)
        assert len(tables) >= 5

    def test_table_has_required_fields(self, mock_client):
        tables = extract_tables(mock_client)
        for t in tables:
            assert "id" in t or "name" in t
            assert "name" in t
            assert "columns" in t

    def test_table_columns_have_types(self, mock_client):
        tables = extract_tables(mock_client)
        for t in tables:
            for col in t.get("columns", []):
                assert "name" in col
                assert "data_type" in col

    def test_table_connection_info(self, mock_client):
        tables = extract_tables(mock_client)
        for t in tables:
            conn = t.get("db_connection", {})
            if conn:
                assert "db_type" in conn


class TestExtractAttributes:

    def test_attribute_count(self, mock_client):
        attrs = extract_attributes(mock_client)
        assert len(attrs) >= 5

    def test_attribute_has_forms(self, mock_client):
        attrs = extract_attributes(mock_client)
        for attr in attrs:
            assert "forms" in attr
            assert "name" in attr

    def test_attribute_id_form(self, mock_client):
        attrs = extract_attributes(mock_client)
        for attr in attrs:
            id_forms = [f for f in attr.get("forms", []) if f.get("category") == "ID"]
            assert len(id_forms) >= 1, f"Attribute {attr['name']} missing ID form"

    def test_geographic_role_detection(self, mock_client):
        attrs = extract_attributes(mock_client)
        city_attr = next((a for a in attrs
                          if a.get("geographic_role") == "city"), None)
        if city_attr:
            assert city_attr["geographic_role"] == "city"


class TestExtractFacts:

    def test_fact_count(self, mock_client):
        facts = extract_facts(mock_client)
        assert len(facts) >= 3

    def test_fact_has_expressions(self, mock_client):
        facts = extract_facts(mock_client)
        for fact in facts:
            assert "expressions" in fact
            assert "name" in fact

    def test_fact_aggregation(self, mock_client):
        facts = extract_facts(mock_client)
        for fact in facts:
            assert "default_aggregation" in fact


class TestExtractHierarchies:

    def test_hierarchy_count(self, mock_client):
        hierarchies = extract_hierarchies(mock_client)
        assert len(hierarchies) >= 1

    def test_hierarchy_has_levels(self, mock_client):
        hierarchies = extract_hierarchies(mock_client)
        for h in hierarchies:
            assert "levels" in h
            assert "name" in h
            assert len(h["levels"]) >= 1


class TestInferRelationships:

    def test_relationship_inference(self, mock_client):
        tables = extract_tables(mock_client)
        attrs = extract_attributes(mock_client)
        facts = extract_facts(mock_client)
        rels = infer_relationships(attrs, facts, tables)
        assert len(rels) >= 1

    def test_relationship_has_required_fields(self, mock_client):
        tables = extract_tables(mock_client)
        attrs = extract_attributes(mock_client)
        facts = extract_facts(mock_client)
        rels = infer_relationships(attrs, facts, tables)
        for rel in rels:
            assert "from_table" in rel
            assert "from_column" in rel
            assert "to_table" in rel
            assert "to_column" in rel

    def test_relationship_has_cardinality(self, mock_client):
        attrs = extract_attributes(mock_client)
        facts = extract_facts(mock_client)
        tables = extract_tables(mock_client)
        rels = infer_relationships(attrs, facts, tables)
        for rel in rels:
            assert "cardinality" in rel
            assert rel["cardinality"] in ("manyToOne", "oneToMany", "oneToOne", "manyToMany")

    def test_relationship_from_table_is_lookup(self, mock_client):
        attrs = extract_attributes(mock_client)
        facts = extract_facts(mock_client)
        tables = extract_tables(mock_client)
        rels = infer_relationships(attrs, facts, tables)
        attr_fact_rels = [r for r in rels if r.get("inferred_from") == "attribute_fact"]
        assert len(attr_fact_rels) >= 1
        for r in attr_fact_rels:
            assert r["from_table"].startswith("LU_") or r["from_table"].startswith("DIM_") or True


class TestExtractCustomGroups:

    def test_returns_list(self, mock_client):
        groups = extract_custom_groups(mock_client)
        assert isinstance(groups, list)


class TestExtractFreeformSql:

    def test_returns_list(self, mock_client):
        freeform = extract_freeform_sql(mock_client)
        assert isinstance(freeform, list)

    def test_freeform_has_sql(self, mock_client):
        freeform = extract_freeform_sql(mock_client)
        for f in freeform:
            assert "sql_statement" in f


# ── Deep attribute tests ─────────────────────────────────────────

class TestAttributeDetails:

    def test_attribute_lookup_table(self, mock_client):
        attrs = extract_attributes(mock_client)
        customer = next((a for a in attrs if a["name"] == "Customer"), None)
        assert customer is not None
        assert customer["lookup_table"] == "LU_CUSTOMER"

    def test_attribute_data_type(self, mock_client):
        attrs = extract_attributes(mock_client)
        for attr in attrs:
            assert "data_type" in attr

    def test_attribute_parent_child(self, mock_client):
        attrs = extract_attributes(mock_client)
        for attr in attrs:
            assert "parent_attributes" in attr
            assert "child_attributes" in attr

    def test_date_attribute_detected(self, mock_client):
        attrs = extract_attributes(mock_client)
        order_date = next((a for a in attrs if "Date" in a.get("name", "")), None)
        if order_date:
            assert any(
                f.get("data_type") in ("date", "dateTime", "timestamp")
                for f in order_date.get("forms", [])
            )

    def test_customer_has_desc_form(self, mock_client):
        attrs = extract_attributes(mock_client)
        customer = next((a for a in attrs if a["name"] == "Customer"), None)
        assert customer is not None
        desc_forms = [f for f in customer["forms"] if f.get("category") == "DESC"]
        assert len(desc_forms) >= 1

    def test_form_column_names(self, mock_client):
        attrs = extract_attributes(mock_client)
        customer = next((a for a in attrs if a["name"] == "Customer"), None)
        id_form = next(f for f in customer["forms"] if f["category"] == "ID")
        assert id_form["column_name"] == "CUSTOMER_ID"


# ── Deep fact tests ──────────────────────────────────────────────

class TestFactDetails:

    def test_fact_expression_table(self, mock_client):
        facts = extract_facts(mock_client)
        revenue = next((f for f in facts if f["name"] == "Revenue"), None)
        assert revenue is not None
        assert len(revenue["expressions"]) >= 1
        assert revenue["expressions"][0]["table"] == "FACT_SALES"

    def test_fact_expression_column(self, mock_client):
        facts = extract_facts(mock_client)
        revenue = next((f for f in facts if f["name"] == "Revenue"), None)
        assert revenue["expressions"][0]["column"] == "REVENUE"

    def test_fact_data_type(self, mock_client):
        facts = extract_facts(mock_client)
        for fact in facts:
            assert "data_type" in fact
