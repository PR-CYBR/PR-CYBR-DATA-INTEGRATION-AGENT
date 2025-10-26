"""Command line interface for the Notion entity synchronisation runner."""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Optional

from .entity_sync import NotionEntitySyncRunner

LOGGER = logging.getLogger(__name__)


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def _load_run_payload(path: Optional[str]) -> Optional[Dict[str, str]]:
    if not path:
        return None
    with open(path, "r", encoding="utf-8") as file_pointer:
        payload = json.load(file_pointer)
    return {str(key): str(value) for key, value in payload.items() if value is not None}


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Synchronise GitHub entities with Notion")
    parser.add_argument("--entity", choices=["tasks", "pull_requests", "issues", "projects", "runs"], required=True)
    parser.add_argument("--database-id", required=True, help="Target Notion database identifier")
    parser.add_argument("--github-token", help="GitHub access token")
    parser.add_argument("--notion-token", help="Notion integration token")
    parser.add_argument("--repository", help="GitHub repository in <owner>/<repo> form")
    parser.add_argument("--task-labels", default="task,Task", help="Comma-separated list of labels considered tasks")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing changes to Notion")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging output")
    parser.add_argument("--run-payload", help="Path to a JSON document describing the workflow run")

    args = parser.parse_args(argv)

    _configure_logging(args.verbose)

    notion_token = args.notion_token or os.environ.get("NOTION_TOKEN")
    if not notion_token:
        LOGGER.error("NOTION_TOKEN must be provided via flag or environment")
        return 1

    github_token = args.github_token or os.environ.get("GITHUB_TOKEN")
    repository = args.repository or os.environ.get("GITHUB_REPOSITORY")

    if args.entity != "runs" and not github_token:
        LOGGER.error("GITHUB_TOKEN must be provided for %s synchronisation", args.entity)
        return 1

    if args.entity != "runs" and not repository:
        LOGGER.error("GITHUB_REPOSITORY environment variable is required when repository is not provided")
        return 1

    task_labels = [label.strip() for label in (args.task_labels.split(",") if args.task_labels else []) if label.strip()]

    runner = NotionEntitySyncRunner(
        entity=args.entity,
        notion_token=notion_token,
        database_id=args.database_id,
        github_token=github_token,
        repository=repository,
        task_labels=task_labels,
    )

    run_payload = _load_run_payload(args.run_payload)
    if args.entity == "runs" and run_payload is None:
        workflow = os.environ.get("GITHUB_WORKFLOW")
        run_id = os.environ.get("GITHUB_RUN_ID")
        run_number = os.environ.get("GITHUB_RUN_NUMBER")
        run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT")
        repository_slug = repository or os.environ.get("GITHUB_REPOSITORY") or ""
        server_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
        workflow_url = None
        if run_id and repository_slug:
            workflow_url = f"{server_url}/{repository_slug}/actions/runs/{run_id}"
        run_payload = {
            "workflow": workflow or "Workflow",
            "run_id": run_id or "",
            "conclusion": os.environ.get("WORKFLOW_CONCLUSION", "unknown"),
            "status": os.environ.get("WORKFLOW_STATUS", "completed"),
            "event": os.environ.get("GITHUB_EVENT_NAME", "unknown"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "repository": repository_slug,
            "url": workflow_url,
            "run_number": run_number or "",
            "run_attempt": run_attempt or "",
            "actor": os.environ.get("GITHUB_ACTOR", ""),
        }

    summary = runner.run(dry_run=args.dry_run, run_payload=run_payload)
    LOGGER.info(
        "Synchronisation complete: processed=%s succeeded=%s failed=%s",
        summary.processed,
        summary.succeeded,
        summary.failed,
    )

    if summary.failed:
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
