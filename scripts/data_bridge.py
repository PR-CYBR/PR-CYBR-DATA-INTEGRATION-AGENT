"""Command line utility for orchestrating GitHub ⇌ Notion synchronisation flows."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.integrations.data_bridge import (
    DataBridge,
    GitHubDiscussionEvent,
    GitHubIssueEvent,
    GitHubPullRequestEvent,
    NotionStatusChangeEvent,
    NotionTaskEvent,
)

DEFAULT_OUTPUT = Path("logs/integration_report.json")


def _load_events(file_path: Path) -> Iterable[Mapping[str, object]]:
    with file_path.open("r", encoding="utf8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError("Event payload must be a list")
    return payload


def _apply_event(bridge: DataBridge, event: Mapping[str, object]) -> None:
    direction = event.get("direction")
    event_type = event.get("type")
    latency = float(event.get("latency_ms", 0.0))

    if direction == "github":
        if event_type == "issue":
            bridge.process_github_issue(
                GitHubIssueEvent(
                    issue_id=str(event["id"]),
                    number=int(event.get("number", 0)),
                    title=str(event.get("title", "")),
                    url=str(event.get("url", "")),
                    state=str(event.get("state", "open")),
                ),
                latency_ms=latency,
            )
        elif event_type == "pull_request":
            bridge.process_github_pull_request(
                GitHubPullRequestEvent(
                    pr_id=str(event["id"]),
                    number=int(event.get("number", 0)),
                    title=str(event.get("title", "")),
                    url=str(event.get("url", "")),
                    state=str(event.get("state", "open")),
                ),
                latency_ms=latency,
            )
        elif event_type == "discussion":
            bridge.process_github_discussion(
                GitHubDiscussionEvent(
                    discussion_id=str(event["id"]),
                    title=str(event.get("title", "")),
                    url=str(event.get("url", "")),
                    category=event.get("category"),
                ),
                latency_ms=latency,
            )
        else:
            raise ValueError(f"Unsupported GitHub event type: {event_type}")
    elif direction == "notion":
        if event_type == "task":
            bridge.process_notion_task(
                NotionTaskEvent(
                    page_id=str(event["page_id"]),
                    title=str(event.get("title", "")),
                    status=str(event.get("status", "Backlog")),
                ),
                latency_ms=latency,
            )
        elif event_type == "status_change":
            bridge.process_notion_status_change(
                NotionStatusChangeEvent(
                    page_id=str(event["page_id"]),
                    status=str(event.get("status", "Backlog")),
                ),
                latency_ms=latency,
            )
        else:
            raise ValueError(f"Unsupported Notion event type: {event_type}")
    else:
        raise ValueError(f"Unsupported event direction: {direction}")


def _build_demo_payload() -> Iterable[Mapping[str, object]]:
    return [
        {
            "direction": "github",
            "type": "issue",
            "id": "12345",
            "number": 42,
            "title": "Bug: fix sync regression",
            "url": "https://github.com/pr-cybr/issues/42",
            "state": "open",
            "latency_ms": 120.5,
        },
        {
            "direction": "github",
            "type": "pull_request",
            "id": "67890",
            "number": 18,
            "title": "Feature: add Notion mirror",
            "url": "https://github.com/pr-cybr/pull/18",
            "state": "merged",
            "latency_ms": 210.8,
        },
        {
            "direction": "github",
            "type": "discussion",
            "id": "112233",
            "title": "Architecture: Notion sync design",
            "url": "https://github.com/pr-cybr/discussions/112233",
            "category": "Architecture",
            "latency_ms": 90.0,
        },
        {
            "direction": "notion",
            "type": "task",
            "page_id": "abc123",
            "title": "Create onboarding issue",
            "status": "Backlog",
            "latency_ms": 75.2,
        },
        {
            "direction": "notion",
            "type": "status_change",
            "page_id": "notion-12345",
            "status": "In Review",
            "latency_ms": 65.4,
        },
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Execute A-09 data bridge synchronisation")
    parser.add_argument(
        "--events",
        type=Path,
        help="Optional path to a JSON file describing sync events",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Where to write the integration report (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Generate a demonstration payload when no events are provided",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    bridge = DataBridge()

    if args.events:
        events = _load_events(args.events)
    elif args.demo:
        events = _build_demo_payload()
    else:
        parser.error("No events provided; use --events or --demo")

    for event in events:
        _apply_event(bridge, event)

    report = bridge.build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf8")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
