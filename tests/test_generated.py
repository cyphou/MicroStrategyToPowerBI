"""
Auto-generated tests from function mappings (Sprint Z.5).

DO NOT EDIT MANUALLY — regenerate with:
    python scripts/generate_tests.py
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from microstrategy_export.expression_converter import convert_mstr_expression_to_dax
from powerbi_import.visual_generator import _VIZ_TYPE_MAP, _convert_visualization
from powerbi_import.tmdl_generator import _map_data_type, _GEO_ROLE_MAP


# ══ Generated expression converter tests ════════════════════════

_EXPR_CASES = [
    ("Sum(Revenue)", "SUM", "sum"),
    ("Avg(Revenue)", "AVERAGE", "avg"),
    ("Count(Revenue)", "COUNT", "count"),
    ("Min(Revenue)", "MIN", "min"),
    ("Max(Revenue)", "MAX", "max"),
    ("Stdev(Revenue)", "STDEV.S", "stdev"),
    ("Stdevp(Revenue)", "STDEV.P", "stdevp"),
    ("Var(Revenue)", "VAR.S", "var"),
    ("Varp(Revenue)", "VAR.P", "varp"),
    ("Median(Revenue)", "MEDIAN", "median"),
    ("Product(Revenue)", "PRODUCTX", "product"),
    ("Geomean(Revenue)", "GEOMEANX", "geomean"),
    ("Distinctcount(Revenue)", "DISTINCTCOUNT", "distinctcount"),
    ("If(Revenue)", "IF", "if"),
    ("And(Revenue)", "AND", "and"),
    ("Or(Revenue)", "OR", "or"),
    ("Not(Revenue)", "NOT", "not"),
    ("Isnull(Revenue)", "ISBLANK", "isnull"),
    ("Concat(ColA, ColB)", "CONCATENATE", "concat"),
    ("Length(Revenue)", "LEN", "length"),
    ("Substr(ColA, ColB)", "MID", "substr"),
    ("Leftstr(ColA, ColB)", "LEFT", "leftstr"),
    ("Rightstr(ColA, ColB)", "RIGHT", "rightstr"),
    ("Trim(Revenue)", "TRIM", "trim"),
    ("Ltrim(Revenue)", "TRIM", "ltrim"),
    ("Rtrim(Revenue)", "TRIM", "rtrim"),
    ("Upper(Revenue)", "UPPER", "upper"),
    ("Lower(Revenue)", "LOWER", "lower"),
    ("Position(ColA, ColB)", "SEARCH", "position"),
    ("Replace(ColA, ColB)", "SUBSTITUTE", "replace"),
    ("Currentdate()", "TODAY", "currentdate"),
    ("Currentdatetime()", "NOW", "currentdatetime"),
    ("Year(Revenue)", "YEAR", "year"),
    ("Month(Revenue)", "MONTH", "month"),
    ("Day(Revenue)", "DAY", "day"),
    ("Hour(Revenue)", "HOUR", "hour"),
    ("Minute(Revenue)", "MINUTE", "minute"),
    ("Second(Revenue)", "SECOND", "second"),
    ("Dayofweek(Revenue)", "WEEKDAY", "dayofweek"),
    ("Weekofyear(Revenue)", "WEEKNUM", "weekofyear"),
    ("Quarter(Revenue)", "QUARTER", "quarter"),
    ("Daysbetween(ColA, ColB)", None, "daysbetween"),
    ("Monthsbetween(ColA, ColB)", None, "monthsbetween"),
    ("Yearsbetween(ColA, ColB)", None, "yearsbetween"),
    ("Adddays(ColA, ColB)", None, "adddays"),
    ("Addmonths(ColA, ColB)", "EDATE", "addmonths"),
    ("Monthstartdate(Revenue)", "STARTOFMONTH", "monthstartdate"),
    ("Monthenddate(Revenue)", "ENDOFMONTH", "monthenddate"),
    ("Yearstartdate(Revenue)", "STARTOFYEAR", "yearstartdate"),
    ("Yearenddate(Revenue)", "ENDOFYEAR", "yearenddate"),
    ("Abs(Revenue)", "ABS", "abs"),
    ("Round(ColA, ColB)", "ROUND", "round"),
    ("Truncate(Revenue)", "TRUNC", "truncate"),
    ("Power(ColA, ColB)", "POWER", "power"),
    ("Sqrt(Revenue)", "SQRT", "sqrt"),
    ("Ln(Revenue)", "LN", "ln"),
    ("Exp(Revenue)", "EXP", "exp"),
    ("Mod(ColA, ColB)", "MOD", "mod"),
    ("Int(Revenue)", "INT", "int"),
    ("Sign(Revenue)", "SIGN", "sign"),
    ("Rsquare(Revenue)", None, "rSquare"),
    ("Initcap(Revenue)", None, "initcap"),
    ("Lpad(ColA, ColB)", None, "lpad"),
    ("Rpad(ColA, ColB)", None, "rpad"),
    ("Datediff(ColA, ColB)", "DATEDIFF", "datediff"),
    ("Dateadd(ColA, ColB)", "DATEADD", "dateadd"),
    ("Quarterstartdate(Revenue)", "STARTOFQUARTER", "quarterstartdate"),
    ("Quarterenddate(Revenue)", "ENDOFQUARTER", "quarterenddate"),
    ("Number(Revenue)", "VALUE", "number"),
    ("Text(Revenue)", "FORMAT", "text"),
]


class TestGeneratedExpressions:

    @pytest.mark.parametrize("expr,expected_fragment,func_name", _EXPR_CASES)
    def test_function_converts(self, expr, expected_fragment, func_name):
        result = convert_mstr_expression_to_dax(expr)
        assert isinstance(result, dict)
        assert "dax" in result
        if expected_fragment:
            assert expected_fragment in result["dax"], (
                f"Expected {expected_fragment} in DAX for {func_name}: {result['dax']}"
            )


_VIZ_CASES = [
    ("grid", "tableEx"),
    ("crosstab", "matrix"),
    ("vertical_bar", "clusteredColumnChart"),
    ("stacked_vertical_bar", "stackedColumnChart"),
    ("horizontal_bar", "clusteredBarChart"),
    ("stacked_horizontal_bar", "stackedBarChart"),
    ("line", "lineChart"),
    ("area", "areaChart"),
    ("stacked_area", "stackedAreaChart"),
    ("pie", "pieChart"),
    ("ring", "donutChart"),
    ("scatter", "scatterChart"),
    ("bubble", "scatterChart"),
    ("combo", "lineClusteredColumnComboChart"),
    ("dual_axis", "lineClusteredColumnComboChart"),
    ("map", "map"),
    ("filled_map", "filledMap"),
    ("treemap", "treemap"),
    ("waterfall", "waterfall"),
    ("funnel", "funnel"),
    ("gauge", "gauge"),
    ("kpi", "kpi"),
    ("heat_map", "matrix"),
    ("histogram", "clusteredColumnChart"),
    ("box_plot", "tableEx"),
    ("word_cloud", "tableEx"),
    ("network", "tableEx"),
    ("sankey", "tableEx"),
    ("bullet", "tableEx"),
    ("text", "textbox"),
    ("image", "image"),
    ("html", "textbox"),
    ("filter_panel", "slicer"),
    ("selector", "slicer"),
]


class TestGeneratedVizTypes:

    @pytest.mark.parametrize("mstr_type,expected_pbi", _VIZ_CASES)
    def test_viz_mapping(self, mstr_type, expected_pbi):
        assert _VIZ_TYPE_MAP[mstr_type] == expected_pbi

    @pytest.mark.parametrize("mstr_type,expected_pbi", _VIZ_CASES)
    def test_viz_converts(self, mstr_type, expected_pbi):
        viz = {
            "viz_type": mstr_type,
            "pbi_visual_type": expected_pbi,
            "data": {"attributes": [], "metrics": []},
            "position": {"x": 0, "y": 0, "width": 200, "height": 200},
            "formatting": {},
            "thresholds": [],
            "key": f"gen_{mstr_type}",
            "name": f"Gen {mstr_type}",
        }
        result = _convert_visualization(viz, 1024, 768)
        assert result is not None
        assert result["visual"]["visualType"] == expected_pbi


_DT_CASES = [
    ("integer", "int64"),
    ("int", "int64"),
    ("biginteger", "int64"),
    ("long", "int64"),
    ("smallint", "int64"),
    ("tinyint", "int64"),
    ("real", "double"),
    ("float", "double"),
    ("double", "double"),
    ("numeric", "double"),
    ("decimal", "decimal"),
    ("bigdecimal", "decimal"),
    ("money", "decimal"),
    ("nvarchar", "string"),
    ("varchar", "string"),
    ("char", "string"),
    ("nchar", "string"),
    ("text", "string"),
    ("longvarchar", "string"),
    ("date", "dateTime"),
    ("datetime", "dateTime"),
    ("timestamp", "dateTime"),
    ("time", "dateTime"),
    ("boolean", "boolean"),
    ("bit", "boolean"),
    ("binary", "binary"),
    ("varbinary", "binary"),
    ("blob", "binary"),
]


class TestGeneratedDataTypes:

    @pytest.mark.parametrize("mstr_type,expected_tmdl", _DT_CASES)
    def test_data_type_mapping(self, mstr_type, expected_tmdl):
        result = _map_data_type(mstr_type)
        assert result == expected_tmdl


_GEO_CASES = [
    ("city", "City"),
    ("state_province", "StateOrProvince"),
    ("state", "StateOrProvince"),
    ("country", "Country"),
    ("continent", "Continent"),
    ("county", "County"),
    ("postal_code", "PostalCode"),
    ("zip_code", "PostalCode"),
    ("latitude", "Latitude"),
    ("longitude", "Longitude"),
    ("address", "Address"),
    ("place", "Place"),
    ("web_url", "WebUrl"),
    ("image_url", "ImageUrl"),
    ("barcode", "Barcode"),
]


class TestGeneratedGeoRoles:

    @pytest.mark.parametrize("mstr_role,expected_category", _GEO_CASES)
    def test_geo_role_mapping(self, mstr_role, expected_category):
        assert _GEO_ROLE_MAP[mstr_role] == expected_category

