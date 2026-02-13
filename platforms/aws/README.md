# AWS App Runner デプロイガイド

内部統制テスト評価AIシステムのAWS App Runner版デプロイ手順です。

## 目次

1. [必要なAWSリソース](#必要なawsリソース)
2. [環境変数設定](#環境変数設定)
3. [ローカル開発](#ローカル開発)
4. [デプロイ手順](#デプロイ手順)
5. [非同期処理（オプション）](#非同期処理オプション)
6. [IAMポリシー](#iamポリシー)
7. [トラブルシューティング](#トラブルシューティング)

---

## 必要なAWSリソース

### 必須リソース

| サービス | 用途 | SKU/プラン |
|---------|------|-----------|
| App Runner | APIホスティング（Dockerコンテナ） | 1 vCPU / 2GB メモリ推奨 |
| ECR (Elastic Container Registry) | Dockerイメージ管理 | Private |
| API Gateway | HTTPエンドポイント | HTTP API (v2) 推奨 |
| Bedrock | LLM処理 | Claude Sonnet 4.5 |
| Textract | OCR処理 | 従量課金 |

### 非同期処理用（オプション）

| サービス | 用途 | 備考 |
|---------|------|------|
| DynamoDB | ジョブ状態管理 | オンデマンドキャパシティ |
| SQS | ジョブキュー | Standard Queue |
| S3 | 大容量ファイル | 証跡ファイル一時保存 |

---

## 環境変数設定

### 必須設定

```bash
# LLM設定
LLM_PROVIDER=AWS
AWS_REGION=ap-northeast-1

# OCR設定（オプション）
OCR_PROVIDER=AWS  # または NONE
```

### Bedrock モデル設定（オプション）

```bash
# デフォルト: jp.anthropic.claude-sonnet-4-5-20250929-v1:0
AWS_BEDROCK_MODEL_ID=jp.anthropic.claude-sonnet-4-5-20250929-v1:0
```

### 非同期処理設定（オプション）

```bash
# ジョブストレージ
JOB_STORAGE_PROVIDER=AWS
AWS_DYNAMODB_TABLE=EvaluationJobs

# ジョブキュー
JOB_QUEUE_PROVIDER=AWS
AWS_SQS_QUEUE_NAME=evaluation-jobs
```

---

## ローカル開発

全プラットフォーム共通のDockerイメージ（FastAPI/Uvicorn）を使用します。

### 1. セットアップ

```powershell
# ディレクトリ移動
cd platforms/local

# 仮想環境作成
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 依存関係インストール
pip install -r requirements.txt
```

### 2. AWS認証設定

```powershell
# AWS CLIで認証設定
aws configure

# または環境変数で設定
$env:AWS_ACCESS_KEY_ID = "your-access-key"
$env:AWS_SECRET_ACCESS_KEY = "your-secret-key"
$env:AWS_REGION = "ap-northeast-1"
```

### 3. ローカルサーバー起動

```powershell
python main.py
```

サーバーが起動したら:
- http://localhost:8000/health - ヘルスチェック
- http://localhost:8000/config - 設定確認
- http://localhost:8000/evaluate - 評価API (POST)

### 4. Dockerでのローカル実行

```powershell
# プロジェクトルートで実行
docker build -t ic-test-ai:local -f platforms/local/Dockerfile .
docker run -p 8000:8000 --env-file .env ic-test-ai:local
```

---

## デプロイ手順

### 1. ECRリポジトリ作成（初回のみ）

```powershell
aws ecr create-repository --repository-name ic-test-ai --region ap-northeast-1
```

### 2. ECRにログイン

```powershell
$ACCOUNT_ID = aws sts get-caller-identity --query Account --output text
$AWS_REGION = "ap-northeast-1"

aws ecr get-login-password --region $AWS_REGION | `
  docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
```

### 3. Dockerイメージをビルド・プッシュ

```powershell
$ECR_REPO = "$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/ic-test-ai"

# プロジェクトルートで実行
docker build -t "${ECR_REPO}:latest" -f platforms/local/Dockerfile .
docker push "${ECR_REPO}:latest"
```

### 4. IAMロール作成（初回のみ）

```powershell
# App Runnerアクセスロール（ECRからイメージ取得用）
@'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "build.apprunner.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
'@ | Out-File -Encoding utf8 trust-policy-access.json

aws iam create-role `
  --role-name apprunner-ic-test-access-role `
  --assume-role-policy-document file://trust-policy-access.json

aws iam attach-role-policy `
  --role-name apprunner-ic-test-access-role `
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess

# App Runnerインスタンスロール（Bedrock等へのアクセス用）
@'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "tasks.apprunner.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
'@ | Out-File -Encoding utf8 trust-policy-instance.json

aws iam create-role `
  --role-name apprunner-ic-test-instance-role `
  --assume-role-policy-document file://trust-policy-instance.json

aws iam attach-role-policy `
  --role-name apprunner-ic-test-instance-role `
  --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess

aws iam attach-role-policy `
  --role-name apprunner-ic-test-instance-role `
  --policy-arn arn:aws:iam::aws:policy/AmazonTextractFullAccess
```

### 5. App Runnerサービス作成

```powershell
aws apprunner create-service `
  --service-name ic-test-evaluate `
  --source-configuration "{
    \"AuthenticationConfiguration\": {
      \"AccessRoleArn\": \"arn:aws:iam::${ACCOUNT_ID}:role/apprunner-ic-test-access-role\"
    },
    \"ImageRepository\": {
      \"ImageIdentifier\": \"${ECR_REPO}:latest\",
      \"ImageRepositoryType\": \"ECR\",
      \"ImageConfiguration\": {
        \"Port\": \"8000\",
        \"RuntimeEnvironmentVariables\": {
          \"LLM_PROVIDER\": \"AWS\",
          \"AWS_REGION\": \"ap-northeast-1\",
          \"OCR_PROVIDER\": \"AWS\"
        }
      }
    },
    \"AutoDeploymentsEnabled\": true
  }" `
  --instance-configuration "{
    \"Cpu\": \"1 vCPU\",
    \"Memory\": \"2 GB\",
    \"InstanceRoleArn\": \"arn:aws:iam::${ACCOUNT_ID}:role/apprunner-ic-test-instance-role\"
  }"
```

### 6. 更新デプロイ（2回目以降）

AutoDeploymentsEnabled が true の場合、ECR に新しいイメージをプッシュすると自動デプロイされます。

```powershell
# イメージをビルド・プッシュするだけでOK
docker build -t "${ECR_REPO}:latest" -f platforms/local/Dockerfile .
docker push "${ECR_REPO}:latest"
```

---

## 非同期処理（オプション）

504タイムアウト対策として、DynamoDB + SQSによる非同期処理をサポートしています。

### DynamoDBテーブル作成

```powershell
aws dynamodb create-table `
  --table-name EvaluationJobs `
  --attribute-definitions `
    AttributeName=tenant_id,AttributeType=S `
    AttributeName=job_id,AttributeType=S `
    AttributeName=status,AttributeType=S `
    AttributeName=created_at,AttributeType=S `
  --key-schema `
    AttributeName=tenant_id,KeyType=HASH `
    AttributeName=job_id,KeyType=RANGE `
  --global-secondary-indexes `
    "[
      {
        \"IndexName\": \"status-created_at-index\",
        \"KeySchema\": [{\"AttributeName\":\"status\",\"KeyType\":\"HASH\"},{\"AttributeName\":\"created_at\",\"KeyType\":\"RANGE\"}],
        \"Projection\": {\"ProjectionType\":\"ALL\"},
        \"ProvisionedThroughput\": {\"ReadCapacityUnits\":5,\"WriteCapacityUnits\":5}
      },
      {
        \"IndexName\": \"job_id-index\",
        \"KeySchema\": [{\"AttributeName\":\"job_id\",\"KeyType\":\"HASH\"}],
        \"Projection\": {\"ProjectionType\":\"ALL\"},
        \"ProvisionedThroughput\": {\"ReadCapacityUnits\":5,\"WriteCapacityUnits\":5}
      }
    ]" `
  --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5
```

### SQSキュー作成

```powershell
aws sqs create-queue `
  --queue-name evaluation-jobs `
  --attributes MessageRetentionPeriod=1209600,VisibilityTimeout=300,ReceiveMessageWaitTimeSeconds=20
```

---

## IAMポリシー

### 最小権限ポリシー

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "arn:aws:bedrock:*::foundation-model/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "textract:DetectDocumentText",
        "textract:AnalyzeDocument"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/EvaluationJobs",
        "arn:aws:dynamodb:*:*:table/EvaluationJobs/index/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage",
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueUrl",
        "sqs:GetQueueAttributes"
      ],
      "Resource": "arn:aws:sqs:*:*:evaluation-jobs"
    }
  ]
}
```

---

## トラブルシューティング

### 1. Bedrockモデルにアクセスできない

**原因**: モデルアクセスが有効化されていない

**解決方法**:
1. AWS Console → Bedrock → Model access
2. Claude Sonnet 4.5を有効化

### 2. App Runner デプロイ失敗

**原因**: Dockerイメージのビルドエラーまたはヘルスチェック失敗

**解決方法**:
```powershell
# サービスログを確認
aws apprunner list-operations --service-arn <SERVICE_ARN>

# CloudWatch Logsで詳細確認
aws logs tail /aws/apprunner/ic-test-evaluate/service --follow
```

### 3. メモリ不足

**原因**: OCR処理でメモリが不足

**解決方法**:
```powershell
# App Runnerのインスタンスリソースを増加
aws apprunner update-service `
  --service-arn <SERVICE_ARN> `
  --instance-configuration "Cpu=2 vCPU,Memory=4 GB"
```

### 4. DynamoDB書き込みエラー

**原因**: アイテムサイズが400KBを超えた

**解決方法**:
- 大きな証跡ファイルはS3に保存
- `JOB_STORAGE_PROVIDER=AWS` + S3統合を使用

---

## コスト見積もり

### 月1,000項目処理の場合

| サービス | 使用量 | 月額（概算） |
|---------|--------|-------------|
| App Runner | 1 vCPU / 2GB × アイドル時間含む | ~$5-7 |
| ECR | イメージストレージ | ~$1 |
| API Gateway | 1,000リクエスト | ~$0.01 |
| Bedrock (Claude Sonnet 4.5) | 7.6M tokens | ~$50 |
| Textract | 2,000ページ | ~$3 |
| DynamoDB | 1GB, 10,000 WCU | ~$2 |
| SQS | 10,000メッセージ | ~$0.01 |
| **合計** | | **~$61-63/月** |

---

## 参考リンク

- [AWS App Runner ドキュメント](https://docs.aws.amazon.com/apprunner/)
- [Amazon ECR ドキュメント](https://docs.aws.amazon.com/ecr/)
- [Amazon Bedrock ドキュメント](https://docs.aws.amazon.com/bedrock/)
- [Amazon Textract ドキュメント](https://docs.aws.amazon.com/textract/)
- [DynamoDB 開発者ガイド](https://docs.aws.amazon.com/dynamodb/)
- [Amazon SQS 開発者ガイド](https://docs.aws.amazon.com/sqs/)
