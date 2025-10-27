#############################################
# Terraform Variable Schema for PR-CYBR Agent
# A-09 (Data Integration Agent)
#
# All variables are populated by Terraform Cloud
# workspace variables and mirrored into GitHub
# Actions via the tfc-sync workflow. No secrets
# are stored in the repository.
#############################################

variable "AGENT_ID" {
  type        = string
  description = "Unique identifier for this agent workspace (e.g., A-09)."
}

variable "PR_CYBR_DOCKER_USER" {
  type        = string
  description = "Shared PR-CYBR DockerHub service account username."
}

variable "PR_CYBR_DOCKER_PASS" {
  type        = string
  sensitive   = true
  description = "Shared PR-CYBR DockerHub service account password."
}

variable "DOCKERHUB_USERNAME" {
  type        = string
  description = "Individual DockerHub username for publishing images."
}

variable "DOCKERHUB_TOKEN" {
  type        = string
  sensitive   = true
  description = "DockerHub personal access token used for CI pushes."
}

variable "GLOBAL_DOMAIN" {
  type        = string
  description = "Root DNS domain for PR-CYBR public services."
}

variable "AGENT_ACTIONS" {
  type        = string
  sensitive   = true
  description = "GitHub Actions token mirrored from Terraform Cloud."
}

variable "NOTION_TOKEN" {
  type        = string
  sensitive   = true
  description = "Shared Notion integration token for API access."
}

variable "NOTION_DISCUSSIONS_ARC_DB_ID" {
  type        = string
  description = "Notion Discussions ARC database ID."
}

variable "NOTION_ISSUES_BACKLOG_DB_ID" {
  type        = string
  description = "Notion Issues Backlog database ID."
}

variable "NOTION_KNOWLEDGE_FILE_DB_ID" {
  type        = string
  description = "Notion Knowledge File database ID."
}

variable "NOTION_PROJECT_BOARD_BACKLOG_DB_ID" {
  type        = string
  description = "Notion Project Board Backlog database ID."
}

variable "NOTION_PR_BACKLOG_DB_ID" {
  type        = string
  description = "Notion Pull Request Backlog database ID."
}

variable "NOTION_TASK_BACKLOG_DB_ID" {
  type        = string
  description = "Notion Task Backlog database ID."
}

variable "NOTION_PAGE_ID" {
  type        = string
  description = "Agent-specific Notion workspace page ID."
}

variable "TFC_TOKEN" {
  type        = string
  sensitive   = true
  description = "Terraform Cloud API token mirrored to GitHub Secrets."
}
