"""
Security validator.

Validates all file paths before write operations to prevent:
  • Path traversal attacks (ZIP slip)
  • Directory escape (writing outside designated output dir)
  • XXE protection hints for any XML inputs
  • Sensitive file name patterns
"""

import logging
import os
import re

logger = logging.getLogger(__name__)

# Patterns that should never appear in generated paths
_TRAVERSAL_PATTERNS = [
    "..",
    "~",
]

# Absolute path indicators (cross-platform)
_ABSOLUTE_INDICATORS_RE = re.compile(
    r"^(?:[A-Za-z]:[/\\]|[/\\]{2}|/)",
)

# Dangerous file extensions that should not be written
_DANGEROUS_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".ps1", ".sh", ".dll", ".so",
    ".msi", ".vbs", ".wsf", ".scr", ".com", ".pif",
}

# XML external entity patterns
_XXE_PATTERNS = [
    re.compile(r"<!ENTITY\s", re.IGNORECASE),
    re.compile(r"<!DOCTYPE\s.*\[", re.IGNORECASE | re.DOTALL),
    re.compile(r"SYSTEM\s+[\"']", re.IGNORECASE),
    re.compile(r"PUBLIC\s+[\"']", re.IGNORECASE),
]

# Sensitive file name patterns
_SENSITIVE_PATTERNS = [
    re.compile(r"\.env$", re.IGNORECASE),
    re.compile(r"\.key$", re.IGNORECASE),
    re.compile(r"\.pem$", re.IGNORECASE),
    re.compile(r"\.p12$", re.IGNORECASE),
    re.compile(r"id_rsa", re.IGNORECASE),
    re.compile(r"\.secret", re.IGNORECASE),
]


# ── Public API ───────────────────────────────────────────────────

def validate_path(path, allowed_root):
    """Validate that *path* is safe to write under *allowed_root*.

    Args:
        path: The file path to validate (may be relative or absolute).
        allowed_root: The directory that all writes must stay within.

    Returns:
        dict with ``valid`` (bool), ``errors`` (list[str]),
        ``warnings`` (list[str]).
    """
    errors = []
    warnings = []

    # Normalise
    norm_root = os.path.normpath(os.path.abspath(allowed_root))
    # If path is relative, resolve it against the root
    if not os.path.isabs(path):
        resolved = os.path.normpath(os.path.join(norm_root, path))
    else:
        resolved = os.path.normpath(os.path.abspath(path))

    # Check 1: path traversal
    for pattern in _TRAVERSAL_PATTERNS:
        if pattern in path:
            errors.append(
                f"Path traversal detected: '{pattern}' in '{path}'"
            )

    # Check 2: resolved path within allowed root
    if not resolved.startswith(norm_root + os.sep) and resolved != norm_root:
        errors.append(
            f"Directory escape: '{resolved}' is outside allowed root '{norm_root}'"
        )

    # Check 3: dangerous extensions
    _, ext = os.path.splitext(path)
    if ext.lower() in _DANGEROUS_EXTENSIONS:
        errors.append(f"Dangerous file extension: '{ext}' in '{path}'")

    # Check 4: sensitive file patterns
    basename = os.path.basename(path)
    for pat in _SENSITIVE_PATTERNS:
        if pat.search(basename):
            warnings.append(f"Sensitive file pattern: '{basename}'")
            break

    return {
        "valid": len(errors) == 0,
        "resolved_path": resolved,
        "errors": errors,
        "warnings": warnings,
    }


def validate_paths(paths, allowed_root):
    """Validate multiple paths.

    Returns:
        dict with ``valid`` (bool — True only if ALL valid),
        ``results`` (list of per-path results), ``summary``.
    """
    results = []
    all_errors = []
    all_warnings = []

    for p in paths:
        r = validate_path(p, allowed_root)
        results.append({"path": p, **r})
        all_errors.extend(r["errors"])
        all_warnings.extend(r["warnings"])

    return {
        "valid": len(all_errors) == 0,
        "results": results,
        "summary": {
            "total_paths": len(paths),
            "valid": sum(1 for r in results if r["valid"]),
            "invalid": sum(1 for r in results if not r["valid"]),
            "errors": len(all_errors),
            "warnings": len(all_warnings),
        },
    }


def check_xxe(content):
    """Check if XML/text content contains XXE patterns.

    Args:
        content: String content to check.

    Returns:
        dict with ``safe`` (bool) and ``findings`` (list[str]).
    """
    findings = []
    for pat in _XXE_PATTERNS:
        if pat.search(content):
            findings.append(f"XXE pattern detected: {pat.pattern}")
    return {
        "safe": len(findings) == 0,
        "findings": findings,
    }


def validate_zip_entry(entry_name, extract_dir):
    """Validate a ZIP entry name before extraction (ZIP slip prevention).

    Args:
        entry_name: The file name from the ZIP archive.
        extract_dir: The target extraction directory.

    Returns:
        dict with ``safe`` (bool) and ``error`` (str or None).
    """
    norm_dir = os.path.normpath(os.path.abspath(extract_dir))
    target = os.path.normpath(os.path.join(norm_dir, entry_name))

    if not target.startswith(norm_dir + os.sep) and target != norm_dir:
        return {
            "safe": False,
            "target": target,
            "error": f"ZIP slip: '{entry_name}' would extract to '{target}' outside '{norm_dir}'",
        }
    return {"safe": True, "target": target, "error": None}


def validate_project_output(output_dir):
    """Scan an output directory for security issues.

    Returns:
        dict with ``valid``, ``errors``, ``warnings``.
    """
    errors = []
    warnings = []

    if not os.path.isdir(output_dir):
        return {"valid": True, "errors": [], "warnings": []}

    for dirpath, _dirs, filenames in os.walk(output_dir):
        for fname in filenames:
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, output_dir)

            # Check traversal in relative path
            if ".." in rel:
                errors.append(f"Traversal in output: {rel}")

            # Check dangerous extension
            _, ext = os.path.splitext(fname)
            if ext.lower() in _DANGEROUS_EXTENSIONS:
                errors.append(f"Dangerous file in output: {rel}")

            # Check sensitive files
            for pat in _SENSITIVE_PATTERNS:
                if pat.search(fname):
                    warnings.append(f"Sensitive file in output: {rel}")
                    break

            # Check for XXE in JSON/XML files
            if ext.lower() in {".xml", ".svg"}:
                try:
                    with open(full, "r", encoding="utf-8") as f:
                        content = f.read(4096)
                    xxe = check_xxe(content)
                    if not xxe["safe"]:
                        errors.extend(
                            f"{rel}: {finding}"
                            for finding in xxe["findings"]
                        )
                except (OSError, UnicodeDecodeError):
                    pass

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }
