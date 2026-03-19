"""
Power Query M expression generator.

Generates M partition expressions for TMDL tables by delegating
to the extraction layer's connection_mapper.
"""

import logging

from microstrategy_export.connection_mapper import map_connection_to_m_query

logger = logging.getLogger(__name__)


def generate_m_partition(datasource):
    """Generate a Power Query M expression for a table partition.

    Args:
        datasource: Table dict from datasources.json

    Returns:
        str: Power Query M expression
    """
    connection = datasource.get("db_connection", {})
    table_name = datasource.get("physical_table", datasource.get("name", ""))
    schema = connection.get("schema", "")
    sql = datasource.get("sql_statement", "")

    return map_connection_to_m_query(
        connection,
        table_name=table_name,
        schema=schema,
        sql_statement=sql if sql else None,
    )


def generate_freeform_partition(freeform_sql):
    """Generate M expression for a freeform SQL table.

    Args:
        freeform_sql: Freeform SQL dict from freeform_sql.json

    Returns:
        str: Power Query M expression with Value.NativeQuery
    """
    connection = freeform_sql.get("db_connection", {})
    sql = freeform_sql.get("sql_statement", "")
    table_name = freeform_sql.get("name", "")

    return map_connection_to_m_query(
        connection,
        table_name=table_name,
        sql_statement=sql,
    )
