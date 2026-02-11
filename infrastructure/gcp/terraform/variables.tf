# ==============================================================================
# variables.tf - GCP Terraform 変数定義
# ==============================================================================
#
# 【概要】
# 内部統制テスト評価AIシステムのGCPインフラストラクチャ変数定義です。
#
# 【使用方法】
# terraform.tfvars ファイルで値を設定してください：
#
# project_id   = "your-gcp-project-id"
# project_name = "ic-test-ai"
# environment  = "prod"
# region       = "asia-northeast1"
#
# ==============================================================================

# ------------------------------------------------------------------------------
# プロジェクト基本情報
# ------------------------------------------------------------------------------

variable "project_id" {
  description = "GCPプロジェクトID"
  type        = string
}

variable "project_name" {
  description = "プロジェクト名（リソース名のプレフィックス）"
  type        = string
  default     = "ic-test-ai"
}

variable "environment" {
  description = "環境名（dev, stg, prod）"
  type        = string
  default     = "prod"

  validation {
    condition     = contains(["dev", "stg", "prod"], var.environment)
    error_message = "環境名は dev, stg, prod のいずれかである必要があります。"
  }
}

variable "region" {
  description = "デプロイ先GCPリージョン"
  type        = string
  default     = "asia-northeast1" # Tokyo
}

# ------------------------------------------------------------------------------
# タグ設定
# ------------------------------------------------------------------------------

variable "labels" {
  description = "全リソースに適用するラベル"
  type        = map(string)
  default = {
    project    = "internal-control-test-ai"
    managed-by = "terraform"
  }
}

# ------------------------------------------------------------------------------
# Cloud Functions設定
# ------------------------------------------------------------------------------

variable "function_runtime" {
  description = "Cloud Functions実行環境"
  type        = string
  default     = "python311"
}

variable "function_timeout" {
  description = "Cloud Functions実行タイムアウト（秒）"
  type        = number
  default     = 540
}

variable "function_memory" {
  description = "Cloud Functionsメモリサイズ（MB）"
  type        = number
  default     = 1024
}

variable "function_max_instances" {
  description = "Cloud Functions最大インスタンス数"
  type        = number
  default     = 10
}

# ------------------------------------------------------------------------------
# Apigee設定
# ------------------------------------------------------------------------------

variable "enable_apigee" {
  description = "Apigeeを有効化（コスト注意：評価版期間外は課金）"
  type        = bool
  default     = false
}

variable "apigee_organization_name" {
  description = "Apigee組織名（プロジェクトIDと同じ）"
  type        = string
  default     = ""
}

variable "apigee_environment_name" {
  description = "Apigee環境名"
  type        = string
  default     = "prod"
}

# ------------------------------------------------------------------------------
# Secret Manager設定
# ------------------------------------------------------------------------------

variable "vertex_ai_api_key" {
  description = "Vertex AI APIキー（セキュリティのため、環境変数で設定）"
  type        = string
  default     = "REPLACE_WITH_ACTUAL_API_KEY"
  sensitive   = true
}

variable "document_ai_api_key" {
  description = "Document AI APIキー"
  type        = string
  default     = "REPLACE_WITH_ACTUAL_API_KEY"
  sensitive   = true
}

variable "openai_api_key" {
  description = "OpenAI APIキー（フォールバック用）"
  type        = string
  default     = ""
  sensitive   = true
}

# ------------------------------------------------------------------------------
# Cloud Logging設定
# ------------------------------------------------------------------------------

variable "log_retention_days" {
  description = "Cloud Logsの保持期間（日数）"
  type        = number
  default     = 30
}

variable "enable_cloud_trace" {
  description = "Cloud Traceトレーシングを有効化"
  type        = bool
  default     = true
}

# ------------------------------------------------------------------------------
# Cloud Storage設定
# ------------------------------------------------------------------------------

variable "storage_lifecycle_age" {
  description = "Cloud Storageオブジェクトの自動削除日数"
  type        = number
  default     = 90
}

# ------------------------------------------------------------------------------
# コスト制御設定
# ------------------------------------------------------------------------------

variable "enable_monitoring_alerts" {
  description = "Cloud Monitoringアラートを有効化"
  type        = bool
  default     = true
}

variable "budget_amount" {
  description = "月次予算額（USD）"
  type        = number
  default     = 100
}
