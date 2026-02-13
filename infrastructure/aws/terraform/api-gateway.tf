# ==============================================================================
# api-gateway.tf - AWS API Gateway リソース定義
# ==============================================================================
#
# 【概要】
# API Gateway REST APIでApp Runnerへプロキシします。
# API Key認証、レート制限、CORS対応を提供。
#
# ==============================================================================

# ------------------------------------------------------------------------------
# REST API
# ------------------------------------------------------------------------------

resource "aws_api_gateway_rest_api" "ic_test_ai" {
  name        = "${var.project_name}-${var.environment}-api"
  description = "内部統制テスト評価AI API Gateway (App Runner Backend)"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-api"
    Environment = var.environment
  })
}

# ------------------------------------------------------------------------------
# プロキシリソース（{proxy+}で全パスをApp Runnerに転送）
# ------------------------------------------------------------------------------

resource "aws_api_gateway_resource" "proxy" {
  rest_api_id = aws_api_gateway_rest_api.ic_test_ai.id
  parent_id   = aws_api_gateway_rest_api.ic_test_ai.root_resource_id
  path_part   = "{proxy+}"
}

# ANY /{proxy+} → App Runner
resource "aws_api_gateway_method" "proxy" {
  rest_api_id      = aws_api_gateway_rest_api.ic_test_ai.id
  resource_id      = aws_api_gateway_resource.proxy.id
  http_method      = "ANY"
  authorization    = "NONE"
  api_key_required = true

  request_parameters = {
    "method.request.path.proxy"                = true
    "method.request.header.X-Correlation-ID"   = false
  }
}

resource "aws_api_gateway_integration" "proxy" {
  rest_api_id = aws_api_gateway_rest_api.ic_test_ai.id
  resource_id = aws_api_gateway_resource.proxy.id
  http_method = aws_api_gateway_method.proxy.http_method

  type                    = "HTTP_PROXY"
  integration_http_method = "ANY"
  uri                     = "https://${aws_apprunner_service.ic_test_ai.service_url}/{proxy}"

  request_parameters = {
    "integration.request.path.proxy"              = "method.request.path.proxy"
    "integration.request.header.X-Correlation-ID" = "method.request.header.X-Correlation-ID"
  }

  timeout_milliseconds = 29000
}

# ルートパス（/）→ App Runner
resource "aws_api_gateway_method" "root" {
  rest_api_id      = aws_api_gateway_rest_api.ic_test_ai.id
  resource_id      = aws_api_gateway_rest_api.ic_test_ai.root_resource_id
  http_method      = "ANY"
  authorization    = "NONE"
  api_key_required = true
}

resource "aws_api_gateway_integration" "root" {
  rest_api_id = aws_api_gateway_rest_api.ic_test_ai.id
  resource_id = aws_api_gateway_rest_api.ic_test_ai.root_resource_id
  http_method = aws_api_gateway_method.root.http_method

  type                    = "HTTP_PROXY"
  integration_http_method = "ANY"
  uri                     = "https://${aws_apprunner_service.ic_test_ai.service_url}/"

  timeout_milliseconds = 29000
}

# ------------------------------------------------------------------------------
# CORS設定（OPTIONSメソッド）
# ------------------------------------------------------------------------------

resource "aws_api_gateway_method" "proxy_options" {
  rest_api_id   = aws_api_gateway_rest_api.ic_test_ai.id
  resource_id   = aws_api_gateway_resource.proxy.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "proxy_options" {
  rest_api_id = aws_api_gateway_rest_api.ic_test_ai.id
  resource_id = aws_api_gateway_resource.proxy.id
  http_method = aws_api_gateway_method.proxy_options.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "proxy_options" {
  rest_api_id = aws_api_gateway_rest_api.ic_test_ai.id
  resource_id = aws_api_gateway_resource.proxy.id
  http_method = aws_api_gateway_method.proxy_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "proxy_options" {
  rest_api_id = aws_api_gateway_rest_api.ic_test_ai.id
  resource_id = aws_api_gateway_resource.proxy.id
  http_method = aws_api_gateway_method.proxy_options.http_method
  status_code = aws_api_gateway_method_response.proxy_options.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Correlation-ID'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,POST,PUT,DELETE,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# ------------------------------------------------------------------------------
# API Gateway デプロイ
# ------------------------------------------------------------------------------

resource "aws_api_gateway_deployment" "ic_test_ai" {
  rest_api_id = aws_api_gateway_rest_api.ic_test_ai.id

  depends_on = [
    aws_api_gateway_integration.proxy,
    aws_api_gateway_integration.root,
    aws_api_gateway_integration.proxy_options,
  ]

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.proxy.id,
      aws_api_gateway_method.proxy.id,
      aws_api_gateway_integration.proxy.id,
      aws_api_gateway_method.root.id,
      aws_api_gateway_integration.root.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

# ------------------------------------------------------------------------------
# API Gateway ステージ
# ------------------------------------------------------------------------------

resource "aws_api_gateway_stage" "prod" {
  deployment_id = aws_api_gateway_deployment.ic_test_ai.id
  rest_api_id   = aws_api_gateway_rest_api.ic_test_ai.id
  stage_name    = var.environment

  xray_tracing_enabled = var.enable_xray_tracing

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      resourcePath   = "$context.resourcePath"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
    })
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-stage"
    Environment = var.environment
  })
}

# ------------------------------------------------------------------------------
# API Gateway メソッド設定（スロットリング）
# ------------------------------------------------------------------------------

resource "aws_api_gateway_method_settings" "all" {
  rest_api_id = aws_api_gateway_rest_api.ic_test_ai.id
  stage_name  = aws_api_gateway_stage.prod.stage_name
  method_path = "*/*"

  settings {
    metrics_enabled    = true
    logging_level      = "INFO"
    data_trace_enabled = false

    throttling_burst_limit = var.api_gateway_throttle_burst_limit
    throttling_rate_limit  = var.api_gateway_throttle_rate_limit
  }
}

# ------------------------------------------------------------------------------
# CloudWatch Logsグループ（API Gateway）
# ------------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${var.project_name}-${var.environment}-api"
  retention_in_days = var.cloudwatch_log_retention_days

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-api-gateway-logs"
    Environment = var.environment
  })
}

# ------------------------------------------------------------------------------
# API Key + Usage Plan
# ------------------------------------------------------------------------------

resource "aws_api_gateway_api_key" "ic_test_ai" {
  name        = "${var.project_name}-${var.environment}-api-key"
  description = "内部統制テスト評価AI APIキー"
  enabled     = true

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-api-key"
    Environment = var.environment
  })
}

resource "aws_api_gateway_usage_plan" "ic_test_ai" {
  name        = "${var.project_name}-${var.environment}-usage-plan"
  description = "内部統制テスト評価AI Usage Plan"

  api_stages {
    api_id = aws_api_gateway_rest_api.ic_test_ai.id
    stage  = aws_api_gateway_stage.prod.stage_name
  }

  quota_settings {
    limit  = 10000
    period = "MONTH"
  }

  throttle_settings {
    burst_limit = var.api_gateway_throttle_burst_limit
    rate_limit  = var.api_gateway_throttle_rate_limit
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-usage-plan"
    Environment = var.environment
  })
}

resource "aws_api_gateway_usage_plan_key" "ic_test_ai" {
  key_id        = aws_api_gateway_api_key.ic_test_ai.id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.ic_test_ai.id
}

# ------------------------------------------------------------------------------
# 出力
# ------------------------------------------------------------------------------

output "api_gateway_id" {
  description = "API Gateway REST API ID"
  value       = aws_api_gateway_rest_api.ic_test_ai.id
}

output "api_gateway_url" {
  description = "API Gateway エンドポイントURL"
  value       = aws_api_gateway_stage.prod.invoke_url
}

output "api_key_value" {
  description = "API Key（機密情報）"
  value       = aws_api_gateway_api_key.ic_test_ai.value
  sensitive   = true
}

output "api_key_id" {
  description = "API Key ID"
  value       = aws_api_gateway_api_key.ic_test_ai.id
}
