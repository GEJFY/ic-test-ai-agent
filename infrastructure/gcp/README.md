# GCP インフラストラクチャ - デプロイガイド

## 概要

内部統制テスト評価AIシステムのGCPインフラストラクチャをTerraformで管理します。

### デプロイされるリソース

| リソース | 用途 | 月額コスト（想定） |
|---------|------|------------------|
| **Cloud Run** | バックエンドAPI（Dockerコンテナ） | ~$1-3 |
| **Artifact Registry** | Dockerイメージ管理 | ~$1.00 |
| **Apigee** (オプション) | API Gateway層、認証、レート制限 | $0/$4.50（評価版/本番） |
| **Secret Manager** | シークレット管理 | ~$3.20 |
| **Cloud Logging/Trace** | 監視、ログ、トレース | ~$1.50 |
| **合計** | | **~$6.70/月（Apigee無効時）<br>~$11.20/月（Apigee有効時）** |

**注意**: Apigeeは高コストです。評価版期間後は月額課金されます。`enable_apigee = false` で無効化できます。

## 前提条件

### 必要なツール

```bash
# Terraform
terraform --version  # 1.5.0以上

# gcloud CLI
gcloud --version  # 450.0.0以上

# 認証
gcloud auth application-default login
```

### GCPプロジェクト設定

```bash
# プロジェクトID設定
export PROJECT_ID="your-gcp-project-id"

# プロジェクト作成（既存の場合はスキップ）
gcloud projects create $PROJECT_ID --name="IC Test AI"

# プロジェクト選択
gcloud config set project $PROJECT_ID

# 課金アカウント有効化
gcloud billing projects link $PROJECT_ID --billing-account=<BILLING_ACCOUNT_ID>

# 必要なAPIを有効化
gcloud services enable run.googleapis.com
gcloud services enable artifactregistry.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable aiplatform.googleapis.com
gcloud services enable documentai.googleapis.com
gcloud services enable logging.googleapis.com
gcloud services enable monitoring.googleapis.com
gcloud services enable cloudtrace.googleapis.com
gcloud services enable storage.googleapis.com

# Apigee使用時のみ
# gcloud services enable apigee.googleapis.com
```

## デプロイ手順

### ステップ1: terraform.tfvars作成

`terraform/terraform.tfvars` ファイルを作成し、環境に合わせて値を設定します。

```hcl
# terraform/terraform.tfvars
project_id   = "your-gcp-project-id"
project_name = "ic-test-ai"
environment  = "prod"
region       = "asia-northeast1"

# Apigee設定（高コスト注意）
enable_apigee = false  # 評価版期間外は false 推奨

# シークレット（SA認証のため通常は不使用、フォールバック用に保持）
vertex_ai_api_key    = "SA_AUTHENTICATION"    # Cloud RunはSA認証でVertex AIにアクセス  # pragma: allowlist secret
document_ai_api_key  = "SA_AUTHENTICATION"    # Cloud RunはSA認証でDocument AIにアクセス  # pragma: allowlist secret
openai_api_key       = ""  # フォールバック用（オプション）

# コスト最適化設定
log_retention_days       = 30
enable_cloud_trace       = true
enable_monitoring_alerts = true
budget_amount            = 100
```

### ステップ2: Terraform初期化

```bash
cd infrastructure/gcp/terraform

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
- `cloud_run_endpoint`: VBA/PowerShellで使用するエンドポイント
- `artifact_registry_url`: Artifact Registry URL
- `secret_manager_vertex_ai_key_id`: Vertex AI API Key Secret ID

### ステップ5: Secret Managerにシークレットを設定

**重要：デプロイ時はダミー値が設定されます。以下のコマンドで実際のAPI Keyを設定してください。**

```bash
# Vertex AI API Key設定
gcloud secrets versions add ic-test-ai-prod-vertex-ai-api-key \
  --data-file=- <<< "<実際のAPIキー>"

# Document AI API Key設定
gcloud secrets versions add ic-test-ai-prod-document-ai-api-key \
  --data-file=- <<< "<実際のAPIキー>"

# OpenAI API Key設定（オプション）
gcloud secrets versions add ic-test-ai-prod-openai-api-key \
  --data-file=- <<< "<実際のAPIキー>"
```

### ステップ6: Dockerイメージをビルド・プッシュしてデプロイ

```bash
# Artifact Registry URLを取得
AR_URL=$(cd infrastructure/gcp/terraform && terraform output -raw artifact_registry_url)
CLOUD_RUN_SERVICE=$(cd infrastructure/gcp/terraform && terraform output -raw cloud_run_service_name)

# Artifact Registryに認証
gcloud auth configure-docker asia-northeast1-docker.pkg.dev

# Dockerイメージをビルド（プロジェクトルートで実行）
docker build -t $AR_URL/ic-test-ai:latest -f platforms/local/Dockerfile .

# Artifact Registryにプッシュ
docker push $AR_URL/ic-test-ai:latest

# Cloud Runサービスを更新
gcloud run deploy $CLOUD_RUN_SERVICE \
  --image=$AR_URL/ic-test-ai:latest \
  --region=asia-northeast1
```

### ステップ7: VBA/PowerShellのエンドポイント変更

**CallCloudApi.ps1 (PowerShell):**

```powershell
# Cloud RunエンドポイントURL
$ApiUrl = (gcloud run services describe ic-test-ai-prod --region=asia-northeast1 --format="value(status.url)")/evaluate

# ヘッダー設定（Apigee無効時はAPI Key不要）
$headers = @{
    "Content-Type" = "application/json; charset=utf-8"
    "X-Correlation-ID" = $CorrelationId
}

# Apigee有効時は以下を追加
# "X-Api-Key" = "<Apigee API Key>"
```

## デプロイ後の確認

### 1. ヘルスチェック

```bash
# Cloud RunエンドポイントURL取得
FUNCTION_URL=$(gcloud run services describe ic-test-ai-prod \
  --region=asia-northeast1 \
  --gen2 \
  --format="value(serviceConfig.uri)")

# ヘルスチェック
curl -X GET "$FUNCTION_URL/health"
```

### 2. 相関IDフロー確認

```bash
# テストリクエスト送信
CORRELATION_ID=$(uuidgen)
curl -X POST \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: $CORRELATION_ID" \
  -d '{"items":[{"ID":"001","controlObjective":"test","testProcedure":"test","acceptanceCriteria":"test"}]}' \
  "$FUNCTION_URL/evaluate"

# Cloud Loggingでログ確認
gcloud logging read "resource.type=cloud_run_revision \
  resource.labels.service_name=ic-test-ai-prod \
  jsonPayload.correlation_id=$CORRELATION_ID" \
  --limit 50 \
  --format json
```

### 3. Cloud Traceで依存関係確認

```bash
# Cloud Trace URL
echo "https://console.cloud.google.com/traces/list?project=$PROJECT_ID"
```

以下が可視化されていることを確認：
- VBA/PowerShell → Cloud Run → Vertex AI API
- 相関IDですべてのリクエストが追跡可能

## Apigee設定（オプション）

### Apigee組織の作成

```bash
# Apigee組織をプロビジョニング（初回のみ、30分程度かかる）
gcloud apigee organizations provision \
  --project=$PROJECT_ID \
  --authorized-network=default \
  --runtime-location=asia-northeast1

# terraform.tfvars でenable_apigee = true に設定
# terraform apply を再実行
```

### Apigee APIプロキシの手動作成

1. Apigee Console: https://apigee.google.com/organizations/$PROJECT_ID
2. "API Proxies" → "Create New" → "Reverse Proxy"
3. ターゲットURL: Cloud Run URI
4. ポリシー追加:
   - VerifyAPIKey（API Key検証）
   - AssignMessage（X-Correlation-ID設定）
   - Quota（レート制限: 100 req/min）
   - MessageLogging（Cloud Logging）

## トラブルシューティング

### デプロイエラー: "API not enabled"

必要なAPIが有効化されていません：

```bash
gcloud services enable run.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  aiplatform.googleapis.com \
  documentai.googleapis.com
```

### Cloud Run: Secret Managerアクセスエラー

サービスアカウント権限確認：

```bash
# サービスアカウントのIAMポリシー確認
gcloud projects get-iam-policy $PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:ic-test-ai-prod-func-sa@$PROJECT_ID.iam.gserviceaccount.com"
```

### Cloud Logging: ログが表示されない

ログ伝播に最大5分かかります。しばらく待ってから再確認してください。

## リソース削除

```bash
# 全リソース削除
terraform destroy

# Apigee組織削除（手動）
# gcloud apigee organizations delete --organization=$PROJECT_ID
```

## Terraform State管理（推奨）

### Cloud Storageバックエンド設定

```bash
# 1. Cloud Storageバケット作成（State保存用）
gcloud storage buckets create gs://ic-test-ai-terraform-state \
  --project=$PROJECT_ID \
  --location=asia-northeast1 \
  --uniform-bucket-level-access

# バージョニング有効化
gcloud storage buckets update gs://ic-test-ai-terraform-state \
  --versioning

# 2. backend.tf のコメントを外す
# 3. 再初期化
terraform init -reconfigure
```

## コスト最適化

### 1. Cloud Traceサンプリング調整

Cloud Run環境変数で調整：

```bash
gcloud run services update ic-test-ai-prod-api \
  --region=asia-northeast1 \
  --update-env-vars CLOUD_TRACE_SAMPLE_RATE=0.1  # 10%サンプリング
```

### 2. ログ保持期間短縮

`variables.tf` の `log_retention_days` を調整：

```hcl
log_retention_days = 7  # 初期30日 → 7日に短縮
```

### 3. Cloud Run最大インスタンス数制限

`variables.tf` の `container_max_instances` を調整：

```hcl
container_max_instances = 5  # 初期10 → 5に制限
```

## セキュリティ強化（本番環境推奨）

### 1. Cloud Runへのアクセス制限

特定サービスアカウントのみ許可：

```bash
gcloud run services remove-iam-policy-binding ic-test-ai-prod-api \
  --region=asia-northeast1 \
  --member="allUsers" \
  --role="roles/run.invoker"

gcloud run services add-iam-policy-binding ic-test-ai-prod-api \
  --region=asia-northeast1 \
  --member="serviceAccount:apigee-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

### 2. Secret Manager自動ローテーション

将来対応：Cloud Schedulerでシークレット自動ローテーション実装

### 3. VPC統合

Cloud RunをVPC内に配置（VPCコネクタ経由）

## 参考リンク

- [Cloud Run Terraform](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_run_v2_service)
- [Secret Manager Terraform](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/secret_manager_secret)
- [Apigee ドキュメント](https://cloud.google.com/apigee/docs)
- [Cloud Trace ドキュメント](https://cloud.google.com/trace/docs)
