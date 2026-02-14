# ==============================================================================
# outputs.tf - Terraform出力定義
# ==============================================================================

# ------------------------------------------------------------------------------
# リソースグループ
# ------------------------------------------------------------------------------

output "resource_group_name" {
  description = "リソースグループ名"
  value       = data.azurerm_resource_group.main.name
}

output "location" {
  description = "デプロイ先リージョン"
  value       = data.azurerm_resource_group.main.location
}

# ------------------------------------------------------------------------------
# Application Insights
# ------------------------------------------------------------------------------

output "app_insights_name" {
  description = "Application Insights名"
  value       = azurerm_application_insights.main.name
}

output "app_insights_connection_string" {
  description = "Application Insights Connection String"
  value       = azurerm_application_insights.main.connection_string
  sensitive   = true
}

output "log_analytics_workspace_id" {
  description = "Log Analytics Workspace ID"
  value       = azurerm_log_analytics_workspace.main.id
}

# ------------------------------------------------------------------------------
# Container Apps
# ------------------------------------------------------------------------------

output "container_app_name" {
  description = "Container App名"
  value       = azurerm_container_app.main.name
}

output "container_app_fqdn" {
  description = "Container AppのFQDN"
  value       = azurerm_container_app.main.ingress[0].fqdn
}

output "container_app_url" {
  description = "Container AppのエンドポイントURL"
  value       = "https://${azurerm_container_app.main.ingress[0].fqdn}"
}

output "acr_login_server" {
  description = "ACRログインサーバー"
  value       = azurerm_container_registry.main.login_server
}

output "acr_name" {
  description = "ACR名"
  value       = azurerm_container_registry.main.name
}

# ------------------------------------------------------------------------------
# Key Vault
# ------------------------------------------------------------------------------

output "key_vault_name" {
  description = "Key Vault名"
  value       = azurerm_key_vault.main.name
}

output "key_vault_uri" {
  description = "Key VaultのURI"
  value       = azurerm_key_vault.main.vault_uri
}

# ------------------------------------------------------------------------------
# API Management（deploy-azure.ymlのAPIM自動取得で使用）
# ------------------------------------------------------------------------------

output "apim_name" {
  description = "API Management名"
  value       = azurerm_api_management.main.name
}

output "apim_gateway_url" {
  description = "API ManagementのゲートウェイURL"
  value       = azurerm_api_management.main.gateway_url
}

output "api_endpoint" {
  description = "APIエンドポイント（VBA/PowerShellで使用）"
  value       = "${azurerm_api_management.main.gateway_url}/api/evaluate"
}

# ------------------------------------------------------------------------------
# Cognitive Services
# ------------------------------------------------------------------------------

output "cognitive_foundry_endpoint" {
  description = "Azure AI Foundry エンドポイント"
  value       = azurerm_cognitive_account.foundry.endpoint
}

output "cognitive_foundry_name" {
  description = "Azure AI Foundry アカウント名"
  value       = azurerm_cognitive_account.foundry.name
}

output "cognitive_di_endpoint" {
  description = "Document Intelligence エンドポイント"
  value       = azurerm_cognitive_account.document_intelligence.endpoint
}

output "cognitive_di_name" {
  description = "Document Intelligence アカウント名"
  value       = azurerm_cognitive_account.document_intelligence.name
}

# ------------------------------------------------------------------------------
# Storage Account（非同期ジョブ用）
# ------------------------------------------------------------------------------

output "storage_account_name" {
  description = "ジョブ用Storage Account名"
  value       = azurerm_storage_account.jobs.name
}
