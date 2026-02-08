# Azure Functions デプロイガイド

内部統制テスト評価AIシステムのAzure Functions版デプロイ手順です。

## 目次

1. [必要なAzureリソース](#必要なazureリソース)
2. [環境変数設定](#環境変数設定)
3. [ローカル開発](#ローカル開発)
4. [デプロイ手順](#デプロイ手順)
5. [非同期処理（オプション）](#非同期処理オプション)
6. [トラブルシューティング](#トラブルシューティング)

---

## 必要なAzureリソース

### 必須リソース

| サービス | 用途 | SKU/プラン |
|---------|------|-----------|
| Azure Functions | APIホスティング | Consumption (Y1) または Premium |
| Storage Account | Functions用ストレージ | Standard LRS |
| Azure AI Foundry または Azure OpenAI | LLM処理 | GPT-4o |
| Document Intelligence | OCR処理（オプション） | S0 |

### 非同期処理用（オプション）

| サービス | 用途 | 備考 |
|---------|------|------|
| Table Storage | ジョブ状態管理 | Storage Account に含まれる |
| Queue Storage | ジョブキュー | Storage Account に含まれる |
| Blob Storage | 大容量ファイル | 証跡ファイル一時保存 |

---

## 環境変数設定

### 必須設定

```bash
# LLM設定（Azure AI Foundry推奨）
LLM_PROVIDER=AZURE_FOUNDRY
AZURE_FOUNDRY_ENDPOINT=https://your-project.region.models.ai.azure.com
AZURE_FOUNDRY_API_KEY=your-foundry-api-key
AZURE_FOUNDRY_MODEL=gpt-4o

# または Azure OpenAI Service
# LLM_PROVIDER=AZURE
# AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
# AZURE_OPENAI_API_KEY=your-azure-openai-api-key
# AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
```

### OCR設定（オプション）

```bash
# Azure Document Intelligence
OCR_PROVIDER=AZURE
AZURE_DI_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
AZURE_DI_KEY=your-document-intelligence-key

# または OCR不要の場合
# OCR_PROVIDER=NONE
```

### 非同期処理設定（オプション）

```bash
# Azure Storage 接続文字列
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net

# ジョブストレージ/キュー
JOB_STORAGE_PROVIDER=AZURE
JOB_QUEUE_PROVIDER=AZURE
```

---

## ローカル開発

### 1. セットアップ

```powershell
# ディレクトリ移動
cd platforms/azure

# 仮想環境作成
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 依存関係インストール
pip install -r requirements.txt
```

### 2. local.settings.json 作成

```powershell
@'
{
    "IsEncrypted": false,
    "Values": {
        "AzureWebJobsStorage": "UseDevelopmentStorage=true",
        "FUNCTIONS_WORKER_RUNTIME": "python"
    }
}
'@ | Out-File -Encoding utf8 local.settings.json
```

### 3. ローカルサーバー起動

```powershell
func start
```

サーバーが起動したら:
- http://localhost:7071/api/health - ヘルスチェック
- http://localhost:7071/api/config - 設定確認
- http://localhost:7071/api/evaluate - 評価API (POST)

---

## デプロイ手順

### 1. デプロイパッケージ作成

deploy.ps1スクリプトを使用するか、手動で作成します。

```powershell
# deploy.ps1 を使用（推奨）
.\deploy.ps1

# または手動で作成
# パッケージディレクトリ作成
mkdir package

# 依存関係インストール
pip install -r requirements.txt -t package/

# ソースコードコピー
Copy-Item -Recurse ../../src package/
Copy-Item function_app.py package/
Copy-Item host.json package/

# ZIPファイル作成
Compress-Archive -Path package/* -DestinationPath deploy.zip -Force
```

### 2. リソースグループ作成（初回のみ）

```powershell
az group create --name rg-ic-test --location japaneast
```

### 3. Storage Account 作成（初回のみ）

```powershell
$STORAGE_NAME = "stictest$(Get-Date -Format 'yyyyMMddHHmm')"

az storage account create `
  --name $STORAGE_NAME `
  --resource-group rg-ic-test `
  --location japaneast `
  --sku Standard_LRS
```

### 4. Function App 作成（初回のみ）

```powershell
az functionapp create `
  --name func-ic-test-eval `
  --resource-group rg-ic-test `
  --storage-account $STORAGE_NAME `
  --runtime python `
  --runtime-version 3.11 `
  --functions-version 4 `
  --os-type Linux `
  --consumption-plan-location japaneast
```

### 5. 環境変数設定

```powershell
az functionapp config appsettings set `
  --name func-ic-test-eval `
  --resource-group rg-ic-test `
  --settings `
    LLM_PROVIDER=AZURE_FOUNDRY `
    AZURE_FOUNDRY_ENDPOINT=https://your-project.region.models.ai.azure.com `
    AZURE_FOUNDRY_API_KEY=your-api-key `
    AZURE_FOUNDRY_MODEL=gpt-4o `
    OCR_PROVIDER=NONE
```

### 6. デプロイ

```powershell
# Azure Functions Core Tools を使用
func azure functionapp publish func-ic-test-eval --python

# または ZIP deploy
az functionapp deployment source config-zip `
  --name func-ic-test-eval `
  --resource-group rg-ic-test `
  --src deploy.zip
```

### 7. Function Key 取得

```powershell
az functionapp keys list `
  --name func-ic-test-eval `
  --resource-group rg-ic-test
```

---

## 非同期処理（オプション）

504タイムアウト対策として、Table Storage + Queue Storageによる非同期処理をサポートしています。

### Azure Storage 接続文字列の取得

```powershell
az storage account show-connection-string `
  --name $STORAGE_NAME `
  --resource-group rg-ic-test `
  --output tsv
```

### 環境変数の更新

```powershell
az functionapp config appsettings set `
  --name func-ic-test-eval `
  --resource-group rg-ic-test `
  --settings `
    AZURE_STORAGE_CONNECTION_STRING="your-connection-string" `
    JOB_STORAGE_PROVIDER=AZURE `
    JOB_QUEUE_PROVIDER=AZURE
```

### 非同期APIエンドポイント

| エンドポイント | メソッド | 説明 |
|---------------|---------|------|
| /api/evaluate/submit | POST | ジョブ送信（即座にjob_idを返却） |
| /api/evaluate/status/{job_id} | GET | ジョブステータス確認 |
| /api/evaluate/results/{job_id} | GET | ジョブ結果取得 |

---

## トラブルシューティング

### 1. Azure AI Foundry に接続できない

**原因**: エンドポイントまたはAPIキーが無効

**解決方法**:
1. Azure Portal → AI Foundry → プロジェクト → エンドポイント
2. API キーを再確認

### 2. Function App タイムアウト

**原因**: 処理時間が230秒（デフォルト）を超えた

**解決方法**:
host.json を編集：
```json
{
  "version": "2.0",
  "functionTimeout": "00:10:00"
}
```

### 3. Document Intelligence エラー

**原因**: リージョンがサポートされていない

**解決方法**:
- japaneast リージョンを使用
- Document Intelligence S0 プランを確認

### 4. メモリ不足

**原因**: Consumption プランのメモリ制限

**解決方法**:
- Premium プラン（EP1以上）に変更
- 大きなファイルは分割処理

---

## コスト見積もり

### 月1,000項目処理の場合

| サービス | 使用量 | 月額（概算） |
|---------|--------|-------------|
| Azure Functions | 1,000回 × 60秒 | ~$0.50 |
| Azure AI Foundry (GPT-4o) | 7.6M tokens | ~$30 |
| Document Intelligence | 2,000ページ | ~$3 |
| Storage Account | 1GB | ~$0.02 |
| **合計** | | **~$34/月** |

---

## 参考リンク

- [Azure Functions 開発者ガイド](https://docs.microsoft.com/ja-jp/azure/azure-functions/)
- [Azure AI Foundry ドキュメント](https://learn.microsoft.com/ja-jp/azure/ai-studio/)
- [Azure OpenAI Service](https://learn.microsoft.com/ja-jp/azure/ai-services/openai/)
- [Azure Document Intelligence](https://learn.microsoft.com/ja-jp/azure/ai-services/document-intelligence/)
- [Azure Storage ドキュメント](https://docs.microsoft.com/ja-jp/azure/storage/)
