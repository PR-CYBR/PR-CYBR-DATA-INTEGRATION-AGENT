# Terraform Cloud workspace variable mappings for the PR-CYBR Data Integration Agent
# Populate these values directly in Terraform Cloud to keep secrets out of source control.

# --- Docker / Registry ---
DOCKERHUB_USERNAME         = "pr-cybr-dockerhub-user"
DOCKERHUB_TOKEN            = "tskey-dockerhub-token-placeholder"
PR_CYBR_DOCKER_USER        = "pr-cybr-service-user"
PR_CYBR_DOCKER_PASS        = "pr-cybr-service-pass-placeholder"
DOCKER_USERNAME            = "integration-test-user"
DOCKER_PASSWORD            = "integration-test-pass-placeholder"

# --- Global Infrastructure URIs ---
GLOBAL_DOMAIN              = "example.pr-cybr.local"
GLOBAL_ELASTIC_URI         = "https://elastic.example.pr-cybr.local"
GLOBAL_GRAFANA_URI         = "https://grafana.example.pr-cybr.local"
GLOBAL_KIBANA_URI          = "https://kibana.example.pr-cybr.local"
GLOBAL_PROMETHEUS_URI      = "https://prometheus.example.pr-cybr.local"

# --- Networking / Security ---
GLOBAL_TAILSCALE_AUTHKEY   = "tskey-placeholder"
GLOBAL_TRAEFIK_ACME_EMAIL  = "admin@example.pr-cybr.local"
GLOBAL_TRAEFIK_ENTRYPOINTS = "websecure"
GLOBAL_ZEROTIER_NETWORK_ID = "0000000000000000"

# --- Agent Tokens ---
AGENT_ACTIONS              = "ghp_agent_actions_placeholder"
AGENT_COLLAB               = "ghp_agent_collab_placeholder"

# --- GitHub / Terraform Cloud Integration ---
GITHUB_TOKEN               = "ghp_github_token_placeholder"
TFC_TOKEN                  = "tfp_token_placeholder"
GITHUB_ORG                 = "pr-cybr"

# --- Notion Integrations ---
NOTION_TOKEN               = "secret_notion_token_placeholder"
NOTION_DATABASE_ID         = "00000000000000000000000000000000"
