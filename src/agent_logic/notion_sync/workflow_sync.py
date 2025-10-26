"""Utility CLI to synchronise GitHub artifacts with Notion databases.

The module provides a lightweight, event-aware synchronisation routine that can
run inside GitHub Actions.  Each invocation targets a specific database and
entity type (tasks, pull requests, issues, projects, workflow runs).  The
workflow relies on repository secrets to obtain the Notion database identifiers
as well as a Notion integration token.  GitHub metadata is fetched via the REST
API using the GitHub token provided to the workflow runner.

The implementation favours explicit configuration so that the automation can be
adapted to different Notion database schemas.  Property names and the
corresponding Notion property types can be overridden through CLI options in the
GitHub Actions workflow definitions.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, List, Mapping, MutableMapping, Optional

import requests


LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions


class SyncConfigurationError(RuntimeError):
    """Raised when the synchronisation cannot run due to misconfiguration."""


class NotionSyncError(RuntimeError):
    """Raised when the Notion API returns an error status code."""


class GitHubSyncError(RuntimeError):
    """Raised when the GitHub API returns an error status code."""


# ---------------------------------------------------------------------------
# Helper dataclasses


@dataclass(frozen=True)
class PropertyBinding:
    """Describe how a GitHub field maps to a Notion property."""

    name: str
    type: str

    def is_configured(self) -> bool:
        """Return ``True`` when the property has a usable configuration."""

        return bool(self.name)


@dataclass
class SyncItem:
    """Normalised representation for an entry pushed to Notion."""

    identifier: str
    title: str
    url: Optional[str]
    status: Optional[str]
    labels: Optional[Iterable[str]] = None
    category: Optional[str] = None
    timestamp: Optional[str] = None
    description: Optional[str] = None


# ---------------------------------------------------------------------------
# GitHub client helpers


class GitHubDataSource:
    """Fetch GitHub metadata via the REST API."""

    def __init__(self, token: Optional[str], repository: str) -> None:
        headers = {
            "Accept": "application/vnd.github+json, application/vnd.github.inertia-preview+json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        self._session = requests.Session()
        self._session.headers.update(headers)
        self._repository = repository
        self._base_url = "https://api.github.com"

    # Public API ---------------------------------------------------------
    def fetch_task_issues(self, label_names: Iterable[str]) -> List[Mapping[str, object]]:
        issues = []
        label_names_lower = {label.lower() for label in label_names}
        for issue in self._paginate(self._repo_url("issues"), params={"state": "all", "per_page": 100}):
            if "pull_request" in issue:
                continue
            issue_labels = {str(label.get("name", "")).lower() for label in issue.get("labels", [])}
            if issue_labels & label_names_lower:
                issues.append(issue)
        return issues

    def fetch_issues(self) -> List[Mapping[str, object]]:
        issues = []
        for issue in self._paginate(self._repo_url("issues"), params={"state": "all", "per_page": 100}):
            if "pull_request" in issue:
                continue
            issues.append(issue)
        return issues

    def fetch_pull_requests(self) -> List[Mapping[str, object]]:
        prs = []
        for pr in self._paginate(self._repo_url("pulls"), params={"state": "all", "per_page": 100}):
            prs.append(pr)
        return prs

    def fetch_projects(self) -> List[Mapping[str, object]]:
        projects = []
        for project in self._paginate(self._repo_url("projects"), params={"state": "all", "per_page": 100}):
            projects.append(project)
        return projects

    def fetch_milestones(self) -> List[Mapping[str, object]]:
        milestones = []
        for milestone in self._paginate(
            self._repo_url("milestones"),
            params={"state": "all", "per_page": 100},
        ):
            milestones.append(milestone)
        return milestones

    # Private helpers ---------------------------------------------------
    def _repo_url(self, suffix: str) -> str:
        return f"{self._base_url}/repos/{self._repository}/{suffix}"

    def _paginate(self, url: str, params: Optional[MutableMapping[str, object]] = None) -> Iterator[Mapping[str, object]]:
        while url:
            response = self._session.get(url, params=params, timeout=30)
            params = None
            if response.status_code >= 400:
                raise GitHubSyncError(
                    f"GitHub API request to {url} failed with {response.status_code}: {response.text}"
                )
            payload = response.json()
            if isinstance(payload, dict):
                yield payload
                break
            for item in payload:
                yield item
            url = response.links.get("next", {}).get("url")


# ---------------------------------------------------------------------------
# Notion client helpers


class NotionClient:
    """Minimal wrapper around the Notion REST API."""

    def __init__(self, token: str, *, base_url: str = "https://api.notion.com/v1") -> None:
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json",
            }
        )
        self._base_url = base_url.rstrip("/")

    def upsert_page(
        self,
        database_id: str,
        *,
        identifier: str,
        id_property: PropertyBinding,
        properties: Mapping[str, object],
    ) -> None:
        """Create or update a page based on a unique identifier property."""

        existing_page_id = self._locate_page(database_id, identifier, id_property)
        if existing_page_id:
            self._update_page(existing_page_id, properties)
            return

        payload = {"parent": {"database_id": database_id}, "properties": dict(properties)}
        response = self._session.post(f"{self._base_url}/pages", json=payload, timeout=30)
        if response.status_code >= 400:
            raise NotionSyncError(
                f"Notion page creation failed with {response.status_code}: {response.text}"
            )

    # Internal API ------------------------------------------------------
    def _locate_page(self, database_id: str, identifier: str, property_binding: PropertyBinding) -> Optional[str]:
        filter_payload = build_filter_payload(property_binding.type, property_binding.name, identifier)
        query_body = {"filter": filter_payload}
        response = self._session.post(
            f"{self._base_url}/databases/{database_id}/query",
            json=query_body,
            timeout=30,
        )
        if response.status_code >= 400:
            raise NotionSyncError(
                f"Failed querying Notion database {database_id}: {response.status_code} {response.text}"
            )

        results = response.json().get("results", [])
        if not results:
            return None
        return results[0].get("id")

    def _update_page(self, page_id: str, properties: Mapping[str, object]) -> None:
        response = self._session.patch(
            f"{self._base_url}/pages/{page_id}",
            json={"properties": dict(properties)},
            timeout=30,
        )
        if response.status_code >= 400:
            raise NotionSyncError(
                f"Notion page update failed for {page_id} with {response.status_code}: {response.text}"
            )


# ---------------------------------------------------------------------------
# Property payload helpers


def build_filter_payload(property_type: str, property_name: str, identifier: str) -> Mapping[str, object]:
    """Return a Notion filter payload to locate pages by identifier."""

    if property_type == "rich_text":
        return {"property": property_name, "rich_text": {"equals": identifier}}
    if property_type == "number":
        return {"property": property_name, "number": {"equals": float(identifier)}}
    if property_type == "title":
        return {"property": property_name, "title": {"equals": identifier}}
    if property_type == "url":
        return {"property": property_name, "url": {"equals": identifier}}

    raise SyncConfigurationError(f"Unsupported identifier property type: {property_type}")


def build_property_value(property_type: str, value: object) -> Mapping[str, object]:
    """Convert a Python value into the structure expected by Notion."""

    if property_type == "title":
        return {"title": [{"text": {"content": str(value)[:2000]}}]}
    if property_type == "rich_text":
        return {"rich_text": [{"text": {"content": str(value)[:2000]}}]}
    if property_type == "status":
        return {"status": {"name": str(value)[:100]}}
    if property_type == "select":
        return {"select": {"name": str(value)[:100]}}
    if property_type == "url":
        return {"url": str(value)}
    if property_type == "multi_select":
        if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
            raise SyncConfigurationError("multi_select property expects an iterable of strings")
        return {"multi_select": [{"name": str(item)[:100]} for item in value]}
    if property_type == "date":
        return {"date": {"start": str(value)}}
    if property_type == "number":
        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as exc:  # pragma: no cover - safety net
            raise SyncConfigurationError("number property expects a numeric value") from exc
        return {"number": numeric_value}

    raise SyncConfigurationError(f"Unsupported property type requested: {property_type}")


def build_properties(
    item: SyncItem,
    *,
    title_property: PropertyBinding,
    status_property: Optional[PropertyBinding],
    url_property: Optional[PropertyBinding],
    label_property: Optional[PropertyBinding],
    category_property: Optional[PropertyBinding],
    timestamp_property: Optional[PropertyBinding],
    description_property: Optional[PropertyBinding],
) -> Mapping[str, object]:
    """Construct the dictionary of Notion property payloads for an item."""

    properties: Dict[str, object] = {}

    if title_property.is_configured():
        properties[title_property.name] = build_property_value(title_property.type, item.title)

    if status_property and status_property.is_configured() and item.status is not None:
        properties[status_property.name] = build_property_value(status_property.type, item.status)

    if url_property and url_property.is_configured() and item.url:
        properties[url_property.name] = build_property_value(url_property.type, item.url)

    if label_property and label_property.is_configured() and item.labels:
        properties[label_property.name] = build_property_value(label_property.type, list(item.labels))

    if category_property and category_property.is_configured() and item.category:
        properties[category_property.name] = build_property_value(category_property.type, item.category)

    if timestamp_property and timestamp_property.is_configured() and item.timestamp:
        properties[timestamp_property.name] = build_property_value(timestamp_property.type, item.timestamp)

    if description_property and description_property.is_configured() and item.description:
        properties[description_property.name] = build_property_value(description_property.type, item.description)

    return properties


# ---------------------------------------------------------------------------
# GitHub -> Notion transformations


def build_task_items(issues: Iterable[Mapping[str, object]]) -> List[SyncItem]:
    items: List[SyncItem] = []
    for issue in issues:
        identifier = f"task-{issue['id']}"
        title = f"#{issue['number']} {issue['title']}"
        status = "Completed" if str(issue.get("state")) == "closed" else "Open"
        labels = [label.get("name", "") for label in issue.get("labels", [])]
        items.append(
            SyncItem(
                identifier=identifier,
                title=title,
                url=issue.get("html_url"),
                status=status,
                labels=[label for label in labels if label],
                description=(issue.get("body") or "")[:1900] or None,
            )
        )
    return items


def build_issue_items(issues: Iterable[Mapping[str, object]]) -> List[SyncItem]:
    items: List[SyncItem] = []
    for issue in issues:
        identifier = f"issue-{issue['id']}"
        status = "Closed" if str(issue.get("state")) == "closed" else "Open"
        labels = [label.get("name", "") for label in issue.get("labels", [])]
        items.append(
            SyncItem(
                identifier=identifier,
                title=f"#{issue['number']} {issue['title']}",
                url=issue.get("html_url"),
                status=status,
                labels=[label for label in labels if label],
                description=(issue.get("body") or "")[:1900] or None,
            )
        )
    return items


def build_pull_request_items(pull_requests: Iterable[Mapping[str, object]]) -> List[SyncItem]:
    items: List[SyncItem] = []
    for pr in pull_requests:
        identifier = f"pr-{pr['id']}"
        if pr.get("merged_at"):
            status = "Merged"
        elif str(pr.get("state")) == "closed":
            status = "Closed"
        else:
            status = "Open"
        labels = [label.get("name", "") for label in pr.get("labels", [])]
        items.append(
            SyncItem(
                identifier=identifier,
                title=f"#{pr['number']} {pr['title']}",
                url=pr.get("html_url"),
                status=status,
                labels=[label for label in labels if label],
                description=(pr.get("body") or "")[:1900] or None,
            )
        )
    return items


def build_project_items(
    projects: Iterable[Mapping[str, object]],
    milestones: Iterable[Mapping[str, object]],
) -> List[SyncItem]:
    items: List[SyncItem] = []

    for project in projects:
        identifier = f"project-{project['id']}"
        status = str(project.get("state", "active")).title()
        items.append(
            SyncItem(
                identifier=identifier,
                title=project.get("name", "Unnamed Project"),
                url=project.get("html_url"),
                status=status,
                category="Project",
                description=(project.get("body") or "")[:1900] or None,
            )
        )

    for milestone in milestones:
        identifier = f"milestone-{milestone['id']}"
        status = "Closed" if str(milestone.get("state")) == "closed" else "Open"
        items.append(
            SyncItem(
                identifier=identifier,
                title=f"Milestone: {milestone.get('title', 'Untitled')}",
                url=milestone.get("html_url"),
                status=status,
                category="Milestone",
                description=(milestone.get("description") or "")[:1900] or None,
            )
        )

    return items


def build_run_item(payload: Mapping[str, object]) -> SyncItem:
    workflow_run = payload.get("workflow_run", {})
    run_id = workflow_run.get("id")
    if not run_id:
        raise SyncConfigurationError("workflow_run payload is missing an identifier")

    conclusion = workflow_run.get("conclusion")
    status = workflow_run.get("status")
    mapped_status = map_run_status(conclusion, status)

    run_number = workflow_run.get("run_number")
    title = workflow_run.get("name", "Workflow Run")
    if run_number:
        title = f"{title} #{run_number}"

    return SyncItem(
        identifier=f"run-{run_id}",
        title=title,
        url=workflow_run.get("html_url"),
        status=mapped_status,
        timestamp=workflow_run.get("updated_at") or workflow_run.get("run_started_at"),
        category=workflow_run.get("event"),
    )


def map_run_status(conclusion: Optional[str], status: Optional[str]) -> str:
    """Normalise GitHub workflow run states to a concise label."""

    conclusion_normalised = (conclusion or "").lower()
    if conclusion_normalised == "success":
        return "Success"
    if conclusion_normalised in {"failure", "timed_out", "startup_failure"}:
        return "Failure"
    if conclusion_normalised in {"cancelled", "skipped"}:
        return conclusion_normalised.title()

    status_normalised = (status or "").lower()
    if status_normalised in {"queued", "in_progress"}:
        return "In Progress"

    if conclusion:
        return conclusion.title()
    if status:
        return status.title()
    return "Unknown"


# ---------------------------------------------------------------------------
# CLI entry point


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Synchronise GitHub data with Notion")
    parser.add_argument("--sync-type", required=True, choices=["tasks", "pull_requests", "issues", "projects", "runs"])
    parser.add_argument("--database-id", required=True, help="Target Notion database identifier")
    parser.add_argument("--id-property", default="GitHub ID", help="Notion property used to store unique identifiers")
    parser.add_argument(
        "--id-property-type",
        default="rich_text",
        choices=["rich_text", "number", "title", "url"],
        help="Property type for the identifier field",
    )
    parser.add_argument("--title-property", default="Name", help="Notion title property name")
    parser.add_argument(
        "--status-property",
        default="Status",
        help="Optional Notion property that tracks the state of the entity",
    )
    parser.add_argument(
        "--status-property-type",
        default="status",
        choices=["status", "select", "rich_text"],
        help="Property type for the status field",
    )
    parser.add_argument(
        "--url-property",
        default="GitHub URL",
        help="Optional Notion property that stores the GitHub permalink",
    )
    parser.add_argument(
        "--url-property-type",
        default="url",
        choices=["url", "rich_text"],
        help="Property type for the URL field",
    )
    parser.add_argument(
        "--labels-property",
        default="Labels",
        help="Optional Notion property used for GitHub labels",
    )
    parser.add_argument(
        "--labels-property-type",
        default="multi_select",
        choices=["multi_select", "rich_text"],
        help="Property type for the labels field",
    )
    parser.add_argument(
        "--category-property",
        default="Category",
        help="Optional Notion property for item categorisation",
    )
    parser.add_argument(
        "--category-property-type",
        default="select",
        choices=["select", "rich_text"],
        help="Property type for the category field",
    )
    parser.add_argument(
        "--timestamp-property",
        default="Last Updated",
        help="Optional Notion property capturing the last update timestamp",
    )
    parser.add_argument(
        "--timestamp-property-type",
        default="date",
        choices=["date", "rich_text"],
        help="Property type for the timestamp field",
    )
    parser.add_argument(
        "--description-property",
        default="Description",
        help="Optional Notion property for text summaries",
    )
    parser.add_argument(
        "--description-property-type",
        default="rich_text",
        choices=["rich_text"],
        help="Property type for the description field",
    )
    return parser.parse_args()


def resolve_secret(name: str, env: Mapping[str, str]) -> str:
    value = env.get(name)
    if not value:
        raise SyncConfigurationError(f"Required environment variable {name} is not set")
    return value


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    args = parse_arguments()

    env = os.environ
    notion_token = resolve_secret("NOTION_TOKEN", env)
    github_token = env.get("GITHUB_TOKEN") or env.get("AGENT_ACTIONS")
    if not github_token:
        raise SyncConfigurationError("GITHUB_TOKEN or AGENT_ACTIONS must be available for GitHub API access")

    repository = env.get("GITHUB_REPOSITORY")
    if not repository:
        raise SyncConfigurationError("GITHUB_REPOSITORY is not set in the environment")

    id_property = PropertyBinding(args.id_property, args.id_property_type)
    title_property = PropertyBinding(args.title_property, "title")
    status_property = PropertyBinding(args.status_property, args.status_property_type) if args.status_property else None
    url_property = PropertyBinding(args.url_property, args.url_property_type) if args.url_property else None
    labels_property = PropertyBinding(args.labels_property, args.labels_property_type) if args.labels_property else None
    category_property = PropertyBinding(args.category_property, args.category_property_type) if args.category_property else None
    timestamp_property = PropertyBinding(args.timestamp_property, args.timestamp_property_type) if args.timestamp_property else None
    description_property = (
        PropertyBinding(args.description_property, args.description_property_type)
        if args.description_property
        else None
    )

    github = GitHubDataSource(github_token, repository)
    notion = NotionClient(notion_token)

    sync_items: List[SyncItem]

    if args.sync_type == "tasks":
        issues = github.fetch_task_issues(["task", "tasks"])
        sync_items = build_task_items(issues)
    elif args.sync_type == "issues":
        issues = github.fetch_issues()
        sync_items = build_issue_items(issues)
    elif args.sync_type == "pull_requests":
        prs = github.fetch_pull_requests()
        sync_items = build_pull_request_items(prs)
    elif args.sync_type == "projects":
        projects = github.fetch_projects()
        milestones = github.fetch_milestones()
        sync_items = build_project_items(projects, milestones)
    else:  # runs
        event_path = env.get("GITHUB_EVENT_PATH")
        if not event_path:
            raise SyncConfigurationError("GITHUB_EVENT_PATH is required for workflow run synchronisation")
        with open(event_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        sync_items = [build_run_item(payload)]

    if not sync_items:
        LOGGER.info("No items discovered for sync type %s", args.sync_type)
        return

    for item in sync_items:
        properties = build_properties(
            item,
            title_property=title_property,
            status_property=status_property,
            url_property=url_property,
            label_property=labels_property,
            category_property=category_property,
            timestamp_property=timestamp_property,
            description_property=description_property,
        )

        properties[id_property.name] = build_property_value(id_property.type, item.identifier)
        LOGGER.info("Synchronising %s (%s)", item.title, item.identifier)
        notion.upsert_page(
            args.database_id,
            identifier=item.identifier,
            id_property=id_property,
            properties=properties,
        )


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()

