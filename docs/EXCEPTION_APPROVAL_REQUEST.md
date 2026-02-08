# セキュリティ例外承認申請書

## 内部統制テスト評価AIシステム - クライアント実行権限

**申請日:** ____年__月__日
**申請者:** ________________
**所属部署:** ________________
**承認者:** ________________

---

## 1. 申請概要

### 1.1 申請目的

内部統制テスト評価AIシステム（ic-test-ai-agent）をクライアントPC上で実行するために必要な、VBA COMオブジェクトおよび/またはPowerShellコマンドの実行許可を申請します。

### 1.2 対象システム

| 項目 | 内容 |
|-----|------|
| システム名 | 内部統制テスト評価AIシステム |
| バージョン | 1.0 |
| 実行環境 | Microsoft Excel + VBA |
| 通信先 | Azure Functions API（HTTPS） |

### 1.3 申請する実行モード

以下から該当するモードを選択してください：

- [ ] **POWERSHELLモード**: PowerShellスクリプト実行権限を申請
- [ ] **VBAモード**: VBA COMオブジェクト使用権限を申請
- [ ] **EXPORTモード**: 最小限のVBA権限のみ申請（推奨）

---

## 2. VBAモード - 承認対象一覧

### 2.1 使用するCOMオブジェクト

| No. | COMオブジェクト | ProgID | 用途 | リスクレベル |
|-----|----------------|--------|------|-------------|
| 1 | FileSystemObject | `Scripting.FileSystemObject` | ファイル・フォルダ操作 | 中 |
| 2 | Stream | `ADODB.Stream` | UTF-8ファイル読み書き | 低 |
| 3 | ServerXMLHTTP | `MSXML2.ServerXMLHTTP.6.0` | HTTPリクエスト送信 | 高 |
| 4 | DOMDocument | `MSXML2.DOMDocument` | Base64エンコード | 低 |
| 5 | WScript.Shell | `WScript.Shell` | PowerShell実行 | 高 |

※ No.5 は POWERSHELLモード使用時のみ必要

---

### 2.2 詳細説明

#### 2.2.1 Scripting.FileSystemObject

**ProgID:** `Scripting.FileSystemObject`

**使用箇所（コード例）:**
```vba
Set fso = CreateObject("Scripting.FileSystemObject")

' フォルダ存在確認
If fso.FolderExists(evidencePath) Then
    Set folder = fso.GetFolder(evidencePath)
    For Each file In folder.Files
        ' ファイル情報を取得
    Next
End If
```

**用途:**
| 機能 | 用途 | 対象パス |
|-----|------|---------|
| `FolderExists` | 証跡フォルダの存在確認 | ユーザー指定パス |
| `FileExists` | ファイル存在確認 | ユーザー指定パス |
| `GetFolder` | フォルダ内ファイル一覧取得 | 証跡フォルダ |
| `GetFile` | ファイル情報取得 | 証跡ファイル |

**アクセス対象:**
- 読み取り: ユーザーが指定した証跡フォルダ
- 書き込み: `%TEMP%` フォルダ（一時ファイル）
- 書き込み: Excelファイルと同じフォルダ（エクスポートJSON）

**リスク軽減策:**
- ユーザーが明示的に指定したパスのみアクセス
- システムフォルダへのアクセスなし
- 書き込みは一時フォルダとExcelフォルダに限定

---

#### 2.2.2 ADODB.Stream

**ProgID:** `ADODB.Stream`

**使用箇所（コード例）:**
```vba
Set stream = CreateObject("ADODB.Stream")
With stream
    .Type = 2  ' adTypeText
    .Charset = "UTF-8"
    .Open
    .WriteText jsonText
    .SaveToFile filePath, 2  ' adSaveCreateOverWrite
    .Close
End With
```

**用途:**
| 機能 | 用途 |
|-----|------|
| テキスト書き込み | JSONファイルのUTF-8保存 |
| テキスト読み込み | APIレスポンスの読み取り |
| バイナリ読み込み | 証跡ファイルのBase64変換 |

**リスク軽減策:**
- ローカルファイル操作のみ（ネットワーク通信なし）
- 日本語文字の正確な処理に必要

---

#### 2.2.3 MSXML2.ServerXMLHTTP.6.0

**ProgID:** `MSXML2.ServerXMLHTTP.6.0`

**使用箇所（コード例）:**
```vba
Set http = CreateObject("MSXML2.ServerXMLHTTP.6.0")

' TLS 1.2 を有効化
http.setOption 2, 13056  ' SXH_OPTION_IGNORE_SERVER_SSL_CERT_ERROR_FLAGS

' リクエスト設定
http.Open "POST", endpoint, False
http.setRequestHeader "Content-Type", "application/json; charset=utf-8"
http.setRequestHeader "x-functions-key", apiKey  ' API認証

' 送信
http.send requestBody

' レスポンス取得
responseText = http.responseText
statusCode = http.Status
```

**用途:**
| 機能 | 用途 |
|-----|------|
| HTTP POST | Azure Functions APIへのリクエスト送信 |
| ヘッダー設定 | 認証情報（APIキー/Bearerトークン）の付与 |
| レスポンス取得 | AI評価結果の受信 |

**通信先ホワイトリスト:**

| No. | 通信先 | ポート | プロトコル | 用途 |
|-----|--------|--------|-----------|------|
| 1 | `*.azurewebsites.net` | 443 | HTTPS | Azure Functions API |
| 2 | `*.cloudfunctions.net` | 443 | HTTPS | GCP Cloud Functions（オプション） |
| 3 | `*.execute-api.amazonaws.com` | 443 | HTTPS | AWS API Gateway（オプション） |

**セキュリティ対策:**
- TLS 1.2以上での暗号化通信
- APIキーまたはAzure ADトークンによる認証
- 送信データは業務データのみ（個人情報は含まない前提）

**リスク軽減策:**
- 通信先をホワイトリストで制限
- 送信前にユーザー確認を表示（オプション）
- すべての通信をログに記録

---

#### 2.2.4 MSXML2.DOMDocument

**ProgID:** `MSXML2.DOMDocument`

**使用箇所（コード例）:**
```vba
Set xmlDoc = CreateObject("MSXML2.DOMDocument")
Set node = xmlDoc.createElement("base64")
node.DataType = "bin.base64"
node.nodeTypedValue = fileBytes  ' バイナリデータ
base64String = node.Text         ' Base64文字列
```

**用途:**
| 機能 | 用途 |
|-----|------|
| Base64エンコード | 証跡ファイルのテキスト変換 |
| XMLノード操作 | データ型変換 |

**リスク軽減策:**
- メモリ内でのデータ変換のみ
- 外部通信なし
- ファイルシステムへの直接アクセスなし

---

#### 2.2.5 WScript.Shell（POWERSHELLモードのみ）

**ProgID:** `WScript.Shell`

**使用箇所（コード例）:**
```vba
Set wsh = CreateObject("WScript.Shell")

' PowerShellスクリプトを実行
psCommand = "powershell.exe -ExecutionPolicy Bypass -File """ & scriptPath & """ " & arguments

' 同期実行（ウィンドウ非表示）
exitCode = wsh.Run(psCommand, 0, True)
```

**用途:**
| 機能 | 用途 |
|-----|------|
| 子プロセス起動 | PowerShellスクリプトの実行 |
| 終了コード取得 | 処理結果の確認 |

**実行されるスクリプト:**
- `CallCloudApi.ps1` - API呼び出しスクリプト（署名付き可能）

**リスク軽減策:**
- 実行するスクリプトは固定（CallCloudApi.ps1のみ）
- スクリプトはExcelファイルと同じフォルダに配置
- 署名付きスクリプトへの変更が可能

---

## 3. POWERSHELLモード - 承認対象一覧

### 3.1 使用するコマンドレット

| No. | コマンドレット/機能 | 用途 | リスクレベル |
|-----|-------------------|------|-------------|
| 1 | `Invoke-WebRequest` | HTTPリクエスト送信 | 高 |
| 2 | `Invoke-RestMethod` | REST API呼び出し | 高 |
| 3 | `Start-Job` / `Wait-Job` | 並列処理 | 低 |
| 4 | `System.Net.HttpListener` | OAuth コールバック | 中 |
| 5 | `Start-Process` | ブラウザ起動 | 中 |
| 6 | `ConvertTo-Json` / `ConvertFrom-Json` | JSON処理 | 低 |
| 7 | `dsregcmd /status` | Azure AD状態確認 | 低 |

### 3.2 実行ポリシー

**申請する実行ポリシー:**
- [ ] `Bypass` - スクリプト単位で許可（推奨）
- [ ] `RemoteSigned` - 署名付きスクリプトのみ許可
- [ ] `AllSigned` - すべて署名必須

**推奨構成:**
```powershell
# スクリプト実行時のみBypassを適用（システム設定は変更しない）
powershell.exe -ExecutionPolicy Bypass -File "CallCloudApi.ps1"
```

---

### 3.3 詳細説明

#### 3.3.1 Invoke-WebRequest / Invoke-RestMethod

**使用箇所（コード例）:**
```powershell
# Azure Functions API呼び出し
$response = Invoke-WebRequest -Uri $Endpoint `
    -Method Post `
    -Headers $Headers `
    -Body $bodyBytes `
    -ContentType "application/json; charset=utf-8" `
    -UseBasicParsing `
    -TimeoutSec 600

# Azure AD トークン取得
$tokenResponse = Invoke-RestMethod -Uri $tokenUrl `
    -Method Post `
    -Body $tokenBody
```

**通信先ホワイトリスト:**

| No. | 通信先 | ポート | 用途 |
|-----|--------|--------|------|
| 1 | `*.azurewebsites.net` | 443 | Azure Functions API |
| 2 | `login.microsoftonline.com` | 443 | Azure AD 認証 |
| 3 | `*.cloudfunctions.net` | 443 | GCP（オプション） |
| 4 | `*.execute-api.amazonaws.com` | 443 | AWS（オプション） |

**セキュリティ対策:**
- TLS 1.2以上で暗号化
- Azure AD OAuth 2.0 認証（本番環境推奨）
- APIキー認証（開発環境）

---

#### 3.3.2 Start-Job / Wait-Job / Receive-Job

**使用箇所（コード例）:**
```powershell
# 並列API呼び出し
foreach ($item in $preparedItems) {
    $job = Start-Job -ScriptBlock {
        param($ItemJson, $Endpoint, $Headers, $TimeoutSec)
        # API呼び出し処理
    } -ArgumentList $itemJson, $Endpoint, $headers, $TimeoutSec
    $jobs += $job
}

# 完了待機
$jobs | Wait-Job -Timeout 660 | Out-Null

# 結果取得
foreach ($job in $jobs) {
    $result = Receive-Job -Job $job
}
```

**用途:**
- 複数のテスト項目を並列処理
- 処理時間の短縮

**リスク軽減策:**
- ローカルでのバックグラウンドジョブのみ
- 外部プロセス起動なし

---

#### 3.3.3 System.Net.HttpListener

**使用箇所（コード例）:**
```powershell
# OAuth 2.0 コールバック受信用ローカルサーバー
$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://localhost:$port/")
$listener.Start()

# 認証コード受信待機
$context = $listener.GetContext()
$authCode = ... # クエリパラメータから抽出
$listener.Stop()
```

**用途:**
- Azure AD OAuth 2.0 Authorization Code Flow
- ブラウザからの認証コールバック受信

**バインドアドレス:**
- `localhost` (127.0.0.1) のみ
- ポート範囲: 8400-8499（ランダム選択）

**リスク軽減策:**
- ループバックアドレスのみ使用
- 外部からのアクセス不可
- 一時的な使用（認証完了後即座に停止）

---

#### 3.3.4 Start-Process

**使用箇所（コード例）:**
```powershell
# Azure AD ログインページをブラウザで開く
$authUrl = "https://login.microsoftonline.com/$TenantId/oauth2/v2.0/authorize?..."
Start-Process $authUrl
```

**用途:**
- Azure AD ログインUIの表示
- ユーザー認証

**起動対象:**
- デフォルトブラウザ
- 起動URL: `https://login.microsoftonline.com/*` のみ

**リスク軽減策:**
- Microsoft公式認証エンドポイントのみ
- ユーザーによる明示的なログイン操作

---

#### 3.3.5 dsregcmd

**使用箇所（コード例）:**
```powershell
# Azure AD 参加状態の確認
$dsregOutput = dsregcmd /status
if ($dsregOutput -match "AzureAdJoined\s*:\s*YES") {
    # Azure AD参加デバイス
}
```

**用途:**
- デバイスのAzure AD参加状態確認
- UPN（ユーザープリンシパル名）取得

**リスク軽減策:**
- 読み取り専用操作
- システム変更なし

---

## 4. EXPORTモード - 承認対象一覧（最小権限）

### 4.1 使用するCOMオブジェクト

| No. | COMオブジェクト | ProgID | 用途 |
|-----|----------------|--------|------|
| 1 | FileSystemObject | `Scripting.FileSystemObject` | フォルダ確認、ファイル一覧 |
| 2 | Stream | `ADODB.Stream` | UTF-8 JSONファイル保存 |

### 4.2 特徴

- **外部通信なし**: HTTPリクエストを行うCOMオブジェクトは使用しない
- **手動ファイル交換**: JSONファイルをWebブラウザで手動アップロード
- **最高セキュリティ環境向け**: PowerShell/VBA HTTP通信が完全禁止の環境

---

## 5. リスク評価

### 5.1 リスクマトリクス

| リスク | 発生可能性 | 影響度 | リスクレベル | 軽減策 |
|-------|-----------|--------|-------------|--------|
| 不正なAPI呼び出し | 低 | 中 | 中 | APIキー/Azure AD認証 |
| データ漏洩 | 低 | 高 | 中 | HTTPS暗号化、アクセス制御 |
| マルウェア感染経由の悪用 | 低 | 高 | 中 | 通信先ホワイトリスト |
| 意図しないファイルアクセス | 低 | 低 | 低 | パス制限、ユーザー確認 |

### 5.2 セキュリティ対策一覧

| 対策 | 実装状況 | 説明 |
|-----|---------|------|
| HTTPS通信 | ✅ 実装済み | TLS 1.2以上 |
| API認証 | ✅ 実装済み | APIキー / Azure AD |
| 通信先制限 | ✅ 実装済み | ホワイトリスト |
| ログ記録 | ✅ 実装済み | 全操作をログ出力 |
| エラーハンドリング | ✅ 実装済み | 例外時の安全な終了 |
| コード署名 | ⚪ オプション | PowerShellスクリプト署名 |

---

## 6. 運用管理

### 6.1 アクセス権限管理

| 役割 | 権限 | 人数制限 |
|-----|------|---------|
| システム管理者 | APIキー管理、設定変更 | 2-3名 |
| 監査担当者 | マクロ実行、結果閲覧 | 制限なし |
| 閲覧者 | 結果閲覧のみ | 制限なし |

### 6.2 監査ログ

**ログ出力先:** `%TEMP%\ExcelToJson_Log.txt`

**ログ内容:**
- 処理開始/終了時刻
- API呼び出し（エンドポイント、ステータス）
- エラー発生時の詳細
- 処理件数

**ログ保持期間:** 90日（推奨）

### 6.3 定期レビュー

| 項目 | 頻度 | 担当 |
|-----|------|------|
| APIキーローテーション | 90日 | システム管理者 |
| アクセスログレビュー | 月次 | セキュリティ担当 |
| 権限棚卸 | 四半期 | 監査部門 |

---

## 7. 承認欄

### 7.1 申請者

| 項目 | 内容 |
|-----|------|
| 氏名 | |
| 所属 | |
| 連絡先 | |
| 申請日 | 年　　月　　日 |

**申請者署名:** ____________________

### 7.2 情報セキュリティ担当

| 項目 | 内容 |
|-----|------|
| 確認事項 | □ リスク評価を確認した |
| | □ 軽減策が適切であることを確認した |
| | □ 通信先ホワイトリストを確認した |
| コメント | |
| 確認日 | 年　　月　　日 |

**確認者署名:** ____________________

### 7.3 IT部門責任者

| 項目 | 内容 |
|-----|------|
| 確認事項 | □ 技術的な実現可能性を確認した |
| | □ 既存システムへの影響がないことを確認した |
| コメント | |
| 承認日 | 年　　月　　日 |

**承認者署名:** ____________________

### 7.4 最終承認者

| 項目 | 内容 |
|-----|------|
| 承認モード | □ POWERSHELL □ VBA □ EXPORT |
| 有効期間 | 年　　月　　日 ～ 年　　月　　日 |
| 条件 | |
| 承認日 | 年　　月　　日 |

**最終承認者署名:** ____________________

---

## 付録A: 設定ファイル例

### A.1 setting.json（VBAモード）

```json
{
    "apiClient": "VBA",
    "asyncMode": true,
    "batchSize": 10,
    "api": {
        "provider": "AZURE",
        "endpoint": "https://your-function-app.azurewebsites.net/api/evaluate",
        "authType": "functionsKey",
        "apiKey": "your-api-key",
        "authHeader": "x-functions-key"
    }
}
```

### A.2 setting.json（POWERSHELLモード + Azure AD認証）

```json
{
    "apiClient": "POWERSHELL",
    "asyncMode": true,
    "batchSize": 10,
    "api": {
        "provider": "AZURE",
        "endpoint": "https://your-function-app.azurewebsites.net/api/evaluate",
        "authType": "azureAd"
    },
    "azureAd": {
        "tenantId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "clientId": "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy",
        "scope": "api://yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy/user_impersonation openid offline_access"
    }
}
```

### A.3 setting.json（EXPORTモード）

```json
{
    "apiClient": "EXPORT",
    "batchSize": 10
}
```

---

## 付録B: 通信フロー図

### B.1 VBAモード

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Excel     │     │   VBA       │     │   Azure     │
│   ユーザー  │     │   マクロ    │     │   Functions │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │
       │ 1. マクロ実行     │                   │
       │──────────────────▶│                   │
       │                   │                   │
       │                   │ 2. JSON生成       │
       │                   │───────┐           │
       │                   │       │           │
       │                   │◀──────┘           │
       │                   │                   │
       │                   │ 3. HTTPS POST     │
       │                   │──────────────────▶│
       │                   │   (x-functions-key)│
       │                   │                   │
       │                   │ 4. JSON Response  │
       │                   │◀──────────────────│
       │                   │                   │
       │ 5. 結果書き込み   │                   │
       │◀──────────────────│                   │
       │                   │                   │
```

### B.2 POWERSHELLモード + Azure AD認証

```
┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
│  Excel  │  │  VBA    │  │PowerShell│  │ Azure AD│  │ Azure   │
│         │  │         │  │         │  │         │  │Functions│
└─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘
     │            │            │            │            │
     │ 1. 実行    │            │            │            │
     │───────────▶│            │            │            │
     │            │ 2. PS起動  │            │            │
     │            │───────────▶│            │            │
     │            │            │ 3. トークン │            │
     │            │            │   要求      │            │
     │            │            │───────────▶│            │
     │            │            │ 4. ブラウザ │            │
     │            │            │   認証      │            │
     │            │            │◀───────────│            │
     │            │            │ 5. API呼び出し           │
     │            │            │───────────────────────▶│
     │            │            │   (Bearer token)        │
     │            │            │ 6. Response              │
     │            │            │◀───────────────────────│
     │            │ 7. 結果    │            │            │
     │            │◀───────────│            │            │
     │ 8. 書込み  │            │            │            │
     │◀───────────│            │            │            │
```

---

## 付録C: チェックリスト

### C.1 申請前チェック

- [ ] 使用するモード（POWERSHELL/VBA/EXPORT）を決定した
- [ ] 必要なCOMオブジェクト/コマンドレットを特定した
- [ ] 通信先ホワイトリストを確認した
- [ ] リスク評価を実施した
- [ ] 軽減策を文書化した

### C.2 承認後チェック

- [ ] 設定ファイル（setting.json）を正しく配置した
- [ ] APIエンドポイントの疎通確認を実施した
- [ ] テスト実行で正常動作を確認した
- [ ] ログ出力が正しく行われることを確認した
- [ ] 運用手順書を作成した

---

**改訂履歴**

| バージョン | 日付 | 変更内容 |
|-----------|------|---------|
| 1.0 | 2025年1月 | 初版作成 |
