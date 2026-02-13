# ==============================================================================
# cloudwatch.tf - CloudWatch / X-Ray 監視設定
# ==============================================================================
#
# 【概要】
# CloudWatch Logs、CloudWatch Alarms、X-Rayトレーシングの設定を管理します。
#
# 【機能】
# - App Runner/API Gatewayの詳細ログ記録
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
# CloudWatch Alarms: App Runner HTTPエラー率
# ------------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "apprunner_errors" {
  count               = var.enable_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-apprunner-errors"
  alarm_description   = "App Runnerの4xx/5xxエラー率が閾値を超えました"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "4xxStatusResponses"
  namespace           = "AWS/AppRunner"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  treat_missing_data  = "notBreaching"

  dimensions = {
    ServiceName = aws_apprunner_service.ic_test_ai.service_name
  }

  alarm_actions = []

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-apprunner-errors-alarm"
    Environment = var.environment
  })
}

# ------------------------------------------------------------------------------
# CloudWatch Alarms: App Runner レスポンス時間
# ------------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "apprunner_latency" {
  count               = var.enable_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-apprunner-latency"
  alarm_description   = "App Runnerの平均レスポンス時間が閾値を超えました"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "RequestLatency"
  namespace           = "AWS/AppRunner"
  period              = 300
  statistic           = "Average"
  threshold           = 180000  # 3分（ミリ秒）
  treat_missing_data  = "notBreaching"

  dimensions = {
    ServiceName = aws_apprunner_service.ic_test_ai.service_name
  }

  alarm_actions = []

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-apprunner-latency-alarm"
    Environment = var.environment
  })
}

# ------------------------------------------------------------------------------
# CloudWatch Alarms: App Runner アクティブインスタンス数
# ------------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "apprunner_instances" {
  count               = var.enable_cloudwatch_alarms ? 1 : 0
  alarm_name          = "${var.project_name}-${var.environment}-apprunner-instances"
  alarm_description   = "App Runnerのアクティブインスタンス数が閾値に達しました"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "ActiveInstances"
  namespace           = "AWS/AppRunner"
  period              = 300
  statistic           = "Maximum"
  threshold           = var.app_runner_max_size
  treat_missing_data  = "notBreaching"

  dimensions = {
    ServiceName = aws_apprunner_service.ic_test_ai.service_name
  }

  alarm_actions = []

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-apprunner-instances-alarm"
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
            ["AWS/AppRunner", "RequestCount", "ServiceName", aws_apprunner_service.ic_test_ai.service_name, { stat = "Sum", label = "リクエスト数" }],
            [".", "4xxStatusResponses", ".", ".", { stat = "Sum", label = "4xxエラー" }],
            [".", "2xxStatusResponses", ".", ".", { stat = "Sum", label = "2xx成功" }]
          ]
          period = 300
          stat   = "Sum"
          region = var.region
          title  = "App Runner リクエストメトリクス"
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/AppRunner", "RequestLatency", "ServiceName", aws_apprunner_service.ic_test_ai.service_name, { stat = "Average", label = "平均レイテンシ" }],
            [".", ".", ".", ".", { stat = "p99", label = "P99レイテンシ" }]
          ]
          period = 300
          stat   = "Average"
          region = var.region
          title  = "App Runner レイテンシ"
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/AppRunner", "ActiveInstances", "ServiceName", aws_apprunner_service.ic_test_ai.service_name, { stat = "Maximum", label = "アクティブインスタンス" }]
          ]
          period = 300
          stat   = "Maximum"
          region = var.region
          title  = "App Runner インスタンス数"
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
