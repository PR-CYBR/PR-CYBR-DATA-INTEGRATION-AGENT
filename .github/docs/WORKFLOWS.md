# Notion Synchronisation Workflows

This repository ships a collection of GitHub Actions workflows that keep the
Notion source-of-truth up to date with GitHub activity. Every workflow uses the
shared `agent_logic.notion_sync.entity_sync_cli` entry point to orchestrate API
calls between GitHub and Notion.

All workflows assume that the target Notion databases expose the following
properties:

| Property name | Type     | Purpose                                             |
| ------------- | -------- | --------------------------------------------------- |
| `Name`        | Title    | Primary title rendered in the database view.        |
| `GitHub ID`   | Text     | Stable identifier used to de-duplicate upserts.     |
| `Status`      | Text     | Human-readable state label (open, closed, merged…). |
| `Details`     | Text     | Rich text summary of metadata captured from GitHub. |
| `URL`         | URL      | Direct link back to the GitHub resource.            |

> **Tip:** When introducing new databases make sure the integration that owns
> `NOTION_TOKEN` has edit permissions and that every property above exists. The
> workflows will emit warnings in the Actions summary when a database identifier
> is missing.

## Notion Task Sync (`.github/workflows/notion-task-sync.yml`)

* **Triggers:** `push` and `pull_request` to any `staging/**` branch, `issues`
events, and manual `workflow_dispatch` executions.
* **Secrets required:** `NOTION_TOKEN`, `GITHUB_TOKEN`,
  `NOTION_TASK_BACKLOG_DB_ID`.
* **Behaviour:** Fetches every issue in the current repository and mirrors the
  ones labelled `task`, `Task`, or `todo` to the configured Notion database.
  The workflow keeps the state in sync (open vs closed), enriches the record
  with assignee and label information, and updates the Notion page if it already
  exists.

## Notion Pull Request Sync (`.github/workflows/notion-pr-sync.yml`)

* **Triggers:** `push` and `pull_request` activity on `staging/**` branches and
  manual `workflow_dispatch` runs.
* **Secrets required:** `NOTION_TOKEN`, `GITHUB_TOKEN`,
  `NOTION_PR_BACKLOG_DB_ID`.
* **Behaviour:** Captures the title, author, base/head branches, status, and
  description for every pull request (open, closed, and merged) and mirrors the
  information into the dedicated Notion database.

## Notion Issues Sync (`.github/workflows/notion-issues-sync.yml`)

* **Triggers:** `push`, `pull_request`, `issues`, and manual `workflow_dispatch`
events focused on the `staging/**` branches.
* **Secrets required:** `NOTION_TOKEN`, `GITHUB_TOKEN`,
  `NOTION_ISSUES_BACKLOG_DB_ID`.
* **Behaviour:** Synchronises all non-pull-request issues, including their
  labels, assignees, and descriptions, into Notion. Closed issues automatically
  update their status field to "Closed".

## Notion Project Sync (`.github/workflows/notion-projects-sync.yml`)

* **Triggers:** `push`, `pull_request`, and manual `workflow_dispatch` events on
  `staging/**` branches.
* **Secrets required:** `NOTION_TOKEN`, `GITHUB_TOKEN`,
  `NOTION_PROJECT_BOARD_BACKLOG_DB_ID`.
* **Behaviour:** Reads the repository milestone catalogue and mirrors each
  milestone (used as a lightweight proxy for project tracking) to the Notion
  projects database, including due dates and the current issue counts.

## Notion Runs Board Sync (`.github/workflows/notion-runs-board-sync.yml`)

* **Triggers:** `workflow_run` (type `completed`) for the Notion synchronisation
  workflows (`Notion Task Sync`, `Notion Pull Request Sync`, `Notion Issues
  Sync`, `Notion Project Sync`, and `Notion Synchronisation Pipeline`).
* **Secrets required:** `NOTION_TOKEN`, `NOTION_DISCUSSIONS_ARC_DB_ID`.
* **Behaviour:** Converts the metadata from the completed workflow run into a
  Notion entry that captures the workflow name, status, triggering event, and
  the branch/commit that executed the run. This provides a durable audit trail
  for cross-agent observability.

## Local execution

To simulate any synchronisation task locally:

```bash
python -m agent_logic.notion_sync.entity_sync_cli \
  --entity <tasks|pull_requests|issues|projects|runs> \
  --database-id "$NOTION_DATABASE" \
  --github-token "$GITHUB_TOKEN" \
  --notion-token "$NOTION_TOKEN" \
  --repository "<owner>/<repo>" \
  --verbose
```

Supply `--dry-run` to inspect the collected records without mutating Notion.
