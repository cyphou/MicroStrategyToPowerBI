"""Tests for connection mapper module."""

import pytest

from microstrategy_export.connection_mapper import map_connection_to_m_query


# ── SQL Server ───────────────────────────────────────────────────

class TestSqlServer:

    def test_basic_connection(self):
        conn = {"db_type": "sql_server", "server": "myserver", "database": "mydb", "schema": "dbo"}
        result = map_connection_to_m_query(conn, table_name="MyTable", schema="dbo")
        assert 'Sql.Database("myserver", "mydb")' in result
        assert 'Schema="dbo"' in result
        assert 'Item="MyTable"' in result

    def test_default_schema(self):
        conn = {"db_type": "sql_server", "server": "srv", "database": "db"}
        result = map_connection_to_m_query(conn, table_name="T1")
        assert 'Schema="dbo"' in result

    def test_freeform_sql(self):
        conn = {"db_type": "sql_server", "server": "srv", "database": "db"}
        result = map_connection_to_m_query(conn, sql_statement="SELECT * FROM T1")
        assert "Value.NativeQuery" in result
        assert "SELECT * FROM T1" in result

    def test_mssql_variant(self):
        conn = {"db_type": "mssql", "server": "srv", "database": "db", "schema": "dbo"}
        result = map_connection_to_m_query(conn, table_name="T1")
        assert "Sql.Database" in result


# ── Oracle ───────────────────────────────────────────────────────

class TestOracle:

    def test_basic_oracle(self):
        conn = {"db_type": "oracle", "server": "orasrv", "database": "ORCL"}
        result = map_connection_to_m_query(conn, table_name="EMP", schema="HR")
        assert "Oracle.Database" in result


# ── PostgreSQL ───────────────────────────────────────────────────

class TestPostgreSQL:

    def test_basic_postgres(self):
        conn = {"db_type": "postgresql", "server": "pgsrv", "database": "mydb"}
        result = map_connection_to_m_query(conn, table_name="users", schema="public")
        assert "PostgreSQL.Database" in result


# ── MySQL ────────────────────────────────────────────────────────

class TestMySQL:

    def test_basic_mysql(self):
        conn = {"db_type": "mysql", "server": "mysqlsrv", "database": "mydb"}
        result = map_connection_to_m_query(conn, table_name="orders")
        assert "MySQL.Database" in result


# ── Cloud warehouses ─────────────────────────────────────────────

class TestCloudWarehouses:

    def test_snowflake(self):
        conn = {"db_type": "snowflake", "server": "account.snowflakecomputing.com", "database": "mydb"}
        result = map_connection_to_m_query(conn, table_name="T1", schema="PUBLIC")
        assert "Snowflake" in result

    def test_databricks(self):
        conn = {"db_type": "databricks", "server": "workspace.cloud.databricks.com", "database": "catalog"}
        result = map_connection_to_m_query(conn, table_name="T1")
        assert "Databricks" in result

    def test_bigquery(self):
        conn = {"db_type": "bigquery", "server": "myproject", "database": "dataset"}
        result = map_connection_to_m_query(conn, table_name="T1")
        assert "BigQuery" in result or "GoogleBigQuery" in result


# ── Teradata ─────────────────────────────────────────────────────

class TestTeradata:

    def test_basic_teradata(self):
        conn = {"db_type": "teradata", "server": "tdsrv", "database": "mydb"}
        result = map_connection_to_m_query(conn, table_name="T1")
        assert "Teradata" in result


# ── SAP HANA ─────────────────────────────────────────────────────

class TestSapHana:

    def test_basic_sap_hana(self):
        conn = {"db_type": "sap_hana", "server": "hana01", "database": "HDB"}
        result = map_connection_to_m_query(conn, table_name="T1")
        assert "SapHana" in result


# ── Fallback ─────────────────────────────────────────────────────

class TestFallback:

    def test_unknown_type_uses_odbc(self):
        conn = {"db_type": "some_unknown_db", "server": "srv", "database": "db"}
        result = map_connection_to_m_query(conn, table_name="T1")
        assert "Odbc" in result

    def test_empty_connection(self):
        conn = {}
        result = map_connection_to_m_query(conn, table_name="T1")
        assert result  # Should return something, not crash


# ── Output format ────────────────────────────────────────────────

class TestOutputFormat:

    def test_let_in_structure(self):
        conn = {"db_type": "sql_server", "server": "srv", "database": "db"}
        result = map_connection_to_m_query(conn, table_name="T1")
        assert result.strip().startswith("let")
        assert "in" in result
        assert "Table" in result

    def test_multiline_output(self):
        conn = {"db_type": "sql_server", "server": "srv", "database": "db"}
        result = map_connection_to_m_query(conn, table_name="T1")
        lines = result.strip().split('\n')
        assert len(lines) >= 3
