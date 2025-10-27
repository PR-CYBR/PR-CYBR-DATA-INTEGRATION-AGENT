"""Bidirectional synchronisation helpers between GitHub and Notion."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Optional


@dataclass
class LinkRecord:
    """Relationship between a GitHub entity and a Notion page."""

    github_id: str
    notion_page_id: str
    entity_type: str
    status: str = "Backlog"


@dataclass
class GitHubIssueEvent:
    """Event emitted when a GitHub issue is created or updated."""

    issue_id: str
    number: int
    title: str
    url: str
    state: str  # "open" or "closed"


@dataclass
class GitHubPullRequestEvent:
    """Event emitted when a GitHub pull request changes state."""

    pr_id: str
    number: int
    title: str
    url: str
    state: str  # "open", "merged", "closed"


@dataclass
class GitHubDiscussionEvent:
    """Event emitted when a GitHub discussion is created."""

    discussion_id: str
    title: str
    url: str
    category: Optional[str] = None


@dataclass
class NotionTaskEvent:
    """Event emitted when a Notion task should become a GitHub issue."""

    page_id: str
    title: str
    status: str


@dataclass
class NotionStatusChangeEvent:
    """Event emitted when the status of a Notion item changed."""

    page_id: str
    status: str


@dataclass
class SyncLogEntry:
    """Record of a single synchronisation action."""

    direction: str
    entity_type: str
    identifier: str
    message: str
    latency_ms: float


@dataclass
class SyncReport:
    """Aggregated metrics describing a synchronisation run."""

    generated_at: str
    entities_synced: int
    error_count: int
    average_latency_ms: float
    details: List[SyncLogEntry]
    links: List[LinkRecord]

    def to_dict(self) -> Dict[str, object]:
        """Return the report as a serialisable mapping."""

        return {
            "generated_at": self.generated_at,
            "entities_synced": self.entities_synced,
            "error_count": self.error_count,
            "average_latency_ms": self.average_latency_ms,
            "details": [entry.__dict__ for entry in self.details],
            "links": [link.__dict__ for link in self.links],
        }


class DataBridge:
    """Coordinates GitHub ⇌ Notion synchronisation for A-09."""

    def __init__(self) -> None:
        self._links: Dict[str, LinkRecord] = {}
        self._notion_state: Dict[str, Dict[str, object]] = {
            "task_backlog": {},
            "pr_backlog": {},
            "discussions_archive": {},
        }
        self._log: List[SyncLogEntry] = []
        self._latencies: List[float] = []
        self._errors: List[str] = []

    # ------------------------------------------------------------------
    # GitHub → Notion handlers
    def process_github_issue(self, event: GitHubIssueEvent, *, latency_ms: float = 0.0) -> None:
        """Create or update a Notion task entry based on a GitHub issue."""

        page_id = self._resolve_or_create_page(event.issue_id, "task_backlog")
        status = "Done" if event.state == "closed" else "Backlog"
        self._notion_state["task_backlog"][page_id] = {
            "title": event.title,
            "issue_number": event.number,
            "url": event.url,
            "status": status,
        }
        self._update_link(event.issue_id, page_id, "issue", status)
        self._record("GitHub→Notion", "issue", event.issue_id, f"Synced issue #{event.number}", latency_ms)

    def process_github_pull_request(self, event: GitHubPullRequestEvent, *, latency_ms: float = 0.0) -> None:
        """Create or update a Notion pull-request entry."""

        page_id = self._resolve_or_create_page(event.pr_id, "pr_backlog")
        status = "Done" if event.state in {"merged", "closed"} else "In Review"
        self._notion_state["pr_backlog"][page_id] = {
            "title": event.title,
            "pr_number": event.number,
            "url": event.url,
            "status": status,
        }
        self._update_link(event.pr_id, page_id, "pull_request", status)
        self._record("GitHub→Notion", "pull_request", event.pr_id, f"Synced PR #{event.number}", latency_ms)

    def process_github_discussion(self, event: GitHubDiscussionEvent, *, latency_ms: float = 0.0) -> None:
        """Archive a GitHub discussion inside Notion."""

        page_id = self._resolve_or_create_page(event.discussion_id, "discussions_archive")
        self._notion_state["discussions_archive"][page_id] = {
            "title": event.title,
            "url": event.url,
            "category": event.category,
            "archived": True,
        }
        self._update_link(event.discussion_id, page_id, "discussion", "Archived")
        self._record("GitHub→Notion", "discussion", event.discussion_id, "Archived discussion", latency_ms)

    # ------------------------------------------------------------------
    # Notion → GitHub handlers
    def process_notion_task(self, event: NotionTaskEvent, *, latency_ms: float = 0.0) -> str:
        """Create a GitHub issue for a new Notion task and return its identifier."""

        github_id = f"gh-issue-{event.page_id}"
        self._update_link(github_id, event.page_id, "issue", event.status)
        self._record("Notion→GitHub", "issue", github_id, "Created GitHub issue from Notion task", latency_ms)
        return github_id

    def process_notion_status_change(self, event: NotionStatusChangeEvent, *, latency_ms: float = 0.0) -> None:
        """Propagate a Notion status update back to GitHub."""

        link = self._links.get(event.page_id)
        if not link:
            for candidate in self._links.values():
                if candidate.notion_page_id == event.page_id:
                    link = candidate
                    break
        if not link:
            self._errors.append(f"Missing link for Notion page {event.page_id}")
            return

        link.status = event.status
        self._record("Notion→GitHub", link.entity_type, link.github_id, "Mirrored status change", latency_ms)

    # ------------------------------------------------------------------
    def _resolve_or_create_page(self, github_id: str, bucket: str) -> str:
        """Return an existing Notion page ID or create a synthetic one."""

        for link in self._links.values():
            if link.github_id == github_id:
                return link.notion_page_id

        page_id = f"notion-{github_id}"
        self._links[page_id] = LinkRecord(github_id=github_id, notion_page_id=page_id, entity_type=bucket)
        return page_id

    def _update_link(self, github_id: str, page_id: str, entity_type: str, status: str) -> None:
        """Ensure the internal link map reflects the most recent state."""

        self._links[github_id] = LinkRecord(
            github_id=github_id,
            notion_page_id=page_id,
            entity_type=entity_type,
            status=status,
        )
        self._links[page_id] = self._links[github_id]

    def _record(self, direction: str, entity_type: str, identifier: str, message: str, latency_ms: float) -> None:
        self._log.append(
            SyncLogEntry(
                direction=direction,
                entity_type=entity_type,
                identifier=identifier,
                message=message,
                latency_ms=latency_ms,
            )
        )
        self._latencies.append(latency_ms)

    # ------------------------------------------------------------------
    def build_report(self) -> SyncReport:
        """Compile the in-memory synchronisation data into a report."""

        generated_at = datetime.now(timezone.utc).isoformat()
        average_latency = mean(self._latencies) if self._latencies else 0.0
        links = []
        seen_ids: List[str] = []
        for key, link in self._links.items():
            if key in seen_ids or key != link.github_id:
                continue
            links.append(link)
            seen_ids.append(key)

        return SyncReport(
            generated_at=generated_at,
            entities_synced=len(self._log),
            error_count=len(self._errors),
            average_latency_ms=round(average_latency, 2),
            details=list(self._log),
            links=links,
        )

    @property
    def errors(self) -> List[str]:
        return list(self._errors)

    @property
    def notion_state(self) -> Dict[str, Dict[str, object]]:
        return self._notion_state
