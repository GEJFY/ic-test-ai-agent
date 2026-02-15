# デプロイメントガイド

## 概要

このガイドでは、Azure/AWS/GCP環境への本システムのデプロイ手順を説明します。

## デプロイ方式の選択

本システムでは3つのデプロイ方式をサポートしています。

| 方式 | 推奨度 | 説明 | 適用場面 |
|------|--------|------|---------|
| **A. GitHub Actions CI/CD** | 推奨 | mainブランチへのpushで自動デプロイ | 継続的な開発・運用 |
| **B. マニュアルデプロイ** | - | CLI操作でDocker build → push → 更新 | 初回セットアップ、トラブルシュート |
| **C. デプロイスクリプト** | - | PowerShellスクリプトで一括実行 | ローカル環境からの手動デプロイ |

### 全体フロー

```text
1. Terraformでインフラ構築（ACR/ECR/Artifact Registry、Container Apps/App Runner/Cloud Run等）
2. Dockerイメージをビルド
3. コンテナレジストリにプッシュ
4. コンテナサービスのイメージを更新
5. デプロイ検証
```

> Terraformはインフラ（レジストリ、コンテナサービス、API Gateway等）を構築しますが、
> **アプリケーションのDockerイメージのビルド・デプロイは別途必要**です。

## 前提条件

- 各クラウドプラットフォームのアカウントとサブスクリプション
- Azure CLI / AWS CLI / gcloud CLI のインストールと認証設定
- Terraform >= 1.5.0 のインストール
- Docker Desktop のインストール（マニュアルデプロイの場合）
- Python 3.11以上

---

## 方式A: GitHub Actions CI/CD（推奨）

### 概要

`.github/workflows/deploy-{azure,aws,gcp}.yml` が用意されており、以下のパイプラインが自動実行されます：

```text
mainブランチへのpush → テスト → セキュリティスキャン → Terraformデプロイ → Dockerビルド＆プッシュ → コンテナ更新 → 検証
```

**トリガー条件**: mainブランチへのpush（Dockerfile, src/**, platforms/local/**, infrastructure/対象クラウド/** の変更時）+ 手動実行（workflow_dispatch）

### セットアップ手順

1. GitHub Secretsの設定（[.github/workflows/README.md](../../.github/workflows/README.md) を参照）
2. GitHub Environments の設定（`staging`, `production`）
3. mainブランチへのpushまたはActionsタブからの手動実行

### プラットフォーム別の必要なSecrets

**Azure**:

| Secret名 | 説明 | 取得方法 |
|----------|------|---------|
| `AZURE_CREDENTIALS` | サービスプリンシパルJSON | `az ad sp create-for-rbac --sdk-auth` |
| `AZURE_RESOURCE_GROUP` | リソースグループ名 | Azure Portal |

> ACR名・Container App名はTerraform outputから自動取得されるため、個別設定は不要です。

**AWS**:

| Secret名 | 説明 | 取得方法 |
|----------|------|---------|
| `AWS_ACCESS_KEY_ID` | IAMアクセスキーID | IAM Console |
| `AWS_SECRET_ACCESS_KEY` | IAMシークレットキー | IAM Console |

> ECR URL・App Runner ARNはTerraform outputから自動取得されます。

**GCP**:

| Secret名 | 説明 | 取得方法 |
|----------|------|---------|
| `GCP_SERVICE_ACCOUNT_KEY` | サービスアカウントキーJSON | GCP Console |
| `GCP_PROJECT_ID` | プロジェクトID | GCP Console |

> Artifact Registry URL・Cloud Runサービス名はTerraform outputから自動取得されます。

### 手動実行方法

1. GitHubリポジトリの **Actions** タブを開く
2. 左側から `Deploy to Azure`（または AWS/GCP）を選択
3. **Run workflow** をクリック
4. `environment` を選択（staging / production）
5. **Run workflow** で実行

---

## Azure デプロイメント

### ステップ1: インフラ構築（Terraform）

```powershell
# 環境変数設定
$RESOURCE_GROUP = "rg-ic-test-evaluation"

# リソースグループ作成（初回のみ）
az group create --name $RESOURCE_GROUP --location japaneast

# Terraformデプロイ
cd infrastructure/azure/terraform
terraform init
terraform plan -out=tfplan -var="resource_group_name=$RESOURCE_GROUP"
terraform apply -auto-approve tfplan
```

シークレット（Azure AI Foundry、Document Intelligence、Storage Account）はTerraformが自動設定します。

### ステップ2: Terraform出力の確認

```powershell
# リソース名を取得（ステップ3以降で使用）
terraform output acr_name              # ACR名
terraform output acr_login_server      # ACRログインサーバー
terraform output container_app_name    # Container App名
terraform output container_app_url     # Container App URL
terraform output apim_gateway_url      # APIM Gateway URL
```

### ステップ3: アプリケーションデプロイ

#### 方式B: マニュアルデプロイ

```powershell
# プロジェクトルートに戻る
cd ../../..

# ACR名を変数に設定（terraform outputの値を使用）
$ACR_NAME = "<terraform output acr_name の値>"
$CA_NAME = "<terraform output container_app_name の値>"

# ACRにログイン
az acr login --name $ACR_NAME

# Dockerイメージをビルド＆プッシュ
docker build -t "$ACR_NAME.azurecr.io/ic-test-ai-agent:latest" .
docker push "$ACR_NAME.azurecr.io/ic-test-ai-agent:latest"

# Container Appのイメージを更新
az containerapp update `
    --name $CA_NAME `
    --resource-group $RESOURCE_GROUP `
    --image "$ACR_NAME.azurecr.io/ic-test-ai-agent:latest"
```

#### 方式C: デプロイスクリプト

```powershell
.\platforms\azure\deploy.ps1 `
    -ContainerAppName $CA_NAME `
    -ResourceGroup $RESOURCE_GROUP `
    -AcrName $ACR_NAME
```

### ステップ4: デプロイ検証

```bash
python scripts/validate_deployment.py --platform azure
```

---

## AWS デプロイメント

### ステップ1: インフラ構築（Terraform）

```bash
export AWS_REGION="ap-northeast-1"

cd infrastructure/aws/terraform
terraform init
terraform plan -out=tfplan
terraform apply -auto-approve tfplan
```

### ステップ2: Terraform出力の確認

```bash
terraform output ecr_repository_url      # ECRリポジトリURL
terraform output app_runner_service_arn   # App Runner ARN
terraform output api_gateway_endpoint     # API Gateway エンドポイント
```

### ステップ3: シークレット設定

```bash
aws secretsmanager create-secret \
  --name ic-test-ai-prod-bedrock-api-key \
  --secret-string "<YOUR_API_KEY>" \
  --region $AWS_REGION
```

### ステップ4: アプリケーションデプロイ

#### 方式B: マニュアルデプロイ

```bash
# プロジェクトルートに戻る
cd ../../..

# ECR URL（terraform outputの値を使用）
ECR_REPO="<terraform output ecr_repository_url の値>"

# ECRにログイン
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $ECR_REPO

# Dockerイメージをビルド＆プッシュ
docker build -t ${ECR_REPO}:latest .
docker push ${ECR_REPO}:latest

# App Runnerのデプロイをトリガー
APP_RUNNER_ARN="<terraform output app_runner_service_arn の値>"
aws apprunner start-deployment --service-arn ${APP_RUNNER_ARN}
```

#### 方式C: デプロイスクリプト

```powershell
.\platforms\aws\deploy.ps1 `
    -EcrRepoUrl $ECR_REPO `
    -Region "ap-northeast-1" `
    -ServiceArn $APP_RUNNER_ARN
```

### ステップ5: デプロイ検証

```bash
python scripts/validate_deployment.py --platform aws
```

---

## GCP デプロイメント

### ステップ1: インフラ構築（Terraform）

```bash
export GCP_PROJECT="${GCP_PROJECT_ID}"
export GCP_REGION="asia-northeast1"

cd infrastructure/gcp/terraform
terraform init
terraform plan -out=tfplan
terraform apply -auto-approve tfplan
```

### ステップ2: Terraform出力の確認

```bash
terraform output artifact_registry_url    # Artifact Registry URL
terraform output cloud_run_service_name   # Cloud Runサービス名
terraform output cloud_run_service_url    # Cloud Run URL
```

### ステップ3: シークレット設定

```bash
echo -n "<YOUR_API_KEY>" | gcloud secrets create vertex-ai-key \
  --data-file=- --project=$GCP_PROJECT
```

### ステップ4: アプリケーションデプロイ

#### 方式B: マニュアルデプロイ

```bash
# プロジェクトルートに戻る
cd ../../..

# Artifact Registry URL（terraform outputの値を使用）
AR_REPO="<terraform output artifact_registry_url の値>"

# Artifact Registryにログイン
gcloud auth configure-docker ${GCP_REGION}-docker.pkg.dev

# Dockerイメージをビルド＆プッシュ
docker build -t ${AR_REPO}/ic-test-ai-agent:latest .
docker push ${AR_REPO}/ic-test-ai-agent:latest

# Cloud Runを更新
SERVICE_NAME="<terraform output cloud_run_service_name の値>"
gcloud run deploy ${SERVICE_NAME} \
  --image ${AR_REPO}/ic-test-ai-agent:latest \
  --region ${GCP_REGION} \
  --platform managed
```

#### 方式C: デプロイスクリプト

```powershell
.\platforms\gcp\deploy.ps1 `
    -ProjectId $GCP_PROJECT `
    -Region "asia-northeast1"
```

### ステップ5: デプロイ検証

```bash
python scripts/validate_deployment.py --platform gcp
```

---

## デプロイ後の確認事項

### 1. ヘルスチェック

```bash
# Azure（APIM経由）
curl -H "Ocp-Apim-Subscription-Key: <KEY>" \
  https://<APIM名>.azure-api.net/api/health

# Azure（Container Apps直接）
curl https://<CA名>.azurecontainerapps.io/health

# AWS
curl -H "x-api-key: <KEY>" \
  https://<API_GATEWAY_ENDPOINT>/health

# GCP
curl https://<CLOUD_RUN_URL>/health
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

### アプリケーションのロールバック（前のイメージに戻す）

```bash
# Azure
az containerapp update --name <CA_NAME> --resource-group <RG> \
  --image <ACR>.azurecr.io/ic-test-ai-agent:<PREVIOUS_TAG>

# AWS
# ECRの前のタグで再デプロイ
aws apprunner start-deployment --service-arn <ARN>

# GCP
gcloud run deploy <SERVICE> \
  --image <AR_REPO>/ic-test-ai-agent:<PREVIOUS_TAG> \
  --region <REGION> --platform managed
```

### インフラの破棄

```bash
# Azure
cd infrastructure/azure/terraform && terraform destroy

# AWS
cd infrastructure/aws/terraform && terraform destroy

# GCP
cd infrastructure/gcp/terraform && terraform destroy
```

---

## トラブルシューティング

デプロイ失敗時は [TROUBLESHOOTING.md](TROUBLESHOOTING.md) を参照してください。

---

## 参考資料

- [GitHub Actions CI/CD 設定ガイド](../../.github/workflows/README.md) - Secrets/Variables設定
- [Azure Setup Guide](../setup/AZURE_SETUP.md) - Azure環境の詳細セットアップ
- [AWS Setup Guide](../setup/AWS_SETUP.md) - AWS環境の詳細セットアップ
- [GCP Setup Guide](../setup/GCP_SETUP.md) - GCP環境の詳細セットアップ
- [Monitoring Runbook](MONITORING_RUNBOOK.md) - 監視・アラート対応
