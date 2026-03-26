# Troubleshooting Guide

**Version:** v16.0.0 — Top-30 migration issues and how to resolve them.

---

## 1. Authentication Failure

**Symptom:** `401 Unauthorized` or `Session expired` during extraction.

**Fix:** Verify credentials. For LDAP/SAML, ensure `--auth-mode` is set correctly. Check that the MicroStrategy session timeout hasn't expired (increase `--timeout`).

---

## 2. Missing Metrics in Output

**Symptom:** Some MSTR metrics don't appear as DAX measures in the TMDL.

**Fix:** Metrics not linked to a fact table may be assigned to a fallback table. Check `datasources.json` for unmapped columns. Use `--assess` to review coverage.

---

## 3. `manual_review` Fidelity on Expressions

**Symptom:** DAX output contains `/* MANUAL REVIEW */` comments.

**Fix:** These expressions (typically `ApplySimple`, `ApplyOLAP`) use SQL not directly convertible to DAX. Review the generated DAX and replace placeholders with proper Power BI equivalents.

---

## 4. Wrong Visual Type Mapping

**Symptom:** A chart appears as a table instead of the expected chart type.

**Fix:** Check `MAPPING_REFERENCE.md` for unsupported visual types. Box plots, Sankey, and network graphs map to `tableEx` by default. Convert manually in Power BI Desktop.

---

## 5. Level Metric `{~+}` Not Converted

**Symptom:** CALCULATE expressions reference `Table` instead of actual table names.

**Fix:** Level metrics produce `CALCULATE([M], ALLEXCEPT(Table, ...))` with placeholder table names. Replace `Table` with the actual TMDL table name.

---

## 6. Relationship Errors in Power BI

**Symptom:** "Ambiguous relationship" or missing relationships after import.

**Fix:** Check `relationships.json` for duplicate or conflicting paths. Use Power BI Desktop's relationship editor to resolve ambiguities.

---

## 7. RLS Roles Not Applied

**Symptom:** Security filter roles exist in TMDL but don't restrict data.

**Fix:** RLS roles must be assigned to users in Power BI Service after publishing. The migration tool generates role definitions, not user assignments.

---

## 8. Large Items Exceed Capacity

**Symptom:** Import fails with "model too large" or memory errors.

**Fix:** Use `--strategy` to evaluate DirectQuery or Composite mode. For large models, consider splitting into multiple semantic models with `--shared-model`.

---

## 9. Calendar Table Conflicts

**Symptom:** Auto-generated calendar table conflicts with existing date dimension.

**Fix:** Use `--no-calendar` to skip calendar table generation. Map date relationships to your existing date dimension manually.

---

## 10. Prompt Conversion Issues

**Symptom:** MSTR prompts don't map cleanly to Power BI slicers or parameters.

**Fix:** Element prompts → slicers, value prompts → What-If parameters, hierarchy prompts → drill-through. Review `prompts.json` for complex prompt types requiring manual setup.

---

## 11. MovingAvg / RunningSum Inaccurate

**Symptom:** WINDOW-based DAX patterns produce different results than MSTR.

**Fix:** Verify the sort column in the generated `ORDERBY` clause matches the MSTR sort order. The `ALLSELECTED()` scope may differ from MSTR's default scope.

---

## 12. ApplyOLAP Not Converted

**Symptom:** ApplyOLAP expressions produce `BLANK()` with manual review comments.

**Fix:** v4.0 handles common patterns (ROW_NUMBER, RANK, LAG, LEAD). Complex SQL window functions still require manual conversion to DAX.

---

## 13. Merge Conflicts Between Projects

**Symptom:** `--merge` reports RED viability with multiple conflicts.

**Fix:** Create a `merge-config.json` with `"conflict_resolution": "keep_all"` to suffix conflicting objects by project name. Or use `"preferred_project"` to pick a winner.

---

## 14. Theme Colors Not Applied

**Symptom:** Generated report uses default Power BI colors instead of MSTR palette.

**Fix:** Open the generated `reportTheme.json` in Power BI Desktop → View → Themes → Browse for themes. The theme file is in the Report/definition/ folder.

---

## 15. Scorecard/Goals Not Appearing

**Symptom:** `--scorecards` flag runs but no goals appear in Fabric.

**Fix:** Goals (Metrics) are a Fabric workspace feature. The tool generates `goals_payload.json` — deploy it via the Power BI REST API or Fabric portal manually.

---

## 16. Derived Metric Circular Reference

**Symptom:** DAX validation error on a measure that references itself.

**Fix:** MSTR allows some circular metric patterns that DAX doesn't. Check `resolve_nested_metrics()` output and break the cycle by inlining one level.

---

## 17. Freeform SQL Tables Missing

**Symptom:** Custom SQL tables from MSTR don't appear in the semantic model.

**Fix:** Ensure `freeform_sql.json` was extracted. The SQL is embedded as a native query M partition — verify the connection supports native queries.

---

## 18. Slow Generation on Large Projects

**Symptom:** Generation takes minutes for projects with 100+ tables.

**Fix:** This is expected for large models. Use `--benchmark` to profile. Consider splitting into smaller projects or using `--shared-model` with thin reports.

---

## 19. Certification Fails

**Symptom:** `--certify` returns FAILED despite visuals looking correct.

**Fix:** The certification checks measure count, relationship coverage, and fidelity ratios. Review `certification.json` for which checks failed. The default threshold is 80%.

---

## 20. Encoding Issues in Column Names

**Symptom:** Special characters in column/table names cause TMDL parse errors.

**Fix:** TMDL auto-quotes names containing spaces or special characters. If issues persist, check for zero-width characters or non-ASCII escaping in source attribute names.

---

## 21. Fabric Lakehouse Table Names Truncated

**Symptom:** Lakehouse table names are shorter than expected or have numeric suffixes.

**Fix:** Fabric Lakehouse tables have a 64-character limit. The `fabric_naming.py` module truncates long names and appends `_2`, `_3` suffixes for collisions. Review `lakehouse_tables.json` for the mapping.

---

## 22. DirectLake Model Shows Empty Tables

**Symptom:** DirectLake semantic model loads but tables show no data.

**Fix:** Ensure the Lakehouse Delta tables exist and contain data. The DirectLake model uses `entityName` partition bindings — verify the entity names match the actual Lakehouse table names. Check the shared expression for correct Lakehouse binding.

---

## 23. Dataflow Gen2 Connector Error

**Symptom:** Dataflow Gen2 fails to refresh with "data source error".

**Fix:** Verify the data source credentials are configured in the Fabric workspace settings. The generated Dataflow uses M connector templates — check that the gateway/credentials for the source database are correctly mapped.

---

## 24. AI-Assisted Conversion Returns BLANK()

**Symptom:** `--ai-assist` enabled but converted expression is still `BLANK()`.

**Fix:** Check Azure OpenAI endpoint and credentials. The AI converter has a token budget (default: 500K) — if exceeded, remaining expressions are skipped. Increase with `--ai-budget`. Also check `ai_cache.json` for previously cached (possibly stale) results.

---

## 25. Multi-Language Culture Files Missing

**Symptom:** `--cultures en-US,fr-FR` runs but only `en-US` appears in the model.

**Fix:** Additional cultures are written to `cultures.tmdl` and `translations.tmdl` in the TMDL definition folder. Open the `.pbip` in Power BI Desktop and check Model → Languages to verify culture files loaded. Ensure culture codes are valid (e.g., `fr-FR` not `FR` or `french`).

---

## 26. RTL Layout Not Applied

**Symptom:** Arabic/Hebrew visuals don't show right-to-left layout.

**Fix:** RTL layout requires Arabic, Hebrew, Farsi, or Urdu in the `--cultures` list. The tool mirrors x-coordinates and sets `textDirection: RTL`. If using a custom layout, manually adjust visual positions.

---

## 27. Change Detection Shows No Changes

**Symptom:** `--watch` reports "no changes detected" even though objects changed.

**Fix:** Ensure `--previous-dir` points to the correct previous extraction output. Change detection compares JSON files byte-by-byte — whitespace-only changes may be ignored. Re-extract both runs with identical settings.

---

## 28. Reconciliation Conflicts

**Symptom:** `--reconcile` flags many conflicts that seem identical.

**Fix:** Three-way reconciliation compares MSTR source (new), PBI target (live), and PBI target (baseline). If the baseline is stale (not from the same migration version), false conflicts appear. Run `--reconcile --dry-run` first to preview without applying changes.

---

## 29. Bundle Deployment Rollback

**Symptom:** `--deploy` with `--shared-model` partially fails and rolls back.

**Fix:** The bundle deployer creates the shared semantic model first, then thin reports. If a report deployment fails, the entire bundle is rolled back. Check the deployment log for the specific error (usually 403 permission or 409 conflict). Verify workspace permissions and that no item with the same name already exists.

---

## 30. DAX Optimizer Changes Breaking Measures

**Symptom:** `--optimize-dax` produces different results than the original DAX.

**Fix:** The optimizer applies semantic-preserving rewrites (IF→SWITCH, ISBLANK→COALESCE, CALCULATE simplification). If results differ, the issue is likely a SWITCH(TRUE(), ...) with overlapping conditions. Run without `--optimize-dax` to verify the original DAX produces correct results, then compare.
