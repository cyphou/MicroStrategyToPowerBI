# Known Limitations — MicroStrategy to Power BI Migration

## Version History of Improvements

### v16.0 — Fabric Deep Integration Phase 2
| Feature | Status | Details |
|---------|--------|--------|
| **DirectLake semantic model** | ✅ New | Dedicated generator with expression-less tables, entityName partition bindings |
| **Dataflow Gen2** | ✅ New | Power Query M mashup → Lakehouse Delta destinations (6 connector templates) |
| **Calculated column classification** | ✅ New | Auto-classify expressions as lakehouse (PySpark) or DAX-only |
| **Centralized Azure AD auth** | ✅ New | Service Principal, Managed Identity, interactive browser, token caching |
| **Fabric REST API client** | ✅ New | Retry, pagination, workspace/item CRUD, long-running ops |
| **Atomic bundle deployment** | ✅ New | Shared model + thin reports with rollback on failure, endorsement |
| **Fabric naming sanitization** | ✅ New | 64-char limits, collision detection, reserved word handling |

### v15.0 — DAX Optimization & Quality Gates
| Feature | Status | Details |
|---------|--------|--------|
| **DAX optimizer** | ✅ New | AST-based: ISBLANK→COALESCE, IF→SWITCH, CALCULATE simplification |
| **Time Intelligence injection** | ✅ New | Auto-generate YTD, PY, YoY% for date-based measures |
| **Equivalence testing** | ✅ New | Cross-platform value comparison + SSIM screenshot comparison |
| **Regression snapshots** | ✅ New | SHA-256 hash-based drift detection with manifest tracking |
| **Security validation** | ✅ New | Path traversal, ZIP slip, XXE, dangerous extension blocking |

### v11.0 — Migration Ops
| Feature | Status | Details |
|---------|--------|--------|
| **Change detection** | ✅ New | Compare current vs previous JSON extraction for added/modified/deleted objects |
| **Drift monitoring** | ✅ New | Detect manual PBI edits against migration baseline |
| **Three-way reconciliation** | ✅ New | Preserve user edits while applying MSTR changes; dry-run mode |
| **Scheduled migration** | ✅ New | Cron-compatible pipeline script |

### v9.0 — Real-Time & Streaming
| Feature | Status | Details |
|---------|--------|--------|
| **Real-time source detection** | ✅ New | Classify dashboards as batch/near-realtime/streaming |
| **Push datasets** | ✅ New | PBI REST API push dataset definitions |
| **Eventstream** | ✅ New | Fabric Real-Time Intelligence Eventstream definitions |
| **Refresh schedule migration** | ✅ New | MSTR cache/subscription → PBI dataset refresh schedules |

### v8.0 — Multi-Language i18n
| Feature | Status | Details |
|---------|--------|--------|
| **30+ cultures** | ✅ New | TMDL cultures.tmdl + translations.tmdl with linguisticMetadata |
| **RTL layout** | ✅ New | x-coordinate mirroring + textDirection for Arabic/Hebrew/Farsi/Urdu |
| **Format strings** | ✅ New | Culture-specific currency, date, number patterns |
| **Auto-detect locale** | ✅ New | Detect locale hints from datasource connections |

### v7.0 — AI-Assisted Migration
| Feature | Status | Details |
|---------|--------|--------|
| **Azure OpenAI fallback** | ✅ New | LLM conversion for ApplySimple/ApplyAgg/ApplyOLAP expressions |
| **DAX syntax validation** | ✅ New | Balance parens, no SQL keywords, known function checks |
| **Response caching** | ✅ New | Persistent JSON cache to avoid redundant API calls |
| **Semantic field matcher** | ✅ New | Fuzzy matching with 90+ abbreviations, correction learning |

### v6.0 — Governance & Lineage
| Feature | Status | Details |
|---------|--------|--------|
| **Data lineage graph** | ✅ New | In-memory DAG from warehouse → MSTR → PBI |
| **Impact analysis** | ✅ New | Transitive upstream/downstream traversal |
| **Purview integration** | ✅ New | Register assets via Apache Atlas REST API with sensitivity labels |
| **Governance report** | ✅ New | 6-category pre-migration checklist with scoring |

### v5.0 — Fabric Native Integration
| Feature | Status | Details |
|---------|--------|--------|
| **DirectLake TMDL** | ✅ New | `mode: directLake` partitions with Delta table entity references |
| **Lakehouse DDL** | ✅ New | Spark SQL `CREATE TABLE ... USING DELTA` scripts |
| **PySpark ETL notebooks** | ✅ New | JDBC/Snowflake/BigQuery/Databricks connectors |
| **Data Factory pipelines** | ✅ New | Copy activities + refresh + notification |
| **OneLake shortcuts** | ✅ New | Zero-copy ADLS/external data references |
| **Fabric Git integration** | ✅ New | Push .pbip to workspace Git repos |

### v4.0 — Multi-Project Merge & Scorecards
| Feature | Status | Details |
|---------|--------|--------|
| **Multi-project merge** | ✅ New | Merge N intermediate-JSON projects into shared model |
| **Scorecard extraction** | ✅ New | MicroStrategy scorecards → PBI Goals |
| **Post-migration certification** | ✅ New | PASS/FAIL verdict based on fidelity threshold |
| **Performance benchmarking** | ✅ New | Generation pipeline timing analysis |

### v3.0 Improvements

| Feature | Status | Details |
|---------|--------|--------|
| **14-category assessment** | ✅ New | CheckItem/CategoryResult model with GREEN/YELLOW/RED scoring, effort estimation in hours |
| **Strategy advisor** | ✅ New | Automatic Import/DQ/Composite/DirectLake recommendation with confidence scoring |
| **Comparison reports** | ✅ New | Side-by-side MSTR↔PBI HTML comparison for post-migration validation |
| **Visual diff** | ✅ New | Field coverage analysis identifying missing columns and measure mismatches |
| **Telemetry** | ✅ New | Migration run data collection with historical dashboard |
| **Thin reports** | ✅ New | Lightweight reports referencing shared semantic models |
| **Plugin system** | ✅ New | Extension hooks for custom pre/post transformations |
| **Progress bars** | ✅ New | tqdm-based progress tracking for long-running operations |
| **Calendar suppression** | ✅ New | `--no-calendar` flag when date dimension table exists |

## Unsupported Features

| Feature | Status | Notes |
|---------|--------|-------|
| **Transaction Services (write-back)** | ❌ Not supported | Power BI does not support write-back natively. Consider Power Apps embedding. |
| **Custom visualization plugins** | ❌ Not supported | MicroStrategy custom viz SDK plugins have no PBI equivalent. Manual recreation required. |
| **Distribution Services** | ❌ Not mapped | MicroStrategy email subscriptions and scheduled deliveries must be recreated as Power BI subscriptions. |
| **Expression prompts** | ❌ Not supported | Complex expression-based prompts have no direct PBI equivalent. |
| **HTML Containers** | ❌ Not supported | HTML rendering in visualizations is not available in Power BI. Converted to text box with warning. |
| **Mobile-specific layouts** | ❌ Not mapped | MicroStrategy mobile-specific dossier layouts are not migrated. Use PBI mobile layout editor. |

## Approximated Features

| Feature | Approximation | Impact |
|---------|---------------|--------|
| **Level metrics** `{~+, Attr}` | `CALCULATE([M], ALLEXCEPT(T, T[Col]))` | Table references need manual adjustment to match actual model |
| **ApplySimple SQL passthrough** | Common patterns auto-converted; complex SQL flagged | Database-specific SQL may need manual DAX rewrite |
| **Panel stacks** | Bookmarks + toggle buttons | Tabs → bookmarks with show/hide; not pixel-identical |
| **Info windows** | Tooltip pages | Tooltip content may differ in layout |
| **Dossier layout** | Proportional scaling to PBI canvas | Positions are scaled from MSTR canvas to 1280×720; not pixel-perfect |
| **Derived metrics (OLAP)** | RANKX / WINDOW / VAR patterns | RunningSum/Avg/MovingAvg use placeholder patterns that may need refinement |
| **Nested metric references** | Inline resolution | Deeply nested metric chains may lose intermediate formatting |
| **Custom groups** | SWITCH() calculated column | Multi-condition groups converted to DAX SWITCH with conditions |
| **Consolidations** | Calculated table or measure | Custom aggregation hierarchies approximated |

## Known Gaps

| Gap | Details | Planned Fix |
|-----|---------|-------------|
| **ApplyAgg** / **ApplyOLAP** functions | Best-effort conversion; complex patterns flagged | Use `--ai-assist` for Azure OpenAI fallback |
| Object prompts with dynamic attributes | Converted to static field parameter | Future: Dynamic parameter support |
| Prompted Intelligent Cubes | Static import from default answers | Future: Parameter integration |
| Multi-source reports | Merged into single model | Future: Multi-model support |
| Nested panel stacks | Flattened to single level | Future: Deep panel stack support |
| Theme CSS customization | Basic colors only | Future: Theme enrichment |

## MicroStrategy Version Compatibility

| Version | Support Level | Notes |
|---------|--------------|-------|
| MicroStrategy 2021+ | ✅ Full | REST API v2 fully supported |
| MicroStrategy 2020 | ⚠️ Partial | Some Modeling API endpoints may be missing |
| MicroStrategy 10.x | ⚠️ Limited | Older REST API; schema extraction may need fallbacks |
| MicroStrategy 9.x | ❌ Not supported | No REST API; would require direct metadata DB access |
