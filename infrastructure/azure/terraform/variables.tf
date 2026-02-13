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
# Function App設定
# ------------------------------------------------------------------------------

variable "function_app_sku_name" {
  description = "Function App SKU名（Consumption=Y1）"
  type        = string
  default     = "Y1"
}

variable "function_app_sku_tier" {
  description = "Function App SKU Tier"
  type        = string
  default     = "Dynamic"
}

variable "python_version" {
  description = "Pythonバージョン"
  type        = string
  default     = "3.11"
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
