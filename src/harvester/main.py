import asyncio
import logging
import os
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from fastapi import FastAPI

from harvester.config import ConfigLoadError, HarvesterConfig, load_config
from harvester.github_client import GitHubClient
from harvester.queue import init_queue
from harvester.scheduler import run_scheduler
from harvester.webhook import router as webhook_router

logger = logging.getLogger(__name__)

_config: HarvesterConfig | None = None


def get_config() -> HarvesterConfig:
    if _config is None:
        raise RuntimeError("Config not loaded — server not started via lifespan")
    return _config


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _config

    config_path = os.environ.get("HARVESTER_CONFIG", "harvester-config.yaml")
    try:
        _config = load_config(config_path)
    except ConfigLoadError as exc:
        logger.error("Startup aborted: %s", exc)
        raise

    # Ensure operational directories exist.
    queue_root = Path(_config.settings.queue_path)
    init_queue(queue_root)
    Path(_config.settings.findings_log_path).mkdir(parents=True, exist_ok=True)
    Path(_config.settings.run_logs_path).mkdir(parents=True, exist_ok=True)

    # Ensure GitHub label taxonomy exists on every configured repo.
    github_token = os.environ.get("GITHUB_TOKEN", "")
    if github_token:
        for repo_cfg in _config.repos:
            try:
                client = GitHubClient(token=github_token, repo_full_name=repo_cfg.github)
                await client.ensure_labels_exist()
                logger.info("Labels verified for %s", repo_cfg.github)
            except Exception as exc:
                logger.warning("Label sync failed for %s: %s", repo_cfg.github, exc)
    else:
        logger.warning("GITHUB_TOKEN not set — skipping label sync")

    # Start scheduler as a background task.
    scheduler_task = asyncio.create_task(run_scheduler(_config))

    logger.info("Harvester ready on port %s", _config.settings.webhook_port)
    yield

    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass

    _config = None


try:
    _version = version("harvester")
except PackageNotFoundError:
    _version = "dev"

app = FastAPI(title="Harvester", version=_version, lifespan=lifespan)
app.include_router(webhook_router)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "version": _version}
