"""Unit tests for the GitHub → Notion entity synchronisation helpers."""
from agent_logic.notion_sync import entity_sync


def _rich_text_values(property_payload):
    return [block["text"]["content"] for block in property_payload.get("rich_text", [])]


def test_build_task_item_filters_by_label():
    issue = {
        "id": 1,
        "number": 42,
        "title": "Ship telemetry",
        "state": "open",
        "html_url": "https://github.com/example/repo/issues/42",
        "labels": [{"name": "Task"}],
        "assignees": [{"login": "octocat"}],
    }

    item = entity_sync.build_task_item(issue, label_names=["task"])

    assert item is not None
    assert item.github_id == "1"
    assert item.name == "Ship telemetry"
    assert item.properties["Status"]["select"]["name"] == "Open"
    assert item.properties["URL"]["url"] == issue["html_url"]
    assert _rich_text_values(item.properties["Assignee"]) == ["octocat"]


def test_build_task_item_returns_none_when_label_missing():
    issue = {"id": 2, "labels": [{"name": "bug"}]}

    assert entity_sync.build_task_item(issue, label_names=["task"]) is None


def test_build_issue_item_skips_pull_requests():
    issue = {"id": 3, "pull_request": {}}

    assert entity_sync.build_issue_item(issue) is None


def test_build_pull_request_item_handles_merged_status():
    pr = {
        "id": 99,
        "number": 7,
        "title": "Improve logging",
        "state": "closed",
        "merged_at": "2024-05-01T12:00:00Z",
        "html_url": "https://github.com/example/repo/pull/7",
        "user": {"login": "octocat"},
        "requested_reviewers": [{"login": "reviewer"}],
    }

    item = entity_sync.build_pull_request_item(pr)

    assert item.github_id == "99"
    assert item.name == "Improve logging"
    assert item.properties["Status"]["select"]["name"] == "Merged"
    assert _rich_text_values(item.properties["Author"]) == ["octocat"]


def test_build_milestone_item_sets_due_date():
    milestone = {
        "id": 5,
        "number": 1,
        "title": "Q4 Delivery",
        "state": "open",
        "due_on": "2024-12-01T00:00:00Z",
        "html_url": "https://github.com/example/repo/milestone/1",
    }

    item = entity_sync.build_milestone_item(milestone)

    assert item.github_id == "milestone-5"
    assert item.properties["Entity Type"]["select"]["name"] == "Milestone"
    assert item.properties["Due Date"]["date"]["start"] == "2024-12-01T00:00:00Z"


def test_build_run_item_uses_conclusion():
    workflow_run = {
        "id": 17,
        "name": "CI",
        "run_number": 11,
        "conclusion": "success",
        "run_started_at": "2024-04-01T10:00:00Z",
        "html_url": "https://github.com/example/repo/actions/runs/17",
    }

    item = entity_sync.build_run_item(workflow_run)

    assert item.github_id == "17"
    assert item.properties["Conclusion"]["select"]["name"] == "Success"
    assert item.properties["Run Timestamp"]["date"]["start"] == "2024-04-01T10:00:00Z"
