import logging
import os
import sys
from pathlib import Path

import click
import uvicorn

from harvester.config import ConfigLoadError, load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)


@click.group()
def cli() -> None:
    pass


@cli.command()
@click.option("--config", default="harvester-config.yaml", show_default=True)
@click.option("--host", default="0.0.0.0", show_default=True)
@click.option("--port", default=None, type=int, help="Override webhook_port from config")
def serve(config: str, host: str, port: int | None) -> None:
    try:
        cfg = load_config(config)
    except ConfigLoadError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)

    os.environ["HARVESTER_CONFIG"] = config
    uvicorn.run(
        "harvester.main:app",
        host=host,
        port=port or cfg.settings.webhook_port,
        log_level="info",
    )


@cli.command()
@click.option("--config", default="harvester-config.yaml", show_default=True)
def validate(config: str) -> None:
    try:
        cfg = load_config(config)
    except ConfigLoadError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)

    click.echo(f"Config OK — {len(cfg.repos)} repo(s) configured:")
    for repo in cfg.repos:
        scanners = ", ".join(s.name for s in repo.scanners)
        click.echo(f"  {repo.name} ({repo.github})  scanners: {scanners}")


@cli.command()
@click.argument("repo")
@click.argument("scanner_name")
@click.option("--config", default="harvester-config.yaml", show_default=True)
def scan(repo: str, scanner_name: str, config: str) -> None:
    click.echo(f"scan {repo} {scanner_name} — not yet implemented (F01-S04)", err=True)
    sys.exit(1)


@cli.group()
def queue() -> None:
    pass


@queue.command("list")
@click.option("--config", default="harvester-config.yaml", show_default=True)
def queue_list(config: str) -> None:
    from harvester.queue import list_queue

    try:
        cfg = load_config(config)
    except ConfigLoadError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)

    queue_root = Path(cfg.settings.queue_path)
    status = list_queue(queue_root)
    for subdir, info in status.items():
        click.echo(f"  {subdir:<12} {info['count']:>4} item(s)")
        for name in info["items"]:
            click.echo(f"    {name}")


@queue.command("clear")
@click.argument("subdir", type=click.Choice(["pending", "failed"]))
@click.option("--config", default="harvester-config.yaml", show_default=True)
def queue_clear(subdir: str, config: str) -> None:
    click.echo(f"queue clear {subdir} — not yet implemented (F01-S03)", err=True)
    sys.exit(1)


if __name__ == "__main__":
    cli()
