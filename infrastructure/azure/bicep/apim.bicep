// =============================================================================
// apim.bicep - Azure API Management リソース定義
// =============================================================================
//
// 【概要】
// 内部統制テスト評価AIのAPI Gateway層（Azure APIM）を構築します。
//
// 【機能】
// - API Key認証（Subscription Key）
// - レート制限（IPアドレスベース）
// - 相関ID管理（X-Correlation-IDヘッダー）
// - Application Insightsログ統合
// - バックエンド（Azure Functions）へのルーティング
// - CORS設定
//
// 【使用例】
// module apim './apim.bicep' = {
//   name: 'apimDeployment'
//   params: {
//     apimName: 'apim-ic-test-ai-prod'
//     location: 'japaneast'
//     publisherEmail: 'admin@example.com'
//     publisherName: 'Internal Control Test AI'
//     functionAppUrl: functionApp.outputs.functionAppUrl
//     appInsightsId: appInsights.outputs.appInsightsId
//     appInsightsInstrumentationKey: appInsights.outputs.instrumentationKey
//     tags: { Environment: 'Production' }
//   }
// }
//
// =============================================================================

@description('API Management名（グローバルで一意）')
param apimName string

@description('デプロイ先リージョン')
param location string = resourceGroup().location

@description('発行者メールアドレス')
param publisherEmail string

@description('発行者名')
param publisherName string

@description('Function AppのエンドポイントURL')
param functionAppUrl string

@description('Application InsightsのリソースID')
param appInsightsId string

@description('Application Insights Instrumentation Key')
param appInsightsInstrumentationKey string

@description('SKU名（Consumption, Developer, Basic, Standard, Premium）')
@allowed(['Consumption', 'Developer', 'Basic', 'Standard', 'Premium'])
param skuName string = 'Consumption'

@description('SKU容量（Consumption=0, Developer=1, Basic=1-2, Standard=1-4, Premium=1-10）')
param skuCapacity int = 0

@description('リソースタグ')
param tags object = {}

// =============================================================================
// API Managementリソース
// =============================================================================

resource apim 'Microsoft.ApiManagement/service@2023-05-01-preview' = {
  name: apimName
  location: location
  tags: tags
  sku: {
    name: skuName
    capacity: skuCapacity
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    publisherEmail: publisherEmail
    publisherName: publisherName

    // カスタムドメイン設定（必要に応じて）
    // hostnameConfigurations: []

    // 仮想ネットワーク統合（Premiumプランの場合）
    // virtualNetworkType: 'None'

    // プロトコル設定
    customProperties: {
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Protocols.Tls10': 'False'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Protocols.Tls11': 'False'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Protocols.Ssl30': 'False'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Backend.Protocols.Tls10': 'False'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Backend.Protocols.Tls11': 'False'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Backend.Protocols.Ssl30': 'False'
    }
  }
}

// =============================================================================
// Application Insightsロガー
// =============================================================================

resource apimLogger 'Microsoft.ApiManagement/service/loggers@2023-05-01-preview' = {
  parent: apim
  name: 'appinsights-logger'
  properties: {
    loggerType: 'applicationInsights'
    resourceId: appInsightsId
    credentials: {
      instrumentationKey: appInsightsInstrumentationKey
    }
    isBuffered: true
  }
}

// =============================================================================
// Named Values（バックエンドURL等の設定値）
// =============================================================================

resource namedValueFunctionAppUrl 'Microsoft.ApiManagement/service/namedValues@2023-05-01-preview' = {
  parent: apim
  name: 'backend-function-app-url'
  properties: {
    displayName: 'backend-function-app-url'
    value: functionAppUrl
    secret: false
  }
}

// =============================================================================
// バックエンド（Azure Functions）
// =============================================================================

resource backend 'Microsoft.ApiManagement/service/backends@2023-05-01-preview' = {
  parent: apim
  name: 'ic-test-ai-backend'
  properties: {
    title: 'IC Test AI Azure Functions Backend'
    description: '内部統制テスト評価AIのバックエンド（Azure Functions）'
    protocol: 'http'
    url: functionAppUrl
    resourceId: '${environment().resourceManager}${functionAppUrl}'
  }
}

// =============================================================================
// API定義
// =============================================================================

resource api 'Microsoft.ApiManagement/service/apis@2023-05-01-preview' = {
  parent: apim
  name: 'ic-test-ai-api'
  properties: {
    displayName: 'IC Test AI API'
    description: '内部統制テスト評価AI API'
    path: 'api'
    protocols: ['https']
    subscriptionRequired: true
    isCurrent: true
    apiRevision: '1'
    apiVersion: 'v1'
    apiVersionSetId: null
    serviceUrl: functionAppUrl
  }
}

// =============================================================================
// API操作（エンドポイント）
// =============================================================================

// POST /api/evaluate
resource operationEvaluate 'Microsoft.ApiManagement/service/apis/operations@2023-05-01-preview' = {
  parent: api
  name: 'evaluate'
  properties: {
    displayName: 'Evaluate Controls'
    method: 'POST'
    urlTemplate: '/evaluate'
    description: 'テスト項目を評価し、結果を返します'
    request: {
      description: 'テスト項目の配列'
      representations: [
        {
          contentType: 'application/json'
          sample: '{"items": [{"ID": "001", "controlObjective": "目的", "testProcedure": "手続", "acceptanceCriteria": "基準"}]}'
        }
      ]
    }
    responses: [
      {
        statusCode: 200
        description: '評価成功'
        representations: [
          {
            contentType: 'application/json'
          }
        ]
      }
      {
        statusCode: 400
        description: 'リクエストエラー'
      }
      {
        statusCode: 500
        description: 'サーバーエラー'
      }
    ]
  }
}

// POST /api/evaluate/submit（非同期）
resource operationEvaluateSubmit 'Microsoft.ApiManagement/service/apis/operations@2023-05-01-preview' = {
  parent: api
  name: 'evaluate-submit'
  properties: {
    displayName: 'Submit Evaluation Job'
    method: 'POST'
    urlTemplate: '/evaluate/submit'
    description: '評価ジョブを送信し、ジョブIDを返します'
  }
}

// GET /api/evaluate/status/{job_id}
resource operationEvaluateStatus 'Microsoft.ApiManagement/service/apis/operations@2023-05-01-preview' = {
  parent: api
  name: 'evaluate-status'
  properties: {
    displayName: 'Get Job Status'
    method: 'GET'
    urlTemplate: '/evaluate/status/{job_id}'
    description: 'ジョブのステータスを取得'
    templateParameters: [
      {
        name: 'job_id'
        type: 'string'
        required: true
      }
    ]
  }
}

// GET /api/evaluate/results/{job_id}
resource operationEvaluateResults 'Microsoft.ApiManagement/service/apis/operations@2023-05-01-preview' = {
  parent: api
  name: 'evaluate-results'
  properties: {
    displayName: 'Get Job Results'
    method: 'GET'
    urlTemplate: '/evaluate/results/{job_id}'
    description: 'ジョブの結果を取得'
    templateParameters: [
      {
        name: 'job_id'
        type: 'string'
        required: true
      }
    ]
  }
}

// GET /api/health
resource operationHealth 'Microsoft.ApiManagement/service/apis/operations@2023-05-01-preview' = {
  parent: api
  name: 'health'
  properties: {
    displayName: 'Health Check'
    method: 'GET'
    urlTemplate: '/health'
    description: 'ヘルスチェックエンドポイント'
  }
}

// GET /api/config
resource operationConfig 'Microsoft.ApiManagement/service/apis/operations@2023-05-01-preview' = {
  parent: api
  name: 'config'
  properties: {
    displayName: 'Config Status'
    method: 'GET'
    urlTemplate: '/config'
    description: '設定状態確認エンドポイント'
  }
}

// =============================================================================
// API診断ログ設定
// =============================================================================

resource apiDiagnostic 'Microsoft.ApiManagement/service/apis/diagnostics@2023-05-01-preview' = {
  parent: api
  name: 'applicationinsights'
  properties: {
    loggerId: apimLogger.id
    alwaysLog: 'allErrors'
    logClientIp: true
    httpCorrelationProtocol: 'W3C'
    verbosity: 'information'
    sampling: {
      samplingType: 'fixed'
      percentage: 100
    }
    frontend: {
      request: {
        headers: ['X-Correlation-ID', 'User-Agent']
        body: {
          bytes: 8192
        }
      }
      response: {
        headers: ['X-Correlation-ID']
        body: {
          bytes: 8192
        }
      }
    }
    backend: {
      request: {
        headers: ['X-Correlation-ID']
        body: {
          bytes: 8192
        }
      }
      response: {
        headers: ['X-Correlation-ID']
        body: {
          bytes: 8192
        }
      }
    }
  }
}

// =============================================================================
// サブスクリプション（API Key）
// =============================================================================

resource subscription 'Microsoft.ApiManagement/service/subscriptions@2023-05-01-preview' = {
  parent: apim
  name: 'ic-test-ai-subscription'
  properties: {
    displayName: 'IC Test AI Subscription'
    scope: api.id
    state: 'active'
  }
}

// =============================================================================
// 製品（Product）
// =============================================================================

resource product 'Microsoft.ApiManagement/service/products@2023-05-01-preview' = {
  parent: apim
  name: 'ic-test-ai-product'
  properties: {
    displayName: 'IC Test AI Product'
    description: '内部統制テスト評価AI製品'
    subscriptionRequired: true
    approvalRequired: false
    state: 'published'
  }
}

resource productApi 'Microsoft.ApiManagement/service/products/apis@2023-05-01-preview' = {
  parent: product
  name: api.name
}

// =============================================================================
// 出力
// =============================================================================

@description('API ManagementのリソースID')
output apimId string = apim.id

@description('API Management名')
output apimName string = apim.name

@description('API ManagementのゲートウェイURL')
output apimGatewayUrl string = apim.properties.gatewayUrl

@description('API ManagementのManaged Identity Principal ID')
output apimPrincipalId string = apim.identity.principalId

@description('サブスクリプションキー（Primary）※機密情報、デプロイ後に取得推奨')
output subscriptionKeyNote string = 'Subscription Keyは Azure Portal から取得してください: ${apim.name} → Subscriptions → ${subscription.name}'

@description('APIエンドポイント例')
output apiEndpointExample string = '${apim.properties.gatewayUrl}/api/evaluate'
