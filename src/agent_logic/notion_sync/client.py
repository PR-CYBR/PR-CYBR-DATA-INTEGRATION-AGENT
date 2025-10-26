"""Client helpers for synchronising GitHub repositories with Notion."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional

import requests

from . import mappers

LOGGER = logging.getLogger(__name__)


class NotionApiError(RuntimeError):
    """Raised when the Notion API returns an error."""


class GitHubApiError(RuntimeError):
    """Raised when the GitHub API returns an error."""


@dataclass
class SyncSummary:
    """Summarises the outcome of a synchronisation run."""

    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    errors: List[Dict[str, str]] = field(default_factory=list)

    def record_success(self) -> None:
        self.processed += 1
        self.succeeded += 1

    def record_failure(self, repository: Mapping[str, object], message: str) -> None:
        self.processed += 1
        self.failed += 1
        self.errors.append({
            "repository": str(repository.get("full_name") or repository.get("name")),
            "message": message,
        })


class NotionApi:
    """Small wrapper around the Notion API endpoints used by the sync."""

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

    def query_database(self, database_id: str, filter_body: Mapping[str, object]) -> Mapping[str, object]:
        response = self._session.post(
            f"{self._base_url}/databases/{database_id}/query",
            json={"filter": filter_body},
            timeout=30,
        )
        if response.status_code >= 400:
            raise NotionApiError(f"Failed to query Notion database: {response.text}")
        return response.json()

    def list_database_pages(
        self,
        database_id: str,
        *,
        filter_body: Optional[Mapping[str, object]] = None,
    ) -> Iterable[Mapping[str, object]]:
        """Iterate over all pages stored in a Notion database.

        Parameters
        ----------
        database_id:
            Identifier of the Notion database being queried.
        filter_body:
            Optional filter applied to the query payload.
        """

        payload: Dict[str, object] = {}
        if filter_body:
            payload["filter"] = filter_body

        while True:
            response = self._session.post(
                f"{self._base_url}/databases/{database_id}/query",
                json=payload,
                timeout=30,
            )
            if response.status_code >= 400:
                raise NotionApiError(f"Failed to list Notion database pages: {response.text}")

            data = response.json()
            for page in data.get("results", []):
                yield page

            if not data.get("has_more"):
                break

            payload["start_cursor"] = data.get("next_cursor")

    def create_page(self, payload: Mapping[str, object]) -> Mapping[str, object]:
        response = self._session.post(
            f"{self._base_url}/pages",
            json=payload,
            timeout=30,
        )
        if response.status_code >= 400:
            raise NotionApiError(f"Failed to create Notion page: {response.text}")
        return response.json()

    def update_page(self, page_id: str, properties: Mapping[str, object]) -> None:
        response = self._session.patch(
            f"{self._base_url}/pages/{page_id}",
            json={"properties": properties},
            timeout=30,
        )
        if response.status_code >= 400:
            raise NotionApiError(f"Failed to update Notion page: {response.text}")


class GitHubClient:
    """Small wrapper around the GitHub REST API to list repositories."""

    def __init__(self, token: str, *, org: Optional[str] = None, base_url: str = "https://api.github.com") -> None:
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            }
        )
        self._base_url = base_url.rstrip("/")
        self._org = org

    def list_repositories(self) -> Iterable[Mapping[str, object]]:
        url = f"{self._base_url}/user/repos"
        if self._org:
            url = f"{self._base_url}/orgs/{self._org}/repos"

        params = {"per_page": 100, "type": "all"}
        repositories: List[Mapping[str, object]] = []

        while url:
            response = self._session.get(url, params=params, timeout=30)
            if response.status_code >= 400:
                raise GitHubApiError(f"Failed to list repositories: {response.text}")
            repositories.extend(response.json())
            url = response.links.get("next", {}).get("url")
            params = None

        return repositories

    # ------------------------------------------------------------------
    def _request(self, method: str, url: str, *, params: Optional[Mapping[str, object]] = None) -> requests.Response:
        response = self._session.request(method, url, params=params, timeout=30)
        if response.status_code >= 400:
            raise GitHubApiError(f"GitHub API request failed ({response.status_code}): {response.text}")
        return response

    def list_repository_issues(
        self,
        repository: str,
        *,
        state: str = "all",
        labels: Optional[str] = None,
    ) -> Iterable[Mapping[str, object]]:
        url = f"{self._base_url}/repos/{repository}/issues"
        params: Dict[str, object] = {"state": state, "per_page": 100}
        if labels:
            params["labels"] = labels

        while url:
            response = self._request("GET", url, params=params)
            yield from response.json()
            url = response.links.get("next", {}).get("url")
            params = None

    def list_pull_requests(
        self,
        repository: str,
        *,
        state: str = "all",
    ) -> Iterable[Mapping[str, object]]:
        url = f"{self._base_url}/repos/{repository}/pulls"
        params: Dict[str, object] = {"state": state, "per_page": 100}

        while url:
            response = self._request("GET", url, params=params)
            yield from response.json()
            url = response.links.get("next", {}).get("url")
            params = None

    def list_milestones(
        self,
        repository: str,
        *,
        state: str = "all",
    ) -> Iterable[Mapping[str, object]]:
        url = f"{self._base_url}/repos/{repository}/milestones"
        params: Dict[str, object] = {"state": state, "per_page": 100}

        while url:
            response = self._request("GET", url, params=params)
            yield from response.json()
            url = response.links.get("next", {}).get("url")
            params = None


class NotionSyncClient:
    """Coordinates synchronisation between GitHub and Notion."""

    def __init__(
        self,
        notion_api: NotionApi,
        github_client: GitHubClient,
        *,
        database_id: str,
        repo_id_property: str = "Repository ID",
        repo_page_map: Optional[MutableMapping[str, str]] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._notion = notion_api
        self._github = github_client
        self._database_id = database_id
        self._repo_id_property = repo_id_property
        self._repo_page_map = repo_page_map if repo_page_map is not None else {}
        self._logger = logger or LOGGER

    @property
    def repo_page_map(self) -> MutableMapping[str, str]:
        return self._repo_page_map

    def sync_repositories(self, *, dry_run: bool = False) -> SyncSummary:
        summary = SyncSummary()
        try:
            repositories = list(self._github.list_repositories())
        except GitHubApiError as exc:
            self._logger.error("Failed to list repositories from GitHub: %s", exc)
            summary.record_failure({"name": "<github>"}, str(exc))
            return summary

        for repository in repositories:
            repo_identifier = str(repository.get("id"))
            context = repository.get("full_name") or repository.get("name") or repo_identifier
            try:
                self._sync_single_repository(repository, repo_identifier, dry_run=dry_run)
            except NotionApiError as exc:
                self._log_error(context, exc)
                summary.record_failure(repository, str(exc))
                continue
            except Exception as exc:  # pragma: no cover - safety net
                self._log_error(context, exc)
                summary.record_failure(repository, str(exc))
                continue

            summary.record_success()

        return summary

    # ------------------------------------------------------------------
    def _log_error(self, context: str, exc: Exception) -> None:
        self._logger.error("Notion sync failed for %s: %s", context, exc)

    def _sync_single_repository(
        self,
        repository: Mapping[str, object],
        repo_identifier: str,
        *,
        dry_run: bool,
    ) -> None:
        payload = mappers.build_page_payload(
            repository,
            database_id=self._database_id,
            repo_id_property=self._repo_id_property,
        )
        existing_page_id = self._resolve_page_id(repo_identifier, repository)

        if dry_run:
            self._logger.info(
                "Dry run enabled; skipping sync for %s", repository.get("full_name") or repository.get("name")
            )
            return

        if existing_page_id:
            self._notion.update_page(existing_page_id, payload["properties"])
            self._logger.debug("Updated Notion page %s for repo %s", existing_page_id, repo_identifier)
        else:
            page = self._notion.create_page(payload)
            existing_page_id = str(page.get("id"))
            self._repo_page_map[repo_identifier] = existing_page_id
            self._logger.debug("Created Notion page %s for repo %s", existing_page_id, repo_identifier)

        if existing_page_id:
            self._repo_page_map[repo_identifier] = existing_page_id

    def _resolve_page_id(self, repo_identifier: str, repository: Mapping[str, object]) -> Optional[str]:
        page_id = self._repo_page_map.get(repo_identifier)
        if page_id:
            return page_id

        filter_body = {
            "property": self._repo_id_property,
            "rich_text": {
                "equals": repo_identifier,
            },
        }
        result = self._notion.query_database(self._database_id, filter_body)
        results = result.get("results", [])
        if results:
            page_id = str(results[0].get("id"))
            self._repo_page_map[repo_identifier] = page_id
        return page_id
