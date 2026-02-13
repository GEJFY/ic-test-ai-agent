# GCP Cloud Run デプロイガイド

内部統制テスト評価AIシステムのGCP Cloud Run版デプロイ手順です。

## 目次

1. [必要なGCPリソース](#必要なgcpリソース)
2. [環境変数設定](#環境変数設定)
3. [ローカル開発](#ローカル開発)
4. [デプロイ手順](#デプロイ手順)
5. [非同期処理（オプション）](#非同期処理オプション)
6. [IAMポリシー](#iamポリシー)
7. [トラブルシューティング](#トラブルシューティング)

---

## 必要なGCPリソース

### 必須リソース

| サービス | 用途 | SKU/プラン |
|---------|------|-----------|
| Cloud Run | APIホスティング（Dockerコンテナ） | 1 vCPU / 2GB メモリ推奨 |
| Artifact Registry | Dockerイメージ管理 | Docker リポジトリ |
| Vertex AI | LLM処理 | Gemini 3 Pro |
| Document AI | OCR処理（オプション） | 従量課金 |

### 非同期処理用（オプション）

| サービス | 用途 | 備考 |
|---------|------|------|
| Firestore | ジョブ状態管理 | ネイティブモード |
| Cloud Tasks | ジョブキュー | HTTPターゲット |
| Cloud Storage | 大容量ファイル | 証跡ファイル一時保存 |

---

## 環境変数設定

### 必須設定

```bash
# LLM設定
LLM_PROVIDER=GCP
GCP_PROJECT_ID=your-project-id
GCP_LOCATION=us-central1

# モデル設定（オプション）
# デフォルト: gemini-3-pro-preview
GCP_MODEL_NAME=gemini-3-pro-preview
```

### OCR設定（オプション）

```bash
# GCP Document AI
OCR_PROVIDER=GCP
GCP_DOCAI_PROJECT_ID=your-project-id
GCP_DOCAI_LOCATION=us
GCP_DOCAI_PROCESSOR_ID=your-processor-id

# または OCR不要の場合
# OCR_PROVIDER=NONE
```

### 非同期処理設定（オプション）

```bash
# ジョブストレージ
JOB_STORAGE_PROVIDER=GCP
GCP_FIRESTORE_COLLECTION=evaluation_jobs

# ジョブキュー
JOB_QUEUE_PROVIDER=GCP
GCP_TASKS_QUEUE=evaluation-jobs
GCP_TASKS_LOCATION=asia-northeast1
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

### 2. GCP認証設定

```powershell
# gcloud CLIで認証
gcloud auth login
gcloud auth application-default login

# プロジェクト設定
gcloud config set project your-project-id

# または環境変数でサービスアカウント指定
$env:GOOGLE_APPLICATION_CREDENTIALS = "path/to/service-account-key.json"
```

### 3. ローカルサーバー起動

```powershell
python main.py
```

サーバーが起動したら:
- http://localhost:8000/health - ヘルスチェック
- http://localhost:8000/config - 設定確認
- http://localhost:8000/evaluate - 評価API (POST)

### 4. Dockerでのローカル実行

```powershell
# プロジェクトルートで実行
docker build -t ic-test-ai:local -f platforms/local/Dockerfile .
docker run -p 8000:8000 --env-file .env ic-test-ai:local
```

---

## デプロイ手順

### 1. Artifact Registryリポジトリ作成（初回のみ）

```powershell
gcloud artifacts repositories create ic-test-ai `
  --repository-format=docker `
  --location=asia-northeast1 `
  --description="IC Test AI Docker images"
```

### 2. Artifact Registryに認証

```powershell
gcloud auth configure-docker asia-northeast1-docker.pkg.dev
```

### 3. Dockerイメージをビルド・プッシュ

```powershell
$PROJECT_ID = "your-project-id"
$AR_REPO = "asia-northeast1-docker.pkg.dev/$PROJECT_ID/ic-test-ai"

# プロジェクトルートで実行
docker build -t "${AR_REPO}/ic-test-ai:latest" -f platforms/local/Dockerfile .
docker push "${AR_REPO}/ic-test-ai:latest"
```

### 4. Cloud Runサービス作成・デプロイ

```powershell
gcloud run deploy ic-test-evaluate `
  --image="${AR_REPO}/ic-test-ai:latest" `
  --region=asia-northeast1 `
  --port=8000 `
  --cpu=1 `
  --memory=2Gi `
  --timeout=540 `
  --min-instances=0 `
  --max-instances=3 `
  --allow-unauthenticated `
  --set-env-vars "LLM_PROVIDER=GCP,GCP_PROJECT_ID=$PROJECT_ID,OCR_PROVIDER=NONE"
```

### 5. 更新デプロイ（2回目以降）

```powershell
# イメージをビルド・プッシュ
docker build -t "${AR_REPO}/ic-test-ai:latest" -f platforms/local/Dockerfile .
docker push "${AR_REPO}/ic-test-ai:latest"

# Cloud Runサービスを更新
gcloud run deploy ic-test-evaluate `
  --image="${AR_REPO}/ic-test-ai:latest" `
  --region=asia-northeast1
```

---

## 非同期処理（オプション）

504タイムアウト対策として、Firestore + Cloud Tasksによる非同期処理をサポートしています。

### Firestore データベース作成

```powershell
# Firestore をネイティブモードで作成
gcloud firestore databases create `
  --location=asia-northeast1
```

### Cloud Tasks キュー作成

```powershell
gcloud tasks queues create evaluation-jobs `
  --location=asia-northeast1
```

### 環境変数の更新

```powershell
gcloud run deploy ic-test-evaluate `
  --image="${AR_REPO}/ic-test-ai:latest" `
  --region=asia-northeast1 `
  --set-env-vars "
    LLM_PROVIDER=GCP,
    GCP_PROJECT_ID=$PROJECT_ID,
    OCR_PROVIDER=NONE,
    JOB_STORAGE_PROVIDER=GCP,
    GCP_FIRESTORE_COLLECTION=evaluation_jobs,
    JOB_QUEUE_PROVIDER=GCP,
    GCP_TASKS_QUEUE=evaluation-jobs,
    GCP_TASKS_LOCATION=asia-northeast1
  "
```

---

## IAMポリシー

### Cloud Run サービスアカウントに必要な権限

```bash
# Vertex AI 権限
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:PROJECT_ID@appspot.gserviceaccount.com" \
  --role="roles/aiplatform.user"

# Document AI 権限（OCR使用時）
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:PROJECT_ID@appspot.gserviceaccount.com" \
  --role="roles/documentai.viewer"

# Firestore 権限（非同期処理使用時）
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:PROJECT_ID@appspot.gserviceaccount.com" \
  --role="roles/datastore.user"

# Cloud Tasks 権限（非同期処理使用時）
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:PROJECT_ID@appspot.gserviceaccount.com" \
  --role="roles/cloudtasks.enqueuer"
```

### 最小権限のカスタムロール

```yaml
# custom-role.yaml
title: "IC Test Evaluation Role"
description: "Minimum permissions for IC Test Evaluation System"
includedPermissions:
  - aiplatform.endpoints.predict
  - documentai.processors.processBatch
  - datastore.entities.create
  - datastore.entities.get
  - datastore.entities.update
  - datastore.entities.delete
  - cloudtasks.tasks.create
```

---

## トラブルシューティング

### 1. Vertex AI モデルにアクセスできない

**原因**: Vertex AI API が有効化されていない

**解決方法**:
```powershell
gcloud services enable aiplatform.googleapis.com
```

### 2. Cloud Run タイムアウト

**原因**: 処理時間がデフォルトタイムアウトを超えた

**解決方法**:
Cloud Run のタイムアウトは最大60分まで延長可能：

```powershell
gcloud run deploy ic-test-evaluate `
  --timeout 3600  # 最大60分
```

### 3. メモリ不足

**原因**: OCR処理でメモリが不足

**解決方法**:
```powershell
gcloud run deploy ic-test-evaluate `
  --memory 4Gi `
  --cpu 2
```

### 4. 認証エラー

**原因**: サービスアカウントの権限不足

**解決方法**:
1. IAMポリシーを確認
2. 必要な権限を追加
3. `gcloud auth application-default login` を再実行

---

## コスト見積もり

### 月1,000項目処理の場合

| サービス | 使用量 | 月額（概算） |
|---------|--------|-------------|
| Cloud Run | 1,000回 × 60秒 × 1 vCPU | ~$1-3 |
| Artifact Registry | イメージストレージ | ~$1 |
| Vertex AI (Gemini 3 Pro) | 7.6M tokens | ~$25 |
| Document AI | 2,000ページ | ~$3 |
| Firestore | 10,000 reads/writes | ~$0.10 |
| Cloud Tasks | 10,000 タスク | ~$0.01 |
| **合計** | | **~$30-32/月** |

---

## 参考リンク

- [Cloud Run ドキュメント](https://cloud.google.com/run/docs)
- [Artifact Registry ドキュメント](https://cloud.google.com/artifact-registry/docs)
- [Vertex AI ドキュメント](https://cloud.google.com/vertex-ai/docs)
- [Document AI ドキュメント](https://cloud.google.com/document-ai/docs)
- [Firestore ドキュメント](https://cloud.google.com/firestore/docs)
- [Cloud Tasks ドキュメント](https://cloud.google.com/tasks/docs)
