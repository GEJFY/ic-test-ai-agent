# クライアント移行ガイド - API Gateway層対応

## 概要

Phase 2で導入されたAPI Gateway層（APIM/API Gateway/Apigee）に対応するため、VBA/PowerShellクライアントコードの修正が必要です。

### 変更点サマリー

| 項目 | 変更前（Phase 1） | 変更後（Phase 2） |
|-----|-----------------|-----------------|
| **エンドポイント** | Azure Functions/Lambda/Cloud Functions直接 | APIM/API Gateway経由 |
| **認証ヘッダー** | `x-functions-key` (Azure) | `Ocp-Apim-Subscription-Key` (Azure APIM)<br>`X-Api-Key` (AWS API Gateway) |
| **相関ID** | なし | `X-Correlation-ID` ヘッダー追加 |

## 1. Azure APIM対応

### setting.json の修正

```json
{
  "api": {
    "provider": "AZURE",
    "endpoint": "https://apim-ic-test-ai-prod-XXXXX.azure-api.net/api/evaluate",
    "apiKey": "<APIM Subscription Key>",
    "authHeader": "Ocp-Apim-Subscription-Key",
    "authType": "functionsKey"
  }
}
```

### CallCloudApi.ps1 の修正

**修正箇所: 738-758行目（ヘッダー設定）**

```powershell
# Set headers by provider and auth type
$headers = @{
    "Content-Type" = "application/json; charset=utf-8"
}

# === 追加: 相関IDヘッダー ===
if ($CorrelationId) {
    $headers["X-Correlation-ID"] = $CorrelationId
}

# Handle Azure AD authentication
if ($AuthType.ToLower() -eq "azuread") {
    # Azure AD認証の場合
    $accessToken = Get-AzureAdToken -TenantId $TenantId -ClientId $ClientId -Scope $Scope
    if ($null -ne $accessToken) {
        $headers["Authorization"] = "Bearer $accessToken"
    } else {
        throw "Azure AD認証に失敗しました。"
    }
} else {
    # === 変更: Azure APIM対応 ===
    if ($Provider.ToUpper() -eq "AZURE") {
        if ($AuthHeader -eq "") {
            # デフォルトはAPIM Subscription Key
            $AuthHeader = "Ocp-Apim-Subscription-Key"
        }
        if ($ApiKey -ne "") {
            $headers[$AuthHeader] = $ApiKey
        }
    } elseif ($Provider.ToUpper() -eq "GCP") {
        if ($ApiKey -ne "") {
            $headers["X-Api-Key"] = $ApiKey
        }
    } elseif ($Provider.ToUpper() -eq "AWS") {
        if ($ApiKey -ne "") {
            $headers["X-Api-Key"] = $ApiKey
        }
    }
}
```

### パラメータ追加

**修正箇所: 6-40行目（パラメータ定義）**

```powershell
param(
    # ... 既存パラメータ ...

    # === 追加: 相関IDパラメータ ===
    [Parameter(Mandatory=$false)]
    [string]$CorrelationId = ""
)
```

### ExcelToJson.bas の修正

**修正箇所: 870-895行目（PowerShell呼び出し）**

```vb
' 同期モード: CallCloudApi.ps1 を呼び出し
psCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File " & _
            Chr(34) & psScriptPath & Chr(34) & " " & _
            "-JsonFilePath " & Chr(34) & inputJsonPath & Chr(34) & " " & _
            "-Endpoint " & Chr(34) & config.ApiEndpoint & Chr(34) & " " & _
            "-ApiKey " & Chr(34) & config.ApiKey & Chr(34) & " " & _
            "-OutputFilePath " & Chr(34) & outputJsonPath & Chr(34) & " " & _
            "-Provider " & Chr(34) & config.ApiProvider & Chr(34) & " " & _
            "-AuthHeader " & Chr(34) & config.ApiAuthHeader & Chr(34) & " " & _
            "-TimeoutSec 600 " & _
            "-AuthType " & Chr(34) & config.ApiAuthType & Chr(34) & " " & _
            "-TenantId " & Chr(34) & config.AzureAdTenantId & Chr(34) & " " & _
            "-ClientId " & Chr(34) & config.AzureAdClientId & Chr(34) & " " & _
            "-Scope " & Chr(34) & config.AzureAdScope & Chr(34) & " " & _
            "-CorrelationId " & Chr(34) & m_SessionId & Chr(34)  ' === 追加: 相関ID ===
```

## 2. AWS API Gateway対応

### setting.json の修正

```json
{
  "api": {
    "provider": "AWS",
    "endpoint": "https://XXXXX.execute-api.ap-northeast-1.amazonaws.com/prod/evaluate",
    "apiKey": "<API Gateway API Key>",
    "authHeader": "X-Api-Key",
    "authType": "functionsKey"
  }
}
```

### CallCloudApi.ps1 の修正

**AWS用ヘッダー設定（上記Azure修正に含まれています）**

```powershell
} elseif ($Provider.ToUpper() -eq "AWS") {
    if ($ApiKey -ne "") {
        $headers["X-Api-Key"] = $ApiKey
    }
}
```

## 3. GCP Cloud Functions対応

### Apigee無効時（推奨）

Apigeeは高コストのため、Cloud Functions直接アクセスを推奨します。

```json
{
  "api": {
    "provider": "GCP",
    "endpoint": "https://asia-northeast1-PROJECT_ID.cloudfunctions.net/ic-test-ai-prod-evaluate/evaluate",
    "apiKey": "",
    "authHeader": "",
    "authType": "functionsKey"
  }
}
```

### Apigee有効時

```json
{
  "api": {
    "provider": "GCP",
    "endpoint": "https://ic-test-ai-api.example.com/api/evaluate",
    "apiKey": "<Apigee API Key>",
    "authHeader": "X-Api-Key",
    "authType": "functionsKey"
  }
}
```

## 4. 修正後の動作確認

### 1. setting.json 更新

```powershell
# デプロイ後に取得したエンドポイントとAPI Keyを設定

# Azure
terraform output -raw api_gateway_url  # または az deployment group show
terraform output -raw api_key

# AWS
terraform output -raw api_gateway_endpoint
terraform output -raw api_key

# GCP
terraform output -raw cloud_functions_endpoint
# または terraform output -raw apigee_endpoint（Apigee有効時）
```

### 2. PowerShell単体テスト

```powershell
# テストJSONファイル作成
$testJson = @"
[
    {
        "ID": "001",
        "controlObjective": "テスト目的",
        "testProcedure": "テスト手続き",
        "acceptanceCriteria": "受入基準"
    }
]
"@ | Out-File -FilePath "test-input.json" -Encoding UTF8

# API呼び出し
.\CallCloudApi.ps1 `
    -JsonFilePath "test-input.json" `
    -Endpoint "<API Gateway Endpoint URL>" `
    -ApiKey "<API Key>" `
    -OutputFilePath "test-output.json" `
    -Provider "AZURE" `
    -AuthHeader "Ocp-Apim-Subscription-Key" `
    -CorrelationId "test-$(Get-Date -Format 'yyyyMMdd-HHmmss')"

# 結果確認
Get-Content "test-output.json" | ConvertFrom-Json | Format-List
```

### 3. Excel VBAテスト

1. `setting.json` を更新
2. Excelを開く
3. `ProcessWithApi` マクロを実行
4. ログファイルで相関ID確認: `%TEMP%\ExcelToJson_Log.txt`

### 4. 相関IDフロー確認

#### Azure (Application Insights)

```bash
# Log Analyticsでクエリ
az monitor log-analytics query \
  --workspace <Workspace ID> \
  --analytics-query "traces | where customDimensions.correlation_id == '<相関ID>' | project timestamp, message"
```

#### AWS (CloudWatch Logs Insights)

```bash
# CloudWatch Logs Insightsでクエリ
fields @timestamp, @message, correlation_id
| filter correlation_id like /<相関ID>/
| sort @timestamp asc
```

#### GCP (Cloud Logging)

```bash
# Cloud Loggingでクエリ
gcloud logging read "resource.type=cloud_function \
  jsonPayload.correlation_id=<相関ID>" \
  --limit 50 \
  --format json
```

## 5. トラブルシューティング

### 401 Unauthorized

**原因**: API Keyが正しく設定されていない

**対処**:
1. `setting.json`の`apiKey`を確認
2. Azure: APIM Subscription Key
3. AWS: API Gateway API Key
4. ヘッダー名が正しいか確認（`authHeader`）

### 403 Forbidden

**原因**: IPアドレス制限またはレート制限

**対処**:
1. APIM/API Gatewayのネットワーク設定を確認
2. Usage Planのレート制限を確認
3. しばらく待ってから再試行

### 相関IDがログに表示されない

**原因**: `X-Correlation-ID` ヘッダーが送信されていない

**対処**:
1. CallCloudApi.ps1の修正が完了しているか確認
2. `-CorrelationId` パラメータが渡されているか確認
3. VBAの `psCommand` で `-CorrelationId` が含まれているか確認

## 6. 後方互換性

Phase 1の直接アクセスも引き続きサポートされます：

```json
{
  "api": {
    "provider": "AZURE",
    "endpoint": "https://func-ic-test-ai-prod-XXXXX.azurewebsites.net/api/evaluate",
    "apiKey": "<Function App Key>",
    "authHeader": "x-functions-key",
    "authType": "functionsKey"
  }
}
```

ただし、本番環境ではAPI Gateway層経由を推奨します（セキュリティ・監視・レート制限）。

## 7. まとめ

### 必須修正

- ✅ `setting.json`: エンドポイントURL、API Key、authHeader更新
- ✅ `CallCloudApi.ps1`: 相関IDヘッダー追加
- ✅ `ExcelToJson.bas`: 相関IDパラメータ追加

### 推奨修正

- ⭐ Azure AD認証からAPIM Subscription Keyへの移行（シンプル化）
- ⭐ 相関IDによるログ追跡の活用（トラブルシューティング効率化）

### 次のステップ

Phase 2完了後、Phase 3で監視最適化を実施し、Application Insights/X-Ray/Cloud Loggingの詳細トレースを活用します。
