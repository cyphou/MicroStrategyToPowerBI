"""
Tests for v18.0 — Content Library & Templates.

Covers: model_templates.py, dax_recipes.py, marketplace.py, html_template.py.
"""

import json
import os
import tempfile
import unittest

from powerbi_import.model_templates import (
    list_templates,
    get_template,
    apply_template,
)
from powerbi_import.dax_recipes import (
    list_industries,
    get_industry_recipes,
    get_all_recipes,
    apply_recipes,
    recipes_to_marketplace_format,
)
from powerbi_import.marketplace import (
    PatternRegistry,
    PatternMetadata,
    Pattern,
    VALID_CATEGORIES,
    _parse_version,
)
from powerbi_import.html_template import (
    esc,
    get_report_css,
    get_report_js,
    html_open,
    html_close,
    stat_card,
    stat_grid,
    section_open,
    section_close,
    card,
    badge,
    fidelity_bar,
    donut_chart,
    bar_chart,
    data_table,
    tab_bar,
    tab_content,
    flow_diagram,
    cmd_box,
    PBI_BLUE,
    SUCCESS,
    FAIL,
)


# ===================================================================
# Model Templates
# ===================================================================

class TestListTemplates(unittest.TestCase):
    def test_returns_three(self):
        names = list_templates()
        self.assertEqual(len(names), 3)
        self.assertIn("healthcare", names)
        self.assertIn("finance", names)
        self.assertIn("retail", names)


class TestGetTemplate(unittest.TestCase):
    def test_healthcare(self):
        tpl = get_template("healthcare")
        self.assertIsNotNone(tpl)
        self.assertEqual(tpl["name"], "Healthcare")
        self.assertEqual(len(tpl["tables"]), 4)

    def test_finance(self):
        tpl = get_template("Finance")  # case-insensitive
        self.assertIsNotNone(tpl)
        self.assertEqual(len(tpl["measures"]), 4)

    def test_retail(self):
        tpl = get_template("RETAIL")
        self.assertIsNotNone(tpl)
        self.assertEqual(len(tpl["relationships"]), 3)

    def test_unknown_returns_none(self):
        self.assertIsNone(get_template("unknown"))

    def test_deep_copy(self):
        t1 = get_template("healthcare")
        t2 = get_template("healthcare")
        t1["tables"][0]["name"] = "MODIFIED"
        self.assertNotEqual(t2["tables"][0]["name"], "MODIFIED")


class TestApplyTemplate(unittest.TestCase):
    def test_all_new_tables(self):
        tpl = get_template("retail")
        result = apply_template(tpl, [])
        self.assertEqual(result["stats"]["new_tables"], 4)
        self.assertEqual(len(result["tables"]), 4)

    def test_enriches_existing_table(self):
        tpl = get_template("retail")
        existing = [{"name": "Sales", "columns": [
            {"name": "TransactionId", "dataType": "string"},
        ]}]
        result = apply_template(tpl, existing)
        # Sales existed, so only 3 new tables
        self.assertEqual(result["stats"]["new_tables"], 3)
        # Existing Sales table should have columns added
        sales = [t for t in result["tables"] if t["name"] == "Sales"][0]
        self.assertGreater(len(sales["columns"]), 1)

    def test_relationships_require_both_tables(self):
        tpl = get_template("healthcare")
        # Only one table exists — relationships can't all be added
        existing = [{"name": "Encounters", "columns": []}]
        result = apply_template(tpl, existing)
        # Only rels where both tables are in result
        for rel in result["relationships"]:
            table_names = {t["name"].lower() for t in result["tables"]}
            self.assertIn(rel["from_table"].lower(), table_names)

    def test_hierarchies_require_parent_table(self):
        tpl = get_template("finance")
        result = apply_template(tpl, [])
        self.assertGreater(result["stats"]["hierarchies_added"], 0)

    def test_measures_always_added(self):
        tpl = get_template("retail")
        result = apply_template(tpl, [])
        self.assertEqual(result["stats"]["measures_added"], 5)


# ===================================================================
# DAX Recipes
# ===================================================================

class TestListIndustries(unittest.TestCase):
    def test_returns_three(self):
        names = list_industries()
        self.assertEqual(set(names), {"healthcare", "finance", "retail"})


class TestGetIndustryRecipes(unittest.TestCase):
    def test_healthcare_count(self):
        recipes = get_industry_recipes("healthcare")
        self.assertEqual(len(recipes), 6)

    def test_finance_count(self):
        self.assertEqual(len(get_industry_recipes("finance")), 8)

    def test_retail_count(self):
        self.assertEqual(len(get_industry_recipes("retail")), 7)

    def test_unknown_empty(self):
        self.assertEqual(get_industry_recipes("unknown"), [])

    def test_recipe_structure(self):
        recipe = get_industry_recipes("healthcare")[0]
        self.assertIn("name", recipe)
        self.assertIn("dax", recipe)
        self.assertIn("tags", recipe)


class TestGetAllRecipes(unittest.TestCase):
    def test_total_count(self):
        self.assertEqual(len(get_all_recipes()), 21)  # 6+8+7


class TestApplyRecipes(unittest.TestCase):
    def test_injection(self):
        measures = {}
        recipes = [{"name": "Revenue", "dax": "SUM('Sales'[Revenue])"}]
        changes = apply_recipes(measures, recipes)
        self.assertIn("Revenue", measures)
        self.assertEqual(changes["injected"], ["Revenue"])

    def test_skip_existing(self):
        measures = {"Revenue": "EXISTING"}
        recipes = [{"name": "Revenue", "dax": "SUM('Sales'[Revenue])"}]
        changes = apply_recipes(measures, recipes)
        self.assertEqual(measures["Revenue"], "EXISTING")
        self.assertEqual(changes["skipped"], ["Revenue"])

    def test_overwrite(self):
        measures = {"Revenue": "EXISTING"}
        recipes = [{"name": "Revenue", "dax": "NEW_DAX"}]
        changes = apply_recipes(measures, recipes, overwrite=True)
        self.assertEqual(measures["Revenue"], "NEW_DAX")

    def test_replacement_mode(self):
        measures = {"Rev": "IF(ISBLANK(x), 0, x)"}
        recipes = [{"match": r"IF\(ISBLANK\((.+?)\),\s*0,\s*\1\)",
                     "replacement": r"COALESCE(\1, 0)"}]
        changes = apply_recipes(measures, recipes)
        self.assertIn("Rev", changes["replaced"])
        self.assertIn("COALESCE", measures["Rev"])

    def test_empty_recipe_skipped(self):
        measures = {}
        changes = apply_recipes(measures, [{"name": "", "dax": ""}])
        self.assertEqual(changes["injected"], [])


class TestRecipesToMarketplace(unittest.TestCase):
    def test_converts_to_marketplace_format(self):
        patterns = recipes_to_marketplace_format("healthcare")
        self.assertEqual(len(patterns), 6)
        p = patterns[0]
        self.assertIn("metadata", p)
        self.assertIn("payload", p)
        self.assertEqual(p["metadata"]["category"], "dax_recipe")

    def test_unknown_industry_empty(self):
        self.assertEqual(recipes_to_marketplace_format("unknown"), [])


# ===================================================================
# Marketplace
# ===================================================================

class TestParseVersion(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(_parse_version("1.2.3"), (1, 2, 3))

    def test_invalid(self):
        self.assertEqual(_parse_version("invalid"), (0, 0, 0))


class TestPatternMetadata(unittest.TestCase):
    def test_defaults(self):
        m = PatternMetadata()
        self.assertEqual(m.name, "")
        self.assertEqual(m.category, "dax_recipe")

    def test_matches_tags(self):
        m = PatternMetadata(tags=["revenue", "finance"])
        self.assertTrue(m.matches(tags=["revenue"]))
        self.assertFalse(m.matches(tags=["healthcare"]))

    def test_matches_category(self):
        m = PatternMetadata(category="visual_mapping")
        self.assertTrue(m.matches(category="visual_mapping"))
        self.assertFalse(m.matches(category="dax_recipe"))

    def test_matches_name_pattern(self):
        m = PatternMetadata(name="Revenue YTD")
        self.assertTrue(m.matches(name_pattern="revenue"))
        self.assertFalse(m.matches(name_pattern="^cost"))

    def test_invalid_category_defaults(self):
        m = PatternMetadata(category="invalid_cat")
        self.assertEqual(m.category, "dax_recipe")


class TestPattern(unittest.TestCase):
    def test_from_dict(self):
        p = Pattern({"name": "Test", "version": "2.0.0"}, {"dax": "x"})
        self.assertEqual(p.name, "Test")
        self.assertEqual(p.version, "2.0.0")
        self.assertEqual(p.category, "dax_recipe")

    def test_to_dict(self):
        p = Pattern({"name": "X"}, {"inject": {"name": "X", "dax": "Y"}})
        d = p.to_dict()
        self.assertIn("metadata", d)
        self.assertIn("payload", d)


class TestPatternRegistry(unittest.TestCase):
    def test_empty(self):
        r = PatternRegistry()
        self.assertEqual(r.count, 0)
        self.assertEqual(r.list_all(), [])

    def test_register_and_get(self):
        r = PatternRegistry()
        r.register({
            "metadata": {"name": "Test", "version": "1.0.0"},
            "payload": {"dax": "x"},
        })
        self.assertEqual(r.count, 1)
        p = r.get("Test")
        self.assertIsNotNone(p)
        self.assertEqual(p.version, "1.0.0")

    def test_versioning(self):
        r = PatternRegistry()
        r.register({"metadata": {"name": "A", "version": "1.0.0"}, "payload": {}})
        r.register({"metadata": {"name": "A", "version": "2.0.0"}, "payload": {}})
        self.assertEqual(r.count, 1)
        self.assertEqual(r.get("A").version, "2.0.0")
        self.assertEqual(r.get("A", "1.0.0").version, "1.0.0")

    def test_get_unknown(self):
        r = PatternRegistry()
        self.assertIsNone(r.get("nope"))

    def test_search_by_tags(self):
        r = PatternRegistry()
        r.register({"metadata": {"name": "A", "tags": ["rev"]}, "payload": {}})
        r.register({"metadata": {"name": "B", "tags": ["cost"]}, "payload": {}})
        results = r.search(tags=["rev"])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "A")

    def test_search_by_category(self):
        r = PatternRegistry()
        r.register({"metadata": {"name": "A", "category": "dax_recipe"}, "payload": {}})
        r.register({"metadata": {"name": "B", "category": "visual_mapping"}, "payload": {}})
        self.assertEqual(len(r.search(category="visual_mapping")), 1)

    def test_load_from_dir(self):
        r = PatternRegistry()
        marketplace_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "examples", "marketplace"
        )
        if os.path.isdir(marketplace_dir):
            count = r.load(marketplace_dir)
            self.assertGreater(count, 0)

    def test_load_invalid_dir(self):
        r = PatternRegistry()
        self.assertEqual(r.load("/nonexistent/dir"), 0)

    def test_apply_dax_recipes(self):
        r = PatternRegistry()
        r.register({
            "metadata": {"name": "Rev", "tags": ["rev"], "category": "dax_recipe"},
            "payload": {"inject": {"name": "Revenue", "dax": "SUM('Sales'[Rev])"}},
        })
        measures = {}
        changes = r.apply_dax_recipes(measures, tags=["rev"])
        self.assertIn("Revenue", measures)
        self.assertEqual(changes["injected"], ["Revenue"])

    def test_apply_visual_overrides(self):
        r = PatternRegistry()
        r.register({
            "metadata": {"name": "MapFix", "category": "visual_mapping"},
            "payload": {"mappings": {"custom_geo": "azureMap"}},
        })
        vmap = {}
        count = r.apply_visual_overrides(vmap)
        self.assertEqual(count, 1)
        self.assertEqual(vmap["custom_geo"], "azureMap")

    def test_export(self):
        with tempfile.TemporaryDirectory() as td:
            r = PatternRegistry()
            r.register({"metadata": {"name": "X"}, "payload": {}})
            path = os.path.join(td, "export.json")
            r.export(path)
            with open(path) as f:
                data = json.load(f)
            self.assertEqual(len(data), 1)

    def test_to_dict(self):
        r = PatternRegistry()
        r.register({"metadata": {"name": "X"}, "payload": {}})
        d = r.to_dict()
        self.assertEqual(d["total_patterns"], 1)

    def test_bridge_dax_recipes_to_marketplace(self):
        """Integration: dax_recipes → marketplace format → registry."""
        r = PatternRegistry()
        patterns = recipes_to_marketplace_format("healthcare")
        for p in patterns:
            r.register(p)
        self.assertEqual(r.count, 6)


# ===================================================================
# HTML Template
# ===================================================================

class TestEsc(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(esc("<b>"), "&lt;b&gt;")

    def test_none(self):
        self.assertEqual(esc(None), "")

    def test_number(self):
        self.assertEqual(esc(42), "42")


class TestCss(unittest.TestCase):
    def test_returns_style(self):
        css = get_report_css()
        self.assertIn("<style>", css)
        self.assertIn("stat-card", css)
        self.assertIn("badge", css)

    def test_dark_mode(self):
        css = get_report_css()
        self.assertIn("prefers-color-scheme: dark", css)


class TestJs(unittest.TestCase):
    def test_returns_script(self):
        js = get_report_js()
        self.assertIn("<script>", js)
        self.assertIn("toggleSection", js)
        self.assertIn("sortTable", js)


class TestHtmlOpen(unittest.TestCase):
    def test_basic(self):
        html = html_open("Test Report")
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("Test Report", html)

    def test_with_subtitle(self):
        html = html_open("Title", subtitle="Sub")
        self.assertIn("Sub", html)


class TestHtmlClose(unittest.TestCase):
    def test_basic(self):
        html = html_close()
        self.assertIn("</html>", html)
        self.assertIn("</body>", html)

    def test_with_version(self):
        html = html_close(version="18.0")
        self.assertIn("18.0", html)


class TestStatCard(unittest.TestCase):
    def test_basic(self):
        html = stat_card("42", "Tables")
        self.assertIn("42", html)
        self.assertIn("Tables", html)
        self.assertIn("stat-card", html)

    def test_accent(self):
        html = stat_card("5", "Errors", accent="fail")
        self.assertIn("accent-fail", html)


class TestStatGrid(unittest.TestCase):
    def test_wraps(self):
        cards = [stat_card("1", "A"), stat_card("2", "B")]
        html = stat_grid(cards)
        self.assertIn("stat-grid", html)
        self.assertEqual(html.count("stat-card"), 2)


class TestSection(unittest.TestCase):
    def test_open_close(self):
        html = section_open("sec1", "Title", icon="📊")
        self.assertIn("sec1", html)
        self.assertIn("Title", html)
        close = section_close()
        self.assertIn("</div>", close)

    def test_collapsed(self):
        html = section_open("s", "T", collapsed=True)
        self.assertIn("collapsed", html)


class TestCard(unittest.TestCase):
    def test_basic(self):
        html = card("content", "Title")
        self.assertIn("content", html)
        self.assertIn("Title", html)


class TestBadge(unittest.TestCase):
    def test_green(self):
        html = badge("PASS", "GREEN")
        self.assertIn("badge-green", html)

    def test_auto_map(self):
        html = badge("95%", "HIGH")
        self.assertIn("badge-green", html)

    def test_default_gray(self):
        html = badge("N/A")
        self.assertIn("badge-gray", html)


class TestFidelityBar(unittest.TestCase):
    def test_high(self):
        html = fidelity_bar(98)
        self.assertIn("high", html)

    def test_medium(self):
        html = fidelity_bar(85)
        self.assertIn("med", html)

    def test_low(self):
        html = fidelity_bar(50)
        self.assertIn("low", html)


class TestDonutChart(unittest.TestCase):
    def test_renders_svg(self):
        html = donut_chart([("A", 70, "#107C10"), ("B", 30, "#D13438")])
        self.assertIn("<svg", html)
        self.assertIn("A", html)


class TestBarChart(unittest.TestCase):
    def test_renders_bars(self):
        html = bar_chart([("Tables", 10), ("Measures", 5)])
        self.assertIn("Tables", html)
        self.assertIn("bar-fill", html)

    def test_empty(self):
        self.assertEqual(bar_chart([]), "")


class TestDataTable(unittest.TestCase):
    def test_basic(self):
        html = data_table(["Name", "Count"], [["Tables", "10"]])
        self.assertIn("<table", html)
        self.assertIn("Name", html)
        self.assertIn("Tables", html)

    def test_searchable(self):
        html = data_table(["A"], [["x"]], searchable=True, table_id="t1")
        self.assertIn("search-box", html)

    def test_sortable(self):
        html = data_table(["A"], [["x"]], sortable=True, table_id="t2")
        self.assertIn("sortTable", html)


class TestTabBar(unittest.TestCase):
    def test_renders(self):
        html = tab_bar("g1", [("t1", "Tab 1"), ("t2", "Tab 2")])
        self.assertIn("tab-bar", html)
        self.assertIn("Tab 1", html)

    def test_first_active(self):
        html = tab_bar("g1", [("t1", "T1"), ("t2", "T2")])
        # First button should have 'active'
        self.assertIn(' active"', html)


class TestTabContent(unittest.TestCase):
    def test_active(self):
        html = tab_content("g1", "t1", "Content", active=True)
        self.assertIn("active", html)
        self.assertIn("Content", html)

    def test_inactive(self):
        html = tab_content("g1", "t2", "Hidden")
        self.assertNotIn("active", html)


class TestFlowDiagram(unittest.TestCase):
    def test_renders(self):
        html = flow_diagram(["Extract", "Transform", "Load"])
        self.assertIn("Extract", html)
        self.assertIn("→", html)
        self.assertEqual(html.count("flow-step"), 3)


class TestCmdBox(unittest.TestCase):
    def test_renders(self):
        html = cmd_box("python migrate.py --batch")
        self.assertIn("cmd-box", html)
        self.assertIn("migrate.py", html)


class TestColorConstants(unittest.TestCase):
    def test_constants_exist(self):
        self.assertTrue(PBI_BLUE.startswith("#"))
        self.assertTrue(SUCCESS.startswith("#"))
        self.assertTrue(FAIL.startswith("#"))


if __name__ == "__main__":
    unittest.main()
