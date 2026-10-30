---
description: "Shared MicroStrategy migration rules for scoped ownership, source-generator fixes, truthful evidence, privacy, provenance, and verification."
applyTo: "**"
---

# Shared Project Rules

These rules apply across this repository. Agents must read this file explicitly:
its location under `.github/agents` is not a guarantee of automatic instruction
discovery. The repository-wide entry point is `.github/copilot-instructions.md`.

## Architecture and Ownership

MicroStrategy REST API or offline JSON exports → `microstrategy_export` extraction
and expression conversion → intermediate JSON → `powerbi_import` PBIP/TMDL/PBIR/M
and optional Fabric definitions. `universal_bi` provides normalization/federation.
`migrate.py` and `wizard.py` coordinate; emitted output directories are artifacts.

- Read target code before editing and search for existing helpers before adding
  functions. Prefer the smallest complete fix; no unrelated refactors.
- Plan multi-step work using task/session tracking, not a new plan Markdown file
  unless requested. Re-plan when an assumption fails.
- Every recursive non-`__init__.py` Python module under `powerbi_import`,
  `microstrategy_export` and `universal_bi`, plus `migrate.py` and `wizard.py`, must
  have exactly one primary owner. Declare backticked full repository-relative paths
  or exclusive globs only under `## Owned Files`, ending at the next heading.
- Coordination roles do not implicitly own whole directories. References elsewhere
  are handoffs, not ownership. Check `docs/AGENTS.md` and the owner before editing.
- Fix source generators first, then regenerate into a separate project-local
  output path. Never make a one-off emitted-artifact patch look like a durable fix.
- Keep generic transformations driven by metadata/structure/types, not hardcoded
  customer/report/field names. Preserve MicroStrategy levels, attribute forms/keys,
  prompts, dossiers, cubes, totals and security semantics.

## Evidence and Capability Claims

- Distinguish source inspection, static artifact checks, mocked tests, generated
  definitions, advisory scores and actual runtime execution.
- Desktop opening/rendering, refresh, semantic query execution, effective RLS,
  deployment and Fabric pipeline completion are **`not_run`** without matching
  authorized execution evidence. A successful static validator or certification
  score cannot substitute for them.
- Record command, scope, revision/baseline, environment, result and limitations.
  Preserve failures, warnings, skips and approximations; do not convert them to pass.
- Recovery reporting and reconciliation utilities are not an automatic healing
  pipeline. Development agents and their handoffs are not runtime orchestration.
- Verify CLI options in `migrate.py` and follow dispatch/prerequisites. Do not copy
  reference-only flags, error types, autoheal modules or runtime assertions.
- Use existing exception/logging conventions; do not assume an unimplemented
  `MigrationError` hierarchy. Avoid hiding programming errors behind broad catches.
- AI fallback is opt-in and budgeted. Deterministic validation remains authoritative;
  no external transmission of formulas/metadata without authorization.

## Verification and Documentation Gate

- Run `pytest tests/ --tb=short -q` after implementation changes. New behavior needs
  corresponding tests; never weaken assertions to make a run pass.
- Coordinate one integrated full-suite run when work is shared. Report exactly
  what ran and what did not; do not claim a coordinator's in-progress run passed.
- After customization changes run `python scripts/check_agent_ownership.py` and
  `python scripts/validate_skills.py`. These static guards do not validate migration
  output or native application behavior.
- Follow existing pytest/`unittest.TestCase` conventions, mocking live services.
  Preserve the supported Python range in project metadata; do not raise the
  minimum version merely to match the reference project's instructions.
- Apply **@readme**'s pre/post-update checklist directly or via a focused handoff:
  links, real CLI examples, version/count provenance and evidence-backed claims.
  Planning priorities belong to **@roadmap-planner**; do not duplicate ownership.

## Privacy, Provenance and Publication

- Treat exports, JSON, formulas, lineage, logs, screenshots and evidence bundles
  as potentially sensitive. Use synthetic fixtures/placeholders; redact credentials,
  auth headers, private endpoints, personal/customer data and environment IDs.
- Never store secrets in code, examples, commands recorded in docs, or commits.
  Remote writes, refreshes, app launches and publication require authorization.
- Before pushing, audit the exact staged/committed scope and changed docs/tests/
  fixtures/assets for secrets, personal/customer information and redistribution
  rights. A public URL is not a license. Unresolved sensitive/provenance findings
  block publication. Report audit scope and remaining caveats.
- Adapt reference patterns only from the identified committed SHA. Ignore dirty
  runtime/docs and untracked Azure bundles; record the source revision used.
- Do not commit generated outputs or unrelated changes. Commit/push only when
  requested and checks pass; use conventional commit messages and required trailer.

## Identifier and Query Safety

Preserve Unicode, accented names, spaces and symbols through M/DAX/TMDL quoting.
Escape connection values, avoid duplicate M step names and preserve explicit
culture where needed. Use `elem is not None` for XML element presence. Check real
emitter syntax and add edge-case regressions rather than copying illustrative code.
