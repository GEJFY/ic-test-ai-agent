# AWS インフラストラクチャ - デプロイガイド

## 概要

内部統制テスト評価AIシステムのAWSインフラストラクチャをTerraformで管理します。

### デプロイされるリソース

| リソース | 用途 | 月額コスト（想定） |
|---------|------|------------------|
| **API Gateway** (REST API) | API Gateway層、認証、レート制限 | ~$3.50 |
| **App Runner** | バックエンドAPI（Dockerコンテナ） | ~$5-7 |
| **ECR** (Elastic Container Registry) | Dockerイメージ管理 | ~$1.00 |
| **Secrets Manager** | シークレット管理 | ~$6.20 |
| **CloudWatch Logs/X-Ray** | 監視、ログ、トレース | ~$2.00 |
| **合計** | | **~$17.70/月** |

## 前提条件

### 必要なツール

```bash
# Terraform
terraform --version  # 1.5.0以上

# AWS CLI
aws --version  # 2.13.0以上

# jq（オプション、JSONパース用）
jq --version
```

### AWS CLI設定

```bash
# AWS CLIログイン
aws configure

# プロファイル確認
aws sts get-caller-identity
```

## デプロイ手順

### ステップ1: terraform.tfvars作成

`terraform/terraform.tfvars` ファイルを作成し、環境に合わせて値を設定します。

```hcl
# terraform/terraform.tfvars
project_name = "ic-test-ai"
environment  = "prod"
region       = "ap-northeast-1"

# シークレット（デプロイ後に実際の値に更新）
bedrock_api_key  = "REPLACE_WITH_ACTUAL_API_KEY"
textract_api_key = "REPLACE_WITH_ACTUAL_API_KEY"
openai_api_key   = ""  # フォールバック用（オプション）

# レート制限設定（必要に応じて調整）
api_gateway_throttle_burst_limit = 100
api_gateway_throttle_rate_limit  = 50

# コスト最適化設定
cloudwatch_log_retention_days = 30
enable_xray_tracing           = true
enable_cloudwatch_alarms      = true
```

### ステップ2: Terraform初期化

```bash
cd infrastructure/aws/terraform

# Terraform初期化
terraform init
```

### ステップ3: デプロイプラン確認

```bash
# デプロイ内容を確認
terraform plan -out=tfplan

# ※ 作成されるリソース数、変更内容を確認してください
```

### ステップ4: デプロイ実行

```bash
# デプロイ実行（約5-10分）
terraform apply tfplan

# 出力情報を確認
terraform output
```

**デプロイ完了後、以下の情報をメモしてください：**
- `api_gateway_endpoint`: VBA/PowerShellで使用するエンドポイント
- `api_key`: VBA/PowerShellの`X-Api-Key`ヘッダーに設定（`terraform output -raw api_key`で取得）
- `app_runner_service_url`: App Runnerサービス URL
- `ecr_repository_url`: ECRリポジトリ URL

### ステップ5: Secrets Managerにシークレットを設定

**重要：デプロイ時はダミー値が設定されます。以下のコマンドで実際のAPI Keyを設定してください。**

```bash
# Bedrock API Key設定
aws secretsmanager put-secret-value \
  --secret-id ic-test-ai-prod-bedrock-api-key \
  --secret-string "<実際のAPIキー>"

# Textract API Key設定
aws secretsmanager put-secret-value \
  --secret-id ic-test-ai-prod-textract-api-key \
  --secret-string "<実際のAPIキー>"

# OpenAI API Key設定（オプション）
aws secretsmanager put-secret-value \
  --secret-id ic-test-ai-prod-openai-api-key \
  --secret-string "<実際のAPIキー>"
```

### ステップ6: Dockerイメージをビルド・プッシュしてデプロイ

```bash
# ECRリポジトリURLを取得
ECR_REPO=$(cd infrastructure/aws/terraform && terraform output -raw ecr_repository_url)
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION="ap-northeast-1"

# ECRにログイン
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Dockerイメージをビルド（プロジェクトルートで実行）
docker build -t $ECR_REPO:latest -f platforms/local/Dockerfile .

# ECRにプッシュ
docker push $ECR_REPO:latest

# App Runnerが自動的に新しいイメージを検出してデプロイします
```

### ステップ7: VBA/PowerShellのエンドポイント変更

**CallCloudApi.ps1 (PowerShell):**

```powershell
# API Gateway経由のエンドポイントに変更
$ApiUrl = (terraform output -raw api_gateway_endpoint)
$ApiKey = (terraform output -raw api_key)

# ヘッダー設定
$headers = @{
    "Content-Type" = "application/json; charset=utf-8"
    "X-Api-Key" = $ApiKey
    "X-Correlation-ID" = $CorrelationId
}
```

## デプロイ後の確認

### 1. ヘルスチェック

```bash
# API Keyを取得
API_KEY=$(terraform output -raw api_key)
API_ENDPOINT=$(terraform output -raw api_gateway_endpoint | sed 's|/evaluate||')

# ヘルスチェック
curl -X GET \
  -H "X-Api-Key: $API_KEY" \
  "$API_ENDPOINT/health"
```

### 2. 相関IDフロー確認

```bash
# テストリクエスト送信
CORRELATION_ID=$(uuidgen)
curl -X POST \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $API_KEY" \
  -H "X-Correlation-ID: $CORRELATION_ID" \
  -d '{"items":[{"ID":"001","controlObjective":"test","testProcedure":"test","acceptanceCriteria":"test"}]}' \
  "$(terraform output -raw api_gateway_endpoint)"

# CloudWatch Logs Insightsでログ確認
# AWS Console → CloudWatch → Logs Insights
# ログ グループ: /aws/lambda/ic-test-ai-prod-evaluate
# クエリ:
fields @timestamp, @message, correlation_id
| filter correlation_id like /$CORRELATION_ID/
| sort @timestamp asc
```

### 3. X-Ray Service Mapで依存関係確認

```bash
# X-Ray Service Map URL
terraform output xray_service_map_url
```

以下が可視化されていることを確認：
- PowerShell → API Gateway → App Runner → Bedrock API
- 相関IDですべてのリクエストが追跡可能

## トラブルシューティング

### デプロイエラー: "AccessDenied: User is not authorized"

IAM権限不足です。必要な権限：

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:*",
        "apigateway:*",
        "iam:*",
        "s3:*",
        "secretsmanager:*",
        "logs:*",
        "xray:*",
        "cloudwatch:*"
      ],
      "Resource": "*"
    }
  ]
}
```

### App Runner: Secrets Managerアクセスエラー

IAMロール権限確認：

```bash
# App Runner実行ロールのポリシー確認
aws iam list-attached-role-policies \
  --role-name ic-test-ai-prod-apprunner-instance-role
```

### API Gateway: 403 Forbidden

API Keyが正しく設定されているか確認：

```bash
# API Key値を取得
terraform output -raw api_key

# リクエストヘッダーに X-Api-Key を含めているか確認
```

### CloudWatch Logs: ログが表示されない

ログ伝播に最大5分かかります。しばらく待ってから再確認してください。

## リソース削除

```bash
# 全リソース削除
terraform destroy

# ECRリポジトリのイメージを手動削除（必要な場合）
aws ecr batch-delete-image --repository-name ic-test-ai --image-ids imageTag=latest
```

## Terraform State管理（推奨）

### S3バックエンド設定

```bash
# 1. S3バケット作成（State保存用）
aws s3api create-bucket \
  --bucket ic-test-ai-terraform-state \
  --region ap-northeast-1 \
  --create-bucket-configuration LocationConstraint=ap-northeast-1

# バージョニング有効化
aws s3api put-bucket-versioning \
  --bucket ic-test-ai-terraform-state \
  --versioning-configuration Status=Enabled

# 2. DynamoDBテーブル作成（Stateロック用）
aws dynamodb create-table \
  --table-name ic-test-ai-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --provisioned-throughput ReadCapacityUnits=1,WriteCapacityUnits=1 \
  --region ap-northeast-1

# 3. backend.tf のコメントを外す
# 4. 再初期化
terraform init -reconfigure
```

## コスト最適化

### 1. X-Rayサンプリング調整

`cloudwatch.tf` の `fixed_rate` を調整：

```hcl
fixed_rate = 0.1  # 初期10% → 1%に削減でコスト削減
```

### 2. ログ保持期間短縮

`variables.tf` の `cloudwatch_log_retention_days` を調整：

```hcl
cloudwatch_log_retention_days = 7  # 初期30日 → 7日に短縮
```

### 3. App Runner同時実行数制限

`variables.tf` の App Runner auto scaling 設定：

```hcl
apprunner_max_concurrency = 25  # 1インスタンスあたり最大25同時リクエスト
apprunner_max_size        = 5   # 最大5インスタンスにスケール
```

## セキュリティ強化（本番環境推奨）

### 1. API Gatewayリソースポリシー

特定IPアドレスのみ許可：

```hcl
resource "aws_api_gateway_rest_api_policy" "ip_whitelist" {
  rest_api_id = aws_api_gateway_rest_api.ic_test_ai.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = "*"
        Action = "execute-api:Invoke"
        Resource = "${aws_api_gateway_rest_api.ic_test_ai.execution_arn}/*"
        Condition = {
          IpAddress = {
            "aws:SourceIp" = ["xxx.xxx.xxx.xxx/32"]
          }
        }
      }
    ]
  })
}
```

### 2. Secrets Manager自動ローテーション

将来対応：App Runnerインスタンスでシークレット自動ローテーション実装

### 3. VPC統合

App RunnerをVPCコネクタで接続（プライベートサブネット）

## 参考リンク

- [AWS App Runner Terraform](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/apprunner_service)
- [AWS API Gateway Terraform](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/api_gateway_rest_api)
- [AWS Secrets Manager Terraform](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/secretsmanager_secret)
- [AWS X-Ray ドキュメント](https://docs.aws.amazon.com/xray/)
