"""Utilities for synchronising GitHub entities with Notion databases."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional

import requests

from .client import NotionApi, NotionApiError, SyncSummary

LOGGER = logging.getLogger(__name__)


class GitHubEntitySyncError(RuntimeError):
    """Raised when the GitHub API returns an unexpected response."""


@dataclass
class EntityRecord:
    """Represents a GitHub entity that should be mirrored to Notion."""

    identifier: str
    title: str
    status: str
    details: str
    url: Optional[str] = None


class NotionEntitySyncRunner:
    """Synchronise GitHub entities with a dedicated Notion database."""

    def __init__(
        self,
        *,
        entity: str,
        notion_token: str,
        database_id: str,
        github_token: Optional[str] = None,
        repository: Optional[str] = None,
        task_labels: Optional[Iterable[str]] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._entity = entity
        self._database_id = database_id
        self._logger = logger or LOGGER
        self._notion = NotionApi(notion_token)
        self._task_labels = {label.lower() for label in task_labels or ()}
        self._repository = repository
        self._page_cache: MutableMapping[str, str] = {}

        if entity != "runs":
            if not github_token:
                raise ValueError("A GitHub token is required to synchronise this entity")
            if not repository:
                raise ValueError("The repository slug must be provided")
            self._github_session = requests.Session()
            self._github_session.headers.update(
                {
                    "Authorization": f"Bearer {github_token}",
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "PR-CYBR-NotionSync/1.0",
                }
            )
            self._api_base = "https://api.github.com"
        else:
            self._github_session = None
            self._api_base = ""

    # ------------------------------------------------------------------
    def run(self, *, dry_run: bool = False, run_payload: Optional[Mapping[str, str]] = None) -> SyncSummary:
        """Execute the synchronisation workflow."""

        summary = SyncSummary()
        try:
            records = self._collect_records(run_payload=run_payload)
        except (GitHubEntitySyncError, requests.RequestException) as exc:
            self._logger.error("Failed to collect %s data: %s", self._entity, exc)
            summary.record_failure({"name": self._entity}, str(exc))
            return summary

        for record in records:
            try:
                self._sync_single_record(record, dry_run=dry_run)
            except NotionApiError as exc:
                self._logger.error("Failed to sync %s (%s): %s", self._entity, record.identifier, exc)
                summary.record_failure({"name": record.identifier}, str(exc))
                continue
            except Exception as exc:  # pragma: no cover - defensive safety net
                self._logger.error("Unexpected failure syncing %s (%s): %s", self._entity, record.identifier, exc)
                summary.record_failure({"name": record.identifier}, str(exc))
                continue

            summary.record_success()

        return summary

    # ------------------------------------------------------------------
    def _collect_records(self, *, run_payload: Optional[Mapping[str, str]]) -> List[EntityRecord]:
        if self._entity == "tasks":
            return list(self._collect_task_records())
        if self._entity == "pull_requests":
            return list(self._collect_pull_request_records())
        if self._entity == "issues":
            return list(self._collect_issue_records())
        if self._entity == "projects":
            return list(self._collect_project_records())
        if self._entity == "runs":
            return list(self._collect_run_records(run_payload or {}))
        raise ValueError(f"Unsupported entity type: {self._entity}")

    # ------------------------------------------------------------------
    def _collect_task_records(self) -> Iterable[EntityRecord]:
        assert self._github_session is not None
        url = f"{self._api_base}/repos/{self._repository}/issues"
        params = {"state": "all", "per_page": 100}
        for issue in self._paginate(url, params=params):
            if "pull_request" in issue:
                continue
            labels = [str(label.get("name", "")) for label in issue.get("labels", [])]
            if self._task_labels:
                match = any(label.lower() in self._task_labels for label in labels)
                if not match:
                    continue
            status = "Closed" if issue.get("state") == "closed" else "Open"
            assignee = issue.get("assignee", {}) or {}
            assignee_login = assignee.get("login") if isinstance(assignee, Mapping) else None
            details_lines = [
                f"Status: {status}",
                f"Labels: {', '.join(labels) if labels else 'None'}",
                f"Assignee: {assignee_login or 'Unassigned'}",
                f"URL: {issue.get('html_url', 'n/a')}",
            ]
            body = issue.get("body") or ""
            if body:
                details_lines.append("---")
                details_lines.append(body)
            yield EntityRecord(
                identifier=str(issue.get("id")),
                title=str(issue.get("title") or "Untitled Task"),
                status=status,
                details="\n".join(details_lines),
                url=issue.get("html_url"),
            )

    # ------------------------------------------------------------------
    def _collect_pull_request_records(self) -> Iterable[EntityRecord]:
        assert self._github_session is not None
        url = f"{self._api_base}/repos/{self._repository}/pulls"
        params = {"state": "all", "per_page": 100}
        for pull in self._paginate(url, params=params):
            status = "Merged" if pull.get("merged_at") else ("Closed" if pull.get("state") == "closed" else "Open")
            details_lines = [
                f"Status: {status}",
                f"Author: {pull.get('user', {}).get('login', 'unknown')}",
                f"Base: {pull.get('base', {}).get('ref', 'n/a')}",
                f"Head: {pull.get('head', {}).get('ref', 'n/a')}",
                f"URL: {pull.get('html_url', 'n/a')}",
            ]
            body = pull.get("body") or ""
            if body:
                details_lines.append("---")
                details_lines.append(body)
            yield EntityRecord(
                identifier=str(pull.get("id")),
                title=str(pull.get("title") or "Untitled Pull Request"),
                status=status,
                details="\n".join(details_lines),
                url=pull.get("html_url"),
            )

    # ------------------------------------------------------------------
    def _collect_issue_records(self) -> Iterable[EntityRecord]:
        assert self._github_session is not None
        url = f"{self._api_base}/repos/{self._repository}/issues"
        params = {"state": "all", "per_page": 100}
        for issue in self._paginate(url, params=params):
            if "pull_request" in issue:
                continue
            status = "Closed" if issue.get("state") == "closed" else "Open"
            labels = [str(label.get("name", "")) for label in issue.get("labels", [])]
            assignees = [assignee.get("login") for assignee in issue.get("assignees", []) if isinstance(assignee, Mapping)]
            details_lines = [
                f"Status: {status}",
                f"Labels: {', '.join(labels) if labels else 'None'}",
                f"Assignees: {', '.join(assignees) if assignees else 'Unassigned'}",
                f"URL: {issue.get('html_url', 'n/a')}",
            ]
            body = issue.get("body") or ""
            if body:
                details_lines.append("---")
                details_lines.append(body)
            yield EntityRecord(
                identifier=str(issue.get("id")),
                title=str(issue.get("title") or "Untitled Issue"),
                status=status,
                details="\n".join(details_lines),
                url=issue.get("html_url"),
            )

    # ------------------------------------------------------------------
    def _collect_project_records(self) -> Iterable[EntityRecord]:
        assert self._github_session is not None
        url = f"{self._api_base}/repos/{self._repository}/milestones"
        params = {"state": "all", "per_page": 100}
        for milestone in self._paginate(url, params=params):
            status = "Closed" if milestone.get("state") == "closed" else "Open"
            due_on = milestone.get("due_on")
            details_lines = [
                f"Status: {status}",
                f"Open issues: {milestone.get('open_issues', 0)}",
                f"Closed issues: {milestone.get('closed_issues', 0)}",
                f"Due on: {due_on or 'n/a'}",
                f"URL: {milestone.get('html_url', 'n/a')}",
            ]
            description = milestone.get("description") or ""
            if description:
                details_lines.append("---")
                details_lines.append(description)
            yield EntityRecord(
                identifier=str(milestone.get("id")),
                title=str(milestone.get("title") or "Untitled Milestone"),
                status=status,
                details="\n".join(details_lines),
                url=milestone.get("html_url"),
            )

    # ------------------------------------------------------------------
    def _collect_run_records(self, payload: Mapping[str, str]) -> Iterable[EntityRecord]:
        run_id = payload.get("run_id") or payload.get("workflow_run_id")
        timestamp = payload.get("timestamp") or datetime.now(timezone.utc).isoformat()
        name = payload.get("name") or payload.get("workflow") or "Workflow Run"
        status = payload.get("conclusion") or payload.get("status") or "unknown"
        url = payload.get("url")
        details_lines = [
            f"Workflow: {payload.get('workflow') or name}",
            f"Event: {payload.get('event') or 'n/a'}",
            f"Status: {status}",
            f"Timestamp: {timestamp}",
        ]
        html_url = payload.get("html_url")
        if html_url and not url:
            url = html_url
        if payload.get("actor"):
            details_lines.append(f"Actor: {payload['actor']}")
        if payload.get("repository"):
            details_lines.append(f"Repository: {payload['repository']}")
        if payload.get("url"):
            details_lines.append(f"URL: {payload['url']}")
        elif html_url:
            details_lines.append(f"URL: {html_url}")
        additional_notes = payload.get("notes")
        if additional_notes:
            details_lines.append("---")
            details_lines.append(additional_notes)
        identifier = run_id or f"{name}-{timestamp}"
        yield EntityRecord(
            identifier=str(identifier),
            title=name,
            status=status,
            details="\n".join(details_lines),
            url=url or html_url,
        )

    # ------------------------------------------------------------------
    def _sync_single_record(self, record: EntityRecord, *, dry_run: bool) -> None:
        if dry_run:
            self._logger.info("Dry-run enabled; skipping update for %s", record.identifier)
            return
        page_id = self._resolve_page_id(record.identifier)
        properties = self._build_properties(record)
        if page_id:
            self._notion.update_page(page_id, properties)
            self._logger.debug("Updated Notion page %s for %s", page_id, record.identifier)
        else:
            payload = {"parent": {"database_id": self._database_id}, "properties": properties}
            response = self._notion.create_page(payload)
            page_id = response.get("id")
            if page_id:
                self._page_cache[record.identifier] = page_id
            self._logger.debug("Created Notion page %s for %s", page_id, record.identifier)

    # ------------------------------------------------------------------
    def _build_properties(self, record: EntityRecord) -> Dict[str, object]:
        properties: Dict[str, object] = {
            "Name": {
                "title": [
                    {
                        "text": {
                            "content": _truncate(record.title, 200),
                        }
                    }
                ]
            },
            "GitHub ID": {
                "rich_text": [
                    {
                        "text": {
                            "content": record.identifier,
                        }
                    }
                ]
            },
        }
        if record.status:
            properties["Status"] = {
                "rich_text": [
                    {
                        "text": {
                            "content": _truncate(record.status, 200),
                        }
                    }
                ]
            }
        if record.details:
            properties["Details"] = {
                "rich_text": [
                    {
                        "text": {
                            "content": _truncate(record.details, 2000),
                        }
                    }
                ]
            }
        if record.url:
            properties["URL"] = {"url": record.url}
        return properties

    # ------------------------------------------------------------------
    def _resolve_page_id(self, identifier: str) -> Optional[str]:
        if identifier in self._page_cache:
            return self._page_cache[identifier]
        filter_body = {
            "property": "GitHub ID",
            "rich_text": {"equals": identifier},
        }
        response = self._notion.query_database(self._database_id, filter_body)
        for result in response.get("results", []):
            page_id = result.get("id")
            if page_id:
                self._page_cache[identifier] = page_id
                return page_id
        return None

    # ------------------------------------------------------------------
    def _paginate(self, url: str, *, params: Optional[Mapping[str, object]] = None) -> Iterable[Mapping[str, object]]:
        session = self._github_session
        if session is None:
            return []
        request_params = dict(params) if params else None
        next_url: Optional[str] = url
        while next_url:
            response = session.get(next_url, params=request_params, timeout=30)
            request_params = None
            if response.status_code >= 400:
                raise GitHubEntitySyncError(f"GitHub API request failed: {response.status_code} {response.text}")
            data = response.json()
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, Mapping):
                        yield item
            elif isinstance(data, Mapping):
                yield data
            else:
                raise GitHubEntitySyncError("Unexpected payload received from GitHub API")
            next_url = response.links.get("next", {}).get("url")


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: max(limit - 1, 1)] + "…"


__all__ = [
    "EntityRecord",
    "GitHubEntitySyncError",
    "NotionEntitySyncRunner",
]
