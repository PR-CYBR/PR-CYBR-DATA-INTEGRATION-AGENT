"""Utility helpers for the Notion synchronisation workflow."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Optional

import logging

import structlog


def configure_logger() -> structlog.BoundLogger:
    """Configure and return a structlog logger instance.

    The configuration is idempotent and safe to call multiple times. It
    produces JSON logs that are easy to ingest by log aggregation platforms.
    """
    if not structlog.is_configured():
        log_level_name = os.environ.get("NOTION_SYNC_LOG_LEVEL", "INFO").upper()
        log_level = getattr(logging, log_level_name, logging.INFO)
        logging.basicConfig(level=log_level)
        structlog.configure(
            processors=[
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.add_log_level,
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            cache_logger_on_first_use=True,
        )
    return structlog.get_logger("notion_sync")


def load_github_event_payload(event_path: Optional[str]) -> Dict[str, Any]:
    """Load and parse the GitHub event payload file.

    Args:
        event_path: Optional path to the GitHub event payload JSON file. When
            ``None`` the ``GITHUB_EVENT_PATH`` environment variable is used.

    Returns:
        Parsed JSON payload as a dictionary.

    Raises:
        FileNotFoundError: If the event payload file cannot be located.
        json.JSONDecodeError: If the event payload cannot be parsed.
    """
    if not event_path:
        event_path = os.environ.get("GITHUB_EVENT_PATH")

    if not event_path:
        raise FileNotFoundError(
            "GitHub event payload path was not provided. Set the --event-path "
            "argument or the GITHUB_EVENT_PATH environment variable."
        )

    path = Path(event_path)
    if not path.exists():
        raise FileNotFoundError(f"GitHub event payload not found at: {path}")

    with path.open("r", encoding="utf-8") as file_obj:
        return json.load(file_obj)


def resolve_event_name(explicit_event_name: Optional[str] = None) -> str:
    """Resolve the GitHub event name from the CLI or the environment."""
    event_name = explicit_event_name or os.environ.get("GITHUB_EVENT_NAME")
    if not event_name:
        raise RuntimeError(
            "GitHub event name is required. Provide --event-name or set "
            "GITHUB_EVENT_NAME in the environment."
        )
    return event_name


def ensure_database_id(explicit_database_id: Optional[str] = None) -> str:
    """Resolve the target Notion database identifier."""
    database_id = explicit_database_id or os.environ.get("NOTION_DATABASE_ID")
    if not database_id:
        raise RuntimeError(
            "A Notion database ID is required. Provide --database-id or set "
            "NOTION_DATABASE_ID in the environment."
        )
    return database_id


def ensure_api_token(explicit_token: Optional[str] = None) -> str:
    """Resolve the Notion API token required for authentication."""
    token = explicit_token or os.environ.get("NOTION_API_TOKEN")
    if not token:
        raise RuntimeError(
            "A Notion integration token is required. Provide --api-token or "
            "set NOTION_API_TOKEN in the environment."
        )
    return token
