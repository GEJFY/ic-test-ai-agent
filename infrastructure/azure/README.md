# Azure インフラストラクチャ - デプロイガイド

## 概要

内部統制テスト評価AIシステムのAzureインフラストラクチャをBicepで管理します。

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

# Bicep CLI
az bicep version  # 0.20.0以上

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

`bicep/parameters.json` を編集し、環境に合わせて値を設定します。

```json
{
  "parameters": {
    "projectName": {
      "value": "ic-test-ai"  // プロジェクト名
    },
    "environment": {
      "value": "prod"  // dev, stg, prod
    },
    "location": {
      "value": "japaneast"  // リージョン
    },
    "apimPublisherEmail": {
      "value": "your-email@example.com"  // ✏️ 要変更
    },
    "apimPublisherName": {
      "value": "Your Organization Name"  // ✏️ 要変更
    }
  }
}
```

### ステップ2: リソースグループ作成

```bash
# リソースグループ作成
az group create \
  --name rg-ic-test-ai-prod \
  --location japaneast
```

### ステップ3: Bicepデプロイ実行

```bash
# デプロイ実行（約15-20分）
cd infrastructure/azure/bicep

az deployment group create \
  --resource-group rg-ic-test-ai-prod \
  --template-file main.bicep \
  --parameters parameters.json \
  --query "properties.outputs" \
  --output table
```

**デプロイ完了後、出力される情報をメモしてください：**
- `apimGatewayUrl`: VBA/PowerShellで使用するエンドポイント
- `keyVaultName`: シークレット設定先
- `functionAppName`: コードデプロイ先

### ステップ4: Key Vaultにシークレットを設定

**重要：デプロイ時はダミー値が設定されます。以下のコマンドで実際のAPI Keyを設定してください。**

```bash
# Key Vault名を取得
KEY_VAULT_NAME=$(az deployment group show \
  --resource-group rg-ic-test-ai-prod \
  --name main \
  --query "properties.outputs.keyVaultName.value" \
  --output tsv)

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

### ステップ6: APIMポリシーを適用

**方法1: Azure Portal（推奨）**

1. Azure Portal → API Management → 対象のAPIM
2. "APIs" → "ic-test-ai-api" → "Design"
3. "All operations" → "Inbound processing" → `</>` (Code editor)
4. `infrastructure/azure/apim-policies.xml` の内容をコピー&ペースト
5. "Save"

**方法2: Azure CLI**

```bash
# ポリシーファイルを適用
az apim api policy create \
  --resource-group rg-ic-test-ai-prod \
  --service-name <APIM名> \
  --api-id ic-test-ai-api \
  --policy-content @apim-policies.xml
```

### ステップ7: APIMサブスクリプションキーを取得

```bash
# Subscription Key（Primary）を取得
az apim subscription show \
  --resource-group rg-ic-test-ai-prod \
  --service-name <APIM名> \
  --sid ic-test-ai-subscription \
  --query "primaryKey" \
  --output tsv
```

**このキーをVBA/PowerShellの `API_KEY` に設定します。**

### ステップ8: VBA/PowerShellのエンドポイント変更

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
  --resource-group rg-ic-test-ai-prod \
  --name <Function App名>

# Key Vaultアクセスポリシー確認
az keyvault show \
  --name <Key Vault名> \
  --query "properties.accessPolicies"
```

### APIM: 429 Too Many Requests

レート制限に達しています。`apim-policies.xml` の以下を調整：

```xml
<rate-limit-by-key calls="100" renewal-period="60" ... />
<!-- calls を増やす -->
```

### Application Insights: ログが表示されない

ログ伝播に最大5分かかります。しばらく待ってから再確認してください。

## リソース削除

```bash
# リソースグループごと削除
az group delete --name rg-ic-test-ai-prod --yes --no-wait

# Key Vaultを完全削除（再デプロイ時）
az keyvault purge --name <Key Vault名>
```

## コスト最適化

### 1. Application Insightsサンプリング

`app-insights.bicep` の `SamplingPercentage` を 10-20% に変更：

```bicep
SamplingPercentage: 10  // 初期100% → 10%に削減
```

### 2. ログ保持期間短縮

`app-insights.bicep` の `retentionInDays` を調整：

```bicep
retentionInDays: 30  // 初期30日 → 必要に応じて短縮
```

### 3. APIM Consumptionプラン活用

Consumptionプランは呼び出し数に応じた従量課金なので、利用が少ない場合は非常に安価です。

## セキュリティ強化（本番環境推奨）

### 1. APIMネットワークアクセス制限

```xml
<!-- apim-policies.xml に追加 -->
<ip-filter action="allow">
    <address>xxx.xxx.xxx.xxx</address>  <!-- 許可するIPアドレス -->
</ip-filter>
```

### 2. Key Vaultネットワークアクセス制限

```bicep
// key-vault.bicep のnetworkAcls変更
networkAcls: {
  bypass: 'AzureServices'
  defaultAction: 'Deny'
  ipRules: [
    {
      value: 'xxx.xxx.xxx.xxx'  // 許可するIPアドレス
    }
  ]
}
```

### 3. Managed Identity RBAC

アクセスポリシーではなくRBACを使用（推奨）：

```bash
# Function AppにKey Vaultシークレット読み取り権限付与
az role assignment create \
  --assignee <Function App Principal ID> \
  --role "Key Vault Secrets User" \
  --scope /subscriptions/<サブスクリプションID>/resourceGroups/rg-ic-test-ai-prod/providers/Microsoft.KeyVault/vaults/<Key Vault名>
```

## 参考リンク

- [Azure API Management ドキュメント](https://learn.microsoft.com/azure/api-management/)
- [Azure Functions Bicep リファレンス](https://learn.microsoft.com/azure/templates/microsoft.web/sites)
- [Key Vault Bicep リファレンス](https://learn.microsoft.com/azure/templates/microsoft.keyvault/vaults)
- [Application Insights ドキュメント](https://learn.microsoft.com/azure/azure-monitor/app/app-insights-overview)
