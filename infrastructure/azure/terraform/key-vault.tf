# ==============================================================================
# key-vault.tf - Azure Key Vault リソース定義
# ==============================================================================

# ------------------------------------------------------------------------------
# Key Vault
# ------------------------------------------------------------------------------

resource "azurerm_key_vault" "main" {
  name                = local.key_vault_name
  location            = data.azurerm_resource_group.main.location
  resource_group_name = data.azurerm_resource_group.main.name
  tenant_id           = data.azurerm_client_config.current.tenant_id

  sku_name = "standard"

  enabled_for_deployment          = false
  enabled_for_disk_encryption     = false
  enabled_for_template_deployment = true
  soft_delete_retention_days      = 90
  purge_protection_enabled        = true

  network_acls {
    bypass         = "AzureServices"
    default_action = "Allow"
  }

  # Container AppのManaged Identityにシークレット読み取り権限付与
  access_policy {
    tenant_id = data.azurerm_client_config.current.tenant_id
    object_id = azurerm_container_app.main.identity[0].principal_id

    secret_permissions = [
      "Get",
      "List",
    ]
  }

  tags = var.tags

  depends_on = [azurerm_container_app.main]
}

# ------------------------------------------------------------------------------
# 診断ログ設定（Log Analyticsに送信）
# ------------------------------------------------------------------------------

resource "azurerm_monitor_diagnostic_setting" "key_vault" {
  name                       = "${local.key_vault_name}-diagnostics"
  target_resource_id         = azurerm_key_vault.main.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  enabled_log {
    category_group = "allLogs"
  }

  metric {
    category = "AllMetrics"
    enabled  = true
  }
}

# ------------------------------------------------------------------------------
# サンプルシークレット（デプロイ後に実際の値を手動で設定）
# ------------------------------------------------------------------------------

resource "azurerm_key_vault_secret" "foundry_api_key" {
  name         = "AZURE-FOUNDRY-API-KEY"
  value        = "REPLACE_WITH_ACTUAL_API_KEY"
  key_vault_id = azurerm_key_vault.main.id
  content_type = "text/plain"

  lifecycle {
    ignore_changes = [value]
  }
}

resource "azurerm_key_vault_secret" "foundry_endpoint" {
  name         = "AZURE-FOUNDRY-ENDPOINT"
  value        = "https://your-foundry-endpoint.openai.azure.com/"
  key_vault_id = azurerm_key_vault.main.id
  content_type = "text/plain"

  lifecycle {
    ignore_changes = [value]
  }
}

resource "azurerm_key_vault_secret" "document_intelligence_key" {
  name         = "AZURE-DOCUMENT-INTELLIGENCE-KEY"
  value        = "REPLACE_WITH_ACTUAL_API_KEY"
  key_vault_id = azurerm_key_vault.main.id
  content_type = "text/plain"

  lifecycle {
    ignore_changes = [value]
  }
}

resource "azurerm_key_vault_secret" "document_intelligence_endpoint" {
  name         = "AZURE-DOCUMENT-INTELLIGENCE-ENDPOINT"
  value        = "https://your-doc-intelligence.cognitiveservices.azure.com/"
  key_vault_id = azurerm_key_vault.main.id
  content_type = "text/plain"

  lifecycle {
    ignore_changes = [value]
  }
}
