# ==============================================================================
# cloudwatch.tf - CloudWatch / X-Ray 監視設定
# ==============================================================================
#
# 【概要】
# CloudWatch Logs、CloudWatch Alarms、X-Rayトレーシングの設定を管理します。
#
# 【機能】
# - Lambda/API Gatewayの詳細ログ記録
# - エラー率アラート
# - レスポンスタイムアラート
# - コストアラート
# - X-Ray Service Map（分散トレーシング）
#
# ==============================================================================

# ------------------------------------------------------------------------------
# データソース
# ------------------------------------------------------------------------------

data "aws_caller_identity" "current" {}

# ------------------------------------------------------------------------------
# CloudWatch Alarms: Lambda エラー率
# ------------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  count               = var.enable_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-lambda-errors"
  alarm_description   = "Lambda関数のエラー率が閾値を超えました"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.ic_test_ai.function_name
  }

  alarm_actions = []  # SNSトピックを追加する場合はここに記述

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-lambda-errors-alarm"
    Environment = var.environment
  })
}

# ------------------------------------------------------------------------------
# CloudWatch Alarms: Lambda スロットリング
# ------------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  count               = var.enable_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-lambda-throttles"
  alarm_description   = "Lambda関数のスロットリングが発生しました"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.ic_test_ai.function_name
  }

  alarm_actions = []

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-lambda-throttles-alarm"
    Environment = var.environment
  })
}

# ------------------------------------------------------------------------------
# CloudWatch Alarms: Lambda 実行時間
# ------------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "lambda_duration" {
  count               = var.enable_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-lambda-duration"
  alarm_description   = "Lambda関数の平均実行時間が閾値を超えました"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Average"
  threshold           = 180000  # 3分（ミリ秒）
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.ic_test_ai.function_name
  }

  alarm_actions = []

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-lambda-duration-alarm"
    Environment = var.environment
  })
}

# ------------------------------------------------------------------------------
# CloudWatch Alarms: API Gateway 4xxエラー率
# ------------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "api_gateway_4xx" {
  count               = var.enable_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-api-gateway-4xx"
  alarm_description   = "API Gateway 4xxエラー率が閾値を超えました"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "4XXError"
  namespace           = "AWS/ApiGateway"
  period              = 300
  statistic           = "Sum"
  threshold           = 20
  treat_missing_data  = "notBreaching"

  dimensions = {
    ApiName = aws_api_gateway_rest_api.ic_test_ai.name
    Stage   = aws_api_gateway_stage.prod.stage_name
  }

  alarm_actions = []

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-api-gateway-4xx-alarm"
    Environment = var.environment
  })
}

# ------------------------------------------------------------------------------
# CloudWatch Alarms: API Gateway 5xxエラー率
# ------------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "api_gateway_5xx" {
  count               = var.enable_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-api-gateway-5xx"
  alarm_description   = "API Gateway 5xxエラー率が閾値を超えました"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "5XXError"
  namespace           = "AWS/ApiGateway"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  treat_missing_data  = "notBreaching"

  dimensions = {
    ApiName = aws_api_gateway_rest_api.ic_test_ai.name
    Stage   = aws_api_gateway_stage.prod.stage_name
  }

  alarm_actions = []

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-api-gateway-5xx-alarm"
    Environment = var.environment
  })
}

# ------------------------------------------------------------------------------
# CloudWatch Dashboard
# ------------------------------------------------------------------------------

resource "aws_cloudwatch_dashboard" "ic_test_ai" {
  dashboard_name = "${var.project_name}-${var.environment}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/Lambda", "Invocations", { stat = "Sum", label = "Lambda呼び出し数" }],
            [".", "Errors", { stat = "Sum", label = "Lambdaエラー数" }],
            [".", "Duration", { stat = "Average", label = "Lambda平均実行時間" }]
          ]
          period = 300
          stat   = "Average"
          region = var.region
          title  = "Lambda メトリクス"
          dimensions = {
            FunctionName = [aws_lambda_function.ic_test_ai.function_name]
          }
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ApiGateway", "Count", { stat = "Sum", label = "API Gateway リクエスト数" }],
            [".", "4XXError", { stat = "Sum", label = "4xxエラー" }],
            [".", "5XXError", { stat = "Sum", label = "5xxエラー" }],
            [".", "Latency", { stat = "Average", label = "平均レイテンシ" }]
          ]
          period = 300
          stat   = "Average"
          region = var.region
          title  = "API Gateway メトリクス"
          dimensions = {
            ApiName = [aws_api_gateway_rest_api.ic_test_ai.name]
            Stage   = [aws_api_gateway_stage.prod.stage_name]
          }
        }
      },
      {
        type = "log"
        properties = {
          query = "SOURCE '/aws/lambda/${aws_lambda_function.ic_test_ai.function_name}' | fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc | limit 20"
          region = var.region
          title  = "最近のエラーログ"
        }
      }
    ]
  })
}

# ------------------------------------------------------------------------------
# X-Ray Sampling Rule（サンプリング設定）
# ------------------------------------------------------------------------------

resource "aws_xray_sampling_rule" "ic_test_ai" {
  count         = var.enable_xray_tracing ? 1 : 0
  rule_name     = "${var.project_name}-${var.environment}-sampling"
  priority      = 1000
  version       = 1
  reservoir_size = 1
  fixed_rate    = 0.1  # 10%サンプリング（コスト最適化）

  service_name = "*"
  service_type = "*"
  host         = "*"
  http_method  = "*"
  url_path     = "*"
  resource_arn = "*"

  attributes = {
    Environment = var.environment
  }
}

# ------------------------------------------------------------------------------
# 出力
# ------------------------------------------------------------------------------

output "cloudwatch_dashboard_url" {
  description = "CloudWatchダッシュボードURL"
  value       = "https://console.aws.amazon.com/cloudwatch/home?region=${var.region}#dashboards:name=${aws_cloudwatch_dashboard.ic_test_ai.dashboard_name}"
}

output "xray_service_map_url" {
  description = "X-Ray Service MapURL"
  value       = var.enable_xray_tracing ? "https://console.aws.amazon.com/xray/home?region=${var.region}#/service-map" : "X-Ray disabled"
}
