# ==============================================================================
# cloud-logging.tf - Cloud Logging / Cloud Trace 監視設定
# ==============================================================================
#
# 【概要】
# Cloud Logging、Cloud Monitoring、Cloud Traceの設定を管理します。
#
# 【機能】
# - Cloud Functionsの詳細ログ記録
# - エラー率アラート
# - レスポンスタイムアラート
# - 予算アラート
# - Cloud Trace（分散トレーシング）
#
# ==============================================================================

# ------------------------------------------------------------------------------
# Cloud Logging シンク（ログエクスポート）
# ------------------------------------------------------------------------------

resource "google_logging_project_sink" "cloud_function_errors" {
  name        = "${var.project_name}-${var.environment}-function-errors"
  project     = var.project_id
  destination = "logging.googleapis.com/projects/${var.project_id}/logs/${var.project_name}-${var.environment}-errors"

  filter = <<-EOT
    resource.type="cloud_function"
    severity>=ERROR
    resource.labels.function_name="${google_cloudfunctions2_function.evaluate.name}"
  EOT

  unique_writer_identity = true
}

# ------------------------------------------------------------------------------
# Cloud Monitoring アラート: Cloud Functions エラー率
# ------------------------------------------------------------------------------

resource "google_monitoring_alert_policy" "function_errors" {
  count        = var.enable_monitoring_alerts ? 1 : 0
  project      = var.project_id
  display_name = "${var.project_name}-${var.environment}-function-errors"
  combiner     = "OR"

  conditions {
    display_name = "Cloud Function エラー率が閾値を超えました"

    condition_threshold {
      filter          = "resource.type = \"cloud_function\" AND resource.labels.function_name = \"${google_cloudfunctions2_function.evaluate.name}\" AND metric.type = \"cloudfunctions.googleapis.com/function/execution_count\" AND metric.labels.status != \"ok\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 10

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = []  # 通知チャンネルを追加する場合はここに記述

  alert_strategy {
    auto_close = "1800s"
  }
}

# ------------------------------------------------------------------------------
# Cloud Monitoring アラート: Cloud Functions 実行時間
# ------------------------------------------------------------------------------

resource "google_monitoring_alert_policy" "function_duration" {
  count        = var.enable_monitoring_alerts ? 1 : 0
  project      = var.project_id
  display_name = "${var.project_name}-${var.environment}-function-duration"
  combiner     = "OR"

  conditions {
    display_name = "Cloud Function 平均実行時間が閾値を超えました"

    condition_threshold {
      filter          = "resource.type = \"cloud_function\" AND resource.labels.function_name = \"${google_cloudfunctions2_function.evaluate.name}\" AND metric.type = \"cloudfunctions.googleapis.com/function/execution_times\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 180000  # 3分（ミリ秒）

      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = []

  alert_strategy {
    auto_close = "1800s"
  }
}

# ------------------------------------------------------------------------------
# Cloud Monitoring ダッシュボード
# ------------------------------------------------------------------------------

resource "google_monitoring_dashboard" "ic_test_ai" {
  project        = var.project_id
  dashboard_json = jsonencode({
    displayName = "${var.project_name}-${var.environment}-dashboard"
    mosaicLayout = {
      columns = 12
      tiles = [
        {
          width  = 6
          height = 4
          widget = {
            title = "Cloud Functions 実行回数"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloud_function\" resource.labels.function_name=\"${google_cloudfunctions2_function.evaluate.name}\" metric.type=\"cloudfunctions.googleapis.com/function/execution_count\""
                    aggregation = {
                      alignmentPeriod  = "60s"
                      perSeriesAligner = "ALIGN_RATE"
                    }
                  }
                }
              }]
              yAxis = {
                label = "Executions/sec"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          xPos   = 6
          width  = 6
          height = 4
          widget = {
            title = "Cloud Functions エラー率"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloud_function\" resource.labels.function_name=\"${google_cloudfunctions2_function.evaluate.name}\" metric.type=\"cloudfunctions.googleapis.com/function/execution_count\" metric.labels.status!=\"ok\""
                    aggregation = {
                      alignmentPeriod  = "60s"
                      perSeriesAligner = "ALIGN_RATE"
                    }
                  }
                }
              }]
            }
          }
        },
        {
          yPos   = 4
          width  = 12
          height = 4
          widget = {
            title = "Cloud Functions 実行時間"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloud_function\" resource.labels.function_name=\"${google_cloudfunctions2_function.evaluate.name}\" metric.type=\"cloudfunctions.googleapis.com/function/execution_times\""
                    aggregation = {
                      alignmentPeriod  = "60s"
                      perSeriesAligner = "ALIGN_MEAN"
                    }
                  }
                }
              }]
              yAxis = {
                label = "Duration (ms)"
                scale = "LINEAR"
              }
            }
          }
        }
      ]
    }
  })
}

# ------------------------------------------------------------------------------
# 予算アラート
# ------------------------------------------------------------------------------

resource "google_billing_budget" "ic_test_ai" {
  billing_account = data.google_project.current.billing_account
  display_name    = "${var.project_name}-${var.environment}-budget"

  budget_filter {
    projects = ["projects/${data.google_project.current.number}"]
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(var.budget_amount)
    }
  }

  threshold_rules {
    threshold_percent = 0.5
  }

  threshold_rules {
    threshold_percent = 0.9
  }

  threshold_rules {
    threshold_percent = 1.0
  }
}

# ------------------------------------------------------------------------------
# データソース
# ------------------------------------------------------------------------------

data "google_project" "current" {
  project_id = var.project_id
}

# ------------------------------------------------------------------------------
# 出力
# ------------------------------------------------------------------------------

output "cloud_logging_url" {
  description = "Cloud Logging URL（Cloud Functions）"
  value       = "https://console.cloud.google.com/logs/query;query=resource.type%3D%22cloud_function%22%0Aresource.labels.function_name%3D%22${google_cloudfunctions2_function.evaluate.name}%22;project=${var.project_id}"
}

output "cloud_trace_url" {
  description = "Cloud Trace URL"
  value       = var.enable_cloud_trace ? "https://console.cloud.google.com/traces/list?project=${var.project_id}" : "Cloud Trace disabled"
}

output "cloud_monitoring_dashboard_url" {
  description = "Cloud Monitoring ダッシュボードURL"
  value       = "https://console.cloud.google.com/monitoring/dashboards/custom/${google_monitoring_dashboard.ic_test_ai.id}?project=${var.project_id}"
}
