# ==============================================================================
# outputs.tf - Terraform 出力定義
# ==============================================================================
#
# 【概要】
# デプロイ完了後に必要な情報を出力します。
#
# 【出力内容】
# - Cloud FunctionsエンドポイントURL（VBA/PowerShell設定用）
# - ApigeeエンドポイントURL（有効な場合）
# - Cloud Monitoring ダッシュボードURL
# - Cloud Trace URL
#
# ==============================================================================

# ------------------------------------------------------------------------------
# 全体情報
# ------------------------------------------------------------------------------

output "project_id" {
  description = "GCPプロジェクトID"
  value       = var.project_id
}

output "project_name" {
  description = "プロジェクト名"
  value       = var.project_name
}

output "environment" {
  description = "環境名"
  value       = var.environment
}

output "region" {
  description = "デプロイリージョン"
  value       = var.region
}

# ------------------------------------------------------------------------------
# Cloud Functions
# ------------------------------------------------------------------------------

output "cloud_functions_endpoint" {
  description = "Cloud FunctionsエンドポイントURL（VBA/PowerShellに設定）"
  value       = "${google_cloudfunctions2_function.evaluate.service_config[0].uri}/evaluate"
}

output "cloud_functions_console_url" {
  description = "Cloud Functions管理コンソールURL"
  value       = "https://console.cloud.google.com/functions/details/${var.region}/${google_cloudfunctions2_function.evaluate.name}?project=${var.project_id}"
}

# ------------------------------------------------------------------------------
# Apigee
# ------------------------------------------------------------------------------

output "apigee_endpoint" {
  description = "ApigeeエンドポイントURL（有効な場合）"
  value       = var.enable_apigee ? (length(google_apigee_envgroup.prod) > 0 ? "https://${google_apigee_envgroup.prod[0].hostnames[0]}/api/evaluate" : "N/A") : "Apigee disabled - use Cloud Functions URI"
}

output "apigee_console_url" {
  description = "Apigee管理コンソールURL"
  value       = var.enable_apigee ? "https://apigee.google.com/organizations/${var.project_id}" : "Apigee disabled"
}

# ------------------------------------------------------------------------------
# Secret Manager
# ------------------------------------------------------------------------------

output "secret_manager_vertex_ai_key_id" {
  description = "Vertex AI API KeyのSecret Manager ID"
  value       = google_secret_manager_secret.vertex_ai_api_key.secret_id
}

output "secret_manager_console_url" {
  description = "Secret Manager管理コンソールURL"
  value       = "https://console.cloud.google.com/security/secret-manager?project=${var.project_id}"
}

# ------------------------------------------------------------------------------
# Cloud Monitoring / Logging / Trace
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
  description = "Cloud Monitoringダッシュボード URL"
  value       = "https://console.cloud.google.com/monitoring/dashboards/custom/${google_monitoring_dashboard.ic_test_ai.id}?project=${var.project_id}"
}

# ------------------------------------------------------------------------------
# デプロイ後の手順
# ------------------------------------------------------------------------------

output "post_deployment_steps" {
  description = "デプロイ後の設定手順"
  value       = <<-EOT
========================================
デプロイ完了！次の手順を実施してください
========================================

1. Secret Managerにシークレットを設定:
   gcloud secrets versions add ${google_secret_manager_secret.vertex_ai_api_key.secret_id} \
     --data-file=- <<< "<実際のAPIキー>"

   gcloud secrets versions add ${google_secret_manager_secret.document_ai_api_key.secret_id} \
     --data-file=- <<< "<実際のAPIキー>"

2. Cloud Functionsにコードをデプロイ:
   cd platforms/gcp

   # デプロイパッケージ作成
   mkdir -p package
   cp -r ../../src package/
   cp main.py package/
   cp requirements.txt package/
   cd package
   zip -r ../function-source.zip .
   cd ..

   # Cloud Storageにアップロード
   gcloud storage cp function-source.zip gs://${google_storage_bucket.function_source.name}/

   # Cloud Functions更新
   gcloud functions deploy ${google_cloudfunctions2_function.evaluate.name} \
     --gen2 \
     --region=${var.region} \
     --source=gs://${google_storage_bucket.function_source.name}/function-source.zip \
     --runtime=python311 \
     --entry-point=evaluate

   # クリーンアップ
   rm -rf package function-source.zip

3. VBA/PowerShellのエンドポイントを更新:
   ${var.enable_apigee ? "- Apigee経由: terraform output apigee_endpoint" : "- Cloud Functions直接: ${google_cloudfunctions2_function.evaluate.service_config[0].uri}/evaluate"}

4. 相関IDフローを確認:
   Cloud Loggingで以下のクエリを実行:

   resource.type="cloud_function"
   resource.labels.function_name="${google_cloudfunctions2_function.evaluate.name}"
   jsonPayload.correlation_id="<X-Correlation-IDヘッダーの値>"

5. Cloud Traceで依存関係を確認:
   ${var.enable_cloud_trace ? "https://console.cloud.google.com/traces/list?project=${var.project_id}" : "Cloud Traceが無効です"}

${var.enable_apigee ? "\n6. Apigee APIプロキシを手動で設定:\n   - Apigee Console → API Proxies → Create\n   - ターゲット: ${google_cloudfunctions2_function.evaluate.service_config[0].uri}\n   - ポリシー: VerifyAPIKey, AssignMessage(相関ID), Quota" : ""}

========================================
EOT
}
