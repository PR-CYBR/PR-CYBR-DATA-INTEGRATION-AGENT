"""Command line entry point for executing granular Notion synchronisation jobs."""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Any, Dict

from .jobs import MissingConfiguration, NotionClient, execute_job


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Synchronise GitHub artefacts into Notion")
    parser.add_argument(
        "job",
        choices=("tasks", "pull_requests", "issues", "projects", "runs"),
        help="Specific Notion synchronisation job to execute",
    )
    parser.add_argument(
        "--database-id",
        help="Notion database identifier; falls back to environment variables if omitted",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log payloads without performing API writes",
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("NOTION_SYNC_LOG_LEVEL", "INFO"),
        help="Logging level (default: INFO)",
    )
    return parser


def _resolve_database_id(job: str, override: str | None) -> str | None:
    if override:
        return override

    fallback_map = {
        "tasks": "NOTION_TASK_DB_ID",
        "pull_requests": "NOTION_PR_DB_ID",
        "issues": "NOTION_ISSUES_DB_ID",
        "projects": "NOTION_PROJECTS_DB_ID",
        "runs": "NOTION_RUNS_BOARD_ID",
    }
    env_var = fallback_map[job]
    return os.environ.get(env_var) or os.environ.get(env_var.replace("NOTION_", "A_"))


def _build_notion_client(*, dry_run: bool) -> NotionClient:
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        logging.getLogger(__name__).warning("NOTION_TOKEN is not available; forcing dry-run mode")
    return NotionClient(token, dry_run=dry_run or not token)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    _configure_logging(args.log_level)
    logger = logging.getLogger("notion-sync-jobs")

    database_id = _resolve_database_id(args.job, args.database_id)
    notion_client = _build_notion_client(dry_run=args.dry_run)

    try:
        summary: Dict[str, Any] = execute_job(args.job, notion_client=notion_client, database_id=database_id)
    except MissingConfiguration as exc:
        logger.error(str(exc))
        return 1
    except Exception:  # pragma: no cover - defensive guard for workflow stability
        logger.exception("Unexpected error executing Notion sync job")
        return 1

    logger.info("Job summary: %s", json.dumps(summary))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
