# ==============================================================================
# lambda.tf - AWS Lambda リソース定義
# ==============================================================================
#
# 【概要】
# 内部統制テスト評価AIのバックエンドAPI（AWS Lambda）を構築します。
#
# 【機能】
# - Python 3.11ランタイム
# - IAMロール（Secrets Manager、CloudWatch Logs、X-Ray）
# - 環境変数設定（LLMプロバイダー、OCRプロバイダー等）
# - CloudWatch Logs統合
# - X-Rayトレーシング有効化
#
# ==============================================================================

# ------------------------------------------------------------------------------
# S3バケット（Lambda デプロイパッケージ用）
# ------------------------------------------------------------------------------

resource "aws_s3_bucket" "lambda_deployments" {
  bucket = "${var.project_name}-${var.environment}-lambda-deployments-${data.aws_caller_identity.current.account_id}"

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-lambda-deployments"
    Environment = var.environment
  })
}

resource "aws_s3_bucket_versioning" "lambda_deployments" {
  bucket = aws_s3_bucket.lambda_deployments.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "lambda_deployments" {
  bucket = aws_s3_bucket.lambda_deployments.id

  rule {
    id     = "delete-old-versions"
    status = "Enabled"

    noncurrent_version_expiration {
      noncurrent_days = var.s3_lifecycle_expiration_days
    }
  }
}

# ------------------------------------------------------------------------------
# Lambda IAMロール
# ------------------------------------------------------------------------------

resource "aws_iam_role" "lambda_execution" {
  name = "${var.project_name}-${var.environment}-lambda-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-lambda-execution-role"
    Environment = var.environment
  })
}

# Lambda基本実行ポリシー（CloudWatch Logs）
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# X-Rayトレーシングポリシー
resource "aws_iam_role_policy_attachment" "lambda_xray" {
  count      = var.enable_xray_tracing ? 1 : 0
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
}

# Secrets Manager読み取りポリシー
resource "aws_iam_role_policy_attachment" "lambda_secrets" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = aws_iam_policy.lambda_secrets_read.arn
}

# Bedrock呼び出しポリシー
resource "aws_iam_role_policy" "lambda_bedrock" {
  name = "${var.project_name}-${var.environment}-lambda-bedrock"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = "*"
      }
    ]
  })
}

# Textract呼び出しポリシー
resource "aws_iam_role_policy" "lambda_textract" {
  name = "${var.project_name}-${var.environment}-lambda-textract"
  role = aws_iam_role.lambda_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "textract:AnalyzeDocument",
          "textract:DetectDocumentText"
        ]
        Resource = "*"
      }
    ]
  })
}

# ------------------------------------------------------------------------------
# Lambda関数
# ------------------------------------------------------------------------------

# Note: 実際のデプロイパッケージは別途アップロード
# 初回デプロイ時はダミーファイルを使用
resource "aws_lambda_function" "ic_test_ai" {
  function_name = "${var.project_name}-${var.environment}-evaluate"
  role          = aws_iam_role.lambda_execution.arn

  # デプロイパッケージ（後でアップデート）
  s3_bucket = aws_s3_bucket.lambda_deployments.id
  s3_key    = "lambda-deployment.zip"

  handler = "lambda_handler.handler"
  runtime = var.lambda_runtime
  timeout = var.lambda_timeout
  memory_size = var.lambda_memory

  reserved_concurrent_executions = var.lambda_reserved_concurrency

  # 環境変数
  environment {
    variables = {
      # LLMプロバイダー設定
      LLM_PROVIDER = "AWS"

      # Secrets Manager参照
      BEDROCK_API_KEY_SECRET_ARN = aws_secretsmanager_secret.bedrock_api_key.arn
      TEXTRACT_API_KEY_SECRET_ARN = aws_secretsmanager_secret.textract_api_key.arn

      # OCRプロバイダー設定
      OCR_PROVIDER = "AWS"

      # タイムアウト設定
      FUNCTION_TIMEOUT_SECONDS = tostring(var.lambda_timeout)

      # デバッグ設定
      DEBUG = "false"

      # AWS リージョン
      AWS_REGION_NAME = var.region
    }
  }

  # X-Rayトレーシング
  tracing_config {
    mode = var.enable_xray_tracing ? "Active" : "PassThrough"
  }

  # デッドレターキュー（将来対応）
  # dead_letter_config {
  #   target_arn = aws_sqs_queue.lambda_dlq.arn
  # }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-evaluate"
    Environment = var.environment
  })

  # ライフサイクル: 初回デプロイ後は手動アップデート
  lifecycle {
    ignore_changes = [
      s3_key,
      source_code_hash
    ]
  }
}

# ------------------------------------------------------------------------------
# CloudWatch Logsグループ
# ------------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${aws_lambda_function.ic_test_ai.function_name}"
  retention_in_days = var.cloudwatch_log_retention_days

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-lambda-logs"
    Environment = var.environment
  })
}

# ------------------------------------------------------------------------------
# Lambda エイリアス（Blue/Greenデプロイ用）
# ------------------------------------------------------------------------------

resource "aws_lambda_alias" "live" {
  name             = "live"
  description      = "Production live alias"
  function_name    = aws_lambda_function.ic_test_ai.arn
  function_version = "$LATEST"

  # Blue/Greenデプロイ時のトラフィック配分（将来対応）
  # routing_config {
  #   additional_version_weights = {
  #     "2" = 0.1  # カナリアデプロイ: 10%
  #   }
  # }
}

# ------------------------------------------------------------------------------
# 出力
# ------------------------------------------------------------------------------
# Note: lambda_function_arn と lambda_function_name は outputs.tf で定義

output "lambda_invoke_arn" {
  description = "Lambda呼び出しARN（API Gateway統合用）"
  value       = aws_lambda_function.ic_test_ai.invoke_arn
}

output "lambda_role_arn" {
  description = "Lambda実行ロールARN"
  value       = aws_iam_role.lambda_execution.arn
}
