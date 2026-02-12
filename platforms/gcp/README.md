# GCP Cloud Functions デプロイガイド

内部統制テスト評価AIシステムのGCP Cloud Functions版デプロイ手順です。

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
| Cloud Functions | APIホスティング | 1024MB+ メモリ推奨 |
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

### 1. セットアップ

```powershell
# ディレクトリ移動
cd platforms/gcp

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
- http://localhost:8080/health - ヘルスチェック
- http://localhost:8080/config - 設定確認
- http://localhost:8080/evaluate - 評価API (POST)

---

## デプロイ手順

### 1. デプロイパッケージ作成

```powershell
# src/ ディレクトリをコピー
Copy-Item -Recurse ../../src .
```

### 2. Cloud Functions にデプロイ

```powershell
# evaluate エンドポイント
gcloud functions deploy evaluate `
  --gen2 `
  --runtime python311 `
  --trigger-http `
  --allow-unauthenticated `
  --entry-point evaluate `
  --region asia-northeast1 `
  --timeout 540 `
  --memory 1024MB `
  --set-env-vars "LLM_PROVIDER=GCP,GCP_PROJECT_ID=your-project-id,OCR_PROVIDER=NONE"

# health エンドポイント
gcloud functions deploy health `
  --gen2 `
  --runtime python311 `
  --trigger-http `
  --allow-unauthenticated `
  --entry-point health `
  --region asia-northeast1

# config エンドポイント
gcloud functions deploy config `
  --gen2 `
  --runtime python311 `
  --trigger-http `
  --allow-unauthenticated `
  --entry-point config_status `
  --region asia-northeast1
```

### 3. 更新（2回目以降）

```powershell
# コードを更新して再デプロイ
gcloud functions deploy evaluate `
  --gen2 `
  --runtime python311 `
  --trigger-http `
  --entry-point evaluate `
  --region asia-northeast1
```

### 4. API Gateway設定（オプション）

複数のエンドポイントを単一URLで公開する場合：

```yaml
# api-config.yaml
swagger: "2.0"
info:
  title: IC Test Evaluation API
  version: "1.0"
paths:
  /evaluate:
    post:
      x-google-backend:
        address: https://asia-northeast1-PROJECT_ID.cloudfunctions.net/evaluate
  /health:
    get:
      x-google-backend:
        address: https://asia-northeast1-PROJECT_ID.cloudfunctions.net/health
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
gcloud functions deploy evaluate `
  --gen2 `
  --runtime python311 `
  --trigger-http `
  --entry-point evaluate `
  --region asia-northeast1 `
  --set-env-vars "
    LLM_PROVIDER=GCP,
    GCP_PROJECT_ID=your-project-id,
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

### Cloud Functions サービスアカウントに必要な権限

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

### 2. Cloud Functions タイムアウト

**原因**: 処理時間が540秒を超えた

**解決方法**:
- Cloud Functions gen2 の最大タイムアウトは 60分
- ただし HTTP トリガーは 60分まで延長可能

```powershell
gcloud functions deploy evaluate `
  --gen2 `
  --timeout 3600  # 最大60分
```

### 3. メモリ不足

**原因**: OCR処理でメモリが不足

**解決方法**:
```powershell
gcloud functions deploy evaluate `
  --gen2 `
  --memory 2048MB  # 2GB
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
| Cloud Functions | 1,000回 × 60秒 × 1GB | ~$1 |
| Vertex AI (Gemini 3 Pro) | 7.6M tokens | ~$25 |
| Document AI | 2,000ページ | ~$3 |
| Firestore | 10,000 reads/writes | ~$0.10 |
| Cloud Tasks | 10,000 タスク | ~$0.01 |
| **合計** | | **~$29/月** |

---

## 参考リンク

- [Cloud Functions 開発者ガイド](https://cloud.google.com/functions/docs)
- [Vertex AI ドキュメント](https://cloud.google.com/vertex-ai/docs)
- [Document AI ドキュメント](https://cloud.google.com/document-ai/docs)
- [Firestore ドキュメント](https://cloud.google.com/firestore/docs)
- [Cloud Tasks ドキュメント](https://cloud.google.com/tasks/docs)
