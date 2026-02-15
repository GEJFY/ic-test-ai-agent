# GitHub Actions CI/CD 設定ガイド

このドキュメントでは、GitHub Actionsを使用したCI/CDパイプラインの設定方法を説明します。

## ワークフロー一覧

| ワークフロー | ファイル | トリガー | 内容 |
|-------------|---------|---------|------|
| CI | `ci.yml` | Push/PR (main, develop) | テスト・Dockerビルド |
| Test | `test.yml` | Push/PR | Lint・テスト・セキュリティ監査 |
| Azure Deploy | `deploy-azure.yml` | Push (main) / 手動 | Azureへのデプロイ |
| AWS Deploy | `deploy-aws.yml` | Push (main) / 手動 | AWSへのデプロイ |
| GCP Deploy | `deploy-gcp.yml` | Push (main) / 手動 | GCPへのデプロイ |

### デプロイワークフローの自動トリガー条件

mainブランチへのpushのうち、以下のパスが変更された場合に自動実行されます：

- `Dockerfile`
- `src/**`
- `platforms/local/**`
- `infrastructure/{azure,aws,gcp}/**`（対象プラットフォームのみ）

手動実行（`workflow_dispatch`）も可能です。

## 初期設定

### 1. GitHub Secrets の設定

リポジトリの **Settings > Secrets and variables > Actions** で以下を設定します。

> **注意**: ACR名、Container App名、ECR URL、App Runner ARN、Artifact Registry URL等の
> リソース名はTerraform outputから自動取得されるため、Secretsへの個別設定は不要です。

#### Azure用

| Secret名 | 説明 | 取得方法 |
|----------|------|---------|
| `AZURE_CREDENTIALS` | サービスプリンシパルJSON | `az ad sp create-for-rbac --sdk-auth` |
| `AZURE_RESOURCE_GROUP` | リソースグループ名 | Azure Portal |

**サービスプリンシパルの作成:**
```powershell
az login
az ad sp create-for-rbac --name "github-actions-ic-test" --role contributor --scopes /subscriptions/<SUBSCRIPTION_ID> --sdk-auth
```

> ACR認証はManaged Identityを使用するため、`ACR_USERNAME`/`ACR_PASSWORD`は不要です。
> ワークフローは `az acr login` でManaged Identity経由のログインを行います。

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
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload",
        "ecr:CreateRepository",
        "ecr:DescribeRepositories"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "apprunner:CreateService",
        "apprunner:UpdateService",
        "apprunner:DescribeService",
        "apprunner:StartDeployment",
        "apprunner:ListServices"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "apigateway:*",
        "secretsmanager:*",
        "iam:PassRole",
        "iam:CreateRole",
        "iam:AttachRolePolicy",
        "s3:*"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "ap-northeast-1"
        }
      }
    }
  ]
}
```

#### GCP用

| Secret名 | 説明 | 取得方法 |
|----------|------|---------|
| `GCP_SERVICE_ACCOUNT_KEY` | サービスアカウントキーJSON | GCP Console > IAM > サービスアカウント |
| `GCP_PROJECT_ID` | プロジェクトID | GCP Console |

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

# key.json の内容をGCP_SERVICE_ACCOUNT_KEYにペースト
```

### 2. GitHub Variables の設定

デプロイワークフローではリソース名をTerraform outputから自動取得するため、
**GitHub Variablesの設定は不要**です。

ワークフロー内のハードコードされたデフォルト値：

| 設定 | ワークフロー | デフォルト値 |
|------|-------------|-------------|
| Python Version | 全て | `3.11` |
| Docker Image名 | 全て | `ic-test-ai-agent` |
| AWSリージョン | AWS | `ap-northeast-1` |
| GCPリージョン | GCP | `asia-northeast1` |

## 使用方法

### CIワークフロー（自動実行）

`main`または`develop`ブランチへのpush/PRで自動実行されます。

```
Push/PR → テスト → Dockerビルド → （mainのみ）レジストリにプッシュ
```

### デプロイワークフロー

#### 自動実行

mainブランチへのpushで対象パスが変更されると自動実行されます。

```
mainへのpush → テスト → セキュリティスキャン → Terraform → Dockerビルド＆プッシュ → コンテナ更新 → 検証
```

#### 手動実行

1. **Actions** タブを開く
2. 左側のワークフロー一覧から対象を選択（例: `Deploy to Azure`）
3. **Run workflow** をクリック
4. パラメータを入力:
   - `environment`: staging / production
5. **Run workflow** で実行

## Environments の設定（推奨）

本番環境へのデプロイには承認フローを設定することを推奨します。

1. **Settings > Environments** を開く
2. `staging` および `production` 環境を作成
3. `production` 環境に **Required reviewers** を有効化し、承認者を設定
4. **Deployment branches** で `main` のみに制限

## デプロイパイプラインの詳細

各プラットフォームのデプロイパイプラインは以下のフローで実行されます：

```
test → security → deploy (Terraform → Docker build/push → Container update → Validate)
```

### Azure (`deploy-azure.yml`)

1. **test**: pytest実行（e2e/integration除外）
2. **security**: `scripts/audit_security.py` 実行
3. **deploy**:
   - Azure Login（`AZURE_CREDENTIALS`）
   - Terraform init/plan/apply（`AZURE_RESOURCE_GROUP` を変数として渡す）
   - Terraform outputからACR名・Container App名を取得
   - ACRにDockerログイン → ビルド＆プッシュ（`sha`タグ + `latest`タグ）
   - Container Appのイメージを更新
   - `scripts/validate_deployment.py --platform azure` で検証

### AWS (`deploy-aws.yml`)

1. **test**: pytest実行
2. **security**: セキュリティスキャン
3. **deploy**:
   - AWS Credentials設定（`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`）
   - Terraform init/plan/apply
   - Terraform outputからECR URL・App Runner ARNを取得
   - ECRにDockerログイン → ビルド＆プッシュ
   - App Runnerのデプロイをトリガー
4. **validate**: `scripts/validate_deployment.py --platform aws` で検証

### GCP (`deploy-gcp.yml`)

1. **test**: pytest実行
2. **security**: セキュリティスキャン
3. **deploy**:
   - GCP認証（`GCP_SERVICE_ACCOUNT_KEY`）
   - Cloud SDK設定（`GCP_PROJECT_ID`）
   - Terraform init/plan/apply
   - Terraform outputからArtifact Registry URL・Cloud Run情報を取得
   - Artifact RegistryにDockerログイン → ビルド＆プッシュ
   - Cloud Runのイメージを更新
4. **validate**: `scripts/validate_deployment.py --platform gcp` で検証

## トラブルシューティング

### よくあるエラー

**Azure: "AADSTS700016: Application not found"**
- AZURE_CREDENTIALSのサービスプリンシパルが正しいか確認
- サブスクリプションIDが一致しているか確認

**AWS: "AccessDenied"**
- IAMユーザーの権限を確認（ECR、App Runner、API Gateway、Secrets Manager）
- リージョンが正しいか確認

**GCP: "Permission denied"**
- サービスアカウントの権限を確認（Cloud Run Admin、Artifact Registry Writer）
- 必要なAPIが有効化されているか確認

**Terraform: "state lock"**
- 他のデプロイが実行中でないか確認
- 必要に応じて `terraform force-unlock` を実行

### ログの確認

1. Actions タブで失敗したワークフローをクリック
2. 失敗したジョブをクリック
3. エラーが発生したステップを展開

## セキュリティ注意事項

- Secretsは暗号化されて保存されますが、ログに出力されないよう注意
- サービスアカウント/IAMユーザーには最小権限を付与
- 本番環境のSecretsは厳重に管理
- 定期的にキーをローテーション
- ACR認証はManaged Identity使用（admin資格情報は無効）

## 参考

- [デプロイメントガイド](../../docs/operations/DEPLOYMENT_GUIDE.md) - マニュアルデプロイ手順
- [Azure Setup](../../docs/setup/AZURE_SETUP.md) - Azure環境セットアップ
- [AWS Setup](../../docs/setup/AWS_SETUP.md) - AWS環境セットアップ
- [GCP Setup](../../docs/setup/GCP_SETUP.md) - GCP環境セットアップ
