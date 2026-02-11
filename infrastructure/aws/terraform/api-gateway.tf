# ==============================================================================
# api-gateway.tf - AWS API Gateway リソース定義
# ==============================================================================
#
# 【概要】
# 内部統制テスト評価AIのAPI Gateway層を構築します。
#
# 【機能】
# - REST API（HTTP API v2も選択可能）
# - API Key認証
# - レート制限・スロットリング
# - 相関ID管理（X-Correlation-IDヘッダー）
# - CloudWatch Logs統合
# - Lambda統合
# - CORSサポート
#
# ==============================================================================

# ------------------------------------------------------------------------------
# REST API
# ------------------------------------------------------------------------------

resource "aws_api_gateway_rest_api" "ic_test_ai" {
  name        = "${var.project_name}-${var.environment}-api"
  description = "内部統制テスト評価AI API Gateway"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-api"
    Environment = var.environment
  })
}

# ------------------------------------------------------------------------------
# API Gateway リソース（/evaluate）
# ------------------------------------------------------------------------------

resource "aws_api_gateway_resource" "evaluate" {
  rest_api_id = aws_api_gateway_rest_api.ic_test_ai.id
  parent_id   = aws_api_gateway_rest_api.ic_test_ai.root_resource_id
  path_part   = "evaluate"
}

# ------------------------------------------------------------------------------
# API Gateway メソッド（POST /evaluate）
# ------------------------------------------------------------------------------

resource "aws_api_gateway_method" "evaluate_post" {
  rest_api_id   = aws_api_gateway_rest_api.ic_test_ai.id
  resource_id   = aws_api_gateway_resource.evaluate.id
  http_method   = "POST"
  authorization = "NONE"
  api_key_required = true

  request_parameters = {
    "method.request.header.X-Correlation-ID" = false
  }
}

# ------------------------------------------------------------------------------
# Lambda統合
# ------------------------------------------------------------------------------

resource "aws_api_gateway_integration" "evaluate_lambda" {
  rest_api_id = aws_api_gateway_rest_api.ic_test_ai.id
  resource_id = aws_api_gateway_resource.evaluate.id
  http_method = aws_api_gateway_method.evaluate_post.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.ic_test_ai.invoke_arn
}

# ------------------------------------------------------------------------------
# Lambda実行権限
# ------------------------------------------------------------------------------

resource "aws_lambda_permission" "api_gateway_invoke" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ic_test_ai.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.ic_test_ai.execution_arn}/*/*"
}

# ------------------------------------------------------------------------------
# CORS設定（OPTIONSメソッド）
# ------------------------------------------------------------------------------

resource "aws_api_gateway_method" "evaluate_options" {
  rest_api_id   = aws_api_gateway_rest_api.ic_test_ai.id
  resource_id   = aws_api_gateway_resource.evaluate.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "evaluate_options" {
  rest_api_id = aws_api_gateway_rest_api.ic_test_ai.id
  resource_id = aws_api_gateway_resource.evaluate.id
  http_method = aws_api_gateway_method.evaluate_options.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "evaluate_options" {
  rest_api_id = aws_api_gateway_rest_api.ic_test_ai.id
  resource_id = aws_api_gateway_resource.evaluate.id
  http_method = aws_api_gateway_method.evaluate_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "evaluate_options" {
  rest_api_id = aws_api_gateway_rest_api.ic_test_ai.id
  resource_id = aws_api_gateway_resource.evaluate.id
  http_method = aws_api_gateway_method.evaluate_options.http_method
  status_code = aws_api_gateway_method_response.evaluate_options.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Correlation-ID'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,POST,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# ------------------------------------------------------------------------------
# API Gateway デプロイ
# ------------------------------------------------------------------------------

resource "aws_api_gateway_deployment" "ic_test_ai" {
  rest_api_id = aws_api_gateway_rest_api.ic_test_ai.id

  depends_on = [
    aws_api_gateway_integration.evaluate_lambda,
    aws_api_gateway_integration.evaluate_options
  ]

  # 変更を検出するためのトリガー
  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.evaluate.id,
      aws_api_gateway_method.evaluate_post.id,
      aws_api_gateway_integration.evaluate_lambda.id,
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

  # X-Rayトレーシング
  xray_tracing_enabled = var.enable_xray_tracing

  # アクセスログ設定
  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      caller         = "$context.identity.caller"
      user           = "$context.identity.user"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      resourcePath   = "$context.resourcePath"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
      correlationId  = "$context.requestId"
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
  name              = "/aws/apigateway/${aws_api_gateway_rest_api.ic_test_ai.name}"
  retention_in_days = var.cloudwatch_log_retention_days

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-api-gateway-logs"
    Environment = var.environment
  })
}

# ------------------------------------------------------------------------------
# API Key + Usage Plan（レート制限・クォータ管理）
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
  description = "API Gateway エンドポイントURL（VBA/PowerShellで使用）"
  value       = "${aws_api_gateway_stage.prod.invoke_url}/evaluate"
}

output "api_key_value" {
  description = "API Key（機密情報、VBA/PowerShellに設定）"
  value       = aws_api_gateway_api_key.ic_test_ai.value
  sensitive   = true
}

output "api_key_id" {
  description = "API Key ID"
  value       = aws_api_gateway_api_key.ic_test_ai.id
}
