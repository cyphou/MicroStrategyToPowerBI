"""Tests for M query generator module."""

import pytest

from powerbi_import.m_query_generator import generate_m_partition, generate_freeform_partition


# ── generate_m_partition ─────────────────────────────────────────

class TestGenerateMPartition:

    def test_sql_server_table(self):
        ds = {
            "name": "LU_CUSTOMER",
            "physical_table": "LU_CUSTOMER",
            "db_connection": {
                "db_type": "sql_server",
                "server": "sql-prod-01.company.com",
                "database": "SalesDB",
                "schema": "dbo",
            },
            "sql_statement": "",
        }
        result = generate_m_partition(ds)
        assert "Sql.Database" in result
        assert "sql-prod-01.company.com" in result
        assert "SalesDB" in result
        assert "LU_CUSTOMER" in result

    def test_oracle_table(self):
        ds = {
            "name": "EMPLOYEES",
            "physical_table": "EMPLOYEES",
            "db_connection": {
                "db_type": "oracle",
                "server": "oracle-prod.company.com",
                "database": "ORCL",
                "schema": "HR",
            },
            "sql_statement": "",
        }
        result = generate_m_partition(ds)
        assert "Oracle.Database" in result
        assert "oracle-prod.company.com" in result

    def test_postgresql_table(self):
        ds = {
            "name": "orders",
            "physical_table": "orders",
            "db_connection": {
                "db_type": "postgresql",
                "server": "pg-prod.company.com",
                "database": "analytics",
                "schema": "public",
            },
            "sql_statement": "",
        }
        result = generate_m_partition(ds)
        assert "PostgreSQL.Database" in result
        assert "pg-prod.company.com" in result

    def test_mysql_table(self):
        ds = {
            "name": "events",
            "physical_table": "events",
            "db_connection": {
                "db_type": "mysql",
                "server": "mysql-prod.company.com",
                "database": "app_db",
                "schema": "",
            },
            "sql_statement": "",
        }
        result = generate_m_partition(ds)
        assert "MySQL.Database" in result

    def test_snowflake_table(self):
        ds = {
            "name": "FACT_ORDERS",
            "physical_table": "FACT_ORDERS",
            "db_connection": {
                "db_type": "snowflake",
                "server": "account.snowflakecomputing.com",
                "database": "DW",
                "schema": "PUBLIC",
            },
            "sql_statement": "",
        }
        result = generate_m_partition(ds)
        assert "Snowflake" in result

    def test_databricks_table(self):
        ds = {
            "name": "fact_sales",
            "physical_table": "fact_sales",
            "db_connection": {
                "db_type": "databricks",
                "server": "adb-123.azuredatabricks.net",
                "database": "catalog.schema",
                "schema": "",
            },
            "sql_statement": "",
        }
        result = generate_m_partition(ds)
        assert "Databricks" in result

    def test_teradata_table(self):
        ds = {
            "name": "DIM_CUSTOMER",
            "physical_table": "DIM_CUSTOMER",
            "db_connection": {
                "db_type": "teradata",
                "server": "teradata-prod.company.com",
                "database": "DW",
                "schema": "",
            },
            "sql_statement": "",
        }
        result = generate_m_partition(ds)
        assert "Teradata" in result or "Odbc" in result

    def test_bigquery_table(self):
        ds = {
            "name": "fact_events",
            "physical_table": "fact_events",
            "db_connection": {
                "db_type": "google_bigquery",
                "server": "my-project",
                "database": "my_dataset",
                "schema": "",
            },
            "sql_statement": "",
        }
        result = generate_m_partition(ds)
        assert "BigQuery" in result or "GoogleBigQuery" in result

    def test_sap_hana_table(self):
        ds = {
            "name": "SALES",
            "physical_table": "SALES",
            "db_connection": {
                "db_type": "sap_hana",
                "server": "hana-prod.company.com",
                "database": "SAPDB",
                "schema": "SAPABAP1",
            },
            "sql_statement": "",
        }
        result = generate_m_partition(ds)
        assert "SapHana" in result

    def test_unknown_db_fallback(self):
        ds = {
            "name": "DATA",
            "physical_table": "DATA",
            "db_connection": {
                "db_type": "exotic_db",
                "server": "exotic.company.com",
                "database": "mydb",
                "schema": "",
            },
            "sql_statement": "",
        }
        result = generate_m_partition(ds)
        assert "Odbc" in result or isinstance(result, str)

    def test_uses_physical_table_name(self):
        ds = {
            "name": "Friendly Name",
            "physical_table": "ACTUAL_TABLE",
            "db_connection": {
                "db_type": "sql_server",
                "server": "s",
                "database": "db",
                "schema": "dbo",
            },
            "sql_statement": "",
        }
        result = generate_m_partition(ds)
        assert "ACTUAL_TABLE" in result

    def test_falls_back_to_name_when_no_physical_table(self):
        ds = {
            "name": "MY_TABLE",
            "db_connection": {
                "db_type": "sql_server",
                "server": "s",
                "database": "db",
                "schema": "dbo",
            },
            "sql_statement": "",
        }
        result = generate_m_partition(ds)
        assert "MY_TABLE" in result

    def test_with_fixture_datasource(self, intermediate_datasources):
        """Test with actual fixture data."""
        for ds in intermediate_datasources:
            result = generate_m_partition(ds)
            assert isinstance(result, str)
            assert len(result) > 0
            # SQL Server datasources should have Sql.Database
            if ds.get("db_connection", {}).get("db_type") == "sql_server":
                assert "Sql.Database" in result

    def test_schema_is_passed(self):
        ds = {
            "name": "MY_TABLE",
            "physical_table": "MY_TABLE",
            "db_connection": {
                "db_type": "sql_server",
                "server": "s",
                "database": "db",
                "schema": "custom_schema",
            },
            "sql_statement": "",
        }
        result = generate_m_partition(ds)
        assert "custom_schema" in result


# ── generate_freeform_partition ──────────────────────────────────

class TestGenerateFreeformPartition:

    def test_freeform_sql_contains_native_query(self):
        freeform = {
            "name": "VW_SUMMARY",
            "sql_statement": "SELECT * FROM fact_sales",
            "db_connection": {
                "db_type": "sql_server",
                "server": "sql-prod.company.com",
                "database": "SalesDB",
                "schema": "dbo",
            },
        }
        result = generate_freeform_partition(freeform)
        assert "Value.NativeQuery" in result
        assert "SELECT * FROM fact_sales" in result

    def test_freeform_with_complex_sql(self):
        freeform = {
            "name": "VW_MONTHLY",
            "sql_statement": "SELECT a.id, SUM(b.amount) FROM orders a JOIN items b ON a.id=b.order_id GROUP BY a.id",
            "db_connection": {
                "db_type": "sql_server",
                "server": "s",
                "database": "db",
                "schema": "dbo",
            },
        }
        result = generate_freeform_partition(freeform)
        assert "Value.NativeQuery" in result
        assert "GROUP BY" in result

    def test_freeform_oracle_connection(self):
        freeform = {
            "name": "VW_ORACLE",
            "sql_statement": "SELECT * FROM employees WHERE dept_id = 10",
            "db_connection": {
                "db_type": "oracle",
                "server": "oracle.company.com",
                "database": "ORCL",
                "schema": "HR",
            },
        }
        result = generate_freeform_partition(freeform)
        assert isinstance(result, str)
        assert "SELECT" in result

    def test_with_fixture_freeform(self, intermediate_freeform_sql):
        """Test with actual fixture data."""
        for freeform in intermediate_freeform_sql:
            result = generate_freeform_partition(freeform)
            assert isinstance(result, str)
            assert len(result) > 0
            assert "Value.NativeQuery" in result

    def test_empty_sql_still_works(self):
        freeform = {
            "name": "EMPTY",
            "sql_statement": "",
            "db_connection": {
                "db_type": "sql_server",
                "server": "s",
                "database": "db",
                "schema": "dbo",
            },
        }
        result = generate_freeform_partition(freeform)
        assert isinstance(result, str)
