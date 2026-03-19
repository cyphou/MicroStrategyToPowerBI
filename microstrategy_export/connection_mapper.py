"""
Warehouse connection mapper for MicroStrategy.

Maps MicroStrategy warehouse database connection types to
Power Query M connection expressions.
"""

import logging

logger = logging.getLogger(__name__)


def map_connection_to_m_query(connection_info, table_name=None, schema=None, sql_statement=None):
    """Generate a Power Query M expression for a warehouse connection.

    Args:
        connection_info: dict with db_type, server, database, schema
        table_name: Physical table name
        schema: Database schema name
        sql_statement: Optional freeform SQL to use instead of table reference

    Returns:
        str: Power Query M expression
    """
    db_type = (connection_info.get("db_type", "") or "").lower()
    server = connection_info.get("server", "")
    database = connection_info.get("database", "")
    schema = schema or connection_info.get("schema", "")

    # Freeform SQL → Value.NativeQuery
    if sql_statement:
        source_expr = _get_source_expression(db_type, server, database)
        return _build_native_query(source_expr, sql_statement)

    # Standard table reference
    generator = _CONNECTION_MAP.get(db_type, _generate_odbc)
    return generator(server, database, schema, table_name)


# ── Connection generators ────────────────────────────────────────

def _generate_sql_server(server, database, schema, table_name):
    """Generate M for SQL Server."""
    lines = [
        'let',
        f'    Source = Sql.Database("{server}", "{database}"),',
    ]
    if schema and table_name:
        lines.append(f'    Table = Source{{[Schema="{schema}", Item="{table_name}"]}}[Data]')
    elif table_name:
        lines.append(f'    Table = Source{{[Schema="dbo", Item="{table_name}"]}}[Data]')
    else:
        lines.append('    Table = Source')
    lines.append('in')
    lines.append('    Table')
    return '\n'.join(lines)


def _generate_oracle(server, database, schema, table_name):
    """Generate M for Oracle."""
    lines = [
        'let',
        f'    Source = Oracle.Database("{server}"),',
    ]
    if schema and table_name:
        lines.append(f'    Table = Source{{[Schema="{schema}", Name="{table_name}"]}}[Data]')
    elif table_name:
        lines.append(f'    Table = Source{{[Name="{table_name}"]}}[Data]')
    else:
        lines.append('    Table = Source')
    lines.append('in')
    lines.append('    Table')
    return '\n'.join(lines)


def _generate_postgresql(server, database, schema, table_name):
    """Generate M for PostgreSQL."""
    lines = [
        'let',
        f'    Source = PostgreSQL.Database("{server}", "{database}"),',
    ]
    if schema and table_name:
        lines.append(f'    Table = Source{{[Schema="{schema}", Item="{table_name}"]}}[Data]')
    elif table_name:
        lines.append(f'    Table = Source{{[Schema="public", Item="{table_name}"]}}[Data]')
    else:
        lines.append('    Table = Source')
    lines.append('in')
    lines.append('    Table')
    return '\n'.join(lines)


def _generate_mysql(server, database, schema, table_name):
    """Generate M for MySQL."""
    lines = [
        'let',
        f'    Source = MySQL.Database("{server}", "{database}"),',
    ]
    if table_name:
        lines.append(f'    Table = Source{{[Name="{table_name}"]}}[Data]')
    else:
        lines.append('    Table = Source')
    lines.append('in')
    lines.append('    Table')
    return '\n'.join(lines)


def _generate_teradata(server, database, schema, table_name):
    """Generate M for Teradata."""
    lines = [
        'let',
        f'    Source = Teradata.Database("{server}"),',
    ]
    if database and table_name:
        lines.append(f'    DB = Source{{[Name="{database}"]}}[Data],')
        lines.append(f'    Table = DB{{[Name="{table_name}"]}}[Data]')
    elif table_name:
        lines.append(f'    Table = Source{{[Name="{table_name}"]}}[Data]')
    else:
        lines.append('    Table = Source')
    lines.append('in')
    lines.append('    Table')
    return '\n'.join(lines)


def _generate_snowflake(server, database, schema, table_name):
    """Generate M for Snowflake."""
    lines = [
        'let',
        f'    Source = Snowflake.Databases("{server}", "{database or "WAREHOUSE"}"),',
    ]
    if database and schema and table_name:
        lines.append(f'    DB = Source{{[Name="{database}"]}}[Data],')
        lines.append(f'    Schema = DB{{[Name="{schema}"]}}[Data],')
        lines.append(f'    Table = Schema{{[Name="{table_name}"]}}[Data]')
    elif table_name:
        lines.append(f'    Table = Source{{[Name="{table_name}"]}}[Data]')
    else:
        lines.append('    Table = Source')
    lines.append('in')
    lines.append('    Table')
    return '\n'.join(lines)


def _generate_databricks(server, database, schema, table_name):
    """Generate M for Databricks."""
    lines = [
        'let',
        f'    Source = Databricks.Catalogs("{server}", "/sql/1.0/warehouses/default"),',
    ]
    if database and schema and table_name:
        lines.append(f'    Catalog = Source{{[Name="{database}"]}}[Data],')
        lines.append(f'    Schema = Catalog{{[Name="{schema}"]}}[Data],')
        lines.append(f'    Table = Schema{{[Name="{table_name}"]}}[Data]')
    elif table_name:
        lines.append(f'    Table = Source{{[Name="{table_name}"]}}[Data]')
    else:
        lines.append('    Table = Source')
    lines.append('in')
    lines.append('    Table')
    return '\n'.join(lines)


def _generate_bigquery(server, database, schema, table_name):
    """Generate M for Google BigQuery."""
    project_id = server or database
    lines = [
        'let',
        f'    Source = GoogleBigQuery.Database([BillingProject="{project_id}"]),',
    ]
    if schema and table_name:
        lines.append(f'    Dataset = Source{{[Name="{schema}"]}}[Data],')
        lines.append(f'    Table = Dataset{{[Name="{table_name}"]}}[Data]')
    elif table_name:
        lines.append(f'    Table = Source{{[Name="{table_name}"]}}[Data]')
    else:
        lines.append('    Table = Source')
    lines.append('in')
    lines.append('    Table')
    return '\n'.join(lines)


def _generate_sap_hana(server, database, schema, table_name):
    """Generate M for SAP HANA."""
    lines = [
        'let',
        f'    Source = SapHana.Database("{server}"),',
    ]
    if schema and table_name:
        lines.append(f'    Table = Source{{[Schema="{schema}", Name="{table_name}"]}}[Data]')
    elif table_name:
        lines.append(f'    Table = Source{{[Name="{table_name}"]}}[Data]')
    else:
        lines.append('    Table = Source')
    lines.append('in')
    lines.append('    Table')
    return '\n'.join(lines)


def _generate_db2(server, database, schema, table_name):
    """Generate M for IBM DB2."""
    lines = [
        'let',
        f'    Source = DB2.Database("{server}", "{database}"),',
    ]
    if schema and table_name:
        lines.append(f'    Table = Source{{[Schema="{schema}", Name="{table_name}"]}}[Data]')
    elif table_name:
        lines.append(f'    Table = Source{{[Name="{table_name}"]}}[Data]')
    else:
        lines.append('    Table = Source')
    lines.append('in')
    lines.append('    Table')
    return '\n'.join(lines)


def _generate_redshift(server, database, schema, table_name):
    """Generate M for Amazon Redshift."""
    lines = [
        'let',
        f'    Source = AmazonRedshift.Database("{server}", "{database}"),',
    ]
    if schema and table_name:
        lines.append(f'    Table = Source{{[Schema="{schema}", Name="{table_name}"]}}[Data]')
    elif table_name:
        lines.append(f'    Table = Source{{[Name="{table_name}"]}}[Data]')
    else:
        lines.append('    Table = Source')
    lines.append('in')
    lines.append('    Table')
    return '\n'.join(lines)


def _generate_odbc(server, database, schema, table_name):
    """Generate M for generic ODBC connection."""
    dsn = server or database or "MSTR_Warehouse"
    lines = [
        'let',
        f'    Source = Odbc.DataSource("DSN={dsn}"),',
    ]
    if schema and table_name:
        lines.append(f'    Table = Source{{[Schema="{schema}", Name="{table_name}"]}}[Data]')
    elif table_name:
        lines.append(f'    Table = Source{{[Name="{table_name}"]}}[Data]')
    else:
        lines.append('    Table = Source')
    lines.append('in')
    lines.append('    Table')
    return '\n'.join(lines)


def _get_source_expression(db_type, server, database):
    """Get the source expression for a native query."""
    generators = {
        "sql server": f'Sql.Database("{server}", "{database}")',
        "mssql": f'Sql.Database("{server}", "{database}")',
        "oracle": f'Oracle.Database("{server}")',
        "postgresql": f'PostgreSQL.Database("{server}", "{database}")',
        "mysql": f'MySQL.Database("{server}", "{database}")',
        "teradata": f'Teradata.Database("{server}")',
        "snowflake": f'Snowflake.Databases("{server}", "{database}")',
        "bigquery": f'GoogleBigQuery.Database([BillingProject="{server}"])',
    }
    return generators.get(db_type, f'Odbc.DataSource("DSN={server}")')


def _build_native_query(source_expr, sql_statement):
    """Build a Value.NativeQuery M expression."""
    # Escape double quotes in SQL
    escaped_sql = sql_statement.replace('"', '""')
    return f'let\n    Source = {source_expr},\n    Query = Value.NativeQuery(Source, "{escaped_sql}")\nin\n    Query'


# ── Connection type mapping ──────────────────────────────────────

_CONNECTION_MAP = {
    "sql server": _generate_sql_server,
    "sql_server": _generate_sql_server,
    "mssql": _generate_sql_server,
    "sqlserver": _generate_sql_server,
    "oracle": _generate_oracle,
    "postgresql": _generate_postgresql,
    "postgres": _generate_postgresql,
    "mysql": _generate_mysql,
    "teradata": _generate_teradata,
    "snowflake": _generate_snowflake,
    "databricks": _generate_databricks,
    "bigquery": _generate_bigquery,
    "google bigquery": _generate_bigquery,
    "sap hana": _generate_sap_hana,
    "sap_hana": _generate_sap_hana,
    "saphana": _generate_sap_hana,
    "db2": _generate_db2,
    "ibm db2": _generate_db2,
    "ibm_db2": _generate_db2,
    "redshift": _generate_redshift,
    "amazon redshift": _generate_redshift,
    "amazon_redshift": _generate_redshift,
    "google_bigquery": _generate_bigquery,
    "netezza": _generate_odbc,
    "impala": _generate_odbc,
    "vertica": _generate_odbc,
    "odbc": _generate_odbc,
    "jdbc": _generate_odbc,
}
