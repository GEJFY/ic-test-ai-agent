# ==============================================================================
# apim.tf - Azure API Management リソース定義
# ==============================================================================

# ------------------------------------------------------------------------------
# API Management
# ------------------------------------------------------------------------------

resource "azurerm_api_management" "main" {
  name                = local.apim_name
  location            = data.azurerm_resource_group.main.location
  resource_group_name = data.azurerm_resource_group.main.name
  publisher_email     = var.apim_publisher_email
  publisher_name      = var.apim_publisher_name
  sku_name            = "${var.apim_sku_name}_${var.apim_sku_capacity}"

  identity {
    type = "SystemAssigned"
  }

  protocols {
    enable_http2 = true
  }

  security {
    enable_backend_ssl30  = false
    enable_backend_tls10  = false
    enable_backend_tls11  = false
    enable_frontend_ssl30 = false
    enable_frontend_tls10 = false
    enable_frontend_tls11 = false
  }

  tags = var.tags

  depends_on = [
    azurerm_container_app.main,
    azurerm_application_insights.main,
  ]
}

# ------------------------------------------------------------------------------
# Application Insightsロガー
# ------------------------------------------------------------------------------

resource "azurerm_api_management_logger" "appinsights" {
  name                = "appinsights-logger"
  api_management_name = azurerm_api_management.main.name
  resource_group_name = data.azurerm_resource_group.main.name
  resource_id         = azurerm_application_insights.main.id

  application_insights {
    instrumentation_key = azurerm_application_insights.main.instrumentation_key
  }
}

# ------------------------------------------------------------------------------
# Named Value（バックエンドURL）
# ------------------------------------------------------------------------------

resource "azurerm_api_management_named_value" "backend_url" {
  name                = "backend-function-app-url"
  api_management_name = azurerm_api_management.main.name
  resource_group_name = data.azurerm_resource_group.main.name
  display_name        = "backend-function-app-url"
  value               = "https://${azurerm_container_app.main.ingress[0].fqdn}"
  secret              = false
}

# ------------------------------------------------------------------------------
# バックエンド（Azure Container Apps）
# ------------------------------------------------------------------------------

resource "azurerm_api_management_backend" "functions" {
  name                = "ic-test-ai-backend"
  api_management_name = azurerm_api_management.main.name
  resource_group_name = data.azurerm_resource_group.main.name
  protocol            = "http"
  url                 = "https://${azurerm_container_app.main.ingress[0].fqdn}"
  title               = "IC Test AI Azure Container Apps Backend"
  description         = "内部統制テスト評価AIのバックエンド（Azure Container Apps）"
}

# ------------------------------------------------------------------------------
# API定義
# ------------------------------------------------------------------------------

resource "azurerm_api_management_api" "ic_test_ai" {
  name                  = "ic-test-ai-api"
  api_management_name   = azurerm_api_management.main.name
  resource_group_name   = data.azurerm_resource_group.main.name
  display_name          = "IC Test AI API"
  description           = "内部統制テスト評価AI API"
  path                  = "api"
  protocols             = ["https"]
  subscription_required = true
  revision              = "1"
  service_url           = "https://${azurerm_container_app.main.ingress[0].fqdn}"
}

# ------------------------------------------------------------------------------
# API操作（エンドポイント）
# ------------------------------------------------------------------------------

# POST /api/evaluate
resource "azurerm_api_management_api_operation" "evaluate" {
  operation_id        = "evaluate"
  api_name            = azurerm_api_management_api.ic_test_ai.name
  api_management_name = azurerm_api_management.main.name
  resource_group_name = data.azurerm_resource_group.main.name
  display_name        = "Evaluate Controls"
  method              = "POST"
  url_template        = "/evaluate"
  description         = "テスト項目を評価し、結果を返します"
}

# POST /api/evaluate/submit（非同期）
resource "azurerm_api_management_api_operation" "evaluate_submit" {
  operation_id        = "evaluate-submit"
  api_name            = azurerm_api_management_api.ic_test_ai.name
  api_management_name = azurerm_api_management.main.name
  resource_group_name = data.azurerm_resource_group.main.name
  display_name        = "Submit Evaluation Job"
  method              = "POST"
  url_template        = "/evaluate/submit"
  description         = "評価ジョブを送信し、ジョブIDを返します"
}

# GET /api/evaluate/status/{job_id}
resource "azurerm_api_management_api_operation" "evaluate_status" {
  operation_id        = "evaluate-status"
  api_name            = azurerm_api_management_api.ic_test_ai.name
  api_management_name = azurerm_api_management.main.name
  resource_group_name = data.azurerm_resource_group.main.name
  display_name        = "Get Job Status"
  method              = "GET"
  url_template        = "/evaluate/status/{job_id}"
  description         = "ジョブのステータスを取得"

  template_parameter {
    name     = "job_id"
    type     = "string"
    required = true
  }
}

# GET /api/evaluate/results/{job_id}
resource "azurerm_api_management_api_operation" "evaluate_results" {
  operation_id        = "evaluate-results"
  api_name            = azurerm_api_management_api.ic_test_ai.name
  api_management_name = azurerm_api_management.main.name
  resource_group_name = data.azurerm_resource_group.main.name
  display_name        = "Get Job Results"
  method              = "GET"
  url_template        = "/evaluate/results/{job_id}"
  description         = "ジョブの結果を取得"

  template_parameter {
    name     = "job_id"
    type     = "string"
    required = true
  }
}

# GET /api/health
resource "azurerm_api_management_api_operation" "health" {
  operation_id        = "health"
  api_name            = azurerm_api_management_api.ic_test_ai.name
  api_management_name = azurerm_api_management.main.name
  resource_group_name = data.azurerm_resource_group.main.name
  display_name        = "Health Check"
  method              = "GET"
  url_template        = "/health"
  description         = "ヘルスチェックエンドポイント"
}

# GET /api/config
resource "azurerm_api_management_api_operation" "config" {
  operation_id        = "config"
  api_name            = azurerm_api_management_api.ic_test_ai.name
  api_management_name = azurerm_api_management.main.name
  resource_group_name = data.azurerm_resource_group.main.name
  display_name        = "Config Status"
  method              = "GET"
  url_template        = "/config"
  description         = "設定状態確認エンドポイント"
}

# ------------------------------------------------------------------------------
# API診断ログ設定
# ------------------------------------------------------------------------------

resource "azurerm_api_management_api_diagnostic" "appinsights" {
  identifier               = "applicationinsights"
  api_name                 = azurerm_api_management_api.ic_test_ai.name
  api_management_name      = azurerm_api_management.main.name
  resource_group_name      = data.azurerm_resource_group.main.name
  api_management_logger_id = azurerm_api_management_logger.appinsights.id

  always_log_errors         = true
  log_client_ip             = true
  http_correlation_protocol = "W3C"
  verbosity                 = "information"

  sampling_percentage = 100

  frontend_request {
    headers_to_log = ["X-Correlation-ID", "User-Agent"]
    body_bytes     = 8192
  }

  frontend_response {
    headers_to_log = ["X-Correlation-ID"]
    body_bytes     = 8192
  }

  backend_request {
    headers_to_log = ["X-Correlation-ID"]
    body_bytes     = 8192
  }

  backend_response {
    headers_to_log = ["X-Correlation-ID"]
    body_bytes     = 8192
  }
}

# ------------------------------------------------------------------------------
# サブスクリプション（API Key）
# ------------------------------------------------------------------------------

resource "azurerm_api_management_subscription" "ic_test_ai" {
  api_management_name = azurerm_api_management.main.name
  resource_group_name = data.azurerm_resource_group.main.name
  display_name        = "IC Test AI Subscription"
  api_id              = azurerm_api_management_api.ic_test_ai.id
  state               = "active"
}

# ------------------------------------------------------------------------------
# 製品（Product）
# ------------------------------------------------------------------------------

resource "azurerm_api_management_product" "ic_test_ai" {
  product_id            = "ic-test-ai-product"
  api_management_name   = azurerm_api_management.main.name
  resource_group_name   = data.azurerm_resource_group.main.name
  display_name          = "IC Test AI Product"
  description           = "内部統制テスト評価AI製品"
  subscription_required = true
  approval_required     = false
  published             = true
}

resource "azurerm_api_management_product_api" "ic_test_ai" {
  api_name            = azurerm_api_management_api.ic_test_ai.name
  product_id          = azurerm_api_management_product.ic_test_ai.product_id
  api_management_name = azurerm_api_management.main.name
  resource_group_name = data.azurerm_resource_group.main.name
}
