import logging
import os
from contextlib import asynccontextmanager
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path

from fastapi import FastAPI

from harvester.config import HarvesterConfig, load_config, ConfigLoadError

logger = logging.getLogger(__name__)

_config: HarvesterConfig | None = None

_QUEUE_SUBDIRS = ("pending", "completed", "failed", "rejected")


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

    # Create operational directories so the server can run even on a fresh checkout.
    # Queue module (F01-S03) will own this logic long-term.
    queue_root = Path(_config.settings.queue_path)
    for subdir in _QUEUE_SUBDIRS:
        (queue_root / subdir).mkdir(parents=True, exist_ok=True)
    Path(_config.settings.findings_log_path).mkdir(parents=True, exist_ok=True)
    Path(_config.settings.run_logs_path).mkdir(parents=True, exist_ok=True)

    logger.info("Harvester ready on port %s", _config.settings.webhook_port)
    yield

    _config = None


try:
    _version = version("harvester")
except PackageNotFoundError:
    _version = "dev"

app = FastAPI(title="Harvester", version=_version, lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "version": _version}
