# ==============================================================================
# backend.tf - Terraform State管理
# ==============================================================================
#
# 【概要】
# TerraformのStateファイルをAzure Blob Storageに保存します。
#
# 【初回セットアップ】
# 1. Storage Accountを手動作成
# 2. backend設定のコメントを外す
# 3. terraform init -reconfigure を実行
#
# 【手動セットアップコマンド】
# az storage account create \
#   --name stictestaiterraformstate \
#   --resource-group rg-terraform-state \
#   --location japaneast \
#   --sku Standard_LRS
#
# az storage container create \
#   --name tfstate \
#   --account-name stictestaiterraformstate
#
# ==============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }

  # Azure Blob Storageバックエンド設定（初回デプロイ後にコメント解除）
  # backend "azurerm" {
  #   resource_group_name  = "rg-terraform-state"
  #   storage_account_name = "stictestaiterraformstate"
  #   container_name       = "tfstate"
  #   key                  = "prod/azure.tfstate"
  # }
}

provider "azurerm" {
  skip_provider_registration = true
  features {
    key_vault {
      purge_soft_delete_on_destroy = false
    }
  }
}

data "azurerm_client_config" "current" {}
