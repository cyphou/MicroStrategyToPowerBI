# Migration Checklist — MicroStrategy to Power BI / Fabric

**Version:** v16.0.0 — Comprehensive enterprise migration guide covering all migration modes.

## Phase 1: Assessment

- [ ] **Inventory MicroStrategy project**
  - Run `python migrate.py --server URL --project P --assess` 
  - Review 14-category assessment: expressions, visuals, connectors, security, prompts, hierarchies, relationships, data types, formatting, calculated tables, partitions, RLS, aggregations, advanced features
  - Review GREEN/YELLOW/RED scoring and effort estimation (hours)
  - Identify unsupported features (transaction services, custom viz plugins)

- [ ] **Portfolio-wide assessment** (if multiple projects)
  - Run `python migrate.py --global-assess ./exports/ --output-dir assessment/`
  - Review consolidated scoring across all projects
  - Identify common patterns and shared data sources

- [ ] **Strategy recommendation**
  - Run `python migrate.py --server URL --project P --strategy`
  - Review recommended mode: Import / DirectQuery / Composite / DirectLake
  - Validate recommendation against data volume and refresh requirements

- [ ] **Map data connections**
  - List all warehouse connections (Oracle, SQL Server, Teradata, etc.)
  - Determine Power BI connectivity: Direct Query vs Import mode
  - Identify on-premises gateways needed
  - Verify network access from Power BI to data sources

- [ ] **Identify security requirements**
  - Map MicroStrategy security filters to Power BI RLS roles
  - Map user/group assignments to Azure AD groups
  - Plan workspace permissions (Admin/Member/Contributor/Viewer)

- [ ] **Plan target architecture**
  - One shared semantic model or per-report models?
  - Power BI Service vs Microsoft Fabric?
  - Workspace organization (one workspace per domain?)
  - Gateway configuration

## Phase 2: Pilot Migration

- [ ] **Select pilot scope**
  - Choose 2-3 representative reports/dossiers
  - Include at least one simple report and one complex dossier
  - Cover major data sources used

- [ ] **Run pilot migration**
  ```bash
  python migrate.py --server URL --project P --dossier "Pilot Dashboard" --output-dir pilot/
  ```

- [ ] **Validate pilot**
  - Open `.pbip` in Power BI Desktop
  - Verify data connections work
  - Compare visuals against MicroStrategy originals
  - Run comparison report: `python migrate.py --server URL --project P --dossier "Pilot Dashboard" --compare`
  - Review side-by-side HTML comparison and visual diff
  - Check calculated measures against known values
  - Review migration report for warnings

- [ ] **Address pilot issues**
  - Fix manual review items (ApplySimple, complex expressions)
  - Adjust layout/positioning if needed
  - Validate RLS roles

## Phase 3: Batch Migration

- [ ] **Run batch migration**
  ```bash
  python migrate.py --server URL --project P --batch --output-dir production/
  ```

- [ ] **Review batch results**
  - Check migration summary for failures
  - Review per-report fidelity scores
  - Prioritize manual review items

- [ ] **Generate shared semantic model** (if applicable)
  ```bash
  python migrate.py --server URL --project P --shared-model --output-dir production/shared/
  ```

## Phase 4: Validation

- [ ] **Data validation**
  - Compare key metrics between MicroStrategy and Power BI
  - Spot-check calculations: totals, averages, counts
  - Validate filters and slicers

- [ ] **Visual validation**
  - Verify chart types are correct
  - Check conditional formatting (thresholds)
  - Verify drill-down behavior
  - Test prompts/slicers

- [ ] **Security validation**
  - Test RLS roles with different user accounts
  - Verify row-level security filters match MicroStrategy

- [ ] **Performance validation**
  - Check report load times
  - Validate Direct Query performance (if used)
  - Optimize slow measures

## Phase 5: Deployment

- [ ] **Deploy to Power BI Service / Fabric**
  ```bash
  # Power BI Service
  python migrate.py --server URL --project P --batch --deploy WORKSPACE_ID --deploy-refresh

  # Microsoft Fabric (DirectLake)
  python migrate.py --from-export ./exports/ --fabric-mode lakehouse \
      --lakehouse-name SalesLakehouse --deploy FABRIC_WORKSPACE_ID --fabric --deploy-env prod

  # Bundle deployment (shared model + thin reports, atomic with rollback)
  python migrate.py --from-export ./exports/ --shared-model \
      --deploy WORKSPACE_ID --fabric --deploy-env staging
  ```

- [ ] **Configure deployment environment**
  - Select environment: `--deploy-env dev|staging|prod`
  - Verify endorsement level: none (dev), Promoted (staging), Certified (prod)
  - Review capacity requirements (F2–F64) if using Fabric

- [ ] **Configure refresh schedule**
  - Set up scheduled refresh for Import mode datasets
  - Configure gateway credentials for on-premises sources
  - For real-time: `python migrate.py --from-export ./exports/ --realtime`

- [ ] **Set up monitoring**
  - Enable Power BI usage metrics
  - Set up data refresh failure alerts
  - Configure Azure Monitor (if using Fabric)
  - Review migration telemetry dashboard

- [ ] **User acceptance testing**
  - Share with pilot users 
  - Collect feedback
  - Run equivalence testing: compare key metrics between MSTR and PBI  
  - Address issues

## Phase 5b: Fabric-Specific Setup (if applicable)

- [ ] **Lakehouse setup**
  - Review generated Lakehouse DDL (`CREATE TABLE ... USING DELTA`)
  - Apply DDL in Fabric Spark notebook
  - Verify schema in Lakehouse

- [ ] **Data ingestion**
  - Deploy Dataflow Gen2 definitions (one per data source)
  - Deploy PySpark ETL notebooks for JDBC/Snowflake/BigQuery sources
  - Configure Data Factory pipeline for orchestration

- [ ] **DirectLake model**
  - Review generated DirectLake semantic model (entityName partition bindings)
  - Verify Lakehouse binding in shared expression
  - Test query performance

- [ ] **OneLake shortcuts** (if `--fabric-mode shortcut`)
  - Verify ADLS account/container access
  - Deploy shortcuts for zero-copy access

## Phase 5c: Advanced Features (optional)

- [ ] **Multi-language support** (`--cultures en-US,fr-FR,de-DE`)
  - Review generated `cultures.tmdl` and `translations.tmdl`
  - Verify RTL layout (if Arabic/Hebrew/Farsi/Urdu cultures)

- [ ] **DAX optimization** (`--optimize-dax`)
  - Review optimization report (patterns applied, before/after stats)
  - Run Time Intelligence injection (`--auto-time-intelligence`) for date measures

- [ ] **Data lineage** (`--lineage`)
  - Review lineage HTML report (D3.js force-directed graph)
  - Run impact analysis for critical columns

- [ ] **Purview registration** (`--purview ACCOUNT`)
  - Verify assets registered in Microsoft Purview catalog
  - Review sensitivity classification labels

- [ ] **Governance check** (`--governance`)
  - Review 6-category governance checklist report
  - Address any RED items before production deployment

## Phase 6: Cutover

- [ ] **Communicate migration timeline** to users
- [ ] **Deploy to production workspace** (`--deploy-env prod`)
- [ ] **Update user bookmarks/links**
- [ ] **Decommission MicroStrategy reports** (after validation period)
- [ ] **Document any manual customizations** made post-migration

## Phase 7: Continuous Migration (optional)

- [ ] **Set up change detection** (`--watch --previous-dir ./v1_export/`)
  - Monitor MicroStrategy changes between extraction runs
  - Review change manifest for added/modified/deleted objects

- [ ] **Configure drift monitoring**
  - Compare live PBI output against migration baseline
  - Detect manual user edits and generate conflict report

- [ ] **Three-way reconciliation** (`--reconcile --baseline-dir ./v1_output/`)
  - Apply MSTR changes while preserving manual PBI edits
  - Review conflict report for items requiring manual resolution

- [ ] **Scheduled pipeline** (`scripts/scheduled_migration.py`)
  - Configure cron schedule for automatic re-migration
  - Set up notification for migration failures
