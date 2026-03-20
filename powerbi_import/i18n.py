"""
Internationalization and localization support.

Provides culture-aware format strings, locale metadata, translated
captions for TMDL, and RTL layout detection for visual generation.
"""

import logging

logger = logging.getLogger(__name__)

# ── Supported cultures ───────────────────────────────────────────

_SUPPORTED_CULTURES = {
    "en-US", "en-GB", "fr-FR", "de-DE", "es-ES", "it-IT", "pt-BR",
    "ja-JP", "zh-CN", "zh-TW", "ko-KR", "ar-SA", "he-IL", "ru-RU",
    "nl-NL", "sv-SE", "da-DK", "nb-NO", "fi-FI", "pl-PL", "tr-TR",
    "th-TH", "vi-VN", "hi-IN", "pt-PT", "cs-CZ", "hu-HU", "ro-RO",
    "uk-UA", "el-GR", "id-ID", "ms-MY",
}

# ── RTL cultures ─────────────────────────────────────────────────

_RTL_CULTURES = {"ar-SA", "he-IL", "fa-IR", "ur-PK"}


def is_rtl_culture(culture):
    """Return True if the culture uses right-to-left text direction."""
    if not culture:
        return False
    return culture in _RTL_CULTURES or culture.split("-")[0] in ("ar", "he", "fa", "ur")


# ── Currency symbols per culture ─────────────────────────────────

_CURRENCY_SYMBOL = {
    "en-US": "$",
    "en-GB": "£",
    "fr-FR": "€",
    "de-DE": "€",
    "es-ES": "€",
    "it-IT": "€",
    "pt-BR": "R$",
    "pt-PT": "€",
    "ja-JP": "¥",
    "zh-CN": "¥",
    "zh-TW": "NT$",
    "ko-KR": "₩",
    "ar-SA": "﷼",
    "he-IL": "₪",
    "ru-RU": "₽",
    "nl-NL": "€",
    "sv-SE": "kr",
    "da-DK": "kr",
    "nb-NO": "kr",
    "fi-FI": "€",
    "pl-PL": "zł",
    "tr-TR": "₺",
    "th-TH": "฿",
    "hi-IN": "₹",
    "cs-CZ": "Kč",
    "hu-HU": "Ft",
    "ro-RO": "lei",
    "uk-UA": "₴",
    "el-GR": "€",
    "id-ID": "Rp",
    "ms-MY": "RM",
    "vi-VN": "₫",
}

# ── Number formats per culture ───────────────────────────────────
# Pattern: (thousands_separator, decimal_separator)

_NUMBER_FORMAT = {
    "en-US": (",", "."),
    "en-GB": (",", "."),
    "fr-FR": ("\u202f", ","),  # narrow no-break space
    "de-DE": (".", ","),
    "es-ES": (".", ","),
    "it-IT": (".", ","),
    "pt-BR": (".", ","),
    "pt-PT": (".", ","),
    "ja-JP": (",", "."),
    "zh-CN": (",", "."),
    "zh-TW": (",", "."),
    "ko-KR": (",", "."),
    "ar-SA": (",", "."),
    "he-IL": (",", "."),
    "ru-RU": ("\u00a0", ","),  # no-break space
    "nl-NL": (".", ","),
    "sv-SE": ("\u00a0", ","),
    "da-DK": (".", ","),
    "nb-NO": ("\u00a0", ","),
    "fi-FI": ("\u00a0", ","),
    "pl-PL": ("\u00a0", ","),
    "tr-TR": (".", ","),
    "th-TH": (",", "."),
    "hi-IN": (",", "."),
    "cs-CZ": ("\u00a0", ","),
    "hu-HU": ("\u00a0", ","),
    "ro-RO": (".", ","),
    "uk-UA": ("\u00a0", ","),
    "el-GR": (".", ","),
    "id-ID": (".", ","),
    "ms-MY": (",", "."),
    "vi-VN": (".", ","),
}

# ── Date formats per culture ─────────────────────────────────────

_DATE_FORMAT = {
    "en-US": "M/d/yyyy",
    "en-GB": "dd/MM/yyyy",
    "fr-FR": "dd/MM/yyyy",
    "de-DE": "dd.MM.yyyy",
    "es-ES": "dd/MM/yyyy",
    "it-IT": "dd/MM/yyyy",
    "pt-BR": "dd/MM/yyyy",
    "pt-PT": "dd/MM/yyyy",
    "ja-JP": "yyyy/MM/dd",
    "zh-CN": "yyyy/M/d",
    "zh-TW": "yyyy/M/d",
    "ko-KR": "yyyy-MM-dd",
    "ar-SA": "dd/MM/yyyy",
    "he-IL": "dd/MM/yyyy",
    "ru-RU": "dd.MM.yyyy",
    "nl-NL": "d-M-yyyy",
    "sv-SE": "yyyy-MM-dd",
    "da-DK": "dd-MM-yyyy",
    "nb-NO": "dd.MM.yyyy",
    "fi-FI": "d.M.yyyy",
    "pl-PL": "dd.MM.yyyy",
    "tr-TR": "d.MM.yyyy",
    "th-TH": "d/M/yyyy",
    "hi-IN": "dd-MM-yyyy",
    "cs-CZ": "dd.MM.yyyy",
    "hu-HU": "yyyy.MM.dd.",
    "ro-RO": "dd.MM.yyyy",
    "uk-UA": "dd.MM.yyyy",
    "el-GR": "d/M/yyyy",
    "id-ID": "dd/MM/yyyy",
    "ms-MY": "d/MM/yyyy",
    "vi-VN": "dd/MM/yyyy",
}


# ── Public API ───────────────────────────────────────────────────

def parse_cultures(cultures_str):
    """Parse a comma-separated culture string into a validated list.

    Args:
        cultures_str: e.g. "en-US,fr-FR,de-DE" or None.

    Returns:
        list[str]: Validated culture codes, or ["en-US"] if empty/None.
    """
    if not cultures_str:
        return ["en-US"]
    parts = [c.strip() for c in cultures_str.split(",") if c.strip()]
    validated = []
    for c in parts:
        if c in _SUPPORTED_CULTURES:
            validated.append(c)
        else:
            # Try to match by language prefix (e.g. "fr" → "fr-FR")
            prefix = c.split("-")[0].lower()
            match = next((s for s in _SUPPORTED_CULTURES if s.lower().startswith(prefix + "-")), None)
            if match:
                logger.warning("Culture '%s' not exact — using '%s'", c, match)
                validated.append(match)
            else:
                logger.warning("Unsupported culture '%s' — skipping", c)
    return validated if validated else ["en-US"]


def get_primary_culture(cultures):
    """Return the first (primary) culture from a list."""
    if cultures and len(cultures) > 0:
        return cultures[0]
    return "en-US"


def get_currency_format(culture):
    """Return a TMDL-compatible currency format string for the culture."""
    symbol = _CURRENCY_SYMBOL.get(culture, "$")
    return f"{symbol}#,##0.00"


def get_number_format(culture):
    """Return a TMDL-compatible number format string for the culture.

    Note: TMDL format strings use Excel-style patterns (# and 0).
    The runtime locale handles the actual separator rendering.
    The format string itself stays in US-style #,##0.00 because
    Power BI resolves separators at render time based on the model culture.
    """
    return "#,##0.00"


def get_date_format(culture):
    """Return the date format pattern for a culture."""
    return _DATE_FORMAT.get(culture, "yyyy-MM-dd")


def convert_format_string_for_culture(mstr_format, culture):
    """Convert an MSTR format string to TMDL formatString for a culture.

    Args:
        mstr_format: e.g. "currency", "fixed", "date", "percent", or raw pattern.
        culture: Target culture code.

    Returns:
        str: TMDL format string.
    """
    if not mstr_format:
        return ""
    low = mstr_format.lower().strip()
    if low == "currency":
        return get_currency_format(culture)
    if low == "fixed":
        return "#,##0.00"
    if low == "percent":
        return "0.00%"
    if low == "scientific":
        return "0.00E+00"
    if low == "general":
        return ""
    if low == "date":
        return get_date_format(culture)
    if low == "time":
        return "HH:mm:ss"
    if low == "datetime":
        return f"{get_date_format(culture)} HH:mm:ss"
    # Already an Excel-style pattern
    if any(c in mstr_format for c in ("#", "0", "%")):
        return mstr_format
    return mstr_format


def generate_culture_tmdl(cultures):
    """Generate TMDL culture/translation sections for additional cultures.

    The primary culture is set in model.tmdl via ``culture: <primary>``.
    This function generates ``cultures.tmdl`` with ``linguisticMetadata``
    entries for each additional culture.

    Args:
        cultures: list of culture codes (first is primary, rest are translations).

    Returns:
        str: TMDL content for cultures.tmdl, or "" if only one culture.
    """
    if not cultures or len(cultures) <= 1:
        return ""

    lines = []
    for culture in cultures[1:]:
        lines.append(f"culture {culture}")
        lines.append(f"\tlinguisticMetadata =")
        lines.append(f'\t\t{{"Version":"1.0.0","Language":"{culture.split("-")[0]}"}}')
        lines.append("")
    return "\n".join(lines) + "\n"


def generate_translations_tmdl(cultures, tables, measures):
    """Generate translated caption sections for additional cultures.

    In TMDL, translations appear inside a ``culture`` block as
    ``translatedCaption: <name>`` for each table, column, and measure.

    Args:
        cultures: list of culture codes (first is primary).
        tables: list of table dicts from datasources.
        measures: list of metric dicts.

    Returns:
        str: TMDL translation content, or "" if single culture.
    """
    if not cultures or len(cultures) <= 1:
        return ""

    lines = []
    for culture in cultures[1:]:
        lines.append(f"culture {culture}")
        lines.append(f"\tlinguisticMetadata =")
        lines.append(f'\t\t{{"Version":"1.0.0","Language":"{culture.split("-")[0]}"}}')
        lines.append("")

        # Table translations (placeholder — same as source names by default)
        # In a real deployment, these would come from MSTR's translated object names
        for table in tables:
            table_name = table.get("name", "")
            if table_name:
                lines.append(f"\ttranslation {table_name}")
                lines.append(f"\t\ttranslatedCaption: {table_name}")
                # Column translations
                for col in table.get("columns", []):
                    col_name = col.get("name", "")
                    if col_name:
                        lines.append(f"\t\ttranslation {col_name}")
                        lines.append(f"\t\t\ttranslatedCaption: {col_name}")
                lines.append("")

        # Measure translations
        for metric in measures:
            m_name = metric.get("name", "")
            if m_name:
                lines.append(f"\ttranslation {m_name}")
                lines.append(f"\t\ttranslatedCaption: {m_name}")
        lines.append("")

    return "\n".join(lines) + "\n"


def extract_cultures_from_data(data):
    """Extract culture hints from intermediate JSON data.

    Looks for locale information in datasources, dossiers, and reports.

    Args:
        data: dict with intermediate JSON keys.

    Returns:
        list[str]: Detected culture codes, or ["en-US"] default.
    """
    cultures = set()

    # Check datasource connection properties for locale hints
    for ds in data.get("datasources", []):
        conn = ds.get("db_connection", {})
        locale = conn.get("locale", "")
        if locale:
            cultures.add(locale)

    # Check dossier language settings
    for doss in data.get("dossiers", []):
        lang = doss.get("language", "")
        if lang:
            cultures.add(lang)

    # Check report language settings
    for rpt in data.get("reports", []):
        lang = rpt.get("language", "")
        if lang:
            cultures.add(lang)

    if cultures:
        return sorted(cultures)
    return ["en-US"]
