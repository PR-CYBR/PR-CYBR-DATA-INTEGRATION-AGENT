"""Helpers for synchronising GitHub entities with Notion databases."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence

from .client import GitHubClient, NotionApi

LOGGER = logging.getLogger(__name__)


@dataclass
class PageContent:
    """Represents the Notion properties required to sync a single entity."""

    key: str
    properties: Dict[str, object]


@dataclass
class EntitySyncSummary:
    """Summarises the outcome of a synchronisation run."""

    processed: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    dry_run: bool = False

    def record_created(self) -> None:
        self.processed += 1
        self.created += 1

    def record_updated(self) -> None:
        self.processed += 1
        self.updated += 1

    def record_skipped(self) -> None:
        self.processed += 1
        self.skipped += 1


class NotionDatabaseSyncer:
    """Synchronises a collection of :class:`PageContent` entries to Notion."""

    def __init__(
        self,
        notion_api: NotionApi,
        *,
        database_id: str,
        unique_property: str = "GitHub ID",
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._notion = notion_api
        self._database_id = database_id
        self._unique_property = unique_property
        self._logger = logger or LOGGER

    # ------------------------------------------------------------------
    def sync(self, contents: Iterable[PageContent], *, dry_run: bool = False) -> EntitySyncSummary:
        summary = EntitySyncSummary(dry_run=dry_run)
        page_map = self._build_page_index()

        for content in contents:
            page_id = page_map.get(content.key)
            if dry_run:
                self._logger.info("Dry-run mode active; skipping sync for %s", content.key)
                summary.record_skipped()
                continue

            if page_id:
                self._notion.update_page(page_id, content.properties)
                self._logger.debug("Updated Notion page %s", page_id)
                summary.record_updated()
            else:
                payload = {
                    "parent": {"database_id": self._database_id},
                    "properties": content.properties,
                }
                self._notion.create_page(payload)
                self._logger.debug("Created Notion page for %s", content.key)
                summary.record_created()

        return summary

    # ------------------------------------------------------------------
    def _build_page_index(self) -> MutableMapping[str, str]:
        index: MutableMapping[str, str] = {}
        for page in self._notion.list_database_pages(self._database_id):
            key = self._extract_property_value(page.get("properties", {}))
            if key:
                index[key] = page.get("id", "")
        return index

    def _extract_property_value(self, properties: Mapping[str, object]) -> Optional[str]:
        property_value = properties.get(self._unique_property)
        if not isinstance(property_value, Mapping):
            return None

        prop_type = property_value.get("type")
        if prop_type == "rich_text":
            return _collect_plain_text(property_value.get("rich_text", [])) or None
        if prop_type == "title":
            return _collect_plain_text(property_value.get("title", [])) or None
        if prop_type == "number":
            number = property_value.get("number")
            return str(int(number)) if isinstance(number, (int, float)) else None
        if prop_type in {"status", "select"}:
            option = property_value.get(prop_type) or {}
            name = option.get("name")
            return name if name else None

        return None


# ---------------------------------------------------------------------------
# Property helpers


def _collect_plain_text(blocks: Sequence[Mapping[str, object]]) -> str:
    text = []
    for block in blocks:
        if isinstance(block, Mapping):
            text.append(str(block.get("plain_text") or block.get("text", {}).get("content", "")))
    return "".join(text).strip()


def _title(text: str) -> Dict[str, object]:
    return {
        "title": [
            {
                "text": {
                    "content": text[:2000],
                }
            }
        ]
    }


def _rich_text(content: str) -> Dict[str, object]:
    return {
        "rich_text": [
            {
                "text": {
                    "content": content[:2000],
                }
            }
        ]
    }


def _multi_select(values: Iterable[str]) -> Dict[str, object]:
    options = [{"name": value[:100]} for value in values if value]
    return {"multi_select": options}


def _status(name: Optional[str]) -> Dict[str, object]:
    if not name:
        return {"status": None}
    return {"status": {"name": name[:100]}}


def _select(name: Optional[str]) -> Dict[str, object]:
    if not name:
        return {"select": None}
    return {"select": {"name": name[:100]}}


def _date(value: Optional[str]) -> Dict[str, object]:
    if not value:
        return {"date": None}
    return {"date": {"start": value}}


def _number(value: Optional[int]) -> Dict[str, object]:
    if value is None:
        return {"number": None}
    return {"number": value}


def _normalise_state(state: Optional[str]) -> str:
    if not state:
        return "Unknown"
    return state.replace("_", " ").strip().title()


def _to_iso8601(value: Optional[object]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    if isinstance(value, str):
        return value
    return str(value)


# ---------------------------------------------------------------------------
# Builders for individual GitHub entities


def build_task_content(issue: Mapping[str, object]) -> PageContent:
    key = str(issue.get("node_id") or issue.get("id") or issue.get("number"))
    title = str(issue.get("title") or f"Task {issue.get('number')}")
    url = issue.get("html_url")
    state = _normalise_state("closed" if issue.get("closed_at") else issue.get("state"))
    labels = [label.get("name") for label in issue.get("labels", []) if isinstance(label, Mapping)]
    assignees = [user.get("login") for user in issue.get("assignees", []) if isinstance(user, Mapping)]
    closed_at = _to_iso8601(issue.get("closed_at"))

    properties: Dict[str, object] = {
        "Name": _title(title),
        "GitHub ID": _rich_text(key),
        "GitHub URL": {"url": url},
        "Status": _status("Closed" if closed_at else "Open"),
        "Labels": _multi_select(labels),
        "Assignees": _multi_select(assignees),
        "GitHub Number": _number(issue.get("number") if isinstance(issue.get("number"), int) else None),
        "Completed At": _date(closed_at),
        "Updated At": _date(_to_iso8601(issue.get("updated_at"))),
    }

    return PageContent(key=key, properties=properties)


def build_issue_content(issue: Mapping[str, object]) -> PageContent:
    key = str(issue.get("node_id") or issue.get("id") or issue.get("number"))
    title = str(issue.get("title") or f"Issue {issue.get('number')}")
    url = issue.get("html_url")
    state = _normalise_state(issue.get("state"))
    labels = [label.get("name") for label in issue.get("labels", []) if isinstance(label, Mapping)]
    assignees = [user.get("login") for user in issue.get("assignees", []) if isinstance(user, Mapping)]

    properties: Dict[str, object] = {
        "Name": _title(title),
        "GitHub ID": _rich_text(key),
        "GitHub URL": {"url": url},
        "Status": _status(state),
        "Labels": _multi_select(labels),
        "Assignees": _multi_select(assignees),
        "GitHub Number": _number(issue.get("number") if isinstance(issue.get("number"), int) else None),
        "Updated At": _date(_to_iso8601(issue.get("updated_at"))),
        "Closed At": _date(_to_iso8601(issue.get("closed_at"))),
    }

    return PageContent(key=key, properties=properties)


def build_pull_request_content(pr: Mapping[str, object]) -> PageContent:
    key = str(pr.get("node_id") or pr.get("id") or pr.get("number"))
    title = str(pr.get("title") or f"PR {pr.get('number')}")
    url = pr.get("html_url")
    state = "Merged" if pr.get("merged_at") else _normalise_state(pr.get("state"))
    labels = [label.get("name") for label in pr.get("labels", []) if isinstance(label, Mapping)]
    assignees = [user.get("login") for user in pr.get("assignees", []) if isinstance(user, Mapping)]
    author = pr.get("user") or {}

    properties: Dict[str, object] = {
        "Name": _title(title),
        "GitHub ID": _rich_text(key),
        "GitHub URL": {"url": url},
        "Status": _status(state),
        "Labels": _multi_select(labels),
        "Assignees": _multi_select(assignees),
        "Author": _multi_select([author.get("login")] if isinstance(author, Mapping) else []),
        "GitHub Number": _number(pr.get("number") if isinstance(pr.get("number"), int) else None),
        "Merged At": _date(_to_iso8601(pr.get("merged_at"))),
        "Updated At": _date(_to_iso8601(pr.get("updated_at"))),
    }

    return PageContent(key=key, properties=properties)


def build_milestone_content(milestone: Mapping[str, object]) -> PageContent:
    key = str(milestone.get("node_id") or milestone.get("id") or milestone.get("number"))
    title = str(milestone.get("title") or f"Milestone {milestone.get('number')}")
    url = milestone.get("html_url")
    state = _normalise_state(milestone.get("state"))

    properties: Dict[str, object] = {
        "Name": _title(title),
        "GitHub ID": _rich_text(key),
        "GitHub URL": {"url": url},
        "Status": _status(state),
        "GitHub Number": _number(milestone.get("number") if isinstance(milestone.get("number"), int) else None),
        "Due Date": _date(_to_iso8601(milestone.get("due_on"))),
        "Open Issues": _number(milestone.get("open_issues") if isinstance(milestone.get("open_issues"), int) else None),
        "Closed Issues": _number(milestone.get("closed_issues") if isinstance(milestone.get("closed_issues"), int) else None),
    }

    description = milestone.get("description")
    if description:
        properties["Description"] = _rich_text(str(description))

    return PageContent(key=key, properties=properties)


def build_run_content(run: Mapping[str, object]) -> PageContent:
    key = str(run.get("id") or run.get("run_id") or run.get("run_number"))
    workflow_name = str(run.get("name") or run.get("workflow_name") or "Workflow")
    url = run.get("html_url")
    status = _normalise_state(run.get("status"))
    conclusion = run.get("conclusion")

    properties: Dict[str, object] = {
        "Name": _title(f"{workflow_name} #{run.get('run_number')}") if run.get("run_number") else _title(workflow_name),
        "GitHub ID": _rich_text(key),
        "GitHub URL": {"url": url},
        "Status": _status(status),
        "Result": _select(_normalise_state(conclusion) if conclusion else None),
        "Run Number": _number(run.get("run_number") if isinstance(run.get("run_number"), int) else None),
        "Workflow": _rich_text(workflow_name),
        "Started At": _date(_to_iso8601(run.get("run_started_at"))),
        "Completed At": _date(_to_iso8601(run.get("updated_at"))),
    }

    return PageContent(key=key, properties=properties)


def filter_github_issues(issues: Iterable[Mapping[str, object]]) -> List[Mapping[str, object]]:
    """Return issues that are not pull requests."""

    return [issue for issue in issues if "pull_request" not in issue]


def fetch_task_issues(client: GitHubClient, repository: str, *, label: Optional[str]) -> List[Mapping[str, object]]:
    issues = list(client.list_repository_issues(repository, state="all", labels=label)) if label else list(
        client.list_repository_issues(repository, state="all")
    )
    return filter_github_issues(issues)


def fetch_repository_issues(client: GitHubClient, repository: str) -> List[Mapping[str, object]]:
    return filter_github_issues(client.list_repository_issues(repository, state="all"))


def fetch_pull_requests(client: GitHubClient, repository: str) -> List[Mapping[str, object]]:
    return list(client.list_pull_requests(repository, state="all"))


def fetch_milestones(client: GitHubClient, repository: str) -> List[Mapping[str, object]]:
    return list(client.list_milestones(repository, state="all"))
