# AWS環境セットアップガイド

## 前提条件

- AWSアカウント
- AWS CLI インストール済み
- Terraform インストール済み
- 権限: AdministratorAccess推奨

## セットアップ手順

### 1. AWS CLI設定

```bash
aws configure
# AWS Access Key ID: <YOUR_KEY>
# AWS Secret Access Key: <YOUR_SECRET>
# Default region: ap-northeast-1
# Default output format: json
```

### 2. Bedrockアクセス申請

1. AWS Console → Bedrock
2. "Model access" → "Manage model access"
3. "Anthropic - Claude 3.5 Sonnet" を選択
4. "Request model access"

**注意**: 承認まで数時間～1営業日かかる場合があります。

### 3. Terraform初期化

```bash
cd infrastructure/aws/terraform
terraform init
```

### 4. Terraformデプロイ

```bash
# 変数設定
export TF_VAR_project_name="ic-test"
export TF_VAR_aws_region="ap-northeast-1"

# デプロイ実行
terraform plan -out=tfplan
terraform apply tfplan
```

### 5. Secrets Managerシークレット設定

```bash
# Bedrock APIアクセスは自動（IAMロール経由）
# 追加シークレット（必要に応じて）
aws secretsmanager create-secret \
  --name custom-api-key \
  --secret-string "<YOUR_API_KEY>" \
  --region ap-northeast-1
```

### 6. API Gateway API Key取得

```bash
API_KEY=$(aws apigateway get-api-keys \
  --include-values \
  --query "items[?name=='ic-test-api-key'].value" \
  --output text)

echo "API Key: $API_KEY"
```

### 7. デプロイ検証

```bash
export AWS_API_GATEWAY_ENDPOINT="https://<API_ID>.execute-api.ap-northeast-1.amazonaws.com/prod"
export AWS_API_KEY="$API_KEY"

python scripts/validate_deployment.py --platform aws
```

## 環境変数設定（クライアント用）

```bash
export AWS_API_GATEWAY_ENDPOINT="https://<API_ID>.execute-api.ap-northeast-1.amazonaws.com/prod"
export AWS_API_KEY="<API_KEY>"
export AWS_REGION="ap-northeast-1"
```

## トラブルシューティング

### Bedrockアクセス拒否エラー

```bash
# Lambda実行ロールにBedrock権限追加
aws iam attach-role-policy \
  --role-name ic-test-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess
```

### X-Rayトレースが表示されない

```bash
# Lambda関数でX-Ray有効化
aws lambda update-function-configuration \
  --function-name ic-test-function \
  --tracing-config Mode=Active
```

## 参考資料

- [Deployment Guide](../operations/DEPLOYMENT_GUIDE.md)
- [AWS Terraform Documentation](https://registry.terraform.io/providers/hashicorp/aws/)
