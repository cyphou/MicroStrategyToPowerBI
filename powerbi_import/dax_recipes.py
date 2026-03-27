"""
DAX recipe library — curated KPI measure templates by industry.

Three verticals: Healthcare (6 recipes), Finance (8), Retail (7).
Recipes can be injected into a measures dict or used to regex-replace
existing DAX expressions.
"""

import logging
import re

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Healthcare recipes (6)
# ---------------------------------------------------------------------------

_HEALTHCARE_RECIPES = [
    {
        "name": "Total Encounters",
        "dax": "COUNTROWS('Encounters')",
        "description": "Count of all patient encounters",
        "tags": ["clinical", "operations", "volume"],
    },
    {
        "name": "Average Length of Stay",
        "dax": "AVERAGE('Encounters'[LengthOfStay])",
        "description": "Average length of stay in days",
        "tags": ["clinical", "los", "quality"],
    },
    {
        "name": "Readmission Rate",
        "dax": "DIVIDE(CALCULATE(COUNTROWS('Encounters'), 'Encounters'[IsReadmission] = TRUE()), COUNTROWS('Encounters'))",
        "description": "30-day all-cause readmission rate",
        "tags": ["clinical", "readmission", "quality"],
    },
    {
        "name": "Mortality Rate",
        "dax": "DIVIDE(CALCULATE(COUNTROWS('Encounters'), 'Encounters'[DischargeStatus] = \"Expired\"), COUNTROWS('Encounters'))",
        "description": "In-hospital mortality rate",
        "tags": ["clinical", "mortality", "quality"],
    },
    {
        "name": "ED Visits",
        "dax": "CALCULATE(COUNTROWS('Encounters'), 'Encounters'[DiagnosisCode] = \"ED\")",
        "description": "Emergency department visit count",
        "tags": ["operations", "ed", "capacity"],
    },
    {
        "name": "Revenue per Encounter",
        "dax": "DIVIDE(SUM('Encounters'[TotalCharges]), COUNTROWS('Encounters'))",
        "description": "Average charges per encounter",
        "tags": ["operations", "revenue"],
    },
]


# ---------------------------------------------------------------------------
# Finance recipes (8)
# ---------------------------------------------------------------------------

_FINANCE_RECIPES = [
    {
        "name": "Net Revenue",
        "dax": "SUM('Financials'[Amount])",
        "description": "Total net revenue",
        "tags": ["revenue", "profitability"],
    },
    {
        "name": "Gross Margin %",
        "dax": "DIVIDE(SUM('Financials'[Amount]) - SUM('Financials'[BudgetAmount]), SUM('Financials'[Amount]))",
        "description": "Gross margin as percentage of revenue",
        "tags": ["profitability", "margin"],
    },
    {
        "name": "Budget Variance",
        "dax": "SUM('Financials'[Amount]) - SUM('Financials'[BudgetAmount])",
        "description": "Actual minus budget amount",
        "tags": ["budget", "variance"],
    },
    {
        "name": "Budget Variance %",
        "dax": "DIVIDE(SUM('Financials'[Amount]) - SUM('Financials'[BudgetAmount]), SUM('Financials'[BudgetAmount]))",
        "description": "Variance as percentage of budget",
        "tags": ["budget", "variance"],
    },
    {
        "name": "Revenue YTD",
        "dax": "TOTALYTD(SUM('Financials'[Amount]), 'Calendar'[Date])",
        "description": "Year-to-date revenue",
        "tags": ["revenue", "time-intelligence"],
    },
    {
        "name": "Revenue PY",
        "dax": "CALCULATE(SUM('Financials'[Amount]), SAMEPERIODLASTYEAR('Calendar'[Date]))",
        "description": "Prior year revenue",
        "tags": ["revenue", "time-intelligence"],
    },
    {
        "name": "Operating Ratio",
        "dax": "DIVIDE(SUM('Financials'[BudgetAmount]), SUM('Financials'[Amount]))",
        "description": "Operating expenses to revenue ratio",
        "tags": ["efficiency", "profitability"],
    },
    {
        "name": "Days Sales Outstanding",
        "dax": "DIVIDE(SUM('AccountsReceivable'[InvoiceAmount]) - SUM('AccountsReceivable'[PaidAmount]), SUM('Financials'[Amount])) * 365",
        "description": "Average days to collect receivables",
        "tags": ["ar", "dso", "efficiency"],
    },
]


# ---------------------------------------------------------------------------
# Retail recipes (7)
# ---------------------------------------------------------------------------

_RETAIL_RECIPES = [
    {
        "name": "Total Revenue",
        "dax": "SUM('Sales'[Revenue])",
        "description": "Total sales revenue",
        "tags": ["revenue"],
    },
    {
        "name": "Basket Size",
        "dax": "DIVIDE(SUM('Sales'[Quantity]), DISTINCTCOUNT('Sales'[TransactionId]))",
        "description": "Average items per transaction",
        "tags": ["basket", "conversion"],
    },
    {
        "name": "Avg Transaction Value",
        "dax": "DIVIDE(SUM('Sales'[Revenue]), DISTINCTCOUNT('Sales'[TransactionId]))",
        "description": "Average revenue per transaction",
        "tags": ["revenue", "basket"],
    },
    {
        "name": "Gross Margin",
        "dax": "SUM('Sales'[Revenue]) - SUM('Sales'[Cost])",
        "description": "Revenue minus cost of goods",
        "tags": ["profitability", "margin"],
    },
    {
        "name": "Inventory Turnover",
        "dax": "DIVIDE(SUM('Sales'[Cost]), AVERAGE('Products'[UnitCost]))",
        "description": "Cost of goods sold divided by average inventory",
        "tags": ["inventory", "turnover"],
    },
    {
        "name": "Same-Store Sales Growth",
        "dax": "VAR _CY = SUM('Sales'[Revenue]) VAR _PY = CALCULATE(SUM('Sales'[Revenue]), SAMEPERIODLASTYEAR('Calendar'[Date])) RETURN DIVIDE(_CY - _PY, _PY)",
        "description": "Year-over-year revenue growth for comparable stores",
        "tags": ["revenue", "growth", "comp-sales"],
    },
    {
        "name": "Customer Lifetime Value",
        "dax": "DIVIDE(SUM('Sales'[Revenue]), DISTINCTCOUNT('Sales'[CustomerId]))",
        "description": "Average revenue per customer",
        "tags": ["customer", "clv"],
    },
]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_INDUSTRY_RECIPES = {
    "healthcare": _HEALTHCARE_RECIPES,
    "finance": _FINANCE_RECIPES,
    "retail": _RETAIL_RECIPES,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_industries():
    """Return available industry names."""
    return list(_INDUSTRY_RECIPES.keys())


def get_industry_recipes(industry):
    """Return recipes for one industry vertical."""
    return list(_INDUSTRY_RECIPES.get(industry.lower().strip(), []))


def get_all_recipes():
    """Return all recipes across all industries."""
    result = []
    for recipes in _INDUSTRY_RECIPES.values():
        result.extend(recipes)
    return result


def apply_recipes(measures, recipes, overwrite=False):
    """Apply recipes to a measures dict (in-place).

    Two modes:
      - **Injection**: recipe has ``name`` + ``dax`` → adds new measure
      - **Replacement**: recipe has ``match`` + ``replacement`` → regex-replaces

    Args:
        measures: dict mapping measure name → DAX expression.
        recipes: list of recipe dicts.
        overwrite: if True, replace existing measures with same name.

    Returns:
        dict with keys: injected (list), replaced (list), skipped (list).
    """
    changes = {"injected": [], "replaced": [], "skipped": []}

    for recipe in recipes:
        # Replacement mode
        if "match" in recipe and "replacement" in recipe:
            pattern = re.compile(recipe["match"])
            for name, dax in list(measures.items()):
                new_dax = pattern.sub(recipe["replacement"], dax)
                if new_dax != dax:
                    measures[name] = new_dax
                    changes["replaced"].append(name)
            continue

        # Injection mode
        rname = recipe.get("name", "")
        rdax = recipe.get("dax", "")
        if not rname or not rdax:
            continue

        if rname in measures and not overwrite:
            changes["skipped"].append(rname)
        else:
            measures[rname] = rdax
            changes["injected"].append(rname)

    logger.info("Recipes applied: %d injected, %d replaced, %d skipped",
                len(changes["injected"]), len(changes["replaced"]),
                len(changes["skipped"]))
    return changes


def recipes_to_marketplace_format(industry):
    """Convert industry recipes to PatternRegistry-compatible format.

    Returns:
        list of dicts ready for ``PatternRegistry.register()``.
    """
    recipes = get_industry_recipes(industry)
    patterns = []
    for recipe in recipes:
        pattern = {
            "metadata": {
                "name": recipe["name"],
                "version": "1.0.0",
                "author": "built-in",
                "description": recipe.get("description", ""),
                "tags": recipe.get("tags", []),
                "category": "dax_recipe",
            },
            "payload": {
                "inject": {"name": recipe["name"], "dax": recipe["dax"]},
            },
        }
        patterns.append(pattern)
    return patterns
