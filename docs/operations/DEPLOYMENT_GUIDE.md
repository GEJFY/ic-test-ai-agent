# デプロイメントガイド

## 概要

このガイドでは、Azure/AWS/GCP環境への本システムのデプロイ手順を説明します。

## 前提条件

- 各クラウドプラットフォームのアカウントとサブスクリプション
- Azure CLI / AWS CLI / gcloud CLI のインストールと認証設定
- Terraform / Azure Bicep のインストール
- Python 3.11以上

## デプロイメント順序

すべてのプラットフォームで以下の順序でデプロイします：

1. **シークレット管理** (Key Vault / Secrets Manager / Secret Manager)
2. **API Gateway層** (APIM / API Gateway / Apigee)
3. **バックエンド** (Functions / Lambda / Cloud Functions)
4. **監視サービス** (Application Insights / CloudWatch/X-Ray / Cloud Logging/Trace)
5. **統合テスト実行**

---

## Azure デプロイメント

### 1. 環境変数設定

```powershell
$RESOURCE_GROUP = "ic-test-rg"
$LOCATION = "japaneast"
$PROJECT_NAME = "ic-test"
```

### 2. リソースグループ作成

```bash
az group create --name $RESOURCE_GROUP --location $LOCATION
```

### 3. Bicepデプロイ実行

```bash
cd infrastructure/azure/bicep
az deployment group create \
  --resource-group $RESOURCE_GROUP \
  --template-file main.bicep \
  --parameters parameters.json
```

### 4. シークレット設定

```bash
# Key Vaultにシークレット登録
az keyvault secret set --vault-name <KEY_VAULT_NAME> \
  --name "azure-foundry-api-key" --value "<YOUR_API_KEY>"
```

### 5. デプロイ検証

```bash
python scripts/validate_deployment.py --platform azure
```

---

## AWS デプロイメント

### 1. 環境変数設定

```bash
export AWS_REGION="ap-northeast-1"
export PROJECT_NAME="ic-test"
```

### 2. Terraform初期化

```bash
cd infrastructure/aws/terraform
terraform init
```

### 3. Terraformデプロイ

```bash
terraform plan -out=tfplan
terraform apply tfplan
```

### 4. シークレット設定

```bash
# Secrets Managerにシークレット登録
aws secretsmanager create-secret \
  --name bedrock-api-key \
  --secret-string "<YOUR_API_KEY>" \
  --region $AWS_REGION
```

### 5. デプロイ検証

```bash
python scripts/validate_deployment.py --platform aws
```

---

## GCP デプロイメント

### 1. 環境変数設定

```bash
export GCP_PROJECT="ic-test-project"
export GCP_REGION="asia-northeast1"
```

### 2. Terraform初期化

```bash
cd infrastructure/gcp/terraform
terraform init
```

### 3. Terraformデプロイ

```bash
terraform plan -out=tfplan
terraform apply tfplan
```

### 4. シークレット設定

```bash
# Secret Managerにシークレット登録
echo -n "<YOUR_API_KEY>" | gcloud secrets create vertex-ai-key \
  --data-file=- --project=$GCP_PROJECT
```

### 5. デプロイ検証

```bash
python scripts/validate_deployment.py --platform gcp
```

---

## デプロイ後の確認事項

### 1. ヘルスチェック

```bash
# Azure
curl -H "Ocp-Apim-Subscription-Key: <KEY>" \
  https://<APIM_ENDPOINT>/api/health

# AWS
curl -H "X-Api-Key: <KEY>" \
  https://<API_GATEWAY_ENDPOINT>/health

# GCP
curl -H "X-Api-Key: <KEY>" \
  https://<APIGEE_ENDPOINT>/health
```

### 2. 相関ID伝播確認

```bash
curl -H "X-Correlation-ID: test-123" \
     -H "<API_KEY_HEADER>: <KEY>" \
     <ENDPOINT>/health
```

### 3. E2Eテスト実行

```bash
pytest tests/e2e/ -v --e2e
```

---

## ロールバック手順

### Azure

```bash
az deployment group delete --resource-group $RESOURCE_GROUP --name <DEPLOYMENT_NAME>
```

### AWS

```bash
cd infrastructure/aws/terraform
terraform destroy
```

### GCP

```bash
cd infrastructure/gcp/terraform
terraform destroy
```

---

## トラブルシューティング

デプロイ失敗時は [TROUBLESHOOTING.md](TROUBLESHOOTING.md) を参照してください。

---

## 参考資料

- [Azure Setup Guide](../setup/AZURE_SETUP.md)
- [AWS Setup Guide](../setup/AWS_SETUP.md)
- [GCP Setup Guide](../setup/GCP_SETUP.md)
- [Monitoring Runbook](MONITORING_RUNBOOK.md)
