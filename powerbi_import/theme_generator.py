"""
Theme generator — convert MicroStrategy color palettes, fonts, and
formatting to Power BI reportTheme.json.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

# MicroStrategy default colour palettes → PBI theme palette
_DEFAULT_PALETTE = [
    "#1F77B4", "#FF7F0E", "#2CA02C", "#D62728", "#9467BD",
    "#8C564B", "#E377C2", "#7F7F7F", "#BCBD22", "#17BECF",
]

_MSTR_FONT_MAP = {
    "Arial": "Arial",
    "Helvetica": "Segoe UI",
    "Times New Roman": "Times New Roman",
    "Courier": "Courier New",
    "Verdana": "Verdana",
    "Tahoma": "Tahoma",
    "Georgia": "Georgia",
}


def generate_theme(dossier_data, output_path):
    """Generate a Power BI reportTheme.json from dossier formatting data.

    Args:
        dossier_data: dict with optional keys:
            - palette: list of hex color strings
            - font_family: default font name
            - background_color: hex color for page background
            - title_color: hex color for titles
            - text_color: hex color for body text
        output_path: Where to write the theme JSON file.

    Returns:
        Path to the generated theme file.
    """
    palette = dossier_data.get("palette") or _DEFAULT_PALETTE
    font = _map_font(dossier_data.get("font_family", "Segoe UI"))
    bg_color = dossier_data.get("background_color", "#FFFFFF")
    title_color = dossier_data.get("title_color", "#333333")
    text_color = dossier_data.get("text_color", "#666666")

    theme = {
        "name": "MicroStrategy Migration Theme",
        "dataColors": palette[:10],
        "background": bg_color,
        "foreground": text_color,
        "tableAccent": palette[0] if palette else "#1F77B4",
        "textClasses": {
            "callout": {"fontSize": 28, "fontFace": font, "color": title_color},
            "title": {"fontSize": 14, "fontFace": font, "color": title_color},
            "header": {"fontSize": 12, "fontFace": font, "color": title_color},
            "label": {"fontSize": 10, "fontFace": font, "color": text_color},
        },
        "visualStyles": {
            "*": {
                "*": {
                    "*": [{
                        "fontFamily": font,
                        "fontSize": {"expr": {"Literal": {"Value": "10D"}}},
                        "wordWrap": True,
                    }]
                }
            }
        },
    }

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(theme, f, indent=2, ensure_ascii=False)

    logger.info("Theme generated at %s", output_path)
    return output_path


def extract_theme_from_dossier(dossier):
    """Extract theme-relevant formatting from a dossier definition.

    Args:
        dossier: A single dossier dict from dossier_extractor.

    Returns:
        dict with palette, font_family, background_color, etc.
    """
    theme_data = {}

    # Extract palette from formatting
    formatting = dossier.get("formatting", {})
    if formatting.get("palette"):
        theme_data["palette"] = formatting["palette"]

    # Extract from graph styles
    if formatting.get("colors"):
        theme_data["palette"] = formatting["colors"]

    # Font family
    font = formatting.get("font_family") or formatting.get("fontFamily")
    if font:
        theme_data["font_family"] = font

    # Background
    bg = formatting.get("background_color") or formatting.get("backgroundColor")
    if bg:
        theme_data["background_color"] = bg

    # Title formatting
    title_fmt = formatting.get("title", {})
    if title_fmt.get("color"):
        theme_data["title_color"] = title_fmt["color"]

    return theme_data


def _map_font(font_name):
    """Map a MicroStrategy font name to a Power BI compatible font."""
    return _MSTR_FONT_MAP.get(font_name, font_name)
