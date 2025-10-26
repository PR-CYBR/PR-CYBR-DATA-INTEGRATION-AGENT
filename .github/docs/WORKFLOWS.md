# Workflow Catalogue

This document summarises the automation pipelines that synchronise GitHub activity
with the Notion workspace for the PR-CYBR data integration agent. Each workflow is
implemented in `.github/workflows/` and relies on repository secrets managed by
Terraform Cloud. The jobs inherit the standard branch promotion strategy defined in
[spec-bootstrap](https://github.com/PR-CYBR/spec-bootstrap/) and should run only on
non-production branches unless manually promoted.

> **Secrets and variables**
>
> The workflows expect the global `NOTION_TOKEN` secret and a GitHub token (the
> `AGENT_ACTIONS` secret is preferred, with the fall-back to the default
> `GITHUB_TOKEN`). Database identifiers are retrieved from secrets if available and
> otherwise from repository variables. The recommended variable names are noted in
> each section below. If your environment uses a different secret naming scheme,
> update the repository variables so that the workflow inputs resolve correctly.

## `.github/workflows/notion-task-sync.yml`

Synchronises GitHub issues labelled as tasks with the Notion task database.

- **Triggers:** any `push`, issue activity (open, edit, assignment, labelling), and
  `workflow_dispatch` for ad-hoc runs.
- **Target database:** `${{ secrets.NOTION_TASK_DB_ID }}` or `vars.TASK_DATABASE_ID`.
- **Defaults:** Task label is `task`, unique key property is `GitHub ID`.
- **Behaviour:** Invokes `python -m agent_logic.notion_sync.entity_cli tasks` to
  fetch all labelled issues (excluding pull requests) and mirrors their status,
  assignees, labels, and completion date to Notion.

## `.github/workflows/notion-pr-sync.yml`

Mirrors pull request metadata to the Notion PR database.

- **Triggers:** `pull_request` events (open, sync, reopen, close) and manual
  dispatch.
- **Target database:** `${{ secrets.NOTION_PR_DB_ID }}` or `vars.PR_DATABASE_ID`.
- **Defaults:** Unique key property is `GitHub ID`.
- **Behaviour:** Uses `python -m agent_logic.notion_sync.entity_cli pull-requests`
  to record title, state (`Open`, `Closed`, or `Merged`), authors, reviewers, and
  merge timestamps.

## `.github/workflows/notion-issue-sync.yml`

Keeps the engineering issue database in Notion aligned with GitHub.

- **Triggers:** issue events (open, edit, close, reopen, label/assign changes) and
  manual dispatch.
- **Target database:** `${{ secrets.NOTION_ISSUES_DB_ID }}` or
  `vars.ISSUE_DATABASE_ID`.
- **Behaviour:** Runs `python -m agent_logic.notion_sync.entity_cli issues` and
  captures the state, assignees, labels, and timestamps for every GitHub issue.

## `.github/workflows/notion-project-sync.yml`

Publishes repository milestones to the Notion projects database.

- **Triggers:** any `push` and manual dispatch.
- **Target database:** `${{ secrets.NOTION_PROJECTS_DB_ID }}` or
  `vars.PROJECT_DATABASE_ID`.
- **Behaviour:** Calls `python -m agent_logic.notion_sync.entity_cli projects` to
  enumerate milestones (treating them as project checkpoints) and sync their due
  dates, open/closed issue counts, and descriptions.

## `.github/workflows/notion-runs-board-sync.yml`

Maintains the automation runs ledger in Notion so that every CI/CD execution is
captured for auditability.

- **Triggers:** any completed GitHub Actions workflow run (excluding the runs board
  workflow itself to avoid recursion).
- **Target database:** `${{ secrets.NOTION_RUNS_BOARD_ID }}` or
  `vars.RUNS_DATABASE_ID`.
- **Behaviour:** Executes `python -m agent_logic.notion_sync.entity_cli runs` with
  the workflow payload to persist run metadata (workflow name, run number, status,
  conclusion, and timestamps). This forms the audit trail requested in the task
  directive.

## Operational Notes

1. Run `verify-env-vars.yml` after provisioning new secrets to ensure they are
   accessible to Actions runners.
2. The CLI supports a `--dry-run` flag that can be added in manual dispatches to
   validate the connection without mutating Notion.
3. When new properties are added to Notion databases, update the corresponding
   repository variables (for example `TASK_UNIQUE_PROPERTY`) so the workflows point
   to the correct property names.
4. The runs board workflow relies on the standard `GITHUB_EVENT_PATH` file provided
   during `workflow_run` executions. No additional configuration is required beyond
   the Notion credentials.

Keeping the documentation in `.github/docs/` ensures that future contributors can
quickly audit automation coverage without searching through individual YAML files.
