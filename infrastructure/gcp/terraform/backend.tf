# ==============================================================================
# backend.tf - Terraform State管理
# ==============================================================================
#
# 【概要】
# TerraformのStateファイルをCloud Storageに保存します。
#
# 【初回セットアップ】
# 1. Cloud Storageバケットを手動作成
# 2. backend設定のコメントを外す
# 3. terraform init -reconfigure を実行
#
# 【手動セットアップコマンド】
# gcloud storage buckets create gs://ic-test-ai-terraform-state \
#   --project=<PROJECT_ID> \
#   --location=asia-northeast1 \
#   --uniform-bucket-level-access
#
# gcloud storage buckets update gs://ic-test-ai-terraform-state \
#   --versioning
#
# ==============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  # Cloud Storageバックエンド設定（初回デプロイ後にコメント解除）
  # backend "gcs" {
  #   bucket = "ic-test-ai-terraform-state"
  #   prefix = "prod/terraform.tfstate"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}
