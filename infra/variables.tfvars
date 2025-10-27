#############################################
# Terraform Cloud Variable Reference Template
#
# This file documents the one-to-one mapping
# between Terraform Cloud workspace variables
# and the root module inputs consumed by this
# agent. Values MUST be supplied by Terraform
# Cloud; never populate secrets locally.
#############################################

# --- Agent Identity ---
AGENT_ID       = "var.AGENT_ID"
NOTION_PAGE_ID = "var.NOTION_PAGE_ID"

# --- Docker / Container Registry ---
PR_CYBR_DOCKER_USER = "var.PR_CYBR_DOCKER_USER"
PR_CYBR_DOCKER_PASS = "var.PR_CYBR_DOCKER_PASS"
DOCKERHUB_USERNAME  = "var.DOCKERHUB_USERNAME"
DOCKERHUB_TOKEN     = "var.DOCKERHUB_TOKEN"

# --- Global Settings ---
GLOBAL_DOMAIN = "var.GLOBAL_DOMAIN"

# --- Automation Tokens ---
AGENT_ACTIONS = "var.AGENT_ACTIONS"
NOTION_TOKEN  = "var.NOTION_TOKEN"
TFC_TOKEN     = "var.TFC_TOKEN"

# --- Notion Databases ---
NOTION_DISCUSSIONS_ARC_DB_ID       = "var.NOTION_DISCUSSIONS_ARC_DB_ID"
NOTION_ISSUES_BACKLOG_DB_ID        = "var.NOTION_ISSUES_BACKLOG_DB_ID"
NOTION_KNOWLEDGE_FILE_DB_ID        = "var.NOTION_KNOWLEDGE_FILE_DB_ID"
NOTION_PROJECT_BOARD_BACKLOG_DB_ID = "var.NOTION_PROJECT_BOARD_BACKLOG_DB_ID"
NOTION_PR_BACKLOG_DB_ID            = "var.NOTION_PR_BACKLOG_DB_ID"
NOTION_TASK_BACKLOG_DB_ID          = "var.NOTION_TASK_BACKLOG_DB_ID"
