"""Regression coverage for the Tableau-derived developer tooling."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import check_agent_ownership
from scripts import validate_skills as skill_checks
from scripts.check_agent_ownership import analyse
from scripts.validate_skills import declared_flags, validate_skill, validate_skills

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def tooling_repo(tmp_path):
    for directory in ("microstrategy_export", "powerbi_import", "universal_bi", ".github/agents"):
        (tmp_path / directory).mkdir(parents=True)
    for module in ("microstrategy_export/client.py", "powerbi_import/client.py", "migrate.py", "wizard.py"):
        (tmp_path / module).write_text("", encoding="utf-8")
    return tmp_path


def _agent(root, name, owned):
    path = root / ".github" / "agents" / f"{name}.agent.md"
    path.write_text(f"# {name}\n\n## Owned Files\n{owned}\n\n## Constraints\n", encoding="utf-8")
    return path


def _skill(root, body="", frontmatter=None):
    path = root / ".github" / "skills" / "migration" / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if frontmatter is None:
        frontmatter = 'name: migration\ndescription: "Use when migrating reports."'
    path.write_text(f"---\n{frontmatter}\n---\n{body}", encoding="utf-8")
    return path


def test_repository_ownership_is_complete():
    result = analyse(ROOT)
    assert result["ok"], result["errors"]
    assert result["modules"] > 80


def test_qualified_paths_do_not_conflate_same_basename(tooling_repo):
    _agent(tooling_repo, "source", "- `microstrategy_export/client.py`\n- `migrate.py`\n- `wizard.py`")
    _agent(tooling_repo, "target", "- `powerbi_import/client.py`")
    (tooling_repo / "powerbi_import" / "__init__.py").write_text("", encoding="utf-8")
    result = analyse(tooling_repo)
    assert result["ok"], result["errors"]
    assert len(result["owners"]) == 4


def test_overlapping_globs_fail_and_duplicate_claims_do_not(tooling_repo):
    _agent(tooling_repo, "first", "- `powerbi_import/*.py`\n- `powerbi_import/client.py`")
    _agent(tooling_repo, "second", "- `powerbi_import/client.py`")
    result = analyse(tooling_repo)
    assert not result["ok"]
    assert result["conflicts"] == {"powerbi_import/client.py": ["first.agent.md", "second.agent.md"]}


def test_handoffs_and_constraints_do_not_claim_files(tooling_repo):
    path = _agent(tooling_repo, "ref", "- No runtime files.")
    with path.open("a", encoding="utf-8") as handle:
        handle.write("Refer to `powerbi_import/client.py`.\n## Handoffs\n- `microstrategy_export/client.py`\n")
    result = analyse(tooling_repo)
    assert result["owners"] == {}
    assert len(result["unowned"]) == 4


def test_stale_and_outside_ownership_paths_fail(tooling_repo):
    _agent(tooling_repo, "bad", "- `powerbi_import/missing.py`\n- `../outside.py`\n- `C:/outside.py`")
    result = analyse(tooling_repo)
    assert any("matches no files" in error for error in result["errors"])
    assert sum("repo-relative" in error for error in result["errors"]) == 2


def test_missing_inventory_and_agents_fail(tmp_path):
    result = analyse(tmp_path)
    assert not result["ok"]
    assert "No agent definitions found" in result["errors"]
    assert "Missing entry point: migrate.py" in result["errors"]


def test_repository_skill_is_valid():
    result = validate_skills(ROOT)
    assert result["ok"], result["errors"]


def test_cli_flags_use_only_argparse_declarations(tmp_path):
    path = tmp_path / "migrate.py"
    path.write_text(
        "parser.add_argument('-o', '--output-dir')\n"
        "group.add_argument('--assess', action='store_true')\n"
        "unrelated = '--not-a-flag'\n",
        encoding="utf-8",
    )
    assert declared_flags(path) == {"--help", "--output-dir", "--assess"}


@pytest.mark.parametrize("style", [">", ">-", "|", "|-"])
def test_folded_skill_description(tmp_path, style):
    path = _skill(tmp_path, frontmatter=f"name: migration\ndescription: {style}\n  Use when migrating\n  reports.")
    assert validate_skill(path, {"--help"}) == []


@pytest.mark.parametrize(
    "frontmatter",
    [
        "name: migration",
        "name: migration\ndescription: ''",
        'name: migration\ndescription: "unterminated',
        "name: migration\ndescription: Use when: migrating",
        "name: migration\nname: duplicate\ndescription: migration",
        "name: different\ndescription: migration",
        "name: migration\ndescription: >-\n\tUse when migrating",
        "name: migration\ndescription: null",
        "name: migration\ndescription: false",
        "name: migration\ndescription: 123",
    ],
)
def test_invalid_frontmatter_fails(tmp_path, frontmatter):
    assert validate_skill(_skill(tmp_path, frontmatter=frontmatter), {"--help"})


def test_missing_frontmatter_fails(tmp_path):
    path = _skill(tmp_path)
    path.write_text("# Migration\n", encoding="utf-8")
    assert "missing YAML frontmatter" in validate_skill(path, {"--help"})[0]


def test_relative_links_support_encoded_spaces_fragments_and_urls(tmp_path):
    (tmp_path / "guide with spaces.md").write_text("# Guide", encoding="utf-8")
    path = _skill(
        tmp_path,
        "[Guide](../../../guide%20with%20spaces.md#guide)\n"
        "[Angle](<../../../guide with spaces.md>)\n"
        "[Web](https://example.com/guide)\n[Section](#workflow)",
    )
    assert validate_skill(path, {"--help"}) == []
    path.write_text(path.read_text(encoding="utf-8") + "\n[Missing](missing.md)", encoding="utf-8")
    assert "broken relative link" in validate_skill(path, {"--help"})[0]


@pytest.mark.parametrize("continuation", ["\\", "`"])
def test_multiline_cli_examples_and_non_migration_commands(tmp_path, continuation):
    path = _skill(
        tmp_path,
        f"python migrate.py --assess {continuation}\n    --from-export fixtures {continuation}\n    --invented\n"
        "python -m pytest tests/ --tb=short -q\n"
        "python migrate.py --help\n",
    )
    errors = validate_skill(path, {"--help", "--assess", "--from-export"})
    assert len(errors) == 1
    assert "unknown migrate.py flag '--invented'" in errors[0]


def test_inline_command_does_not_consume_following_prose(tmp_path):
    path = _skill(tmp_path, "`python migrate.py --help`\nUse pytest's --tb=short for test output.\n")
    assert validate_skill(path, {"--help"}) == []


def test_no_skills_is_a_failure(tooling_repo):
    result = validate_skills(tooling_repo)
    assert not result["ok"]
    assert result["errors"] == ["No repository skills found"]


@pytest.mark.parametrize(
    ("module", "check"),
    [(check_agent_ownership, "analyse"), (skill_checks, "validate_skills")],
)
def test_tool_main_fails_with_json_errors(tooling_repo, monkeypatch, capsys, module, check):
    validate = getattr(module, check)
    monkeypatch.setattr(module, check, lambda: validate(tooling_repo))
    assert module.main(["--json"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert not result["ok"]
    assert result["errors"]


@pytest.mark.parametrize("script", ["check_agent_ownership.py", "validate_skills.py"])
def test_tool_cli_runs_outside_repo_and_emits_json(tmp_path, script):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), "--json"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["ok"], report["errors"]
