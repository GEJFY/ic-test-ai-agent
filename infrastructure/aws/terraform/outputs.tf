# ==============================================================================
# outputs.tf - Terraform 出力定義
# ==============================================================================
#
# 【概要】
# デプロイ完了後に必要な情報を出力します。
#
# 【出力内容】
# - API GatewayエンドポイントURL（VBA/PowerShell設定用）
# - API Key（VBA/PowerShell設定用）
# - Lambda関数名（コードデプロイ用）
# - CloudWatchダッシュボードURL
# - X-Ray Service MapURL
#
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
  value       = "${aws_api_gateway_stage.prod.invoke_url}/evaluate"
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
# Lambda
# ------------------------------------------------------------------------------

output "lambda_function_name" {
  description = "Lambda関数名（コードデプロイ用）"
  value       = aws_lambda_function.ic_test_ai.function_name
}

output "lambda_function_arn" {
  description = "Lambda関数ARN"
  value       = aws_lambda_function.ic_test_ai.arn
}

output "lambda_console_url" {
  description = "Lambda管理コンソールURL"
  value       = "https://console.aws.amazon.com/lambda/home?region=${var.region}#/functions/${aws_lambda_function.ic_test_ai.function_name}"
}

output "s3_bucket_name" {
  description = "Lambdaデプロイメント用S3バケット名"
  value       = aws_s3_bucket.lambda_deployments.id
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
# CloudWatch / X-Ray
# ------------------------------------------------------------------------------

output "cloudwatch_dashboard_url" {
  description = "CloudWatchダッシュボードURL"
  value       = aws_cloudwatch_dashboard.ic_test_ai
.dashboard_name != "" ? "https://console.aws.amazon.com/cloudwatch/home?region=${var.region}#dashboards:name=${aws_cloudwatch_dashboard.ic_test_ai.dashboard_name}" : ""
}

output "cloudwatch_logs_url" {
  description = "CloudWatch Logs URL（Lambda）"
  value       = "https://console.aws.amazon.com/cloudwatch/home?region=${var.region}#logsV2:log-groups/log-group/${replace(aws_cloudwatch_log_group.lambda.name, "/", "$252F")}"
}

output "xray_service_map_url" {
  description = "X-Ray Service MapURL"
  value       = var.enable_xray_tracing ? "https://console.aws.amazon.com/xray/home?region=${var.region}#/service-map" : "X-Ray disabled"
}

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

2. Lambda関数にコードをデプロイ:
   cd platforms/aws

   # デプロイパッケージ作成
   zip -r lambda-deployment.zip lambda_handler.py ../../src/

   # S3にアップロード
   aws s3 cp lambda-deployment.zip s3://${aws_s3_bucket.lambda_deployments.id}/

   # Lambda更新
   aws lambda update-function-code \
     --function-name ${aws_lambda_function.ic_test_ai.function_name} \
     --s3-bucket ${aws_s3_bucket.lambda_deployments.id} \
     --s3-key lambda-deployment.zip

3. VBA/PowerShellのエンドポイントとAPI Keyを更新:
   - エンドポイント: ${aws_api_gateway_stage.prod.invoke_url}/evaluate
   - API Key: terraform output -raw api_key

4. 相関IDフローを確認:
   CloudWatch Logs Insightsで以下のクエリを実行:

   fields @timestamp, @message, correlation_id
   | filter correlation_id like /<X-Correlation-IDヘッダーの値>/
   | sort @timestamp asc

5. X-Ray Service Mapで依存関係を確認:
   ${var.enable_xray_tracing ? "https://console.aws.amazon.com/xray/home?region=${var.region}#/service-map" : "X-Rayが無効です"}

========================================
EOT
}
