"""
Interactive wizard for guided MicroStrategy to Power BI migration.

Prompts the user step-by-step through connection, object selection,
output options, and optionally saves the answers to a config JSON file.
"""

import json
import os
import sys
import getpass
import logging

logger = logging.getLogger(__name__)


def run_wizard():
    """Run the interactive migration wizard.

    Returns:
        argparse.Namespace-compatible dict with all migration parameters.
    """
    print()
    print("=" * 60)
    print("  MicroStrategy → Power BI Migration Wizard")
    print("=" * 60)
    print()

    answers = {}

    # ── Step 1: Mode ─────────────────────────────────────────
    print("[1/7] Migration Mode")
    print("  1) Online  — connect to MicroStrategy REST API")
    print("  2) Offline — load from exported JSON files")
    mode = _ask_choice("  Select mode", ["1", "2"], default="1")

    if mode == "2":
        export_dir = _ask("  Path to exported JSON directory", required=True)
        answers["from_export"] = export_dir
    else:
        answers["from_export"] = None
        # ── Connection details ───────────────────────────────
        print()
        print("[2/7] MicroStrategy Connection")
        answers["server"] = _ask("  Server URL (e.g. https://mstr.company.com/MicroStrategyLibrary)", required=True)
        answers["username"] = _ask("  Username", required=True)
        answers["password"] = _ask_password("  Password")
        answers["project"] = _ask("  Project name", required=True)
        answers["auth_mode"] = _ask_choice(
            "  Auth mode",
            ["standard", "ldap", "saml", "oauth"],
            default="standard",
        )

    # ── Step 3: Object Selection ─────────────────────────────
    print()
    print("[3/7] Object Selection")
    print("  1) Single report   (by name)")
    print("  2) Single report   (by ID)")
    print("  3) Single dossier  (by name)")
    print("  4) Single dossier  (by ID)")
    print("  5) Batch — all reports & dossiers")
    print("  6) Assessment only (no output)")
    sel = _ask_choice("  Select", ["1", "2", "3", "4", "5", "6"], default="5")

    answers["report"] = None
    answers["report_id"] = None
    answers["dossier"] = None
    answers["dossier_id"] = None
    answers["batch"] = False
    answers["assess"] = False

    if sel == "1":
        answers["report"] = _ask("  Report name", required=True)
    elif sel == "2":
        answers["report_id"] = _ask("  Report ID", required=True)
    elif sel == "3":
        answers["dossier"] = _ask("  Dossier name", required=True)
    elif sel == "4":
        answers["dossier_id"] = _ask("  Dossier ID", required=True)
    elif sel == "5":
        answers["batch"] = True
    elif sel == "6":
        answers["assess"] = True

    # ── Step 4: Output ───────────────────────────────────────
    print()
    print("[4/7] Output")
    answers["output_dir"] = _ask("  Output directory", default="artifacts/")
    answers["report_name"] = _ask("  Override report name (leave blank to auto-detect)", default="")
    answers["culture"] = _ask("  Culture/locale (e.g. en-US, fr-FR)", default="")
    answers["shared_model"] = _ask_bool("  Generate shared semantic model?", default=False)

    # ── Step 5: Deployment ───────────────────────────────────
    print()
    print("[5/7] Deployment")
    deploy = _ask_bool("  Deploy after generation?", default=False)
    answers["deploy"] = None
    answers["fabric"] = False
    answers["tenant_id"] = None
    answers["client_id"] = None
    answers["client_secret"] = None
    answers["deploy_refresh"] = False
    answers["lakehouse_id"] = None
    answers["direct_lake"] = False

    if deploy:
        answers["deploy"] = _ask("  Workspace ID", required=True)
        answers["fabric"] = _ask_bool("  Deploy to Fabric (instead of PBI Service)?", default=False)
        answers["tenant_id"] = _ask("  Azure tenant ID", default="")
        answers["client_id"] = _ask("  Azure app client ID", default="")
        answers["client_secret"] = _ask_password("  Azure app client secret") if answers["client_id"] else ""
        answers["deploy_refresh"] = _ask_bool("  Trigger dataset refresh?", default=False)
        if answers["fabric"]:
            answers["lakehouse_id"] = _ask("  Lakehouse ID (for DirectLake)", default="")
            answers["direct_lake"] = bool(answers["lakehouse_id"])

    # ── Step 6: Logging ──────────────────────────────────────
    print()
    print("[6/7] Logging")
    answers["verbose"] = _ask_bool("  Verbose logging?", default=False)
    answers["quiet"] = False
    answers["log_file"] = _ask("  Log file path (leave blank for none)", default="")

    # ── Step 7: Save config ──────────────────────────────────
    print()
    print("[7/7] Save Configuration")
    save = _ask_bool("  Save settings to a config file for reuse?", default=True)
    if save:
        config_path = _ask("  Config file path", default="migration_config.json")
        _save_config(answers, config_path)
        print(f"  ✓ Config saved to {config_path}")
        print(f"    Re-run with: python migrate.py --config {config_path}")

    # Convert empty strings to None
    for k, v in answers.items():
        if v == "":
            answers[k] = None

    return answers


# ── Helpers ──────────────────────────────────────────────────────


def _ask(prompt, default=None, required=False):
    """Prompt user for text input."""
    suffix = f" [{default}]" if default else ""
    while True:
        val = input(f"{prompt}{suffix}: ").strip()
        if not val and default is not None:
            return default
        if not val and required:
            print("    (required — please enter a value)")
            continue
        return val


def _ask_password(prompt):
    """Prompt for a password (hidden input)."""
    try:
        return getpass.getpass(f"{prompt}: ")
    except (EOFError, KeyboardInterrupt):
        return ""


def _ask_choice(prompt, choices, default=None):
    """Prompt user to pick from a list of choices."""
    suffix = f" [{default}]" if default else ""
    while True:
        val = input(f"{prompt} ({'/'.join(choices)}){suffix}: ").strip()
        if not val and default:
            return default
        if val in choices:
            return val
        print(f"    (invalid — choose one of: {', '.join(choices)})")


def _ask_bool(prompt, default=False):
    """Prompt user for yes/no."""
    hint = "Y/n" if default else "y/N"
    val = input(f"{prompt} [{hint}]: ").strip().lower()
    if not val:
        return default
    return val in ("y", "yes", "1", "true")


def _save_config(answers, path):
    """Save wizard answers to a JSON config file (excluding password/secret)."""
    safe = {}
    # Map wizard answers to config format
    if answers.get("server"):
        safe["server"] = answers["server"]
    if answers.get("username"):
        safe["username"] = answers["username"]
    if answers.get("project"):
        safe["project"] = answers["project"]
    if answers.get("auth_mode"):
        safe["auth_mode"] = answers["auth_mode"]
    if answers.get("from_export"):
        safe["from_export"] = answers["from_export"]
    if answers.get("output_dir"):
        safe["output_dir"] = answers["output_dir"]
    if answers.get("report_name"):
        safe["report_name"] = answers["report_name"]
    if answers.get("culture"):
        safe["culture"] = answers["culture"]
    if answers.get("batch"):
        safe["batch"] = True
    if answers.get("deploy"):
        safe["deployment"] = {
            "workspace_id": answers["deploy"],
            "fabric": answers.get("fabric", False),
            "tenant_id": answers.get("tenant_id", ""),
            "client_id": answers.get("client_id", ""),
        }

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(safe, f, indent=2, ensure_ascii=False)
