# ==============================================================================
# outputs.tf - Terraform 出力定義
# ==============================================================================

# ------------------------------------------------------------------------------
# 全体情報
# ------------------------------------------------------------------------------

output "project_name" {
  description = "プロジェクト名"
  value       = var.project_name
}

output "environment" {
  description = "環境名"
  value       = var.environment
}

output "region" {
  description = "デプロイリージョン"
  value       = var.region
}

# ------------------------------------------------------------------------------
# API Gateway
# ------------------------------------------------------------------------------

output "api_gateway_endpoint" {
  description = "API Gateway エンドポイントURL（VBA/PowerShellに設定）"
  value       = "${aws_api_gateway_stage.prod.invoke_url}"
}

output "api_key" {
  description = "API Key（VBA/PowerShellのX-Api-Keyヘッダーに設定）"
  value       = aws_api_gateway_api_key.ic_test_ai.value
  sensitive   = true
}

output "api_gateway_console_url" {
  description = "API Gateway管理コンソールURL"
  value       = "https://console.aws.amazon.com/apigateway/home?region=${var.region}#/apis/${aws_api_gateway_rest_api.ic_test_ai.id}/stages/${aws_api_gateway_stage.prod.stage_name}"
}

# ------------------------------------------------------------------------------
# App Runner
# ------------------------------------------------------------------------------

output "app_runner_service_name" {
  description = "App Runnerサービス名"
  value       = aws_apprunner_service.ic_test_ai.service_name
}

output "app_runner_console_url" {
  description = "App Runner管理コンソールURL"
  value       = "https://console.aws.amazon.com/apprunner/home?region=${var.region}#/services"
}

# ------------------------------------------------------------------------------
# ECR
# ------------------------------------------------------------------------------

output "ecr_repository_name" {
  description = "ECRリポジトリ名"
  value       = aws_ecr_repository.ic_test_ai.name
}

# ------------------------------------------------------------------------------
# Secrets Manager
# ------------------------------------------------------------------------------

output "secrets_manager_bedrock_key_arn" {
  description = "Bedrock API Key Secrets Manager ARN"
  value       = aws_secretsmanager_secret.bedrock_api_key.arn
}

output "secrets_manager_console_url" {
  description = "Secrets Manager管理コンソールURL"
  value       = "https://console.aws.amazon.com/secretsmanager/home?region=${var.region}"
}

# ------------------------------------------------------------------------------
# CloudWatch
# ------------------------------------------------------------------------------

output "cloudwatch_logs_url" {
  description = "CloudWatch Logs URL"
  value       = "https://console.aws.amazon.com/cloudwatch/home?region=${var.region}#logsV2:log-groups"
}

# xray_service_map_url は cloudwatch.tf で定義

# ------------------------------------------------------------------------------
# デプロイ後の手順
# ------------------------------------------------------------------------------

output "post_deployment_steps" {
  description = "デプロイ後の設定手順"
  value       = <<-EOT
========================================
デプロイ完了！次の手順を実施してください
========================================

1. Secrets Managerにシークレットを設定:
   aws secretsmanager put-secret-value \
     --secret-id ${aws_secretsmanager_secret.bedrock_api_key.name} \
     --secret-string "<実際のAPIキー>"

   aws secretsmanager put-secret-value \
     --secret-id ${aws_secretsmanager_secret.textract_api_key.name} \
     --secret-string "<実際のAPIキー>"

2. ECRにDockerイメージをプッシュ:
   aws ecr get-login-password --region ${var.region} | docker login --username AWS --password-stdin ${aws_ecr_repository.ic_test_ai.repository_url}
   docker build -t ${aws_ecr_repository.ic_test_ai.repository_url}:latest .
   docker push ${aws_ecr_repository.ic_test_ai.repository_url}:latest

3. App Runnerを更新:
   aws apprunner start-deployment --service-arn ${aws_apprunner_service.ic_test_ai.arn}

4. VBA/PowerShellのエンドポイントとAPI Keyを更新:
   - エンドポイント: ${aws_api_gateway_stage.prod.invoke_url}
   - API Key: terraform output -raw api_key

========================================
EOT
}
