# ==============================================================================
# backend.tf - Terraform State管理
# ==============================================================================
#
# 【概要】
# TerraformのStateファイルをS3に保存し、DynamoDBでロック管理を行います。
#
# 【初回セットアップ】
# 1. S3バケットとDynamoDBテーブルを手動作成
# 2. backend設定のコメントを外す
# 3. terraform init -reconfigure を実行
#
# 【手動セットアップコマンド】
# aws s3api create-bucket \
#   --bucket ic-test-ai-terraform-state \
#   --region ap-northeast-1 \
#   --create-bucket-configuration LocationConstraint=ap-northeast-1
#
# aws s3api put-bucket-versioning \
#   --bucket ic-test-ai-terraform-state \
#   --versioning-configuration Status=Enabled
#
# aws dynamodb create-table \
#   --table-name ic-test-ai-terraform-locks \
#   --attribute-definitions AttributeName=LockID,AttributeType=S \
#   --key-schema AttributeName=LockID,KeyType=HASH \
#   --provisioned-throughput ReadCapacityUnits=1,WriteCapacityUnits=1 \
#   --region ap-northeast-1
#
# ==============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # S3バックエンド設定（初回デプロイ後にコメント解除）
  # backend "s3" {
  #   bucket         = "ic-test-ai-terraform-state"
  #   key            = "prod/terraform.tfstate"
  #   region         = "ap-northeast-1"
  #   encrypt        = true
  #   dynamodb_table = "ic-test-ai-terraform-locks"
  # }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = var.tags
  }
}
