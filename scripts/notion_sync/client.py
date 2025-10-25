"""Notion client abstractions with retry support."""
from __future__ import annotations

from typing import Any, Dict

from notion_client import Client
from notion_client.errors import APIResponseError
import structlog
from tenacity import RetryError, Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from .mappers import PageOperation


class NotionSyncClient:
    """A thin wrapper around the official Notion SDK with retries."""

    def __init__(self, token: str, logger: structlog.BoundLogger):
        self._client = Client(auth=token)
        self._logger = logger.bind(component="notion_client")

    def _call_with_retry(self, func, *args, **kwargs):
        retrying = Retrying(
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type(APIResponseError),
            reraise=True,
        )
        try:
            for attempt in retrying:
                with attempt:
                    return func(*args, **kwargs)
        except RetryError as exc:  # pragma: no cover - defensive logging path
            self._logger.error("notion_api_retry_failed", error=str(exc.last_attempt.exception()))
            raise

    def _find_page_by_github_id(self, operation: PageOperation) -> str | None:
        if not operation.github_id:
            return None
        try:
            response = self._call_with_retry(
                self._client.databases.query,
                **{
                    "database_id": operation.database_id,
                    "filter": {
                        "property": "GitHub ID",
                        "rich_text": {"equals": operation.github_id},
                    },
                    "page_size": 1,
                },
            )
        except APIResponseError as error:
            self._logger.warning(
                "notion_database_query_failed",
                github_id=operation.github_id,
                error_code=getattr(error, "code", "unknown"),
                message=str(error),
            )
            raise
        results = response.get("results", [])
        if results:
            page_id = results[0]["id"]
            self._logger.debug("existing_page_found", github_id=operation.github_id, page_id=page_id)
            return page_id
        return None

    def _create_page(self, operation: PageOperation) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "parent": {"database_id": operation.database_id},
            "properties": operation.properties,
        }
        if operation.children:
            payload["children"] = operation.children
        self._logger.info("creating_notion_page", github_id=operation.github_id)
        return self._call_with_retry(self._client.pages.create, **payload)

    def _update_page(self, page_id: str, operation: PageOperation) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "page_id": page_id,
            "properties": operation.properties,
        }
        if operation.children is not None:
            payload["children"] = operation.children
        self._logger.info("updating_notion_page", github_id=operation.github_id, page_id=page_id)
        return self._call_with_retry(self._client.pages.update, **payload)

    def upsert(self, operation: PageOperation) -> Dict[str, Any]:
        """Create or update a Notion page based on the supplied operation."""
        page_id = operation.page_id or self._find_page_by_github_id(operation)
        if page_id:
            return self._update_page(page_id, operation)
        return self._create_page(operation)


__all__ = ["NotionSyncClient"]
