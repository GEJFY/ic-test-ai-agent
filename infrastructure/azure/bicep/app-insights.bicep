// =============================================================================
// app-insights.bicep - Application Insights リソース定義
// =============================================================================
//
// 【概要】
// Azure Functions、APIM、AIサービスの監視・トレーシングを統合管理します。
//
// 【機能】
// - アプリケーションパフォーマンス監視（APM）
// - 分散トレーシング（相関ID追跡）
// - カスタムメトリクス・イベント記録
// - ログクエリ（Log Analytics統合）
// - アラート設定基盤
//
// 【使用例】
// module appInsights './app-insights.bicep' = {
//   name: 'appInsightsDeployment'
//   params: {
//     appInsightsName: 'appi-ic-test-ai-prod'
//     location: 'japaneast'
//     tags: { Environment: 'Production' }
//   }
// }
//
// =============================================================================

@description('Application Insights名')
param appInsightsName string

@description('Log Analytics Workspace名')
param logAnalyticsWorkspaceName string

@description('デプロイ先リージョン')
param location string = resourceGroup().location

@description('リソースタグ')
param tags object = {}

@description('データ保持期間（日数）30, 60, 90, 120, 180, 270, 365, 550, 730')
@allowed([30, 60, 90, 120, 180, 270, 365, 550, 730])
param retentionInDays int = 30

@description('日次データ上限（GB）0=無制限')
param dailyDataCapInGB int = 1

// =============================================================================
// Log Analytics Workspace（Application Insightsのバックエンド）
// =============================================================================

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsWorkspaceName
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: retentionInDays
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    workspaceCapping: {
      dailyQuotaGb: dailyDataCapInGB
    }
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

// =============================================================================
// Application Insightsリソース
// =============================================================================

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalyticsWorkspace.id
    RetentionInDays: retentionInDays
    IngestionMode: 'LogAnalytics'
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'

    // サンプリング設定（コスト最適化）
    SamplingPercentage: 100 // 初期は100%、本番環境では10-20%推奨

    // 無効な要求フィルタリング（ノイズ削減）
    DisableIpMasking: false
  }
}

// =============================================================================
// アラートルール（サンプル）
// =============================================================================

// エラー率アラート（5分間で10件以上のエラー）
resource errorRateAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: '${appInsightsName}-error-rate-alert'
  location: 'global'
  tags: tags
  properties: {
    description: 'エラー率が閾値を超えました'
    severity: 2
    enabled: true
    scopes: [
      appInsights.id
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'HighErrorRate'
          metricName: 'exceptions/count'
          metricNamespace: 'microsoft.insights/components'
          operator: 'GreaterThan'
          threshold: 10
          timeAggregation: 'Count'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: [
      // アクショングループを追加する場合はここに記述
    ]
  }
}

// レスポンスタイムアラート（平均レスポンス3秒以上）
resource responseTimeAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: '${appInsightsName}-response-time-alert'
  location: 'global'
  tags: tags
  properties: {
    description: 'レスポンスタイムが閾値を超えました'
    severity: 3
    enabled: true
    scopes: [
      appInsights.id
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'HighResponseTime'
          metricName: 'requests/duration'
          metricNamespace: 'microsoft.insights/components'
          operator: 'GreaterThan'
          threshold: 3000
          timeAggregation: 'Average'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: []
  }
}

// =============================================================================
// 出力
// =============================================================================

@description('Application InsightsのリソースID')
output appInsightsId string = appInsights.id

@description('Application Insights名')
output appInsightsName string = appInsights.name

@description('Instrumentation Key')
output instrumentationKey string = appInsights.properties.InstrumentationKey

@description('Connection String（推奨）')
output connectionString string = appInsights.properties.ConnectionString

@description('Log Analytics Workspace ID')
output logAnalyticsWorkspaceId string = logAnalyticsWorkspace.id

@description('Log Analytics Workspace名')
output logAnalyticsWorkspaceName string = logAnalyticsWorkspace.name

@description('Log Analytics Customer ID（クエリ用）')
output logAnalyticsCustomerId string = logAnalyticsWorkspace.properties.customerId
