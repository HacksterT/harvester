import asyncio
import importlib
import json
import logging
import os
import time
import uuid
from pathlib import Path

from harvester.config import HarvesterConfig
from harvester.models import ScanContext

logger = logging.getLogger(__name__)

SKIP_ALERT_THRESHOLD = 3


# ---------------------------------------------------------------------------
# State file helpers
# ---------------------------------------------------------------------------

def _load_state(state_path: Path) -> dict:
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text())
    except Exception as exc:
        logger.warning("Could not read state file %s: %s — starting fresh", state_path, exc)
        return {}


def _save_state(state_path: Path, state: dict) -> None:
    tmp = state_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    os.replace(tmp, state_path)


def _scanner_state(state: dict, repo_name: str, scanner_name: str) -> dict:
    return state.setdefault(repo_name, {}).setdefault(
        scanner_name, {"last_run": None, "consecutive_skips": 0}
    )


def is_overdue(scanner_state: dict, cadence_days: int) -> bool:
    last_run = scanner_state.get("last_run")
    if last_run is None:
        return True
    return (time.time() - last_run) >= cadence_days * 86400


# ---------------------------------------------------------------------------
# Scanner module loader
# ---------------------------------------------------------------------------

def _load_scanner_module(scanner_name: str) -> object | None:
    module_path = f"harvester.scanners.{scanner_name}"
    try:
        return importlib.import_module(module_path)
    except ImportError:
        logger.warning("Scanner module not found: %s — skipping", module_path)
        return None


# ---------------------------------------------------------------------------
# Main scheduler loop
# ---------------------------------------------------------------------------

async def run_scheduler(config: HarvesterConfig) -> None:
    from harvester import notifier, scanner_runner

    state_path = Path(config.settings.state_path)
    tick = config.settings.scheduler_tick_seconds

    logger.info("Scheduler started — tick every %ds", tick)

    while True:
        await asyncio.sleep(tick)
        logger.info("Scheduler tick — checking for overdue scanners")

        state = _load_state(state_path)

        for repo_cfg in config.repos:
            for scanner_cfg in repo_cfg.scanners:
                s_state = _scanner_state(state, repo_cfg.name, scanner_cfg.name)

                if not is_overdue(s_state, scanner_cfg.cadence_days):
                    logger.debug(
                        "%s/%s not overdue — skipping", repo_cfg.name, scanner_cfg.name
                    )
                    continue

                logger.info("Running scanner: %s/%s", repo_cfg.name, scanner_cfg.name)

                module = _load_scanner_module(scanner_cfg.name)
                context = ScanContext(run_id=str(uuid.uuid4()))
                finding = None

                if module is not None:
                    try:
                        finding = await scanner_runner.run_scanner(module, repo_cfg, context)
                    except Exception as exc:
                        logger.error(
                            "Scanner %s/%s raised an exception: %s",
                            repo_cfg.name, scanner_cfg.name, exc,
                        )

                s_state["last_run"] = time.time()

                if finding is None:
                    s_state["consecutive_skips"] += 1
                    skips = s_state["consecutive_skips"]
                    logger.info(
                        "%s/%s returned no finding (consecutive skips: %d)",
                        repo_cfg.name, scanner_cfg.name, skips,
                    )
                    if skips >= SKIP_ALERT_THRESHOLD:
                        await notifier.send(
                            f"⚠️ Scanner {scanner_cfg.name} on {repo_cfg.name} has returned "
                            f"no findings {skips} times in a row. Consider reviewing the cadence."
                        )
                else:
                    s_state["consecutive_skips"] = 0
                    logger.info(
                        "%s/%s produced finding: %s",
                        repo_cfg.name, scanner_cfg.name, finding.title,
                    )
                    # Finding → GitHub issue + queue enqueue handled by writer (F01-S04).

                _save_state(state_path, state)

        logger.info("Scheduler tick complete")
