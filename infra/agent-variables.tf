#############################################
# PR-CYBR Data Integration Agent Variables  #
# Managed by Terraform Cloud workspace vars. #
#############################################

variable "AGENT_ACTIONS" {
  description = "Automation token for CI/CD execution"
  type        = string
  sensitive   = true
}

variable "NOTION_TOKEN" {
  description = "Secure API token for Notion integration"
  type        = string
  sensitive   = true
}

variable "NOTION_PAGE_ID" {
  description = "Root Notion page hosting automation dashboards"
  type        = string
}

variable "NOTION_DISCUSSIONS_ARC_DB_ID" {
  description = "Database ID for archived GitHub discussions"
  type        = string
}

variable "NOTION_ISSUES_BACKLOG_DB_ID" {
  description = "Database ID for the engineering issues backlog"
  type        = string
}

variable "NOTION_KNOWLEDGE_FILE_DB_ID" {
  description = "Database ID for knowledge file tracking"
  type        = string
}

variable "NOTION_PROJECT_BOARD_BACKLOG_DB_ID" {
  description = "Database ID for project board backlog sync"
  type        = string
}

variable "NOTION_TASK_BACKLOG_DB_ID" {
  description = "Database ID for the task backlog"
  type        = string
}

variable "TFC_TOKEN" {
  description = "Terraform Cloud API token"
  type        = string
  sensitive   = true
}

variable "DOCKERHUB_USERNAME" {
  description = "Docker Hub username for publishing images"
  type        = string
}

variable "DOCKERHUB_TOKEN" {
  description = "Docker Hub access token"
  type        = string
  sensitive   = true
}
