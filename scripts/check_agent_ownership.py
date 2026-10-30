"""Check explicit agent ownership, adapted from TableauToPowerBI's ownership guard.

Only backticked Python paths in ``## Owned Files`` count as primary claims.
References in handoffs, constraints, or other sections do not claim ownership.
Run from any directory; missing owners, overlapping claims, and stale paths fail.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_MODULE_DIRS = ("microstrategy_export", "powerbi_import", "universal_bi")
_ENTRY_POINTS = ("migrate.py", "wizard.py")


def analyse(repo_root: Path = _ROOT) -> dict:
    """Return qualified module ownership and actionable errors."""
    root = Path(repo_root)
    modules = set()
    errors = []
    for directory in _MODULE_DIRS:
        base = root / directory
        if not base.is_dir():
            errors.append(f"Missing module directory: {directory}")
        modules.update(path.relative_to(root).as_posix() for path in base.rglob("*.py") if path.name != "__init__.py")
    for name in _ENTRY_POINTS:
        if not (root / name).is_file():
            errors.append(f"Missing entry point: {name}")
        else:
            modules.add(name)

    agents = sorted((root / ".github" / "agents").glob("*.agent.md"))
    if not agents:
        errors.append("No agent definitions found")
    owners: dict[str, list[str]] = {}
    for agent in agents:
        in_owned_files = False
        claimed = set()
        for line in agent.read_text(encoding="utf-8").splitlines():
            if line.startswith("#"):
                in_owned_files = line.strip().lower() == "## owned files"
                continue
            if not in_owned_files:
                continue
            for token in re.findall(r"`([^`]+)`", line):
                pattern = token.replace("\\", "/")
                if not pattern.endswith(".py"):
                    continue
                if pattern.startswith("/") or ".." in pattern.split("/") or ":" in pattern:
                    errors.append(f"{agent.name}: ownership path must be repo-relative: {token}")
                    continue
                matches = {path.relative_to(root).as_posix() for path in root.glob(pattern) if path.is_file()}
                if not matches:
                    errors.append(f"{agent.name}: ownership path matches no files: {token}")
                claimed.update(matches & modules)
        for module in sorted(claimed):
            owners.setdefault(module, []).append(agent.name)

    unowned = sorted(modules - owners.keys())
    conflicts = {module: names for module, names in sorted(owners.items()) if len(names) > 1}
    errors.extend(f"No primary owner: {module}" for module in unowned)
    errors.extend(f"Multiple primary owners: {module}: {', '.join(names)}" for module, names in conflicts.items())
    return {
        "ok": not errors,
        "modules": len(modules),
        "agents": len(agents),
        "owners": dict(sorted(owners.items())),
        "unowned": unowned,
        "conflicts": conflicts,
        "errors": errors,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit a machine-readable report")
    args = parser.parse_args(argv)
    result = analyse()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        status = "OK" if result["ok"] else "FAIL"
        print(f"{status}: {result['modules']} modules, {result['agents']} agents")
        for error in result["errors"]:
            print(f"  - {error}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
