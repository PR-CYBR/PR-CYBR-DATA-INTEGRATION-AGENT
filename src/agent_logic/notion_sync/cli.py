"""Command line entry-point for the Notion synchronisation utility."""
from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Optional

from .client import GitHubClient, NotionApi, NotionSyncClient, SyncSummary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Synchronise GitHub repositories with a Notion database")
    parser.add_argument("--database-id", required=True, help="Target Notion database identifier")
    parser.add_argument("--github-org", help="GitHub organisation to pull repositories from")
    parser.add_argument("--repo-id-property", default="Repository ID", help="Notion property that stores repo IDs")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing changes to Notion")
    parser.add_argument("--log-level", default="INFO", help="Logging level (default: INFO)")
    return parser


def _build_sync_client(args: argparse.Namespace) -> NotionSyncClient:
    notion_token = os.environ.get("NOTION_TOKEN")
    if not notion_token:
        raise SystemExit("NOTION_TOKEN environment variable must be set")

    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        raise SystemExit("GITHUB_TOKEN environment variable must be set")

    notion_api = NotionApi(notion_token)
    github_client = GitHubClient(github_token, org=args.github_org)
    return NotionSyncClient(
        notion_api,
        github_client,
        database_id=args.database_id,
        repo_id_property=args.repo_id_property,
    )


def _run_sync(client: NotionSyncClient, *, dry_run: bool) -> SyncSummary:
    summary = client.sync_repositories(dry_run=dry_run)
    return summary


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    logger = logging.getLogger("notion_sync")
    logger.debug("Starting Notion synchronisation")

    try:
        client = _build_sync_client(args)
    except SystemExit as exc:
        logger.error(str(exc))
        return int(exc.code or 1)

    summary = _run_sync(client, dry_run=args.dry_run)

    if summary.failed:
        logger.error(
            "Synchronisation completed with %s failures out of %s repositories", summary.failed, summary.processed
        )
        return 1

    logger.info(
        "Synchronisation completed successfully for %s repositories", summary.succeeded
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
