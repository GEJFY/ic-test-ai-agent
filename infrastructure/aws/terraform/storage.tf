# ==============================================================================
# storage.tf - AWS Storage リソース定義（非同期ジョブ処理用）
# ==============================================================================

# ------------------------------------------------------------------------------
# DynamoDB テーブル（ジョブ追跡）
# ------------------------------------------------------------------------------

resource "aws_dynamodb_table" "evaluation_jobs" {
  name         = "${var.project_name}-${var.environment}-evaluation-jobs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "job_id"

  attribute {
    name = "job_id"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-evaluation-jobs"
    Environment = var.environment
  })
}

# ------------------------------------------------------------------------------
# SQS キュー（ジョブキュー）
# ------------------------------------------------------------------------------

resource "aws_sqs_queue" "evaluation_queue" {
  name                       = "${var.project_name}-${var.environment}-evaluation-queue"
  visibility_timeout_seconds = 600
  message_retention_seconds  = 86400
  receive_wait_time_seconds  = 10

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-evaluation-queue"
    Environment = var.environment
  })
}

# デッドレターキュー
resource "aws_sqs_queue" "evaluation_dlq" {
  name                      = "${var.project_name}-${var.environment}-evaluation-dlq"
  message_retention_seconds = 1209600

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-evaluation-dlq"
    Environment = var.environment
  })
}

resource "aws_sqs_queue_redrive_policy" "evaluation_queue" {
  queue_url = aws_sqs_queue.evaluation_queue.id
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.evaluation_dlq.arn
    maxReceiveCount     = 3
  })
}

# ------------------------------------------------------------------------------
# DynamoDB + SQS アクセスポリシー
# ------------------------------------------------------------------------------

resource "aws_iam_role_policy" "apprunner_storage" {
  name = "${var.project_name}-${var.environment}-apprunner-storage"
  role = aws_iam_role.apprunner_instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          aws_dynamodb_table.evaluation_jobs.arn,
          "${aws_dynamodb_table.evaluation_jobs.arn}/index/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:GetQueueUrl"
        ]
        Resource = [
          aws_sqs_queue.evaluation_queue.arn
        ]
      }
    ]
  })
}

# ------------------------------------------------------------------------------
# 出力
# ------------------------------------------------------------------------------

output "dynamodb_table_name" {
  description = "DynamoDBジョブテーブル名"
  value       = aws_dynamodb_table.evaluation_jobs.name
}

output "sqs_queue_url" {
  description = "SQSジョブキューURL"
  value       = aws_sqs_queue.evaluation_queue.url
}
