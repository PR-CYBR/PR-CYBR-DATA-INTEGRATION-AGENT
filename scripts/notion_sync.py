"""Wrapper script to invoke the internal Notion sync CLI."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent_logic.notion_sync.cli import main


if __name__ == "__main__":  # pragma: no cover - convenience wrapper
    raise SystemExit(main())
