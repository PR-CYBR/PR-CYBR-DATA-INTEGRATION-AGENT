from __future__ import annotations

import json

import pytest
import responses

from agent_logic.notion_sync.entity_sync import (
    NotionDatabaseSyncer,
    PageContent,
    build_pull_request_content,
    build_run_content,
    build_task_content,
)
from agent_logic.notion_sync.client import NotionApi


@pytest.fixture()
def notion_api() -> NotionApi:
    return NotionApi("token")


@responses.activate
def test_sync_creates_new_pages(notion_api: NotionApi) -> None:
    responses.add(
        responses.POST,
        "https://api.notion.com/v1/databases/tasks/query",
        json={"results": [], "has_more": False},
        status=200,
    )
    responses.add(
        responses.POST,
        "https://api.notion.com/v1/pages",
        json={"id": "new-page"},
        status=200,
    )

    syncer = NotionDatabaseSyncer(notion_api, database_id="tasks")
    content = PageContent(key="123", properties={"Name": {"title": [{"text": {"content": "Example"}}]}})

    summary = syncer.sync([content])

    assert summary.created == 1
    assert summary.updated == 0

    assert len(responses.calls) == 2
    payload = json.loads(responses.calls[1].request.body)
    assert payload["parent"]["database_id"] == "tasks"
    assert payload["properties"]["Name"]["title"][0]["text"]["content"] == "Example"


@responses.activate
def test_sync_updates_existing_page(notion_api: NotionApi) -> None:
    responses.add(
        responses.POST,
        "https://api.notion.com/v1/databases/tasks/query",
        json={
            "results": [
                {
                    "id": "page-1",
                    "properties": {
                        "GitHub ID": {
                            "type": "rich_text",
                            "rich_text": [
                                {
                                    "plain_text": "123",
                                }
                            ],
                        }
                    },
                }
            ],
            "has_more": False,
        },
        status=200,
    )
    responses.add(
        responses.PATCH,
        "https://api.notion.com/v1/pages/page-1",
        json={"id": "page-1"},
        status=200,
    )

    syncer = NotionDatabaseSyncer(notion_api, database_id="tasks")
    content = PageContent(key="123", properties={"Name": {"title": [{"text": {"content": "Updated"}}]}})

    summary = syncer.sync([content])

    assert summary.updated == 1
    assert summary.created == 0

    assert len(responses.calls) == 2
    payload = json.loads(responses.calls[1].request.body)
    assert payload["properties"]["Name"]["title"][0]["text"]["content"] == "Updated"


@responses.activate
def test_sync_dry_run_skips_writes(notion_api: NotionApi) -> None:
    responses.add(
        responses.POST,
        "https://api.notion.com/v1/databases/tasks/query",
        json={"results": [], "has_more": False},
        status=200,
    )

    syncer = NotionDatabaseSyncer(notion_api, database_id="tasks")
    content = PageContent(key="123", properties={"Name": {"title": [{"text": {"content": "Example"}}]}})

    summary = syncer.sync([content], dry_run=True)

    assert summary.skipped == 1
    assert summary.created == 0
    assert summary.updated == 0
    assert len(responses.calls) == 1


def test_build_task_content_contains_expected_fields() -> None:
    issue = {
        "id": 42,
        "number": 7,
        "title": "Implement feature",
        "html_url": "https://github.com/org/repo/issues/7",
        "labels": [
            {"name": "task"},
            {"name": "backend"},
        ],
        "assignees": [
            {"login": "octocat"},
        ],
        "updated_at": "2024-01-01T12:00:00Z",
        "closed_at": None,
    }

    content = build_task_content(issue)
    assert content.key == "42"
    assert content.properties["GitHub Number"]["number"] == 7
    assert content.properties["Status"]["status"]["name"] == "Open"
    labels = {item["name"] for item in content.properties["Labels"]["multi_select"]}
    assert labels == {"task", "backend"}


def test_build_pull_request_content_marks_merged() -> None:
    pull_request = {
        "id": 99,
        "number": 10,
        "title": "Add sync workflow",
        "html_url": "https://github.com/org/repo/pull/10",
        "state": "closed",
        "merged_at": "2024-02-02T10:00:00Z",
        "labels": [],
        "assignees": [],
        "user": {"login": "octocat"},
    }

    content = build_pull_request_content(pull_request)
    assert content.properties["Status"]["status"]["name"] == "Merged"
    author = content.properties["Author"]["multi_select"][0]["name"]
    assert author == "octocat"


def test_build_run_content_uses_run_number() -> None:
    run = {
        "id": 1234,
        "name": "CI",
        "run_number": 56,
        "status": "completed",
        "conclusion": "success",
        "html_url": "https://github.com/org/repo/actions/runs/1234",
        "updated_at": "2024-03-03T12:00:00Z",
    }

    content = build_run_content(run)
    assert "CI #56" in content.properties["Name"]["title"][0]["text"]["content"]
    assert content.properties["Result"]["select"]["name"] == "Success"
