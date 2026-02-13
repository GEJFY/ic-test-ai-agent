# Azure インフラストラクチャ - デプロイガイド

## 概要

内部統制テスト評価AIシステムのAzureインフラストラクチャをTerraformで管理します。

### デプロイされるリソース

| リソース | 用途 | 月額コスト（想定） |
|---------|------|------------------|
| **API Management** (Consumption) | API Gateway層、認証、レート制限 | ~$3.50 |
| **Azure Functions** (Consumption) | バックエンドAPI | ~$0.50 |
| **Key Vault** | シークレット管理 | ~$9.00 |
| **Application Insights** | 監視、ログ、トレース | ~$4.60 |
| **Storage Account** | Function App用ストレージ | ~$0.02 |
| **Log Analytics Workspace** | ログ保存 | 無料枠内 |
| **合計** | | **~$17.62/月** |

## 前提条件

### 必要なツール

```bash
# Azure CLI
az --version  # 2.50.0以上

# Terraform
terraform --version  # 1.5.0以上

# Azure Functions Core Tools（コードデプロイ用）
func --version  # 4.0.5
```

### Azure CLIログイン

```bash
# Azureにログイン
az login

# サブスクリプション確認
az account show

# サブスクリプション変更（必要な場合）
az account set --subscription "<サブスクリプションID>"
```

## デプロイ手順

### ステップ1: パラメータファイル編集

`terraform/terraform.tfvars` を編集し、環境に合わせて値を設定します。

```hcl
project_name        = "ic-test-ai"
environment         = "prod"          # dev, stg, prod
location            = "japaneast"     # リージョン
resource_group_name = "rg-ic-test-evaluation"

# APIM設定
apim_publisher_email = "your-email@example.com"  # ✏️ 要変更
apim_publisher_name  = "Your Organization Name"  # ✏️ 要変更
apim_sku_name        = "Consumption"
apim_sku_capacity    = 0

# Function App設定
function_app_sku_name = "Y1"
function_app_sku_tier = "Dynamic"
python_version        = "3.11"
```

### ステップ2: リソースグループ作成

```bash
# リソースグループ作成
az group create \
  --name rg-ic-test-evaluation \
  --location japaneast
```

### ステップ3: Terraformデプロイ実行

```bash
# Terraformディレクトリに移動
cd infrastructure/azure/terraform

# 初期化
terraform init

# プラン確認（約15-20分）
terraform plan -out=tfplan

# デプロイ実行
terraform apply tfplan
```

**デプロイ完了後、出力される情報をメモしてください：**

- `apim_gateway_url`: VBA/PowerShellで使用するエンドポイント
- `key_vault_name`: シークレット設定先
- `function_app_name`: コードデプロイ先

### ステップ4: Key Vaultにシークレットを設定

**重要：デプロイ時はダミー値が設定されます。以下のコマンドで実際のAPI Keyを設定してください。**

```bash
# Key Vault名を取得
KEY_VAULT_NAME=$(cd infrastructure/azure/terraform && terraform output -raw key_vault_name)

# Azure Foundry API Key設定
az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name AZURE-FOUNDRY-API-KEY \
  --value "<実際のAPIキー>"

# Azure Foundry Endpoint設定
az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name AZURE-FOUNDRY-ENDPOINT \
  --value "https://your-foundry-endpoint.openai.azure.com/"

# Document Intelligence Key設定
az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name AZURE-DOCUMENT-INTELLIGENCE-KEY \
  --value "<実際のAPIキー>"

# Document Intelligence Endpoint設定
az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name AZURE-DOCUMENT-INTELLIGENCE-ENDPOINT \
  --value "https://your-doc-intelligence.cognitiveservices.azure.com/"
```

### ステップ5: Function Appにコードをデプロイ

```bash
# platforms/azureディレクトリに移動
cd ../../../platforms/azure

# Function Appにデプロイ
func azure functionapp publish <FunctionAppName>
```

### ステップ6: APIMサブスクリプションキーを取得

```bash
# Subscription Key（Primary）を取得
az apim subscription show \
  --resource-group rg-ic-test-evaluation \
  --service-name <APIM名> \
  --sid ic-test-ai-subscription \
  --query "primaryKey" \
  --output tsv
```

**このキーをVBA/PowerShellの `API_KEY` に設定します。**

### ステップ7: VBA/PowerShellのエンドポイント変更

**ExcelToJson.bas (VBA):**

```vb
' APIM経由のエンドポイントに変更
Private Const API_URL As String = "https://<APIM名>.azure-api.net/api/evaluate"
Private Const API_KEY As String = "<Subscription Key>"

' HTTP リクエストヘッダーにAPI Key追加
xhr.setRequestHeader "Ocp-Apim-Subscription-Key", API_KEY
xhr.setRequestHeader "X-Correlation-ID", correlationID
```

**CallCloudApi.ps1 (PowerShell):**

```powershell
# APIM経由のエンドポイントに変更
$ApiUrl = "https://<APIM名>.azure-api.net/api/evaluate"
$ApiKey = "<Subscription Key>"

# ヘッダー設定
$headers = @{
    "Content-Type" = "application/json; charset=utf-8"
    "Ocp-Apim-Subscription-Key" = $ApiKey
    "X-Correlation-ID" = $CorrelationId
}
```

## デプロイ後の確認

### 1. ヘルスチェック

```bash
curl -X GET \
  -H "Ocp-Apim-Subscription-Key: <Subscription Key>" \
  "https://<APIM名>.azure-api.net/api/health"
```

### 2. 相関IDフロー確認

```bash
# テストリクエスト送信
CORRELATION_ID=$(uuidgen)
curl -X POST \
  -H "Content-Type: application/json" \
  -H "Ocp-Apim-Subscription-Key: <Subscription Key>" \
  -H "X-Correlation-ID: $CORRELATION_ID" \
  -d '{"items":[{"ID":"001","controlObjective":"test","testProcedure":"test","acceptanceCriteria":"test"}]}' \
  "https://<APIM名>.azure-api.net/api/evaluate"

# Log Analyticsでログ確認
az monitor log-analytics query \
  --workspace <Log Analytics Workspace ID> \
  --analytics-query "traces | where customDimensions.correlation_id == '$CORRELATION_ID' | project timestamp, message, customDimensions, operation_Name | order by timestamp asc"
```

### 3. Application Insightsで依存関係マップ確認

Azure Portal → Application Insights → "Application map"

以下が可視化されていることを確認：

- VBA/PowerShell → APIM → Azure Functions → Azure Foundry API
- 相関IDですべてのリクエストが追跡可能

## トラブルシューティング

### デプロイエラー: "Key Vault name already exists"

Key Vault名は削除後90日間予約されます。以下で完全削除：

```bash
az keyvault purge --name <Key Vault名>
```

### Function App: Key Vaultアクセスエラー

Managed Identityの権限確認：

```bash
# Function AppのManaged Identity確認
az functionapp identity show \
  --resource-group rg-ic-test-evaluation \
  --name <Function App名>

# Key Vaultアクセスポリシー確認
az keyvault show \
  --name <Key Vault名> \
  --query "properties.accessPolicies"
```

### APIM: 429 Too Many Requests

レート制限に達しています。Terraform の `apim.tf` で設定されたAPIMポリシーを調整してください。

### Application Insights: ログが表示されない

ログ伝播に最大5分かかります。しばらく待ってから再確認してください。

## リソース削除

### Terraformで削除（推奨）

```bash
cd infrastructure/azure/terraform
terraform destroy
```

### リソースグループごと削除

```bash
az group delete --name rg-ic-test-evaluation --yes --no-wait

# Key Vaultを完全削除（再デプロイ時）
az keyvault purge --name <Key Vault名>
```

## コスト最適化

### 1. Application Insightsサンプリング

`terraform/monitoring.tf` の `sampling_percentage` を 10-20% に変更：

```hcl
sampling_percentage = 10  # 初期100% → 10%に削減
```

### 2. ログ保持期間短縮

`terraform/variables.tf` の `log_retention_in_days` を調整：

```hcl
variable "log_retention_in_days" {
  default = 30  # 必要に応じて短縮
}
```

### 3. APIM Consumptionプラン活用

Consumptionプランは呼び出し数に応じた従量課金なので、利用が少ない場合は非常に安価です。

## セキュリティ強化（本番環境推奨）

### 1. APIMネットワークアクセス制限

`terraform/apim.tf` でIPフィルタリングポリシーを追加：

```hcl
# APIM ポリシーでIPフィルタリングを追加
# azure_api_management_api_policy リソースで管理
```

### 2. Key Vaultネットワークアクセス制限

`terraform/key-vault.tf` の `network_acls` を変更：

```hcl
network_acls {
  bypass         = "AzureServices"
  default_action = "Deny"
  ip_rules       = ["xxx.xxx.xxx.xxx"]  # 許可するIPアドレス
}
```

### 3. Managed Identity RBAC

アクセスポリシーではなくRBACを使用（推奨）：

```bash
# Function AppにKey Vaultシークレット読み取り権限付与
az role assignment create \
  --assignee <Function App Principal ID> \
  --role "Key Vault Secrets User" \
  --scope /subscriptions/<サブスクリプションID>/resourceGroups/rg-ic-test-evaluation/providers/Microsoft.KeyVault/vaults/<Key Vault名>
```

## 参考リンク

- [Azure API Management ドキュメント](https://learn.microsoft.com/azure/api-management/)
- [Azure Functions Terraform リファレンス](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/linux_function_app)
- [Key Vault Terraform リファレンス](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/key_vault)
- [Application Insights ドキュメント](https://learn.microsoft.com/azure/azure-monitor/app/app-insights-overview)
