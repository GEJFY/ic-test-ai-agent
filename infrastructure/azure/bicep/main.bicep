// =============================================================================
// main.bicep - メインデプロイメントテンプレート
// =============================================================================
//
// 【概要】
// 内部統制テスト評価AIシステムの全Azureリソースを統合デプロイします。
//
// 【デプロイされるリソース】
// 1. Log Analytics Workspace + Application Insights（監視基盤）
// 2. Storage Account + App Service Plan + Function App（バックエンド）
// 3. Key Vault（シークレット管理）
// 4. API Management（API Gateway層）
//
// 【デプロイ方法】
// ```bash
// # リソースグループ作成
// az group create --name rg-ic-test-ai-prod --location japaneast
//
// # デプロイ実行
// az deployment group create \
//   --resource-group rg-ic-test-ai-prod \
//   --template-file main.bicep \
//   --parameters parameters.json
//
// # デプロイ後の設定
// 1. Key Vaultに実際のAPI Keyを設定
// 2. Function Appにコードをデプロイ（func azure functionapp publish <FunctionAppName>）
// 3. APIMポリシーを設定（apim-policies.xmlを適用）
// 4. APIMサブスクリプションキーを取得し、VBA/PowerShellに設定
// ```
//
// 【相関IDフロー確認】
// 1. VBAでSessionID生成 → X-Correlation-IDヘッダー
// 2. APIM受信 → ログ記録 → Functions転送
// 3. Functionsで処理 → Application Insightsにログ記録
// 4. Log Analyticsでクエリ：
//    traces | where customDimensions.correlation_id == "<相関ID>"
//
// =============================================================================

targetScope = 'resourceGroup'

// =============================================================================
// パラメータ
// =============================================================================

@description('プロジェクト名（リソース名のプレフィックス）')
param projectName string

@description('環境名（dev, stg, prod）')
@allowed(['dev', 'stg', 'prod'])
param environment string

@description('デプロイ先リージョン')
param location string = resourceGroup().location

@description('APIM発行者メールアドレス')
param apimPublisherEmail string

@description('APIM発行者名')
param apimPublisherName string

@description('APIM SKU名')
@allowed(['Consumption', 'Developer', 'Basic', 'Standard', 'Premium'])
param apimSkuName string = 'Consumption'

@description('APIM SKU容量')
param apimSkuCapacity int = 0

@description('Function App SKU名')
param functionAppSkuName string = 'Y1'

@description('Function App SKU Tier')
param functionAppSkuTier string = 'Dynamic'

@description('Pythonバージョン')
@allowed(['3.9', '3.10', '3.11'])
param pythonVersion string = '3.11'

@description('リソースタグ')
param tags object = {
  Project: 'InternalControlTestAI'
  Environment: environment
  ManagedBy: 'Bicep'
}

// =============================================================================
// 変数（リソース名生成）
// =============================================================================

var suffix = uniqueString(resourceGroup().id)
var logAnalyticsWorkspaceName = 'log-${projectName}-${environment}-${suffix}'
var appInsightsName = 'appi-${projectName}-${environment}-${suffix}'
var storageAccountName = toLower(replace('st${projectName}${environment}${take(suffix, 6)}', '-', ''))
var appServicePlanName = 'asp-${projectName}-${environment}-${suffix}'
var functionAppName = 'func-${projectName}-${environment}-${suffix}'
var keyVaultName = 'kv-${projectName}-${take(suffix, 8)}'
var apimName = 'apim-${projectName}-${environment}-${suffix}'

// =============================================================================
// モジュール1: Application Insights（監視基盤）
// =============================================================================

module appInsights './app-insights.bicep' = {
  name: 'appInsightsDeployment'
  params: {
    appInsightsName: appInsightsName
    logAnalyticsWorkspaceName: logAnalyticsWorkspaceName
    location: location
    tags: tags
    retentionInDays: 30
    dailyDataCapInGB: 1
  }
}

// =============================================================================
// モジュール2: Function App（バックエンド）
// =============================================================================

module functionApp './function-app.bicep' = {
  name: 'functionAppDeployment'
  params: {
    functionAppName: functionAppName
    storageAccountName: storageAccountName
    appServicePlanName: appServicePlanName
    location: location
    appInsightsConnectionString: appInsights.outputs.connectionString
    keyVaultName: keyVaultName
    pythonVersion: pythonVersion
    skuName: functionAppSkuName
    skuTier: functionAppSkuTier
    tags: tags
  }
}

// =============================================================================
// モジュール3: Key Vault（シークレット管理）
// =============================================================================

module keyVault './key-vault.bicep' = {
  name: 'keyVaultDeployment'
  dependsOn: [
    functionApp
  ]
  params: {
    keyVaultName: keyVaultName
    location: location
    functionAppPrincipalId: functionApp.outputs.principalId
    logAnalyticsWorkspaceId: appInsights.outputs.logAnalyticsWorkspaceId
    tags: tags
  }
}

// =============================================================================
// モジュール4: API Management（API Gateway層）
// =============================================================================

module apim './apim.bicep' = {
  name: 'apimDeployment'
  dependsOn: [
    functionApp
    appInsights
  ]
  params: {
    apimName: apimName
    location: location
    publisherEmail: apimPublisherEmail
    publisherName: apimPublisherName
    functionAppUrl: functionApp.outputs.functionAppUrl
    appInsightsId: appInsights.outputs.appInsightsId
    appInsightsInstrumentationKey: appInsights.outputs.instrumentationKey
    skuName: apimSkuName
    skuCapacity: apimSkuCapacity
    tags: tags
  }
}

// =============================================================================
// 出力
// =============================================================================

@description('リソースグループ名')
output resourceGroupName string = resourceGroup().name

@description('デプロイ先リージョン')
output location string = location

// Application Insights
@description('Application Insights名')
output appInsightsName string = appInsights.outputs.appInsightsName

@description('Application Insights Connection String')
output appInsightsConnectionString string = appInsights.outputs.connectionString

@description('Log Analytics Workspace ID')
output logAnalyticsWorkspaceId string = appInsights.outputs.logAnalyticsWorkspaceId

// Function App
@description('Function App名')
output functionAppName string = functionApp.outputs.functionAppName

@description('Function AppのエンドポイントURL')
output functionAppUrl string = functionApp.outputs.functionAppUrl

// Key Vault
@description('Key Vault名')
output keyVaultName string = keyVault.outputs.keyVaultName

@description('Key VaultのURI')
output keyVaultUri string = keyVault.outputs.keyVaultUri

// API Management
@description('API Management名')
output apimName string = apim.outputs.apimName

@description('API ManagementのゲートウェイURL')
output apimGatewayUrl string = apim.outputs.apimGatewayUrl

@description('APIエンドポイント（VBA/PowerShellで使用）')
output apiEndpoint string = '${apim.outputs.apimGatewayUrl}/api/evaluate'

// デプロイ後の手順
@description('デプロイ後の設定手順')
output postDeploymentSteps string = '''
========================================
デプロイ完了！次の手順を実施してください
========================================

1. Key Vaultにシークレットを設定:
   az keyvault secret set --vault-name ${keyVault.outputs.keyVaultName} --name AZURE-FOUNDRY-API-KEY --value "<実際のAPIキー>"
   az keyvault secret set --vault-name ${keyVault.outputs.keyVaultName} --name AZURE-FOUNDRY-ENDPOINT --value "<実際のエンドポイント>"
   az keyvault secret set --vault-name ${keyVault.outputs.keyVaultName} --name AZURE-DOCUMENT-INTELLIGENCE-KEY --value "<実際のAPIキー>"
   az keyvault secret set --vault-name ${keyVault.outputs.keyVaultName} --name AZURE-DOCUMENT-INTELLIGENCE-ENDPOINT --value "<実際のエンドポイント>"

2. Function Appにコードをデプロイ:
   cd platforms/azure
   func azure functionapp publish ${functionApp.outputs.functionAppName}

3. APIMポリシーを適用:
   Azure Portal → API Management → APIs → ic-test-ai-api → Design → Inbound processing
   → Code editor → infrastructure/azure/apim-policies.xml の内容を貼り付け

4. APIMサブスクリプションキーを取得:
   Azure Portal → ${apim.outputs.apimName} → Subscriptions → ic-test-ai-subscription
   → Primary Key をコピー

5. VBA/PowerShellのエンドポイントとAPI Keyを更新:
   - エンドポイント: ${apim.outputs.apimGatewayUrl}/api/evaluate
   - API Key: 上記で取得したSubscription Key

6. 相関IDフローを確認:
   Log Analyticsで以下のクエリを実行:
   traces
   | where customDimensions.correlation_id == "<X-Correlation-IDヘッダーの値>"
   | project timestamp, message, customDimensions, operation_Name
   | order by timestamp asc

========================================
'''
