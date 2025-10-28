output "agent_sync_status" {
  description = "Human-readable confirmation of baseline initialization."
  value       = "Agent ${var.AGENT_ID} baseline loaded with Notion ${var.NOTION_PAGE_ID}"
}

output "validation_timestamp" {
  description = "When the validation resource last reconciled."
  value       = timestamp()
}
