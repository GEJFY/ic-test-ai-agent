# ==============================================================================
# monitoring.tf - 監視基盤（Log Analytics + Application Insights）
# ==============================================================================

locals {
  suffix                       = substr(md5(var.resource_group_name), 0, 13)
  log_analytics_workspace_name = "log-${var.project_name}-${var.environment}-${local.suffix}"
  app_insights_name            = "appi-${var.project_name}-${var.environment}-${local.suffix}"
  key_vault_name               = "kv-${var.project_name}-${substr(local.suffix, 0, 8)}"
  apim_name                    = "apim-${var.project_name}-${var.environment}-${local.suffix}"
  acr_name                     = lower(replace("acr${var.project_name}${var.environment}${substr(local.suffix, 0, 6)}", "-", ""))
  container_env_name           = "cae-${var.project_name}-${var.environment}-${local.suffix}"
  container_app_name           = "ca-${var.project_name}-${var.environment}-${local.suffix}"
}

# ------------------------------------------------------------------------------
# リソースグループ（既存を参照）
# ------------------------------------------------------------------------------

data "azurerm_resource_group" "main" {
  name = var.resource_group_name
}

# ------------------------------------------------------------------------------
# Log Analytics Workspace
# ------------------------------------------------------------------------------

resource "azurerm_log_analytics_workspace" "main" {
  name                = local.log_analytics_workspace_name
  location            = data.azurerm_resource_group.main.location
  resource_group_name = data.azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = var.log_retention_in_days
  daily_quota_gb      = var.daily_data_cap_in_gb

  tags = var.tags
}

# ------------------------------------------------------------------------------
# Application Insights
# ------------------------------------------------------------------------------

resource "azurerm_application_insights" "main" {
  name                = local.app_insights_name
  location            = data.azurerm_resource_group.main.location
  resource_group_name = data.azurerm_resource_group.main.name
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"
  retention_in_days   = var.log_retention_in_days
  sampling_percentage = 100

  tags = var.tags
}

# ------------------------------------------------------------------------------
# アラートルール: エラー率（5分間で10件以上）
# ------------------------------------------------------------------------------

resource "azurerm_monitor_metric_alert" "error_rate" {
  name                = "${local.app_insights_name}-error-rate-alert"
  resource_group_name = data.azurerm_resource_group.main.name
  scopes              = [azurerm_application_insights.main.id]
  description         = "エラー率が閾値を超えました"
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT5M"

  criteria {
    metric_namespace = "microsoft.insights/components"
    metric_name      = "exceptions/count"
    aggregation      = "Count"
    operator         = "GreaterThan"
    threshold        = 10
  }

  tags = var.tags
}

# ------------------------------------------------------------------------------
# アラートルール: レスポンスタイム（平均3秒以上）
# ------------------------------------------------------------------------------

resource "azurerm_monitor_metric_alert" "response_time" {
  name                = "${local.app_insights_name}-response-time-alert"
  resource_group_name = data.azurerm_resource_group.main.name
  scopes              = [azurerm_application_insights.main.id]
  description         = "レスポンスタイムが閾値を超えました"
  severity            = 3
  frequency           = "PT5M"
  window_size         = "PT15M"

  criteria {
    metric_namespace = "microsoft.insights/components"
    metric_name      = "requests/duration"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 3000
  }

  tags = var.tags
}
