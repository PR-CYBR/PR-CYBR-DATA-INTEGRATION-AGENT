#############################################
# PR-CYBR Agent Terraform Bootstrap (A-09)
#
# This configuration intentionally keeps the
# root module lightweight. All sensitive data
# is sourced dynamically from Terraform Cloud
# workspace variables that are mirrored to the
# GitHub Actions environment via tfc-sync.
#############################################

terraform {
  required_version = ">= 1.5.0"
}

locals {
  agent_identity = {
    id             = var.AGENT_ID
    notion_page_id = var.NOTION_PAGE_ID
  }

  docker_registry = {
    service_user = var.PR_CYBR_DOCKER_USER
    service_pass = var.PR_CYBR_DOCKER_PASS
    username     = var.DOCKERHUB_USERNAME
    token        = var.DOCKERHUB_TOKEN
  }

  notion_databases = {
    discussions_arc       = var.NOTION_DISCUSSIONS_ARC_DB_ID
    issues_backlog        = var.NOTION_ISSUES_BACKLOG_DB_ID
    knowledge_file        = var.NOTION_KNOWLEDGE_FILE_DB_ID
    project_board_backlog = var.NOTION_PROJECT_BOARD_BACKLOG_DB_ID
    pr_backlog            = var.NOTION_PR_BACKLOG_DB_ID
    task_backlog          = var.NOTION_TASK_BACKLOG_DB_ID
  }

  automation_tokens = {
    agent_actions = var.AGENT_ACTIONS
    notion_token  = var.NOTION_TOKEN
    tfc_token     = var.TFC_TOKEN
  }

  global_settings = {
    domain = var.GLOBAL_DOMAIN
  }
}

output "agent_configuration" {
  description = "Structured representation of the agent configuration sourced from Terraform Cloud."
  value = {
    agent_identity   = local.agent_identity
    docker_registry  = local.docker_registry
    notion_databases = local.notion_databases
    automation = {
      agent_actions = local.automation_tokens.agent_actions
      notion_token  = local.automation_tokens.notion_token
    }
    global_settings = local.global_settings
  }
  sensitive = true
}

output "tfc_token_hint" {
  description = "Confirmation that a Terraform Cloud token is provided for downstream automation."
  value       = local.automation_tokens.tfc_token
  sensitive   = true
}
