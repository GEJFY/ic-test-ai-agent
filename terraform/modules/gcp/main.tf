# =============================================================================
# GCP Module - 内部統制テスト評価AIシステム
# =============================================================================
#
# 作成するリソース:
#   - Cloud Run Service (またはCloud Functions)
#   - Firestore Database (ジョブ管理用)
#   - Cloud Tasks Queue (非同期処理用)
#   - IAM設定
#
# =============================================================================

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# -----------------------------------------------------------------------------
# Variables
# -----------------------------------------------------------------------------

variable "client_name" {
  description = "Client identifier (used in resource names)"
  type        = string
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "asia-northeast1"
}

variable "llm_config" {
  description = "LLM configuration"
  type = object({
    model = optional(string, "gemini-2.5-flash")
  })
  default = {}
}

variable "ocr_config" {
  description = "OCR configuration"
  type = object({
    provider     = string
    processor_id = optional(string)
  })
  default = {
    provider = "NONE"
  }
}

variable "app_settings" {
  description = "Application settings"
  type = object({
    max_plan_revisions     = optional(number, 1)
    max_judgment_revisions = optional(number, 1)
    skip_plan_creation     = optional(bool, false)
    async_mode             = optional(bool, true)
    memory_mb              = optional(number, 1024)
    timeout_seconds        = optional(number, 540)
    min_instances          = optional(number, 0)
    max_instances          = optional(number, 10)
  })
  default = {}
}

variable "container_image" {
  description = "Container image URL"
  type        = string
  default     = ""
}

variable "allow_unauthenticated" {
  description = "Allow unauthenticated access"
  type        = bool
  default     = false
}

variable "labels" {
  description = "Resource labels"
  type        = map(string)
  default     = {}
}

# -----------------------------------------------------------------------------
# Locals
# -----------------------------------------------------------------------------

locals {
  service_name = "ic-${var.client_name}-${var.environment}"

  default_labels = {
    application = "ic-test-ai-agent"
    client      = var.client_name
    environment = var.environment
    managed-by  = "terraform"
  }

  all_labels = merge(local.default_labels, var.labels)
}

# -----------------------------------------------------------------------------
# Enable Required APIs
# -----------------------------------------------------------------------------

resource "google_project_service" "services" {
  for_each = toset([
    "run.googleapis.com",
    "aiplatform.googleapis.com",
    "firestore.googleapis.com",
    "cloudtasks.googleapis.com",
  ])

  project = var.project_id
  service = each.key

  disable_on_destroy = false
}

# -----------------------------------------------------------------------------
# Service Account
# -----------------------------------------------------------------------------

resource "google_service_account" "main" {
  account_id   = "${local.service_name}-sa"
  display_name = "IC Test AI Agent - ${var.client_name}"
  project      = var.project_id
}

# Vertex AI User role
resource "google_project_iam_member" "vertex_ai" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.main.email}"
}

# Firestore User role
resource "google_project_iam_member" "firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.main.email}"
}

# Cloud Tasks Enqueuer role
resource "google_project_iam_member" "tasks" {
  project = var.project_id
  role    = "roles/cloudtasks.enqueuer"
  member  = "serviceAccount:${google_service_account.main.email}"
}

# -----------------------------------------------------------------------------
# Firestore Database (ジョブ管理)
# -----------------------------------------------------------------------------

resource "google_firestore_database" "main" {
  project     = var.project_id
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.services]

  lifecycle {
    ignore_changes = [
      # Firestoreは既存の場合変更しない
      location_id,
    ]
  }
}

# -----------------------------------------------------------------------------
# Cloud Tasks Queue (非同期処理)
# -----------------------------------------------------------------------------

resource "google_cloud_tasks_queue" "jobs" {
  name     = "${local.service_name}-jobs"
  location = var.region
  project  = var.project_id

  rate_limits {
    max_concurrent_dispatches = 10
    max_dispatches_per_second = 5
  }

  retry_config {
    max_attempts       = 3
    max_retry_duration = "3600s"
    min_backoff        = "10s"
    max_backoff        = "300s"
  }

  depends_on = [google_project_service.services]
}

# -----------------------------------------------------------------------------
# Cloud Run Service
# -----------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "main" {
  name     = local.service_name
  location = var.region
  project  = var.project_id

  template {
    service_account = google_service_account.main.email

    scaling {
      min_instance_count = var.app_settings.min_instances
      max_instance_count = var.app_settings.max_instances
    }

    timeout = "${var.app_settings.timeout_seconds}s"

    containers {
      image = var.container_image != "" ? var.container_image : "gcr.io/cloudrun/hello"

      resources {
        limits = {
          memory = "${var.app_settings.memory_mb}Mi"
          cpu    = "1"
        }
      }

      env {
        name  = "LLM_PROVIDER"
        value = "GCP"
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GCP_LOCATION"
        value = var.region
      }
      env {
        name  = "GCP_MODEL_NAME"
        value = var.llm_config.model
      }
      env {
        name  = "OCR_PROVIDER"
        value = var.ocr_config.provider
      }
      env {
        name  = "JOB_STORAGE_PROVIDER"
        value = "GCP"
      }
      env {
        name  = "JOB_QUEUE_PROVIDER"
        value = "GCP"
      }
      env {
        name  = "GCP_FIRESTORE_COLLECTION"
        value = "evaluation_jobs"
      }
      env {
        name  = "GCP_TASKS_QUEUE_PATH"
        value = google_cloud_tasks_queue.jobs.name
      }
      env {
        name  = "MAX_PLAN_REVISIONS"
        value = tostring(var.app_settings.max_plan_revisions)
      }
      env {
        name  = "MAX_JUDGMENT_REVISIONS"
        value = tostring(var.app_settings.max_judgment_revisions)
      }
      env {
        name  = "SKIP_PLAN_CREATION"
        value = tostring(var.app_settings.skip_plan_creation)
      }
      env {
        name  = "LOG_TO_FILE"
        value = "false"
      }
    }
  }

  labels = local.all_labels

  depends_on = [
    google_project_service.services,
    google_project_iam_member.vertex_ai,
  ]

  lifecycle {
    ignore_changes = [
      template[0].containers[0].image,
    ]
  }
}

# -----------------------------------------------------------------------------
# IAM Policy (Public Access)
# -----------------------------------------------------------------------------

resource "google_cloud_run_v2_service_iam_member" "public" {
  count = var.allow_unauthenticated ? 1 : 0

  project  = var.project_id
  location = google_cloud_run_v2_service.main.location
  name     = google_cloud_run_v2_service.main.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------

output "service_name" {
  description = "Cloud Run service name"
  value       = google_cloud_run_v2_service.main.name
}

output "service_url" {
  description = "Cloud Run service URL"
  value       = google_cloud_run_v2_service.main.uri
}

output "service_account_email" {
  description = "Service account email"
  value       = google_service_account.main.email
}

output "firestore_database" {
  description = "Firestore database name"
  value       = google_firestore_database.main.name
}

output "tasks_queue_name" {
  description = "Cloud Tasks queue name"
  value       = google_cloud_tasks_queue.jobs.name
}

output "endpoints" {
  description = "API endpoints"
  value = {
    health   = "${google_cloud_run_v2_service.main.uri}/health"
    config   = "${google_cloud_run_v2_service.main.uri}/config"
    evaluate = "${google_cloud_run_v2_service.main.uri}/evaluate"
    submit   = "${google_cloud_run_v2_service.main.uri}/evaluate/submit"
  }
}
