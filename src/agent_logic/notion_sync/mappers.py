"""Mapping helpers for building Notion payloads."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Mapping, Optional


def _rich_text(content: Optional[str]) -> Dict[str, List[Dict[str, Dict[str, str]]]]:
    text = content or ""
    return {
        "rich_text": [
            {
                "text": {
                    "content": text,
                }
            }
        ]
    }


def build_page_payload(
    repository: Mapping[str, object],
    *,
    database_id: str,
    repo_id_property: str,
) -> Dict[str, object]:
    """Create the Notion request payload for a repository.

    Parameters
    ----------
    repository:
        Mapping containing GitHub repository metadata. The following keys are
        recognised: ``id``, ``name``, ``full_name``, ``html_url``, ``topics``,
        ``description`` and ``pushed_at``.
    database_id:
        The identifier of the Notion database that should receive the page.
    repo_id_property:
        Name of the property that stores the GitHub repository identifier.
    """

    repo_id = str(repository.get("id", ""))
    name = repository.get("name") or repository.get("full_name") or repo_id
    description = repository.get("description") or ""
    html_url = repository.get("html_url") or ""
    topics = repository.get("topics") or []
    pushed_at = repository.get("pushed_at")

    last_push = None
    if pushed_at:
        if isinstance(pushed_at, datetime):
            last_push = pushed_at.isoformat()
        else:
            last_push = str(pushed_at)

    properties: Dict[str, object] = {
        "Name": {
            "title": [
                {
                    "text": {
                        "content": str(name),
                    }
                }
            ]
        },
        repo_id_property: _rich_text(repo_id),
        "Repository": {
            "url": str(html_url) if html_url else None,
        },
        "Description": _rich_text(description),
    }

    if last_push:
        properties["Last Push"] = {
            "date": {
                "start": last_push,
            }
        }

    if topics:
        properties["Topics"] = {
            "multi_select": [
                {"name": str(topic)}
                for topic in topics
                if str(topic).strip()
            ]
        }

    payload: Dict[str, object] = {
        "parent": {"database_id": database_id},
        "properties": properties,
    }

    return payload
