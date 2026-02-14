# ==============================================================================
# storage.tf - Azure Storage リソース定義（非同期ジョブ処理用）
# ==============================================================================

resource "azurerm_storage_account" "jobs" {
  name                     = lower(replace("st${var.project_name}jobs${substr(local.suffix, 0, 6)}", "-", ""))
  resource_group_name      = data.azurerm_resource_group.main.name
  location                 = data.azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"

  tags = var.tags
}

# ジョブ追跡テーブル
resource "azurerm_storage_table" "jobs" {
  name                 = "evaluationjobs"
  storage_account_name = azurerm_storage_account.jobs.name
}

# ジョブキュー
resource "azurerm_storage_queue" "jobs" {
  name                 = "evaluation-queue"
  storage_account_name = azurerm_storage_account.jobs.name
}
