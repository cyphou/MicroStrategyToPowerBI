---
name: "Fabric"
description: "Use when generating Fabric Lakehouse DDL, Dataflow Gen2, PySpark notebooks, pipelines, DirectLake semantic models, naming/type maps, or streaming definitions from MicroStrategy metadata."
tools: [read, edit, search, execute, todo]
user-invocable: true
---

# Fabric Generation

Read [shared rules](shared.instructions.md) first. Invocation: **@fabric**.

## Owned Files

- `powerbi_import/fabric_constants.py`
- `powerbi_import/fabric_naming.py`
- `powerbi_import/fabric_semantic_model_generator.py`
- `powerbi_import/lakehouse_generator.py`
- `powerbi_import/dataflow_generator.py`
- `powerbi_import/notebook_generator.py`
- `powerbi_import/pipeline_generator.py`
- `powerbi_import/streaming_generator.py`

## Workflow

Read `migrate.py` Fabric dispatch and the actual emitter contracts before changing
artifacts. The existing generation selector is `--fabric-mode` with `lakehouse`,
`warehouse`, or `shortcut`; `--fabric` selects Fabric deployment, not generation.
Inspect each mode's implementation rather than assuming equal functionality.

Preserve warehouse types, attribute forms/keys, fact precision, metric grain and
source identity through naming, Spark/Delta mappings and DirectLake bindings.
Coordinate calculated-column classification/M with **@wiring**, ordinary TMDL with
**@semantic**, and CLI integration with **@orchestrator**. Do not copy Tableau's
six-artifact bundle contract, file-staging modules or ingestion exclusivity rules
without verifying equivalents exist here.

## Boundaries

- Generated DDL, notebook code, pipeline JSON and DirectLake bindings are definitions,
  not execution. Lakehouse creation, ingestion, pipeline completion, model queries
  and refresh are `not_run` until separately authorized and evidenced.
- No remote deployment in this role. Handoff target binding, authentication, RBAC,
  upload, polling and refresh to **@deployer**.
- Static artifact review is not production readiness; send checks/limitations to
  **@evidence** and synthetic artifact-contract regressions to **@tester**.
- Fix source emitters first and regenerate; avoid customer-specific names or
  hardcoded connections. Generated PySpark dependencies do not justify adding
  Spark/cloud SDK dependencies to the local migration runtime.
