# ==============================================================================
# variables.tf - AWS Terraform 変数定義
# ==============================================================================

# ------------------------------------------------------------------------------
# プロジェクト基本情報
# ------------------------------------------------------------------------------

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
  description = "デプロイ先AWSリージョン"
  type        = string
  default     = "ap-northeast-1" # Tokyo
}

# ------------------------------------------------------------------------------
# タグ設定
# ------------------------------------------------------------------------------

variable "tags" {
  description = "全リソースに適用するタグ"
  type        = map(string)
  default = {
    Project   = "InternalControlTestAI"
    ManagedBy = "Terraform"
  }
}

# ------------------------------------------------------------------------------
# App Runner設定
# ------------------------------------------------------------------------------

variable "app_runner_cpu" {
  description = "App Runner CPU（例: 1024 = 1 vCPU）"
  type        = string
  default     = "1024"
}

variable "app_runner_memory" {
  description = "App Runner メモリ（例: 2048 = 2 GB）"
  type        = string
  default     = "2048"
}

variable "app_runner_timeout" {
  description = "App Runner リクエストタイムアウト（秒）"
  type        = number
  default     = 540
}

variable "app_runner_max_concurrency" {
  description = "App Runner 最大同時リクエスト数（インスタンスあたり）"
  type        = number
  default     = 25
}

variable "app_runner_max_size" {
  description = "App Runner 最大インスタンス数"
  type        = number
  default     = 5
}

variable "container_image_tag" {
  description = "Dockerイメージタグ（CDワークフローから上書き）"
  type        = string
  default     = "latest"
}

# ------------------------------------------------------------------------------
# API Gateway設定
# ------------------------------------------------------------------------------

variable "api_gateway_throttle_burst_limit" {
  description = "APIバーストリミット（リクエスト数）"
  type        = number
  default     = 100
}

variable "api_gateway_throttle_rate_limit" {
  description = "APIレート制限（リクエスト/秒）"
  type        = number
  default     = 50
}

# ------------------------------------------------------------------------------
# Secrets Manager設定
# ------------------------------------------------------------------------------

variable "aws_bedrock_model_id" {
  description = "AWS Bedrock モデルID"
  type        = string
  default     = "jp.anthropic.claude-sonnet-4-5-20250929-v1:0"
}

variable "bedrock_api_key" {
  description = "AWS Bedrock APIキー（IAM認証のため通常は不使用）"
  type        = string
  default     = "IAM_AUTHENTICATION"
  sensitive   = true
}

variable "textract_api_key" {
  description = "AWS Textract APIキー（IAM認証のため通常は不使用）"
  type        = string
  default     = "IAM_AUTHENTICATION"
  sensitive   = true
}

variable "openai_api_key" {
  description = "OpenAI APIキー（フォールバック用）"
  type        = string
  default     = ""
  sensitive   = true
}

# ------------------------------------------------------------------------------
# CloudWatch設定
# ------------------------------------------------------------------------------

variable "cloudwatch_log_retention_days" {
  description = "CloudWatch Logsの保持期間（日数）"
  type        = number
  default     = 30
}

variable "enable_xray_tracing" {
  description = "X-Rayトレーシングを有効化"
  type        = bool
  default     = true
}

# ------------------------------------------------------------------------------
# コスト制御設定
# ------------------------------------------------------------------------------

variable "enable_cloudwatch_alarms" {
  description = "CloudWatchアラームを有効化"
  type        = bool
  default     = true
}

variable "cost_alert_threshold" {
  description = "コストアラート閾値（USD/月）"
  type        = number
  default     = 100
}
