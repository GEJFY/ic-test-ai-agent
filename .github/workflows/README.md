# GitHub Actions CI/CD 設定ガイド

このドキュメントでは、GitHub Actionsを使用したCI/CDパイプラインの設定方法を説明します。

## ワークフロー一覧

| ワークフロー | ファイル | トリガー | 内容 |
|-------------|---------|---------|------|
| CI | `ci.yml` | Push/PR (main, develop) | テスト・Dockerビルド |
| Azure Deploy | `deploy-azure.yml` | 手動 | Azureへのデプロイ |
| AWS Deploy | `deploy-aws.yml` | 手動 | AWSへのデプロイ |
| GCP Deploy | `deploy-gcp.yml` | 手動 | GCPへのデプロイ |

## 初期設定

### 1. GitHub Secrets の設定

リポジトリの **Settings > Secrets and variables > Actions** で以下を設定します。

#### Azure用

| Secret名 | 説明 | 取得方法 |
|----------|------|---------|
| `AZURE_CREDENTIALS` | サービスプリンシパルJSON | `az ad sp create-for-rbac --sdk-auth` |
| `AZURE_SUBSCRIPTION_ID` | サブスクリプションID | Azure Portal |
| `ACR_USERNAME` | ACRユーザー名 | ACR > アクセスキー |
| `ACR_PASSWORD` | ACRパスワード | ACR > アクセスキー |

**サービスプリンシパルの作成:**
```powershell
az login
az ad sp create-for-rbac --name "github-actions-ic-test" --role contributor --scopes /subscriptions/<SUBSCRIPTION_ID> --sdk-auth
```

#### AWS用

| Secret名 | 説明 | 取得方法 |
|----------|------|---------|
| `AWS_ACCESS_KEY_ID` | アクセスキーID | IAM > ユーザー > セキュリティ認証情報 |
| `AWS_SECRET_ACCESS_KEY` | シークレットアクセスキー | IAM > ユーザー > セキュリティ認証情報 |

**IAMポリシー例:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:UpdateFunctionCode",
        "lambda:GetFunction",
        "lambda:InvokeFunction",
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload"
      ],
      "Resource": "*"
    }
  ]
}
```

#### GCP用

| Secret名 | 説明 | 取得方法 |
|----------|------|---------|
| `GCP_SA_KEY` | サービスアカウントキーJSON | GCP Console > IAM > サービスアカウント |

**サービスアカウントの作成:**
```bash
# サービスアカウント作成
gcloud iam service-accounts create github-actions \
  --display-name="GitHub Actions"

# 必要な権限を付与
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:github-actions@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:github-actions@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/artifactregistry.writer"

# キーファイル作成
gcloud iam service-accounts keys create key.json \
  --iam-account=github-actions@PROJECT_ID.iam.gserviceaccount.com

# key.json の内容をGCP_SA_KEYにペースト
```

### 2. GitHub Variables の設定

リポジトリの **Settings > Secrets and variables > Actions > Variables** で以下を設定します。

#### Azure用

| Variable名 | 説明 | 例 |
|------------|------|-----|
| `ACR_REGISTRY` | ACR URL | `myregistry.azurecr.io` |
| `AZURE_RESOURCE_GROUP` | リソースグループ | `rg-ic-test-prod` |
| `AZURE_ENDPOINT_URL` | APIエンドポイント | `https://ca-ic-test-prod.japaneast.azurecontainerapps.io` |

#### AWS用

| Variable名 | 説明 | 例 |
|------------|------|-----|
| `AWS_REGION` | リージョン | `ap-northeast-1` |
| `AWS_ECR_REGISTRY` | ECR URL | `123456789.dkr.ecr.ap-northeast-1.amazonaws.com` |
| `AWS_APP_RUNNER_SERVICE` | App Runnerサービス名 | `ic-test-prod` |

#### GCP用

| Variable名 | 説明 | 例 |
|------------|------|-----|
| `GCP_PROJECT_ID` | プロジェクトID | `my-project-id` |
| `GCP_REGION` | リージョン | `asia-northeast1` |
| `GCP_ARTIFACT_REGISTRY` | Artifact Registry | `asia-northeast1-docker.pkg.dev/my-project/ic-test` |
| `GCP_CLOUD_RUN_SERVICE` | Cloud Runサービス名 | `ic-test-prod` |

## 使用方法

### CIワークフロー（自動実行）

`main`または`develop`ブランチへのpush/PRで自動実行されます。

```
Push/PR → テスト → Dockerビルド → （mainのみ）レジストリにプッシュ
```

### デプロイワークフロー（手動実行）

1. **Actions** タブを開く
2. 左側のワークフロー一覧から対象を選択（例: `Deploy to Azure`）
3. **Run workflow** をクリック
4. パラメータを入力:
   - `environment`: dev / staging / prod
   - `client`: クライアント名（terraform/clients/下のディレクトリ名）
   - `deploy_infra`: インフラ（Terraform）をデプロイするか
   - `deploy_app`: アプリケーションをデプロイするか
5. **Run workflow** で実行

## Environments の設定（推奨）

本番環境へのデプロイには承認フローを設定することを推奨します。

1. **Settings > Environments** を開く
2. `prod` 環境を作成
3. **Required reviewers** を有効化し、承認者を設定
4. **Deployment branches** で `main` のみに制限

## トラブルシューティング

### よくあるエラー

**Azure: "AADSTS700016: Application not found"**
- AZURE_CREDENTIALSのサービスプリンシパルが正しいか確認
- サブスクリプションIDが一致しているか確認

**AWS: "AccessDenied"**
- IAMユーザーの権限を確認
- リージョンが正しいか確認

**GCP: "Permission denied"**
- サービスアカウントの権限を確認
- 必要なAPIが有効化されているか確認

### ログの確認

1. Actions タブで失敗したワークフローをクリック
2. 失敗したジョブをクリック
3. エラーが発生したステップを展開

## セキュリティ注意事項

- Secretsは暗号化されて保存されますが、ログに出力されないよう注意
- サービスアカウント/IAMユーザーには最小権限を付与
- 本番環境のSecretsは厳重に管理
- 定期的にキーをローテーション
