import asyncio
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


@cli.command()
@click.option("--config", default="harvester-config.yaml", show_default=True)
@click.option("--apply", is_flag=True, default=False, help="Apply drift fixes (move stale pending items to rejected/)")
def reconcile(config: str, apply: bool) -> None:
    import asyncio
    from harvester.reconcile import apply_reconciliation, build_drift_report

    try:
        cfg = load_config(config)
    except ConfigLoadError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)

    report = asyncio.run(build_drift_report(cfg))

    if "error" in report:
        click.echo(f"Error: {report['error']}", err=True)
        sys.exit(1)

    open_not_pending = report["open_not_pending"]
    pending_not_open = report["pending_not_open"]
    click.echo(f"Checked at: {report['checked_at']}")
    click.echo(f"Open+agent-ready on GitHub but not in pending/: {len(open_not_pending)}")
    for item in open_not_pending:
        click.echo(f"  #{item['issue_number']} {item['issue_title']} ({item['repo']})")
    click.echo(f"In pending/ but issue no longer open+agent-ready: {len(pending_not_open)}")
    for item in pending_not_open:
        click.echo(f"  #{item['issue_number']} ({item['repo']}) {item['item_path']}")

    if not open_not_pending and not pending_not_open:
        click.echo("Queue is in sync with GitHub.")
        return

    if apply:
        counts = apply_reconciliation(report, cfg)
        click.echo(f"\nApplied: {counts['moved_to_rejected']} item(s) moved to rejected/")
    else:
        click.echo("\nRun with --apply to resolve pending_not_open drift.")


@queue.command("clear")
@click.argument("subdir", type=click.Choice(["pending", "failed"]))
@click.option("--config", default="harvester-config.yaml", show_default=True)
def queue_clear(subdir: str, config: str) -> None:
    click.echo(f"queue clear {subdir} — not yet implemented (F01-S03)", err=True)
    sys.exit(1)


if __name__ == "__main__":
    cli()
