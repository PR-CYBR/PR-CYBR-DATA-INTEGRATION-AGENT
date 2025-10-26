"""Command line entry point for synchronising GitHub entities with Notion."""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Iterable, List, Optional, Sequence

from .client import NotionApi, SyncSummary
from .entities import (
    EntitySyncEngine,
    GitHubDataFetcher,
    build_issue_records,
    build_pr_records,
    build_project_records,
    build_run_records,
    build_task_records,
)


LOGGER = logging.getLogger("notion_entity_sync")


def _get_token(env_var: str) -> str:
    value = os.environ.get(env_var)
    if not value:
        raise SystemExit(f"{env_var} environment variable must be set")
    return value


def _parse_labels(value: Optional[str]) -> Optional[List[str]]:
    if not value:
        return None
    return [label.strip() for label in value.split(",") if label.strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Synchronise GitHub data with Notion")
    parser.add_argument(
        "entity",
        choices=["tasks", "pull_requests", "issues", "projects", "runs"],
        help="Entity type to synchronise",
    )
    parser.add_argument("--database-id", required=True, help="Target Notion database identifier")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"), help="GitHub repository (owner/name)")
    parser.add_argument("--task-labels", help="Comma separated labels to treat as tasks")
    parser.add_argument("--unique-property", default="GitHub ID", help="Notion property used as unique identifier")
    parser.add_argument("--dry-run", action="store_true", help="Log actions without writing to Notion")
    parser.add_argument(
        "--event-path",
        default=os.environ.get("GITHUB_EVENT_PATH"),
        help="Path to GitHub event payload (used for workflow_run events)",
    )
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    return parser


def _load_event_payload(path: Optional[str]) -> dict:
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _sync_records(
    engine: EntitySyncEngine,
    records: Iterable,
    *,
    dry_run: bool,
) -> SyncSummary:
    return engine.sync(records, dry_run=dry_run)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    notion_token = _get_token("NOTION_TOKEN")
    github_token = _get_token("GITHUB_TOKEN")

    notion_api = NotionApi(notion_token)

    engine = EntitySyncEngine(
        notion_api,
        database_id=args.database_id,
        unique_property=args.unique_property,
        logger=LOGGER,
    )

    dry_run = args.dry_run
    summary: SyncSummary

    if args.entity == "runs":
        payload = _load_event_payload(args.event_path)
        records = build_run_records(payload)
        summary = _sync_records(engine, records, dry_run=dry_run)
        return 0 if not summary.failed else 1

    repository = args.repo
    if not repository:
        LOGGER.error("--repo must be provided or GITHUB_REPOSITORY must be set")
        return 1

    fetcher = GitHubDataFetcher(github_token, repository=repository, logger=LOGGER)

    if args.entity == "tasks":
        task_labels = _parse_labels(args.task_labels)
        issues = fetcher.fetch_task_issues(labels=task_labels)
        records = build_task_records(issues)
    elif args.entity == "pull_requests":
        pull_requests = fetcher.fetch_pull_requests()
        records = build_pr_records(pull_requests)
    elif args.entity == "issues":
        issues = fetcher.fetch_issues()
        records = build_issue_records(issues)
    elif args.entity == "projects":
        milestones = fetcher.fetch_milestones()
        projects = fetcher.fetch_projects()
        records = build_project_records(milestones, projects)
    else:  # pragma: no cover - defensive programming
        parser.error(f"Unsupported entity: {args.entity}")
        return 2

    summary = _sync_records(engine, records, dry_run=dry_run)
    if summary.failed:
        LOGGER.error(
            "Synchronisation completed with %s failures out of %s records",
            summary.failed,
            summary.processed,
        )
        return 1

    LOGGER.info(
        "Synchronisation completed successfully for %s records",
        summary.succeeded,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())

