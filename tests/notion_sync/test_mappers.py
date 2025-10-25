from datetime import datetime

import pytest

from agent_logic.notion_sync import mappers


@pytest.fixture
def repository_payload():
    return {
        "id": 42,
        "name": "demo",
        "full_name": "pr-cybr/demo",
        "html_url": "https://github.com/pr-cybr/demo",
        "topics": ["automation", "integration"],
        "description": "Sample repository",
        "pushed_at": datetime(2024, 4, 1, 12, 30, 0),
    }


def test_build_page_payload(repository_payload):
    payload = mappers.build_page_payload(
        repository_payload,
        database_id="abc123",
        repo_id_property="Repository ID",
    )

    assert payload["parent"] == {"database_id": "abc123"}
    props = payload["properties"]
    assert props["Name"]["title"][0]["text"]["content"] == "demo"
    assert props["Repository ID"]["rich_text"][0]["text"]["content"] == "42"
    assert props["Repository"]["url"] == "https://github.com/pr-cybr/demo"
    assert props["Description"]["rich_text"][0]["text"]["content"] == "Sample repository"
    assert props["Last Push"]["date"]["start"] == "2024-04-01T12:30:00"
    topic_names = {topic["name"] for topic in props["Topics"]["multi_select"]}
    assert topic_names == {"automation", "integration"}


def test_build_page_payload_handles_missing_optionals(repository_payload):
    repository_payload.update({
        "topics": [],
        "description": None,
        "html_url": None,
        "pushed_at": None,
    })

    payload = mappers.build_page_payload(
        repository_payload,
        database_id="abc123",
        repo_id_property="Repo",
    )

    props = payload["properties"]
    assert "Topics" not in props
    assert "Last Push" not in props
    assert props["Repo"]["rich_text"][0]["text"]["content"] == "42"
    assert props["Repository"]["url"] is None
    assert props["Description"]["rich_text"][0]["text"]["content"] == ""
