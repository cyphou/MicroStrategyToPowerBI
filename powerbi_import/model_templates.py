"""
Industry-specific semantic model templates.

Pre-built star-schema skeletons for Healthcare, Finance, and Retail.
Each template provides fact/dimension tables, relationships, measures,
and hierarchies that can be merged into a migrated model.
"""

import copy
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Healthcare template
# ---------------------------------------------------------------------------

_HEALTHCARE_TEMPLATE = {
    "name": "Healthcare",
    "description": "Patient encounters star schema — Encounters fact with Patient, Provider, Facility dimensions",
    "tables": [
        {
            "name": "Encounters",
            "role": "fact",
            "columns": [
                {"name": "EncounterId", "dataType": "string", "isKey": True},
                {"name": "PatientId", "dataType": "string"},
                {"name": "ProviderId", "dataType": "string"},
                {"name": "FacilityId", "dataType": "string"},
                {"name": "AdmitDate", "dataType": "dateTime", "dataCategory": "Date"},
                {"name": "DischargeDate", "dataType": "dateTime", "dataCategory": "Date"},
                {"name": "LengthOfStay", "dataType": "int64"},
                {"name": "DiagnosisCode", "dataType": "string"},
                {"name": "ProcedureCode", "dataType": "string"},
                {"name": "TotalCharges", "dataType": "double"},
                {"name": "IsReadmission", "dataType": "boolean"},
                {"name": "DischargeStatus", "dataType": "string"},
            ],
        },
        {
            "name": "Patients",
            "role": "dimension",
            "columns": [
                {"name": "PatientId", "dataType": "string", "isKey": True},
                {"name": "PatientName", "dataType": "string"},
                {"name": "DateOfBirth", "dataType": "dateTime", "dataCategory": "Date"},
                {"name": "Gender", "dataType": "string"},
                {"name": "InsuranceType", "dataType": "string"},
            ],
        },
        {
            "name": "Providers",
            "role": "dimension",
            "columns": [
                {"name": "ProviderId", "dataType": "string", "isKey": True},
                {"name": "ProviderName", "dataType": "string"},
                {"name": "Specialty", "dataType": "string"},
                {"name": "Department", "dataType": "string"},
            ],
        },
        {
            "name": "Facilities",
            "role": "dimension",
            "columns": [
                {"name": "FacilityId", "dataType": "string", "isKey": True},
                {"name": "FacilityName", "dataType": "string"},
                {"name": "FacilityType", "dataType": "string"},
                {"name": "City", "dataType": "string", "dataCategory": "City"},
                {"name": "State", "dataType": "string", "dataCategory": "StateOrProvince"},
            ],
        },
    ],
    "relationships": [
        {"from_table": "Encounters", "from_column": "PatientId", "to_table": "Patients", "to_column": "PatientId", "cardinality": "manyToOne"},
        {"from_table": "Encounters", "from_column": "ProviderId", "to_table": "Providers", "to_column": "ProviderId", "cardinality": "manyToOne"},
        {"from_table": "Encounters", "from_column": "FacilityId", "to_table": "Facilities", "to_column": "FacilityId", "cardinality": "manyToOne"},
    ],
    "measures": [
        {"name": "Total Encounters", "dax": "COUNTROWS('Encounters')", "description": "Count of all encounters"},
        {"name": "Avg Length of Stay", "dax": "AVERAGE('Encounters'[LengthOfStay])", "description": "Average length of stay in days"},
        {"name": "Readmission Rate", "dax": "DIVIDE(CALCULATE(COUNTROWS('Encounters'), 'Encounters'[IsReadmission] = TRUE()), COUNTROWS('Encounters'))", "description": "Percentage of readmissions"},
        {"name": "Total Charges", "dax": "SUM('Encounters'[TotalCharges])", "description": "Sum of all charges"},
    ],
    "hierarchies": [
        {"name": "Geography", "table": "Facilities", "levels": ["State", "City", "FacilityName"]},
    ],
}


# ---------------------------------------------------------------------------
# Finance template
# ---------------------------------------------------------------------------

_FINANCE_TEMPLATE = {
    "name": "Finance",
    "description": "Financial reporting star schema — Financials fact with Accounts, CostCenters, AR dimensions",
    "tables": [
        {
            "name": "Financials",
            "role": "fact",
            "columns": [
                {"name": "TransactionId", "dataType": "string", "isKey": True},
                {"name": "AccountId", "dataType": "string"},
                {"name": "CostCenterId", "dataType": "string"},
                {"name": "TransactionDate", "dataType": "dateTime", "dataCategory": "Date"},
                {"name": "Amount", "dataType": "double"},
                {"name": "BudgetAmount", "dataType": "double"},
                {"name": "TransactionType", "dataType": "string"},
                {"name": "FiscalYear", "dataType": "int64"},
                {"name": "FiscalQuarter", "dataType": "string"},
                {"name": "Currency", "dataType": "string"},
            ],
        },
        {
            "name": "Accounts",
            "role": "dimension",
            "columns": [
                {"name": "AccountId", "dataType": "string", "isKey": True},
                {"name": "AccountName", "dataType": "string"},
                {"name": "AccountType", "dataType": "string"},
                {"name": "AccountCategory", "dataType": "string"},
            ],
        },
        {
            "name": "CostCenters",
            "role": "dimension",
            "columns": [
                {"name": "CostCenterId", "dataType": "string", "isKey": True},
                {"name": "CostCenterName", "dataType": "string"},
                {"name": "Department", "dataType": "string"},
                {"name": "Division", "dataType": "string"},
            ],
        },
        {
            "name": "AccountsReceivable",
            "role": "dimension",
            "columns": [
                {"name": "InvoiceId", "dataType": "string", "isKey": True},
                {"name": "AccountId", "dataType": "string"},
                {"name": "InvoiceDate", "dataType": "dateTime", "dataCategory": "Date"},
                {"name": "DueDate", "dataType": "dateTime", "dataCategory": "Date"},
                {"name": "InvoiceAmount", "dataType": "double"},
                {"name": "PaidAmount", "dataType": "double"},
            ],
        },
    ],
    "relationships": [
        {"from_table": "Financials", "from_column": "AccountId", "to_table": "Accounts", "to_column": "AccountId", "cardinality": "manyToOne"},
        {"from_table": "Financials", "from_column": "CostCenterId", "to_table": "CostCenters", "to_column": "CostCenterId", "cardinality": "manyToOne"},
        {"from_table": "AccountsReceivable", "from_column": "AccountId", "to_table": "Accounts", "to_column": "AccountId", "cardinality": "manyToOne"},
    ],
    "measures": [
        {"name": "Net Revenue", "dax": "SUM('Financials'[Amount])", "description": "Total revenue"},
        {"name": "Gross Margin %", "dax": "DIVIDE(SUM('Financials'[Amount]) - SUM('Financials'[BudgetAmount]), SUM('Financials'[Amount]))", "description": "Gross margin percentage"},
        {"name": "Budget Variance", "dax": "SUM('Financials'[Amount]) - SUM('Financials'[BudgetAmount])", "description": "Actual minus budget"},
        {"name": "Budget Variance %", "dax": "DIVIDE(SUM('Financials'[Amount]) - SUM('Financials'[BudgetAmount]), SUM('Financials'[BudgetAmount]))", "description": "Variance as percent of budget"},
    ],
    "hierarchies": [
        {"name": "Account Hierarchy", "table": "Accounts", "levels": ["AccountCategory", "AccountType", "AccountName"]},
        {"name": "Organization", "table": "CostCenters", "levels": ["Division", "Department", "CostCenterName"]},
    ],
}


# ---------------------------------------------------------------------------
# Retail template
# ---------------------------------------------------------------------------

_RETAIL_TEMPLATE = {
    "name": "Retail",
    "description": "Retail sales star schema — Sales fact with Products, Stores, Customers dimensions",
    "tables": [
        {
            "name": "Sales",
            "role": "fact",
            "columns": [
                {"name": "TransactionId", "dataType": "string", "isKey": True},
                {"name": "ProductId", "dataType": "string"},
                {"name": "StoreId", "dataType": "string"},
                {"name": "CustomerId", "dataType": "string"},
                {"name": "TransactionDate", "dataType": "dateTime", "dataCategory": "Date"},
                {"name": "Quantity", "dataType": "int64"},
                {"name": "UnitPrice", "dataType": "double"},
                {"name": "Revenue", "dataType": "double"},
                {"name": "Cost", "dataType": "double"},
                {"name": "Discount", "dataType": "double"},
            ],
        },
        {
            "name": "Products",
            "role": "dimension",
            "columns": [
                {"name": "ProductId", "dataType": "string", "isKey": True},
                {"name": "ProductName", "dataType": "string"},
                {"name": "Category", "dataType": "string"},
                {"name": "SubCategory", "dataType": "string"},
                {"name": "Brand", "dataType": "string"},
                {"name": "UnitCost", "dataType": "double"},
            ],
        },
        {
            "name": "Stores",
            "role": "dimension",
            "columns": [
                {"name": "StoreId", "dataType": "string", "isKey": True},
                {"name": "StoreName", "dataType": "string"},
                {"name": "StoreType", "dataType": "string"},
                {"name": "City", "dataType": "string", "dataCategory": "City"},
                {"name": "State", "dataType": "string", "dataCategory": "StateOrProvince"},
                {"name": "Region", "dataType": "string"},
            ],
        },
        {
            "name": "Customers",
            "role": "dimension",
            "columns": [
                {"name": "CustomerId", "dataType": "string", "isKey": True},
                {"name": "CustomerName", "dataType": "string"},
                {"name": "Segment", "dataType": "string"},
                {"name": "City", "dataType": "string", "dataCategory": "City"},
                {"name": "State", "dataType": "string", "dataCategory": "StateOrProvince"},
            ],
        },
    ],
    "relationships": [
        {"from_table": "Sales", "from_column": "ProductId", "to_table": "Products", "to_column": "ProductId", "cardinality": "manyToOne"},
        {"from_table": "Sales", "from_column": "StoreId", "to_table": "Stores", "to_column": "StoreId", "cardinality": "manyToOne"},
        {"from_table": "Sales", "from_column": "CustomerId", "to_table": "Customers", "to_column": "CustomerId", "cardinality": "manyToOne"},
    ],
    "measures": [
        {"name": "Total Revenue", "dax": "SUM('Sales'[Revenue])", "description": "Sum of revenue"},
        {"name": "Total Quantity", "dax": "SUM('Sales'[Quantity])", "description": "Sum of quantity sold"},
        {"name": "Avg Revenue per Transaction", "dax": "AVERAGE('Sales'[Revenue])", "description": "Average revenue per transaction"},
        {"name": "Items per Basket", "dax": "DIVIDE(SUM('Sales'[Quantity]), DISTINCTCOUNT('Sales'[TransactionId]))", "description": "Average items per transaction"},
        {"name": "Gross Margin", "dax": "SUM('Sales'[Revenue]) - SUM('Sales'[Cost])", "description": "Revenue minus cost"},
    ],
    "hierarchies": [
        {"name": "Product Hierarchy", "table": "Products", "levels": ["Category", "SubCategory", "ProductName"]},
        {"name": "Store Geography", "table": "Stores", "levels": ["Region", "State", "City", "StoreName"]},
    ],
}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_TEMPLATES = {
    "healthcare": _HEALTHCARE_TEMPLATE,
    "finance": _FINANCE_TEMPLATE,
    "retail": _RETAIL_TEMPLATE,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_templates():
    """Return available template names."""
    return list(_TEMPLATES.keys())


def get_template(industry):
    """Return a deep copy of a template by industry name.

    Returns None if the template does not exist.
    """
    tpl = _TEMPLATES.get(industry.lower().strip() if industry else "")
    return copy.deepcopy(tpl) if tpl else None


def apply_template(template, existing_tables):
    """Merge template skeleton into existing migrated tables.

    - Existing tables matched (case-insensitive) get enriched with missing columns.
    - New tables from template are added as skeletons.
    - Measures are always added.
    - Relationships only added if both endpoint tables exist.
    - Hierarchies only added if their parent table exists.

    Args:
        template: A template dict (from ``get_template``).
        existing_tables: list of table dicts with at least ``name`` and ``columns``.

    Returns:
        dict with keys: tables, measures, relationships, hierarchies, stats.
    """
    existing_by_name = {t["name"].lower(): t for t in existing_tables}
    result_tables = list(existing_tables)

    stats = {
        "new_tables": 0,
        "columns_added": 0,
        "measures_added": 0,
        "relationships_added": 0,
        "hierarchies_added": 0,
    }

    # Tables + columns
    for tpl_table in template.get("tables", []):
        tname_lower = tpl_table["name"].lower()
        if tname_lower in existing_by_name:
            # Enrich existing table with missing columns
            existing = existing_by_name[tname_lower]
            existing_cols = {c["name"].lower() for c in existing.get("columns", [])}
            for col in tpl_table.get("columns", []):
                if col["name"].lower() not in existing_cols:
                    existing.setdefault("columns", []).append(copy.deepcopy(col))
                    stats["columns_added"] += 1
        else:
            # Add new template table
            result_tables.append(copy.deepcopy(tpl_table))
            existing_by_name[tname_lower] = result_tables[-1]
            stats["new_tables"] += 1

    # Measures
    measures = copy.deepcopy(template.get("measures", []))
    stats["measures_added"] = len(measures)

    # Relationships — only if both tables exist
    relationships = []
    for rel in template.get("relationships", []):
        if (rel["from_table"].lower() in existing_by_name
                and rel["to_table"].lower() in existing_by_name):
            relationships.append(copy.deepcopy(rel))
            stats["relationships_added"] += 1

    # Hierarchies — only if parent table exists
    hierarchies = []
    for hier in template.get("hierarchies", []):
        if hier.get("table", "").lower() in existing_by_name:
            hierarchies.append(copy.deepcopy(hier))
            stats["hierarchies_added"] += 1

    logger.info("Template '%s' applied: %s", template.get("name", "?"), stats)

    return {
        "tables": result_tables,
        "measures": measures,
        "relationships": relationships,
        "hierarchies": hierarchies,
        "stats": stats,
    }
