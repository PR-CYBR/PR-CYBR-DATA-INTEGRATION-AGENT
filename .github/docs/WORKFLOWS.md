# Workflow Automation Overview

_Last updated: 2024-06-26_

This repository defines a Notion synchronisation layer that mirrors core
GitHub artefacts into the Codex Notion workspace.  The automation is designed to
follow the branching conventions from the [`spec-bootstrap`][spec-bootstrap]
baseline and integrates with the org-level Terraform-managed secrets.

## Secret and variable configuration

Each workflow expects the Notion database identifiers to be delivered via
repository variables that reference the underlying secrets.  The pattern keeps
the real secret names within Terraform/Secrets Manager while enabling the
workflow to resolve them dynamically:

| Variable name              | Description                                                |
|----------------------------|------------------------------------------------------------|
| `TASK_DB_SECRET_NAME`      | Name of the secret that stores the Notion task DB ID.      |
| `PR_DB_SECRET_NAME`        | Name of the secret that stores the Notion PR DB ID.        |
| `ISSUES_DB_SECRET_NAME`    | Name of the secret that stores the Notion issues DB ID.    |
| `PROJECTS_DB_SECRET_NAME`  | Name of the secret that stores the Notion projects DB ID.  |
| `RUNS_BOARD_SECRET_NAME`   | Name of the secret that stores the Notion runs board ID.   |

Each secret referenced by the variables above must contain a valid Notion
database identifier (usually a UUID without hyphens).  The following repository
secrets must also be present:

- `NOTION_TOKEN` – integration token with access to all databases listed above.
- `NOTION_PAGE_ID` – used by legacy tooling (`notion-sync.yml`).
- `GITHUB_TOKEN` – automatically provided by GitHub, used for REST API calls.

Use the existing `verify-env-vars.yml` workflow to confirm that the variables
and secrets are configured before enabling the sync jobs.

## Workflow catalogue

### `Notion Task Sync`

*File*: `.github/workflows/notion-task-sync.yml`

Triggered on pushes and pull requests targeting the `staging/**`, `feature/**`,
or `hotfix/**` branches.  The workflow synchronises GitHub issues labelled as
`task` into the Notion task database (`TASK_DB_SECRET_NAME`).  Each page records
the GitHub identifier, state, labels, assignees, and completion timestamp.

### `Notion PR Sync`

*File*: `.github/workflows/notion-pr-sync.yml`

Runs on all pull request lifecycle events.  It mirrors the repository’s pull
requests into the Notion PR database (`PR_DB_SECRET_NAME`), tracking authors,
merged timestamps, and statuses (`Open`, `Closed`, `Merged`).

### `Notion Issues Sync`

*File*: `.github/workflows/notion-issues-sync.yml`

Triggered on GitHub issue events to ensure the Notion issues database
(`ISSUES_DB_SECRET_NAME`) stays aligned.  The sync includes labels, assignees,
state changes, and closure timestamps.

### `Notion Project Sync`

*File*: `.github/workflows/notion-project-sync.yml`

Runs after pushes to the staging/feature/hotfix branches and on manual request.
The job fetches the repository project boards via the GitHub REST API and
publishes the metadata (state, summary, updated timestamp) into the Notion
projects database (`PROJECTS_DB_SECRET_NAME`).

### `Notion Runs Board Sync`

*File*: `.github/workflows/notion-runs-board-sync.yml`

Captures the outcome of the Notion sync workflows (plus the `verify-env-vars`
sanity check) using the `workflow_run` trigger.  Each completed workflow run is
recorded in the Notion runs board (`RUNS_BOARD_SECRET_NAME`) along with the
workflow name, run attempt title, status, and completion timestamp, providing a
cross-agent audit trail.

## Script entry point

All workflows call `python -m agent_logic.notion_sync.workflow_sync`, a new
utility located in `src/agent_logic/notion_sync/workflow_sync.py`.  The script
supports the five entity types described above and performs the following:

1. Fetches the relevant GitHub data via the REST API using the provided
   `GITHUB_TOKEN`.
2. Upserts pages in the target Notion database by matching on the `GitHub ID`
   property.
3. Logs the synchronisation progress for easier troubleshooting inside GitHub
   Action logs.

Ensure that each target Notion database includes the following properties:

- `Name` (title)
- `GitHub ID` (rich text)
- `State` (status)
- Optional fields referenced in the script (e.g., `Labels`, `Assignees`,
  `Updated At`, `Completed At`, `Merged At`, `Summary`, `Timestamp`, `Run ID`).

If a property is missing, the script simply skips the update for that field.

[spec-bootstrap]: https://github.com/PR-CYBR/spec-bootstrap/
