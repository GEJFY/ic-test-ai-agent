# ==============================================================================
# cognitive-services.tf - Azure AI サービスリソース定義
# ==============================================================================

# ------------------------------------------------------------------------------
# Azure AI Foundry (Cognitive Services kind=OpenAI)
# ------------------------------------------------------------------------------

resource "azurerm_cognitive_account" "foundry" {
  name                  = "foundry-${var.project_name}-${var.environment}-${local.suffix}"
  location              = data.azurerm_resource_group.main.location
  resource_group_name   = data.azurerm_resource_group.main.name
  kind                  = "OpenAI" # Azure APIの種別名（変更不可）
  sku_name              = "S0"
  custom_subdomain_name = "foundry-${var.project_name}-${var.environment}-${local.suffix}"

  network_acls {
    default_action = "Allow"
  }

  tags = var.tags
}

resource "azurerm_cognitive_deployment" "llm" {
  name                 = var.azure_model
  cognitive_account_id = azurerm_cognitive_account.foundry.id

  model {
    format  = "OpenAI" # Azure APIのモデルフォーマット名（変更不可）
    name    = var.azure_model
    version = var.azure_model_version
  }

  scale {
    type     = "GlobalStandard"
    capacity = var.azure_capacity
  }
}

# ------------------------------------------------------------------------------
# Azure Document Intelligence (Form Recognizer)
# ------------------------------------------------------------------------------

resource "azurerm_cognitive_account" "document_intelligence" {
  name                  = "di-${var.project_name}-${var.environment}-${local.suffix}"
  location              = data.azurerm_resource_group.main.location
  resource_group_name   = data.azurerm_resource_group.main.name
  kind                  = "FormRecognizer"
  sku_name              = "S0"
  custom_subdomain_name = "di-${var.project_name}-${var.environment}-${local.suffix}"

  network_acls {
    default_action = "Allow"
  }

  tags = var.tags
}
