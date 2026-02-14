# ==============================================================================
# app-runner.tf - AWS App Runner リソース定義
# ==============================================================================
#
# 【概要】
# 内部統制テスト評価AIのバックエンドAPI（AWS App Runner）を構築します。
#
# 【機能】
# - ECRリポジトリ（Dockerイメージ保存）
# - App Runnerサービス（コンテナ実行）
# - IAMロール（Secrets Manager、Bedrock、Textract）
# - 自動スケーリング
# - ヘルスチェック
#
# ==============================================================================

# ------------------------------------------------------------------------------
# ECR リポジトリ
# ------------------------------------------------------------------------------

resource "aws_ecr_repository" "ic_test_ai" {
  name                 = "${var.project_name}-${var.environment}"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-ecr"
    Environment = var.environment
  })
}

# ECRライフサイクルポリシー（古いイメージ自動削除）
resource "aws_ecr_lifecycle_policy" "ic_test_ai" {
  repository = aws_ecr_repository.ic_test_ai.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "古いイメージを削除（最新10個を保持）"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# ------------------------------------------------------------------------------
# App Runner ECR Access IAMロール
# ------------------------------------------------------------------------------

resource "aws_iam_role" "apprunner_ecr_access" {
  name = "${var.project_name}-${var.environment}-apprunner-ecr-access"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "build.apprunner.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-apprunner-ecr-access"
    Environment = var.environment
  })
}

resource "aws_iam_role_policy_attachment" "apprunner_ecr_access" {
  role       = aws_iam_role.apprunner_ecr_access.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

# ------------------------------------------------------------------------------
# App Runner Instance IAMロール
# ------------------------------------------------------------------------------

resource "aws_iam_role" "apprunner_instance" {
  name = "${var.project_name}-${var.environment}-apprunner-instance-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "tasks.apprunner.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-apprunner-instance-role"
    Environment = var.environment
  })
}

# Secrets Manager読み取りポリシー
resource "aws_iam_role_policy_attachment" "apprunner_secrets" {
  role       = aws_iam_role.apprunner_instance.name
  policy_arn = aws_iam_policy.apprunner_secrets_read.arn
}

# Bedrock呼び出しポリシー
resource "aws_iam_role_policy" "apprunner_bedrock" {
  name = "${var.project_name}-${var.environment}-apprunner-bedrock"
  role = aws_iam_role.apprunner_instance.id

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
resource "aws_iam_role_policy" "apprunner_textract" {
  name = "${var.project_name}-${var.environment}-apprunner-textract"
  role = aws_iam_role.apprunner_instance.id

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

# X-Rayトレーシングポリシー
resource "aws_iam_role_policy_attachment" "apprunner_xray" {
  count      = var.enable_xray_tracing ? 1 : 0
  role       = aws_iam_role.apprunner_instance.name
  policy_arn = "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
}

# ------------------------------------------------------------------------------
# App Runner サービス
# ------------------------------------------------------------------------------

resource "aws_apprunner_service" "ic_test_ai" {
  service_name = "${var.project_name}-${var.environment}-api"

  source_configuration {
    auto_deployments_enabled = false

    authentication_configuration {
      access_role_arn = aws_iam_role.apprunner_ecr_access.arn
    }

    image_repository {
      image_identifier      = "${aws_ecr_repository.ic_test_ai.repository_url}:${var.container_image_tag}"
      image_repository_type = "ECR"

      image_configuration {
        port = "8080"

        runtime_environment_variables = {
          # LLMプロバイダー設定
          LLM_PROVIDER         = "AWS"
          OCR_PROVIDER         = "AWS"
          AWS_BEDROCK_MODEL_ID = var.aws_bedrock_model_id
          AWS_REGION_NAME      = var.region

          # オーケストレータ・パフォーマンス設定
          USE_GRAPH_ORCHESTRATOR = "true"
          MAX_PLAN_REVISIONS     = "1"
          MAX_JUDGMENT_REVISIONS = "1"
          SKIP_PLAN_CREATION     = "false"

          # 非同期ジョブ処理設定
          JOB_STORAGE_PROVIDER      = "AWS"
          JOB_QUEUE_PROVIDER        = "AWS"
          AWS_DYNAMODB_TABLE_NAME   = aws_dynamodb_table.evaluation_jobs.name
          AWS_SQS_QUEUE_URL         = aws_sqs_queue.evaluation_queue.url

          # タイムアウト設定
          FUNCTION_TIMEOUT_SECONDS = tostring(var.app_runner_timeout)

          # デバッグ設定
          DEBUG = "false"
        }
      }
    }
  }

  instance_configuration {
    cpu               = var.app_runner_cpu
    memory            = var.app_runner_memory
    instance_role_arn = aws_iam_role.apprunner_instance.arn
  }

  health_check_configuration {
    protocol            = "HTTP"
    path                = "/health"
    interval            = 10
    timeout             = 5
    healthy_threshold   = 1
    unhealthy_threshold = 5
  }

  auto_scaling_configuration_arn = aws_apprunner_auto_scaling_configuration_version.ic_test_ai.arn

  network_configuration {
    egress_configuration {
      egress_type = "DEFAULT"
    }
  }

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-api"
    Environment = var.environment
  })

  lifecycle {
    ignore_changes = [
      source_configuration[0].image_repository[0].image_identifier,
    ]
  }
}

# ------------------------------------------------------------------------------
# App Runner Auto Scaling
# ------------------------------------------------------------------------------

resource "aws_apprunner_auto_scaling_configuration_version" "ic_test_ai" {
  auto_scaling_configuration_name = "${var.project_name}-${var.environment}-autoscaling"

  max_concurrency = var.app_runner_max_concurrency
  max_size        = var.app_runner_max_size
  min_size        = 1

  tags = merge(var.tags, {
    Name        = "${var.project_name}-${var.environment}-autoscaling"
    Environment = var.environment
  })
}

# ------------------------------------------------------------------------------
# 出力
# ------------------------------------------------------------------------------

output "app_runner_service_url" {
  description = "App RunnerサービスURL"
  value       = "https://${aws_apprunner_service.ic_test_ai.service_url}"
}

output "app_runner_service_arn" {
  description = "App RunnerサービスARN"
  value       = aws_apprunner_service.ic_test_ai.arn
}

output "ecr_repository_url" {
  description = "ECRリポジトリURL"
  value       = aws_ecr_repository.ic_test_ai.repository_url
}
