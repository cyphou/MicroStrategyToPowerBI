---
name: microstrategy-to-powerbi
description: "Migrate MicroStrategy reports, dossiers, metadata and offline JSON exports to Power BI PBIP/TMDL/PBIR or Fabric definitions using this repository. Use for readiness assessment, batch/shared models, generation defects, source-to-target comparisons, certification and deployment handoffs; not general Power BI authoring or raw Tableau workbook migration."
user-invocable: true
---

# MicroStrategy Migration Workflow

## Read Before Running

Read the [shared rules](../../agents/shared.instructions.md),
[agent ownership guide](../../../docs/AGENTS.md),
[architecture](../../../docs/ARCHITECTURE.md),
[migration checklist](../../../docs/MIGRATION_CHECKLIST.md),
[mapping reference](../../../docs/MAPPING_REFERENCE.md), and
[known limitations](../../../docs/KNOWN_LIMITATIONS.md) for the affected feature.
The [CLI implementation](../../../migrate.py), especially `build_parser()` and
dispatch, is authoritative when historical documentation differs.

This skill adapts committed TableauToPowerBI workflow patterns at
`3de10594f4e2b7d5fc97a58e8adb9571a9844d94`; its positional commands, automatic
healing/native probes, stdlib-only policy and bundle guarantees do not transfer.

## Procedure

1. **Establish scope and privacy.** Identify authorized project/object IDs, REST
   access or an existing intermediate JSON export directory, target/output paths,
   connectivity and security requirements. Protect exports and auth material.
   Read the dependency manifest; use the configured interpreter/environment.
   Do not install dependencies unless the chosen command reports one missing.
2. **Inspect current behavior.** Read relevant CLI parsing/dispatch and existing
   tests, then run help. This is a flag-based CLI, not a positional subcommand CLI.
   Check prerequisites for each mode; parser acceptance alone does not prove a
   branch executes. Offline loading can populate working extraction files, so run
   in an appropriate checkout and preserve existing intermediates before running.
3. **Assess before generating.** Inventory reports/dossiers, cubes, attribute
   forms/keys, facts, level/conditional metrics, prompts, connections and security
   filters. Assess unsupported features and explain approximation/manual work.
4. **Generate reproducibly.** Prefer the repository CLI over hand-authoring emitted
   files. Fix the source extractor/converter/generator first when output is wrong,
   add a synthetic regression, and regenerate into a separate local output folder.
   Never patch emitted TMDL/PBIR/M as the only durable fix.
5. **Validate and compare.** Inspect static validation, warnings, coverage and
   certification scope. Route implementation to the exclusive owner. Reconcile
   manual edits conservatively; keep source IDs and baseline provenance.
6. **Report evidence and hand off.** Record input scope/revision, command, output,
   exit/result and limitations. Remote deployment/refresh and native application
   work are separate authorized actions, not implied by generation.

## Canonical CLI Examples

Run from the repository root with the configured Python interpreter. Paths below
are synthetic project-local placeholders; the export directory must already
contain valid MicroStrategy intermediate JSON, not report XML or raw Tableau files.

```powershell
python migrate.py --help
python migrate.py --from-export .\mstr_exports --assess --output-dir .\artifacts\assessment
python migrate.py --from-export .\mstr_exports --strategy --output-dir .\artifacts\strategy
python migrate.py --from-export .\mstr_exports --output-dir .\artifacts\pilot --report-name Pilot
python migrate.py --from-export .\mstr_exports --batch --output-dir .\artifacts\batch
python migrate.py --from-export .\mstr_exports --shared-model --output-dir .\artifacts\shared
python migrate.py --from-export .\mstr_exports --compare --certify --certify-threshold 80 --output-dir .\artifacts\review
python migrate.py --from-export .\mstr_exports --fabric-mode lakehouse --lakehouse-name PilotLakehouse --output-dir .\artifacts\fabric
```

For live extraction select an authorized server/project and `--report`,
`--report-id`, `--dossier`, `--dossier-id` or `--batch`. Read the existing auth/config
implementation; never put real passwords, tokens or private URLs in documentation
or recorded command examples. `--config` loads supported connection fields; do not
assume it supplies every generation option.

Other real options include `--no-calendar`, `--culture`, `--cultures`,
`--incremental`, `--parallel`, `--optimize-dax`, `--auto-time-intelligence`,
`--lineage` and `--governance`. Inspect their dispatch and mode restrictions first.
Change detection/reconciliation additionally use `--watch`, `--previous-dir`,
`--reconcile` and `--baseline-dir`; these utilities do not imply automatic healing.

`--fabric-mode` selects generated Fabric definitions; `--fabric` selects Fabric
deployment with `--deploy WORKSPACE_ID`. `--direct-lake` requires `--lakehouse-id`.
Do not launch deployment, refresh, Git sync, Purview registration or external AI
calls without explicit authorization, correct target binding and safe credentials.
AI fallback uses `--ai-assist` and the existing endpoint/deployment/budget settings;
do not enable it silently or transmit sensitive formulas without approval.

## Owner Handoffs

- **@orchestrator:** parser/dispatch/wizard.
- **@extraction / @expression:** REST/JSON extraction and MicroStrategy formulas.
- **@extractor / @merger:** normalized adapters, federation, shared models/conflicts.
- **@generator / @semantic / @visual / @wiring / @dax / @fabric:** source emitters.
- **@assessor / @evidence / @healing:** readiness, static reports/checks, recovery
  recording/reconciliation development.
- **@tester / @reviewer / @readme:** regressions, independent review, truthful docs.

Handoffs are development coordination, not automated runtime routing. Include a
minimal reproducer, source IDs, expected semantics, failure evidence and exit gate.

## Verification Limits

Run `pytest tests/ --tb=short -q` after implementation changes and coordinate one
integrated suite when several agents share the checkout. For customization changes:

```powershell
python scripts/check_agent_ownership.py
python scripts/validate_skills.py
```

Those guards inspect developer-tool contracts only. Static PBIR/TMDL checks, mock
tests, generated notebooks/pipelines, comparison coverage and certification scores
cannot prove Desktop opening/rendering, successful data refresh, measure results,
effective RLS, live deployment or completed Fabric ingestion. Report those stages
as **`not_run`** unless a matching authorized runtime run provides proof. Recovery
utilities do not establish an integrated auto-healing pipeline. Never upgrade an
approximation, skipped check or absent runtime evidence to success.
