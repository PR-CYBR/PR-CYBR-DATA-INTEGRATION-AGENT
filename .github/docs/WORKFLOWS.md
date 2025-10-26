# Workflow Automation Overview

_Last updated: 2024-11-25_

This document describes the GitHub Actions workflows responsible for keeping
the repository in sync with the PR-CYBR Notion workspace.  The workflows are
designed to run on the `work` integration branch family and use the shared
Terraform-provisioned secrets that are made available to the repository.

## Environment prerequisites

Each workflow depends on the following repository secrets and variables:

| Secret / Variable | Purpose |
| --- | --- |
| `NOTION_TOKEN` | OAuth token for the Notion integration with access to the agent databases. |
| `AGENT_ACTIONS` | Fine-grained GitHub token with read access to repository metadata. |
| `NOTION_TASK_BACKLOG_DB_ID` | Target database for task synchronisation. |
| `NOTION_PR_BACKLOG_DB_ID` | Database that mirrors repository pull requests. |
| `NOTION_ISSUES_BACKLOG_DB_ID` | Database used to store GitHub issues. |
| `NOTION_PROJECT_BOARD_BACKLOG_DB_ID` | Database that aggregates GitHub projects and milestones. |
| `NOTION_RUNS_BOARD_DB_ID` | Database used to log CI/CD workflow outcomes. |
| `vars.GITHUB_ORG` (optional) | Organisation slug for enterprise GitHub tokens. |

Run the existing **Verify Environment Variables** workflow after updating any
secrets to ensure the runtime has everything required.

## Workflow catalogue

### Sync Notion Tasks (`.github/workflows/sync-notion-tasks.yml`)

* **Triggers:** `push`, `pull_request`, `issues`, `workflow_dispatch`.
* **Purpose:** synchronises GitHub issues labelled `task` or `tasks` with the
  Notion task backlog database.  Both open and closed tasks are mirrored,
  including their description and GitHub labels.
* **Implementation:** installs the repository dependencies and executes
  `python -m agent_logic.notion_sync.workflow_sync --sync-type tasks` with the
  relevant database identifier.

### Sync Notion Pull Requests (`.github/workflows/sync-notion-pull-requests.yml`)

* **Triggers:** `push`, `pull_request`, `workflow_dispatch`.
* **Purpose:** collects metadata for every pull request in the repository and
  mirrors it to the pull request backlog database, tracking open, merged and
  closed states.
* **Implementation:** runs the workflow sync CLI with `--sync-type pull_requests`.

### Sync Notion Issues (`.github/workflows/sync-notion-issues.yml`)

* **Triggers:** `push`, `pull_request`, `issues`, `workflow_dispatch`.
* **Purpose:** ensures all GitHub issues (excluding PRs) are represented in the
  Notion issues backlog.  Each issue entry includes state, labels, URL and the
  latest description.

### Sync Notion Projects (`.github/workflows/sync-notion-projects.yml`)

* **Triggers:** `push`, `pull_request`, `workflow_dispatch`.
* **Purpose:** synchronises GitHub classic projects and repository milestones
  into a unified Notion project board.  Entries are categorised as either
  `Project` or `Milestone` with their latest state.

### Sync Notion Runs Board (`.github/workflows/sync-notion-runs-board.yml`)

* **Triggers:** `workflow_run` (completed).
* **Purpose:** records the outcome of GitHub Actions workflows in the Notion
  runs board to maintain an audit log of automation activity.  Each entry is
  keyed by run identifier and captures the workflow name, trigger event,
  conclusion and final timestamp.

## Operational notes

* The synchronisation CLI is implemented in
  `src/agent_logic/notion_sync/workflow_sync.py`.  Property names and types can
  be overridden through CLI arguments when the Notion schema differs from the
  defaults (`Name`, `Status`, `GitHub URL`, `Labels`, `Category`, `Last Updated`,
  `Description`, `GitHub ID`).
* Workflows are intentionally idempotent.  The CLI queries the target database
  using the `GitHub ID` property to either update an existing page or create a
  new entry when the identifier is missing.
* When extending the workflow suite, reuse the same CLI to avoid duplicating
  API integration logic and keep the mapping centralised.
* Always run the **Verify Environment Variables** workflow after updating
  repository secrets to confirm the Terraform-managed credentials are present.

