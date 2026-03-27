# Enterprise Migration Guide

Step-by-step guide for large-scale MicroStrategy → Power BI / Fabric migrations.

---

## Phase 1: Discovery & Assessment

1. **Inventory**: Use `--batch --assess` to catalog all reports, dossiers, and cubes.
2. **Portfolio assessment**: Run `--global-assess DIR` across multiple projects.
3. **Strategy recommendation**: Run `--strategy` per project to get Import / DirectQuery / Composite / DirectLake advice.
4. **Governance check**: Run `--governance` to generate a pre-migration checklist (ownership, classification, RLS, lineage).

```bash
python migrate.py --server URL --username admin --password pass \
    --project "Enterprise" --batch --assess --strategy --governance \
    --output-dir assessment/
```

---

## Phase 2: Infrastructure Setup

1. **Fabric workspace**: Create a Fabric workspace with appropriate capacity (F2–F64).
2. **Lakehouse**: Provision a Lakehouse for DirectLake mode.
3. **Git integration**: Enable Fabric Git integration for version control.
4. **SLA configuration**: Create an SLA config file:

```json
{
    "max_migration_seconds": 120,
    "min_fidelity_score": 85.0,
    "require_validation_pass": true,
    "alert_on_breach": true
}
```

---

## Phase 3: Pilot Migration (1–3 Reports)

1. Select representative reports (simple, medium, complex).
2. Run full migration with monitoring:

```bash
python migrate.py --from-export ./pilot_export/ \
    --output-dir pilot_output/ \
    --monitor json --sla-config sla.json \
    --compare --alerts
```

3. Review:
   - `migration_report.html` — fidelity scores
   - `sla_report.json` — timing compliance
   - `alert_rules.json` — threshold migration
   - `recovery_report.json` — automatic repairs

---

## Phase 4: Bulk Migration

1. Extract all objects:
```bash
python migrate.py --server URL --username admin --password pass \
    --project "Enterprise" --batch --output-dir bulk_output/ \
    --monitor json --alerts --migrate-schedules
```

2. For Fabric DirectLake mode:
```bash
python migrate.py --from-export ./exports/ \
    --fabric-mode lakehouse --lakehouse-name EnterpriseLH \
    --direct-lake --output-dir fabric_output/
```

---

## Phase 5: Validation & Quality Gates

1. **DAX optimization**: `--optimize-dax --auto-time-intelligence`
2. **Comparison**: `--compare` for source-vs-output HTML report
3. **Certification**: `--certify --certify-threshold 85`
4. **Regression snapshots**: `--snapshot-update` to baseline outputs

```bash
python migrate.py --from-export ./exports/ \
    --output-dir validated/ \
    --optimize-dax --compare --certify --certify-threshold 85
```

---

## Phase 6: Deployment

### Power BI Service
```bash
python migrate.py --from-export ./exports/ \
    --output-dir deploy/ \
    --deploy WORKSPACE_ID --tenant-id TENANT --client-id APP --client-secret SECRET \
    --deploy-refresh
```

### Microsoft Fabric
```bash
python migrate.py --from-export ./exports/ \
    --output-dir deploy/ \
    --deploy WORKSPACE_ID --fabric \
    --tenant-id TENANT --client-id APP --client-secret SECRET \
    --deploy-env prod --direct-lake --lakehouse-id LH_ID
```

### Fabric Git Push
```bash
python migrate.py --from-export ./exports/ \
    --output-dir deploy/ \
    --fabric-git --fabric-git-branch main
```

---

## Phase 7: Monitoring & Operations

1. **Enable monitoring** on all production migrations: `--monitor azure`
2. **SLA tracking**: Review `sla_report.json` after each run
3. **Alerting**: Deploy `alert_rules.json` to PBI data-driven alerts
4. **Refresh schedules**: Apply `refresh_config.json` via PBI REST API
5. **Recovery reports**: Review `recovery_report.json` for automatic fixes

### Continuous monitoring
```bash
# Change detection for incremental sync
python migrate.py --from-export ./latest/ \
    --previous-dir ./previous/ --watch --reconcile \
    --baseline-dir ./baseline/ --monitor json
```

---

## Phase 8: Ongoing Maintenance

1. **Incremental migration**: Use `--incremental` for changed objects only.
2. **Drift detection**: Use `--watch` to detect manual PBI edits.
3. **Three-way reconcile**: Use `--reconcile` to preserve manual edits while applying MSTR changes.
4. **Real-time sources**: Use `--realtime` for push datasets and Eventstream.
5. **Lineage tracking**: Use `--lineage --purview ACCOUNT` for data catalog integration.

---

## CLI Quick Reference

| Flag | Purpose |
|------|---------|
| `--assess` | Pre-migration assessment |
| `--strategy` | Import/DQ/Composite/DirectLake recommendation |
| `--governance` | Governance checklist |
| `--monitor json\|azure\|prometheus` | Migration monitoring |
| `--sla-config FILE` | SLA compliance tracking |
| `--alerts` | Generate alert rules from thresholds |
| `--migrate-schedules` | Convert refresh schedules |
| `--compare` | Source-vs-output comparison |
| `--certify` | Pass/fail certification |
| `--optimize-dax` | DAX optimization rewrites |
| `--deploy WORKSPACE` | Deploy to PBI Service |
| `--fabric` | Deploy to Fabric |
| `--watch` | Change detection |
| `--reconcile` | Three-way merge with user edits |
| `--incremental` | Incremental migration |
| `--lineage` | Data lineage graph |
