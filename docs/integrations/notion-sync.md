# Notion Sync Integration

This guide walks through provisioning the Notion integration that powers the PR-CYBR Data Integration Agent, configuring Terraform Cloud workspace variables, and confirming that the integration has the proper capabilities.

## 1. Provision the Notion Integration

1. Navigate to the [Notion integrations dashboard](https://www.notion.so/my-integrations) and select **+ New integration**.
2. Give the integration a descriptive name such as `PR-CYBR Data Integration Agent`.
3. Set the workspace that owns the databases you plan to sync.
4. Under **Capabilities**, enable the following scopes:
   - **Read content** – required for ingesting pages and database entries.
   - **Update content** – required for writing sync results back to Notion.
   - **Insert content** – required if the agent needs to create new database rows.
   - **Read user information** – optional, but recommended for enriching sync metadata.
5. Click **Submit** and copy the generated internal integration token. This value is only shown once.

> ℹ️ **Share databases with the integration**: In Notion, open each database that should be synchronized, choose **Share**, and grant access to the newly created integration. Record the database IDs from the page URL (the 32-character UUID segment after the last `/`).

## 2. Configure Terraform Cloud Workspace Variables

Terraform Cloud manages the runtime configuration for this repository. Add the following variables to the workspace connected to the Data Integration Agent:

| Name | Type | Sensitive | Value Guidance |
| --- | --- | --- | --- |
| `NOTION_TOKEN` | Terraform (string) | ✅ | Paste the integration token copied from Notion. |
| `NOTION_DATABASE_IDS` | Terraform (HCL) | ❌ | Provide a map of logical database names to their UUIDs. Example below. |

Example HCL for the `NOTION_DATABASE_IDS` variable:

```hcl
{
  pipelines = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  datasets  = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  reports   = "cccccccccccccccccccccccccccccccc"
}
```

Mark `NOTION_TOKEN` as **Sensitive** so Terraform Cloud redacts it in logs. Database IDs are identifiers rather than credentials and can remain non-sensitive, but keep them managed in Terraform Cloud to avoid hard-coding values in the repository.

## 3. Validate Integration Scopes and Connectivity

1. In the Notion integrations dashboard, open the integration and confirm the scopes listed above remain enabled.
2. From any environment that has access to the Terraform Cloud variables, run a smoke test to ensure the integration works:

   ```bash
   export NOTION_TOKEN="$(terraform output -raw notion_token)"
   python -m scripts.notion_smoke_test
   ```

   Replace the smoke test command with your repository's verification script if one exists.
3. Review Terraform Cloud run logs after applying workspace variables to ensure the agent can reach Notion without permission errors.

Once these steps are complete, the Data Integration Agent will have the credentials and database identifiers it needs to synchronize records with Notion.
