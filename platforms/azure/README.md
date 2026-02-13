# Azure Container Apps デプロイガイド

内部統制テスト評価AIシステムのAzure Container Apps版デプロイ手順です。

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
| Azure Container Apps | APIホスティング（Dockerコンテナ） | Consumption |
| Azure Container Registry (ACR) | Dockerイメージ管理 | Basic |
| Storage Account | ストレージ | Standard LRS |
| Azure AI Foundry | LLM処理 | GPT-5 Nano |
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
AZURE_FOUNDRY_MODEL=gpt-5-nano
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

全プラットフォーム共通のDockerイメージ（FastAPI/Uvicorn）を使用します。

### 1. セットアップ

```powershell
# ディレクトリ移動
cd platforms/local

# 仮想環境作成
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 依存関係インストール
pip install -r requirements.txt
```

### 2. ローカルサーバー起動

```powershell
# FastAPIサーバーを起動
python main.py

# または uvicorn を使用
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

サーバーが起動したら:
- http://localhost:8000/health - ヘルスチェック
- http://localhost:8000/config - 設定確認
- http://localhost:8000/evaluate - 評価API (POST)

### 3. Dockerでのローカル実行

```powershell
# プロジェクトルートで実行
docker build -t ic-test-ai:local -f platforms/local/Dockerfile .
docker run -p 8000:8000 --env-file .env ic-test-ai:local
```

---

## デプロイ手順

### 1. ACRにログイン

```powershell
$ACR_NAME = "<ACR名>"
az acr login --name $ACR_NAME
```

### 2. Dockerイメージをビルド・プッシュ

```powershell
# プロジェクトルートで実行
docker build -t "$ACR_NAME.azurecr.io/ic-test-ai:latest" -f platforms/local/Dockerfile .
docker push "$ACR_NAME.azurecr.io/ic-test-ai:latest"
```

### 3. リソースグループ作成（初回のみ）

```powershell
az group create --name rg-ic-test --location japaneast
```

### 4. Container Apps環境作成（初回のみ）

```powershell
az containerapp env create `
  --name ic-test-env `
  --resource-group rg-ic-test `
  --location japaneast
```

### 5. Container Apps作成・デプロイ

```powershell
az containerapp create `
  --name ic-test-eval `
  --resource-group rg-ic-test `
  --environment ic-test-env `
  --image "$ACR_NAME.azurecr.io/ic-test-ai:latest" `
  --registry-server "$ACR_NAME.azurecr.io" `
  --target-port 8000 `
  --ingress external `
  --cpu 1.0 --memory 2.0Gi `
  --min-replicas 0 --max-replicas 3 `
  --env-vars `
    LLM_PROVIDER=AZURE_FOUNDRY `
    AZURE_FOUNDRY_ENDPOINT=https://your-project.region.models.ai.azure.com `
    AZURE_FOUNDRY_API_KEY=your-api-key `
    AZURE_FOUNDRY_MODEL=gpt-5-nano `
    OCR_PROVIDER=NONE
```

### 6. 更新デプロイ（2回目以降）

```powershell
# イメージをビルド・プッシュ
docker build -t "$ACR_NAME.azurecr.io/ic-test-ai:latest" -f platforms/local/Dockerfile .
docker push "$ACR_NAME.azurecr.io/ic-test-ai:latest"

# Container Appsを更新
az containerapp update `
  --name ic-test-eval `
  --resource-group rg-ic-test `
  --image "$ACR_NAME.azurecr.io/ic-test-ai:latest"
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
az containerapp update `
  --name ic-test-eval `
  --resource-group rg-ic-test `
  --set-env-vars `
    AZURE_STORAGE_CONNECTION_STRING="your-connection-string" `
    JOB_STORAGE_PROVIDER=AZURE `
    JOB_QUEUE_PROVIDER=AZURE
```

### 非同期APIエンドポイント

| エンドポイント | メソッド | 説明 |
|---------------|---------|------|
| /evaluate/submit | POST | ジョブ送信（即座にjob_idを返却） |
| /evaluate/status/{job_id} | GET | ジョブステータス確認 |
| /evaluate/results/{job_id} | GET | ジョブ結果取得 |

---

## トラブルシューティング

### 1. Azure AI Foundry に接続できない

**原因**: エンドポイントまたはAPIキーが無効

**解決方法**:
1. Azure Portal → AI Foundry → プロジェクト → エンドポイント
2. API キーを再確認

### 2. Container Apps タイムアウト

**原因**: 処理時間がデフォルトタイムアウトを超えた

**解決方法**:
Container Appsのリクエストタイムアウトを調整：
```powershell
az containerapp ingress update `
  --name ic-test-eval `
  --resource-group rg-ic-test `
  --transport http `
  --request-timeout 600
```

### 3. Document Intelligence エラー

**原因**: リージョンがサポートされていない

**解決方法**:
- japaneast リージョンを使用
- Document Intelligence S0 プランを確認

### 4. メモリ不足

**原因**: コンテナのメモリ制限

**解決方法**:
```powershell
az containerapp update `
  --name ic-test-eval `
  --resource-group rg-ic-test `
  --cpu 2.0 --memory 4.0Gi
```

---

## コスト見積もり

### 月1,000項目処理の場合

| サービス | 使用量 | 月額（概算） |
|---------|--------|-------------|
| Azure Container Apps | 1,000回 × 60秒 | ~$1-3 |
| Azure Container Registry | Basic | ~$5 |
| Azure AI Foundry (GPT-5 Nano) | 7.6M tokens | ~$30 |
| Document Intelligence | 2,000ページ | ~$3 |
| Storage Account | 1GB | ~$0.02 |
| **合計** | | **~$39-41/月** |

---

## 参考リンク

- [Azure Container Apps ドキュメント](https://learn.microsoft.com/ja-jp/azure/container-apps/)
- [Azure Container Registry ドキュメント](https://learn.microsoft.com/ja-jp/azure/container-registry/)
- [Azure AI Foundry ドキュメント](https://learn.microsoft.com/ja-jp/azure/ai-studio/)
- [Azure Document Intelligence](https://learn.microsoft.com/ja-jp/azure/ai-services/document-intelligence/)
- [Azure Storage ドキュメント](https://docs.microsoft.com/ja-jp/azure/storage/)
