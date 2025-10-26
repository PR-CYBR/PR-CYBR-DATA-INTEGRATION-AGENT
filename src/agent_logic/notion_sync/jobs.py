"""Utility jobs for synchronising GitHub data into Notion databases."""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional

import requests

GITHUB_API = "https://api.github.com"
NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

logger = logging.getLogger(__name__)


class MissingConfiguration(RuntimeError):
    """Raised when a mandatory configuration value is absent."""


@dataclass
class GitHubEntity:
    """Represents a subset of metadata synchronised to Notion."""

    external_id: str
    title: str
    url: str
    state: str
    authored_by: Optional[str] = None
    assignees: Optional[List[str]] = None
    labels: Optional[List[str]] = None
    last_updated: Optional[str] = None
    extra: Optional[Mapping[str, Any]] = None


class GitHubDataFetcher:
    """Lightweight helper used by the workflow jobs to query GitHub."""

    def __init__(self, token: str, repository: str) -> None:
        self._token = token
        self._repository = repository

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self._token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _request(self, endpoint: str, *, params: Optional[Mapping[str, Any]] = None) -> Iterable[Mapping[str, Any]]:
        url = f"{GITHUB_API}{endpoint}"
        response = requests.get(url, headers=self.headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list):
            return data
        if isinstance(data, Mapping) and "items" in data:
            return data["items"]  # type: ignore[index]
        return []

    def issues(self, *, include_pull_requests: bool = False) -> List[GitHubEntity]:
        owner_repo = self._repository
        endpoint = f"/repos/{owner_repo}/issues"
        params = {"state": "all", "per_page": 100}
        issues_payload = self._request(endpoint, params=params)
        entities: List[GitHubEntity] = []
        for issue in issues_payload:
            if issue.get("pull_request") and not include_pull_requests:
                continue
            labels = [label["name"] for label in issue.get("labels", []) if isinstance(label, Mapping)]
            assignees = [assignee["login"] for assignee in issue.get("assignees", []) if isinstance(assignee, Mapping)]
            entities.append(
                GitHubEntity(
                    external_id=str(issue["id"]),
                    title=issue.get("title", "Untitled"),
                    url=issue.get("html_url", ""),
                    state=issue.get("state", "unknown"),
                    authored_by=issue.get("user", {}).get("login"),
                    assignees=assignees or None,
                    labels=labels or None,
                    last_updated=issue.get("updated_at"),
                    extra={"number": issue.get("number"), "body": issue.get("body")},
                )
            )
        return entities

    def pull_requests(self) -> List[GitHubEntity]:
        owner_repo = self._repository
        endpoint = f"/repos/{owner_repo}/pulls"
        params = {"state": "all", "per_page": 100}
        pulls_payload = self._request(endpoint, params=params)
        entities: List[GitHubEntity] = []
        for pr in pulls_payload:
            entities.append(
                GitHubEntity(
                    external_id=str(pr["id"]),
                    title=pr.get("title", "Untitled"),
                    url=pr.get("html_url", ""),
                    state=pr.get("state", "unknown"),
                    authored_by=pr.get("user", {}).get("login"),
                    assignees=[assignee["login"] for assignee in pr.get("assignees", []) if isinstance(assignee, Mapping)]
                    or None,
                    labels=[label["name"] for label in pr.get("labels", []) if isinstance(label, Mapping)] or None,
                    last_updated=pr.get("updated_at"),
                    extra={
                        "number": pr.get("number"),
                        "draft": pr.get("draft"),
                        "merged_at": pr.get("merged_at"),
                        "head_ref": pr.get("head", {}).get("ref"),
                        "base_ref": pr.get("base", {}).get("ref"),
                    },
                )
            )
        return entities

    def milestones(self) -> List[GitHubEntity]:
        owner_repo = self._repository
        endpoint = f"/repos/{owner_repo}/milestones"
        params = {"state": "all", "per_page": 100}
        milestones_payload = self._request(endpoint, params=params)
        entities: List[GitHubEntity] = []
        for milestone in milestones_payload:
            entities.append(
                GitHubEntity(
                    external_id=str(milestone["id"]),
                    title=milestone.get("title", "Untitled"),
                    url=milestone.get("html_url", ""),
                    state=milestone.get("state", "unknown"),
                    authored_by=milestone.get("creator", {}).get("login"),
                    assignees=None,
                    labels=None,
                    last_updated=milestone.get("updated_at"),
                    extra={
                        "description": milestone.get("description"),
                        "open_issues": milestone.get("open_issues"),
                        "closed_issues": milestone.get("closed_issues"),
                        "due_on": milestone.get("due_on"),
                    },
                )
            )
        return entities


class NotionClient:
    """Minimal client for upserting rows into a Notion database."""

    def __init__(self, token: Optional[str], *, dry_run: bool = False, session: Optional[requests.Session] = None) -> None:
        self._token = token
        self._dry_run = dry_run or not token
        self._session = session or requests.Session()

    def _headers(self) -> Dict[str, str]:
        if not self._token:
            return {"Notion-Version": NOTION_VERSION}
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_VERSION,
        }

    def upsert(  # noqa: C901 - function intentionally comprehensive
        self,
        *,
        database_id: Optional[str],
        entity: GitHubEntity,
        id_property: str,
        additional_properties: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload = self._build_properties(entity, id_property, additional_properties)
        if self._dry_run:
            logger.info("[DRY-RUN] Would sync %s to Notion database %s", entity.external_id, database_id)
            return {"status": "dry-run", "properties": payload}
        if not database_id:
            raise MissingConfiguration("Notion database identifier is required when not running in dry-run mode")

        query_body = {
            "filter": {
                "property": id_property,
                "rich_text": {"equals": entity.external_id},
            }
        }
        response = self._session.post(
            f"{NOTION_API}/databases/{database_id}/query",
            headers=self._headers(),
            data=json.dumps(query_body),
            timeout=30,
        )
        if response.status_code == 404:
            logger.warning("Database %s not found or token missing permissions", database_id)
            return {"status": "not-found", "properties": payload}
        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Failed querying Notion database %s: %s", database_id, exc)
            return {"status": "error", "error": str(exc)}

        results = response.json().get("results", [])
        if results:
            page_id = results[0]["id"]
            update_payload = {"properties": payload}
            update_response = self._session.patch(
                f"{NOTION_API}/pages/{page_id}",
                headers=self._headers(),
                data=json.dumps(update_payload),
                timeout=30,
            )
            try:
                update_response.raise_for_status()
            except requests.RequestException as exc:
                logger.error("Unable to update Notion page %s: %s", page_id, exc)
                return {"status": "error", "error": str(exc)}
            return {"status": "updated", "page_id": page_id}

        create_payload = {
            "parent": {"database_id": database_id},
            "properties": payload,
        }
        create_response = self._session.post(
            f"{NOTION_API}/pages",
            headers=self._headers(),
            data=json.dumps(create_payload),
            timeout=30,
        )
        try:
            create_response.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Unable to create Notion page for %s: %s", entity.external_id, exc)
            return {"status": "error", "error": str(exc)}
        result_body = create_response.json()
        return {"status": "created", "page_id": result_body.get("id")}

    @staticmethod
    def _build_properties(
        entity: GitHubEntity, id_property: str, additional_properties: Optional[Mapping[str, Any]]
    ) -> Dict[str, Any]:
        properties: Dict[str, Any] = {
            "Name": {
                "title": [
                    {
                        "text": {
                            "content": entity.title[:2000],
                        }
                    }
                ]
            },
            id_property: {
                "rich_text": [
                    {
                        "text": {
                            "content": entity.external_id,
                        }
                    }
                ]
            },
            "GitHub URL": {"url": entity.url},
            "State": {"select": {"name": entity.state.title()}},
            "Last Synced": {"date": {"start": dt.datetime.utcnow().isoformat()}},
        }
        if entity.authored_by:
            properties["Author"] = {
                "rich_text": [
                    {
                        "text": {
                            "content": entity.authored_by,
                        }
                    }
                ]
            }
        if entity.assignees:
            properties["Assignees"] = {
                "multi_select": [{"name": assignee} for assignee in entity.assignees[:25]]
            }
        if entity.labels:
            properties["Labels"] = {
                "multi_select": [{"name": label} for label in entity.labels[:25]]
            }
        if entity.last_updated:
            properties["GitHub Updated"] = {"date": {"start": entity.last_updated}}
        if additional_properties:
            properties.update(additional_properties)
        return properties


def _detect_repository() -> str:
    repository = os.environ.get("GITHUB_REPOSITORY")
    if not repository:
        raise MissingConfiguration("GITHUB_REPOSITORY environment variable is required")
    return repository


def _build_fetcher() -> GitHubDataFetcher:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("ACTIONS_RUNTIME_TOKEN")
    if not token:
        raise MissingConfiguration("GITHUB_TOKEN environment variable is required")
    repository = _detect_repository()
    return GitHubDataFetcher(token, repository)


def sync_entities(
    *,
    notion_client: NotionClient,
    database_id: Optional[str],
    entities: Iterable[GitHubEntity],
    id_property: str,
    property_builder: Callable[[GitHubEntity], Mapping[str, Any]] | None = None,
) -> Dict[str, Any]:
    summary = {"processed": 0, "created": 0, "updated": 0, "errors": 0}
    for entity in entities:
        summary["processed"] += 1
        extra_props = property_builder(entity) if property_builder else None
        result = notion_client.upsert(
            database_id=database_id, entity=entity, id_property=id_property, additional_properties=extra_props
        )
        status = result.get("status")
        if status == "created":
            summary["created"] += 1
        elif status == "updated":
            summary["updated"] += 1
        elif status in {"error", "not-found"}:
            summary["errors"] += 1
    return summary


def sync_tasks(notion_client: NotionClient, *, database_id: Optional[str]) -> Dict[str, Any]:
    fetcher = _build_fetcher()
    issues = fetcher.issues(include_pull_requests=False)
    task_label = os.environ.get("NOTION_TASK_LABEL", "task")
    filtered = [issue for issue in issues if issue.labels and task_label in [label.lower() for label in issue.labels]]
    if not filtered:
        logger.info("No task-labelled issues detected for synchronisation")
    return sync_entities(
        notion_client=notion_client,
        database_id=database_id,
        entities=filtered,
        id_property=os.environ.get("NOTION_TASK_ID_PROPERTY", "GitHub ID"),
    )


def sync_pull_requests(notion_client: NotionClient, *, database_id: Optional[str]) -> Dict[str, Any]:
    fetcher = _build_fetcher()
    pull_requests = fetcher.pull_requests()
    return sync_entities(
        notion_client=notion_client,
        database_id=database_id,
        entities=pull_requests,
        id_property=os.environ.get("NOTION_PR_ID_PROPERTY", "GitHub ID"),
    )


def sync_issues(notion_client: NotionClient, *, database_id: Optional[str]) -> Dict[str, Any]:
    fetcher = _build_fetcher()
    issues = fetcher.issues(include_pull_requests=False)
    return sync_entities(
        notion_client=notion_client,
        database_id=database_id,
        entities=issues,
        id_property=os.environ.get("NOTION_ISSUE_ID_PROPERTY", "GitHub ID"),
    )


def sync_projects(notion_client: NotionClient, *, database_id: Optional[str]) -> Dict[str, Any]:
    fetcher = _build_fetcher()
    milestones = fetcher.milestones()
    return sync_entities(
        notion_client=notion_client,
        database_id=database_id,
        entities=milestones,
        id_property=os.environ.get("NOTION_PROJECT_ID_PROPERTY", "GitHub ID"),
    )


def sync_run_log(notion_client: NotionClient, *, database_id: Optional[str]) -> Dict[str, Any]:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    payload: Mapping[str, Any]
    if not event_path or not os.path.exists(event_path):
        payload = {}
    else:
        with open(event_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    workflow_run = payload.get("workflow_run", {})
    run_id = workflow_run.get("id", "unknown")
    name = workflow_run.get("name", os.environ.get("GITHUB_WORKFLOW", "Unnamed Workflow"))
    status = workflow_run.get("conclusion") or workflow_run.get("status", "unknown")
    html_url = workflow_run.get("html_url", "")
    updated_at = workflow_run.get("updated_at")

    entity = GitHubEntity(
        external_id=str(run_id),
        title=f"Workflow Run: {name}",
        url=html_url,
        state=str(status).title(),
        authored_by=workflow_run.get("actor", {}).get("login") if isinstance(workflow_run.get("actor"), Mapping) else None,
        assignees=None,
        labels=None,
        last_updated=updated_at,
        extra={"run_number": workflow_run.get("run_number"), "event": workflow_run.get("event")},
    )

    return sync_entities(
        notion_client=notion_client,
        database_id=database_id,
        entities=[entity],
        id_property=os.environ.get("NOTION_RUN_ID_PROPERTY", "GitHub ID"),
        property_builder=lambda _: {
            "Workflow": {
                "rich_text": [
                    {
                        "text": {
                            "content": name,
                        }
                    }
                ]
            },
            "Result": {
                "select": {"name": str(status).title()},
            },
        },
    )


JOB_HANDLERS = {
    "tasks": sync_tasks,
    "pull_requests": sync_pull_requests,
    "issues": sync_issues,
    "projects": sync_projects,
    "runs": sync_run_log,
}


def execute_job(job: str, *, notion_client: NotionClient, database_id: Optional[str]) -> Dict[str, Any]:
    if job not in JOB_HANDLERS:
        raise ValueError(f"Unknown Notion sync job: {job}")
    handler = JOB_HANDLERS[job]
    summary = handler(notion_client, database_id=database_id)
    logger.info("Completed %s job: %s", job, summary)
    return summary
