"""Translation utilities converting GitHub events into Notion page payloads."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional


@dataclass
class PageOperation:
    """Representation of a Notion page upsert operation."""

    database_id: str
    properties: Dict[str, Any]
    github_id: Optional[str]
    page_id: Optional[str] = None
    children: Optional[List[Dict[str, Any]]] = None


def _title_property(value: str) -> Dict[str, Any]:
    return {"title": [{"type": "text", "text": {"content": value[:2000]}}]}


def _rich_text_property(value: str) -> Dict[str, Any]:
    return {"rich_text": [{"type": "text", "text": {"content": value[:2000]}}]}


def _url_property(value: Optional[str]) -> Dict[str, Any]:
    return {"url": value or None}


def _date_property(dt: datetime) -> Dict[str, Any]:
    return {"date": {"start": dt.isoformat()}}


def _multi_line_children(body: Optional[str]) -> Optional[List[Dict[str, Any]]]:
    if not body:
        return None
    paragraphs = []
    for line in body.splitlines():
        if not line.strip():
            paragraphs.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": []}})
            continue
        paragraphs.append(
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": line[:2000]},
                        }
                    ]
                },
            }
        )
    return paragraphs or None


def _base_properties(database_id: str, github_id: str, name: str, resource_type: str, url: Optional[str], state: Optional[str]) -> PageOperation:
    now = datetime.now(timezone.utc)
    properties = {
        "Name": _title_property(name),
        "GitHub ID": _rich_text_property(github_id),
        "Type": _rich_text_property(resource_type),
        "Last Synced": _date_property(now),
    }
    if state:
        properties["State"] = _rich_text_property(state)
    if url:
        properties["GitHub URL"] = _url_property(url)
    return PageOperation(database_id=database_id, properties=properties, github_id=github_id)


def map_issue_event(payload: Dict[str, Any], database_id: str) -> PageOperation:
    issue = payload["issue"]
    github_id = issue.get("node_id") or str(issue.get("id"))
    name = f"Issue #{issue['number']}: {issue['title']}"
    operation = _base_properties(
        database_id=database_id,
        github_id=github_id,
        name=name,
        resource_type="Issue",
        url=issue.get("html_url"),
        state=issue.get("state"),
    )
    body_children = _multi_line_children(issue.get("body"))
    if body_children:
        operation.children = body_children
    if payload.get("notion_page_id"):
        operation.page_id = payload["notion_page_id"]
    elif issue.get("notion_page_id"):
        operation.page_id = issue["notion_page_id"]
    if issue.get("user", {}).get("login"):
        operation.properties["Author"] = _rich_text_property(issue["user"]["login"])
    return operation


def map_pull_request_event(payload: Dict[str, Any], database_id: str) -> PageOperation:
    pull_request = payload["pull_request"]
    github_id = pull_request.get("node_id") or str(pull_request.get("id"))
    name = f"PR #{pull_request['number']}: {pull_request['title']}"
    operation = _base_properties(
        database_id=database_id,
        github_id=github_id,
        name=name,
        resource_type="Pull Request",
        url=pull_request.get("html_url"),
        state=pull_request.get("state"),
    )
    body_children = _multi_line_children(pull_request.get("body"))
    if body_children:
        operation.children = body_children
    if payload.get("notion_page_id"):
        operation.page_id = payload["notion_page_id"]
    elif pull_request.get("notion_page_id"):
        operation.page_id = pull_request["notion_page_id"]
    if pull_request.get("user", {}).get("login"):
        operation.properties["Author"] = _rich_text_property(pull_request["user"]["login"])
    if pull_request.get("base", {}).get("ref"):
        operation.properties["Base Branch"] = _rich_text_property(pull_request["base"]["ref"])
    if pull_request.get("head", {}).get("ref"):
        operation.properties["Head Branch"] = _rich_text_property(pull_request["head"]["ref"])
    return operation


def map_discussion_event(payload: Dict[str, Any], database_id: str) -> PageOperation:
    discussion = payload["discussion"]
    github_id = discussion.get("node_id") or str(discussion.get("id"))
    name = f"Discussion: {discussion['title']}"
    operation = _base_properties(
        database_id=database_id,
        github_id=github_id,
        name=name,
        resource_type="Discussion",
        url=discussion.get("html_url"),
        state=discussion.get("state"),
    )
    body_children = _multi_line_children(discussion.get("body"))
    if body_children:
        operation.children = body_children
    if payload.get("notion_page_id"):
        operation.page_id = payload["notion_page_id"]
    elif discussion.get("notion_page_id"):
        operation.page_id = discussion["notion_page_id"]
    if discussion.get("category", {}).get("name"):
        operation.properties["Category"] = _rich_text_property(discussion["category"]["name"])
    return operation


def map_project_item_event(payload: Dict[str, Any], database_id: str) -> PageOperation:
    project_item = payload.get("project_item") or payload.get("projects_v2_item") or {}
    github_id = project_item.get("node_id") or str(project_item.get("id", payload.get("id", "unknown")))
    title = project_item.get("title") or project_item.get("content", {}).get("title") or "Project Item"
    operation = _base_properties(
        database_id=database_id,
        github_id=github_id,
        name=title,
        resource_type="Project Item",
        url=project_item.get("url") or project_item.get("html_url"),
        state=project_item.get("status") or project_item.get("state"),
    )
    if payload.get("notion_page_id"):
        operation.page_id = payload["notion_page_id"]
    if project_item.get("assignee"):
        assignee = project_item["assignee"].get("login") or project_item["assignee"].get("name")
        if assignee:
            operation.properties["Assignee"] = _rich_text_property(assignee)
    summary = project_item.get("content", {}).get("body") or project_item.get("summary")
    body_children = _multi_line_children(summary)
    if body_children:
        operation.children = body_children
    return operation


def map_workflow_run_event(payload: Dict[str, Any], database_id: str) -> PageOperation:
    workflow_run = payload["workflow_run"]
    github_id = workflow_run.get("node_id") or str(workflow_run.get("id"))
    name = f"Workflow: {workflow_run['name']}"
    operation = _base_properties(
        database_id=database_id,
        github_id=github_id,
        name=name,
        resource_type="Workflow Run",
        url=workflow_run.get("html_url"),
        state=workflow_run.get("conclusion") or workflow_run.get("status"),
    )
    if payload.get("notion_page_id"):
        operation.page_id = payload["notion_page_id"]
    summary = workflow_run.get("display_title") or workflow_run.get("head_branch")
    if summary:
        operation.properties["Summary"] = _rich_text_property(summary)
    return operation


_EVENT_MAPPERS: Dict[str, Callable[[Dict[str, Any], str], PageOperation]] = {
    "issues": map_issue_event,
    "pull_request": map_pull_request_event,
    "pull_request_target": map_pull_request_event,
    "pull_request_review": map_pull_request_event,
    "discussion": map_discussion_event,
    "discussion_comment": map_discussion_event,
    "projects_v2_item": map_project_item_event,
    "project": map_project_item_event,
    "workflow_run": map_workflow_run_event,
}


def map_event_to_page(event_name: str, payload: Dict[str, Any], database_id: str) -> PageOperation:
    """Return the :class:`PageOperation` for the given GitHub event."""
    try:
        mapper = _EVENT_MAPPERS[event_name]
    except KeyError as exc:  # pragma: no cover - defensive branch
        raise ValueError(f"Unsupported GitHub event: {event_name}") from exc
    return mapper(payload, database_id)


__all__ = [
    "PageOperation",
    "map_event_to_page",
]
