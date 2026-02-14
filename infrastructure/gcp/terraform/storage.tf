# ==============================================================================
# storage.tf - GCP Storage リソース定義（非同期ジョブ処理用）
# ==============================================================================

# ------------------------------------------------------------------------------
# Firestore データベース（ジョブ追跡）
# ------------------------------------------------------------------------------

resource "google_firestore_database" "evaluation_jobs" {
  project     = var.project_id
  name        = "${var.project_name}-${var.environment}-jobs"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  delete_protection_state = "DELETE_PROTECTION_DISABLED"
}

# ------------------------------------------------------------------------------
# Cloud Tasks キュー（ジョブキュー）
# ------------------------------------------------------------------------------

resource "google_cloud_tasks_queue" "evaluation_queue" {
  name     = "${var.project_name}-${var.environment}-evaluation-queue"
  location = var.region
  project  = var.project_id

  rate_limits {
    max_dispatches_per_second = 10
    max_concurrent_dispatches = 5
  }

  retry_config {
    max_attempts       = 3
    max_retry_duration = "600s"
    min_backoff        = "10s"
    max_backoff        = "300s"
  }
}

# ------------------------------------------------------------------------------
# Cloud Tasks + Firestore IAM権限
# ------------------------------------------------------------------------------

resource "google_project_iam_member" "cloud_run_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_project_iam_member" "cloud_run_cloud_tasks" {
  project = var.project_id
  role    = "roles/cloudtasks.enqueuer"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

# ------------------------------------------------------------------------------
# 出力
# ------------------------------------------------------------------------------

output "firestore_database_name" {
  description = "Firestoreデータベース名"
  value       = google_firestore_database.evaluation_jobs.name
}

output "cloud_tasks_queue_name" {
  description = "Cloud Tasksキュー名"
  value       = google_cloud_tasks_queue.evaluation_queue.name
}
