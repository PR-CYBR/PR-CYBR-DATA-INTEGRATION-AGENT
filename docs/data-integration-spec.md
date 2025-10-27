# A-09 Data Integration Specification

## Terraform Variable Schema
All Terraform configuration is defined in `infra/agent-variables.tf` with workspace values stored securely in Terraform Cloud. The required variables are:

| Name | Purpose |
| --- | --- |
| `AGENT_ACTIONS` | Automation token for CI/CD execution |
| `NOTION_TOKEN` | Secure API token for Notion integration |
| `NOTION_PAGE_ID` | Root Notion page hosting automation dashboards |
| `NOTION_DISCUSSIONS_ARC_DB_ID` | Database ID for archived GitHub discussions |
| `NOTION_ISSUES_BACKLOG_DB_ID` | Database ID for the engineering issues backlog |
| `NOTION_KNOWLEDGE_FILE_DB_ID` | Database ID for knowledge file tracking |
| `NOTION_PROJECT_BOARD_BACKLOG_DB_ID` | Database ID for project board backlog sync |
| `NOTION_TASK_BACKLOG_DB_ID` | Database ID for the task backlog |
| `TFC_TOKEN` | Terraform Cloud API token |
| `DOCKERHUB_USERNAME` | Docker Hub username for publishing images |
| `DOCKERHUB_TOKEN` | Docker Hub access token |

Workspace placeholders live in `infra/variables.tfvars` and mirror the Terraform Cloud workspace variable layout.

## Workflow Overview
The automation surface is composed of three GitHub Actions workflows:

1. **`tfc-sync.yml`** – Runs Terraform commands within `./infra` and injects `TF_VAR_TFC_TOKEN` and `TF_VAR_NOTION_TOKEN` into the environment to match Terraform Cloud expectations.
2. **`notion-sync.yml`** – Validates the Notion synchronisation pipeline in staging and production, propagating `NOTION_TOKEN`/`TFC_TOKEN` secrets to each job.
3. **`data-integration.yml`** – Executes the bidirectional data bridge, uploads the resulting `logs/integration_report.json`, and is scheduled hourly.

The dependency graph is linear: Terraform validation (`tfc-sync`) provisions infrastructure prerequisites, while the data bridge (`data-integration`) depends on working Terraform variables and feeds the Notion synchronisation workflow (`notion-sync`).

## Notion Database Mapping
The bridge uses the following database IDs (exported via `scripts/utils/notion_mappers.py`):

| Logical Database | Environment Variable | Purpose |
| --- | --- | --- |
| Task Backlog | `NOTION_TASK_BACKLOG_DB_ID` | GitHub issues and Notion-originated tasks |
| PR Backlog | `NOTION_PROJECT_BOARD_BACKLOG_DB_ID` | GitHub pull requests awaiting review |
| Issues Backlog | `NOTION_ISSUES_BACKLOG_DB_ID` | Canonical backlog of GitHub issues |
| Discussions Archive | `NOTION_DISCUSSIONS_ARC_DB_ID` | Long-term archive of GitHub discussions |

## Synchronisation Matrix
The synchronisation scripts enforce the following behaviour:

| Source | Target | Action |
| --- | --- | --- |
| GitHub Issues (opened) | Notion Task Backlog | Create/update page with "Backlog" status |
| GitHub Issues (closed) | Notion Task Backlog | Mark linked page status as "Done" |
| GitHub Pull Requests (opened) | Notion PR Backlog | Create/update page with "In Review" status |
| GitHub Pull Requests (merged/closed) | Notion PR Backlog | Mark linked page status as "Done" |
| GitHub Discussions | Notion Discussions Archive | Create/update page and flag as archived |
| Notion Tasks | GitHub Issues | Create linked GitHub issue placeholder |
| Notion Status Changes | GitHub Issues / PRs | Mirror latest status back to GitHub entities |

Each synchronisation maintains a persistent link between GitHub node IDs and Notion page IDs, allowing follow-up status updates to propagate bidirectionally.

## Reporting
Every data bridge execution writes `logs/integration_report.json` capturing:

- UTC timestamp of the run
- Total entities synchronised and error count
- Average sync latency (milliseconds)
- Detailed action log and ID linkage metadata

This file is uploaded by `data-integration.yml` as an artifact for downstream observability.
