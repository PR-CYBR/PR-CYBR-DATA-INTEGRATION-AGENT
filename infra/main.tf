provider "null" {}

resource "null_resource" "agent_validation" {
  triggers = {
    agent_id       = var.AGENT_ID
    notion_page_id = var.NOTION_PAGE_ID
    validated_at   = timestamp()
  }
}
