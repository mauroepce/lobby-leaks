"""
Report generation for InfoLobby sync operations.

Generates JSON reports with metrics from fetch, merge, and persistence operations.
Reports are saved to data/info_lobby/reports/ with timestamped filenames.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.info_lobby_sync.merge import MergeResult
from services.info_lobby_sync.persistence import PersistenceResult


# Default reports directory (relative to project root)
DEFAULT_REPORTS_DIR = Path("data/info_lobby/reports")


@dataclass
class FetchMetrics:
    """Metrics from SPARQL fetch operation."""
    audiencias_fetched: int = 0
    viajes_fetched: int = 0
    donativos_fetched: int = 0
    total_fetched: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "audiencias_fetched": self.audiencias_fetched,
            "viajes_fetched": self.viajes_fetched,
            "donativos_fetched": self.donativos_fetched,
            "total_fetched": self.total_fetched,
            "errors": self.errors,
        }


@dataclass
class SyncReport:
    """Complete sync operation report."""
    timestamp: datetime
    tenant_code: str
    status: str  # "ok", "partial", "error", "skipped"
    fetch: Optional[FetchMetrics] = None
    merge: Optional[MergeResult] = None
    persistence: Optional[PersistenceResult] = None
    duration_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "tenant_code": self.tenant_code,
            "status": self.status,
            "fetch": self.fetch.to_dict() if self.fetch else None,
            "merge": {
                "persons_count": len(self.merge.persons) if self.merge else 0,
                "orgs_count": len(self.merge.organisations) if self.merge else 0,
                "duplicates_found": self.merge.duplicates_found if self.merge else 0,
                "merged_count": self.merge.merged_count if self.merge else 0,
                "persons_existing": self.merge.persons_existing if self.merge else 0,
                "persons_new": self.merge.persons_new if self.merge else 0,
                "orgs_existing": self.merge.orgs_existing if self.merge else 0,
                "orgs_new": self.merge.orgs_new if self.merge else 0,
            } if self.merge else None,
            "persistence": self.persistence.to_dict() if self.persistence else None,
            "duration_seconds": self.duration_seconds,
            "errors": self.errors,
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert report to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


def create_report(
    tenant_code: str = "CL",
    fetch_metrics: Optional[FetchMetrics] = None,
    merge_result: Optional[MergeResult] = None,
    persistence_result: Optional[PersistenceResult] = None,
    started_at: Optional[datetime] = None,
    errors: Optional[List[str]] = None,
) -> SyncReport:
    """
    Create a sync report from operation results.

    Args:
        tenant_code: Tenant identifier
        fetch_metrics: Metrics from fetch operation
        merge_result: Result from merge operation
        persistence_result: Result from persistence operation
        started_at: When the sync started (for duration calculation)
        errors: List of errors encountered

    Returns:
        SyncReport instance
    """
    now = datetime.utcnow()
    all_errors = errors or []

    # Collect errors from all stages
    if fetch_metrics and fetch_metrics.errors:
        all_errors.extend(fetch_metrics.errors)
    if persistence_result and persistence_result.errors:
        all_errors.extend(persistence_result.errors)

    # Determine status
    if all_errors:
        if persistence_result and persistence_result.total_processed > 0:
            status = "partial"
        else:
            status = "error"
    elif not fetch_metrics or fetch_metrics.total_fetched == 0:
        status = "skipped"
    else:
        status = "ok"

    # Calculate duration
    duration = 0.0
    if started_at:
        duration = (now - started_at).total_seconds()
    elif persistence_result:
        duration = persistence_result.duration_seconds

    return SyncReport(
        timestamp=now,
        tenant_code=tenant_code,
        status=status,
        fetch=fetch_metrics,
        merge=merge_result,
        persistence=persistence_result,
        duration_seconds=duration,
        errors=all_errors,
    )


def save_report(
    report: SyncReport,
    reports_dir: Optional[Path] = None,
) -> Path:
    """
    Save report to JSON file.

    File is named with timestamp: YYYY-MM-DD_HHmmss.json

    Args:
        report: SyncReport to save
        reports_dir: Directory for reports (default: data/info_lobby/reports/)

    Returns:
        Path to saved report file
    """
    if reports_dir is None:
        reports_dir = DEFAULT_REPORTS_DIR

    # Ensure directory exists
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename with timestamp
    timestamp_str = report.timestamp.strftime("%Y-%m-%d_%H%M%S")
    filename = f"{timestamp_str}.json"
    filepath = reports_dir / filename

    # Write report
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report.to_json())

    return filepath


def load_report(filepath: Path) -> SyncReport:
    """
    Load a report from JSON file.

    Args:
        filepath: Path to report file

    Returns:
        SyncReport instance (partially reconstructed)
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Reconstruct fetch metrics
    fetch = None
    if data.get("fetch"):
        fetch = FetchMetrics(
            audiencias_fetched=data["fetch"].get("audiencias_fetched", 0),
            viajes_fetched=data["fetch"].get("viajes_fetched", 0),
            donativos_fetched=data["fetch"].get("donativos_fetched", 0),
            total_fetched=data["fetch"].get("total_fetched", 0),
            errors=data["fetch"].get("errors", []),
        )

    # Reconstruct persistence result
    persistence = None
    if data.get("persistence"):
        p = data["persistence"]
        persistence = PersistenceResult(
            persons_inserted=p.get("persons_inserted", 0),
            persons_updated=p.get("persons_updated", 0),
            persons_unchanged=p.get("persons_unchanged", 0),
            orgs_inserted=p.get("orgs_inserted", 0),
            orgs_updated=p.get("orgs_updated", 0),
            orgs_unchanged=p.get("orgs_unchanged", 0),
            total_processed=p.get("total_processed", 0),
            errors=p.get("errors", []),
        )

    return SyncReport(
        timestamp=datetime.fromisoformat(data["timestamp"]),
        tenant_code=data["tenant_code"],
        status=data["status"],
        fetch=fetch,
        merge=None,  # Cannot fully reconstruct MergeResult from JSON
        persistence=persistence,
        duration_seconds=data.get("duration_seconds", 0.0),
        errors=data.get("errors", []),
    )


def get_latest_report(reports_dir: Optional[Path] = None) -> Optional[SyncReport]:
    """
    Get the most recent report from the reports directory.

    Args:
        reports_dir: Directory containing reports

    Returns:
        Latest SyncReport or None if no reports exist
    """
    if reports_dir is None:
        reports_dir = DEFAULT_REPORTS_DIR

    if not reports_dir.exists():
        return None

    # Find all JSON files
    report_files = sorted(reports_dir.glob("*.json"), reverse=True)

    if not report_files:
        return None

    return load_report(report_files[0])


def list_reports(
    reports_dir: Optional[Path] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    List recent reports with summary info.

    Args:
        reports_dir: Directory containing reports
        limit: Maximum number of reports to return

    Returns:
        List of report summaries (timestamp, status, counts)
    """
    if reports_dir is None:
        reports_dir = DEFAULT_REPORTS_DIR

    if not reports_dir.exists():
        return []

    report_files = sorted(reports_dir.glob("*.json"), reverse=True)[:limit]
    summaries = []

    for filepath in report_files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            persistence = data.get("persistence") or {}
            summaries.append({
                "filename": filepath.name,
                "timestamp": data.get("timestamp"),
                "status": data.get("status"),
                "total_processed": persistence.get("total_processed", 0),
                "errors_count": len(data.get("errors", [])),
            })
        except Exception:
            continue

    return summaries
