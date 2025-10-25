"""Utilities for mapping Notion database entries to the internal domain models.

The module provides high-level helpers that normalize Notion API payloads so that
GitHub issues, pull requests, and project tasks can be synchronized consistently.
It also exposes functions that prepare updates back to Notion and GitHub.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional


@dataclass(frozen=True)
class NotionPropertyNames:
    """Names of the core Notion properties required by the sync pipeline."""

    title: str
    status: str
    assignee: str
    labels: str
    github_url: str
    github_id: str
    github_number: Optional[str] = None


@dataclass(frozen=True)
class NotionRelationConfig:
    """Definition of a relation property used for cross-database links."""

    name: str
    target_database: str
    description: str


@dataclass(frozen=True)
class NotionDatabaseConfig:
    """Full configuration describing how a Notion database is synchronized."""

    slug: str
    name: str
    required_properties: NotionPropertyNames
    relation_properties: Iterable[NotionRelationConfig] = field(default_factory=tuple)


NOTION_DATABASES: Dict[str, NotionDatabaseConfig] = {
    "issues": NotionDatabaseConfig(
        slug="issues",
        name="Engineering Issues",
        required_properties=NotionPropertyNames(
            title="Name",
            status="Status",
            assignee="Assignee",
            labels="Labels",
            github_url="GitHub URL",
            github_id="GitHub ID",
            github_number="GitHub Number",
        ),
        relation_properties=(
            NotionRelationConfig(
                name="Pull Requests",
                target_database="pull_requests",
                description="Connects an issue to any pull requests that address it.",
            ),
        ),
    ),
    "pull_requests": NotionDatabaseConfig(
        slug="pull_requests",
        name="Engineering Pull Requests",
        required_properties=NotionPropertyNames(
            title="Name",
            status="Status",
            assignee="Assignee",
            labels="Labels",
            github_url="GitHub URL",
            github_id="GitHub ID",
            github_number="GitHub Number",
        ),
        relation_properties=(
            NotionRelationConfig(
                name="Related Issue",
                target_database="issues",
                description="Links a pull request back to the primary issue.",
            ),
        ),
    ),
    "project_tasks": NotionDatabaseConfig(
        slug="project_tasks",
        name="Project Tasks",
        required_properties=NotionPropertyNames(
            title="Name",
            status="Status",
            assignee="Assignee",
            labels="Labels",
            github_url="GitHub URL",
            github_id="GitHub ID",
        ),
        relation_properties=(
            NotionRelationConfig(
                name="Related Issue",
                target_database="issues",
                description="Allows tasks to reference an engineering issue.",
            ),
            NotionRelationConfig(
                name="Related Pull Request",
                target_database="pull_requests",
                description="Allows tasks to reference a pull request under review.",
            ),
        ),
    ),
}


def get_database_config(database_slug: str) -> NotionDatabaseConfig:
    """Return the configuration for the requested Notion database."""

    try:
        return NOTION_DATABASES[database_slug]
    except KeyError as exc:  # pragma: no cover - defensive programming branch
        raise ValueError(f"Unknown Notion database slug: {database_slug!r}") from exc


@dataclass
class NotionUser:
    """Simplified representation of a Notion person property entry."""

    id: Optional[str]
    name: Optional[str] = None
    email: Optional[str] = None


@dataclass
class NotionSyncItem:
    """Normalized representation of a Notion page ready for synchronization."""

    database_slug: str
    notion_page_id: str
    title: str
    status: Optional[str]
    assignees: List[NotionUser] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)
    github_url: Optional[str] = None
    github_node_id: Optional[str] = None
    github_number: Optional[int] = None
    relations: Dict[str, List[str]] = field(default_factory=dict)


def _collect_plain_text(blocks: Iterable[Mapping[str, Any]]) -> str:
    """Extract the concatenated plain text from a Notion rich text collection."""

    return "".join(block.get("plain_text", "") for block in blocks)


def _extract_title(property_value: Mapping[str, Any]) -> str:
    return _collect_plain_text(property_value.get("title", []))


def _extract_rich_text(property_value: Mapping[str, Any]) -> Optional[str]:
    text = _collect_plain_text(property_value.get("rich_text", []))
    return text or None


def _extract_status(property_value: Mapping[str, Any]) -> Optional[str]:
    status = property_value.get("status") or {}
    return status.get("name")


def _extract_people(property_value: Mapping[str, Any]) -> List[NotionUser]:
    people = []
    for person in property_value.get("people", []):
        people.append(
            NotionUser(
                id=person.get("id"),
                name=person.get("name"),
                email=(person.get("person") or {}).get("email"),
            )
        )
    return people


def _extract_multi_select(property_value: Mapping[str, Any]) -> List[str]:
    return [item.get("name", "") for item in property_value.get("multi_select", []) if item.get("name")]


def _extract_url(property_value: Mapping[str, Any]) -> Optional[str]:
    return property_value.get("url")


def _extract_number(property_value: Mapping[str, Any]) -> Optional[int]:
    number = property_value.get("number")
    return int(number) if isinstance(number, (int, float)) else None


def _extract_relation_ids(property_value: Mapping[str, Any]) -> List[str]:
    return [rel.get("id") for rel in property_value.get("relation", []) if rel.get("id")]


def parse_notion_page(database_slug: str, page_payload: Mapping[str, Any]) -> NotionSyncItem:
    """Normalize a Notion page payload into the internal :class:`NotionSyncItem`."""

    config = get_database_config(database_slug)
    properties: Mapping[str, Mapping[str, Any]] = page_payload.get("properties", {})

    def get_property(name: str) -> Mapping[str, Any]:
        return properties.get(name, {})

    title = _extract_title(get_property(config.required_properties.title))
    status = _extract_status(get_property(config.required_properties.status))
    assignees = _extract_people(get_property(config.required_properties.assignee))
    labels = _extract_multi_select(get_property(config.required_properties.labels))
    github_url = _extract_url(get_property(config.required_properties.github_url))
    github_node_id = _extract_rich_text(get_property(config.required_properties.github_id))
    github_number = None
    if config.required_properties.github_number:
        github_number = _extract_number(get_property(config.required_properties.github_number))

    relations: Dict[str, List[str]] = {}
    for relation_config in config.relation_properties:
        relations[relation_config.name] = _extract_relation_ids(get_property(relation_config.name))

    return NotionSyncItem(
        database_slug=database_slug,
        notion_page_id=page_payload.get("id", ""),
        title=title,
        status=status,
        assignees=assignees,
        labels=labels,
        github_url=github_url,
        github_node_id=github_node_id,
        github_number=github_number,
        relations=relations,
    )


def _build_title_payload(title: str) -> Dict[str, Any]:
    return {"title": [{"text": {"content": title}}]}


def _build_status_payload(status: str) -> Dict[str, Any]:
    return {"status": {"name": status}}


def _build_people_payload(assignees: Iterable[NotionUser]) -> Dict[str, Any]:
    people = [{"id": person.id} for person in assignees if person.id]
    return {"people": people}


def _build_multi_select_payload(labels: Iterable[str]) -> Dict[str, Any]:
    return {"multi_select": [{"name": label} for label in labels]}


def _build_url_payload(url: str) -> Dict[str, Any]:
    return {"url": url}


def _build_rich_text_payload(content: str) -> Dict[str, Any]:
    return {"rich_text": [{"text": {"content": content}}]}


def _build_number_payload(number: int) -> Dict[str, Any]:
    return {"number": number}


def _build_relation_payload(relation_ids: Iterable[str]) -> Dict[str, Any]:
    return {"relation": [{"id": relation_id} for relation_id in relation_ids if relation_id]}


def build_notion_update_payload(item: NotionSyncItem) -> Dict[str, Any]:
    """Create a Notion property payload from a :class:`NotionSyncItem`."""

    config = get_database_config(item.database_slug)
    properties: MutableMapping[str, Any] = {}

    if item.title:
        properties[config.required_properties.title] = _build_title_payload(item.title)
    if item.status:
        properties[config.required_properties.status] = _build_status_payload(item.status)
    if item.assignees:
        properties[config.required_properties.assignee] = _build_people_payload(item.assignees)
    if item.labels:
        properties[config.required_properties.labels] = _build_multi_select_payload(item.labels)
    if item.github_url:
        properties[config.required_properties.github_url] = _build_url_payload(item.github_url)
    if item.github_node_id:
        properties[config.required_properties.github_id] = _build_rich_text_payload(item.github_node_id)
    if config.required_properties.github_number and item.github_number is not None:
        properties[config.required_properties.github_number] = _build_number_payload(item.github_number)

    for relation_config in config.relation_properties:
        relation_ids = item.relations.get(relation_config.name)
        if relation_ids:
            properties[relation_config.name] = _build_relation_payload(relation_ids)

    return {"properties": dict(properties)}


def build_notion_url(notion_page_id: str) -> str:
    """Return the canonical Notion URL for the provided page identifier."""

    sanitized = notion_page_id.replace("-", "")
    return f"https://www.notion.so/{sanitized}"
