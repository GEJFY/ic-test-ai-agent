# Terraform - マルチクライアント・マルチクラウドデプロイ

内部統制テスト評価AIシステムのインフラストラクチャをコードで管理します。

## ディレクトリ構造

```
terraform/
├── README.md              # このファイル
├── modules/               # 再利用可能なモジュール
│   ├── azure/             # Azure Functions + Storage
│   ├── aws/               # Lambda + DynamoDB + SQS
│   └── gcp/               # Cloud Run + Firestore + Cloud Tasks
└── clients/               # クライアント別設定
    ├── _template/         # 新規クライアント用テンプレート
    ├── client-a/          # クライアントAの設定
    └── client-b/          # クライアントBの設定
```

## クイックスタート

### 1. 新規クライアント追加

```powershell
# テンプレートをコピー
Copy-Item -Path terraform/clients/_template -Destination terraform/clients/new-client -Recurse

# 設定ファイルを作成
cd terraform/clients/new-client
Copy-Item terraform.tfvars.example terraform.tfvars

# terraform.tfvars を編集
notepad terraform.tfvars
```

### 2. インフラ構築

```powershell
# 初期化
terraform init

# プラン確認
terraform plan

# 適用
terraform apply
```

### 3. アプリケーションデプロイ

インフラ構築後、アプリケーションコードをデプロイします。

**Azure:**
```powershell
cd platforms/azure
.\deploy.ps1 -FunctionAppName "func-ic-newclient-prod" -ResourceGroup "rg-ic-newclient-prod"
```

**AWS:**
```powershell
cd platforms/aws
.\deploy.ps1 -FunctionName "ic-newclient-prod-evaluate"
```

**GCP:**
```powershell
# Dockerイメージをビルド・プッシュ
docker build -t asia-northeast1-docker.pkg.dev/PROJECT/ic-test/app:v1.0.0 .
docker push asia-northeast1-docker.pkg.dev/PROJECT/ic-test/app:v1.0.0

# Cloud Runを更新
gcloud run services update ic-newclient-prod --image=asia-northeast1-docker.pkg.dev/PROJECT/ic-test/app:v1.0.0
```

## クラウド別設定例

### Azure

```hcl
# terraform.tfvars
client_name    = "company-a"
environment    = "prod"
cloud_provider = "azure"

azure_subscription_id = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
azure_location        = "japaneast"

azure_llm_config = {
  endpoint    = "https://your-project.japaneast.models.ai.azure.com"
  api_key     = "your-api-key"
  model       = "gpt-4o"
}
```

### AWS

```hcl
# terraform.tfvars
client_name    = "company-b"
environment    = "prod"
cloud_provider = "aws"

aws_region = "ap-northeast-1"

aws_llm_config = {
  model_id = "jp.anthropic.claude-sonnet-4-5-20250929-v1:0"
}
```

### GCP

```hcl
# terraform.tfvars
client_name    = "company-c"
environment    = "prod"
cloud_provider = "gcp"

gcp_project_id = "your-project-id"
gcp_region     = "asia-northeast1"

gcp_llm_config = {
  model = "gemini-2.5-flash"
}

gcp_container_image = "asia-northeast1-docker.pkg.dev/your-project/ic-test/app:latest"
```

## 環境別設定

同一クライアントで複数環境（dev, staging, prod）を管理する場合：

```
terraform/clients/
├── company-a-dev/
│   └── terraform.tfvars   # environment = "dev"
├── company-a-staging/
│   └── terraform.tfvars   # environment = "staging"
└── company-a-prod/
    └── terraform.tfvars   # environment = "prod"
```

## リモートバックエンド設定

本番運用では、tfstateをリモートストレージで管理することを推奨します。

### Azure Storage Backend

```hcl
# main.tf
terraform {
  backend "azurerm" {
    resource_group_name  = "rg-terraform-state"
    storage_account_name = "stterraformstate"
    container_name       = "tfstate"
    key                  = "clients/company-a-prod.tfstate"
  }
}
```

### AWS S3 Backend

```hcl
terraform {
  backend "s3" {
    bucket = "terraform-state-bucket"
    key    = "clients/company-b-prod.tfstate"
    region = "ap-northeast-1"
  }
}
```

### GCP Cloud Storage Backend

```hcl
terraform {
  backend "gcs" {
    bucket = "terraform-state-bucket"
    prefix = "clients/company-c-prod"
  }
}
```

## よくある操作

### インフラの更新

```powershell
cd terraform/clients/company-a-prod
terraform plan    # 変更内容を確認
terraform apply   # 適用
```

### インフラの削除

```powershell
cd terraform/clients/company-a-prod
terraform destroy  # 全リソースを削除
```

### 設定の確認

```powershell
terraform output           # 出力値を表示
terraform output endpoints # エンドポイントを表示
```

## 注意事項

1. **機密情報**: `terraform.tfvars` にはAPIキー等の機密情報が含まれます。Gitにコミットしないでください。

2. **状態ファイル**: `terraform.tfstate` にはインフラの現在状態が保存されます。チームで作業する場合はリモートバックエンドを使用してください。

3. **リソース命名**: クライアント名は英数字とハイフンのみ使用可能です。リソース名の制約に注意してください。

4. **削除時の注意**: `terraform destroy` は全リソースを削除します。本番環境では慎重に実行してください。
