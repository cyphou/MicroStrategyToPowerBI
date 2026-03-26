"""
Tests for v16.0 Sprint GG — Fabric Deep Integration.

Covers: fabric_constants, fabric_naming, calc_column_utils,
        dataflow_generator, fabric_semantic_model_generator.
"""

import json
import os
import shutil
import tempfile
import unittest

from powerbi_import.fabric_constants import (
    SPARK_TYPE_MAP,
    TMDL_TYPE_MAP,
    SPARK_FORMAT_MAP,
    JDBC_DRIVER_MAP,
    PYSPARK_AGG_MAP,
    map_spark_type,
    map_tmdl_type,
    sanitize_column_name,
    is_reserved_word,
)
from powerbi_import.fabric_naming import (
    sanitize_table_name,
    sanitize_item_name,
    sanitize_dataflow_name,
    sanitize_pipeline_name,
    sanitize_semantic_model_name,
    resolve_collisions,
    validate_table_names,
)
from powerbi_import.calc_column_utils import (
    classify_expression,
    classify_metrics,
    expression_to_pyspark,
)
from powerbi_import.dataflow_generator import generate_dataflows
from powerbi_import.fabric_semantic_model_generator import (
    generate_direct_lake_model,
)


# ═══════════════════════════════════════════════════════════════════
# Fabric Constants Tests
# ═══════════════════════════════════════════════════════════════════

class TestSparkTypeMap(unittest.TestCase):
    """GG.1: Centralized Spark type map."""

    def test_integer_types(self):
        self.assertEqual(map_spark_type("integer"), "INT")
        self.assertEqual(map_spark_type("biginteger"), "BIGINT")
        self.assertEqual(map_spark_type("smallint"), "SMALLINT")
        self.assertEqual(map_spark_type("tinyint"), "TINYINT")

    def test_float_types(self):
        self.assertEqual(map_spark_type("float"), "FLOAT")
        self.assertEqual(map_spark_type("double"), "DOUBLE")
        self.assertEqual(map_spark_type("real"), "DOUBLE")

    def test_decimal_types(self):
        self.assertEqual(map_spark_type("numeric"), "DECIMAL(38,10)")
        self.assertEqual(map_spark_type("money"), "DECIMAL(19,4)")

    def test_string_types(self):
        self.assertEqual(map_spark_type("varchar"), "STRING")
        self.assertEqual(map_spark_type("nvarchar"), "STRING")
        self.assertEqual(map_spark_type("text"), "STRING")
        self.assertEqual(map_spark_type("clob"), "STRING")

    def test_date_types(self):
        self.assertEqual(map_spark_type("date"), "DATE")
        self.assertEqual(map_spark_type("datetime"), "TIMESTAMP")
        self.assertEqual(map_spark_type("timestamp"), "TIMESTAMP")

    def test_boolean_types(self):
        self.assertEqual(map_spark_type("boolean"), "BOOLEAN")
        self.assertEqual(map_spark_type("bit"), "BOOLEAN")

    def test_unknown_type_defaults_to_string(self):
        self.assertEqual(map_spark_type("foo_bar"), "STRING")
        self.assertEqual(map_spark_type(None), "STRING")
        self.assertEqual(map_spark_type(""), "STRING")

    def test_case_insensitive(self):
        self.assertEqual(map_spark_type("INTEGER"), "INT")
        self.assertEqual(map_spark_type("VarChar"), "STRING")


class TestTmdlTypeMap(unittest.TestCase):
    def test_integer_to_int64(self):
        self.assertEqual(map_tmdl_type("integer"), "int64")

    def test_varchar_to_string(self):
        self.assertEqual(map_tmdl_type("varchar"), "string")

    def test_date_to_dateTime(self):
        self.assertEqual(map_tmdl_type("date"), "dateTime")

    def test_unknown_defaults(self):
        self.assertEqual(map_tmdl_type("unknown"), "string")


class TestSanitizeColumn(unittest.TestCase):
    def test_clean_name_unchanged(self):
        self.assertEqual(sanitize_column_name("Sales_Amount"), "Sales_Amount")

    def test_special_chars_replaced(self):
        result = sanitize_column_name("Sales Amount ($)")
        self.assertNotIn(" ", result)
        self.assertNotIn("$", result)

    def test_reserved_word_backticked(self):
        result = sanitize_column_name("select")
        self.assertEqual(result, "`select`")

    def test_empty_name(self):
        self.assertEqual(sanitize_column_name(""), "col")
        self.assertEqual(sanitize_column_name(None), "col")

    def test_is_reserved_word(self):
        self.assertTrue(is_reserved_word("SELECT"))
        self.assertTrue(is_reserved_word("table"))
        self.assertFalse(is_reserved_word("Revenue"))


class TestConstantMaps(unittest.TestCase):
    def test_spark_format_map_has_common_dbs(self):
        self.assertEqual(SPARK_FORMAT_MAP["sql_server"], "jdbc")
        self.assertEqual(SPARK_FORMAT_MAP["snowflake"], "snowflake")

    def test_jdbc_driver_map_keys(self):
        self.assertIn("sql_server", JDBC_DRIVER_MAP)
        self.assertIn("oracle", JDBC_DRIVER_MAP)
        self.assertIn("postgresql", JDBC_DRIVER_MAP)

    def test_pyspark_agg_map(self):
        self.assertEqual(PYSPARK_AGG_MAP["sum"], "F.sum")
        self.assertEqual(PYSPARK_AGG_MAP["avg"], "F.avg")


# ═══════════════════════════════════════════════════════════════════
# Fabric Naming Tests
# ═══════════════════════════════════════════════════════════════════

class TestTableNameSanitization(unittest.TestCase):
    """GG.2: Lakehouse table naming."""

    def test_clean_name_unchanged(self):
        self.assertEqual(sanitize_table_name("Sales"), "Sales")

    def test_spaces_replaced(self):
        result = sanitize_table_name("Sales Amount")
        self.assertNotIn(" ", result)

    def test_special_chars_stripped(self):
        result = sanitize_table_name("fact.Sales$2024")
        self.assertNotIn(".", result)
        self.assertNotIn("$", result)

    def test_leading_digit(self):
        result = sanitize_table_name("123_table")
        self.assertFalse(result[0].isdigit())

    def test_truncation_at_64(self):
        long_name = "a" * 100
        result = sanitize_table_name(long_name)
        self.assertLessEqual(len(result), 64)

    def test_empty_name(self):
        self.assertEqual(sanitize_table_name(""), "table")
        self.assertEqual(sanitize_table_name(None), "table")


class TestItemNameSanitization(unittest.TestCase):
    def test_normal_name(self):
        self.assertEqual(sanitize_item_name("My Dataflow"), "My Dataflow")

    def test_special_chars_removed(self):
        result = sanitize_item_name("DF <script>alert(1)</script>")
        self.assertNotIn("<", result)

    def test_max_length_256(self):
        result = sanitize_item_name("x" * 300)
        self.assertLessEqual(len(result), 256)

    def test_dataflow_prefix(self):
        result = sanitize_dataflow_name("Sales")
        self.assertTrue(result.startswith("DF_"))

    def test_pipeline_prefix(self):
        result = sanitize_pipeline_name("ETL")
        self.assertTrue(result.startswith("PL_"))

    def test_semantic_model_name(self):
        self.assertEqual(sanitize_semantic_model_name("Model"), "Model")
        self.assertEqual(sanitize_semantic_model_name(""), "SemanticModel")


class TestCollisionResolution(unittest.TestCase):
    def test_no_collisions(self):
        names = ["A", "B", "C"]
        self.assertEqual(resolve_collisions(names), names)

    def test_duplicate_names(self):
        names = ["Sales", "sales", "Revenue"]
        result = resolve_collisions(names)
        self.assertEqual(len(set(r.lower() for r in result)), 3)

    def test_triple_collision(self):
        names = ["Fact", "fact", "FACT"]
        result = resolve_collisions(names)
        self.assertEqual(result[0], "Fact")
        self.assertIn("_2", result[1])
        self.assertIn("_3", result[2])


class TestValidateTableNames(unittest.TestCase):
    def test_all_valid(self):
        names = ["Sales", "Products"]
        report = validate_table_names(names)
        self.assertEqual(len(report["valid"]), 2)

    def test_sanitized_names(self):
        names = ["Sales Amount", "Products"]
        report = validate_table_names(names)
        self.assertTrue(len(report["sanitized"]) >= 1)

    def test_collision_detected(self):
        names = ["Sales", "sales"]
        report = validate_table_names(names)
        self.assertTrue(len(report["collisions"]) >= 1)


# ═══════════════════════════════════════════════════════════════════
# Calculated Column Utils Tests
# ═══════════════════════════════════════════════════════════════════

class TestExpressionClassification(unittest.TestCase):
    """GG.3: Classify as lakehouse or dax_only."""

    def test_simple_arithmetic_is_lakehouse(self):
        self.assertEqual(classify_expression("[Price] * [Qty]"), "lakehouse")

    def test_simple_function_is_lakehouse(self):
        self.assertEqual(classify_expression("UPPER([Name])"), "lakehouse")

    def test_calculate_is_dax_only(self):
        self.assertEqual(
            classify_expression("CALCULATE(SUM([Sales]), ALL(Region))"),
            "dax_only"
        )

    def test_filter_is_dax_only(self):
        self.assertEqual(
            classify_expression("FILTER(Sales, Sales[Amount] > 100)"),
            "dax_only"
        )

    def test_sumx_is_dax_only(self):
        self.assertEqual(classify_expression("SUMX(Sales, [Price]*[Qty])"), "dax_only")

    def test_aggregate_sum_is_dax_only(self):
        self.assertEqual(classify_expression("SUM([Sales])"), "dax_only")

    def test_empty_expression(self):
        self.assertEqual(classify_expression(""), "dax_only")
        self.assertEqual(classify_expression(None), "dax_only")

    def test_time_intelligence_is_dax_only(self):
        self.assertEqual(
            classify_expression("TOTALYTD(SUM([Sales]), Calendar[Date])"),
            "dax_only"
        )


class TestClassifyMetrics(unittest.TestCase):
    def test_mixed_classification(self):
        metrics = [
            {"name": "FullName", "expression": "UPPER([First]) & LOWER([Last])"},
            {"name": "TotalSales", "expression": "SUM([Revenue])"},
        ]
        result = classify_metrics(metrics)
        # At least one in each bucket or check specific
        total = len(result["lakehouse"]) + len(result["dax_only"])
        self.assertEqual(total, 2)

    def test_empty_list(self):
        result = classify_metrics([])
        self.assertEqual(len(result["lakehouse"]), 0)
        self.assertEqual(len(result["dax_only"]), 0)


class TestExpressionToPyspark(unittest.TestCase):
    def test_abs_function(self):
        result = expression_to_pyspark("ABS([Amount])", "abs_amount")
        self.assertIn("withColumn", result)
        self.assertIn("abs", result.lower())

    def test_upper_function(self):
        result = expression_to_pyspark("UPPER([Name])", "upper_name")
        self.assertIn("withColumn", result)
        self.assertIn("upper", result.lower())

    def test_arithmetic(self):
        result = expression_to_pyspark("[Price] * [Qty]", "total")
        self.assertIn("withColumn", result)
        self.assertIn("*", result)

    def test_complex_returns_manual(self):
        # Expression that doesn't match any function or arithmetic pattern
        result = expression_to_pyspark("some complex nested thing without brackets", "calc")
        self.assertIn("MANUAL", result)

    def test_empty_expression(self):
        result = expression_to_pyspark("", "col")
        self.assertIn("MANUAL", result)


# ═══════════════════════════════════════════════════════════════════
# Dataflow Generator Tests
# ═══════════════════════════════════════════════════════════════════

class TestDataflowGenerator(unittest.TestCase):
    """GG.4: Dataflow Gen2 definition generation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _sample_data(self, db_type="sql_server"):
        return {
            "datasources": [
                {
                    "name": "Sales",
                    "physical_table": "FactSales",
                    "db_connection": {
                        "db_type": db_type,
                        "server": "myserver.database.windows.net",
                        "database": "WarehouseDB",
                        "schema": "dbo",
                    },
                    "columns": [
                        {"name": "SalesID", "data_type": "integer"},
                        {"name": "Amount", "data_type": "decimal"},
                    ],
                }
            ],
            "freeform_sql": [],
        }

    def test_generates_dataflow_files(self):
        result = generate_dataflows(self._sample_data(), self.tmpdir,
                                    lakehouse_name="TestLH")
        self.assertEqual(result["dataflows_generated"], 1)
        self.assertTrue(os.path.isdir(result["dataflow_dir"]))

    def test_manifest_created(self):
        generate_dataflows(self._sample_data(), self.tmpdir)
        manifest_path = os.path.join(self.tmpdir, "dataflows", "manifest.json")
        self.assertTrue(os.path.exists(manifest_path))

    def test_dataflow_json_structure(self):
        generate_dataflows(self._sample_data(), self.tmpdir)
        # Find first dataflow JSON
        df_dir = os.path.join(self.tmpdir, "dataflows")
        jsons = [f for f in os.listdir(df_dir) if f.endswith(".json") and f != "manifest.json"]
        self.assertTrue(len(jsons) > 0)
        with open(os.path.join(df_dir, jsons[0]), "r") as f:
            df = json.load(f)
        self.assertEqual(df["type"], "dataflow")
        self.assertIn("definition", df)
        self.assertIn("destination", df)

    def test_column_mappings(self):
        generate_dataflows(self._sample_data(), self.tmpdir)
        df_dir = os.path.join(self.tmpdir, "dataflows")
        jsons = [f for f in os.listdir(df_dir) if f.endswith(".json") and f != "manifest.json"]
        with open(os.path.join(df_dir, jsons[0]), "r") as f:
            df = json.load(f)
        mappings = df["destination"]["columnMappings"]
        self.assertEqual(len(mappings), 2)
        self.assertEqual(mappings[0]["source"], "SalesID")

    def test_freeform_sql_dataflow(self):
        data = {
            "datasources": [],
            "freeform_sql": [
                {
                    "name": "CustomQuery",
                    "sql": "SELECT * FROM vw_Sales",
                    "db_connection": {"db_type": "sql_server", "server": "s", "database": "d"},
                    "columns": [{"name": "X", "data_type": "integer"}],
                }
            ],
        }
        result = generate_dataflows(data, self.tmpdir)
        self.assertEqual(result["dataflows_generated"], 1)

    def test_multiple_datasources(self):
        data = self._sample_data()
        data["datasources"].append({
            "name": "Products",
            "physical_table": "DimProduct",
            "db_connection": {"db_type": "postgresql", "server": "pg", "database": "db", "schema": "public"},
            "columns": [{"name": "ProdID", "data_type": "integer"}],
        })
        result = generate_dataflows(data, self.tmpdir)
        self.assertEqual(result["dataflows_generated"], 2)

    def test_empty_datasources(self):
        result = generate_dataflows({"datasources": [], "freeform_sql": []}, self.tmpdir)
        self.assertEqual(result["dataflows_generated"], 0)


# ═══════════════════════════════════════════════════════════════════
# DirectLake Semantic Model Generator Tests
# ═══════════════════════════════════════════════════════════════════

class TestDirectLakeModelGenerator(unittest.TestCase):
    """GG.5: DirectLake semantic model generation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _sample_data(self):
        return {
            "datasources": [
                {
                    "name": "Sales",
                    "physical_table": "FactSales",
                    "db_connection": {"db_type": "sql_server"},
                    "columns": [
                        {"name": "SalesID", "data_type": "integer"},
                        {"name": "Amount", "data_type": "decimal"},
                        {"name": "OrderDate", "data_type": "date"},
                    ],
                },
                {
                    "name": "Products",
                    "physical_table": "DimProduct",
                    "db_connection": {"db_type": "sql_server"},
                    "columns": [
                        {"name": "ProductID", "data_type": "integer"},
                        {"name": "ProductName", "data_type": "varchar"},
                    ],
                },
            ],
            "metrics": [
                {"name": "Total Sales", "table": "Sales",
                 "expression": "SUM(Sales[Amount])"},
            ],
            "derived_metrics": [],
            "relationships": [
                {
                    "from_table": "Sales",
                    "from_column": "ProductID",
                    "to_table": "Products",
                    "to_column": "ProductID",
                    "cardinality": "manyToOne",
                },
            ],
            "freeform_sql": [],
        }

    def test_generates_model_tmdl(self):
        result = generate_direct_lake_model(
            self._sample_data(), self.tmpdir, lakehouse_name="TestLH")
        model_path = os.path.join(result["model_dir"], "model.tmdl")
        self.assertTrue(os.path.exists(model_path))

    def test_generates_table_files(self):
        result = generate_direct_lake_model(
            self._sample_data(), self.tmpdir, lakehouse_name="TestLH")
        self.assertEqual(result["tables_generated"], 2)

    def test_directlake_partition_in_tmdl(self):
        result = generate_direct_lake_model(
            self._sample_data(), self.tmpdir, lakehouse_name="TestLH")
        tables_dir = os.path.join(result["model_dir"], "tables")
        sales_path = os.path.join(tables_dir, "FactSales.tmdl")
        with open(sales_path, "r") as f:
            content = f.read()
        self.assertIn("directLake", content)
        self.assertIn("entityName:", content)

    def test_relationships_generated(self):
        result = generate_direct_lake_model(
            self._sample_data(), self.tmpdir, lakehouse_name="TestLH")
        rel_path = os.path.join(result["model_dir"], "relationships.tmdl")
        self.assertTrue(os.path.exists(rel_path))
        with open(rel_path, "r") as f:
            content = f.read()
        self.assertIn("relationship", content)

    def test_measures_in_table(self):
        result = generate_direct_lake_model(
            self._sample_data(), self.tmpdir, lakehouse_name="TestLH")
        tables_dir = os.path.join(result["model_dir"], "tables")
        sales_path = os.path.join(tables_dir, "FactSales.tmdl")
        with open(sales_path, "r") as f:
            content = f.read()
        self.assertIn("measure Total Sales", content)

    def test_expression_tmdl_generated(self):
        result = generate_direct_lake_model(
            self._sample_data(), self.tmpdir, lakehouse_name="TestLH")
        expr_path = os.path.join(result["model_dir"], "expression.tmdl")
        self.assertTrue(os.path.exists(expr_path))

    def test_lakehouse_annotation(self):
        result = generate_direct_lake_model(
            self._sample_data(), self.tmpdir, lakehouse_name="TestLH")
        model_path = os.path.join(result["model_dir"], "model.tmdl")
        with open(model_path, "r") as f:
            content = f.read()
        self.assertIn("LakehouseName = TestLH", content)

    def test_no_relationships_skip_file(self):
        data = self._sample_data()
        data["relationships"] = []
        result = generate_direct_lake_model(data, self.tmpdir)
        rel_path = os.path.join(result["model_dir"], "relationships.tmdl")
        self.assertFalse(os.path.exists(rel_path))

    def test_empty_datasources(self):
        data = {"datasources": [], "metrics": [], "derived_metrics": [],
                "relationships": [], "freeform_sql": []}
        result = generate_direct_lake_model(data, self.tmpdir)
        self.assertEqual(result["tables_generated"], 0)

    def test_freeform_sql_table(self):
        data = {
            "datasources": [],
            "metrics": [],
            "derived_metrics": [],
            "relationships": [],
            "freeform_sql": [
                {"name": "CustomView", "columns": [
                    {"name": "ID", "data_type": "integer"},
                ]},
            ],
        }
        result = generate_direct_lake_model(data, self.tmpdir, lakehouse_name="LH")
        self.assertEqual(result["tables_generated"], 1)


if __name__ == "__main__":
    unittest.main()
