"""
Regression tests for bug bash findings.

Covers fixes for confirmed bugs discovered during code audit.
"""

import pytest


class TestRunBenchmarkMethod:
    """Bug #1: run_benchmark was calling non-existent importer.generate()."""

    def test_import_all_exists_on_importer(self):
        from powerbi_import.import_to_powerbi import PowerBIImporter
        importer = PowerBIImporter()
        assert hasattr(importer, 'import_all')

    def test_generate_method_does_not_exist(self):
        from powerbi_import.import_to_powerbi import PowerBIImporter
        importer = PowerBIImporter()
        assert not hasattr(importer, 'generate'), \
            "generate() should not exist — run_benchmark must use import_all()"

    def test_run_benchmark_source_uses_import_all(self):
        """Verify run_benchmark calls import_all, not generate."""
        import inspect
        from migrate import run_benchmark
        source = inspect.getsource(run_benchmark)
        assert 'import_all' in source
        assert 'importer.generate(' not in source


class TestBatchGenerationCultures:
    """Bug #6: Batch generation was missing cultures for reports."""

    def test_batch_report_generation_has_cultures_kwarg(self):
        """Verify run_batch_generation passes cultures to report generate_pbip."""
        import inspect
        from migrate import run_batch_generation
        source = inspect.getsource(run_batch_generation)
        # Count occurrences of cultures=batch_cultures — should appear twice
        # (once for reports, once for dossiers)
        count = source.count('cultures=batch_cultures')
        assert count >= 2, (
            f"Expected cultures=batch_cultures at least twice (reports + dossiers), "
            f"found {count}"
        )


class TestBatchGenerationCulturesParam:
    """Bug #6 extended: batch_cultures should be constructed from args."""

    def test_batch_cultures_initialized(self):
        """Verify batch_cultures variable is constructed in run_batch_generation."""
        import inspect
        from migrate import run_batch_generation
        source = inspect.getsource(run_batch_generation)
        assert 'batch_cultures' in source


class TestComparisonReportWiring:
    """Bug #5: Comparison report was getting empty stats dict."""

    def test_comparison_report_handles_empty_stats(self):
        """generate_comparison_report must not crash with empty stats."""
        import os
        import tempfile
        from powerbi_import.comparison_report import generate_comparison_report
        data = {
            "datasources": [{"name": "T1", "columns": [{"name": "C1"}]}],
            "metrics": [{"name": "M1", "dax_expression": "SUM(T1[C1])"}],
            "reports": [],
            "dossiers": [],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            result = generate_comparison_report(data, {}, tmpdir)
            assert "summary" in result
            assert os.path.isfile(os.path.join(tmpdir, "comparison_report.json"))
            assert os.path.isfile(os.path.join(tmpdir, "comparison_report.html"))


class TestCLIPlaceholderFlags:
    """Verify placeholder CLI flags exist but are documented as unimplemented."""

    def test_incremental_flag_exists(self):
        from migrate import build_parser
        parser = build_parser()
        args = parser.parse_args(['--incremental'])
        assert args.incremental is True

    def test_parallel_flag_exists(self):
        from migrate import build_parser
        parser = build_parser()
        args = parser.parse_args(['--parallel', '4'])
        assert args.parallel == 4

    def test_folder_flag_exists(self):
        from migrate import build_parser
        parser = build_parser()
        args = parser.parse_args(['--folder', '/some/path'])
        assert args.folder == '/some/path'


class TestImportAllSignature:
    """Verify import_all accepts all documented parameters without error."""

    def test_import_all_accepts_cultures(self):
        """cultures parameter added in v8.0 must be accepted."""
        import inspect
        from powerbi_import.import_to_powerbi import PowerBIImporter
        sig = inspect.signature(PowerBIImporter.import_all)
        assert 'cultures' in sig.parameters

    def test_import_all_accepts_culture_singular(self):
        import inspect
        from powerbi_import.import_to_powerbi import PowerBIImporter
        sig = inspect.signature(PowerBIImporter.import_all)
        assert 'culture' in sig.parameters

    def test_import_all_accepts_direct_lake(self):
        import inspect
        from powerbi_import.import_to_powerbi import PowerBIImporter
        sig = inspect.signature(PowerBIImporter.import_all)
        assert 'direct_lake' in sig.parameters


class TestGeneratePbipSignature:
    """Verify generate_pbip accepts all parameters from callers."""

    def test_generate_pbip_accepts_cultures(self):
        import inspect
        from powerbi_import.pbip_generator import generate_pbip
        sig = inspect.signature(generate_pbip)
        assert 'cultures' in sig.parameters

    def test_generate_pbip_accepts_direct_lake(self):
        import inspect
        from powerbi_import.pbip_generator import generate_pbip
        sig = inspect.signature(generate_pbip)
        assert 'direct_lake' in sig.parameters

    def test_generate_pbip_accepts_lakehouse_name(self):
        import inspect
        from powerbi_import.pbip_generator import generate_pbip
        sig = inspect.signature(generate_pbip)
        assert 'lakehouse_name' in sig.parameters


class TestVisualGeneratorSignature:
    """Verify visual generator accepts cultures parameter (v8.0 wiring)."""

    def test_generate_all_visuals_accepts_cultures(self):
        import inspect
        from powerbi_import.visual_generator import generate_all_visuals
        sig = inspect.signature(generate_all_visuals)
        assert 'cultures' in sig.parameters

    def test_generate_all_visuals_cultures_default_none(self):
        import inspect
        from powerbi_import.visual_generator import generate_all_visuals
        sig = inspect.signature(generate_all_visuals)
        assert sig.parameters['cultures'].default is None


class TestRunGenerationSignature:
    """Verify run_generation accepts cultures parameter (v8.0)."""

    def test_run_generation_accepts_cultures(self):
        import inspect
        from migrate import run_generation
        sig = inspect.signature(run_generation)
        assert 'cultures' in sig.parameters
