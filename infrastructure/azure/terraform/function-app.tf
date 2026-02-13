# ==============================================================================
# function-app.tf - Azure Functions リソース定義
# ==============================================================================

# ------------------------------------------------------------------------------
# Storage Account（Function App用）
# ------------------------------------------------------------------------------

resource "azurerm_storage_account" "main" {
  name                     = local.storage_account_name
  location                 = data.azurerm_resource_group.main.location
  resource_group_name      = data.azurerm_resource_group.main.name
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"

  allow_nested_items_to_be_public = false

  network_rules {
    bypass         = ["AzureServices"]
    default_action = "Allow"
  }

  tags = var.tags
}

# ------------------------------------------------------------------------------
# App Service Plan（Consumption）
# ------------------------------------------------------------------------------

resource "azurerm_service_plan" "main" {
  name                = local.app_service_plan_name
  location            = data.azurerm_resource_group.main.location
  resource_group_name = data.azurerm_resource_group.main.name
  os_type             = "Linux"
  sku_name            = var.function_app_sku_name

  tags = var.tags
}

# ------------------------------------------------------------------------------
# Function App
# ------------------------------------------------------------------------------

resource "azurerm_linux_function_app" "main" {
  name                = local.function_app_name
  location            = data.azurerm_resource_group.main.location
  resource_group_name = data.azurerm_resource_group.main.name

  storage_account_name       = azurerm_storage_account.main.name
  storage_account_access_key = azurerm_storage_account.main.primary_access_key
  service_plan_id            = azurerm_service_plan.main.id

  https_only = true

  identity {
    type = "SystemAssigned"
  }

  site_config {
    application_stack {
      python_version = var.python_version
    }

    application_insights_key               = azurerm_application_insights.main.instrumentation_key
    application_insights_connection_string = azurerm_application_insights.main.connection_string

    cors {
      allowed_origins = ["*"]
    }
  }

  app_settings = {
    # 基本設定
    FUNCTIONS_EXTENSION_VERSION    = "~4"
    FUNCTIONS_WORKER_RUNTIME       = "python"
    SCM_DO_BUILD_DURING_DEPLOYMENT = "true"

    # LLMプロバイダー設定
    LLM_PROVIDER = "AZURE"

    # Azure Foundry（Key Vaultから参照）
    AZURE_FOUNDRY_API_KEY         = "@Microsoft.KeyVault(VaultName=${local.key_vault_name};SecretName=AZURE-FOUNDRY-API-KEY)"
    AZURE_FOUNDRY_ENDPOINT        = "@Microsoft.KeyVault(VaultName=${local.key_vault_name};SecretName=AZURE-FOUNDRY-ENDPOINT)"
    AZURE_FOUNDRY_DEPLOYMENT_NAME = "gpt-4o"

    # Document Intelligence（Key Vaultから参照）
    AZURE_DOCUMENT_INTELLIGENCE_KEY      = "@Microsoft.KeyVault(VaultName=${local.key_vault_name};SecretName=AZURE-DOCUMENT-INTELLIGENCE-KEY)"
    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT = "@Microsoft.KeyVault(VaultName=${local.key_vault_name};SecretName=AZURE-DOCUMENT-INTELLIGENCE-ENDPOINT)"

    # OCRプロバイダー設定
    OCR_PROVIDER = "AZURE"

    # タイムアウト設定
    FUNCTION_TIMEOUT_SECONDS = "540"

    # デバッグ設定
    DEBUG = "false"
  }

  tags = var.tags
}
