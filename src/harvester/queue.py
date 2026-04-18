import json
import logging
import os
from pathlib import Path

from harvester.config import RepoConfig
from harvester.models import QueueItem

logger = logging.getLogger(__name__)

SUBDIRS = ("pending", "completed", "failed", "rejected")


class QueueRefusedError(Exception):
    pass


def init_queue(queue_path: Path) -> None:
    for subdir in SUBDIRS:
        (queue_path / subdir).mkdir(parents=True, exist_ok=True)


def enqueue(item: QueueItem, queue_path: Path, repo_config: RepoConfig) -> Path:
    if item.touches_guarded_paths and repo_config.guarded_path_policy == "never_execute":
        msg = (
            f"Enqueue refused: {item.repo_name}#{item.issue_number} touches guarded paths "
            f"and policy is never_execute"
        )
        logger.warning(msg)
        raise QueueRefusedError(msg)

    filename = f"{item.repo_name}-{item.issue_number}.json"
    dest = queue_path / "pending" / filename
    tmp = dest.with_suffix(".tmp")

    tmp.write_text(json.dumps(item.to_dict(), indent=2))
    os.replace(tmp, dest)

    item.item_path = str(dest)
    logger.info("Enqueued %s → %s", filename, dest)
    return dest


def load_pending(queue_path: Path) -> list[QueueItem]:
    pending_dir = queue_path / "pending"
    items = []
    for p in sorted(pending_dir.glob("*.json"), key=lambda f: f.stat().st_mtime):
        try:
            data = json.loads(p.read_text())
            items.append(QueueItem.from_dict(data, item_path=str(p)))
        except Exception as exc:
            logger.warning("Skipping malformed queue item %s: %s", p.name, exc)
    return items


def move_to(item_path: str, destination: str, queue_path: Path) -> Path:
    src = Path(item_path)
    dest_dir = queue_path / destination
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    os.replace(src, dest)
    logger.info("Queue: %s → %s/", src.name, destination)
    return dest


def list_queue(queue_path: Path) -> dict:
    result: dict = {}
    for subdir in SUBDIRS:
        d = queue_path / subdir
        files = sorted(d.glob("*.json")) if d.exists() else []
        result[subdir] = {
            "count": len(files),
            "items": [f.name for f in files] if subdir == "pending" else [],
        }
    return result
