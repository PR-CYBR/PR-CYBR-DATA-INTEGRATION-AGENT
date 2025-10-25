from types import SimpleNamespace

import pytest

from integrations.github.project_board import (
    build_card_note_with_notion_page,
    build_sync_item_with_status,
    capture_status_from_event,
    map_column_to_status,
)
from integrations.notion.mappers import NotionSyncItem


@pytest.fixture
def sample_status_map():
    return {"Todo": "Backlog", "Doing": "In Progress", "Done": "Complete"}


def test_map_column_to_status_defaults_to_identity(sample_status_map):
    assert map_column_to_status("Doing", sample_status_map) == "In Progress"
    assert map_column_to_status("Review", sample_status_map) == "Review"


def test_capture_status_from_event_reads_column_name(sample_status_map):
    payload = {"project_card": {"column_name": "Doing"}}
    assert capture_status_from_event(payload, sample_status_map) == "In Progress"


def test_build_card_note_with_notion_page_appends_backlink():
    notion_page_id = "1234abcd-5678-ef00-1234-abcdef123456"
    note = build_card_note_with_notion_page(notion_page_id, existing_note="Existing note")

    assert "Existing note" in note
    assert "https://www.notion.so/1234abcd5678ef001234abcdef123456" in note


def test_build_sync_item_with_status_returns_copy():
    item = NotionSyncItem(
        database_slug="issues",
        notion_page_id="page-1",
        title="Demo",
        status="Backlog",
    )
    updated = build_sync_item_with_status(item, "In Progress")

    assert updated.status == "In Progress"
    assert item.status == "Backlog"  # original object is untouched
    assert updated.title == item.title
