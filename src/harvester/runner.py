import logging
import re
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter

from harvester.queue import queue_counts

logger = logging.getLogger(__name__)

router = APIRouter()

_RUN_LOG_PATTERN = re.compile(r"^run-(\d{8}-\d{6})\.log$")


def _parse_run_timestamp(filename: str) -> datetime | None:
    m = _RUN_LOG_PATTERN.match(filename)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d-%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        return None


def _last_run_summary(log_dir: Path) -> dict:
    if not log_dir.is_dir():
        return {"last_run": None, "outcome": None, "log_file": None}

    log_files = [
        (f, ts)
        for f in log_dir.glob("run-*.log")
        if (ts := _parse_run_timestamp(f.name)) is not None
    ]

    if not log_files:
        return {"last_run": None, "outcome": None, "log_file": None}

    log_files.sort(key=lambda x: x[1], reverse=True)
    latest_file, latest_ts = log_files[0]

    # Scan last 50 lines for the run summary
    try:
        lines = latest_file.read_text(errors="replace").splitlines()
        tail = lines[-50:]
        succeeded = 0
        failed = 0
        for line in tail:
            if "Succeeded:" in line:
                try:
                    succeeded = int(line.split(":")[-1].strip())
                except ValueError:
                    pass
            if "Failed:" in line:
                try:
                    failed = int(line.split(":")[-1].strip())
                except ValueError:
                    pass
        outcome = f"{succeeded} succeeded, {failed} failed"
    except Exception:
        outcome = "unknown"

    return {
        "last_run": latest_ts.isoformat(),
        "outcome": outcome,
        "log_file": str(latest_file),
    }


@router.get("/api/queue")
async def queue_status():
    """Queue counts across all four directories."""
    from harvester.main import _config

    if _config is None:
        return {"error": "Config not loaded"}

    queue_path = Path(_config.settings.queue_path)
    return {
        "queue": queue_counts(queue_path),
        "checked_at": datetime.now(UTC).isoformat(),
    }


@router.get("/api/runner/status")
async def runner_status():
    """Queue depth and last run outcome for the launchd health check."""
    from harvester.main import _config

    if _config is None:
        return {"error": "Config not loaded"}

    queue_path = Path(_config.settings.queue_path)
    log_dir = Path(_config.settings.run_logs_path)

    return {
        "queue": queue_counts(queue_path),
        "last_run": _last_run_summary(log_dir),
        "checked_at": datetime.now(UTC).isoformat(),
    }
