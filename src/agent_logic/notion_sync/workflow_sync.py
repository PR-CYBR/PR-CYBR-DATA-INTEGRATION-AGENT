"""Synchronisation helpers for GitHub ⇄ Notion workflow automation.

This module provides a light-weight command line utility that is tailored for the
automation requirements described in the Codex Agent workflow specification.
It purposely keeps the implementation dependency-free (apart from ``requests``)
so that it can run inside GitHub Actions without additional tooling.

The script supports five synchronisation targets:

``tasks``
    Mirrors GitHub issues labelled as tasks into the configured Notion task
    database.

``pull_requests``
    Tracks pull request metadata and status changes.

``issues``
    Keeps a general issues database in sync (excluding pull requests).

``projects``
    Publishes repository project board metadata such as state and columns.

``runs_board``
    Records workflow runs so that there is a permanent audit trail in Notion.

The module does *not* attempt to model every property that could exist inside a
Notion database.  Instead, it focuses on a portable contract that is documented
in ``.github/docs/WORKFLOWS.md``.  Databases must expose the following
properties for the synchronisation to succeed:

``Name`` (title)
    Title column containing the human readable name of the item.

``GitHub ID`` (rich text)
    Stores the numeric identifier from GitHub.  It is used as the primary key.

``State`` (status)
    Optional status field representing ``open``/``closed`` states.

Additional properties are created opportunistically if present, but the
synchroniser does not fail if they do not exist (it simply skips them).

The entry point can be executed with ``python -m agent_logic.notion_sync.workflow_sync``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
from typing import Iterable, Iterator, List, Mapping, MutableMapping, Optional

import requests


LOGGER = logging.getLogger("agent_logic.notion_sync.workflow_sync")


# ---------------------------------------------------------------------------
# Helper utilities


class SyncError(RuntimeError):
    """Raised when a synchronisation step encounters a fatal error."""


def _isoformat(timestamp: Optional[str]) -> Optional[str]:
    if not timestamp:
        return None
    try:
        return dt.datetime.fromisoformat(timestamp.rstrip("Z")).replace(tzinfo=dt.timezone.utc).isoformat()
    except ValueError:
        LOGGER.debug("Unable to parse timestamp %s", timestamp)
        return None


def _build_title(text: str) -> Mapping[str, object]:
    return {
        "title": [
            {
                "type": "text",
                "text": {"content": text[:2000]},
            }
        ]
    }


def _build_rich_text(value: str) -> Mapping[str, object]:
    return {
        "rich_text": [
            {
                "type": "text",
                "text": {"content": value[:2000]},
            }
        ]
    }


def _build_status(value: Optional[str]) -> Mapping[str, object]:
    if not value:
        return {}
    return {"status": {"name": value[:100]}}


def _build_multi_select(values: Iterable[str]) -> Mapping[str, object]:
    items = [{"name": val[:100]} for val in values if val]
    if not items:
        return {}
    return {"multi_select": items}


def _build_date(value: Optional[str]) -> Mapping[str, object]:
    if not value:
        return {}
    return {"date": {"start": value}}


def _build_url(value: Optional[str]) -> Mapping[str, object]:
    if not value:
        return {}
    return {"url": value}


def _merge_properties(*entries: Mapping[str, object]) -> Mapping[str, object]:
    merged: MutableMapping[str, object] = {}
    for entry in entries:
        for key, value in entry.items():
            if value:
                merged[key] = value
    return merged


# ---------------------------------------------------------------------------
# HTTP clients


class NotionClient:
    """Minimal Notion API client for querying, creating and updating pages."""

    def __init__(self, token: str, *, base_url: str = "https://api.notion.com/v1") -> None:
        self._base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json",
            }
        )

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
            raise SyncError(f"Failed to query Notion database {database_id}: {response.text}")
        payload = response.json()
        results = payload.get("results") or []
        if not results:
            return None
        return str(results[0].get("id"))

    def upsert_page(self, database_id: str, github_id: str, properties: Mapping[str, object]) -> None:
        page_id = self.query_by_github_id(database_id, github_id)
        if page_id:
            self._update_page(page_id, properties)
        else:
            self._create_page(database_id, properties)

    def _create_page(self, database_id: str, properties: Mapping[str, object]) -> None:
        response = self._session.post(
            f"{self._base_url}/pages",
            json={"parent": {"database_id": database_id}, "properties": properties},
            timeout=30,
        )
        if response.status_code >= 400:
            raise SyncError(f"Failed to create Notion page: {response.text}")

    def _update_page(self, page_id: str, properties: Mapping[str, object]) -> None:
        response = self._session.patch(
            f"{self._base_url}/pages/{page_id}",
            json={"properties": properties},
            timeout=30,
        )
        if response.status_code >= 400:
            raise SyncError(f"Failed to update Notion page {page_id}: {response.text}")


class GitHubClient:
    """Small helper for retrieving repository metadata from the GitHub REST API."""

    def __init__(self, token: str, repository: str, *, base_url: str = "https://api.github.com") -> None:
        self._repository = repository
        self._base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            }
        )

    @property
    def repository(self) -> str:
        return self._repository

    def _paginate(self, url: str, *, params: Optional[Mapping[str, object]] = None) -> Iterator[Mapping[str, object]]:
        params = dict(params or {})
        params.setdefault("per_page", 100)
        while url:
            response = self._session.get(url, params=params, timeout=30)
            if response.status_code >= 400:
                raise SyncError(f"GitHub API request failed: {response.text}")
            data = response.json()
            if isinstance(data, list):
                for item in data:
                    yield item
            else:
                yield data
                return
            params = None
            url = response.links.get("next", {}).get("url")

    def fetch_issues(self, *, state: str = "all") -> List[Mapping[str, object]]:
        url = f"{self._base_url}/repos/{self._repository}/issues"
        return [
            issue
            for issue in self._paginate(url, params={"state": state})
            if "pull_request" not in issue
        ]

    def fetch_pull_requests(self, *, state: str = "all") -> List[Mapping[str, object]]:
        url = f"{self._base_url}/repos/{self._repository}/pulls"
        return list(self._paginate(url, params={"state": state}))

    def fetch_projects(self) -> List[Mapping[str, object]]:
        url = f"{self._base_url}/repos/{self._repository}/projects"
        session = self._session
        original_accept = session.headers.get("Accept")
        session.headers["Accept"] = "application/vnd.github.inertia-preview+json"
        try:
            return list(self._paginate(url))
        finally:
            if original_accept is not None:
                session.headers["Accept"] = original_accept


# ---------------------------------------------------------------------------
# Synchronisation routines


def sync_tasks(github: GitHubClient, notion: NotionClient, *, database_id: str) -> int:
    issues = github.fetch_issues()
    task_candidates = [issue for issue in issues if any(label.get("name", "").lower() == "task" for label in issue.get("labels", []))]

    for issue in task_candidates:
        github_id = str(issue.get("id"))
        title = issue.get("title") or f"Task #{issue.get('number')}"
        state = (issue.get("state") or "open").capitalize()
        closed_at = _isoformat(issue.get("closed_at"))
        updated_at = _isoformat(issue.get("updated_at"))
        properties = _merge_properties(
            {"Name": _build_title(title)},
            {"GitHub ID": _build_rich_text(github_id)},
            {"URL": _build_url(issue.get("html_url"))},
            {"State": _build_status(state)},
            {"Updated At": _build_date(updated_at)},
            {"Completed At": _build_date(closed_at)},
            {"Labels": _build_multi_select(label.get("name", "") for label in issue.get("labels", []))},
            {"Assignees": _build_multi_select(assignee.get("login", "") for assignee in issue.get("assignees", []))},
        )
        notion.upsert_page(database_id, github_id, properties)

    return len(task_candidates)


def sync_pull_requests(github: GitHubClient, notion: NotionClient, *, database_id: str) -> int:
    pull_requests = github.fetch_pull_requests()
    for pull in pull_requests:
        github_id = str(pull.get("id"))
        title = pull.get("title") or f"PR #{pull.get('number')}"
        state = (pull.get("state") or "open").capitalize()
        if pull.get("merged_at"):
            state = "Merged"
        properties = _merge_properties(
            {"Name": _build_title(title)},
            {"GitHub ID": _build_rich_text(github_id)},
            {"URL": _build_url(pull.get("html_url"))},
            {"State": _build_status(state)},
            {"Author": _build_multi_select([pull.get("user", {}).get("login", "")])},
            {"Updated At": _build_date(_isoformat(pull.get("updated_at")))},
            {"Merged At": _build_date(_isoformat(pull.get("merged_at")))},
        )
        notion.upsert_page(database_id, github_id, properties)

    return len(pull_requests)


def sync_issues(github: GitHubClient, notion: NotionClient, *, database_id: str) -> int:
    issues = github.fetch_issues()
    for issue in issues:
        github_id = str(issue.get("id"))
        title = issue.get("title") or f"Issue #{issue.get('number')}"
        state = (issue.get("state") or "open").capitalize()
        properties = _merge_properties(
            {"Name": _build_title(title)},
            {"GitHub ID": _build_rich_text(github_id)},
            {"URL": _build_url(issue.get("html_url"))},
            {"State": _build_status(state)},
            {"Labels": _build_multi_select(label.get("name", "") for label in issue.get("labels", []))},
            {"Assignees": _build_multi_select(assignee.get("login", "") for assignee in issue.get("assignees", []))},
            {"Updated At": _build_date(_isoformat(issue.get("updated_at")))},
            {"Closed At": _build_date(_isoformat(issue.get("closed_at")))},
        )
        notion.upsert_page(database_id, github_id, properties)

    return len(issues)


def sync_projects(github: GitHubClient, notion: NotionClient, *, database_id: str) -> int:
    projects = github.fetch_projects()
    for project in projects:
        github_id = str(project.get("id"))
        name = project.get("name") or f"Project #{project.get('number')}"
        body = project.get("body") or ""
        state = (project.get("state") or "open").capitalize()
        properties = _merge_properties(
            {"Name": _build_title(name)},
            {"GitHub ID": _build_rich_text(github_id)},
            {"URL": _build_url(project.get("html_url"))},
            {"State": _build_status(state)},
            {"Summary": _build_rich_text(body[:2000]) if body else {}},
            {"Updated At": _build_date(_isoformat(project.get("updated_at")))},
        )
        notion.upsert_page(database_id, github_id, properties)

    return len(projects)


def sync_runs_board(notion: NotionClient, *, database_id: str, payload: Mapping[str, str]) -> None:
    run_id = payload.get("run_id")
    if not run_id:
        raise SyncError("Workflow run payload is missing a run identifier")

    timestamp = payload.get("timestamp") or dt.datetime.now(dt.timezone.utc).isoformat()
    properties = _merge_properties(
        {"Name": _build_title(payload.get("workflow") or "Workflow Run")},
        {"GitHub ID": _build_rich_text(str(run_id))},
        {"Run ID": _build_rich_text(str(run_id))},
        {"State": _build_status(payload.get("status"))},
        {"URL": _build_url(payload.get("url"))},
        {"Timestamp": _build_date(timestamp)},
        {"Job": _build_rich_text(payload.get("job") or "")},
    )
    notion.upsert_page(database_id, str(run_id), properties)


# ---------------------------------------------------------------------------
# CLI


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Synchronise GitHub artefacts with Notion databases")
    parser.add_argument("--entity", choices=["tasks", "pull_requests", "issues", "projects", "runs_board"], required=True)
    parser.add_argument("--database-id", required=True, help="Target Notion database identifier")
    parser.add_argument("--repository", help="GitHub repository in owner/name format")
    parser.add_argument("--payload", help="JSON payload for runs_board updates")
    parser.add_argument("--log-level", default=os.getenv("SYNC_LOG_LEVEL", "INFO"))
    return parser


def _load_payload(raw: Optional[str]) -> Mapping[str, str]:
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            return {str(key): str(value) for key, value in payload.items() if value is not None}
    except json.JSONDecodeError as exc:
        raise SyncError(f"Invalid JSON payload: {exc}") from exc
    raise SyncError("Payload must be a JSON object")


def main(args: Optional[List[str]] = None) -> None:
    parser = _build_argument_parser()
    parsed = parser.parse_args(args)

    logging.basicConfig(level=getattr(logging, str(parsed.log_level).upper(), logging.INFO))

    notion_token = os.getenv("NOTION_TOKEN")
    if not notion_token:
        LOGGER.warning("NOTION_TOKEN is not configured; skipping synchronisation")
        return

    entity = parsed.entity
    database_id = parsed.database_id

    notion = NotionClient(notion_token)

    if entity == "runs_board":
        payload = _load_payload(parsed.payload)
        sync_runs_board(notion, database_id=database_id, payload=payload)
        LOGGER.info("Logged workflow run %s to Notion", payload.get("run_id"))
        return

    repository = parsed.repository or os.getenv("GITHUB_REPOSITORY")
    if not repository:
        raise SyncError("Repository information is required for this synchronisation")

    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        LOGGER.warning("GITHUB_TOKEN is not available; skipping GitHub data fetch")
        return

    github = GitHubClient(github_token, repository)

    if entity == "tasks":
        count = sync_tasks(github, notion, database_id=database_id)
        LOGGER.info("Synchronised %s task issues from %s", count, repository)
    elif entity == "pull_requests":
        count = sync_pull_requests(github, notion, database_id=database_id)
        LOGGER.info("Synchronised %s pull requests from %s", count, repository)
    elif entity == "issues":
        count = sync_issues(github, notion, database_id=database_id)
        LOGGER.info("Synchronised %s issues from %s", count, repository)
    elif entity == "projects":
        count = sync_projects(github, notion, database_id=database_id)
        LOGGER.info("Synchronised %s projects from %s", count, repository)
    else:  # pragma: no cover - defensive programming
        raise SyncError(f"Unsupported entity: {entity}")


if __name__ == "__main__":  # pragma: no cover
    main()

