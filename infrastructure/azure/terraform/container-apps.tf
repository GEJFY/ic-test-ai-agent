# ==============================================================================
# container-apps.tf - Azure Container Apps リソース定義
# ==============================================================================

# ------------------------------------------------------------------------------
# Azure Container Registry (ACR)
# ------------------------------------------------------------------------------

resource "azurerm_container_registry" "main" {
  name                = local.acr_name
  location            = data.azurerm_resource_group.main.location
  resource_group_name = data.azurerm_resource_group.main.name
  sku                 = "Basic"
  admin_enabled       = true

  tags = var.tags
}

# ------------------------------------------------------------------------------
# Container Apps Environment
# ------------------------------------------------------------------------------

resource "azurerm_container_app_environment" "main" {
  name                       = local.container_env_name
  location                   = data.azurerm_resource_group.main.location
  resource_group_name        = data.azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  tags = var.tags
}

# ------------------------------------------------------------------------------
# Container App
# ------------------------------------------------------------------------------

resource "azurerm_container_app" "main" {
  name                         = local.container_app_name
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = data.azurerm_resource_group.main.name
  revision_mode                = "Single"

  identity {
    type = "SystemAssigned"
  }

  registry {
    server               = azurerm_container_registry.main.login_server
    username             = azurerm_container_registry.main.admin_username
    password_secret_name = "acr-password"  # pragma: allowlist secret
  }

  secret {
    name  = "acr-password"
    value = azurerm_container_registry.main.admin_password
  }

  ingress {
    external_enabled = true
    target_port      = 8080
    transport        = "auto"

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  template {
    min_replicas = var.container_app_min_replicas
    max_replicas = var.container_app_max_replicas

    container {
      name   = "ic-test-ai-agent"
      image  = "mcr.microsoft.com/k8se/quickstart:latest"
      cpu    = var.container_app_cpu
      memory = var.container_app_memory

      # 環境変数
      env {
        name  = "LLM_PROVIDER"
        value = "AZURE"
      }
      env {
        name  = "OCR_PROVIDER"
        value = "AZURE"
      }
      env {
        name  = "AZURE_FOUNDRY_API_KEY"
        value = "@Microsoft.KeyVault(VaultName=${local.key_vault_name};SecretName=AZURE-FOUNDRY-API-KEY)"
      }
      env {
        name  = "AZURE_FOUNDRY_ENDPOINT"
        value = "@Microsoft.KeyVault(VaultName=${local.key_vault_name};SecretName=AZURE-FOUNDRY-ENDPOINT)"
      }
      env {
        name  = "AZURE_FOUNDRY_DEPLOYMENT_NAME"
        value = "gpt-4o"
      }
      env {
        name  = "AZURE_DOCUMENT_INTELLIGENCE_KEY"
        value = "@Microsoft.KeyVault(VaultName=${local.key_vault_name};SecretName=AZURE-DOCUMENT-INTELLIGENCE-KEY)"
      }
      env {
        name  = "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"
        value = "@Microsoft.KeyVault(VaultName=${local.key_vault_name};SecretName=AZURE-DOCUMENT-INTELLIGENCE-ENDPOINT)"
      }
      env {
        name  = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        value = azurerm_application_insights.main.connection_string
      }
      env {
        name  = "FUNCTION_TIMEOUT_SECONDS"
        value = "540"
      }
      env {
        name  = "DEBUG"
        value = "false"
      }
      env {
        name  = "PORT"
        value = "8080"
      }

      # ヘルスチェック
      liveness_probe {
        transport = "HTTP"
        port      = 8080
        path      = "/health"

        initial_delay    = 10
        interval_seconds = 30
        timeout          = 10
        failure_count_threshold = 3
      }

      readiness_probe {
        transport = "HTTP"
        port      = 8080
        path      = "/health"

        interval_seconds = 10
        timeout          = 5
        failure_count_threshold = 3
      }
    }
  }

  tags = var.tags

  lifecycle {
    ignore_changes = [
      template[0].container[0].image,
    ]
  }
}
