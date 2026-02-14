# ==============================================================================
# container-apps.tf - Azure Container Apps リソース定義
# ==============================================================================
#
# 【ネットワークセキュリティ】
# - Inbound:  HTTPS (443) API Management経由のみ許可
# - Outbound: HTTPS (443) Azure AI Foundry / Document Intelligence へのアクセス
# - 認証:     API Management + サブスクリプションキー
# - 暗号化:   TLS 1.2+（トランジット中）、Key Vault（シークレット管理）
#
# ==============================================================================

# ------------------------------------------------------------------------------
# Azure Container Registry (ACR)
# ------------------------------------------------------------------------------

resource "azurerm_container_registry" "main" {
  name                = local.acr_name
  location            = data.azurerm_resource_group.main.location
  resource_group_name = data.azurerm_resource_group.main.name
  sku                 = "Basic"
  admin_enabled       = false

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
# User-Assigned Managed Identity（ACR認証用、循環依存回避）
# ------------------------------------------------------------------------------

resource "azurerm_user_assigned_identity" "container_app" {
  name                = local.user_identity_name
  resource_group_name = data.azurerm_resource_group.main.name
  location            = data.azurerm_resource_group.main.location
  tags                = var.tags
}

# ACR Pull権限をManaged Identityに付与
resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.container_app.principal_id
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
    type         = "SystemAssigned, UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.container_app.id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.container_app.id
  }

  secret {
    name  = "azure-foundry-api-key"
    value = azurerm_cognitive_account.foundry.primary_access_key  # pragma: allowlist secret
  }

  secret {
    name  = "azure-foundry-endpoint"
    value = azurerm_cognitive_account.foundry.endpoint  # pragma: allowlist secret
  }

  secret {
    name  = "azure-di-key"
    value = azurerm_cognitive_account.document_intelligence.primary_access_key  # pragma: allowlist secret
  }

  secret {
    name  = "azure-di-endpoint"
    value = azurerm_cognitive_account.document_intelligence.endpoint  # pragma: allowlist secret
  }

  secret {
    name  = "azure-storage-conn-string"
    value = azurerm_storage_account.jobs.primary_connection_string  # pragma: allowlist secret
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

      # 環境変数（アプリが期待する変数名に合わせる）
      env {
        name  = "LLM_PROVIDER"
        value = "AZURE_FOUNDRY"
      }
      env {
        name  = "OCR_PROVIDER"
        value = "AZURE"
      }
      env {
        name        = "AZURE_FOUNDRY_API_KEY"
        secret_name = "azure-foundry-api-key"  # pragma: allowlist secret
      }
      env {
        name        = "AZURE_FOUNDRY_ENDPOINT"
        secret_name = "azure-foundry-endpoint"  # pragma: allowlist secret
      }
      env {
        name        = "AZURE_DI_KEY"
        secret_name = "azure-di-key"  # pragma: allowlist secret
      }
      env {
        name        = "AZURE_DI_ENDPOINT"
        secret_name = "azure-di-endpoint"  # pragma: allowlist secret
      }
      # Azure Storage（非同期ジョブ処理用）
      env {
        name        = "AZURE_STORAGE_CONNECTION_STRING"
        secret_name = "azure-storage-conn-string"  # pragma: allowlist secret
      }

      # モデル・API設定
      env {
        name  = "AZURE_FOUNDRY_MODEL"
        value = var.azure_foundry_model
      }
      env {
        name  = "AZURE_FOUNDRY_API_VERSION"
        value = var.azure_foundry_api_version
      }

      # オーケストレータ・パフォーマンス設定
      env {
        name  = "USE_GRAPH_ORCHESTRATOR"
        value = "true"
      }
      env {
        name  = "MAX_PLAN_REVISIONS"
        value = "1"
      }
      env {
        name  = "MAX_JUDGMENT_REVISIONS"
        value = "1"
      }
      env {
        name  = "SKIP_PLAN_CREATION"
        value = "false"
      }

      # 非同期ジョブ処理設定
      env {
        name  = "JOB_STORAGE_PROVIDER"
        value = "AZURE"
      }
      env {
        name  = "JOB_QUEUE_PROVIDER"
        value = "AZURE"
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
