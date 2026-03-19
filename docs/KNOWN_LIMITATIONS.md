# Known Limitations — MicroStrategy to Power BI Migration

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
| `ApplyAgg` / `ApplyOLAP` functions | Flagged as manual review | Sprint 11: Enhanced passthrough handling |
| Object prompts with dynamic attributes | Converted to static field parameter | Sprint 12: Dynamic parameter support |
| Prompted Intelligent Cubes | Static import from default answers | Sprint 12: Parameter integration |
| Multi-source reports | Merged into single model | Sprint 13: Multi-model support |
| Nested panel stacks | Flattened to single level | Sprint 12: Deep panel stack support |
| Theme CSS customization | Basic colors only | Sprint 12: Theme enrichment |

## MicroStrategy Version Compatibility

| Version | Support Level | Notes |
|---------|--------------|-------|
| MicroStrategy 2021+ | ✅ Full | REST API v2 fully supported |
| MicroStrategy 2020 | ⚠️ Partial | Some Modeling API endpoints may be missing |
| MicroStrategy 10.x | ⚠️ Limited | Older REST API; schema extraction may need fallbacks |
| MicroStrategy 9.x | ❌ Not supported | No REST API; would require direct metadata DB access |
