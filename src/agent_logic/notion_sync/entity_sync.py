"""Synchronisation helpers for GitHub → Notion automation workflows."""
from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import dataclass
from typing import Iterable, Iterator, List, Mapping, MutableMapping, Optional, Sequence

import requests

LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Utility data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GitHubItem:
    """Container representing a GitHub entity that will be mirrored to Notion."""

    github_id: str
    name: str
    url: Optional[str]
    properties: Mapping[str, Mapping[str, object]]


# ---------------------------------------------------------------------------
# GitHub client wrappers
# ---------------------------------------------------------------------------


class GitHubDataFetcher:
    """Small helper around the GitHub REST API for workflow integrations."""

    def __init__(self, token: str, *, base_url: str = "https://api.github.com") -> None:
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            }
        )
        self._base_url = base_url.rstrip("/")

    # ------------------------------------------------------------------
    def _paginate(
        self,
        url: str,
        *,
        params: Optional[MutableMapping[str, object]] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Iterator[Mapping[str, object]]:
        """Yield each page of results for a GitHub API request."""

        current_params = params.copy() if params else None
        while url:
            response = self._session.get(url, params=current_params, headers=headers, timeout=30)
            if response.status_code >= 400:
                raise RuntimeError(f"GitHub API error ({response.status_code}): {response.text}")
            data = response.json()
            if isinstance(data, Mapping):
                # Some endpoints return a dict with an "items" list.
                items = data.get("items", [])
            else:
                items = data
            for item in items:
                yield item
            url = response.links.get("next", {}).get("url")
            current_params = None

    # ------------------------------------------------------------------
    def list_issues(self, repository: str, *, state: str = "all") -> List[Mapping[str, object]]:
        url = f"{self._base_url}/repos/{repository}/issues"
        params: MutableMapping[str, object] = {"per_page": 100, "state": state}
        return list(self._paginate(url, params=params))

    def list_pull_requests(self, repository: str, *, state: str = "all") -> List[Mapping[str, object]]:
        url = f"{self._base_url}/repos/{repository}/pulls"
        params: MutableMapping[str, object] = {"per_page": 100, "state": state}
        return list(self._paginate(url, params=params))

    def list_milestones(self, repository: str, *, state: str = "all") -> List[Mapping[str, object]]:
        url = f"{self._base_url}/repos/{repository}/milestones"
        params: MutableMapping[str, object] = {"per_page": 100, "state": state}
        return list(self._paginate(url, params=params))

    def list_projects(self, repository: str, *, state: str = "all") -> List[Mapping[str, object]]:
        url = f"{self._base_url}/repos/{repository}/projects"
        params: MutableMapping[str, object] = {"per_page": 100, "state": state}
        headers = {"Accept": "application/vnd.github.inertia-preview+json"}
        return list(self._paginate(url, params=params, headers=headers))


# ---------------------------------------------------------------------------
# Notion helpers
# ---------------------------------------------------------------------------


class NotionDatabaseClient:
    """Minimal Notion client tailored for database upsert operations."""

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

    # ------------------------------------------------------------------
    def query_by_github_id(self, database_id: str, github_id: str) -> Optional[str]:
        response = self._session.post(
            f"{self._base_url}/databases/{database_id}/query",
            json={
                "filter": {
                    "property": "GitHub ID",
                    "rich_text": {"equals": github_id},
                }
            },
            timeout=30,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Failed querying Notion database: {response.text}")
        data = response.json()
        results = data.get("results", [])
        if results:
            return results[0].get("id")
        return None

    # ------------------------------------------------------------------
    def create_page(self, database_id: str, properties: Mapping[str, object]) -> Mapping[str, object]:
        payload = {"parent": {"database_id": database_id}, "properties": dict(properties)}
        response = self._session.post(f"{self._base_url}/pages", json=payload, timeout=30)
        if response.status_code >= 400:
            raise RuntimeError(f"Failed creating Notion page: {response.text}")
        return response.json()

    def update_page(self, page_id: str, properties: Mapping[str, object]) -> None:
        response = self._session.patch(
            f"{self._base_url}/pages/{page_id}",
            json={"properties": dict(properties)},
            timeout=30,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Failed updating Notion page: {response.text}")

    # ------------------------------------------------------------------
    def upsert_page(self, database_id: str, item: GitHubItem) -> str:
        """Create or update a page to mirror the GitHub item."""

        base_properties: MutableMapping[str, object] = {
            "Name": _notion_title(item.name),
            "GitHub ID": _rich_text(item.github_id),
        }
        base_properties.update(item.properties)

        existing_page_id = self.query_by_github_id(database_id, item.github_id)
        if existing_page_id:
            self.update_page(existing_page_id, base_properties)
            return "updated"
        self.create_page(database_id, base_properties)
        return "created"


# ---------------------------------------------------------------------------
# Property builders
# ---------------------------------------------------------------------------


def _rich_text(content: Optional[str]) -> Mapping[str, object]:
    if not content:
        return {"rich_text": []}
    return {"rich_text": [{"text": {"content": content[:2000]}}]}


def _notion_title(content: str) -> Mapping[str, object]:
    return {"title": [{"text": {"content": content[:2000]}}]}


def _multi_select(options: Sequence[str]) -> Mapping[str, object]:
    return {"multi_select": [{"name": value[:100]} for value in options if value]}


def _select(name: Optional[str]) -> Mapping[str, object]:
    if not name:
        return {"select": None}
    return {"select": {"name": name[:100]}}


def _date(value: Optional[str]) -> Mapping[str, object]:
    if not value:
        return {"date": None}
    return {"date": {"start": value}}


def build_task_item(issue: Mapping[str, object], *, label_names: Sequence[str]) -> Optional[GitHubItem]:
    labels = [label.get("name", "") for label in issue.get("labels", [])]
    normalized = {name.lower() for name in label_names if name}
    matched = any(label.lower() in normalized for label in labels)
    if not matched:
        return None

    status = "Completed" if issue.get("state") == "closed" else "Open"
    assignees = ", ".join(assignee.get("login", "") for assignee in issue.get("assignees", []) if assignee.get("login"))
    properties = {
        "Status": _select(status),
        "URL": {"url": issue.get("html_url")},
        "Assignee": _rich_text(assignees or None),
        "Labels": _multi_select(labels),
    }
    if issue.get("closed_at"):
        properties["Completed At"] = _date(issue.get("closed_at"))

    return GitHubItem(
        github_id=str(issue.get("id")),
        name=str(issue.get("title") or f"Task {issue.get('number')}"),
        url=issue.get("html_url"),
        properties=properties,
    )


def build_issue_item(issue: Mapping[str, object]) -> Optional[GitHubItem]:
    if "pull_request" in issue:
        return None

    labels = [label.get("name", "") for label in issue.get("labels", [])]
    assignees = ", ".join(assignee.get("login", "") for assignee in issue.get("assignees", []) if assignee.get("login"))
    status = "Closed" if issue.get("state") == "closed" else "Open"

    properties = {
        "State": _select(status),
        "URL": {"url": issue.get("html_url")},
        "Assignee": _rich_text(assignees or None),
        "Labels": _multi_select(labels),
    }
    if issue.get("closed_at"):
        properties["Closed At"] = _date(issue.get("closed_at"))

    return GitHubItem(
        github_id=str(issue.get("id")),
        name=str(issue.get("title") or f"Issue {issue.get('number')}"),
        url=issue.get("html_url"),
        properties=properties,
    )


def build_pull_request_item(pr: Mapping[str, object]) -> GitHubItem:
    status = "Merged" if pr.get("merged_at") else ("Closed" if pr.get("state") == "closed" else "Open")
    author = pr.get("user", {}).get("login")
    reviewers = sorted({reviewer.get("login") for reviewer in pr.get("requested_reviewers", []) if reviewer.get("login")})
    reviewers_text = ", ".join(reviewers)

    properties = {
        "Status": _select(status),
        "URL": {"url": pr.get("html_url")},
        "Author": _rich_text(author or None),
        "Reviewers": _rich_text(reviewers_text or None),
        "Merged At": _date(pr.get("merged_at")),
    }

    return GitHubItem(
        github_id=str(pr.get("id")),
        name=str(pr.get("title") or f"PR {pr.get('number')}"),
        url=pr.get("html_url"),
        properties=properties,
    )


def build_milestone_item(milestone: Mapping[str, object]) -> GitHubItem:
    status = "Closed" if milestone.get("state") == "closed" else "Open"
    due_on = milestone.get("due_on")
    if due_on and not due_on.endswith("Z"):
        # Notion expects ISO8601 with timezone; GitHub returns Z or null.
        due_on = f"{due_on}Z"

    properties = {
        "Status": _select(status),
        "URL": {"url": milestone.get("html_url")},
        "Due Date": _date(due_on),
        "Entity Type": _select("Milestone"),
    }

    return GitHubItem(
        github_id=f"milestone-{milestone.get('id')}",
        name=str(milestone.get("title") or f"Milestone {milestone.get('number')}"),
        url=milestone.get("html_url"),
        properties=properties,
    )


def build_project_item(project: Mapping[str, object]) -> GitHubItem:
    status = "Closed" if project.get("state") == "closed" else "Open"
    updated_at = project.get("updated_at")
    properties = {
        "Status": _select(status),
        "URL": {"url": project.get("html_url")},
        "Entity Type": _select("Project"),
        "Run Timestamp": _date(updated_at),
    }

    return GitHubItem(
        github_id=f"project-{project.get('id')}",
        name=str(project.get("name") or "Project"),
        url=project.get("html_url"),
        properties=properties,
    )


def build_run_item(workflow_run: Mapping[str, object]) -> GitHubItem:
    conclusion = workflow_run.get("conclusion") or workflow_run.get("status")
    timestamp = workflow_run.get("updated_at") or workflow_run.get("run_started_at")
    properties = {
        "Conclusion": _select(conclusion.title() if isinstance(conclusion, str) else conclusion),
        "Workflow Name": _rich_text(workflow_run.get("name")),
        "Run Timestamp": _date(timestamp),
        "URL": {"url": workflow_run.get("html_url")},
        "Run Attempt": _rich_text(str(workflow_run.get("run_attempt")) if workflow_run.get("run_attempt") else None),
    }

    return GitHubItem(
        github_id=str(workflow_run.get("id")),
        name=str(
            workflow_run.get("display_title")
            or f"{workflow_run.get('name', 'workflow')} #{workflow_run.get('run_number')}"
        ),
        url=workflow_run.get("html_url"),
        properties=properties,
    )


# ---------------------------------------------------------------------------
# Synchronisation runners
# ---------------------------------------------------------------------------


def _load_event_payload(event_path: Optional[str]) -> Mapping[str, object]:
    if not event_path:
        raise ValueError("workflow_run events require --event-path")
    with open(event_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def sync_tasks(
    fetcher: GitHubDataFetcher,
    notion: NotionDatabaseClient,
    *,
    repository: str,
    database_id: str,
    label_names: Sequence[str],
    dry_run: bool = False,
) -> None:
    github_items = []
    for issue in fetcher.list_issues(repository):
        item = build_task_item(issue, label_names=label_names)
        if item is not None:
            github_items.append(item)

    _process_items(notion, database_id, github_items, dry_run=dry_run)


def sync_pull_requests(
    fetcher: GitHubDataFetcher,
    notion: NotionDatabaseClient,
    *,
    repository: str,
    database_id: str,
    dry_run: bool = False,
) -> None:
    github_items = [build_pull_request_item(pr) for pr in fetcher.list_pull_requests(repository)]
    _process_items(notion, database_id, github_items, dry_run=dry_run)


def sync_issues(
    fetcher: GitHubDataFetcher,
    notion: NotionDatabaseClient,
    *,
    repository: str,
    database_id: str,
    dry_run: bool = False,
) -> None:
    github_items: List[GitHubItem] = []
    for issue in fetcher.list_issues(repository):
        item = build_issue_item(issue)
        if item is not None:
            github_items.append(item)

    _process_items(notion, database_id, github_items, dry_run=dry_run)


def sync_projects(
    fetcher: GitHubDataFetcher,
    notion: NotionDatabaseClient,
    *,
    repository: str,
    database_id: str,
    dry_run: bool = False,
) -> None:
    github_items: List[GitHubItem] = []
    for milestone in fetcher.list_milestones(repository):
        github_items.append(build_milestone_item(milestone))

    for project in fetcher.list_projects(repository):
        github_items.append(build_project_item(project))

    _process_items(notion, database_id, github_items, dry_run=dry_run)


def sync_runs(
    notion: NotionDatabaseClient,
    *,
    database_id: str,
    event_path: str,
    dry_run: bool = False,
) -> None:
    payload = _load_event_payload(event_path)
    workflow_run = payload.get("workflow_run")
    if not isinstance(workflow_run, Mapping):
        raise ValueError("workflow_run payload missing or malformed")

    item = build_run_item(workflow_run)
    _process_items(notion, database_id, [item], dry_run=dry_run)


def _process_items(
    notion: NotionDatabaseClient,
    database_id: str,
    items: Iterable[GitHubItem],
    *,
    dry_run: bool,
) -> None:
    processed = 0
    created = 0
    updated = 0

    for item in items:
        processed += 1
        if dry_run:
            LOGGER.info("Dry-run enabled; would sync %s (%s)", item.name, item.github_id)
            continue
        try:
            action = notion.upsert_page(database_id, item)
        except Exception as exc:  # pragma: no cover - defensive logging
            LOGGER.error("Failed synchronising %s (%s): %s", item.name, item.github_id, exc)
            continue
        if action == "created":
            created += 1
        else:
            updated += 1

    LOGGER.info(
        "Processed %s items for database %s (created=%s, updated=%s)",
        processed,
        database_id,
        created,
        updated,
    )


# ---------------------------------------------------------------------------
# Command line entry point
# ---------------------------------------------------------------------------


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Synchronise GitHub entities with Notion databases")
    parser.add_argument("--entity", choices=["tasks", "pull_requests", "issues", "projects", "runs"], required=True)
    parser.add_argument("--database-id", required=True, help="Target Notion database identifier")
    parser.add_argument("--github-repo", default=os.environ.get("GITHUB_REPOSITORY"), help="GitHub repository (owner/name)")
    parser.add_argument("--task-labels", default=os.environ.get("TASK_LABELS", "task,Task"))
    parser.add_argument("--event-path", default=os.environ.get("GITHUB_EVENT_PATH"))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = _parse_args(argv)

    notion_token = os.environ.get("NOTION_TOKEN")
    if not notion_token:
        raise EnvironmentError("NOTION_TOKEN is required for Notion synchronisation")

    if args.entity != "runs":
        github_token = os.environ.get("GITHUB_TOKEN")
        if not github_token:
            raise EnvironmentError("GITHUB_TOKEN is required for GitHub synchronisation")
        if not args.github_repo:
            raise EnvironmentError("--github-repo must be provided")
        fetcher = GitHubDataFetcher(github_token)
    else:
        fetcher = None

    notion_client = NotionDatabaseClient(notion_token)

    if args.entity == "tasks":
        label_names = [label.strip() for label in args.task_labels.split(",") if label.strip()]
        sync_tasks(fetcher, notion_client, repository=args.github_repo, database_id=args.database_id, label_names=label_names, dry_run=args.dry_run)  # type: ignore[arg-type]
    elif args.entity == "pull_requests":
        sync_pull_requests(fetcher, notion_client, repository=args.github_repo, database_id=args.database_id, dry_run=args.dry_run)  # type: ignore[arg-type]
    elif args.entity == "issues":
        sync_issues(fetcher, notion_client, repository=args.github_repo, database_id=args.database_id, dry_run=args.dry_run)  # type: ignore[arg-type]
    elif args.entity == "projects":
        sync_projects(fetcher, notion_client, repository=args.github_repo, database_id=args.database_id, dry_run=args.dry_run)  # type: ignore[arg-type]
    else:
        sync_runs(notion_client, database_id=args.database_id, event_path=args.event_path, dry_run=args.dry_run)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
