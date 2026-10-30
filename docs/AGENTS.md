# Development Agents — MicroStrategy to Power BI

These are scoped **development/customization roles**, not agents automatically
executed by the migration engine. The runtime remains REST/offline extraction →
intermediate JSON → generation → local validation and optional authorized
operations. Adding a role does not implement a healing loop or native validation.

## Entry Points and Shared Rules

- [Repository instructions](../.github/copilot-instructions.md)
- [Shared rules](../.github/agents/shared.instructions.md) — read explicitly;
  automatic discovery is not assumed for this nested location.
- [Migration workflow skill](../.github/skills/microstrategy-to-powerbi/SKILL.md)
- [Architecture](ARCHITECTURE.md), [limitations](KNOWN_LIMITATIONS.md) and
  [existing development plan](DEVELOPMENT_PLAN.md)

Each agent has a meaningful discovery description, supported tool aliases and
`user-invocable: true`; no model is pinned. The filename is its invocation alias.
Use roles only when their scope helps; do not launch a separate agent for every
small lookup or checklist.

## Topology

```text
orchestrator (CLI/wizard)
  +-- extractor (extraction contracts + universal BI adapters)
  |     +-- extraction (MicroStrategy REST/objects/JSON)
  |     +-- expression (MicroStrategy expression grammar -> DAX)
  +-- converter (conversion coordination)
  |     +-- expression / dax (optimization/recipes/AI fallback)
  |     +-- wiring (M + calculated-column classification)
  +-- generator / generation (integration / cross-cutting triage)
  |     +-- semantic (TMDL, Calendar, RLS, locale, goals)
  |     +-- visual (PBIR, themes, threshold alerts)
  |     +-- fabric (Lakehouse/Dataflow/notebook/pipeline/DirectLake emitters)
  +-- merger (shared models, conflicts, thin reports)
  +-- assessor (readiness, strategy, governance)
  +-- evidence (static checks, reports, comparisons, certification)
  +-- healing (recovery-report + reconciliation development)
  +-- deployer (authorized remote operations + telemetry)

Cross-cutting: validation / testing (coordination), reviewer (read-only),
              tester (tests), parity (committed-reference analysis),
              roadmap-planner (existing plans), readme (documentation governance)
```

Arrows describe development handoffs, not runtime scheduling, automatic delegation,
or a mandatory invocation chain.

## Primary Owners and Invocation

The exact file inventory lives in each linked agent's **`## Owned Files`** section.
This table summarizes scope without creating a second ownership source.

| Alias | Primary responsibility |
|---|---|
| [@orchestrator](../.github/agents/orchestrator.agent.md) | CLI, wizard, plugin hooks and progress |
| [@extractor](../.github/agents/extractor.agent.md) | Extraction coordination; universal BI schema/adapters/cross-lineage |
| [@extraction](../.github/agents/extraction.agent.md) | REST auth/pagination, reports/dossiers/cubes/prompts/security, JSON and extraction change tracking |
| [@expression](../.github/agents/expression.agent.md) | Apply* expressions, levels, derived/conditional/compound metrics |
| [@converter](../.github/agents/converter.agent.md) | Conversion coordination only; no runtime files |
| [@dax](../.github/agents/dax.agent.md) | DAX optimization/recipes, semantic matching and opt-in AI fallback |
| [@wiring](../.github/agents/wiring.agent.md) | M generation and calculated-column classification |
| [@generator](../.github/agents/generator.agent.md) | Importer, PBIP scaffolding and pattern registry |
| [@generation](../.github/agents/generation.agent.md) | Cross-cutting generation triage only; no directory-wide ownership |
| [@semantic](../.github/agents/semantic.agent.md) | Ordinary TMDL, model templates, goals and i18n |
| [@visual](../.github/agents/visual.agent.md) | Visual JSON, themes and alert definitions |
| [@fabric](../.github/agents/fabric.agent.md) | Fabric type/naming maps and native artifact generators |
| [@merger](../.github/agents/merger.agent.md) | Merge/shared-model logic, assessments/config/reports and thin reports |
| [@assessor](../.github/agents/assessor.agent.md) | Readiness, global/server assessments, strategy and governance checklist |
| [@evidence](../.github/agents/evidence.agent.md) | Artifact/security checks, certification, comparison/regression, lineage/SLA and report presentation |
| [@healing](../.github/agents/healing.agent.md) | Existing recovery ledger and three-way reconciliation utilities |
| [@deployer](../.github/agents/deployer.agent.md) | Deployment/auth/gateway/Git/environment/refresh and telemetry/monitoring |
| [@validation](../.github/agents/validation.agent.md) | Validation coordination only; evidence/assessment owners implement checks |
| [@reviewer](../.github/agents/reviewer.agent.md) | Read-only artifact/source review and advisory coaching |
| [@tester](../.github/agents/tester.agent.md) | Test code/fixtures; no runtime modules |
| [@testing](../.github/agents/testing.agent.md) | Test strategy/execution interpretation; no competing test ownership |
| [@parity](../.github/agents/parity.agent.md) | Read-only reference gap analysis; no copied counts or feature guarantees |
| [@roadmap-planner](../.github/agents/roadmap-planner.agent.md) | Existing development/migration plans, priorities and exit gates |
| [@readme](../.github/agents/readme.agent.md) | README/contributor/changelog/customization governance and developer-tool guards |

## Ownership Contract

Every non-`__init__.py` Python module recursively under `powerbi_import`,
`microstrategy_export` and `universal_bi`, plus `migrate.py` and `wizard.py`, must
have **exactly one** primary owner. Only backticked full repository-relative paths
or exclusive globs inside `## Owned Files`, up to the next heading, count.
Other sections may mention modules for handoffs without claiming them.

Coordination roles explicitly own no runtime files. New modules require a primary
owner in the same change; do not reintroduce broad generation/extraction/validation
directory claims that overlap specialists. Tests belong to Tester; the ownership
and skills guard scripts belong to Documentation Guardian.

```powershell
python scripts/check_agent_ownership.py
python scripts/validate_skills.py
```

The first guard checks runtime coverage, overlaps and stale Python claims. The
second checks skill frontmatter, relative links and documented CLI options.
These are static developer-tool checks, not migration/runtime proof.

## Handoff and Review Protocol

1. Read shared rules, relevant source and the actual CLI dispatch. Start with a
   concrete failure or falsifiable hypothesis, not a historical feature count.
2. Supply source IDs, a synthetic minimal fixture, input/output contract, failing
   check, expected semantics, owner and focused acceptance criterion.
3. Fix source extractors/converters/generators, regenerate separately, and preserve
   manual edits/conflicts. Reports must not mutate artifacts to improve a score.
4. Tester supplies positive/negative regressions; coordinate one integrated
   `pytest tests/ --tb=short -q` run rather than competing full suites.
5. Reviewer may score completeness, formulas, queries, structure and report
   fidelity. A four-star advisory review is not an implemented automatic gate.
   After three unsuccessful development iterations, report the blocker.
6. Apply Readme's pre/post-update documentation checklist directly or via handoff;
   reconcile release claims, links, command examples and privacy/provenance.

## Evidence Limits

Static checks establish only what their implementation inspects. Mocked tests
prove local contracts, not live service behavior. Object/field coverage, screenshot
similarity or certification scores are not numeric, interaction or security parity.

Desktop opening/rendering, data refresh, semantic queries, effective RLS, deployment
and Fabric pipeline completion remain **`not_run`** unless an authorized executor
produced evidence for the matching generated revision/environment. Record command,
scope, result, baseline and limitations; preserve skips, warnings and approximations.
Do not retrofit a new serialized status schema merely to document these principles.

Healing owns recovery recording and reconciliation development. It does not claim
an automatic healing pipeline, native Desktop probes or reference-only modules.
Fabric owns emitted definitions; remote binding, deployment and refresh belong to
Deployer and need separate authorization/evidence. AI fallback must remain opt-in,
budgeted and privacy-preserving; deterministic checks stay authoritative.

## Synchronization Provenance

Governance, planner/readme, healing/evidence/Fabric role patterns and the migration
skill workflow were adapted from committed TableauToPowerBI SHA
`3de10594f4e2b7d5fc97a58e8adb9571a9844d94` using committed file reads.
Dirty reference runtime/docs and untracked Azure bundles were not imported.
MicroStrategy expression/extraction knowledge and target module boundaries are
retained; reference-only CLI flags, error hierarchies, healing/runtime features and
test/coverage totals are not target capabilities.
