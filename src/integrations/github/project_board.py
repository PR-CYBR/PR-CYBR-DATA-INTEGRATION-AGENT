"""Helpers for synchronizing GitHub project board events with Notion."""
from __future__ import annotations

import logging
from typing import Any, Dict, Mapping, MutableMapping, Optional

import requests

from ..notion.mappers import NotionSyncItem, build_notion_url

LOGGER = logging.getLogger(__name__)


def extract_column_name(event_payload: Mapping[str, Any]) -> Optional[str]:
    """Extract the project column name from a GitHub webhook payload."""

    project_card = event_payload.get("project_card") or {}
    if "column_name" in project_card:
        return project_card.get("column_name")

    project_column = event_payload.get("project_column") or {}
    return project_column.get("name")


def map_column_to_status(column_name: Optional[str], status_map: Mapping[str, str]) -> Optional[str]:
    """Translate a GitHub project column name into a Notion status value."""

    if column_name is None:
        return None
    if column_name in status_map:
        return status_map[column_name]
    # fall back to identity mapping so that unknown columns are still represented
    return column_name


def capture_status_from_event(event_payload: Mapping[str, Any], status_map: Mapping[str, str]) -> Optional[str]:
    """Convenience wrapper that extracts the column name and maps it to status."""

    column_name = extract_column_name(event_payload)
    return map_column_to_status(column_name, status_map)


def build_card_note_with_notion_page(notion_page_id: str, existing_note: Optional[str] = None) -> str:
    """Return a card note that includes a backlink to the Notion page."""

    notion_url = build_notion_url(notion_page_id)
    backlink_line = f"Notion Page: {notion_url}"
    if existing_note:
        existing_note = existing_note.strip()
        if backlink_line in existing_note:
            return existing_note
        if existing_note:
            return f"{existing_note}\n\n{backlink_line}"
    return backlink_line


def persist_notion_page_id_to_card(
    github_token: str,
    card_id: int,
    notion_page_id: str,
    existing_note: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> bool:
    """Patch the GitHub project card note so that it links back to Notion.

    Returns ``True`` when the GitHub API confirms the update.
    """

    note = build_card_note_with_notion_page(notion_page_id, existing_note)
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
    }
    payload: MutableMapping[str, Any] = {"note": note}
    session = session or requests.Session()
    response = session.patch(
        f"https://api.github.com/projects/columns/cards/{card_id}",
        json=payload,
        headers=headers,
    )
    if response.status_code == 200:
        return True
    LOGGER.warning(
        "Failed to persist Notion backlink to GitHub card %s: %s %s", card_id, response.status_code, response.text
    )
    return False


def build_sync_item_with_status(item: NotionSyncItem, status: Optional[str]) -> NotionSyncItem:
    """Return a copy of ``item`` with the provided status override."""

    if status is None or item.status == status:
        return item
    return NotionSyncItem(
        database_slug=item.database_slug,
        notion_page_id=item.notion_page_id,
        title=item.title,
        status=status,
        assignees=list(item.assignees),
        labels=list(item.labels),
        github_url=item.github_url,
        github_node_id=item.github_node_id,
        github_number=item.github_number,
        relations=dict(item.relations),
    )
