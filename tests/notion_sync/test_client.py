import logging
from typing import Dict, List

import pytest

from agent_logic.notion_sync.client import GitHubApiError, NotionApiError, NotionSyncClient


class DummyNotionAPI:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.created: List[Dict[str, object]] = []
        self.updated: List[Dict[str, object]] = []
        self.queries: List[Dict[str, object]] = []
        self.pages = {}

    def query_database(self, database_id: str, filter_body: Dict[str, object]):
        self.queries.append({"database_id": database_id, "filter": filter_body})
        repo_id = filter_body["rich_text"]["equals"]
        if repo_id in self.pages:
            return {"results": [{"id": self.pages[repo_id]}]}
        return {"results": []}

    def create_page(self, payload: Dict[str, object]):
        if self.should_fail:
            raise NotionApiError("create failed")
        new_id = f"page-{len(self.created) + 1}"
        repo_id = payload["properties"]["Repository ID"]["rich_text"][0]["text"]["content"]
        self.pages[repo_id] = new_id
        self.created.append(payload)
        return {"id": new_id}

    def update_page(self, page_id: str, properties: Dict[str, object]):
        if self.should_fail:
            raise NotionApiError("update failed")
        self.updated.append({"page_id": page_id, "properties": properties})


class DummyGitHubClient:
    def __init__(self, repositories: List[Dict[str, object]], *, should_fail: bool = False) -> None:
        self.repositories = repositories
        self.should_fail = should_fail

    def list_repositories(self):
        if self.should_fail:
            raise GitHubApiError("boom")
        return self.repositories


@pytest.fixture
def repositories():
    return [
        {
            "id": 1,
            "name": "first",
            "full_name": "org/first",
            "html_url": "https://github.com/org/first",
            "description": "First repository",
            "topics": ["alpha"],
        },
        {
            "id": 2,
            "name": "second",
            "full_name": "org/second",
            "html_url": "https://github.com/org/second",
            "description": "Second repository",
            "topics": ["beta"],
        },
    ]


def test_sync_repositories_success(repositories):
    notion = DummyNotionAPI()
    github = DummyGitHubClient(repositories)
    client = NotionSyncClient(notion, github, database_id="db1")

    summary = client.sync_repositories()

    assert summary.processed == 2
    assert summary.failed == 0
    assert len(notion.created) == 2
    assert client.repo_page_map == {"1": "page-1", "2": "page-2"}


def test_sync_repositories_updates_existing(repositories):
    notion = DummyNotionAPI()
    notion.pages["1"] = "existing-page"
    github = DummyGitHubClient(repositories)
    cache = {"1": "existing-page"}
    client = NotionSyncClient(notion, github, database_id="db1", repo_page_map=cache)

    summary = client.sync_repositories()

    assert summary.failed == 0
    assert notion.updated[0]["page_id"] == "existing-page"
    assert client.repo_page_map["1"] == "existing-page"


def test_sync_repositories_dry_run_skips_writes(repositories, caplog):
    notion = DummyNotionAPI()
    github = DummyGitHubClient(repositories)
    client = NotionSyncClient(notion, github, database_id="db1")

    with caplog.at_level(logging.INFO):
        summary = client.sync_repositories(dry_run=True)

    assert summary.succeeded == 2
    assert not notion.created
    assert "Dry run enabled" in caplog.text


def test_sync_repositories_handles_notion_errors(repositories, caplog):
    notion = DummyNotionAPI(should_fail=True)
    github = DummyGitHubClient(repositories)
    client = NotionSyncClient(notion, github, database_id="db1")

    with caplog.at_level(logging.ERROR):
        summary = client.sync_repositories()

    assert summary.failed == 2
    assert "Notion sync failed" in caplog.text
    assert len(summary.errors) == 2


def test_sync_repositories_handles_github_errors(caplog):
    notion = DummyNotionAPI()
    github = DummyGitHubClient([], should_fail=True)
    client = NotionSyncClient(notion, github, database_id="db1")

    with caplog.at_level(logging.ERROR):
        summary = client.sync_repositories()

    assert summary.failed == 1
    assert summary.processed == 1
    assert "Failed to list repositories" in caplog.text
