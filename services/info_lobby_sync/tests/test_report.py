"""Tests for report module."""

import json
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from ..report import (
    FetchMetrics,
    SyncReport,
    create_report,
    save_report,
    load_report,
    get_latest_report,
    list_reports,
)
from ..merge import MergeResult
from ..persistence import PersistenceResult


class TestFetchMetrics:
    """Tests for FetchMetrics dataclass."""

    def test_default_values(self):
        metrics = FetchMetrics()
        assert metrics.audiencias_fetched == 0
        assert metrics.total_fetched == 0
        assert metrics.errors == []

    def test_to_dict(self):
        metrics = FetchMetrics(
            audiencias_fetched=100,
            viajes_fetched=20,
            donativos_fetched=5,
            total_fetched=125,
            errors=["error1"],
        )

        d = metrics.to_dict()

        assert d["audiencias_fetched"] == 100
        assert d["total_fetched"] == 125
        assert d["errors"] == ["error1"]


class TestSyncReport:
    """Tests for SyncReport dataclass."""

    def test_basic_report(self):
        report = SyncReport(
            timestamp=datetime(2025, 1, 1, 12, 0, 0),
            tenant_code="CL",
            status="ok",
        )

        assert report.tenant_code == "CL"
        assert report.status == "ok"

    def test_to_dict(self):
        fetch = FetchMetrics(total_fetched=100)
        persistence = PersistenceResult(persons_inserted=10)

        report = SyncReport(
            timestamp=datetime(2025, 1, 1, 12, 0, 0),
            tenant_code="CL",
            status="ok",
            fetch=fetch,
            persistence=persistence,
            duration_seconds=5.5,
        )

        d = report.to_dict()

        assert d["tenant_code"] == "CL"
        assert d["status"] == "ok"
        assert d["fetch"]["total_fetched"] == 100
        assert d["persistence"]["persons_inserted"] == 10
        assert d["duration_seconds"] == 5.5

    def test_to_json(self):
        report = SyncReport(
            timestamp=datetime(2025, 1, 1, 12, 0, 0),
            tenant_code="CL",
            status="ok",
        )

        json_str = report.to_json()
        parsed = json.loads(json_str)

        assert parsed["tenant_code"] == "CL"
        assert parsed["status"] == "ok"

    def test_to_dict_with_merge_result(self):
        merge = MergeResult(
            persons=[{"name": "Test"}],
            organisations=[{"name": "Org"}],
            duplicates_found=2,
            merged_count=5,
            persons_existing=1,
            persons_new=3,
            orgs_existing=0,
            orgs_new=1,
        )

        report = SyncReport(
            timestamp=datetime(2025, 1, 1),
            tenant_code="CL",
            status="ok",
            merge=merge,
        )

        d = report.to_dict()

        assert d["merge"]["persons_count"] == 1
        assert d["merge"]["orgs_count"] == 1
        assert d["merge"]["duplicates_found"] == 2
        assert d["merge"]["persons_new"] == 3


class TestCreateReport:
    """Tests for create_report function."""

    def test_create_ok_report(self):
        fetch = FetchMetrics(total_fetched=100)
        persistence = PersistenceResult(persons_inserted=10, total_processed=10)

        report = create_report(
            tenant_code="CL",
            fetch_metrics=fetch,
            persistence_result=persistence,
        )

        assert report.status == "ok"
        assert report.tenant_code == "CL"

    def test_create_error_report(self):
        fetch = FetchMetrics(total_fetched=0, errors=["Fetch failed"])

        report = create_report(
            tenant_code="CL",
            fetch_metrics=fetch,
            errors=["Connection error"],
        )

        assert report.status == "error"
        assert "Fetch failed" in report.errors
        assert "Connection error" in report.errors

    def test_create_partial_report(self):
        fetch = FetchMetrics(total_fetched=100)
        persistence = PersistenceResult(
            persons_inserted=5,
            total_processed=5,
            errors=["Some insert failed"],
        )

        report = create_report(
            fetch_metrics=fetch,
            persistence_result=persistence,
        )

        assert report.status == "partial"

    def test_create_skipped_report(self):
        fetch = FetchMetrics(total_fetched=0)

        report = create_report(fetch_metrics=fetch)

        assert report.status == "skipped"

    def test_duration_calculation(self):
        """Duration should be calculated from persistence result if available."""
        persistence = PersistenceResult(
            started_at=datetime(2025, 1, 1, 10, 0, 0),
            finished_at=datetime(2025, 1, 1, 10, 0, 30),
        )

        report = create_report(
            fetch_metrics=FetchMetrics(total_fetched=1),
            persistence_result=persistence,
        )

        # Duration comes from persistence result
        assert report.duration_seconds == 30.0


class TestSaveLoadReport:
    """Tests for save and load operations."""

    def test_save_report(self):
        with TemporaryDirectory() as tmpdir:
            reports_dir = Path(tmpdir)

            report = SyncReport(
                timestamp=datetime(2025, 1, 15, 14, 30, 0),
                tenant_code="CL",
                status="ok",
            )

            filepath = save_report(report, reports_dir)

            assert filepath.exists()
            assert filepath.name == "2025-01-15_143000.json"

    def test_load_report(self):
        with TemporaryDirectory() as tmpdir:
            reports_dir = Path(tmpdir)

            original = SyncReport(
                timestamp=datetime(2025, 1, 15, 14, 30, 0),
                tenant_code="CL",
                status="ok",
                fetch=FetchMetrics(total_fetched=100),
                persistence=PersistenceResult(persons_inserted=10),
            )

            filepath = save_report(original, reports_dir)
            loaded = load_report(filepath)

            assert loaded.tenant_code == "CL"
            assert loaded.status == "ok"
            assert loaded.fetch.total_fetched == 100
            assert loaded.persistence.persons_inserted == 10

    def test_save_creates_directory(self):
        with TemporaryDirectory() as tmpdir:
            nested_dir = Path(tmpdir) / "nested" / "reports"

            report = SyncReport(
                timestamp=datetime(2025, 1, 1),
                tenant_code="CL",
                status="ok",
            )

            filepath = save_report(report, nested_dir)

            assert filepath.exists()
            assert nested_dir.exists()


class TestGetLatestReport:
    """Tests for get_latest_report function."""

    def test_get_latest_from_empty_dir(self):
        with TemporaryDirectory() as tmpdir:
            result = get_latest_report(Path(tmpdir))
            assert result is None

    def test_get_latest_from_nonexistent_dir(self):
        result = get_latest_report(Path("/nonexistent/path"))
        assert result is None

    def test_get_latest_report(self):
        with TemporaryDirectory() as tmpdir:
            reports_dir = Path(tmpdir)

            # Create older report
            old_report = SyncReport(
                timestamp=datetime(2025, 1, 1, 10, 0, 0),
                tenant_code="CL",
                status="ok",
            )
            save_report(old_report, reports_dir)

            # Create newer report
            new_report = SyncReport(
                timestamp=datetime(2025, 1, 2, 10, 0, 0),
                tenant_code="CL",
                status="partial",
            )
            save_report(new_report, reports_dir)

            latest = get_latest_report(reports_dir)

            assert latest is not None
            assert latest.status == "partial"


class TestListReports:
    """Tests for list_reports function."""

    def test_list_empty_dir(self):
        with TemporaryDirectory() as tmpdir:
            result = list_reports(Path(tmpdir))
            assert result == []

    def test_list_reports_with_limit(self):
        with TemporaryDirectory() as tmpdir:
            reports_dir = Path(tmpdir)

            # Create 5 reports with different timestamps
            for i in range(5):
                report = SyncReport(
                    timestamp=datetime(2025, 1, i + 1, 10, 0, i),  # Different seconds
                    tenant_code="CL",
                    status="ok",
                )
                save_report(report, reports_dir)

            result = list_reports(reports_dir, limit=3)

            assert len(result) == 3
            # Should be sorted by filename descending (newest first)
            assert "2025-01-05" in result[0]["filename"]

    def test_list_reports_summary(self):
        with TemporaryDirectory() as tmpdir:
            reports_dir = Path(tmpdir)

            report = SyncReport(
                timestamp=datetime(2025, 1, 1),
                tenant_code="CL",
                status="error",
                persistence=PersistenceResult(total_processed=5),
                errors=["error1", "error2"],
            )
            save_report(report, reports_dir)

            result = list_reports(reports_dir)

            assert len(result) == 1
            assert result[0]["status"] == "error"
            assert result[0]["total_processed"] == 5
            assert result[0]["errors_count"] == 2
