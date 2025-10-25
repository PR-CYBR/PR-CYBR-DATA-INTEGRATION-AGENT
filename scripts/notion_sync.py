"""Command line entrypoint for synchronising GitHub events with Notion."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Treat this module as a package so that ``python -m scripts.notion_sync`` can
# co-exist with the supporting modules living under ``scripts/notion_sync``.
_PACKAGE_DIR = Path(__file__).with_name("notion_sync")
if _PACKAGE_DIR.exists():
    __path__ = [str(_PACKAGE_DIR)]  # type: ignore[name-defined]
    if __spec__ is not None:  # pragma: no cover - attribute absent in some tooling
        __spec__.submodule_search_locations = __path__  # type: ignore[attr-defined]

from scripts.notion_sync.client import NotionSyncClient
from scripts.notion_sync.mappers import map_event_to_page
from scripts.notion_sync.utils import (
    configure_logger,
    ensure_api_token,
    ensure_database_id,
    load_github_event_payload,
    resolve_event_name,
)


def _parse_arguments(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Synchronise GitHub events into Notion")
    parser.add_argument("--event-name", help="GitHub event name", default=None)
    parser.add_argument("--event-path", help="Path to the GitHub event payload", default=None)
    parser.add_argument("--database-id", help="Target Notion database identifier", default=None)
    parser.add_argument("--api-token", help="Notion integration token", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_arguments(argv or sys.argv[1:])
    logger = configure_logger()

    try:
        event_name = resolve_event_name(args.event_name)
        event_payload = load_github_event_payload(args.event_path)
        database_id = ensure_database_id(args.database_id)
        api_token = ensure_api_token(args.api_token)
    except Exception as error:  # pragma: no cover - CLI error handling
        logger.error("notion_sync_configuration_error", error=str(error))
        return 1

    try:
        operation = map_event_to_page(event_name, event_payload, database_id)
    except Exception as error:
        logger.error("notion_sync_mapping_error", event_name=event_name, error=str(error))
        return 1

    client = NotionSyncClient(token=api_token, logger=logger)

    try:
        response = client.upsert(operation)
    except Exception as error:
        logger.error(
            "notion_sync_upsert_failed",
            error=str(error),
            github_id=operation.github_id,
        )
        return 1

    notion_page_id = response.get("id") if isinstance(response, dict) else None
    logger.info(
        "notion_sync_complete",
        event_name=event_name,
        github_id=operation.github_id,
        notion_page_id=notion_page_id,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
