# Notion Synchronisation Workflows

This repository ships a suite of GitHub Actions workflows that keep the PR-CYBR Notion workspaces synchronised with the activity that happens in GitHub. Each workflow runs on the standard Codex branch model (feature → staging → production) and is designed to be idempotent, safe to re-run, and observability-friendly.

> **Important:** Before enabling any of the synchronisation jobs, run the [`verify-env-vars.yml`](../workflows/verify-env-vars.yml) workflow to ensure that all required tokens and database identifiers are present. The workflows automatically fall back to dry-run mode when a token is missing, but validation provides earlier feedback.

## Required secrets and variables

All workflows rely on the following repository secrets. They typically map back to Terraform Cloud managed variables named `A_##_<RESOURCE>`:

- `NOTION_TOKEN` – Notion integration token with database read/write access.
- `NOTION_PAGE_ID` – Identifier of the parent status page (used for auditing and validation).
- `NOTION_TASK_DB_ID` – Notion database ID for task items.
- `NOTION_PR_DB_ID` – Notion database ID for pull requests.
- `NOTION_ISSUES_DB_ID` – Notion database ID for GitHub issues.
- `NOTION_PROJECTS_DB_ID` – Notion database ID for project/milestone tracking.
- `NOTION_RUNS_BOARD_ID` – Notion database ID used as the automation runs board.

Optional repository variables can be used to override default property mappings without changing the workflows:

- `NOTION_TASK_LABEL` – Name of the GitHub issue label treated as a task (default: `task`).
- `NOTION_*_ID_PROPERTY` – Override the Notion property that stores the GitHub identifier for each sync domain (`TASK`, `PR`, `ISSUE`, `PROJECT`, `RUN`).

## Workflow catalogue

### `notion-task-sync.yml` – Sync Tasks to Notion

- **Triggers:** `push`, `pull_request`, `issues`, and `workflow_dispatch`.
- **Purpose:** Syncs GitHub issues labelled as tasks into the task database, updating their status, assignees, labels, and backlinks.
- **Implementation details:** Runs the `agent_logic.notion_sync.run_jobs` CLI in `tasks` mode. The job filters issues using the configurable `NOTION_TASK_LABEL` and upserts entries into Notion via the `GitHub ID` property.

### `notion-pr-sync.yml` – Sync Pull Requests to Notion

- **Triggers:** `push`, `pull_request`, and `workflow_dispatch`.
- **Purpose:** Mirrors pull request metadata (state, author, branches, merge status) into the PR database to maintain a deployment audit trail.
- **Implementation details:** Uses the same CLI with the `pull_requests` job to upsert PR records keyed on their GitHub identifier.

### `notion-issues-sync.yml` – Sync Issues to Notion

- **Triggers:** `push`, `issues`, and `workflow_dispatch`.
- **Purpose:** Provides a full mirror of GitHub issues (excluding pull requests) in the Notion issue database, keeping labels, assignees, and timestamps in sync.
- **Implementation details:** Leverages the `issues` job to query the GitHub REST API and upsert Notion pages.

### `notion-project-sync.yml` – Sync Projects to Notion

- **Triggers:** `push`, weekly `schedule` (`0 6 * * 1`), and `workflow_dispatch`.
- **Purpose:** Synchronises repository milestones into the project tracking database, capturing open/closed counts, due dates, and descriptions.
- **Implementation details:** Executes the `projects` job which maps milestones into Notion entries keyed by the milestone identifier.

### `notion-runs-sync.yml` – Sync Workflow Runs to Notion

- **Triggers:** `workflow_run` for all sync jobs and the existing automation suite.
- **Purpose:** Logs the outcome of each workflow run (including failures) in the automation runs board to provide an auditable trail.
- **Implementation details:** Parses the workflow run payload provided by GitHub and records the result in Notion using the `runs` job.

## Observability and failure handling

- Each job installs project dependencies and uses the shared Python CLI, ensuring consistent behaviour across workflows.
- The CLI switches to dry-run mode automatically when `NOTION_TOKEN` is unavailable, preventing accidental failures when secrets have not yet been provisioned.
- Notion API errors are logged but do not halt the entire workflow, allowing subsequent entities to continue syncing.
- To assist with debugging, the CLI emits a JSON summary at the end of each run.

## Extending the workflows

- Additional Notion properties can be mapped by setting the relevant `NOTION_*_ID_PROPERTY` variables or by extending the Python CLI.
- To add new workflow triggers, edit the corresponding YAML file and re-run the `verify-env-vars` workflow to confirm configuration health.
- For new automation domains, add a new job implementation in `src/agent_logic/notion_sync/jobs.py` and register it in the CLI dispatcher.

_Last updated: 2025-10-26_
