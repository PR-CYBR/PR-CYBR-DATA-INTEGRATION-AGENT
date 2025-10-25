# Notion Sync Data Mapping

This reference documents how the Notion ↔︎ GitHub synchronization script expects each database and property to be structured. The mapping mirrors the logic implemented in `src/integrations/notion/mappers.py` and should be kept in sync with that module.

## Database Overview

| Database | Purpose | Required Properties | Relation Properties |
| --- | --- | --- | --- |
| **Engineering Issues** (`issues`) | Tracks issues imported from GitHub repositories. | `Name` (Title), `Status` (Status), `Assignee` (People), `Labels` (Multi-select), `GitHub URL` (URL), `GitHub ID` (Rich text), `GitHub Number` (Number) | `Pull Requests` → Engineering Pull Requests |
| **Engineering Pull Requests** (`pull_requests`) | Mirrors pull requests that are moving through review. | `Name` (Title), `Status` (Status), `Assignee` (People), `Labels` (Multi-select), `GitHub URL` (URL), `GitHub ID` (Rich text), `GitHub Number` (Number) | `Related Issue` → Engineering Issues |
| **Project Tasks** (`project_tasks`) | Internal tasks that may reference GitHub artifacts. | `Name` (Title), `Status` (Status), `Assignee` (People), `Labels` (Multi-select), `GitHub URL` (URL), `GitHub ID` (Rich text) | `Related Issue` → Engineering Issues, `Related Pull Request` → Engineering Pull Requests |

- **Title**: Always stored in the Notion `title` property named `Name`.
- **Status**: Stored in the Notion `status` property named `Status`. Column movements on GitHub project boards are normalized to these values.
- **Assignee**: Managed through the `people` property named `Assignee` (list of Notion users).
- **Labels**: Backed by a `multi_select` property named `Labels`.
- **GitHub URL**: Written to the `GitHub URL` property (URL type) for direct navigation.
- **GitHub ID**: Stores the GitHub GraphQL node ID as `rich_text` for cross-system traceability.
- **GitHub Number**: Optional but recommended `number` property capturing the repository-level issue or pull request number.

## Relation Properties

| Relation | Source Database | Target Database | Description |
| --- | --- | --- | --- |
| `Pull Requests` | Engineering Issues | Engineering Pull Requests | Connects an issue to any pull requests that address it. |
| `Related Issue` | Engineering Pull Requests | Engineering Issues | Links a pull request back to the primary issue. |
| `Related Issue` | Project Tasks | Engineering Issues | Allows tasks to reference an engineering issue. |
| `Related Pull Request` | Project Tasks | Engineering Pull Requests | Allows tasks to reference a pull request under review. |

All relation properties are stored as Notion relation property types where the value is the target page ID. The sync script preserves existing relations and will append or replace entries based on the data received from GitHub events.

## Traceability Fields

The sync process records the following identifiers:

- **`github_number`** – Numeric identifier from GitHub (issue or pull request number) persisted to the `GitHub Number` property when available.
- **`github_node_id`** – Global GraphQL node identifier persisted to the `GitHub ID` property.
- **`notion_page_id`** – Primary identifier for the Notion page; echoed in GitHub project card notes to create a backlink.

These identifiers make it possible to reconcile actions between Notion, GitHub Issues/PRs, and GitHub project boards.

## Project Board Status Alignment

GitHub project columns should be mapped to the Notion `Status` values. The helper in `src/integrations/github/project_board.py` accepts a status mapping (e.g., `{ "Todo": "Backlog", "Doing": "In Progress", "Done": "Complete" }`) and translates the column name from webhook payloads into the canonical Notion status. Update the mapping configuration whenever columns or status options change.

## Backlinks to GitHub Project Cards

When a Notion page is created or updated from a GitHub event, the sync process attempts to patch the originating GitHub project card note to include the canonical Notion page URL. This allows team members working in GitHub to jump directly to the synchronized Notion record.

Keep this document current whenever property names, relation structures, or supported databases change.
