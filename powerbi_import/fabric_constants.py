"""
Fabric constants — centralized type maps, function maps, and reserved words.

Shared across all Fabric generators (lakehouse, notebook, dataflow,
semantic model).  Consolidates the per-module _SPARK_TYPE_MAP /
_SPARK_FORMAT_MAP / _JDBC_* tables into a single source of truth.
"""

import logging
import re

logger = logging.getLogger(__name__)

# ── MSTR data-type → Spark SQL type map ──────────────────────────

SPARK_TYPE_MAP = {
    # Integer family
    "integer": "INT",
    "int": "INT",
    "biginteger": "BIGINT",
    "long": "BIGINT",
    "smallint": "SMALLINT",
    "tinyint": "TINYINT",
    # Floating-point family
    "real": "DOUBLE",
    "float": "FLOAT",
    "double": "DOUBLE",
    # Fixed-point family
    "numeric": "DECIMAL(38,10)",
    "decimal": "DECIMAL(38,10)",
    "bigdecimal": "DECIMAL(38,10)",
    "money": "DECIMAL(19,4)",
    "currency": "DECIMAL(19,4)",
    # String family
    "nvarchar": "STRING",
    "varchar": "STRING",
    "char": "STRING",
    "nchar": "STRING",
    "text": "STRING",
    "longvarchar": "STRING",
    "string": "STRING",
    "clob": "STRING",
    "ntext": "STRING",
    "xml": "STRING",
    # Date/time family
    "date": "DATE",
    "datetime": "TIMESTAMP",
    "timestamp": "TIMESTAMP",
    "time": "STRING",
    "datetimeoffset": "TIMESTAMP",
    "smalldatetime": "TIMESTAMP",
    # Boolean
    "boolean": "BOOLEAN",
    "bit": "BOOLEAN",
    # Binary family
    "binary": "BINARY",
    "varbinary": "BINARY",
    "blob": "BINARY",
    "image": "BINARY",
}

# ── MSTR data-type → TMDL dataType enum ─────────────────────────

TMDL_TYPE_MAP = {
    "integer": "int64",
    "int": "int64",
    "biginteger": "int64",
    "long": "int64",
    "smallint": "int64",
    "tinyint": "int64",
    "real": "double",
    "float": "double",
    "double": "double",
    "numeric": "decimal",
    "decimal": "decimal",
    "bigdecimal": "decimal",
    "money": "decimal",
    "currency": "decimal",
    "nvarchar": "string",
    "varchar": "string",
    "char": "string",
    "nchar": "string",
    "text": "string",
    "longvarchar": "string",
    "string": "string",
    "clob": "string",
    "ntext": "string",
    "xml": "string",
    "date": "dateTime",
    "datetime": "dateTime",
    "timestamp": "dateTime",
    "time": "string",
    "datetimeoffset": "dateTime",
    "smalldatetime": "dateTime",
    "boolean": "boolean",
    "bit": "boolean",
    "binary": "binary",
    "varbinary": "binary",
    "blob": "binary",
    "image": "binary",
}

# ── Spark data-source format by warehouse type ───────────────────

SPARK_FORMAT_MAP = {
    "sql_server": "jdbc",
    "oracle": "jdbc",
    "postgresql": "jdbc",
    "mysql": "jdbc",
    "teradata": "jdbc",
    "db2": "jdbc",
    "netezza": "jdbc",
    "sap_hana": "jdbc",
    "redshift": "jdbc",
    "snowflake": "snowflake",
    "databricks": "databricks",
    "bigquery": "bigquery",
}

# ── JDBC driver class by warehouse type ──────────────────────────

JDBC_DRIVER_MAP = {
    "sql_server": "com.microsoft.sqlserver.jdbc.SQLServerDriver",
    "oracle": "oracle.jdbc.driver.OracleDriver",
    "postgresql": "org.postgresql.Driver",
    "mysql": "com.mysql.cj.jdbc.Driver",
    "teradata": "com.teradata.jdbc.TeraDriver",
    "db2": "com.ibm.db2.jcc.DB2Driver",
    "netezza": "org.netezza.Driver",
    "sap_hana": "com.sap.db.jdbc.Driver",
    "redshift": "com.amazon.redshift.jdbc42.Driver",
}

# ── JDBC URL template by warehouse type ──────────────────────────

JDBC_URL_TEMPLATE = {
    "sql_server": "jdbc:sqlserver://{server};databaseName={database};encrypt=true;trustServerCertificate=true",
    "oracle": "jdbc:oracle:thin:@{server}/{database}",
    "postgresql": "jdbc:postgresql://{server}/{database}",
    "mysql": "jdbc:mysql://{server}/{database}",
    "teradata": "jdbc:teradata://{server}/DATABASE={database}",
    "db2": "jdbc:db2://{server}/{database}",
    "netezza": "jdbc:netezza://{server}/{database}",
    "sap_hana": "jdbc:sap://{server}/?databaseName={database}",
    "redshift": "jdbc:redshift://{server}/{database}",
}

# ── PySpark function map (MSTR aggregate → PySpark) ──────────────

PYSPARK_AGG_MAP = {
    "sum": "F.sum",
    "avg": "F.avg",
    "count": "F.count",
    "min": "F.min",
    "max": "F.max",
    "count_distinct": "F.countDistinct",
    "stdev": "F.stddev",
    "variance": "F.variance",
    "median": "F.percentile_approx({col}, 0.5)",
    "first": "F.first",
    "last": "F.last",
}

# ── Spark / Delta reserved words ─────────────────────────────────

_RESERVED_WORDS = frozenset({
    "add", "alter", "and", "as", "between", "by", "case", "column",
    "create", "cross", "current", "database", "date", "delete", "desc",
    "distinct", "drop", "else", "end", "exists", "false", "for", "from",
    "full", "function", "grant", "group", "having", "if", "in", "inner",
    "insert", "int", "into", "is", "join", "left", "like", "not", "null",
    "on", "or", "order", "outer", "primary", "right", "select", "set",
    "table", "then", "to", "true", "union", "update", "using", "values",
    "when", "where", "with",
})

# ── Column name sanitization ─────────────────────────────────────

_SANITIZE_RE = re.compile(r"[^a-zA-Z0-9_]")


def sanitize_column_name(name):
    """Sanitize a column name for use in Spark / Delta tables.

    Replaces non-alphanumeric characters with ``_``, collapses consecutive
    underscores, strips leading/trailing underscores, and backtick-wraps
    reserved words.
    """
    cleaned = _SANITIZE_RE.sub("_", name or "")
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned:
        cleaned = "col"
    if cleaned.lower() in _RESERVED_WORDS:
        cleaned = f"`{cleaned}`"
    return cleaned


def map_spark_type(mstr_type):
    """Map a MicroStrategy data type string to a Spark SQL type."""
    return SPARK_TYPE_MAP.get((mstr_type or "string").lower().strip(), "STRING")


def map_tmdl_type(mstr_type):
    """Map a MicroStrategy data type string to a TMDL dataType enum."""
    return TMDL_TYPE_MAP.get((mstr_type or "string").lower().strip(), "string")


def is_reserved_word(name):
    """Return True if *name* is a Spark/Delta reserved word."""
    return (name or "").lower() in _RESERVED_WORDS
