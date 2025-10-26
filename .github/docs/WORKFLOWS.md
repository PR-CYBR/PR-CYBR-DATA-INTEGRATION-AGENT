# Workflow Catalogue

This document summarises the automation responsible for keeping the Notion workspaces in sync with activity from this repository. Each workflow follows the conventions from the [`spec-bootstrap`](https://github.com/PR-CYBR/spec-bootstrap/) reference implementation and is safe to run on any non-production branch.

## Shared Behaviour

* **Runtime** – All synchronisation workflows execute inside Ubuntu runners with Python 3.11 and use the shared script `agent_logic/notion_sync/entity_sync.py` to call the Notion and GitHub REST APIs.
* **Dependencies** – `pip install -r requirements.txt` provides the `requests` library that backs both API clients.
* **Authentication** – Each workflow expects the following secrets or repository variables to be defined:
  * `NOTION_TOKEN` – Organisation-scoped integration token with write access to the required Notion databases.
  * `NOTION_*_DB_ID` – Database identifiers for the respective boards (tasks, pull requests, issues, projects, runs). If the canonical `A_##_*_DB_ID` secrets exist, create repository-level secret aliases with these names to keep the workflow definitions generic.
  * `AGENT_COLLAB` – Preferred GitHub fine-grained token for accessing issues and pull requests. The built-in `GITHUB_TOKEN` is used automatically when the collaboration token is not supplied.
* **Dry Runs** – Any workflow can be launched manually through `workflow_dispatch` for validation. Use the existing `Verify Environment Variables` workflow to confirm all required secrets are available before enabling schedules.

## Workflow Overview

### `Notion Task Sync` (`.github/workflows/notion-task-sync.yml`)
* **Triggers** – `push`, `pull_request`, and `issues` events along with manual dispatches.
* **Scope** – Mirrors GitHub issues labelled `task`/`tasks` into the Notion Project Tasks database and records state transitions between Open and Complete.
* **Secrets** – Requires `NOTION_TOKEN`, `NOTION_TASK_DB_ID` (alias for `A_##_TASK_DB_ID`), and optionally `AGENT_COLLAB`.

### `Notion Pull Request Sync` (`.github/workflows/notion-pr-sync.yml`)
* **Triggers** – `push`, `pull_request`, `issues`, and manual dispatch.
* **Scope** – Captures all pull requests (open, closed, merged) with metadata such as labels and links, mirroring them into the Notion Pull Request tracker.
* **Secrets** – Requires `NOTION_TOKEN`, `NOTION_PR_DB_ID` (alias for `A_##_PR_DB_ID`), and optionally `AGENT_COLLAB`.

### `Notion Issue Sync` (`.github/workflows/notion-issue-sync.yml`)
* **Triggers** – `push`, `pull_request`, `issues`, and manual dispatch.
* **Scope** – Synchronises GitHub issues, including state, labels, URLs, and numeric identifiers, with the Notion Engineering Issues database.
* **Secrets** – Requires `NOTION_TOKEN`, `NOTION_ISSUES_DB_ID` (alias for `A_##_ISSUES_DB_ID`), and optionally `AGENT_COLLAB`.

### `Notion Project Sync` (`.github/workflows/notion-project-sync.yml`)
* **Triggers** – `push`, `pull_request`, `issues`, and manual dispatch.
* **Scope** – Reflects repository milestones back to the Notion Projects board. Due dates are preserved as contextual labels to maintain lightweight status history.
* **Secrets** – Requires `NOTION_TOKEN`, `NOTION_PROJECTS_DB_ID` (alias for `A_##_PROJECTS_DB_ID`), and optionally `AGENT_COLLAB`.

### `Notion Runs Board Sync` (`.github/workflows/notion-runs-board-sync.yml`)
* **Triggers** – `workflow_run` (fires when any automation in this repository completes) and manual dispatch.
* **Scope** – Records workflow execution outcomes, including the run number and conclusion, in the Notion automation log (`RUNS_BOARD_ID`).
* **Secrets** – Requires `NOTION_TOKEN` and `NOTION_RUNS_BOARD_ID` (alias for `A_##_RUNS_BOARD_ID`).

## Implementation Notes

* The synchronisation script performs an upsert by checking for existing Notion pages with matching `GitHub ID` rich text values before deciding to create or update entries.
* Labels in GitHub are mirrored to Notion multi-select properties. No attempt is made to manage Notion people assignments automatically, so those properties are cleared during updates.
* Workflow run entries rely on the `workflow_run` event payload supplied through `GITHUB_EVENT_PATH`. The automation records a single page per run with the naming convention `<workflow name> #<run number>`.
* When adding new GitHub workflows, update `notion-runs-board-sync.yml` so the automation log remains exhaustive.

## Validation

1. Run `Verify Environment Variables` to confirm that each Notion database ID is surfaced through the expected secret or repository variable alias.
2. Trigger the relevant workflow with `workflow_dispatch` to confirm the sync completes successfully. Review the logs for the summary emitted by `entity_sync.py` to ensure items are created or updated as expected.
