"""Unit tests for the workflow-driven Notion synchronisation helpers."""

from agent_logic.notion_sync import workflow_sync


def test_build_property_value_for_multi_select() -> None:
    payload = workflow_sync.build_property_value("multi_select", ["bug", "triage"])
    assert payload == {
        "multi_select": [
            {"name": "bug"},
            {"name": "triage"},
        ]
    }


def test_map_run_status_prefers_conclusion() -> None:
    assert workflow_sync.map_run_status("success", "completed") == "Success"
    assert workflow_sync.map_run_status("failure", "completed") == "Failure"


def test_build_task_items_infers_status_from_issue_state() -> None:
    issues = [
        {
            "id": 1,
            "number": 42,
            "title": "Investigate incident",
            "state": "open",
            "labels": [{"name": "task"}],
            "html_url": "https://example.test/issues/42",
            "body": "Document mitigation steps",
        },
        {
            "id": 2,
            "number": 43,
            "title": "Patch dependency",
            "state": "closed",
            "labels": [],
            "html_url": "https://example.test/issues/43",
            "body": "Patched in release 1.2.3",
        },
    ]

    items = workflow_sync.build_task_items(issues)

    assert len(items) == 2
    assert items[0].identifier == "task-1"
    assert items[0].status == "Open"
    assert items[1].status == "Completed"
