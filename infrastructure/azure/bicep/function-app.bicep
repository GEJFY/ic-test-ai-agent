// =============================================================================
// function-app.bicep - Azure Functions リソース定義
// =============================================================================
//
// 【概要】
// 内部統制テスト評価AIのバックエンドAPI（Azure Functions）を構築します。
//
// 【機能】
// - Python 3.11ランタイム
// - Managed Identity有効化（Key Vault、AIサービスアクセス用）
// - Application Insights統合
// - Key Vaultからのシークレット参照
// - CORS設定（APIM経由でのアクセス）
//
// 【使用例】
// module functionApp './function-app.bicep' = {
//   name: 'functionAppDeployment'
//   params: {
//     functionAppName: 'func-ic-test-ai-prod'
//     location: 'japaneast'
//     appInsightsConnectionString: appInsights.outputs.connectionString
//     keyVaultName: keyVault.outputs.keyVaultName
//     tags: { Environment: 'Production' }
//   }
// }
//
// =============================================================================

@description('Function App名（グローバルで一意）')
param functionAppName string

@description('Storage Account名（グローバルで一意、3-24文字、小文字英数字のみ）')
param storageAccountName string

@description('App Service Plan名')
param appServicePlanName string

@description('デプロイ先リージョン')
param location string = resourceGroup().location

@description('Application Insights Connection String')
param appInsightsConnectionString string

@description('Key Vault名（シークレット参照用）')
param keyVaultName string

@description('Pythonバージョン')
@allowed(['3.9', '3.10', '3.11'])
param pythonVersion string = '3.11'

@description('SKU名（Consumption=Y1, Premium=EP1/EP2/EP3）')
param skuName string = 'Y1'

@description('SKU Tier')
param skuTier string = 'Dynamic'

@description('リソースタグ')
param tags object = {}

// =============================================================================
// Storage Account（Function App用）
// =============================================================================

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  tags: tags
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Allow'
    }
  }
}

// =============================================================================
// App Service Plan（Consumption/Premium）
// =============================================================================

resource appServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: appServicePlanName
  location: location
  tags: tags
  sku: {
    name: skuName
    tier: skuTier
  }
  kind: 'functionapp'
  properties: {
    reserved: true // Linuxの場合はtrue
  }
}

// =============================================================================
// Function App
// =============================================================================

resource functionApp 'Microsoft.Web/sites@2023-01-01' = {
  name: functionAppName
  location: location
  tags: tags
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlan.id
    reserved: true
    httpsOnly: true

    siteConfig: {
      linuxFxVersion: 'Python|${pythonVersion}'
      pythonVersion: pythonVersion

      // アプリケーション設定
      appSettings: [
        // 基本設定
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=${environment().suffixes.storage}'
        }
        {
          name: 'WEBSITE_CONTENTAZUREFILECONNECTIONSTRING'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=${environment().suffixes.storage}'
        }
        {
          name: 'WEBSITE_CONTENTSHARE'
          value: toLower(functionAppName)
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }

        // Application Insights
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsightsConnectionString
        }

        // LLMプロバイダー設定
        {
          name: 'LLM_PROVIDER'
          value: 'AZURE'
        }

        // Azure Foundry API Key（Key Vaultから参照）
        {
          name: 'AZURE_FOUNDRY_API_KEY'
          value: '@Microsoft.KeyVault(VaultName=${keyVaultName};SecretName=AZURE-FOUNDRY-API-KEY)'
        }
        {
          name: 'AZURE_FOUNDRY_ENDPOINT'
          value: '@Microsoft.KeyVault(VaultName=${keyVaultName};SecretName=AZURE-FOUNDRY-ENDPOINT)'
        }
        {
          name: 'AZURE_FOUNDRY_DEPLOYMENT_NAME'
          value: 'gpt-4o'
        }

        // Document Intelligence設定（Key Vaultから参照）
        {
          name: 'AZURE_DOCUMENT_INTELLIGENCE_KEY'
          value: '@Microsoft.KeyVault(VaultName=${keyVaultName};SecretName=AZURE-DOCUMENT-INTELLIGENCE-KEY)'
        }
        {
          name: 'AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT'
          value: '@Microsoft.KeyVault(VaultName=${keyVaultName};SecretName=AZURE-DOCUMENT-INTELLIGENCE-ENDPOINT)'
        }

        // OCRプロバイダー設定
        {
          name: 'OCR_PROVIDER'
          value: 'AZURE'
        }

        // タイムアウト設定
        {
          name: 'FUNCTION_TIMEOUT_SECONDS'
          value: '540'
        }

        // デバッグ設定（本番環境ではfalse）
        {
          name: 'DEBUG'
          value: 'false'
        }

        // CORS設定（APIM経由を想定）
        {
          name: 'WEBSITE_CORS_ALLOWED_ORIGINS'
          value: '*'
        }
        {
          name: 'WEBSITE_CORS_SUPPORT_CREDENTIALS'
          value: 'false'
        }
      ]

      cors: {
        allowedOrigins: [
          '*'
        ]
        supportCredentials: false
      }

      // タイムアウト設定
      functionAppScaleLimit: 10
      minimumElasticInstanceCount: 0
    }
  }
}

// =============================================================================
// 出力
// =============================================================================

@description('Function AppのリソースID')
output functionAppId string = functionApp.id

@description('Function App名')
output functionAppName string = functionApp.name

@description('Function Appのデフォルトホスト名')
output functionAppHostName string = functionApp.properties.defaultHostName

@description('Function AppのManaged Identity Principal ID（Key Vaultアクセス権限付与用）')
output principalId string = functionApp.identity.principalId

@description('Function AppのエンドポイントURL')
output functionAppUrl string = 'https://${functionApp.properties.defaultHostName}'
