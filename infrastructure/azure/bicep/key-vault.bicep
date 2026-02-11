// =============================================================================
// key-vault.bicep - Azure Key Vault リソース定義
// =============================================================================
//
// 【概要】
// APIキーやシークレットを安全に管理するためのKey Vaultを構築します。
//
// 【機能】
// - シークレット管理（Azure Foundry API Key、OpenAI API Key等）
// - アクセス制御（Function AppのManaged Identityに読み取り権限付与）
// - 監査ログ（Diagnostic Settings経由でLog Analyticsに送信）
// - ソフトデリート有効化（誤削除対策）
//
// 【使用例】
// module keyVault './key-vault.bicep' = {
//   name: 'keyVaultDeployment'
//   params: {
//     keyVaultName: 'kv-ic-test-ai-prod'
//     location: 'japaneast'
//     functionAppPrincipalId: functionApp.outputs.principalId
//     tags: { Environment: 'Production' }
//   }
// }
//
// =============================================================================

@description('Key Vault名（3-24文字、英数字とハイフンのみ）')
param keyVaultName string

@description('デプロイ先リージョン')
param location string = resourceGroup().location

@description('Function AppのManaged Identity Principal ID（シークレット読み取り権限付与用）')
param functionAppPrincipalId string

@description('Log Analytics Workspace ID（診断ログ送信先）')
param logAnalyticsWorkspaceId string = ''

@description('リソースタグ')
param tags object = {}

// =============================================================================
// Key Vaultリソース
// =============================================================================

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId

    // アクセスポリシー（RBAC推奨だが、既存システムとの互換性のため）
    enabledForDeployment: false
    enabledForDiskEncryption: false
    enabledForTemplateDeployment: true

    // ソフトデリート設定（誤削除対策）
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    enablePurgeProtection: true

    // ネットワーク設定（初期はすべて許可、本番環境では制限推奨）
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Allow'
    }

    // Function Appへのアクセス権限
    accessPolicies: [
      {
        tenantId: subscription().tenantId
        objectId: functionAppPrincipalId
        permissions: {
          secrets: [
            'get'
            'list'
          ]
        }
      }
    ]
  }
}

// =============================================================================
// 診断ログ設定（Log Analyticsに送信）
// =============================================================================

resource keyVaultDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (!empty(logAnalyticsWorkspaceId)) {
  name: '${keyVaultName}-diagnostics'
  scope: keyVault
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
        retentionPolicy: {
          enabled: true
          days: 30
        }
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
        retentionPolicy: {
          enabled: true
          days: 30
        }
      }
    ]
  }
}

// =============================================================================
// サンプルシークレット（デプロイ後に実際の値を手動で設定）
// =============================================================================

// Note: デプロイ時はダミー値を設定し、デプロイ後にAzure Portalまたは
// Azure CLIで実際のAPI Keyを設定してください。

resource secretAzureFoundryApiKey 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'AZURE-FOUNDRY-API-KEY'
  properties: {
    value: 'REPLACE_WITH_ACTUAL_API_KEY'
    contentType: 'text/plain'
    attributes: {
      enabled: true
    }
  }
}

resource secretOpenAiApiKey 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'OPENAI-API-KEY'
  properties: {
    value: 'REPLACE_WITH_ACTUAL_API_KEY'
    contentType: 'text/plain'
    attributes: {
      enabled: true
    }
  }
}

resource secretAzureFoundryEndpoint 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'AZURE-FOUNDRY-ENDPOINT'
  properties: {
    value: 'https://your-foundry-endpoint.openai.azure.com/'
    contentType: 'text/plain'
    attributes: {
      enabled: true
    }
  }
}

resource secretDocumentIntelligenceKey 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'AZURE-DOCUMENT-INTELLIGENCE-KEY'
  properties: {
    value: 'REPLACE_WITH_ACTUAL_API_KEY'
    contentType: 'text/plain'
    attributes: {
      enabled: true
    }
  }
}

resource secretDocumentIntelligenceEndpoint 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'AZURE-DOCUMENT-INTELLIGENCE-ENDPOINT'
  properties: {
    value: 'https://your-doc-intelligence.cognitiveservices.azure.com/'
    contentType: 'text/plain'
    attributes: {
      enabled: true
    }
  }
}

// =============================================================================
// 出力
// =============================================================================

@description('Key VaultのリソースID')
output keyVaultId string = keyVault.id

@description('Key Vault名')
output keyVaultName string = keyVault.name

@description('Key VaultのURI')
output keyVaultUri string = keyVault.properties.vaultUri

@description('シークレット参照形式の例（Function App環境変数用）')
output secretReferenceExample string = '@Microsoft.KeyVault(VaultName=${keyVault.name};SecretName=AZURE-FOUNDRY-API-KEY)'
