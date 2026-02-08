# =============================================================================
# AWS Module - 内部統制テスト評価AIシステム
# =============================================================================
#
# 作成するリソース:
#   - IAM Role (Lambda用)
#   - Lambda Function
#   - API Gateway (HTTP API)
#   - DynamoDB Table (ジョブ管理用)
#   - SQS Queue (非同期処理用)
#
# =============================================================================

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
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

variable "region" {
  description = "AWS region"
  type        = string
  default     = "ap-northeast-1"
}

variable "llm_config" {
  description = "LLM configuration"
  type = object({
    model_id = optional(string, "jp.anthropic.claude-sonnet-4-5-20250929-v1:0")
  })
  default = {}
}

variable "ocr_config" {
  description = "OCR configuration"
  type = object({
    provider = string
  })
  default = {
    provider = "AWS"
  }
}

variable "app_settings" {
  description = "Application settings"
  type = object({
    max_plan_revisions     = optional(number, 1)
    max_judgment_revisions = optional(number, 1)
    skip_plan_creation     = optional(bool, false)
    async_mode             = optional(bool, true)
    memory_size            = optional(number, 1024)
    timeout                = optional(number, 300)
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
# IAM Role for Lambda
# -----------------------------------------------------------------------------

resource "aws_iam_role" "lambda" {
  name = "${local.resource_prefix}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = local.all_tags
}

# Lambda基本実行ポリシー
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Bedrock アクセスポリシー
resource "aws_iam_role_policy_attachment" "bedrock" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonBedrockFullAccess"
}

# Textract アクセスポリシー (OCR用)
resource "aws_iam_role_policy_attachment" "textract" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonTextractFullAccess"
}

# DynamoDB アクセスポリシー
resource "aws_iam_role_policy" "dynamodb" {
  name = "${local.resource_prefix}-dynamodb-policy"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = aws_dynamodb_table.jobs.arn
      }
    ]
  })
}

# SQS アクセスポリシー
resource "aws_iam_role_policy" "sqs" {
  name = "${local.resource_prefix}-sqs-policy"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.jobs.arn
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# DynamoDB Table (ジョブ管理)
# -----------------------------------------------------------------------------

resource "aws_dynamodb_table" "jobs" {
  name           = "${local.resource_prefix}-jobs"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "job_id"

  attribute {
    name = "job_id"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = local.all_tags
}

# -----------------------------------------------------------------------------
# SQS Queue (非同期処理)
# -----------------------------------------------------------------------------

resource "aws_sqs_queue" "jobs" {
  name                       = "${local.resource_prefix}-jobs"
  visibility_timeout_seconds = var.app_settings.timeout + 60
  message_retention_seconds  = 86400  # 1 day

  tags = local.all_tags
}

# -----------------------------------------------------------------------------
# Lambda Function
# -----------------------------------------------------------------------------

resource "aws_lambda_function" "main" {
  function_name = "${local.resource_prefix}-evaluate"
  role          = aws_iam_role.lambda.arn
  handler       = "lambda_handler.handler"
  runtime       = "python3.11"
  memory_size   = var.app_settings.memory_size
  timeout       = var.app_settings.timeout

  # デプロイはCI/CDで行うため、プレースホルダーZIPを使用
  filename         = "${path.module}/placeholder.zip"
  source_code_hash = filebase64sha256("${path.module}/placeholder.zip")

  environment {
    variables = {
      LLM_PROVIDER           = "AWS"
      AWS_BEDROCK_MODEL_ID   = var.llm_config.model_id
      OCR_PROVIDER           = var.ocr_config.provider
      JOB_STORAGE_PROVIDER   = "AWS"
      JOB_QUEUE_PROVIDER     = "AWS"
      AWS_DYNAMODB_TABLE_NAME = aws_dynamodb_table.jobs.name
      AWS_SQS_QUEUE_URL      = aws_sqs_queue.jobs.url
      MAX_PLAN_REVISIONS     = tostring(var.app_settings.max_plan_revisions)
      MAX_JUDGMENT_REVISIONS = tostring(var.app_settings.max_judgment_revisions)
      SKIP_PLAN_CREATION     = tostring(var.app_settings.skip_plan_creation)
      LOG_TO_FILE            = "false"
    }
  }

  tags = local.all_tags

  lifecycle {
    ignore_changes = [
      filename,
      source_code_hash,
    ]
  }
}

# -----------------------------------------------------------------------------
# API Gateway (HTTP API)
# -----------------------------------------------------------------------------

resource "aws_apigatewayv2_api" "main" {
  name          = "${local.resource_prefix}-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["*"]
    max_age       = 300
  }

  tags = local.all_tags
}

resource "aws_apigatewayv2_stage" "main" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.main.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.main.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------

output "lambda_function_name" {
  description = "Lambda function name"
  value       = aws_lambda_function.main.function_name
}

output "lambda_function_arn" {
  description = "Lambda function ARN"
  value       = aws_lambda_function.main.arn
}

output "api_gateway_url" {
  description = "API Gateway URL"
  value       = aws_apigatewayv2_api.main.api_endpoint
}

output "dynamodb_table_name" {
  description = "DynamoDB table name"
  value       = aws_dynamodb_table.jobs.name
}

output "sqs_queue_url" {
  description = "SQS queue URL"
  value       = aws_sqs_queue.jobs.url
}

output "endpoints" {
  description = "API endpoints"
  value = {
    health   = "${aws_apigatewayv2_api.main.api_endpoint}/health"
    config   = "${aws_apigatewayv2_api.main.api_endpoint}/config"
    evaluate = "${aws_apigatewayv2_api.main.api_endpoint}/evaluate"
    submit   = "${aws_apigatewayv2_api.main.api_endpoint}/evaluate/submit"
  }
}
