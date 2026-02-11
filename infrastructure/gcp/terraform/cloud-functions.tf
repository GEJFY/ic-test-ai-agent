# ==============================================================================
# cloud-functions.tf - GCP Cloud Functions リソース定義
# ==============================================================================
#
# 【概要】
# 内部統制テスト評価AIのバックエンドAPI（Cloud Functions Gen 2）を構築します。
#
# 【機能】
# - Python 3.11ランタイム
# - サービスアカウント（Secret Manager、Vertex AI、Document AIアクセス用）
# - 環境変数設定（LLMプロバイダー、OCRプロバイダー等）
# - Cloud Logging統合
# - Cloud Trace統合
#
# ==============================================================================

# ------------------------------------------------------------------------------
# Cloud Storage バケット（デプロイパッケージ用）
# ------------------------------------------------------------------------------

resource "google_storage_bucket" "function_source" {
  name          = "${var.project_name}-${var.environment}-function-source-${var.project_id}"
  location      = var.region
  project       = var.project_id
  force_destroy = true

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = var.storage_lifecycle_age
    }
    action {
      type = "Delete"
    }
  }

  labels = merge(var.labels, {
    environment = var.environment
    purpose     = "cloud-functions-source"
  })
}

# ------------------------------------------------------------------------------
# Cloud Functions IAMロール
# ------------------------------------------------------------------------------

# Vertex AI呼び出し権限
resource "google_project_iam_member" "function_vertex_ai" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.cloud_function.email}"
}

# Document AI呼び出し権限
resource "google_project_iam_member" "function_document_ai" {
  project = var.project_id
  role    = "roles/documentai.apiUser"
  member  = "serviceAccount:${google_service_account.cloud_function.email}"
}

# Cloud Logging書き込み権限
resource "google_project_iam_member" "function_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.cloud_function.email}"
}

# Cloud Trace書き込み権限
resource "google_project_iam_member" "function_trace" {
  count   = var.enable_cloud_trace ? 1 : 0
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.cloud_function.email}"
}

# ------------------------------------------------------------------------------
# Cloud Functions Gen 2
# ------------------------------------------------------------------------------

resource "google_cloudfunctions2_function" "evaluate" {
  name        = "${var.project_name}-${var.environment}-evaluate"
  location    = var.region
  project     = var.project_id
  description = "内部統制テスト評価AI - 評価エンドポイント"

  build_config {
    runtime     = var.function_runtime
    entry_point = "evaluate"

    source {
      storage_source {
        bucket = google_storage_bucket.function_source.name
        object = "function-source.zip"
      }
    }
  }

  service_config {
    max_instance_count = var.function_max_instances
    min_instance_count = 0
    available_memory   = "${var.function_memory}Mi"
    timeout_seconds    = var.function_timeout

    service_account_email = google_service_account.cloud_function.email

    environment_variables = {
      # LLMプロバイダー設定
      LLM_PROVIDER = "GCP"

      # Secret Manager参照
      VERTEX_AI_API_KEY_SECRET_ID    = google_secret_manager_secret.vertex_ai_api_key.secret_id
      DOCUMENT_AI_API_KEY_SECRET_ID  = google_secret_manager_secret.document_ai_api_key.secret_id

      # OCRプロバイダー設定
      OCR_PROVIDER = "GCP"

      # GCP プロジェクト設定
      GCP_PROJECT_ID = var.project_id
      GCP_REGION     = var.region

      # タイムアウト設定
      FUNCTION_TIMEOUT_SECONDS = tostring(var.function_timeout)

      # デバッグ設定
      DEBUG = "false"
    }

    ingress_settings               = "ALLOW_ALL"
    all_traffic_on_latest_revision = true
  }

  labels = merge(var.labels, {
    environment = var.environment
  })

  # ライフサイクル: 初回デプロイ後は手動アップデート
  lifecycle {
    ignore_changes = [
      build_config[0].source
    ]
  }
}

# ------------------------------------------------------------------------------
# Cloud Functions 公開アクセス許可（Apigeeから呼び出し可能）
# ------------------------------------------------------------------------------

resource "google_cloudfunctions2_function_iam_member" "invoker" {
  project        = google_cloudfunctions2_function.evaluate.project
  location       = google_cloudfunctions2_function.evaluate.location
  cloud_function = google_cloudfunctions2_function.evaluate.name
  role           = "roles/cloudfunctions.invoker"
  member         = "allUsers"
}

# ------------------------------------------------------------------------------
# 出力
# ------------------------------------------------------------------------------

output "function_uri" {
  description = "Cloud FunctionsのエンドポイントURL"
  value       = google_cloudfunctions2_function.evaluate.service_config[0].uri
}

output "function_name" {
  description = "Cloud Functions名"
  value       = google_cloudfunctions2_function.evaluate.name
}

output "function_service_account" {
  description = "Cloud Functions用サービスアカウント"
  value       = google_service_account.cloud_function.email
}
