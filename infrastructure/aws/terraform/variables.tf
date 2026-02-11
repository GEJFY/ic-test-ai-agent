# ==============================================================================
# variables.tf - AWS Terraform 変数定義
# ==============================================================================
#
# 【概要】
# 内部統制テスト評価AIシステムのAWSインフラストラクチャ変数定義です。
#
# 【使用方法】
# terraform.tfvars ファイルで値を設定してください：
#
# project_name = "ic-test-ai"
# environment  = "prod"
# region       = "ap-northeast-1"
#
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
    Project    = "InternalControlTestAI"
    ManagedBy  = "Terraform"
  }
}

# ------------------------------------------------------------------------------
# Lambda設定
# ------------------------------------------------------------------------------

variable "lambda_runtime" {
  description = "Lambda実行環境"
  type        = string
  default     = "python3.11"
}

variable "lambda_timeout" {
  description = "Lambda実行タイムアウト（秒）"
  type        = number
  default     = 540
}

variable "lambda_memory" {
  description = "Lambda メモリサイズ（MB）"
  type        = number
  default     = 1024
}

variable "lambda_reserved_concurrency" {
  description = "Lambda予約同時実行数（-1=無制限）"
  type        = number
  default     = -1
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

variable "bedrock_api_key" {
  description = "AWS Bedrock APIキー（セキュリティのため、terraform.tfvarsではなく環境変数で設定）"
  type        = string
  default     = "REPLACE_WITH_ACTUAL_API_KEY"
  sensitive   = true
}

variable "textract_api_key" {
  description = "AWS Textract APIキー"
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
# S3設定
# ------------------------------------------------------------------------------

variable "s3_lifecycle_expiration_days" {
  description = "S3オブジェクトの自動削除日数"
  type        = number
  default     = 90
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
