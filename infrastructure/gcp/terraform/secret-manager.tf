# ==============================================================================
# secret-manager.tf - GCP Secret Manager リソース定義
# ==============================================================================
#
# 【概要】
# APIキーやシークレットを安全に管理するためのSecret Managerシークレットを構築します。
#
# 【機能】
# - シークレット管理（Vertex AI API Key、Document AI API Key等）
# - Cloud Runからのアクセス制御（IAMポリシー）
# - 自動ローテーション機能（将来対応）
# - バージョン管理
#
# ==============================================================================

# ------------------------------------------------------------------------------
# Vertex AI 設定（SA認証のため通常は不使用、将来の拡張用に保持）
# ------------------------------------------------------------------------------

resource "google_secret_manager_secret" "vertex_ai_api_key" {
  secret_id = "${var.project_name}-${var.environment}-vertex-ai-api-key"
  project   = var.project_id

  replication {
    auto {}
  }

  labels = merge(var.labels, {
    environment = var.environment
  })
}

resource "google_secret_manager_secret_version" "vertex_ai_api_key" {
  secret      = google_secret_manager_secret.vertex_ai_api_key.id
  secret_data = var.vertex_ai_api_key
}

# ------------------------------------------------------------------------------
# Document AI 設定（SA認証のため通常は不使用、将来の拡張用に保持）
# ------------------------------------------------------------------------------

resource "google_secret_manager_secret" "document_ai_api_key" {
  secret_id = "${var.project_name}-${var.environment}-document-ai-api-key"
  project   = var.project_id

  replication {
    auto {}
  }

  labels = merge(var.labels, {
    environment = var.environment
  })
}

resource "google_secret_manager_secret_version" "document_ai_api_key" {
  secret      = google_secret_manager_secret.document_ai_api_key.id
  secret_data = var.document_ai_api_key
}

# ------------------------------------------------------------------------------
# OpenAI API Key（フォールバック用）
# ------------------------------------------------------------------------------

resource "google_secret_manager_secret" "openai_api_key" {
  secret_id = "${var.project_name}-${var.environment}-openai-api-key"
  project   = var.project_id

  replication {
    auto {}
  }

  labels = merge(var.labels, {
    environment = var.environment
  })
}

resource "google_secret_manager_secret_version" "openai_api_key" {
  secret      = google_secret_manager_secret.openai_api_key.id
  secret_data = var.openai_api_key != "" ? var.openai_api_key : "NOT_CONFIGURED"
}

# ------------------------------------------------------------------------------
# Cloud Run用サービスアカウント
# ------------------------------------------------------------------------------

resource "google_service_account" "cloud_run" {
  account_id   = "${var.project_name}-${var.environment}-run-sa"
  display_name = "Cloud Run Service Account for ${var.project_name}"
  project      = var.project_id
}

# ------------------------------------------------------------------------------
# Secret Manager IAMポリシー（Cloud Run読み取り権限）
# ------------------------------------------------------------------------------

resource "google_secret_manager_secret_iam_member" "vertex_ai_access" {
  secret_id = google_secret_manager_secret.vertex_ai_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run.email}"
  project   = var.project_id
}

resource "google_secret_manager_secret_iam_member" "document_ai_access" {
  secret_id = google_secret_manager_secret.document_ai_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run.email}"
  project   = var.project_id
}

resource "google_secret_manager_secret_iam_member" "openai_access" {
  secret_id = google_secret_manager_secret.openai_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run.email}"
  project   = var.project_id
}

# ------------------------------------------------------------------------------
# 出力
# ------------------------------------------------------------------------------

output "vertex_ai_api_key_id" {
  description = "Vertex AI API KeyのSecret Manager ID"
  value       = google_secret_manager_secret.vertex_ai_api_key.id
}

output "document_ai_api_key_id" {
  description = "Document AI API KeyのSecret Manager ID"
  value       = google_secret_manager_secret.document_ai_api_key.id
}

output "openai_api_key_id" {
  description = "OpenAI API KeyのSecret Manager ID"
  value       = google_secret_manager_secret.openai_api_key.id
}

output "cloud_run_service_account_email" {
  description = "Cloud Run用サービスアカウントのEmail"
  value       = google_service_account.cloud_run.email
}
