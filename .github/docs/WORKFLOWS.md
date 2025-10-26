# Workflow Catalogue

This repository now provides dedicated GitHub → Notion synchronisation workflows. Each workflow relies on the shared Python entry point `agent_logic.notion_sync.entity_sync` and mirrors GitHub data into the organisation-wide Notion databases.

All workflows adopt the staging-first branching strategy described in the [`spec-bootstrap`](https://github.com/PR-CYBR/spec-bootstrap/) repository. Push-based automation is scoped to `staging/**` branches to ensure that production remains protected.

> **Before enabling any workflow in production, trigger the `Verify Environment Variables` workflow from the Actions tab to confirm that the required secrets and repository variables are available.**

## Secrets and Repository Variables

| Purpose | Secret | Notes |
| --- | --- | --- |
| Notion API access | `NOTION_TOKEN` | Org-level integration token scoped to the relevant databases. |
| GitHub API access | `AGENT_COLLAB` (fallback to `GITHUB_TOKEN`) | Used for read-only GitHub API calls. |
| Task database | `${AGENT_SECRET_PREFIX}_TASK_DB_ID` | Database identifier for task tracking. |
| Pull request database | `${AGENT_SECRET_PREFIX}_PR_DB_ID` | Database identifier for PR synchronisation. |
| Issue database | `${AGENT_SECRET_PREFIX}_ISSUES_DB_ID` | Database identifier for GitHub issues. |
| Project database | `${AGENT_SECRET_PREFIX}_PROJECTS_DB_ID` | Database identifier for milestones/projects. |
| Runs board | `${AGENT_SECRET_PREFIX}_RUNS_BOARD_ID` | Database identifier used for workflow run audit logs. |

`AGENT_SECRET_PREFIX` is stored as a repository variable (for example `A_07`). Each workflow composes the secret name dynamically using this prefix. Database schemas must expose the following properties: `Name` (title), `GitHub ID` (rich text), `URL` (url), `Status`/`State` (select), and any optional fields referenced below.

## Workflow Overview

### `Notion Task Sync`

* **Trigger:** Push or pull request targeting `staging/**` branches.
* **Data:** GitHub issues labelled with `task` (configurable via the `TASK_LABELS` repository variable).
* **Notion Fields:** Status (select), URL, Assignee (rich text), Labels (multi-select), Completed At (date).
* **Purpose:** Keeps the Notion task board aligned with open and completed GitHub tasks.

### `Notion Pull Request Sync`

* **Trigger:** Pull request events (`opened`, `edited`, `closed`, etc.).
* **Data:** Repository pull requests including authors, reviewers, and merge timestamps.
* **Notion Fields:** Status (select), URL, Author (rich text), Reviewers (rich text), Merged At (date).
* **Purpose:** Mirrors the live pull request lifecycle for stakeholder visibility.

### `Notion Issues Sync`

* **Trigger:** Issue lifecycle events (open, edit, assign, label, close).
* **Data:** GitHub issues excluding pull requests.
* **Notion Fields:** State (select), URL, Assignee (rich text), Labels (multi-select), Closed At (date).
* **Purpose:** Ensures the Notion issue register reflects the canonical GitHub state.

### `Notion Project Sync`

* **Trigger:** Push or pull request targeting `staging/**` branches.
* **Data:** Repository milestones and classic projects (requires the Projects API preview header).
* **Notion Fields:** Status (select), URL, Entity Type (select), Due Date (date for milestones), Run Timestamp (date for project updates).
* **Purpose:** Publishes milestone targets and project status changes into the Notion project tracking database.

### `Notion Runs Board Sync`

* **Trigger:** `workflow_run` (completed) for the automation catalog, including the new Notion workflows and the existing operational pipelines.
* **Data:** Metadata from each completed workflow run (name, attempt number, timestamps, conclusion).
* **Notion Fields:** Workflow Name (rich text), Run Timestamp (date), Conclusion (select), Run Attempt (rich text), URL.
* **Purpose:** Maintains an auditable run log in Notion for cross-agent governance.

## Local Testing

To exercise the synchronisation logic locally:

```bash
export NOTION_TOKEN="<token>"
export GITHUB_TOKEN="<github_token>"
python -m agent_logic.notion_sync.entity_sync --entity tasks --database-id "<database_id>" --github-repo "owner/repo" --dry-run
```

Use the `--dry-run` flag when testing to avoid modifying Notion data. Replace `--entity` with `pull_requests`, `issues`, or `projects` as needed. For `runs` synchronisation, provide the GitHub event payload via `--event-path`.
