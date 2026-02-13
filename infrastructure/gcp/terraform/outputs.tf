# ==============================================================================
# outputs.tf - Terraform 出力定義
# ==============================================================================
#
# 【概要】
# デプロイ完了後に必要な情報を出力します。
#
# 【出力内容】
# - Cloud RunエンドポイントURL（VBA/PowerShell設定用）
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
# Cloud Run
# ------------------------------------------------------------------------------

output "cloud_run_endpoint" {
  description = "Cloud RunエンドポイントURL（VBA/PowerShellに設定）"
  value       = "${google_cloud_run_v2_service.ic_test_ai.uri}/evaluate"
}

output "cloud_run_console_url" {
  description = "Cloud Run管理コンソールURL"
  value       = "https://console.cloud.google.com/run/detail/${var.region}/${google_cloud_run_v2_service.ic_test_ai.name}?project=${var.project_id}"
}

# ------------------------------------------------------------------------------
# Apigee
# ------------------------------------------------------------------------------

output "apigee_endpoint" {
  description = "ApigeeエンドポイントURL（有効な場合）"
  value       = var.enable_apigee ? (length(google_apigee_envgroup.prod) > 0 ? "https://${google_apigee_envgroup.prod[0].hostnames[0]}/api/evaluate" : "N/A") : "Apigee disabled - use Cloud Run URI"
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

# Note: cloud_logging_url, cloud_trace_url, cloud_monitoring_dashboard_url
# は cloud-logging.tf で定義されています。

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

2. Artifact RegistryにDockerイメージをプッシュ:
   gcloud auth configure-docker ${var.region}-docker.pkg.dev
   docker build -t ${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.ic_test_ai.repository_id}/ic-test-ai-agent:latest .
   docker push ${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.ic_test_ai.repository_id}/ic-test-ai-agent:latest

3. Cloud Runを更新:
   gcloud run deploy ${google_cloud_run_v2_service.ic_test_ai.name} \
     --image ${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.ic_test_ai.repository_id}/ic-test-ai-agent:latest \
     --region ${var.region} \
     --platform managed

4. VBA/PowerShellのエンドポイントを更新:
   ${var.enable_apigee ? "- Apigee経由: terraform output apigee_endpoint" : "- Cloud Run直接: ${google_cloud_run_v2_service.ic_test_ai.uri}/evaluate"}

5. 相関IDフローを確認:
   Cloud Loggingで以下のクエリを実行:

   resource.type="cloud_run_revision"
   resource.labels.service_name="${google_cloud_run_v2_service.ic_test_ai.name}"
   jsonPayload.correlation_id="<X-Correlation-IDヘッダーの値>"

6. Cloud Traceで依存関係を確認:
   ${var.enable_cloud_trace ? "https://console.cloud.google.com/traces/list?project=${var.project_id}" : "Cloud Traceが無効です"}

${var.enable_apigee ? "\n7. Apigee APIプロキシを手動で設定:\n   - Apigee Console → API Proxies → Create\n   - ターゲット: ${google_cloud_run_v2_service.ic_test_ai.uri}\n   - ポリシー: VerifyAPIKey, AssignMessage(相関ID), Quota" : ""}

========================================
EOT
}
