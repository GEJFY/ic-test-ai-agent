# AWS Lambda デプロイガイド

内部統制テスト評価AIシステムのAWS Lambda版デプロイ手順です。

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
| Lambda | APIホスティング | 1024MB+ メモリ推奨 |
| API Gateway | HTTPエンドポイント | HTTP API (v2) 推奨 |
| Bedrock | LLM処理 | Claude 3.5 Sonnet |
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

### 1. セットアップ

```powershell
# ディレクトリ移動
cd platforms/aws

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
python lambda_handler.py
```

サーバーが起動したら:
- http://localhost:8080/health - ヘルスチェック
- http://localhost:8080/config - 設定確認
- http://localhost:8080/evaluate - 評価API (POST)

---

## デプロイ手順

### 1. デプロイパッケージ作成

```powershell
# パッケージディレクトリ作成
mkdir package

# 依存関係インストール
pip install -r requirements.txt -t package/

# ソースコードコピー
Copy-Item -Recurse ../../src/* package/
Copy-Item lambda_handler.py package/

# ZIPファイル作成
Compress-Archive -Path package/* -DestinationPath deployment.zip -Force
```

### 2. IAMロール作成（初回のみ）

```powershell
# 信頼ポリシーファイル作成
@'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
'@ | Out-File -Encoding utf8 trust-policy.json

# ロール作成
aws iam create-role `
  --role-name lambda-ic-test-role `
  --assume-role-policy-document file://trust-policy.json

# ポリシーアタッチ（基本実行権限）
aws iam attach-role-policy `
  --role-name lambda-ic-test-role `
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Bedrockアクセス権限
aws iam attach-role-policy `
  --role-name lambda-ic-test-role `
  --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess

# Textractアクセス権限（OCR使用時）
aws iam attach-role-policy `
  --role-name lambda-ic-test-role `
  --policy-arn arn:aws:iam::aws:policy/AmazonTextractFullAccess
```

### 3. Lambda関数作成

```powershell
# アカウントID取得
$ACCOUNT_ID = aws sts get-caller-identity --query Account --output text

# Lambda関数作成
aws lambda create-function `
  --function-name ic-test-evaluate `
  --runtime python3.11 `
  --handler lambda_handler.handler `
  --zip-file fileb://deployment.zip `
  --role "arn:aws:iam::${ACCOUNT_ID}:role/lambda-ic-test-role" `
  --timeout 300 `
  --memory-size 1024 `
  --environment "Variables={LLM_PROVIDER=AWS,AWS_REGION=ap-northeast-1,OCR_PROVIDER=AWS}"
```

### 4. 更新（2回目以降）

```powershell
aws lambda update-function-code `
  --function-name ic-test-evaluate `
  --zip-file fileb://deployment.zip
```

### 5. API Gateway設定

```powershell
# HTTP API作成
aws apigatewayv2 create-api `
  --name ic-test-api `
  --protocol-type HTTP `
  --target "arn:aws:lambda:ap-northeast-1:${ACCOUNT_ID}:function:ic-test-evaluate"

# Lambda権限追加
aws lambda add-permission `
  --function-name ic-test-evaluate `
  --statement-id apigateway-invoke `
  --action lambda:InvokeFunction `
  --principal apigateway.amazonaws.com
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

### Lambda環境変数更新

```powershell
aws lambda update-function-configuration `
  --function-name ic-test-evaluate `
  --environment "Variables={
    LLM_PROVIDER=AWS,
    AWS_REGION=ap-northeast-1,
    OCR_PROVIDER=AWS,
    JOB_STORAGE_PROVIDER=AWS,
    AWS_DYNAMODB_TABLE=EvaluationJobs,
    JOB_QUEUE_PROVIDER=AWS,
    AWS_SQS_QUEUE_NAME=evaluation-jobs
  }"
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
2. Claude 3.5 Sonnetを有効化

### 2. Lambda タイムアウト

**原因**: 処理時間が300秒を超えた

**解決方法**:
```powershell
aws lambda update-function-configuration `
  --function-name ic-test-evaluate `
  --timeout 900  # 最大15分
```

### 3. メモリ不足

**原因**: OCR処理でメモリが不足

**解決方法**:
```powershell
aws lambda update-function-configuration `
  --function-name ic-test-evaluate `
  --memory-size 2048  # 2GB
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
| Lambda | 1,000回 × 60秒 × 1GB | ~$1 |
| API Gateway | 1,000リクエスト | ~$0.01 |
| Bedrock (Claude 3.5) | 7.6M tokens | ~$50 |
| Textract | 2,000ページ | ~$3 |
| DynamoDB | 1GB, 10,000 WCU | ~$2 |
| SQS | 10,000メッセージ | ~$0.01 |
| **合計** | | **~$56/月** |

---

## 参考リンク

- [AWS Lambda 開発者ガイド](https://docs.aws.amazon.com/lambda/latest/dg/)
- [Amazon Bedrock ドキュメント](https://docs.aws.amazon.com/bedrock/)
- [Amazon Textract ドキュメント](https://docs.aws.amazon.com/textract/)
- [DynamoDB 開発者ガイド](https://docs.aws.amazon.com/dynamodb/)
- [Amazon SQS 開発者ガイド](https://docs.aws.amazon.com/sqs/)
