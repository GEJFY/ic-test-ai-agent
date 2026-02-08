# =============================================================================
# Client Configuration Template
# =============================================================================
#
# 新規クライアント追加手順:
#   1. このディレクトリを clients/[client-name]/ にコピー
#   2. terraform.tfvars を編集
#   3. terraform init && terraform plan && terraform apply
#
# =============================================================================

terraform {
  required_version = ">= 1.0"

  # リモートバックエンド設定（クライアントごとに変更）
  # backend "azurerm" {
  #   resource_group_name  = "rg-terraform-state"
  #   storage_account_name = "stterraformstate"
  #   container_name       = "tfstate"
  #   key                  = "clients/CLIENT_NAME.tfstate"
  # }

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
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
  description = "Client name (used in resource naming)"
  type        = string
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "cloud_provider" {
  description = "Cloud provider to use (azure, aws, gcp)"
  type        = string
  validation {
    condition     = contains(["azure", "aws", "gcp"], var.cloud_provider)
    error_message = "cloud_provider must be one of: azure, aws, gcp"
  }
}

# Azure specific
variable "azure_location" {
  description = "Azure region"
  type        = string
  default     = "japaneast"
}

variable "azure_subscription_id" {
  description = "Azure subscription ID"
  type        = string
  default     = ""
}

variable "azure_llm_config" {
  description = "Azure LLM configuration"
  type = object({
    endpoint    = string
    api_key     = string
    model       = string
    api_version = optional(string, "2024-08-01-preview")
  })
  default   = null
  sensitive = true
}

# AWS specific
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-northeast-1"
}

variable "aws_llm_config" {
  description = "AWS LLM configuration"
  type = object({
    model_id = optional(string, "jp.anthropic.claude-sonnet-4-5-20250929-v1:0")
  })
  default = {}
}

# GCP specific
variable "gcp_project_id" {
  description = "GCP project ID"
  type        = string
  default     = ""
}

variable "gcp_region" {
  description = "GCP region"
  type        = string
  default     = "asia-northeast1"
}

variable "gcp_llm_config" {
  description = "GCP LLM configuration"
  type = object({
    model = optional(string, "gemini-2.5-flash")
  })
  default = {}
}

variable "gcp_container_image" {
  description = "Container image for GCP Cloud Run"
  type        = string
  default     = ""
}

# Common settings
variable "ocr_config" {
  description = "OCR configuration"
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

# -----------------------------------------------------------------------------
# Provider Configuration
# -----------------------------------------------------------------------------

provider "azurerm" {
  features {}
  subscription_id = var.azure_subscription_id
  skip_provider_registration = true
}

provider "aws" {
  region = var.aws_region
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

# -----------------------------------------------------------------------------
# Module Selection (based on cloud_provider)
# -----------------------------------------------------------------------------

module "azure" {
  source = "../../modules/azure"
  count  = var.cloud_provider == "azure" ? 1 : 0

  client_name  = var.client_name
  environment  = var.environment
  location     = var.azure_location
  llm_config   = var.azure_llm_config
  ocr_config   = var.ocr_config
  app_settings = var.app_settings
}

module "aws" {
  source = "../../modules/aws"
  count  = var.cloud_provider == "aws" ? 1 : 0

  client_name  = var.client_name
  environment  = var.environment
  region       = var.aws_region
  llm_config   = var.aws_llm_config
  ocr_config   = var.ocr_config
  app_settings = var.app_settings
}

module "gcp" {
  source = "../../modules/gcp"
  count  = var.cloud_provider == "gcp" ? 1 : 0

  client_name     = var.client_name
  environment     = var.environment
  project_id      = var.gcp_project_id
  region          = var.gcp_region
  llm_config      = var.gcp_llm_config
  ocr_config      = var.ocr_config
  app_settings    = var.app_settings
  container_image = var.gcp_container_image
}

# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------

output "cloud_provider" {
  description = "Selected cloud provider"
  value       = var.cloud_provider
}

output "client_name" {
  description = "Client name"
  value       = var.client_name
}

output "environment" {
  description = "Environment"
  value       = var.environment
}

output "endpoints" {
  description = "API endpoints"
  value = var.cloud_provider == "azure" ? (
    length(module.azure) > 0 ? module.azure[0].endpoints : {}
  ) : var.cloud_provider == "aws" ? (
    length(module.aws) > 0 ? module.aws[0].endpoints : {}
  ) : var.cloud_provider == "gcp" ? (
    length(module.gcp) > 0 ? module.gcp[0].endpoints : {}
  ) : {}
}
