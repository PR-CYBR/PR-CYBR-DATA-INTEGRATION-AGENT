"""Command-line utilities for synchronising GitHub entities with Notion databases.

The module provides a pragmatic bridge between GitHub repository artefacts and
Notion databases by reading the latest state from GitHub and upserting
corresponding pages in Notion.  Each entity type (issues, pull requests,
project tasks, milestones, and workflow runs) is mapped to a Notion database
that follows the conventions documented in ``docs/integrations/notion-sync.md``.

The implementation is intentionally light-weight so that it can run inside
GitHub Actions without additional build steps.  It relies exclusively on the
``requests`` package which is already part of the agent runtime dependencies.
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

GITHUB_API_BASE_URL = "https://api.github.com"
NOTION_API_BASE_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
DEFAULT_TIMEOUT = 30


@dataclass(frozen=True)
class NotionPropertyNames:
    """Names of the Notion properties used by a synchronisation target."""

    title: str = "Name"
    status: str = "Status"
    assignee: str = "Assignee"
    labels: str = "Labels"
    github_url: str = "GitHub URL"
    github_id: str = "GitHub ID"
    github_number: Optional[str] = "GitHub Number"


@dataclass(frozen=True)
class SyncTarget:
    """Configuration describing a GitHub → Notion synchronisation target."""

    slug: str
    properties: NotionPropertyNames
    default_status_open: str = "Open"
    default_status_closed: str = "Closed"


SYNC_TARGETS: Dict[str, SyncTarget] = {
    "tasks": SyncTarget(
        slug="project_tasks",
        properties=NotionPropertyNames(github_number=None),
        default_status_open="Open",
        default_status_closed="Complete",
    ),
    "issues": SyncTarget(
        slug="issues",
        properties=NotionPropertyNames(),
        default_status_open="Open",
        default_status_closed="Closed",
    ),
    "pull_requests": SyncTarget(
        slug="pull_requests",
        properties=NotionPropertyNames(),
        default_status_open="Open",
        default_status_closed="Closed",
    ),
    "projects": SyncTarget(
        slug="projects",
        properties=NotionPropertyNames(
            assignee="Owner",
            labels="Tags",
            github_number="GitHub Number",
        ),
        default_status_open="Active",
        default_status_closed="Closed",
    ),
    "runs": SyncTarget(
        slug="automation_runs",
        properties=NotionPropertyNames(
            assignee="Operator",
            labels="Context",
            github_number="Run Number",
        ),
        default_status_open="Running",
        default_status_closed="Completed",
    ),
}


class GitHubClient:
    """Minimal GitHub REST client used for synchronisation routines."""

    def __init__(self, token: str, repo: str) -> None:
        if not repo or "/" not in repo:
            raise ValueError("GITHUB_REPOSITORY must be provided in the form 'owner/repo'.")
        owner, name = repo.split("/", 1)
        self._owner = owner
        self._repo = name
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "pr-cybr-notion-sync-agent",
            }
        )

    # ------------------------------------------------------------------
    def _paginate(self, url: str, params: Optional[Mapping[str, object]] = None) -> Iterator[Mapping[str, object]]:
        while url:
            response = self._session.get(url, params=params, timeout=DEFAULT_TIMEOUT)
            if response.status_code >= 400:
                raise RuntimeError(f"GitHub request failed: {response.status_code} {response.text}")
            data = response.json()
            if isinstance(data, list):
                for item in data:
                    yield item
            else:
                yield data
                return
            url = response.links.get("next", {}).get("url")
            params = None

    # ------------------------------------------------------------------
    def iter_issues(self, *, include_pull_requests: bool = False) -> Iterator[Mapping[str, object]]:
        url = f"{GITHUB_API_BASE_URL}/repos/{self._owner}/{self._repo}/issues"
        params = {"state": "all", "per_page": 100, "sort": "updated"}
        for issue in self._paginate(url, params=params):
            if not include_pull_requests and "pull_request" in issue:
                continue
            yield issue

    def iter_pull_requests(self) -> Iterator[Mapping[str, object]]:
        url = f"{GITHUB_API_BASE_URL}/repos/{self._owner}/{self._repo}/pulls"
        params = {"state": "all", "per_page": 100, "sort": "updated"}
        yield from self._paginate(url, params=params)

    def iter_milestones(self) -> Iterator[Mapping[str, object]]:
        url = f"{GITHUB_API_BASE_URL}/repos/{self._owner}/{self._repo}/milestones"
        params = {"state": "all", "per_page": 100}
        yield from self._paginate(url, params=params)


class NotionClient:
    """Small helper around the Notion REST API."""

    def __init__(self, token: str) -> None:
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Notion-Version": NOTION_VERSION,
                "Content-Type": "application/json",
            }
        )

    def query_by_rich_text(
        self,
        database_id: str,
        property_name: str,
        value: str,
    ) -> Optional[str]:
        payload = {
            "filter": {
                "property": property_name,
                "rich_text": {"equals": value},
            }
        }
        response = self._session.post(
            f"{NOTION_API_BASE_URL}/databases/{database_id}/query",
            json=payload,
            timeout=DEFAULT_TIMEOUT,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Failed to query Notion database: {response.status_code} {response.text}")
        results = response.json().get("results", [])
        if not results:
            return None
        return results[0].get("id")

    def create_page(self, database_id: str, properties: Mapping[str, object]) -> str:
        payload = {"parent": {"database_id": database_id}, "properties": properties}
        response = self._session.post(
            f"{NOTION_API_BASE_URL}/pages",
            json=payload,
            timeout=DEFAULT_TIMEOUT,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Failed to create Notion page: {response.status_code} {response.text}")
        data = response.json()
        return str(data.get("id"))

    def update_page(self, page_id: str, properties: Mapping[str, object]) -> None:
        response = self._session.patch(
            f"{NOTION_API_BASE_URL}/pages/{page_id}",
            json={"properties": properties},
            timeout=DEFAULT_TIMEOUT,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Failed to update Notion page: {response.status_code} {response.text}")


@dataclass
class SyncResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0

    def record_created(self) -> None:
        self.created += 1

    def record_updated(self) -> None:
        self.updated += 1

    def record_skipped(self) -> None:
        self.skipped += 1


def _build_title_payload(title: str) -> Mapping[str, object]:
    truncated = title[:2000] if title else "Untitled"
    return {"title": [{"text": {"content": truncated}}]}


def _build_status_payload(status: Optional[str]) -> Mapping[str, object]:
    if not status:
        return {}
    return {"status": {"name": status}}


def _build_people_payload() -> Mapping[str, object]:
    return {"people": []}


def _build_labels_payload(labels: Iterable[str]) -> Mapping[str, object]:
    return {"multi_select": [{"name": label} for label in labels if label]}


def _build_url_payload(url: Optional[str]) -> Mapping[str, object]:
    if not url:
        return {}
    return {"url": url}


def _build_rich_text_payload(value: Optional[str]) -> Mapping[str, object]:
    if not value:
        return {}
    return {"rich_text": [{"text": {"content": value}}]}


def _build_number_payload(number: Optional[int]) -> Mapping[str, object]:
    if number is None:
        return {}
    return {"number": number}


def _merge_properties(*entries: Mapping[str, object]) -> Dict[str, object]:
    properties: Dict[str, object] = {}
    for entry in entries:
        for key, value in entry.items():
            if value or value == [] or value == 0:
                properties[key] = value
    return properties


def _extract_labels(raw_labels: Iterable[Mapping[str, object]]) -> List[str]:
    labels: List[str] = []
    for label in raw_labels:
        name = label.get("name")
        if name:
            labels.append(str(name))
    return labels


def _issue_status(issue: Mapping[str, object], target: SyncTarget) -> str:
    return target.default_status_closed if issue.get("state") == "closed" else target.default_status_open


def _pull_request_status(pr: Mapping[str, object], target: SyncTarget) -> str:
    if pr.get("merged_at"):
        return "Merged"
    return target.default_status_closed if pr.get("state") == "closed" else target.default_status_open


def _project_status(milestone: Mapping[str, object], target: SyncTarget) -> str:
    state = str(milestone.get("state") or "")
    if state.lower() == "closed":
        return target.default_status_closed
    if state:
        return state.capitalize()
    return target.default_status_open


def _run_status(run: Mapping[str, object], target: SyncTarget) -> str:
    conclusion = (run.get("conclusion") or "").lower()
    status = target.default_status_open
    if conclusion:
        if conclusion == "success":
            status = target.default_status_closed
        elif conclusion in {"failure", "timed_out"}:
            status = "Failed"
        elif conclusion in {"cancelled", "skipped"}:
            status = conclusion.capitalize()
        else:
            status = conclusion.capitalize()
    return status


def _task_matches(issue: Mapping[str, object]) -> bool:
    labels = {str(label.get("name", "")).lower() for label in issue.get("labels", [])}
    return "task" in labels or "tasks" in labels


def _build_issue_properties(issue: Mapping[str, object], target: SyncTarget) -> Dict[str, object]:
    props = target.properties
    labels = _extract_labels(issue.get("labels", []))
    status = _issue_status(issue, target)
    return _merge_properties(
        {props.title: _build_title_payload(issue.get("title") or "Untitled")},
        {props.status: _build_status_payload(status)},
        {props.assignee: _build_people_payload()},
        {props.labels: _build_labels_payload(labels)},
        {props.github_url: _build_url_payload(issue.get("html_url"))},
        {props.github_id: _build_rich_text_payload(issue.get("node_id"))},
        (
            {props.github_number: _build_number_payload(issue.get("number"))}
            if props.github_number
            else {}
        ),
    )


def _build_pull_request_properties(pr: Mapping[str, object], target: SyncTarget) -> Dict[str, object]:
    props = target.properties
    labels = _extract_labels(pr.get("labels", []))
    status = _pull_request_status(pr, target)
    return _merge_properties(
        {props.title: _build_title_payload(pr.get("title") or "(no title)")},
        {props.status: _build_status_payload(status)},
        {props.assignee: _build_people_payload()},
        {props.labels: _build_labels_payload(labels)},
        {props.github_url: _build_url_payload(pr.get("html_url"))},
        {props.github_id: _build_rich_text_payload(pr.get("node_id"))},
        (
            {props.github_number: _build_number_payload(pr.get("number"))}
            if props.github_number
            else {}
        ),
    )


def _build_project_properties(milestone: Mapping[str, object], target: SyncTarget) -> Dict[str, object]:
    props = target.properties
    status = _project_status(milestone, target)
    labels: List[str] = []
    due_on = milestone.get("due_on")
    if due_on:
        labels.append(f"Due {due_on}")
    return _merge_properties(
        {props.title: _build_title_payload(milestone.get("title") or "Project")},
        {props.status: _build_status_payload(status)},
        {props.assignee: _build_people_payload()},
        {props.labels: _build_labels_payload(labels)},
        {props.github_url: _build_url_payload(milestone.get("html_url"))},
        {props.github_id: _build_rich_text_payload(milestone.get("node_id"))},
        (
            {props.github_number: _build_number_payload(milestone.get("number"))}
            if props.github_number
            else {}
        ),
    )


def _build_run_properties(run: Mapping[str, object], target: SyncTarget) -> Dict[str, object]:
    props = target.properties
    status = _run_status(run, target)
    labels = [run.get("event", "").capitalize()] if run.get("event") else []
    return _merge_properties(
        {props.title: _build_title_payload(f"{run.get('name')} #{run.get('run_number')}")},
        {props.status: _build_status_payload(status)},
        {props.assignee: _build_people_payload()},
        {props.labels: _build_labels_payload(labels)},
        {props.github_url: _build_url_payload(run.get("html_url"))},
        {props.github_id: _build_rich_text_payload(str(run.get("id")))},
        (
            {props.github_number: _build_number_payload(run.get("run_number"))}
            if props.github_number
            else {}
        ),
    )


def _sync_items(
    items: Iterable[Mapping[str, object]],
    *,
    target: SyncTarget,
    database_id: str,
    notion_client: NotionClient,
    property_builder,
) -> SyncResult:
    result = SyncResult()
    for item in items:
        github_id = str(item.get("node_id") or item.get("id"))
        if not github_id:
            LOGGER.debug("Skipping item without GitHub ID: %s", item)
            result.record_skipped()
            continue
        properties = property_builder(item, target)
        if not properties:
            LOGGER.debug("No properties produced for %s; skipping", github_id)
            result.record_skipped()
            continue
        page_id = notion_client.query_by_rich_text(database_id, target.properties.github_id, github_id)
        if page_id:
            notion_client.update_page(page_id, properties)
            result.record_updated()
        else:
            notion_client.create_page(database_id, properties)
            result.record_created()
    return result


def sync_tasks(github: GitHubClient, notion: NotionClient, database_id: str, target: SyncTarget) -> SyncResult:
    items = (issue for issue in github.iter_issues() if _task_matches(issue))
    return _sync_items(items, target=target, database_id=database_id, notion_client=notion, property_builder=_build_issue_properties)


def sync_issues(github: GitHubClient, notion: NotionClient, database_id: str, target: SyncTarget) -> SyncResult:
    return _sync_items(github.iter_issues(), target=target, database_id=database_id, notion_client=notion, property_builder=_build_issue_properties)


def sync_pull_requests(github: GitHubClient, notion: NotionClient, database_id: str, target: SyncTarget) -> SyncResult:
    return _sync_items(github.iter_pull_requests(), target=target, database_id=database_id, notion_client=notion, property_builder=_build_pull_request_properties)


def sync_projects(github: GitHubClient, notion: NotionClient, database_id: str, target: SyncTarget) -> SyncResult:
    return _sync_items(github.iter_milestones(), target=target, database_id=database_id, notion_client=notion, property_builder=_build_project_properties)


def sync_runs(event_path: str, notion: NotionClient, database_id: str, target: SyncTarget) -> SyncResult:
    if not os.path.exists(event_path):
        raise FileNotFoundError(f"GitHub event payload not found at {event_path}")
    with open(event_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    run = payload.get("workflow_run")
    if not isinstance(run, Mapping):
        raise ValueError("workflow_run payload missing from event context")
    return _sync_items([run], target=target, database_id=database_id, notion_client=notion, property_builder=_build_run_properties)


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Synchronise GitHub entities with Notion")
    parser.add_argument("entity", choices=sorted(SYNC_TARGETS.keys()), help="Entity type to synchronise")
    parser.add_argument("--database-id", required=True, help="Target Notion database identifier")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"), help="GitHub repository in owner/repo format")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    _configure_logging(args.verbose)

    notion_token = os.environ.get("NOTION_TOKEN")
    github_token = os.environ.get("GITHUB_TOKEN")
    if not notion_token:
        parser.error("NOTION_TOKEN environment variable must be set")
    if args.entity != "runs" and not github_token:
        parser.error("GITHUB_TOKEN environment variable must be set")

    target = SYNC_TARGETS[args.entity]
    notion = NotionClient(notion_token)

    try:
        if args.entity == "runs":
            event_path = os.environ.get("GITHUB_EVENT_PATH")
            if not event_path:
                parser.error("GITHUB_EVENT_PATH must be provided for workflow run synchronisation")
            result = sync_runs(event_path, notion, args.database_id, target)
        else:
            if not args.repo:
                parser.error("--repo must be provided or GITHUB_REPOSITORY must be set")
            github = GitHubClient(github_token, args.repo)
            if args.entity == "tasks":
                result = sync_tasks(github, notion, args.database_id, target)
            elif args.entity == "issues":
                result = sync_issues(github, notion, args.database_id, target)
            elif args.entity == "pull_requests":
                result = sync_pull_requests(github, notion, args.database_id, target)
            elif args.entity == "projects":
                result = sync_projects(github, notion, args.database_id, target)
            else:  # pragma: no cover - defensive guard
                parser.error(f"Unsupported entity type: {args.entity}")
                return 2
    except Exception as exc:  # pragma: no cover - runtime protection
        LOGGER.exception("Synchronisation failed: %s", exc)
        return 1

    LOGGER.info(
        "Synchronisation completed for %s: %s created, %s updated, %s skipped",
        args.entity,
        result.created,
        result.updated,
        result.skipped,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
