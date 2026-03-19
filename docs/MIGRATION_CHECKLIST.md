# Migration Checklist — MicroStrategy to Power BI / Fabric

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
  python migrate.py --server URL --project P --batch --deploy WORKSPACE_ID --deploy-refresh
  ```

- [ ] **Configure refresh schedule**
  - Set up scheduled refresh for Import mode datasets
  - Configure gateway credentials

- [ ] **Set up monitoring**
  - Enable Power BI usage metrics
  - Set up data refresh failure alerts
  - Configure Azure Monitor (if using Fabric)

- [ ] **User acceptance testing**
  - Share with pilot users 
  - Collect feedback
  - Address issues

## Phase 6: Cutover

- [ ] **Communicate migration timeline** to users
- [ ] **Deploy to production workspace**
- [ ] **Update user bookmarks/links**
- [ ] **Decommission MicroStrategy reports** (after validation period)
- [ ] **Document any manual customizations** made post-migration
