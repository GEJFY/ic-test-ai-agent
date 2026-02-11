# クライアントセットアップガイド（VBA/PowerShell）

## 概要

VBAおよびPowerShellクライアントから本システムへアクセスするためのセットアップ手順を説明します。

---

## VBAクライアント（Excel）

### 前提条件

- Microsoft Excel 2016以降
- インターネット接続
- VBAマクロが有効

### セットアップ手順

#### 1. VBAコードのインポート

1. Excelを開く
2. `Alt + F11` でVBAエディタを開く
3. `clients/vba/ExcelToJson.bas` をインポート
   - File → Import File → `ExcelToJson.bas`

#### 2. API設定の編集

VBAコード内のAPI設定を環境に合わせて変更：

```vba
' ExcelToJson.bas の先頭部分

' =============================================================================
' API設定（環境に合わせて変更）
' =============================================================================

' Azure環境
Const API_ENDPOINT As String = "https://<APIM_NAME>.azure-api.net/api/evaluate"
Const API_KEY_HEADER As String = "Ocp-Apim-Subscription-Key"
Const API_KEY As String = "<YOUR_APIM_SUBSCRIPTION_KEY>"

' AWS環境の場合
' Const API_ENDPOINT As String = "https://<API_ID>.execute-api.ap-northeast-1.amazonaws.com/prod/evaluate"
' Const API_KEY_HEADER As String = "X-Api-Key"
' Const API_KEY As String = "<YOUR_AWS_API_KEY>"

' GCP環境の場合
' Const API_ENDPOINT As String = "https://<APIGEE_ENDPOINT>/evaluate"
' Const API_KEY_HEADER As String = "X-Api-Key"
' Const API_KEY As String = "<YOUR_GCP_API_KEY>"
```

#### 3. Excelテンプレート準備

評価項目シートのフォーマット：

| 列 | 項目名 | 説明 |
|----|--------|------|
| A | ID | 項目番号（例: 001） |
| B | カテゴリ | 統制環境、リスク評価、等 |
| C | 統制名 | 統制の名称 |
| D | 評価基準 | 評価の基準 |
| E | 評価方法 | 評価の方法 |
| F | 証憑 | エビデンスファイル名 |
| G | ステータス | 実施中、完了、等 |

#### 4. マクロ実行

1. Excelで評価項目シートを開く
2. `Alt + F8` でマクロ一覧を表示
3. `EvaluateControls` を選択して実行

#### 5. 結果確認

- 処理が完了すると、新しいシート「評価結果」が作成されます
- 各項目の効果性評価と改善提案が記載されます

---

## PowerShellクライアント

### 前提条件

- PowerShell 5.1以降
- インターネット接続

### セットアップ手順

#### 1. スクリプトのダウンロード

```powershell
# プロジェクトルートから
cd clients/powershell
```

#### 2. API設定の編集

`CallCloudApi.ps1` または `CallCloudApiAsync.ps1` を環境に合わせて編集：

```powershell
# CallCloudApi.ps1 の先頭部分

# =============================================================================
# API設定（環境に合わせて変更）
# =============================================================================

# Azure環境
$apiEndpoint = "https://<APIM_NAME>.azure-api.net/api/evaluate"
$apiKeyHeader = "Ocp-Apim-Subscription-Key"
$apiKey = "<YOUR_APIM_SUBSCRIPTION_KEY>"

# AWS環境の場合
# $apiEndpoint = "https://<API_ID>.execute-api.ap-northeast-1.amazonaws.com/prod/evaluate"
# $apiKeyHeader = "X-Api-Key"
# $apiKey = "<YOUR_AWS_API_KEY>"

# GCP環境の場合
# $apiEndpoint = "https://<APIGEE_ENDPOINT>/evaluate"
# $apiKeyHeader = "X-Api-Key"
# $apiKey = "<YOUR_GCP_API_KEY>"
```

#### 3. JSONリクエストファイル準備

`request.json` のサンプル：

```json
{
  "items": [
    {
      "id": "001",
      "category": "統制環境",
      "control_name": "経営者の誠実性と倫理観",
      "evaluation_criteria": "行動規範が文書化され、全社員に周知されている",
      "evaluation_method": "行動規範の文書確認、全社員へのアンケート実施",
      "evidence": "倫理規定.pdf",
      "status": "実施中"
    }
  ]
}
```

#### 4. スクリプト実行

**同期処理**:
```powershell
.\CallCloudApi.ps1 -RequestFile .\request.json -OutputFile .\result.json
```

**非同期処理**:
```powershell
# ジョブ送信
.\CallCloudApiAsync.ps1 -Action Submit -RequestFile .\request.json

# ステータス確認
.\CallCloudApiAsync.ps1 -Action Status -JobId <JOB_ID>

# 結果取得
.\CallCloudApiAsync.ps1 -Action Results -JobId <JOB_ID> -OutputFile .\result.json
```

---

## トラブルシューティング

### VBA: "型が一致しません" エラー

**原因**: JSONパースエラー

**解決策**:
```vba
' デバッグ用にレスポンスを確認
Debug.Print httpReq.responseText
```

### VBA: "接続できません" エラー

**原因**: プロキシ設定、または証明書エラー

**解決策**:
```vba
' プロキシ設定
httpReq.setProxy 2, "proxy.example.com:8080"

' 証明書検証を無効化（開発環境のみ）
httpReq.setOption 2, 13056  ' SXH_SERVER_CERT_IGNORE_ALL_SERVER_ERRORS
```

### PowerShell: 証明書エラー

**解決策**:
```powershell
# 証明書検証を一時的に無効化（開発環境のみ）
[System.Net.ServicePointManager]::ServerCertificateValidationCallback = {$true}
```

### PowerShell: タイムアウトエラー

**解決策**:
```powershell
# タイムアウト時間を延長（秒）
$timeout = 300  # 5分

Invoke-RestMethod -Uri $apiEndpoint -Method POST `
  -Headers $headers -Body $body -ContentType "application/json" `
  -TimeoutSec $timeout
```

---

## 相関ID活用

クライアントから相関IDを送信することで、ログ追跡が容易になります：

**VBA**:
```vba
' SessionIDを相関IDとして使用
Dim correlationId As String
correlationId = Format(Now, "yyyymmdd") & "_" & CLng(Timer) & "_0001"

httpReq.setRequestHeader "X-Correlation-ID", correlationId
```

**PowerShell**:
```powershell
# 相関ID生成
$correlationId = "$(Get-Date -Format 'yyyyMMdd')_$([int](Get-Date -UFormat %s))_0001"

$headers = @{
    "$apiKeyHeader" = $apiKey
    "X-Correlation-ID" = $correlationId
    "Content-Type" = "application/json"
}
```

ログ追跡例（Azure）:
```kusto
traces
| where customDimensions.correlation_id == "20260209_1707484800_0001"
| order by timestamp asc
```

---

## セキュリティ注意事項

⚠️ **API Keyの管理**:
- VBAコード内にAPI Keyをハードコードしない（本番環境）
- 環境変数またはレジストリから取得することを推奨
- API Keyは定期的にローテーション

⚠️ **証明書検証**:
- 本番環境では証明書検証を必ず有効にする
- 自己署名証明書は使用しない

---

## 参考資料

- [Deployment Guide](../operations/DEPLOYMENT_GUIDE.md)
- [Troubleshooting Guide](../operations/TROUBLESHOOTING.md)
- [API Specification](../../SYSTEM_SPECIFICATION.md)
