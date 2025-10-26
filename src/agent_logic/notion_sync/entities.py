"""Utilities for synchronising GitHub entities with Notion databases."""
from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence

import requests

from .client import GitHubApiError, NotionApi, NotionApiError, SyncSummary

LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper structures


@dataclass(frozen=True)
class PropertyValue:
    """Container for describing a Notion property update."""

    value: object
    preferred_types: Sequence[str]

    @classmethod
    def text(cls, value: Optional[str]) -> "PropertyValue":
        return cls(value or "", ("rich_text", "title"))

    @classmethod
    def url(cls, value: Optional[str]) -> "PropertyValue":
        return cls(value or "", ("url", "rich_text"))

    @classmethod
    def status(cls, value: Optional[str]) -> "PropertyValue":
        return cls(value or "", ("status", "select", "rich_text"))

    @classmethod
    def multi_select(cls, values: Sequence[str]) -> "PropertyValue":
        return cls(list(values), ("multi_select", "rich_text"))

    @classmethod
    def number(cls, value: Optional[float]) -> "PropertyValue":
        return cls(value, ("number", "rich_text"))

    @classmethod
    def date(cls, value: Optional[str]) -> "PropertyValue":
        return cls(value, ("date", "rich_text"))


@dataclass
class NotionRecord:
    """Represents a single entry that should exist inside a Notion database."""

    unique_id: str
    name: str
    properties: Mapping[str, PropertyValue]


def _truncate_text(value: str, *, limit: int = 1900) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 3]}..."


class EntitySyncEngine:
    """Generic synchroniser that can upsert records into a Notion database."""

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
        self._database_schema = self._load_database_schema()
        self._title_property = self._find_title_property()
        self._unique_schema = self._database_schema.get(unique_property)
        self._page_cache: MutableMapping[str, str] = {}

    # ------------------------------------------------------------------
    def _load_database_schema(self) -> Mapping[str, Mapping[str, object]]:
        database = self._notion.retrieve_database(self._database_id)
        properties = database.get("properties", {})
        if not isinstance(properties, Mapping):
            raise NotionApiError("Unable to read Notion database properties")
        return properties  # type: ignore[return-value]

    def _find_title_property(self) -> str:
        for name, schema in self._database_schema.items():
            if isinstance(schema, Mapping) and schema.get("type") == "title":
                return name
        raise NotionApiError(
            "Target Notion database does not contain a title property"
        )

    # ------------------------------------------------------------------
    def sync(self, records: Iterable[NotionRecord], *, dry_run: bool = False) -> SyncSummary:
        summary = SyncSummary()
        for record in records:
            try:
                self._sync_single(record, dry_run=dry_run)
            except Exception as exc:  # pragma: no cover - resiliency guard
                self._logger.error("Failed to sync %s: %s", record.unique_id, exc)
                summary.record_failure({"id": record.unique_id}, str(exc))
                continue
            summary.record_success()
        return summary

    def _sync_single(self, record: NotionRecord, *, dry_run: bool) -> None:
        page_payload = self._build_payload(record)
        if dry_run:
            self._logger.info(
                "Dry-run enabled; skipping update for %s", record.unique_id
            )
            return

        page_id = self._resolve_page_id(record.unique_id)
        if page_id:
            self._notion.update_page(page_id, page_payload["properties"])
        else:
            page = self._notion.create_page(page_payload)
            page_id = str(page.get("id"))
        if page_id:
            self._page_cache[record.unique_id] = page_id

    # ------------------------------------------------------------------
    def _build_payload(self, record: NotionRecord) -> Mapping[str, object]:
        properties: Dict[str, object] = {}
        title_schema = self._database_schema[self._title_property]
        properties[self._title_property] = self._coerce_property(
            self._title_property,
            PropertyValue.text(record.name),
            title_schema,
        )

        for name, prop in record.properties.items():
            if name == self._title_property:
                continue
            schema = self._database_schema.get(name)
            if not schema:
                continue
            notion_value = self._coerce_property(name, prop, schema)
            if notion_value is None:
                continue
            properties[name] = notion_value

        return {"parent": {"database_id": self._database_id}, "properties": properties}

    def _coerce_property(
        self,
        name: str,
        prop: PropertyValue,
        schema: Mapping[str, object],
    ) -> Optional[Mapping[str, object]]:
        notion_type = schema.get("type")
        if notion_type not in prop.preferred_types:
            if notion_type != "rich_text":
                return None

        if notion_type == "title":
            return {
                "title": [
                    {
                        "text": {"content": _truncate_text(str(prop.value))},
                    }
                ]
            }
        if notion_type == "rich_text":
            text_value = _truncate_text(str(prop.value))
            return {"rich_text": [{"text": {"content": text_value}}]}
        if notion_type == "url":
            return {"url": str(prop.value) if prop.value else None}
        if notion_type == "number":
            if prop.value in (None, ""):
                return {"number": None}
            try:
                return {"number": float(prop.value)}
            except (TypeError, ValueError):
                return None
        if notion_type == "multi_select":
            values = prop.value or []
            if not isinstance(values, (list, tuple)):
                values = [str(values)]
            return {"multi_select": [{"name": str(v)} for v in values if v]}
        if notion_type == "status":
            return self._build_status(schema, prop.value)
        if notion_type == "select":
            return self._build_select(schema, prop.value)
        if notion_type == "date":
            if not prop.value:
                return {"date": None}
            return {"date": {"start": str(prop.value)}}
        return None

    def _build_status(
        self, schema: Mapping[str, object], value: object
    ) -> Optional[Mapping[str, object]]:
        if not value:
            return None
        options = schema.get("status", {}).get("options", [])
        allowed = {opt.get("name") for opt in options if isinstance(opt, Mapping)}
        if allowed and str(value) not in allowed:
            return None
        return {"status": {"name": str(value)}}

    def _build_select(
        self, schema: Mapping[str, object], value: object
    ) -> Optional[Mapping[str, object]]:
        if not value:
            return None
        options = schema.get("select", {}).get("options", [])
        allowed = {opt.get("name") for opt in options if isinstance(opt, Mapping)}
        if allowed and str(value) not in allowed:
            return None
        return {"select": {"name": str(value)}}

    # ------------------------------------------------------------------
    def _resolve_page_id(self, unique_id: str) -> Optional[str]:
        if unique_id in self._page_cache:
            return self._page_cache[unique_id]
        if not self._unique_schema:
            return None
        filter_body = self._build_unique_filter(unique_id)
        if filter_body is None:
            return None
        result = self._notion.query_database(self._database_id, filter_body)
        results = result.get("results", [])
        if results:
            page_id = str(results[0].get("id"))
            self._page_cache[unique_id] = page_id
            return page_id
        return None

    def _build_unique_filter(self, unique_id: str) -> Optional[Mapping[str, object]]:
        notion_type = self._unique_schema.get("type") if self._unique_schema else None
        if notion_type == "rich_text":
            return {
                "property": self._unique_property,
                "rich_text": {"equals": unique_id},
            }
        if notion_type == "title":
            return {
                "property": self._unique_property,
                "title": {"equals": unique_id},
            }
        if notion_type == "number":
            try:
                number_value = float(unique_id)
            except ValueError:
                return None
            return {
                "property": self._unique_property,
                "number": {"equals": number_value},
            }
        if notion_type == "url":
            return {
                "property": self._unique_property,
                "url": {"equals": unique_id},
            }
        return None


# ---------------------------------------------------------------------------
# GitHub data fetcher


class GitHubDataFetcher:
    """Collects data from the GitHub REST API for synchronisation."""

    def __init__(
        self,
        token: str,
        *,
        repository: str,
        api_url: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if not repository or "/" not in repository:
            raise ValueError("Repository must be in the form 'owner/name'")
        self._repository = repository
        base_url = (api_url or os.environ.get("GITHUB_API_URL") or "https://api.github.com").rstrip("/")
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            }
        )
        # Project APIs currently require a preview header.
        self._project_headers = {
            "Accept": "application/vnd.github.inertia-preview+json",
        }
        self._base_url = base_url
        self._logger = logger or LOGGER

    # ------------------------------------------------------------------
    def fetch_task_issues(self, *, labels: Optional[Sequence[str]] = None) -> List[Mapping[str, object]]:
        issues = self._list_repository_issues(state="all")
        filtered: List[Mapping[str, object]] = []
        lowered = [label.lower() for label in labels] if labels else []
        for issue in issues:
            if issue.get("pull_request"):
                continue
            issue_labels = [str(l.get("name", "")).lower() for l in issue.get("labels", [])]
            if labels:
                if not any(label in issue_labels for label in lowered):
                    continue
            else:
                if not any("task" in label for label in issue_labels):
                    continue
            filtered.append(issue)
        return filtered

    def fetch_issues(self) -> List[Mapping[str, object]]:
        issues = self._list_repository_issues(state="all")
        return [issue for issue in issues if not issue.get("pull_request")]

    def fetch_pull_requests(self) -> List[Mapping[str, object]]:
        owner, name = self._repository.split("/")
        url = f"{self._base_url}/repos/{owner}/{name}/pulls"
        params = {"state": "all", "per_page": 100}
        data = self._paginate(url, params=params)
        return data

    def fetch_milestones(self) -> List[Mapping[str, object]]:
        owner, name = self._repository.split("/")
        url = f"{self._base_url}/repos/{owner}/{name}/milestones"
        params = {"state": "all", "per_page": 100}
        return self._paginate(url, params=params)

    def fetch_projects(self) -> List[Mapping[str, object]]:
        owner, name = self._repository.split("/")
        url = f"{self._base_url}/repos/{owner}/{name}/projects"
        params = {"state": "all", "per_page": 100}
        try:
            return self._paginate(url, params=params, extra_headers=self._project_headers)
        except GitHubApiError as exc:
            # Some repositories disable projects; treat this as non-fatal.
            if "410" in str(exc) or "404" in str(exc):
                self._logger.debug("Repository projects unavailable: %s", exc)
                return []
            raise

    # ------------------------------------------------------------------
    def _list_repository_issues(self, *, state: str = "open") -> List[Mapping[str, object]]:
        owner, name = self._repository.split("/")
        url = f"{self._base_url}/repos/{owner}/{name}/issues"
        params = {"state": state, "per_page": 100}
        return self._paginate(url, params=params)

    def _paginate(
        self,
        url: str,
        *,
        params: Optional[Mapping[str, object]] = None,
        extra_headers: Optional[Mapping[str, str]] = None,
    ) -> List[Mapping[str, object]]:
        results: List[Mapping[str, object]] = []
        headers = dict(self._session.headers)
        if extra_headers:
            headers.update(extra_headers)
        while url:
            response = self._session.get(url, params=params, headers=headers, timeout=30)
            if response.status_code >= 400:
                raise GitHubApiError(
                    f"GitHub API error ({response.status_code}): {response.text}"
                )
            payload = response.json()
            if isinstance(payload, list):
                results.extend(payload)
            else:
                results.append(payload)
            url = response.links.get("next", {}).get("url")
            params = None
        return results


# ---------------------------------------------------------------------------
# Record builders


def build_task_records(issues: Sequence[Mapping[str, object]]) -> List[NotionRecord]:
    records: List[NotionRecord] = []
    for issue in issues:
        labels = [label.get("name", "") for label in issue.get("labels", [])]
        assignees = [assignee.get("login", "") for assignee in issue.get("assignees", [])]
        properties: Dict[str, PropertyValue] = {
            "GitHub ID": PropertyValue.text(str(issue.get("id"))),
            "GitHub URL": PropertyValue.url(issue.get("html_url")),
            "Status": PropertyValue.status(str(issue.get("state", "")).title()),
            "Labels": PropertyValue.multi_select([label for label in labels if label]),
            "Assignees": PropertyValue.text(", ".join([a for a in assignees if a]) or "Unassigned"),
            "Created": PropertyValue.date(issue.get("created_at")),
            "Updated": PropertyValue.date(issue.get("updated_at")),
        }
        if issue.get("closed_at"):
            properties["Completed"] = PropertyValue.date(issue.get("closed_at"))
        properties["Summary"] = PropertyValue.text(issue.get("title"))
        records.append(
            NotionRecord(
                unique_id=str(issue.get("id")),
                name=str(issue.get("title", "Task")),
                properties=properties,
            )
        )
    return records


def build_issue_records(issues: Sequence[Mapping[str, object]]) -> List[NotionRecord]:
    records: List[NotionRecord] = []
    for issue in issues:
        labels = [label.get("name", "") for label in issue.get("labels", [])]
        assignees = [assignee.get("login", "") for assignee in issue.get("assignees", [])]
        properties: Dict[str, PropertyValue] = {
            "GitHub ID": PropertyValue.text(str(issue.get("id"))),
            "GitHub URL": PropertyValue.url(issue.get("html_url")),
            "Status": PropertyValue.status(str(issue.get("state", "")).title()),
            "Labels": PropertyValue.multi_select([label for label in labels if label]),
            "Assignees": PropertyValue.text(", ".join([a for a in assignees if a]) or "Unassigned"),
            "Created": PropertyValue.date(issue.get("created_at")),
            "Updated": PropertyValue.date(issue.get("updated_at")),
            "Summary": PropertyValue.text(issue.get("title")),
        }
        if issue.get("closed_at"):
            properties["Closed"] = PropertyValue.date(issue.get("closed_at"))
        records.append(
            NotionRecord(
                unique_id=str(issue.get("id")),
                name=str(issue.get("title", "Issue")),
                properties=properties,
            )
        )
    return records


def build_pr_records(pull_requests: Sequence[Mapping[str, object]]) -> List[NotionRecord]:
    records: List[NotionRecord] = []
    for pr in pull_requests:
        labels = [label.get("name", "") for label in pr.get("labels", [])]
        author = pr.get("user", {}).get("login") if isinstance(pr.get("user"), Mapping) else None
        reviewers = pr.get("requested_reviewers", []) or []
        reviewer_names = [reviewer.get("login", "") for reviewer in reviewers]
        merged_at = pr.get("merged_at")
        state = str(pr.get("state", "")).title()
        if merged_at:
            state = "Merged"
        properties: Dict[str, PropertyValue] = {
            "GitHub ID": PropertyValue.text(str(pr.get("id"))),
            "GitHub URL": PropertyValue.url(pr.get("html_url")),
            "Status": PropertyValue.status(state),
            "Author": PropertyValue.text(author or "unknown"),
            "Labels": PropertyValue.multi_select([label for label in labels if label]),
            "Reviewers": PropertyValue.text(", ".join([r for r in reviewer_names if r]) or "None"),
            "Created": PropertyValue.date(pr.get("created_at")),
            "Updated": PropertyValue.date(pr.get("updated_at")),
        }
        if merged_at:
            properties["Completed"] = PropertyValue.date(merged_at)
        records.append(
            NotionRecord(
                unique_id=str(pr.get("id")),
                name=str(pr.get("title", "Pull Request")),
                properties=properties,
            )
        )
    return records


def build_project_records(
    milestones: Sequence[Mapping[str, object]],
    projects: Sequence[Mapping[str, object]],
) -> List[NotionRecord]:
    records: List[NotionRecord] = []
    for milestone in milestones:
        properties: Dict[str, PropertyValue] = {
            "GitHub ID": PropertyValue.text(str(milestone.get("id"))),
            "GitHub URL": PropertyValue.url(milestone.get("html_url")),
            "Status": PropertyValue.status(str(milestone.get("state", "")).title()),
            "Type": PropertyValue.text("Milestone"),
            "Due Date": PropertyValue.date(milestone.get("due_on")),
            "Description": PropertyValue.text(milestone.get("description")),
            "Open Issues": PropertyValue.number(milestone.get("open_issues")),
            "Closed Issues": PropertyValue.number(milestone.get("closed_issues")),
            "Updated": PropertyValue.date(milestone.get("updated_at")),
            "Created": PropertyValue.date(milestone.get("created_at")),
        }
        records.append(
            NotionRecord(
                unique_id=str(milestone.get("id")),
                name=str(milestone.get("title", "Milestone")),
                properties=properties,
            )
        )

    for project in projects:
        properties = {
            "GitHub ID": PropertyValue.text(str(project.get("id"))),
            "GitHub URL": PropertyValue.url(project.get("html_url")),
            "Status": PropertyValue.status(str(project.get("state", "")).title()),
            "Type": PropertyValue.text("Project"),
            "Description": PropertyValue.text(project.get("body")),
            "Created": PropertyValue.date(project.get("created_at")),
            "Updated": PropertyValue.date(project.get("updated_at")),
        }
        records.append(
            NotionRecord(
                unique_id=str(project.get("id")),
                name=str(project.get("name", "Project")),
                properties=properties,
            )
        )

    return records


def build_run_records(run_payload: Mapping[str, object]) -> List[NotionRecord]:
    workflow_run = run_payload.get("workflow_run") if isinstance(run_payload, Mapping) else None
    if not isinstance(workflow_run, Mapping):
        return []
    run_id = str(workflow_run.get("id"))
    run_name = str(workflow_run.get("name", "Workflow"))
    run_number = workflow_run.get("run_number")
    full_name = f"{run_name} #{run_number}" if run_number else run_name
    conclusion = workflow_run.get("conclusion") or workflow_run.get("status")
    properties: Dict[str, PropertyValue] = {
        "GitHub ID": PropertyValue.text(run_id),
        "GitHub URL": PropertyValue.url(workflow_run.get("html_url")),
        "Status": PropertyValue.status(str(workflow_run.get("status", "")).title()),
        "Conclusion": PropertyValue.status(str(conclusion or "unknown").title()),
        "Event": PropertyValue.text(workflow_run.get("event")),
        "Branch": PropertyValue.text(workflow_run.get("head_branch")),
        "Commit": PropertyValue.text(workflow_run.get("head_sha")),
        "Run Number": PropertyValue.number(run_number),
        "Created": PropertyValue.date(workflow_run.get("run_started_at")),
        "Updated": PropertyValue.date(workflow_run.get("updated_at")),
    }
    actor = workflow_run.get("actor")
    if isinstance(actor, Mapping):
        properties["Actor"] = PropertyValue.text(actor.get("login"))
    return [
        NotionRecord(
            unique_id=run_id,
            name=full_name,
            properties=properties,
        )
    ]


__all__ = [
    "EntitySyncEngine",
    "GitHubDataFetcher",
    "NotionRecord",
    "PropertyValue",
    "build_issue_records",
    "build_pr_records",
    "build_project_records",
    "build_run_records",
    "build_task_records",
]

