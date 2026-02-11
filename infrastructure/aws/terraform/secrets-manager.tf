# ==============================================================================
# secrets-manager.tf - AWS Secrets Manager リソース定義
# ==============================================================================
#
# 【概要】
# APIキーやシークレットを安全に管理するためのSecrets Managerシークレットを構築します。
#
# 【機能】
# - シークレット管理（Bedrock API Key、OpenAI API Key等）
# - Lambda関数からのアクセス制御（IAMポリシー）
# - 自動ローテーション機能（将来対応）
# - 削除保護（30日間の復旧期間）
#
# ==============================================================================

# ------------------------------------------------------------------------------
# Bedrock API Key
# ------------------------------------------------------------------------------

resource "aws_secretsmanager_secret" "bedrock_api_key" {
  name        = "${var.project_name}-${var.environment}-bedrock-api-key"
  description = "AWS Bedrock API Key for LLM operations"

  recovery_window_in_days = 30

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-bedrock-api-key"
    Environment = var.environment
  })
}

resource "aws_secretsmanager_secret_version" "bedrock_api_key" {
  secret_id     = aws_secretsmanager_secret.bedrock_api_key.id
  secret_string = var.bedrock_api_key
}

# ------------------------------------------------------------------------------
# Textract API Key
# ------------------------------------------------------------------------------

resource "aws_secretsmanager_secret" "textract_api_key" {
  name        = "${var.project_name}-${var.environment}-textract-api-key"
  description = "AWS Textract API Key for OCR operations"

  recovery_window_in_days = 30

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-textract-api-key"
    Environment = var.environment
  })
}

resource "aws_secretsmanager_secret_version" "textract_api_key" {
  secret_id     = aws_secretsmanager_secret.textract_api_key.id
  secret_string = var.textract_api_key
}

# ------------------------------------------------------------------------------
# OpenAI API Key（フォールバック用）
# ------------------------------------------------------------------------------

resource "aws_secretsmanager_secret" "openai_api_key" {
  name        = "${var.project_name}-${var.environment}-openai-api-key"
  description = "OpenAI API Key (fallback)"

  recovery_window_in_days = 30

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-openai-api-key"
    Environment = var.environment
  })
}

resource "aws_secretsmanager_secret_version" "openai_api_key" {
  secret_id     = aws_secretsmanager_secret.openai_api_key.id
  secret_string = var.openai_api_key != "" ? var.openai_api_key : "NOT_CONFIGURED"
}

# ------------------------------------------------------------------------------
# Lambda IAMポリシー（Secrets Manager読み取り権限）
# ------------------------------------------------------------------------------

resource "aws_iam_policy" "lambda_secrets_read" {
  name        = "${var.project_name}-${var.environment}-lambda-secrets-read"
  description = "Lambda関数がSecrets Managerからシークレットを読み取る権限"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          aws_secretsmanager_secret.bedrock_api_key.arn,
          aws_secretsmanager_secret.textract_api_key.arn,
          aws_secretsmanager_secret.openai_api_key.arn
        ]
      }
    ]
  })

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-lambda-secrets-read"
    Environment = var.environment
  })
}

# ------------------------------------------------------------------------------
# 出力
# ------------------------------------------------------------------------------

output "bedrock_api_key_arn" {
  description = "Bedrock API KeyのSecrets Manager ARN"
  value       = aws_secretsmanager_secret.bedrock_api_key.arn
}

output "textract_api_key_arn" {
  description = "Textract API KeyのSecrets Manager ARN"
  value       = aws_secretsmanager_secret.textract_api_key.arn
}

output "openai_api_key_arn" {
  description = "OpenAI API KeyのSecrets Manager ARN"
  value       = aws_secretsmanager_secret.openai_api_key.arn
}

output "lambda_secrets_read_policy_arn" {
  description = "Lambda Secrets読み取りポリシーARN"
  value       = aws_iam_policy.lambda_secrets_read.arn
}
