# クイックスタートガイド

このガイドでは、最速でデプロイメントを実行する手順を説明します。

## 📋 前提条件

### 共通
- Python 3.11+
- Git

### Azure
- Azure CLI (`az`)
- Azure サブスクリプション

### AWS
- AWS CLI (`aws`)
- AWS アカウント
- Terraform

### GCP
- Google Cloud SDK (`gcloud`)
- GCP プロジェクト
- Terraform

---

## 🚀 クイックデプロイ（5ステップ）

### Step 1: リポジトリクローン

```bash
git clone https://github.com/GEJFY/ic-test-ai-agent.git
cd ic-test-ai-agent
```

### Step 2: 環境変数設定

#### Azure
```bash
cp .env.azure.template .env.azure
# .env.azure を編集して実際の値を設定
```

#### AWS
```bash
cp .env.aws.template .env.aws
# .env.aws を編集して実際の値を設定
```

#### GCP
```bash
cp .env.gcp.template .env.gcp
# .env.gcp を編集して実際の値を設定
```

### Step 3: CLIツール認証

#### Azure
```bash
az login
az account set --subscription "YOUR_SUBSCRIPTION_ID"
```

#### AWS
```bash
aws configure
# Access Key ID、Secret Access Key、リージョンを入力
```

#### GCP
```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

### Step 4: デプロイメント準備確認

```bash
# 準備状況を確認
python scripts/prepare_deployment.py --platform azure
python scripts/prepare_deployment.py --platform aws
python scripts/prepare_deployment.py --platform gcp
```

### Step 5: デプロイメント実行

#### DRY RUN（推奨: 初回実行時）
```bash
# 実際のリソースを作成せずにシミュレーション
python scripts/deploy.py --platform azure --dry-run
python scripts/deploy.py --platform aws --dry-run
python scripts/deploy.py --platform gcp --dry-run
```

#### 本番デプロイ
```bash
# Staging環境へデプロイ
python scripts/deploy.py --platform azure --environment staging
python scripts/deploy.py --platform aws --environment staging
python scripts/deploy.py --platform gcp --environment staging

# Production環境へデプロイ（注意: 本番環境）
python scripts/deploy.py --platform azure --environment production
```

#### 全プラットフォーム一括デプロイ
```bash
python scripts/deploy.py --platform all --environment staging
```

---

## ✅ デプロイメント検証

デプロイ完了後、以下のコマンドで検証します:

```bash
python scripts/validate_deployment.py --platform azure
python scripts/validate_deployment.py --platform aws
python scripts/validate_deployment.py --platform gcp
```

---

## 🔄 ロールバック

デプロイメントを元に戻す場合:

```bash
# DRY RUN
python scripts/rollback.py --platform azure --dry-run

# 実際のロールバック
python scripts/rollback.py --platform azure --environment staging
```

**⚠️ 警告**: ロールバックは全リソースを削除します。

---

## 📊 デプロイメント後の確認

### Azure

```bash
# リソースグループ確認
az group show --name ic-test-staging-rg

# Function App確認
az functionapp list --resource-group ic-test-staging-rg

# APIM確認
az apim show --name ic-test-staging-apim --resource-group ic-test-staging-rg
```

### AWS

```bash
# Lambda関数確認
aws lambda get-function --function-name ic-test-staging-evaluator

# API Gateway確認
aws apigatewayv2 get-apis
```

### GCP

```bash
# Cloud Functions確認
gcloud functions list

# Apigee確認
gcloud apigee organizations list
```

---

## 🔐 シークレット登録

### Azure Key Vault

```bash
az keyvault secret set \
  --vault-name ic-test-staging-kv \
  --name AZURE-FOUNDRY-API-KEY \
  --value "YOUR_API_KEY"
```

### AWS Secrets Manager

```bash
aws secretsmanager create-secret \
  --name ic-test/bedrock-api-key \
  --secret-string "YOUR_API_KEY"
```

### GCP Secret Manager

```bash
echo -n "YOUR_API_KEY" | gcloud secrets create vertexai-api-key --data-file=-
```

---

## 🧪 テスト実行

### ローカルテスト

```bash
# ユニットテスト
pytest tests/unit/ -v

# 統合テスト（モック使用）
pytest tests/integration/ -v
```

### E2Eテスト（デプロイ後）

```bash
# 環境変数設定後
pytest tests/e2e/ -v --e2e
```

---

## 📝 VBA/PowerShellクライアント設定

デプロイ完了後、クライアントを設定します:

### VBA (Excel)

1. `clients/vba/ExcelToJson.bas` を開く
2. API設定を編集:
   ```vba
   Const API_ENDPOINT As String = "https://ic-test-staging-apim.azure-api.net/api/evaluate"
   Const API_KEY As String = "YOUR_APIM_SUBSCRIPTION_KEY"
   ```
3. VBAマクロを実行

### PowerShell

1. `clients/powershell/CallCloudApi.ps1` を開く
2. API設定を編集:
   ```powershell
   $apiEndpoint = "https://ic-test-staging-apim.azure-api.net/api/evaluate"
   $apiKey = "YOUR_APIM_SUBSCRIPTION_KEY"
   ```
3. スクリプトを実行

詳細は [CLIENT_SETUP.md](docs/setup/CLIENT_SETUP.md) を参照してください。

---

## 🔍 トラブルシューティング

### 問題: Azure CLIがインストールされていない

**解決策**:
```bash
# Windows
winget install Microsoft.AzureCLI

# macOS
brew install azure-cli

# Linux
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

### 問題: Terraformがインストールされていない

**解決策**:
```bash
# Windows
winget install Hashicorp.Terraform

# macOS
brew install terraform

# Linux
sudo apt-get install terraform
```

### 問題: デプロイメントが失敗する

**解決策**:
1. 準備チェックを実行:
   ```bash
   python scripts/prepare_deployment.py --platform <platform>
   ```
2. 環境変数を確認:
   ```bash
   cat .env.<platform>
   ```
3. ログを確認:
   - Azure: Application Insights
   - AWS: CloudWatch Logs
   - GCP: Cloud Logging

詳細は [TROUBLESHOOTING.md](docs/operations/TROUBLESHOOTING.md) を参照してください。

---

## 📚 関連ドキュメント

| ドキュメント | 説明 |
|------------|------|
| [DEPLOYMENT_GUIDE.md](docs/operations/DEPLOYMENT_GUIDE.md) | 詳細なデプロイメント手順 |
| [MONITORING_RUNBOOK.md](docs/operations/MONITORING_RUNBOOK.md) | 監視・運用ガイド |
| [CLOUD_COST_ESTIMATION.md](docs/CLOUD_COST_ESTIMATION.md) | コスト見積もり |
| [SYSTEM_SPECIFICATION.md](SYSTEM_SPECIFICATION.md) | システム仕様書 |

---

## 💡 ベストプラクティス

1. **初回は必ずDRY RUNを実行**
   ```bash
   python scripts/deploy.py --platform azure --dry-run
   ```

2. **Staging環境で検証後、Productionへ**
   ```bash
   # Stagingで検証
   python scripts/deploy.py --platform azure --environment staging

   # 検証成功後、Productionへ
   python scripts/deploy.py --platform azure --environment production
   ```

3. **デプロイ前に必ず準備チェック実行**
   ```bash
   python scripts/prepare_deployment.py --platform azure
   ```

4. **デプロイ後は必ず検証実行**
   ```bash
   python scripts/validate_deployment.py --platform azure
   ```

5. **定期的にセキュリティ監査実行**
   ```bash
   python scripts/audit_security.py
   ```

---

## ⚡ ワンライナーコマンド

```bash
# 全プラットフォームDRY RUN
for platform in azure aws gcp; do python scripts/deploy.py --platform $platform --dry-run; done

# 全プラットフォームデプロイ（Staging）
python scripts/deploy.py --platform all --environment staging

# 全プラットフォーム検証
for platform in azure aws gcp; do python scripts/validate_deployment.py --platform $platform; done
```

---

## 🆘 サポート

問題が発生した場合:

1. [TROUBLESHOOTING.md](docs/operations/TROUBLESHOOTING.md) を確認
2. [GitHub Issues](https://github.com/GEJFY/ic-test-ai-agent/issues) で報告
3. [デプロイメントガイド](docs/operations/DEPLOYMENT_GUIDE.md) を参照
