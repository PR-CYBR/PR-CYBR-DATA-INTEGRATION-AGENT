"""Command line interface for GitHub ⇆ Notion synchronisation."""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Iterable, List, Mapping

from .client import GitHubApiError, GitHubClient, NotionApi, NotionApiError
from .entity_sync import (
    EntitySyncSummary,
    NotionDatabaseSyncer,
    build_issue_content,
    build_milestone_content,
    build_pull_request_content,
    build_run_content,
    build_task_content,
    fetch_milestones,
    fetch_pull_requests,
    fetch_repository_issues,
    fetch_task_issues,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Synchronise GitHub artefacts with Notion databases")
    parser.add_argument("command", choices=["tasks", "pull-requests", "issues", "projects", "runs"], help="Entity to sync")
    parser.add_argument("--database-id", required=True, help="Target Notion database identifier")
    parser.add_argument("--unique-property", default="GitHub ID", help="Notion property used as the unique key")
    parser.add_argument("--repository", help="GitHub repository in owner/name format")
    parser.add_argument("--task-label", default="task", help="Label used to identify GitHub task issues")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing to Notion")
    parser.add_argument("--log-level", default="INFO", help="Logging level (default: INFO)")
    parser.add_argument(
        "--event-path",
        help="Path to the GitHub Actions event payload (for workflow run sync)",
    )
    return parser


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Environment variable {name!r} must be configured")
    return value


def _build_clients() -> tuple[NotionApi, GitHubClient]:
    notion_token = _require_env("NOTION_TOKEN")
    github_token = _require_env("GITHUB_TOKEN")
    return NotionApi(notion_token), GitHubClient(github_token)


def _resolve_repository(args: argparse.Namespace) -> str:
    repository = args.repository or os.environ.get("GITHUB_REPOSITORY")
    if not repository:
        raise RuntimeError("GitHub repository must be provided via --repository or GITHUB_REPOSITORY")
    return repository


def _sync_with_summary(
    syncer: NotionDatabaseSyncer,
    contents: Iterable[Mapping[str, object]],
    builder,
    *,
    dry_run: bool,
) -> EntitySyncSummary:
    pages = [builder(item) for item in contents]
    return syncer.sync(pages, dry_run=dry_run)


def _load_workflow_run(event_path: str) -> Mapping[str, object]:
    with open(event_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if "workflow_run" not in payload:
        raise RuntimeError("Event payload does not contain workflow_run data")
    run = payload["workflow_run"]
    if "workflow" in payload and isinstance(payload["workflow"], Mapping):
        run.setdefault("workflow_name", payload["workflow"].get("name"))
    return run


def main(argv: List[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    logger = logging.getLogger("notion-entity-sync")

    try:
        notion_api, github_client = _build_clients()
    except RuntimeError as exc:
        logger.error(str(exc))
        return 1

    syncer = NotionDatabaseSyncer(
        notion_api,
        database_id=args.database_id,
        unique_property=args.unique_property,
        logger=logger,
    )

    try:
        if args.command == "tasks":
            repository = _resolve_repository(args)
            issues = fetch_task_issues(github_client, repository, label=args.task_label)
            summary = _sync_with_summary(syncer, issues, build_task_content, dry_run=args.dry_run)
        elif args.command == "issues":
            repository = _resolve_repository(args)
            issues = fetch_repository_issues(github_client, repository)
            summary = _sync_with_summary(syncer, issues, build_issue_content, dry_run=args.dry_run)
        elif args.command == "pull-requests":
            repository = _resolve_repository(args)
            pull_requests = fetch_pull_requests(github_client, repository)
            summary = _sync_with_summary(syncer, pull_requests, build_pull_request_content, dry_run=args.dry_run)
        elif args.command == "projects":
            repository = _resolve_repository(args)
            milestones = fetch_milestones(github_client, repository)
            summary = _sync_with_summary(syncer, milestones, build_milestone_content, dry_run=args.dry_run)
        elif args.command == "runs":
            event_path = args.event_path or os.environ.get("GITHUB_EVENT_PATH")
            if not event_path:
                raise RuntimeError("workflow_run payload path must be provided via --event-path or GITHUB_EVENT_PATH")
            run = _load_workflow_run(event_path)
            summary = syncer.sync([build_run_content(run)], dry_run=args.dry_run)
        else:  # pragma: no cover - defensive
            parser.error(f"Unknown command: {args.command}")
            return 2
    except (RuntimeError, GitHubApiError, NotionApiError) as exc:
        logger.error("Failed to complete synchronisation: %s", exc)
        return 1

    logger.info(
        "Processed %s records (%s created, %s updated, %s skipped)",
        summary.processed,
        summary.created,
        summary.updated,
        summary.skipped,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
