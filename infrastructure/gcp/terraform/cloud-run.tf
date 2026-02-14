# ==============================================================================
# cloud-run.tf - GCP Cloud Run リソース定義
# ==============================================================================
#
# 【概要】
# 内部統制テスト評価AIのバックエンドAPI（Cloud Run）を構築します。
#
# 【機能】
# - Artifact Registryリポジトリ（Dockerイメージ保存）
# - Cloud Runサービス（コンテナ実行）
# - IAMロール（Secret Manager、Vertex AI、Document AIアクセス用）
# - 自動スケーリング（0〜max_instances）
# - ヘルスチェック
#
# 【ネットワークセキュリティ】
# - Inbound:  HTTPS (443) Apigee経由のみ許可（ingress = internal-and-cloud-load-balancing）
# - Outbound: HTTPS (443) Vertex AI / Document AI / Secret Manager
# - 認証:     Apigee + APIキー / サービスアカウント
# - 暗号化:   TLS 1.2+（トランジット中）、Secret Manager（シークレット管理）
#
# ==============================================================================

# ------------------------------------------------------------------------------
# Artifact Registry リポジトリ
# ------------------------------------------------------------------------------

resource "google_artifact_registry_repository" "ic_test_ai" {
  location      = var.region
  repository_id = "${var.project_name}-${var.environment}"
  description   = "Docker images for ${var.project_name}"
  format        = "DOCKER"
  project       = var.project_id

  cleanup_policy_dry_run = false

  cleanup_policies {
    id     = "keep-latest-10"
    action = "KEEP"

    most_recent_versions {
      keep_count = 10
    }
  }

  labels = merge(var.labels, {
    environment = var.environment
    purpose     = "container-images"
  })
}

# ------------------------------------------------------------------------------
# Cloud Run IAMロール
# ------------------------------------------------------------------------------

# Vertex AI呼び出し権限
resource "google_project_iam_member" "cloud_run_vertex_ai" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

# Document AI呼び出し権限
resource "google_project_iam_member" "cloud_run_document_ai" {
  project = var.project_id
  role    = "roles/documentai.apiUser"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

# Cloud Logging書き込み権限
resource "google_project_iam_member" "cloud_run_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

# Cloud Trace書き込み権限
resource "google_project_iam_member" "cloud_run_trace" {
  count   = var.enable_cloud_trace ? 1 : 0
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

# Artifact Registry読み取り権限
resource "google_project_iam_member" "cloud_run_artifact_registry" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

# ------------------------------------------------------------------------------
# Cloud Run サービス
# ------------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "ic_test_ai" {
  name     = "${var.project_name}-${var.environment}-api"
  location = var.region
  project  = var.project_id

  template {
    service_account = google_service_account.cloud_run.email

    scaling {
      min_instance_count = 0
      max_instance_count = var.container_max_instances
    }

    timeout = "${var.container_timeout}s"

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.ic_test_ai.repository_id}/ic-test-ai-agent:${var.container_image_tag}"

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = var.container_cpu
          memory = var.container_memory
        }
      }

      # 環境変数設定
      env {
        name  = "LLM_PROVIDER"
        value = "GCP"
      }

      env {
        name  = "OCR_PROVIDER"
        value = "GCP"
      }

      env {
        name  = "VERTEX_AI_API_KEY_SECRET_ID"
        value = google_secret_manager_secret.vertex_ai_api_key.secret_id
      }

      env {
        name  = "DOCUMENT_AI_API_KEY_SECRET_ID"
        value = google_secret_manager_secret.document_ai_api_key.secret_id
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "GCP_REGION"
        value = var.region
      }

      env {
        name  = "FUNCTION_TIMEOUT_SECONDS"
        value = tostring(var.container_timeout)
      }

      env {
        name  = "DEBUG"
        value = "false"
      }

      # モデル設定
      env {
        name  = "GCP_MODEL_NAME"
        value = var.gcp_model_name
      }

      # オーケストレータ・パフォーマンス設定
      env {
        name  = "USE_GRAPH_ORCHESTRATOR"
        value = "true"
      }

      env {
        name  = "MAX_PLAN_REVISIONS"
        value = "1"
      }

      env {
        name  = "MAX_JUDGMENT_REVISIONS"
        value = "1"
      }

      env {
        name  = "SKIP_PLAN_CREATION"
        value = "false"
      }

      # 非同期ジョブ処理設定
      env {
        name  = "JOB_STORAGE_PROVIDER"
        value = "GCP"
      }

      env {
        name  = "JOB_QUEUE_PROVIDER"
        value = "GCP"
      }

      env {
        name  = "GCP_FIRESTORE_DATABASE"
        value = google_firestore_database.evaluation_jobs.name
      }

      env {
        name  = "GCP_CLOUD_TASKS_QUEUE"
        value = google_cloud_tasks_queue.evaluation_queue.name
      }

      # ヘルスチェック（Liveness）
      liveness_probe {
        http_get {
          path = "/health"
          port = 8080
        }
        initial_delay_seconds = 10
        period_seconds        = 30
        failure_threshold     = 3
      }

      # ヘルスチェック（Startup）
      startup_probe {
        http_get {
          path = "/health"
          port = 8080
        }
        initial_delay_seconds = 5
        period_seconds        = 10
        failure_threshold     = 5
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  labels = merge(var.labels, {
    environment = var.environment
  })

  lifecycle {
    ignore_changes = [
      template[0].containers[0].image,
    ]
  }
}

# ------------------------------------------------------------------------------
# Cloud Run 公開アクセス許可（Apigeeから呼び出し可能）
# ------------------------------------------------------------------------------

resource "google_cloud_run_v2_service_iam_member" "invoker" {
  project  = google_cloud_run_v2_service.ic_test_ai.project
  location = google_cloud_run_v2_service.ic_test_ai.location
  name     = google_cloud_run_v2_service.ic_test_ai.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ------------------------------------------------------------------------------
# 出力
# ------------------------------------------------------------------------------

output "cloud_run_service_url" {
  description = "Cloud RunサービスURL"
  value       = google_cloud_run_v2_service.ic_test_ai.uri
}

output "cloud_run_service_name" {
  description = "Cloud Runサービス名"
  value       = google_cloud_run_v2_service.ic_test_ai.name
}

output "cloud_run_service_account" {
  description = "Cloud Run用サービスアカウント"
  value       = google_service_account.cloud_run.email
}

output "artifact_registry_url" {
  description = "Artifact RegistryリポジトリURL"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.ic_test_ai.repository_id}"
}
