"""Central definitions for Notion database identifiers used by A-09."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class DatabaseMapping:
    """Mapping details linking GitHub entities to Notion databases."""

    slug: str
    description: str
    database_env_var: str


NOTION_DATABASE_MAPPINGS: Dict[str, DatabaseMapping] = {
    "task_backlog": DatabaseMapping(
        slug="task_backlog",
        description="Issues and tasks captured from GitHub repositories",
        database_env_var="NOTION_TASK_BACKLOG_DB_ID",
    ),
    "pr_backlog": DatabaseMapping(
        slug="pr_backlog",
        description="Pull requests awaiting review or merge",
        database_env_var="NOTION_PROJECT_BOARD_BACKLOG_DB_ID",
    ),
    "discussions_archive": DatabaseMapping(
        slug="discussions_archive",
        description="Archived GitHub discussions for long-term reference",
        database_env_var="NOTION_DISCUSSIONS_ARC_DB_ID",
    ),
    "issues_backlog": DatabaseMapping(
        slug="issues_backlog",
        description="Primary backlog for GitHub issues",
        database_env_var="NOTION_ISSUES_BACKLOG_DB_ID",
    ),
}


__all__ = ["DatabaseMapping", "NOTION_DATABASE_MAPPINGS"]
