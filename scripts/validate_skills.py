"""Validate repo migration skills, adapted from TableauToPowerBI's skill guard.

Check required scalar/folded frontmatter fields, skill names, relative links,
and options in migrate.py command examples without importing the migration CLI.
This intentionally checks the supported frontmatter subset, not arbitrary YAML.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

_ROOT = Path(__file__).resolve().parents[1]
_FLAG_RE = re.compile(r"(?<![\w-])--[a-z][a-z0-9-]*")
_LINK_RE = re.compile(r"\[[^\]]+\]\((<[^>]+>|[^)\s]+)(?:\s+\"[^\"]*\")?\)")


def _frontmatter_field(frontmatter: str, field: str) -> str:
    lines = frontmatter.splitlines()
    matches = [index for index, line in enumerate(lines) if re.match(rf"^{field}\s*:", line)]
    if len(matches) != 1:
        return ""
    index = matches[0]
    value = lines[index].split(":", 1)[1].strip()
    if value in (">", ">-", "|", "|-"):
        parts = []
        for line in lines[index + 1 :]:
            if line and not line.startswith(" "):
                break
            parts.append(line.strip())
        return " ".join(parts).strip()
    if value.startswith(("'", '"')):
        return value[1:-1].strip() if len(value) >= 2 and value[-1] == value[0] else ""
    if (
        ": " in value
        or value.startswith(("#", "[", "{"))
        or value.lower() in ("null", "~", "true", "false")
        or value.isdecimal()
    ):
        return ""
    return value


def declared_flags(cli_path: Path) -> set[str]:
    """Read literal argparse option strings, including short/long aliases."""
    tree = ast.parse(Path(cli_path).read_text(encoding="utf-8"))
    flags = {"--help"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument":
            flags.update(
                argument.value
                for argument in node.args
                if isinstance(argument, ast.Constant)
                and isinstance(argument.value, str)
                and argument.value.startswith("--")
            )
    return flags


def validate_skill(path: Path, known_flags: set[str]) -> list[str]:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    errors = []
    lines = text.splitlines()
    end = next((index for index, line in enumerate(lines[1:], 1) if line == "---"), None)
    if not lines or lines[0] != "---" or end is None:
        errors.append(f"{path}: missing YAML frontmatter")
        body = text
    else:
        frontmatter = "\n".join(lines[1:end])
        for field in ("name", "description"):
            if not _frontmatter_field(frontmatter, field):
                errors.append(f"{path}: missing or invalid '{field}' scalar")
        name = _frontmatter_field(frontmatter, "name")
        if name and name != path.parent.name:
            errors.append(f"{path}: skill name '{name}' does not match directory '{path.parent.name}'")
        if "\t" in frontmatter:
            errors.append(f"{path}: tabs are not supported in frontmatter")
        body = "\n".join(lines[end + 1 :])

    for match in _LINK_RE.finditer(text):
        target = match.group(1).strip("<>")
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        resolved = path.parent / unquote(parsed.path)
        if not resolved.exists():
            errors.append(f"{path}: broken relative link: {target}")

    continuation = False
    for line in body.splitlines():
        command = line.split("migrate.py", 1)[1] if "migrate.py" in line else line
        if "migrate.py" in line or continuation:
            for flag in _FLAG_RE.findall(command):
                if flag not in known_flags:
                    errors.append(f"{path}: unknown migrate.py flag '{flag}'")
            continuation = bool(re.search(r"(?:\\|\s`)$", line.rstrip()))
        else:
            continuation = False
    return errors


def validate_skills(repo_root: Path = _ROOT) -> dict:
    root = Path(repo_root)
    files = sorted((root / ".github" / "skills").rglob("SKILL.md"))
    errors = []
    if not files:
        errors.append("No repository skills found")
    flags = declared_flags(root / "migrate.py")
    for path in files:
        errors.extend(validate_skill(path, flags))
    return {"ok": not errors, "files": len(files), "errors": errors}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit a machine-readable report")
    args = parser.parse_args(argv)
    result = validate_skills()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        status = "OK" if result["ok"] else "FAIL"
        print(f"{status}: {result['files']} skill file(s)")
        for error in result["errors"]:
            print(f"  - {error}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
