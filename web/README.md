# 内部統制テスト評価AI - Webフロントエンド

PowerShell/VBA制限環境向けのWebベースインターフェースです。

## 概要

企業のセキュリティポリシーでPowerShellやVBA COMオブジェクトの使用が禁止されている場合に、
ブラウザ経由でAI評価機能を利用できます。

## 使用方法

### ローカルでの使用

1. `web/index.html` をブラウザで直接開く
2. または、簡易HTTPサーバーで配信:
   ```powershell
   cd web
   python -m http.server 8080
   ```
   ブラウザで `http://localhost:8080` にアクセス

### Azure Static Web Appsへのデプロイ

1. Azure CLIでログイン:
   ```bash
   az login
   ```

2. Static Web Appsを作成:
   ```bash
   az staticwebapp create \
     --name ic-test-web \
     --resource-group your-resource-group \
     --location "East Asia" \
     --source ./web \
     --app-location "/" \
     --output-location "/"
   ```

3. または、GitHub Actionsで自動デプロイ（推奨）

## ワークフロー

```
┌─────────────────────────────────────────────────────────────────┐
│ Excel                                                           │
│                                                                 │
│  1. ProcessForExport マクロを実行                               │
│     ↓                                                          │
│  export_YYYYMMDD_HHMMSS.json が生成される                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Webブラウザ (web/index.html)                                    │
│                                                                 │
│  2. JSONファイルをドラッグ&ドロップでアップロード               │
│  3. APIエンドポイントとキーを入力                               │
│  4. 「AI評価を開始」をクリック                                  │
│  5. 処理完了後、結果JSONをダウンロード                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Excel                                                           │
│                                                                 │
│  6. ImportResults マクロを実行                                  │
│  7. ダウンロードしたJSONファイルを選択                          │
│  8. 評価結果がExcelに反映される                                 │
└─────────────────────────────────────────────────────────────────┘
```

## ファイル構成

```
web/
├── index.html              # メインHTML
├── styles.css              # スタイルシート
├── app.js                  # JavaScript
├── staticwebapp.config.json # Azure Static Web Apps設定
└── README.md               # このファイル
```

## 設定

### setting.json (Excel側)

EXPORTモードを使用する場合:

```json
{
    "apiClient": "EXPORT"
}
```

### Webフロントエンド

- **APIエンドポイント**: Azure Functions/GCP/AWSのevaluateエンドポイントURL
- **APIキー**: Functions Key、Bearer Token、またはAPI Key
- **認証ヘッダー**: プロバイダーに応じて選択
  - Azure Functions: `x-functions-key`
  - GCP/Bearer Token: `Authorization`
  - AWS API Gateway: `x-api-key`

## セキュリティ

- APIキーはブラウザのローカルストレージに保存されません
- HTTPS通信を推奨
- CORS設定はAPI側で適切に構成してください

## ブラウザ対応

- Chrome 80+
- Firefox 75+
- Safari 13+
- Edge 80+

## トラブルシューティング

### CORSエラー

API側でCORSヘッダーを設定してください:

```python
# Azure Functions の場合
headers = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, x-functions-key, Authorization"
}
```

### 大きなファイルのアップロード

50MB以上のファイルはサポートされていません。
バッチサイズを小さくしてエクスポートしてください。
