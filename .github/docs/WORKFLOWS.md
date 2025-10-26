# Notion Synchronisation Workflows

This repository contains a suite of GitHub Actions that keep the agent's Notion
databases aligned with GitHub activity. Each workflow can operate in dry-run
mode (set the repository variable `NOTION_SYNC_DRY_RUN` to `true`) while
credentials are being provisioned. When the required secrets are present the
workflows perform live updates to the mapped Notion databases.

All workflows rely on the following shared secrets:

- `NOTION_TOKEN` – API token for the Notion integration.
- `GITHUB_TOKEN` – token with read access to issues, pull requests and
  workflows.

Additional database identifiers are provided via secrets using the
`A_*_DB_ID` naming convention (for example `A_TASK_DB_ID`). The values are
managed centrally in Terraform Cloud and exposed to the repository via secrets.

## Notion Task Sync (`.github/workflows/notion-task-sync.yml`)

- **Triggers**: push (non-main branches), pull request lifecycle events,
  issue lifecycle events, manual dispatch.
- **Purpose**: mirrors GitHub issues labelled as tasks into the Notion task
  database. The workflow filters issues for labels containing the word
  "task" unless a custom label list is provided through the `--task-labels`
  argument.
- **Secrets & Variables**:
  - `A_TASK_DB_ID` – Notion task database ID.
  - `NOTION_SYNC_DRY_RUN` (repository variable, optional) – run without
    writing changes.
- **Implementation**: executes `python -m agent_logic.notion_sync.sync_entities
  tasks` which fetches candidate issues through the GitHub REST API and upserts
  them into Notion via the Notion REST API.

## Notion Pull Request Sync (`.github/workflows/notion-pr-sync.yml`)

- **Triggers**: push (non-main branches), pull request events, manual dispatch.
- **Purpose**: maintains a record of pull requests—including state, author and
  reviewer metadata—in the Notion pull request database.
- **Secrets & Variables**:
  - `A_PR_DB_ID` – Notion pull-request database ID.
  - `NOTION_SYNC_DRY_RUN` – optional dry-run control.
- **Implementation**: runs `python -m agent_logic.notion_sync.sync_entities
  pull_requests` to aggregate PR data and synchronise it to Notion.

## Notion Issue Sync (`.github/workflows/notion-issues-sync.yml`)

- **Triggers**: push (non-main branches), issue lifecycle events, manual
  dispatch.
- **Purpose**: keeps the canonical Notion issue backlog aligned with the state
  of GitHub issues.
- **Secrets & Variables**:
  - `A_ISSUES_DB_ID` – Notion issues database ID.
  - `NOTION_SYNC_DRY_RUN` – optional dry-run control.
- **Implementation**: runs `python -m agent_logic.notion_sync.sync_entities
  issues` to capture issue metadata (labels, assignees, timestamps) and upsert
  it into Notion.

## Notion Project Sync (`.github/workflows/notion-project-sync.yml`)

- **Triggers**: push (non-main branches), GitHub milestone and project events,
  manual dispatch.
- **Purpose**: synchronises repository milestones and classic projects to the
  Notion project tracking database, capturing dates, descriptions and issue
  counts.
- **Secrets & Variables**:
  - `A_PROJECTS_DB_ID` – Notion project database ID.
  - `NOTION_SYNC_DRY_RUN` – optional dry-run control.
- **Implementation**: executes `python -m agent_logic.notion_sync.sync_entities
  projects` which queries milestones and repository projects, then upserts the
  combined dataset into Notion.

## Notion Runs Board Sync (`.github/workflows/notion-runs-sync.yml`)

- **Triggers**: completion of core automation workflows (including the four
  Notion sync pipelines, Terraform, maintenance and Docker builds), manual
  dispatch.
- **Purpose**: provides an audit trail of automation runs in Notion by
  capturing workflow name, status, branch, SHA and timestamps.
- **Secrets & Variables**:
  - `A_RUNS_BOARD_ID` – Notion runs/audit database ID.
  - `NOTION_SYNC_DRY_RUN` – optional dry-run control.
- **Implementation**: when triggered by a `workflow_run` event the workflow
  invokes `python -m agent_logic.notion_sync.sync_entities runs`, which reads
  the GitHub event payload (`GITHUB_EVENT_PATH`) and upserts a single run
  record into Notion.

## Operational Notes

- Execute the existing `Verify Environment Variables` workflow whenever
  secrets are updated to confirm that required credentials are available to the
  pipelines.
- The synchronisation scripts automatically inspect Notion database schemas and
  only populate properties that already exist, reducing the risk of runtime
  errors when database schemas change.
- To onboard a new database, populate the matching secret (`A_*_DB_ID`) and
  allow the automation to run on the next relevant GitHub event.
