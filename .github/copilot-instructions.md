# MicroStrategy to Power BI / Fabric

This repository extracts MicroStrategy metadata through REST or offline JSON
exports and generates Power BI projects (TMDL semantic models, PBIR reports and
Power Query M), with optional Fabric artifact generation and deployment.

## Start Here

Read [shared project rules](agents/shared.instructions.md) before work and the
relevant owner in [agent topology](../docs/AGENTS.md). Use the
[migration skill](skills/microstrategy-to-powerbi/SKILL.md) for migration workflows.
Those links are explicit: do not assume nested instruction files auto-load.

- Extraction/expression conversion: `microstrategy_export/`.
- Generation/assessment/evidence/deployment: `powerbi_import/`.
- Normalized federation/adapters: `universal_bi/`.
- CLI/wizard: `migrate.py`, `wizard.py`.
- Tests: `tests/`; architecture, limitations and plans: `docs/`.
- Output folders are generated artifacts, not implementation source.

## Development Contract

1. Read before editing; search for existing helpers before adding functions.
2. Plan multi-step changes without creating unsolicited plan documents.
3. Use exactly one primary owner per recursive non-`__init__.py` runtime module
   under the three packages above, plus the CLI/wizard. Only backticked paths in
   an agent's `## Owned Files` section are ownership claims. Keep handoffs elsewhere.
4. Fix source generators, regenerate, and preserve MicroStrategy-specific levels,
   attribute forms/keys, prompts, reports/dossiers, cubes and security filters.
5. Run `pytest tests/ --tb=short -q` after implementation changes; coordinate a
   single integrated run during parallel work. New behavior requires tests.
   Never weaken assertions or invent pass/coverage counts.
6. Run `python scripts/check_agent_ownership.py` and
   `python scripts/validate_skills.py` after customization changes.
7. Use existing dependency/runtime conventions. Read the actual parser and dispatch
   before documenting commands; Tableau CLI syntax is not this CLI's syntax.
8. Apply **@readme**'s documentation checklist before and after updates. Keep
   release claims, links, examples and counts tied to current implementation and
   measured evidence; **@roadmap-planner** owns planning priorities.

## Safety and Evidence

Static inspection, generated definitions, mocked tests and advisory review are
not runtime proof. Desktop opening/rendering, refresh, query execution, effective
RLS, deployment and Fabric pipeline completion remain **`not_run`** unless an
authorized matching run supplies evidence. Healing/evidence/Fabric agent roles
add development guidance, not an automatic runtime healing or evidence pipeline.

Keep changes metadata-driven, not report-specific. Do not assume nonexistent
error hierarchies, modules or CLI switches. AI fallback is opt-in/budgeted and
must not transmit customer metadata without permission. Audit exact publication
scope for secrets, personal/customer data, private endpoints and asset provenance.
Do not publish unresolved sensitive or unlicensed content, generated outputs or
unrelated changes. Commit/push only when requested, after checks pass, using
conventional messages and the required co-author trailer.

## Committed Reference

Customization governance patterns were adapted from TableauToPowerBI commit
`3de10594f4e2b7d5fc97a58e8adb9571a9844d94`, not dirty working-tree files or
untracked Azure bundles. Preserve target-domain behavior rather than claiming
the reference project's runtime features or test totals exist here.
