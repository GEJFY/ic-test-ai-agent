# Azure Functions セットアップガイド

内部統制テスト評価APIをAzure Functionsにデプロイするための詳細ガイドです。

## 目次
1. [前提条件](#前提条件)
2. [ローカル開発環境のセットアップ](#ローカル開発環境のセットアップ)
3. [ローカルでの動作確認](#ローカルでの動作確認)
4. [Azureリソースの作成](#azureリソースの作成)
5. [Azure へのデプロイ](#azure-へのデプロイ)
6. [APIキーの取得と設定](#apiキーの取得と設定)
7. [動作確認](#動作確認)
8. [トラブルシューティング](#トラブルシューティング)

---

## 前提条件

### 必要なソフトウェア

1. **Python 3.9以上**（推奨: 3.11）
   ```powershell
   python --version
   ```

2. **Azure Functions Core Tools v4**
   ```powershell
   # wingetでインストール
   winget install Microsoft.Azure.FunctionsCoreTools

   # または npm でインストール
   npm install -g azure-functions-core-tools@4 --unsafe-perm true

   # インストール確認
   func --version
   ```

3. **Azure CLI**
   ```powershell
   # wingetでインストール
   winget install Microsoft.AzureCLI

   # インストール確認
   az --version
   ```

4. **VS Code** + **Azure Functions 拡張機能**（オプション、GUI操作用）

---

## ローカル開発環境のセットアップ

### 1. 仮想環境の作成

```powershell
cd azure-functions

# 仮想環境作成
python -m venv .venv

# 仮想環境有効化
.\.venv\Scripts\Activate.ps1

# 依存関係インストール
pip install -r requirements.txt
```

### 2. ローカル設定ファイルの確認

`local.settings.json` が以下の内容であることを確認:

```json
{
    "IsEncrypted": false,
    "Values": {
        "AzureWebJobsStorage": "UseDevelopmentStorage=true",
        "FUNCTIONS_WORKER_RUNTIME": "python"
    }
}
```

> **注意**: このファイルはローカル開発用です。Gitにコミットしないでください。

---

## ローカルでの動作確認

### 1. Azure Functions ローカル実行

```powershell
# azure-functions フォルダ内で実行
func start
```

成功すると以下のように表示されます:

```
Functions:
    evaluate: [POST] http://localhost:7071/api/evaluate
    health: [GET] http://localhost:7071/api/health
```

### 2. ヘルスチェック

```powershell
# 別のターミナルで実行
Invoke-RestMethod -Uri "http://localhost:7071/api/health" -Method GET
```

期待されるレスポンス:
```json
{
    "status": "healthy",
    "version": "1.0.0-mock"
}
```

### 3. 評価API のテスト

```powershell
$testBody = @'
[
    {
        "ID": "IC-001",
        "ControlDescription": "アクセス権限の承認プロセス",
        "TestProcedure": "承認記録を確認する",
        "EvidenceLink": "C:\\Evidence\\IC-001",
        "EvidenceFiles": [
            {
                "fileName": "approval.pdf",
                "extension": ".pdf",
                "mimeType": "application/pdf",
                "base64": "JVBERi0x..."
            }
        ]
    }
]
'@

Invoke-RestMethod -Uri "http://localhost:7071/api/evaluate" -Method POST -Body $testBody -ContentType "application/json"
```

---

## Azureリソースの作成

### 1. Azure にログイン

```powershell
az login
```

ブラウザが開くので、Azureアカウントでログインします。

### 2. サブスクリプションの確認・設定

```powershell
# 利用可能なサブスクリプション一覧
az account list --output table

# 使用するサブスクリプションを設定
az account set --subscription "<サブスクリプション名またはID>"
```

### 3. リソースグループの作成

```powershell
$resourceGroup = "rg-ic-test-evaluation"
$location = "japaneast"

az group create --name $resourceGroup --location $location
```

### 4. ストレージアカウントの作成

```powershell
$storageAccount = "stictestevaluation"  # 小文字英数字のみ、3-24文字

az storage account create `
    --name $storageAccount `
    --location $location `
    --resource-group $resourceGroup `
    --sku Standard_LRS
```

### 5. Function App の作成

```powershell
$functionApp = "func-ic-test-evaluation"  # グローバルで一意の名前

az functionapp create `
    --resource-group $resourceGroup `
    --consumption-plan-location $location `
    --runtime python `
    --runtime-version 3.11 `
    --functions-version 4 `
    --name $functionApp `
    --storage-account $storageAccount `
    --os-type Linux
```

---

## Azure へのデプロイ

### 方法1: Azure Functions Core Tools を使用（推奨）

```powershell
# azure-functions フォルダ内で実行
func azure functionapp publish $functionApp
```

デプロイ成功時の出力例:
```
Deployment successful.
Remote build succeeded!
Syncing triggers...
Functions in func-ic-test-evaluation:
    evaluate - [httpTrigger]
        Invoke url: https://func-ic-test-evaluation.azurewebsites.net/api/evaluate
    health - [httpTrigger]
        Invoke url: https://func-ic-test-evaluation.azurewebsites.net/api/health
```

### 方法2: VS Code から GUI でデプロイ

1. VS Code で azure-functions フォルダを開く
2. Azure 拡張機能アイコンをクリック
3. FUNCTIONS セクションで「Deploy to Function App...」を選択
4. 作成した Function App を選択

---

## APIキーの取得と設定

### 1. Function キーの取得

```powershell
# Function キー一覧を取得
az functionapp function keys list `
    --resource-group $resourceGroup `
    --name $functionApp `
    --function-name evaluate
```

または Azure Portal で取得:

1. Azure Portal (https://portal.azure.com) にアクセス
2. Function App を開く
3. 左メニュー「関数」→「evaluate」を選択
4. 「関数キー」タブを開く
5. 「default」キーをコピー

### 2. setting.json への設定

取得したキーを `setting.json` に設定:

```json
{
    "api": {
        "provider": "AZURE",
        "endpoint": "https://func-ic-test-evaluation.azurewebsites.net/api/evaluate",
        "apiKey": "ここに取得したキーを貼り付け",
        "authHeader": "x-functions-key"
    }
}
```

---

## 動作確認

### PowerShell から直接テスト

```powershell
$endpoint = "https://func-ic-test-evaluation.azurewebsites.net/api/evaluate"
$apiKey = "your-function-key"

$headers = @{
    "Content-Type" = "application/json"
    "x-functions-key" = $apiKey
}

$testBody = @'
[
    {
        "ID": "IC-001",
        "ControlDescription": "テスト",
        "TestProcedure": "確認する",
        "EvidenceLink": "",
        "EvidenceFiles": []
    }
]
'@

Invoke-RestMethod -Uri $endpoint -Method POST -Headers $headers -Body $testBody
```

### Excel VBA からテスト

1. Excel ファイルを開く
2. テストデータを入力
3. マクロ `ProcessWithApi` を実行
4. 結果が該当列に書き込まれることを確認

---

## トラブルシューティング

### 問題: `func start` でエラー

**症状**: `No job functions found` と表示される

**解決策**:
```powershell
# function_app.py が正しい場所にあるか確認
ls function_app.py

# 仮想環境が有効か確認
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 問題: デプロイ後に 401 Unauthorized

**症状**: APIキーが無効

**解決策**:
1. Azure Portal で正しいキーを再取得
2. `setting.json` を更新
3. `authHeader` が `x-functions-key` であることを確認

### 問題: デプロイ後に 500 Internal Server Error

**症状**: サーバーエラー

**解決策**:
```powershell
# ログストリームを確認
func azure functionapp logstream $functionApp
```

または Azure Portal で:
1. Function App → 「ログストリーム」
2. エラーメッセージを確認

### 問題: 日本語が文字化け

**症状**: レスポンスの日本語が正しく表示されない

**解決策**:
- `ensure_ascii=False` がコードに含まれていることを確認
- PowerShell側で UTF-8 エンコーディングを使用

---

## 次のステップ

モック実装が動作確認できたら、以下の拡張を検討:

1. **AI統合**: Azure OpenAI / Claude API との連携
2. **OCR処理**: Azure AI Vision でのドキュメント解析
3. **ログ記録**: Application Insights での監視
4. **認証強化**: Azure AD 認証の追加

---

## リソースの削除（不要になった場合）

```powershell
# リソースグループごと削除（すべてのリソースが削除されます）
az group delete --name $resourceGroup --yes --no-wait
```

---

## 関連ドキュメント

- [Azure Functions Python 開発者ガイド](https://learn.microsoft.com/ja-jp/azure/azure-functions/functions-reference-python)
- [Azure Functions Core Tools リファレンス](https://learn.microsoft.com/ja-jp/azure/azure-functions/functions-run-local)
- [Azure CLI ドキュメント](https://learn.microsoft.com/ja-jp/cli/azure/)
