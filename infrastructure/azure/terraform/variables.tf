# ==============================================================================
# variables.tf - Azure Terraform 変数定義
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

variable "location" {
  description = "デプロイ先Azureリージョン"
  type        = string
  default     = "japaneast"
}

variable "resource_group_name" {
  description = "既存リソースグループ名（CDワークフローのAZURE_RESOURCE_GROUP）"
  type        = string
}

# ------------------------------------------------------------------------------
# タグ設定
# ------------------------------------------------------------------------------

variable "tags" {
  description = "全リソースに適用するタグ"
  type        = map(string)
  default = {
    Project     = "InternalControlTestAI"
    Environment = "Production"
    ManagedBy   = "Terraform"
  }
}

# ------------------------------------------------------------------------------
# APIM設定
# ------------------------------------------------------------------------------

variable "apim_publisher_email" {
  description = "APIM発行者メールアドレス"
  type        = string
  default     = "admin@example.com"
}

variable "apim_publisher_name" {
  description = "APIM発行者名"
  type        = string
  default     = "Internal Control Test AI"
}

variable "apim_sku_name" {
  description = "APIM SKU名"
  type        = string
  default     = "Consumption"

  validation {
    condition     = contains(["Consumption", "Developer", "Basic", "Standard", "Premium"], var.apim_sku_name)
    error_message = "SKU名は Consumption, Developer, Basic, Standard, Premium のいずれかである必要があります。"
  }
}

variable "apim_sku_capacity" {
  description = "APIM SKU容量（Consumption=0）"
  type        = number
  default     = 0
}

# ------------------------------------------------------------------------------
# Container Apps設定
# ------------------------------------------------------------------------------

variable "container_app_cpu" {
  description = "Container App CPU（コア数）"
  type        = number
  default     = 0.5
}

variable "container_app_memory" {
  description = "Container App メモリ（例: 1Gi）"
  type        = string
  default     = "1Gi"
}

variable "container_app_min_replicas" {
  description = "Container App 最小レプリカ数（0=スケールtoゼロ）"
  type        = number
  default     = 0
}

variable "container_app_max_replicas" {
  description = "Container App 最大レプリカ数"
  type        = number
  default     = 5
}

variable "container_image_tag" {
  description = "Dockerイメージタグ（CDワークフローから上書き）"
  type        = string
  default     = "latest"
}

# ------------------------------------------------------------------------------
# Azure AI / Cognitive Services 設定
# ------------------------------------------------------------------------------

variable "azure_model" {
  description = "Azure AI Foundry モデル名"
  type        = string
  default     = "gpt-5-nano"
}

variable "azure_api_version" {
  description = "Azure AI Foundry APIバージョン"
  type        = string
  default     = "2025-01-01-preview"
}

variable "azure_model_version" {
  description = "Azure AI Foundry モデルバージョン"
  type        = string
  default     = "2025-08-07"
}

variable "azure_capacity" {
  description = "Azure AI Foundry デプロイメント容量（TPM単位、1=1000 TPM）"
  type        = number
  default     = 1
}

# ------------------------------------------------------------------------------
# 監視設定
# ------------------------------------------------------------------------------

variable "log_retention_in_days" {
  description = "ログ保持期間（日数）"
  type        = number
  default     = 30
}

variable "daily_data_cap_in_gb" {
  description = "日次データ上限（GB）"
  type        = number
  default     = 1
}

# ------------------------------------------------------------------------------
# コスト管理
# ------------------------------------------------------------------------------

variable "enable_budget_alert" {
  description = "月次予算アラートを有効にするか"
  type        = bool
  default     = true
}

variable "budget_amount" {
  description = "月次予算額（USD）"
  type        = number
  default     = 100
}

variable "budget_alert_email" {
  description = "予算アラートの通知先メールアドレス"
  type        = string
  default     = ""
}
