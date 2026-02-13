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
# Function App
# ------------------------------------------------------------------------------

output "function_app_name" {
  description = "Function App名"
  value       = azurerm_linux_function_app.main.name
}

output "function_app_url" {
  description = "Function AppのエンドポイントURL"
  value       = "https://${azurerm_linux_function_app.main.default_hostname}"
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
