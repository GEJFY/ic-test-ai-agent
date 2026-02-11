# GCP環境セットアップガイド

## 前提条件

- GCPプロジェクト
- gcloud CLI インストール済み
- Terraform インストール済み
- 権限: Project Editor以上

## セットアップ手順

### 1. gcloud CLI設定

```bash
gcloud init
gcloud auth application-default login
gcloud config set project <PROJECT_ID>
```

### 2. 必要なAPIの有効化

```bash
# Cloud Functions API
gcloud services enable cloudfunctions.googleapis.com

# Cloud Build API
gcloud services enable cloudbuild.googleapis.com

# Vertex AI API
gcloud services enable aiplatform.googleapis.com

# Document AI API
gcloud services enable documentai.googleapis.com

# Apigee API
gcloud services enable apigee.googleapis.com

# Secret Manager API
gcloud services enable secretmanager.googleapis.com

# Cloud Logging API
gcloud services enable logging.googleapis.com

# Cloud Trace API
gcloud services enable cloudtrace.googleapis.com
```

### 3. Terraform初期化

```bash
cd infrastructure/gcp/terraform
terraform init
```

### 4. Terraformデプロイ

```bash
# 変数設定
export TF_VAR_project_id="<PROJECT_ID>"
export TF_VAR_region="asia-northeast1"

# デプロイ実行
terraform plan -out=tfplan
terraform apply tfplan
```

### 5. Secret Managerシークレット設定

```bash
# Vertex AI APIキーは自動（サービスアカウント経由）
# 追加シークレット（必要に応じて）
echo -n "<YOUR_API_KEY>" | gcloud secrets create custom-api-key \
  --data-file=- \
  --replication-policy="automatic"
```

### 6. Apigee設定（評価版または本番）

**評価版**:
```bash
# Apigee評価版は無料
# GCP Console → Apigee → "Start evaluation"
```

**本番環境**:
```bash
# Apigee組織作成
gcloud apigee organizations create \
  --project=<PROJECT_ID> \
  --analytics-region=asia-northeast1 \
  --runtime-type=CLOUD
```

### 7. API Key取得

```bash
# Apigee APIプロダクトとアプリ作成後
# GCP Console → Apigee → Publish → Apps → <APP_NAME>
# Consumer Key/Secretを確認
```

### 8. デプロイ検証

```bash
export GCP_APIGEE_ENDPOINT="https://<APIGEE_ENDPOINT>"
export GCP_API_KEY="<API_KEY>"
export GCP_PROJECT="<PROJECT_ID>"

python scripts/validate_deployment.py --platform gcp
```

## 環境変数設定（クライアント用）

```bash
export GCP_APIGEE_ENDPOINT="https://<APIGEE_ENDPOINT>"
export GCP_API_KEY="<API_KEY>"
export GCP_PROJECT="<PROJECT_ID>"
```

## トラブルシューティング

### Vertex AIアクセス拒否エラー

```bash
# Cloud Functionsサービスアカウントに権限追加
gcloud projects add-iam-policy-binding <PROJECT_ID> \
  --member="serviceAccount:<PROJECT_ID>@appspot.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

### Cloud Loggingにログが表示されない

```bash
# Logging権限確認
gcloud projects get-iam-policy <PROJECT_ID> \
  --flatten="bindings[].members" \
  --filter="bindings.role:roles/logging.logWriter"
```

## コスト最適化

GCPは3つのプラットフォームで最もコスト効率的です：

- **月額約¥1,300** (監視コスト¥200含む)
- **無料枠活用**: Cloud Logging 50GiB/月、Cloud Trace 2.5M spans/月
- **Apigee評価版**: 開発環境では無料

## 参考資料

- [Deployment Guide](../operations/DEPLOYMENT_GUIDE.md)
- [GCP Terraform Documentation](https://registry.terraform.io/providers/hashicorp/google/)
- [Vertex AI Pricing](https://cloud.google.com/vertex-ai/pricing)
