# =============================================================================
# Azure Module - 内部統制テスト評価AIシステム
# =============================================================================
#
# 作成するリソース:
#   - Resource Group
#   - Storage Account (Table Storage + Queue Storage)
#   - Function App (Consumption Plan)
#   - Application Insights
#
# =============================================================================

terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
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

variable "location" {
  description = "Azure region"
  type        = string
  default     = "japaneast"
}

variable "llm_config" {
  description = "LLM configuration"
  type = object({
    provider    = string
    endpoint    = string
    api_key     = string
    model       = string
    api_version = optional(string, "2024-08-01-preview")
  })
  sensitive = true
}

variable "ocr_config" {
  description = "OCR configuration (optional)"
  type = object({
    provider = string
    endpoint = optional(string)
    api_key  = optional(string)
  })
  default = {
    provider = "NONE"
  }
  sensitive = true
}

variable "app_settings" {
  description = "Application settings"
  type = object({
    max_plan_revisions     = optional(number, 1)
    max_judgment_revisions = optional(number, 1)
    skip_plan_creation     = optional(bool, false)
    async_mode             = optional(bool, true)
  })
  default = {}
}

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}

# -----------------------------------------------------------------------------
# Locals
# -----------------------------------------------------------------------------

locals {
  resource_prefix = "ic-${var.client_name}-${var.environment}"

  default_tags = {
    Application = "IC-Test-AI-Agent"
    Client      = var.client_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }

  all_tags = merge(local.default_tags, var.tags)
}

# -----------------------------------------------------------------------------
# Resource Group
# -----------------------------------------------------------------------------

resource "azurerm_resource_group" "main" {
  name     = "rg-${local.resource_prefix}"
  location = var.location
  tags     = local.all_tags
}

# -----------------------------------------------------------------------------
# Storage Account
# -----------------------------------------------------------------------------

resource "azurerm_storage_account" "main" {
  name                     = replace("st${local.resource_prefix}", "-", "")
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  tags = local.all_tags
}

# Table Storage for job management
resource "azurerm_storage_table" "jobs" {
  name                 = "EvaluationJobs"
  storage_account_name = azurerm_storage_account.main.name
}

# Queue Storage for async processing
resource "azurerm_storage_queue" "jobs" {
  name                 = "evaluation-jobs"
  storage_account_name = azurerm_storage_account.main.name
}

# -----------------------------------------------------------------------------
# Application Insights
# -----------------------------------------------------------------------------

resource "azurerm_application_insights" "main" {
  name                = "appi-${local.resource_prefix}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  application_type    = "web"

  tags = local.all_tags
}

# -----------------------------------------------------------------------------
# Function App (Consumption Plan)
# -----------------------------------------------------------------------------

resource "azurerm_service_plan" "main" {
  name                = "asp-${local.resource_prefix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  os_type             = "Linux"
  sku_name            = "Y1"  # Consumption plan

  tags = local.all_tags
}

resource "azurerm_linux_function_app" "main" {
  name                = "func-${local.resource_prefix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  storage_account_name       = azurerm_storage_account.main.name
  storage_account_access_key = azurerm_storage_account.main.primary_access_key
  service_plan_id            = azurerm_service_plan.main.id

  site_config {
    application_stack {
      python_version = "3.11"
    }

    application_insights_key               = azurerm_application_insights.main.instrumentation_key
    application_insights_connection_string = azurerm_application_insights.main.connection_string
  }

  app_settings = {
    # LLM設定
    LLM_PROVIDER              = var.llm_config.provider
    AZURE_FOUNDRY_ENDPOINT    = var.llm_config.endpoint
    AZURE_FOUNDRY_API_KEY     = var.llm_config.api_key
    AZURE_FOUNDRY_MODEL       = var.llm_config.model
    AZURE_FOUNDRY_API_VERSION = var.llm_config.api_version

    # OCR設定
    OCR_PROVIDER    = var.ocr_config.provider
    AZURE_DI_ENDPOINT = var.ocr_config.endpoint
    AZURE_DI_KEY      = var.ocr_config.api_key

    # ジョブ管理設定
    JOB_STORAGE_PROVIDER           = "AZURE"
    JOB_QUEUE_PROVIDER             = "AZURE"
    AZURE_STORAGE_CONNECTION_STRING = azurerm_storage_account.main.primary_connection_string

    # アプリケーション設定
    MAX_PLAN_REVISIONS     = tostring(var.app_settings.max_plan_revisions)
    MAX_JUDGMENT_REVISIONS = tostring(var.app_settings.max_judgment_revisions)
    SKIP_PLAN_CREATION     = tostring(var.app_settings.skip_plan_creation)

    # その他
    FUNCTIONS_WORKER_RUNTIME = "python"
    SCM_DO_BUILD_DURING_DEPLOYMENT = "true"
  }

  tags = local.all_tags
}

# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------

output "resource_group_name" {
  description = "Resource group name"
  value       = azurerm_resource_group.main.name
}

output "function_app_name" {
  description = "Function app name"
  value       = azurerm_linux_function_app.main.name
}

output "function_app_url" {
  description = "Function app URL"
  value       = "https://${azurerm_linux_function_app.main.default_hostname}"
}

output "storage_account_name" {
  description = "Storage account name"
  value       = azurerm_storage_account.main.name
}

output "application_insights_name" {
  description = "Application Insights name"
  value       = azurerm_application_insights.main.name
}

output "endpoints" {
  description = "API endpoints"
  value = {
    health   = "https://${azurerm_linux_function_app.main.default_hostname}/api/health"
    config   = "https://${azurerm_linux_function_app.main.default_hostname}/api/config"
    evaluate = "https://${azurerm_linux_function_app.main.default_hostname}/api/evaluate"
    submit   = "https://${azurerm_linux_function_app.main.default_hostname}/api/evaluate/submit"
  }
}
