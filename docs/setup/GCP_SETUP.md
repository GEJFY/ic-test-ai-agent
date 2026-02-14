# GCP環境セットアップガイド - 内部統制テスト評価AIシステム

> **完全初心者向け** | 所要時間: 約2〜3時間 | 最終更新: 2026年2月

---

## 目次

1. [はじめに](#1-はじめに)
2. [GCPとは](#2-gcpとは)
3. [gcloud CLIのセットアップ](#3-gcloud-cliのセットアップ)
4. [IAMとサービスアカウント](#4-iamとサービスアカウント)
5. [必要なAPIの有効化](#5-必要なapiの有効化)
6. [Cloud Run](#6-cloud-run)
7. [Vertex AI (Gemini 3 Pro)](#7-vertex-ai-gemini-3-pro)
8. [Document AI](#8-document-ai)
9. [Apigee](#9-apigee)
10. [Secret Manager](#10-secret-manager)
11. [Cloud Logging / Cloud Trace](#11-cloud-logging--cloud-trace)
12. [Cloud Storage](#12-cloud-storage)
13. [Terraformデプロイ](#13-terraformデプロイ)
14. [統合テスト](#14-統合テスト)
15. [コスト管理](#15-コスト管理)
16. [まとめ・次のステップ](#16-まとめ次のステップ)

---

## 1. はじめに

### このガイドの目的

このガイドでは、**内部統制テスト評価AIシステム** をGoogle Cloud Platform（GCP）上に構築するための手順を、クラウド未経験者でも迷わずに進められるよう、一つひとつ丁寧に解説します。

### 前提条件

| 項目 | 要件 |
|------|------|
| OS | Windows 11（Mac/Linuxでも可） |
| Python | 3.11以上がインストール済み |
| Git | インストール済み |
| クレジットカード | GCPアカウント作成に必要（$300無料クレジットあり） |
| ブラウザ | Chrome推奨（GCP Consoleの表示最適化） |

### 所要時間の目安

| セクション | 時間 |
|------------|------|
| GCPアカウント作成〜gcloud CLI | 約30分 |
| IAM・API有効化・各サービス設定 | 約60分 |
| Terraform デプロイ | 約30分 |
| 統合テスト・動作確認 | 約30分 |

### 記号の説明

| 記号 | 意味 |
|------|------|
| 💡 | ヒント・補足情報 |
| ⚠️ | 注意・警告 |
| ✅ | 完了確認・成功 |
| 📖 | 用語説明・学習ポイント |

---

## 2. GCPとは

### 📖 クラウドサービスとは

「クラウドサービス」とは、自分のPCではなく、インターネット上のサーバーでプログラムを動かしたりデータを保存したりするサービスです。自分でサーバーを買う必要がなく、使った分だけ料金を払います。

### 📖 Google Cloud Platform (GCP) の特徴

GCPは、Googleが提供するクラウドサービスです。主要なクラウドサービスには以下の3つがあります。

| プラットフォーム | 提供元 | 特徴 |
|------------------|--------|------|
| **GCP** | Google | AI/ML機能が強力、コスト効率が良い |
| Azure | Microsoft | 企業向け機能が充実、Office連携 |
| AWS | Amazon | シェア最大、サービス数最多 |

本システムではGCPが**最もコスト効率が良く（月額約¥1,300）**、Geminiモデルとの統合もスムーズです。

### GCPアカウント作成

1. ブラウザで [https://cloud.google.com/](https://cloud.google.com/) を開く
2. 右上の「無料で開始」をクリック
3. Googleアカウントでログイン（なければ新規作成）
4. 支払い情報を入力（$300 / 90日間の無料クレジットが付与されます）
5. 利用規約に同意して登録完了

💡 **$300の無料クレジット** が付与されるので、本システムの構築・テストは無料クレジット内で十分に賄えます。クレジットが切れても自動課金はされません（手動で有料アカウントに切り替えるまで）。

⚠️ 無料クレジットの有効期限は **90日間** です。期間内にテスト・検証を完了させましょう。

### GCP Console 基本操作

GCP Consoleは、GCPのすべてのリソースを管理するWebダッシュボードです。

1. [https://console.cloud.google.com/](https://console.cloud.google.com/) にアクセス
2. 左上のハンバーガーメニュー（≡）から各サービスにアクセス
3. 上部のプロジェクト選択ドロップダウンでプロジェクトを切り替え
4. 右上の「Cloud Shell」アイコンでブラウザ内ターミナルを起動可能

📖 **プロジェクト** とは、GCPリソースをまとめる「箱」のようなものです。一つのプロジェクトの中に、Cloud Run、Vertex AI、Secret Managerなどのサービスを配置します。

### プロジェクトの作成

```bash
# GCP Consoleの上部バーで「プロジェクトを選択」→「新しいプロジェクト」をクリック
# プロジェクト名: ic-test-ai（推奨）
# 組織: 個人の場合は「組織なし」
```

プロジェクトIDは後でよく使うので、メモしておいてください。

✅ **確認**: GCP Consoleにログインし、プロジェクトが作成されていればOKです。

---

## 3. gcloud CLIのセットアップ

### 📖 gcloud CLI とは

`gcloud` は、GCPをコマンドライン（ターミナル）から操作するためのツールです。GCP Consoleの画面操作と同じことを、コマンドで実行できます。自動化やスクリプト化に不可欠なツールです。

### インストール

#### Windows

```bash
# PowerShellで実行（管理者権限推奨）
# Google Cloud SDK インストーラーをダウンロードして実行
# https://cloud.google.com/sdk/docs/install からインストーラーをダウンロード

# または、wingetを使用（Windows 11推奨）
winget install Google.CloudSDK
```

#### Mac

```bash
# Homebrew経由でインストール
brew install --cask google-cloud-sdk
```

#### Linux

```bash
# aptリポジトリを追加してインストール
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list
sudo apt-get update && sudo apt-get install google-cloud-cli
```

### インストール確認

```bash
gcloud version
```

✅ **期待される出力**:
```
Google Cloud SDK 500.x.x
bq 2.x.x
core 2026.x.x
gcloud-crc32c 1.x.x
gsutil 5.x
```

### 初期設定（gcloud init）

```bash
gcloud init
```

対話形式で以下の設定を行います。

```
Welcome! This command will take you through the configuration of gcloud.

Pick configuration to use:
 [1] Re-initialize this configuration [default] with new settings
 [2] Create a new configuration
Please enter your numeric choice: 1

Choose the account you would like to use to perform operations for
this configuration:
 [1] your-email@gmail.com
 [2] Log in with a new account
Please enter your numeric choice: 1

Pick cloud project to use:
 [1] ic-test-ai-xxxxxx
 [2] Enter a project ID
 [3] Create a new project
Please enter numeric choice or text value: 1

Do you want to configure a default Compute Region and Zone? (Y/n)? Y
 [19] asia-northeast1-a  ← 東京リージョン
Please enter numeric choice or text value: 19
```

💡 **リージョン** は `asia-northeast1`（東京）を選択してください。日本からのアクセス遅延が最小になります。

### アプリケーションデフォルト認証の設定

```bash
gcloud auth application-default login
```

ブラウザが開くので、Googleアカウントでログインしてください。この認証情報は、Pythonコードからの GCP API 呼び出しに使用されます。

✅ **期待される出力**:
```
Credentials saved to file: [C:\Users\<username>\AppData\Roaming\gcloud\application_default_credentials.json]

These credentials will be used by any library that requests Application Default Credentials (ADC).
```

### プロジェクトの設定確認

```bash
# 現在の設定を確認
gcloud config list
```

✅ **期待される出力**:
```
[compute]
region = asia-northeast1
zone = asia-northeast1-a
[core]
account = your-email@gmail.com
project = ic-test-ai-xxxxxx
```

```bash
# プロジェクトIDを変更する場合
gcloud config set project <YOUR_PROJECT_ID>
```

### よくあるエラーと対処法

| エラー | 原因 | 対処法 |
|--------|------|--------|
| `gcloud: command not found` | PATHが通っていない | インストーラーを再実行するか、PATHに手動追加 |
| `ERROR: (gcloud.init) Failed to authenticate` | 認証失敗 | `gcloud auth login` を再実行 |
| `The project does not exist` | プロジェクトIDが間違っている | `gcloud projects list` で正しいIDを確認 |
| `Billing account not found` | 請求先アカウント未設定 | GCP Console → 「お支払い」で請求先を設定 |

⚠️ 認証情報ファイル（`application_default_credentials.json`）は **絶対にGitにコミットしない** でください。`.gitignore` に含まれていることを確認しましょう。

---

## 4. IAMとサービスアカウント

### 📖 IAM（Identity and Access Management）とは

IAMは「**誰が**」「**何に対して**」「**何をできるか**」を管理する仕組みです。

| 概念 | 説明 | 例 |
|------|------|-----|
| **プリンシパル** | アクセスする人・サービス | ユーザー、サービスアカウント |
| **ロール** | 権限のまとまり | `roles/run.developer` |
| **ポリシー** | プリンシパルとロールの紐付け | 「AさんにCloud Run開発者権限を付与」 |

📖 **サービスアカウント** は、人間ではなくプログラム（Cloud RunやTerraformなど）がGCPリソースにアクセスするための「仮想的なアカウント」です。

### サービスアカウントの作成

本システムでは、Cloud Runが Vertex AI、Document AI、Secret Manager にアクセスするためのサービスアカウントが必要です。

```bash
# プロジェクトIDを変数に設定
export PROJECT_ID="ic-test-ai-xxxxxx"

# サービスアカウントを作成
gcloud iam service-accounts create ic-test-ai-prod-run-sa \
  --display-name="Cloud Run Service Account for ic-test-ai" \
  --project=$PROJECT_ID
```

✅ **期待される出力**:
```
Created service account [ic-test-ai-prod-run-sa].
```

💡 Windows PowerShellの場合は `export` の代わりに `$env:PROJECT_ID = "ic-test-ai-xxxxxx"` を使用してください。

### ロールの付与

```bash
# Vertex AI ユーザー権限
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:ic-test-ai-prod-run-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

# Document AI ユーザー権限
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:ic-test-ai-prod-run-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/documentai.apiUser"

# Secret Manager アクセス権限
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:ic-test-ai-prod-run-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Cloud Logging 書き込み権限
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:ic-test-ai-prod-run-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/logging.logWriter"

# Cloud Trace エージェント権限
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:ic-test-ai-prod-run-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/cloudtrace.agent"
```

✅ **期待される出力**（各コマンドに対して）:
```
Updated IAM policy for project [ic-test-ai-xxxxxx].
bindings:
- members:
  - serviceAccount:ic-test-ai-prod-run-sa@ic-test-ai-xxxxxx.iam.gserviceaccount.com
  role: roles/aiplatform.user
...
```

### サービスアカウントキーの管理

📖 ローカル開発時には、サービスアカウントの **キーファイル（JSON）** を使ってプログラムから認証します。

```bash
# キーファイルを作成（ローカル開発用のみ）
gcloud iam service-accounts keys create key.json \
  --iam-account=ic-test-ai-prod-run-sa@${PROJECT_ID}.iam.gserviceaccount.com
```

✅ **期待される出力**:
```
created key [xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx] of type [json] as [key.json]
```

```bash
# 環境変数にキーファイルのパスを設定
export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/key.json"
```

⚠️ **重要**: `key.json` は **絶対にGitにコミットしない** でください。`.gitignore` に `key.json` が含まれていることを確認しましょう。漏洩した場合は直ちにキーを無効化してください。

⚠️ **本番環境では**: Cloud Run上ではサービスアカウントが自動的に割り当てられるため、キーファイルは不要です。キーファイルはローカル開発時のみ使用します。

### IAM権限の確認

```bash
# サービスアカウントに付与されたロールを確認
gcloud projects get-iam-policy $PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:ic-test-ai-prod-run-sa" \
  --format="table(bindings.role)"
```

✅ **期待される出力**:
```
ROLE
roles/aiplatform.user
roles/cloudtrace.agent
roles/documentai.apiUser
roles/logging.logWriter
roles/secretmanager.secretAccessor
```

---

## 5. 必要なAPIの有効化

### 📖 なぜAPIの有効化が必要か

GCPでは、各サービスのAPIは**デフォルトで無効**になっています。使いたいサービスのAPIを明示的に「有効化」する必要があります。これはセキュリティのためです。使わないAPIを有効にしなければ、意図しないアクセスや課金を防げます。

### 全APIの一括有効化

```bash
# 必要な全APIを一括で有効化
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  aiplatform.googleapis.com \
  documentai.googleapis.com \
  secretmanager.googleapis.com \
  logging.googleapis.com \
  cloudtrace.googleapis.com \
  monitoring.googleapis.com \
  storage.googleapis.com \
  cloudresourcemanager.googleapis.com \
  iam.googleapis.com \
  --project=$PROJECT_ID
```

✅ **期待される出力**:
```
Operation "operations/acat.xxxxx" finished successfully.
```

💡 すべてのAPIが有効化されるまで1〜2分かかる場合があります。

### 各APIの説明

| API | 用途 | 本システムでの使い方 |
|-----|------|---------------------|
| `run.googleapis.com` | Cloud Run | バックエンドAPI（コンテナベース） |
| `cloudbuild.googleapis.com` | Cloud Build | Dockerイメージのビルド・デプロイ |
| `artifactregistry.googleapis.com` | Artifact Registry | Dockerイメージの保存 |
| `aiplatform.googleapis.com` | Vertex AI | Gemini 3 Proによるテスト評価 |
| `documentai.googleapis.com` | Document AI | PDF・画像からのOCRテキスト抽出 |
| `secretmanager.googleapis.com` | Secret Manager | APIキーの安全な管理 |
| `logging.googleapis.com` | Cloud Logging | ログの記録・検索 |
| `cloudtrace.googleapis.com` | Cloud Trace | リクエストの分散トレーシング |
| `monitoring.googleapis.com` | Cloud Monitoring | メトリクス・アラート |
| `storage.googleapis.com` | Cloud Storage | ファイル保存・デプロイパッケージ |
| `cloudresourcemanager.googleapis.com` | Resource Manager | プロジェクト管理 |
| `iam.googleapis.com` | IAM | 認証・認可 |

### Apigee API（オプション）

Apigeeを使用する場合のみ有効化してください（高コスト注意）。

```bash
# Apigee API（オプション - 月額$4.50〜）
gcloud services enable apigee.googleapis.com --project=$PROJECT_ID
```

⚠️ Apigeeは評価版期間外では課金されます。開発・テスト段階では無効のままにすることを推奨します。

### API有効化の確認

```bash
# 有効なAPIの一覧を表示
gcloud services list --enabled --project=$PROJECT_ID --format="table(config.name)"
```

✅ 上記の全APIが一覧に含まれていれば成功です。

---

## 6. Cloud Run

### 📖 コンテナサービスとは

「コンテナサービス」とは、Dockerコンテナ化されたアプリケーションをクラウド上で実行するサービスです。サーバーの購入、OS更新、スケーリング（負荷増加時のサーバー追加）をクラウド側が自動管理します。

### 📖 Cloud Run とは

Cloud Runは、GCPのフルマネージドコンテナ実行サービスです。Dockerイメージをデプロイするだけで、HTTPS URL が自動発行され、リクエスト数に応じて自動スケーリングされます。

Cloud Runの特徴：
- **Dockerイメージ対応**: 任意のコンテナイメージをデプロイ可能
- **自動HTTPS**: SSL/TLS証明書が自動発行される
- **自動スケーリング**: リクエスト数に応じてコンテナインスタンスが増減（ゼロスケール対応）
- **従量課金**: リクエスト処理中のCPU・メモリのみ課金
- **最大60分のタイムアウト**: AI処理に十分な時間

💡 本システムではCloud Runを使用します。FastAPIアプリケーションをDockerコンテナとしてデプロイします。

### 本システムのCloud Run構成

本システムのCloud Runは以下の設定で構築されます（`infrastructure/gcp/terraform/cloud-run.tf` に定義済み）。

| 設定項目 | 値 | 説明 |
|----------|-----|------|
| コンテナポート | `8000` | FastAPIデフォルトポート |
| タイムアウト | `540秒` | 最大9分（AI処理の余裕を確保） |
| メモリ | `1Gi` | 1GB |
| CPU | `1` | 1 vCPU |
| 最大インスタンス | `10` | 同時最大10インスタンス |
| 最小インスタンス | `0` | 使わない時はゼロ（コスト最適化） |

### ローカルでのテスト（Cloud Runデプロイ前のテスト）

デプロイ前に、ローカルでコードが正常に動作するか確認しましょう。

```bash
# プロジェクトルートで仮想環境を作成
python -m venv .venv

# 仮想環境を有効化（Windows PowerShell）
.\.venv\Scripts\Activate.ps1

# 依存パッケージのインストール
pip install -r requirements.txt
```

```bash
# ユニットテストの実行
python -m pytest tests/unit/ -v
```

✅ **期待される出力**:
```
tests/unit/test_tasks.py::test_xxx PASSED
...
792 passed in X.XXs
```

### DockerイメージのビルドとCloud Runへのデプロイ

```bash
# プロジェクトルートでDockerイメージをビルド
docker build -t ic-test-ai-agent .

# ローカルでテスト実行
docker run -p 8000:8000 --env-file .env ic-test-ai-agent

# 別ターミナルからヘルスチェック
curl http://localhost:8000/api/health

# Artifact Registryリポジトリを作成
gcloud artifacts repositories create ic-test-ai-repo \
  --repository-format=docker \
  --location=asia-northeast1 \
  --project=$PROJECT_ID

# Dockerイメージにタグを付与
docker tag ic-test-ai-agent \
  asia-northeast1-docker.pkg.dev/${PROJECT_ID}/ic-test-ai-repo/ic-test-ai-agent:latest

# Artifact Registryにプッシュ
gcloud auth configure-docker asia-northeast1-docker.pkg.dev
docker push \
  asia-northeast1-docker.pkg.dev/${PROJECT_ID}/ic-test-ai-repo/ic-test-ai-agent:latest

# Cloud Runにデプロイ
gcloud run deploy ic-test-ai-prod \
  --image=asia-northeast1-docker.pkg.dev/${PROJECT_ID}/ic-test-ai-repo/ic-test-ai-agent:latest \
  --region=asia-northeast1 \
  --memory=1Gi \
  --cpu=1 \
  --timeout=540s \
  --max-instances=10 \
  --min-instances=0 \
  --port=8000 \
  --service-account=ic-test-ai-prod-run-sa@${PROJECT_ID}.iam.gserviceaccount.com \
  --set-env-vars="LLM_PROVIDER=GCP,OCR_PROVIDER=GCP,GCP_PROJECT_ID=${PROJECT_ID},GCP_REGION=asia-northeast1" \
  --allow-unauthenticated
```

✅ **期待される出力**:
```
Deploying container to Cloud Run service [ic-test-ai-prod] in project [ic-test-ai-xxxxxx] region [asia-northeast1]
...
Service [ic-test-ai-prod] revision [ic-test-ai-prod-xxxxx] has been deployed and is serving 100 percent of traffic.
Service URL: https://ic-test-ai-prod-xxxxxx-an.a.run.app
```

💡 デプロイには2〜5分かかります。Service URLが表示されれば成功です。

### 環境変数の設定

Cloud Runの環境変数はTerraform経由で自動設定されますが、手動で変更する場合は以下のコマンドを使用します。

```bash
# 環境変数の確認
gcloud run services describe ic-test-ai-prod \
  --region=asia-northeast1 \
  --format="yaml(spec.template.spec.containers[0].env)"

# 環境変数を追加・更新する場合
gcloud run services update ic-test-ai-prod \
  --region=asia-northeast1 \
  --update-env-vars="DEBUG=true"
```

### デプロイの検証

```bash
# Cloud RunのサービスURLを取得
SERVICE_URL=$(gcloud run services describe ic-test-ai-prod \
  --region=asia-northeast1 \
  --format="value(status.url)")

# ヘルスチェック
curl -s "${SERVICE_URL}/api/health" | python -m json.tool
```

✅ **期待される出力**:
```json
{
    "status": "healthy",
    "platform": "gcp",
    "version": "1.0.0"
}
```

### よくあるエラーと対処法

| エラー | 原因 | 対処法 |
|--------|------|--------|
| `Build failed` | Dockerイメージのビルドエラー | `Dockerfile` と `requirements.txt` を確認 |
| `Permission denied` | サービスアカウント権限不足 | セクション4のロール付与を再確認 |
| `Container timeout` | 処理時間超過 | `--timeout` を延長 |
| `Memory limit exceeded` | メモリ不足 | `--memory` を増加（2Giなど） |

---

## 7. Vertex AI (Gemini 3 Pro)

### 📖 Vertex AI とは

Vertex AIは、GoogleのマネージドAI/MLプラットフォームです。GeminiモデルをはじめとするGoogleの最先端AIモデルにAPI経由でアクセスできます。モデルのトレーニングやデプロイ、推論（予測）をすべてVertex AI上で行えます。

### 📖 Gemini 3 Pro モデル

Gemini 3 Proは、Googleが開発した最新の大規模言語モデル（LLM）です。テキスト理解、コード生成、推論に優れ、日本語にも対応しています。

本システムで使用可能なGeminiモデル:

| モデル名 | 特徴 | 推奨用途 |
|----------|------|----------|
| `gemini-3-pro-preview` | 最高性能（globalリージョン必須） | 高精度な評価が必要な場合 |
| `gemini-2.5-pro` | 高度な推論・コーディング | 標準的な評価 |
| `gemini-2.5-flash` | 高速・コスト効率 | 画像認識（Vision対応） |
| `gemini-2.5-flash-lite` | 超軽量 | 大量処理・コスト重視 |

### Vertex AIのテスト（Python SDK）

ローカル環境からVertex AIに接続できるか確認しましょう。

```bash
# 必要なパッケージをインストール
pip install langchain-google-vertexai google-cloud-aiplatform
```

```python
# test_vertex_ai.py - ローカルテスト用スクリプト
from langchain_google_vertexai import ChatVertexAI

# Gemini 3 Pro Preview で接続テスト（globalリージョン必須）
llm = ChatVertexAI(
    project="ic-test-ai-xxxxxx",  # あなたのプロジェクトIDに置き換え
    location="global",             # Gemini 3 Pro はglobalリージョン必須
    model_name="gemini-3-pro-preview",
    temperature=0.0
)

# テスト実行
response = llm.invoke("内部統制テストとは何ですか？簡潔に説明してください。")
print(response.content)
```

```bash
python test_vertex_ai.py
```

✅ **期待される出力**（例）:
```
内部統制テストとは、企業の内部統制の有効性を評価するために実施される
テスト手続きです。財務報告の信頼性、法令遵守、業務の有効性・効率性
を確認する目的で、統制活動が設計通りに運用されているかを検証します。
```

### 環境変数の設定

本システムでは `LLM_PROVIDER=GCP` を設定することで、自動的にVertex AI（Geminiモデル）が使用されます。

```bash
# .envファイルに追加（ローカル開発用）
echo "LLM_PROVIDER=GCP" >> .env
echo "GCP_PROJECT_ID=ic-test-ai-xxxxxx" >> .env
echo "GCP_LOCATION=asia-northeast1" >> .env
```

💡 Gemini 3 Pro Preview を使用する場合は、`GCP_LOCATION=global` に設定してください（Preview版はglobalリージョンのみ対応）。

### トークンとコストの目安

| モデル | 入力トークン単価 | 出力トークン単価 | 1回の評価コスト目安 |
|--------|-----------------|-----------------|-------------------|
| gemini-2.5-flash | $0.15/1Mトークン | $0.60/1Mトークン | 約¥0.5〜¥2 |
| gemini-2.5-flash-lite | $0.075/1Mトークン | $0.30/1Mトークン | 約¥0.2〜¥1 |
| gemini-2.5-pro | $1.25/1Mトークン | $10.00/1Mトークン | 約¥5〜¥20 |
| gemini-3-pro-preview | 要確認 | 要確認 | 要確認 |

📖 **トークン** とは、AIモデルがテキストを処理する最小単位です。日本語の場合、1文字がおおよそ1〜3トークンに相当します。「内部統制テスト」は約10〜15トークンです。

💡 月間100回の評価を想定した場合、`gemini-2.5-flash` で月額約¥50〜¥200です。

### よくあるエラーと対処法

| エラー | 原因 | 対処法 |
|--------|------|--------|
| `403 Permission denied on resource project` | Vertex AI API未有効化 | セクション5のAPI有効化を実行 |
| `Model not found` | モデル名が間違っている | 上記のモデル名一覧を確認 |
| `Quota exceeded` | APIクォータ超過 | GCP Console → IAMと管理 → 割り当てで確認 |
| `Location not supported` | リージョン非対応 | `asia-northeast1` または `global` を使用 |

---

## 8. Document AI

### 📖 Document AI とは

Document AIは、GCPのOCR（光学文字認識）サービスです。PDF文書や画像からテキストを抽出します。スキャンされた書類、領収書、請求書などからテキストデータを自動的に読み取ることができます。

本システムでは、内部統制テストの証跡書類（PDF、画像）からテキストを抽出するために使用します。

### プロセッサの作成

Document AIでは「プロセッサ」という処理エンジンを作成する必要があります。

#### GCP Consoleから作成する方法（推奨）

1. [https://console.cloud.google.com/ai/document-ai](https://console.cloud.google.com/ai/document-ai) にアクセス
2. 「プロセッサを作成」をクリック
3. 「Document OCR」を選択
4. プロセッサ名: `ic-test-ai-ocr`
5. リージョン: `us`（Document AIは現時点で `us` と `eu` のみ対応）
6. 「作成」をクリック

💡 Document AIのプロセッサは `asia-northeast1` には対応していないため、`us` リージョンを使用します。処理データは一時的に米国リージョンを経由しますが、保存はされません。

#### gcloud CLIから作成する方法

```bash
# Document AI プロセッサを作成
gcloud ai document-processors create \
  --project=$PROJECT_ID \
  --location=us \
  --display-name="ic-test-ai-ocr" \
  --type="OCR_PROCESSOR"
```

✅ **期待される出力**:
```
Created processor [projects/xxxx/locations/us/processors/xxxxxxxxxx].
```

プロセッサIDをメモしてください（`processors/` の後の値）。

### 環境変数の設定

```bash
# .envファイルに追加
echo "OCR_PROVIDER=GCP" >> .env
echo "GCP_DOCAI_PROJECT_ID=ic-test-ai-xxxxxx" >> .env
echo "GCP_DOCAI_LOCATION=us" >> .env
echo "GCP_DOCAI_PROCESSOR_ID=<プロセッサID>" >> .env
```

### Python SDKでのテスト

```bash
# 必要なパッケージをインストール
pip install google-cloud-documentai
```

```python
# test_document_ai.py - Document AIテスト用スクリプト
from google.cloud import documentai_v1 as documentai

project_id = "ic-test-ai-xxxxxx"       # あなたのプロジェクトID
location = "us"                          # Document AIリージョン
processor_id = "xxxxxxxxxx"              # プロセッサID

# クライアント初期化
client = documentai.DocumentProcessorServiceClient()
name = f"projects/{project_id}/locations/{location}/processors/{processor_id}"

# テスト用PDFを読み込み（サンプルファイルが必要）
with open("test_document.pdf", "rb") as f:
    file_content = f.read()

raw_document = documentai.RawDocument(
    content=file_content,
    mime_type="application/pdf"
)
request = documentai.ProcessRequest(name=name, raw_document=raw_document)

result = client.process_document(request=request)
print(f"抽出されたテキスト ({len(result.document.text)} 文字):")
print(result.document.text[:500])
```

### 対応フォーマット

| フォーマット | MIMEタイプ | 対応状況 |
|-------------|-----------|---------|
| PDF | `application/pdf` | ✅ |
| JPEG | `image/jpeg` | ✅ |
| PNG | `image/png` | ✅ |
| TIFF | `image/tiff` | ✅ |
| BMP | `image/bmp` | ✅ |
| GIF | `image/gif` | ✅ |
| WebP | `image/webp` | ✅ |

💡 PDFの場合、最大15ページまで同期処理が可能です。15ページ以上の場合は非同期処理（Batch Processing）が必要です。

---

## 9. Apigee

### 📖 API管理とは

API管理は、公開するAPIの認証、レート制限（1分間に何回まで呼び出し可能か）、ログ記録、分析などを一元的に管理する仕組みです。APIの「門番」のような役割を果たします。

### 📖 Apigee とは

ApigeeはGCPのフルマネージドAPI管理プラットフォームです。本システムでは以下の機能を提供します。

| 機能 | 説明 |
|------|------|
| **API Key認証** | 不正アクセスを防止 |
| **レート制限** | 1分間に100リクエストまで |
| **相関ID管理** | `X-Correlation-ID` ヘッダーの付与・伝播 |
| **ログ統合** | Cloud Loggingへの自動ログ送信 |
| **Cloud Run連携** | バックエンドへのルーティング |

⚠️ **コスト注意**: Apigeeは評価版期間外では**月額$4.50〜**の課金が発生します。開発段階ではApigeeなしでCloud Runに直接アクセスする構成を推奨します。

### 評価版 vs 本番

| 項目 | 評価版 | 本番環境 |
|------|--------|----------|
| 費用 | **無料**（60日間） | 月額$4.50〜 |
| 制限 | 一部機能制限あり | フル機能 |
| 推奨用途 | 開発・テスト | 本番運用 |

### Apigeeのセットアップ（評価版）

#### Step 1: Apigee組織の作成

```bash
# GCP Console → Apigee → "Get started with a free evaluation"
# または以下のコマンドで組織をプロビジョニング
gcloud apigee organizations provision \
  --project=$PROJECT_ID \
  --authorized-network=default \
  --runtime-location=asia-northeast1 \
  --analytics-region=asia-northeast1
```

💡 組織のプロビジョニングには **30分〜1時間** かかります。GCP Consoleの画面で進捗を確認できます。

⚠️ 評価版を開始する前に、請求先アカウントが有効であることを確認してください。

#### Step 2: 環境の作成

```bash
# Apigee環境を作成
gcloud apigee environments create prod \
  --organization=$PROJECT_ID \
  --display-name="ic-test-ai-prod"
```

✅ **期待される出力**:
```
Created environment [prod].
```

#### Step 3: 環境グループの作成

```bash
# 環境グループ（ホスト名とAPIプロキシのマッピング）
gcloud apigee envgroups create ic-test-ai-prod-group \
  --organization=$PROJECT_ID \
  --hostnames="ic-test-ai-api.example.com"

# 環境グループに環境を紐付け
gcloud apigee envgroups attachments create \
  --organization=$PROJECT_ID \
  --envgroup=ic-test-ai-prod-group \
  --environment=prod
```

#### Step 4: APIプロキシの作成

APIプロキシは、クライアントのリクエストをCloud Runに転送する「中継器」です。

```bash
# Apigee Console（Web UI）でAPIプロキシを作成
# 1. https://apigee.google.com/ にアクセス
# 2. 組織を選択
# 3. Develop → API Proxies → + Create New
# 4. Reverse proxy を選択
# 5. 以下を設定:
#    - Proxy name: ic-test-ai-evaluate
#    - Base path: /api
#    - Target URL: <Cloud RunのURL>
# 6. ポリシーを追加:
#    - Verify API Key（リクエスト時にAPIキーを検証）
#    - Assign Message（X-Correlation-IDヘッダーを付与）
#    - Quota（レート制限: 100回/分）
```

💡 Apigeeのプロキシ設定はXML形式で定義されます。GUIから設定するのが簡単です。

#### Step 5: API製品の作成

```bash
# GCP Console → Apigee → Publish → API Products → + API Product
# 名前: ic-test-ai-prod-product
# 環境: prod
# レート制限: 100回/分
# APIリソース: /**
```

#### Step 6: 開発者アプリの作成とAPIキー取得

```bash
# GCP Console → Apigee → Publish → Apps → + App
# App名: ic-test-ai-prod-app
# 開発者: 管理者メールアドレス
# API製品: ic-test-ai-prod-product

# 作成後、「Credentials」セクションから Consumer Key（APIキー）を取得
```

✅ Consumer Key（APIキー）をメモしてください。クライアントからのリクエストで使用します。

### Apigee未使用の場合（推奨: 開発段階）

Apigeeなしでも本システムは動作します。Cloud Runに直接アクセスする場合は、Terraform変数で `enable_apigee = false`（デフォルト）を設定します。

```bash
# Cloud Runに直接アクセス
SERVICE_URL=$(gcloud run services describe ic-test-ai-prod \
  --region=asia-northeast1 \
  --format="value(status.url)")

curl -X POST "${SERVICE_URL}/api/evaluate" \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: test-corr-001" \
  -d '{"test_data": "sample"}'
```

💡 Apigeeなしの場合、レート制限や API Key認証はCloud Run内で実装するか、Cloud Armor + Cloud Load Balancerで代替できます。

---

## 10. Secret Manager

### 📖 Secret Manager とは

Secret Managerは、APIキーやパスワードなどの機密情報を安全に保存・管理するGCPサービスです。ソースコードに機密情報を書く代わりに、Secret Managerに保存し、必要な時だけプログラムから取得します。

| 方法 | セキュリティ | 推奨度 |
|------|-------------|--------|
| ソースコードに直接記述 | 非常に危険 | NG |
| 環境変数 | 低セキュリティ | 開発のみ |
| `.env` ファイル | 中セキュリティ | ローカル開発 |
| **Secret Manager** | **高セキュリティ** | **本番推奨** |

### シークレットの作成

```bash
# Vertex AI APIキー用のシークレットを作成
echo -n "YOUR_VERTEX_AI_API_KEY" | \
  gcloud secrets create ic-test-ai-prod-vertex-ai-api-key \
    --data-file=- \
    --replication-policy="automatic" \
    --project=$PROJECT_ID

# Document AI APIキー用のシークレットを作成
echo -n "YOUR_DOCUMENT_AI_API_KEY" | \
  gcloud secrets create ic-test-ai-prod-document-ai-api-key \
    --data-file=- \
    --replication-policy="automatic" \
    --project=$PROJECT_ID

# OpenAI APIキー（フォールバック用、オプション）
echo -n "YOUR_OPENAI_API_KEY" | \
  gcloud secrets create ic-test-ai-prod-openai-api-key \
    --data-file=- \
    --replication-policy="automatic" \
    --project=$PROJECT_ID
```

✅ **期待される出力**（各コマンドに対して）:
```
Created secret [ic-test-ai-prod-vertex-ai-api-key].
Created version [1] of the secret [ic-test-ai-prod-vertex-ai-api-key].
```

💡 `--replication-policy="automatic"` は、GCPが自動的に複数リージョンにデータを複製してくれる設定です。可用性が高くなります。

### シークレットの確認

```bash
# シークレット一覧を表示
gcloud secrets list --project=$PROJECT_ID

# シークレットの値を確認（デバッグ用）
gcloud secrets versions access latest \
  --secret=ic-test-ai-prod-vertex-ai-api-key \
  --project=$PROJECT_ID
```

### シークレットの更新（新バージョン追加）

```bash
# 新しい値でバージョンを追加
echo -n "NEW_API_KEY_VALUE" | \
  gcloud secrets versions add ic-test-ai-prod-vertex-ai-api-key \
    --data-file=- \
    --project=$PROJECT_ID
```

✅ **期待される出力**:
```
Created version [2] of the secret [ic-test-ai-prod-vertex-ai-api-key].
```

📖 Secret Managerはバージョン管理をサポートしています。古いバージョンに戻すことも可能です。

### IAM権限の設定

Cloud Runのサービスアカウントが Secret Manager にアクセスできるようにします（セクション4で設定済みの場合はスキップ可能）。

```bash
# 個別シークレットへのアクセス権限を付与
gcloud secrets add-iam-policy-binding ic-test-ai-prod-vertex-ai-api-key \
  --member="serviceAccount:ic-test-ai-prod-run-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor" \
  --project=$PROJECT_ID
```

### Python SDKからのアクセス（テスト）

```bash
pip install google-cloud-secret-manager
```

```python
# test_secret_manager.py - Secret Managerアクセステスト
from google.cloud import secretmanager

project_id = "ic-test-ai-xxxxxx"  # あなたのプロジェクトID
secret_id = "ic-test-ai-prod-vertex-ai-api-key"

client = secretmanager.SecretManagerServiceClient()
name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"

response = client.access_secret_version(request={"name": name})
secret_value = response.payload.data.decode("utf-8")
print(f"シークレット取得成功: {secret_value[:4]}****")
```

✅ **期待される出力**:
```
シークレット取得成功: YOUR****
```

本システムの `src/infrastructure/secrets/gcp_secrets.py` では `GCPSecretManagerProvider` クラスがこの機能をラップしています。リトライ機能付きで環境変数へのフォールバックも対応しています。

---

## 11. Cloud Logging / Cloud Trace

### 📖 Cloud Logging とは

Cloud Loggingは、GCPリソースのログを一元的に収集・検索・分析するサービスです。Cloud Runの実行ログ、エラーログ、カスタムログをすべてここで確認できます。

### 📖 Cloud Trace とは

Cloud Traceは、リクエストの処理経路（どのサービスをどの順番で呼び出したか）を可視化する分散トレーシングサービスです。パフォーマンスのボトルネックを特定するのに役立ちます。

### Cloud Loggingの確認

#### GCP Consoleから確認

1. [https://console.cloud.google.com/logs](https://console.cloud.google.com/logs) にアクセス
2. リソースタイプを「Cloud Run Revision」に設定
3. サービス名でフィルタリング

#### gcloud CLIから確認

```bash
# Cloud Runの最新ログを表示（直近10件）
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="ic-test-ai-prod"' \
  --project=$PROJECT_ID \
  --limit=10 \
  --format="table(timestamp, severity, textPayload)"
```

✅ **期待される出力**:
```
TIMESTAMP                    SEVERITY  TEXT_PAYLOAD
2026-02-11T12:00:00.000Z     INFO      Container started
2026-02-11T12:00:01.000Z     INFO      GCP Cloud Logging/Trace監視を初期化しました
2026-02-11T12:00:05.000Z     INFO      Request processed in 5000 ms
```

### Cloud Loggingのクエリ構文

Cloud Loggingでは、ログの検索にフィルター構文を使用します。

```
# Cloud Runのエラーログ
resource.type="cloud_run_revision"
resource.labels.function_name="ic-test-ai-prod-evaluate"
severity>=ERROR

# 特定の相関IDのログ
resource.type="cloud_run_revision"
jsonPayload.correlation_id="corr-12345-abcde"

# 直近1時間のログ
resource.type="cloud_run_revision"
timestamp>="2026-02-11T11:00:00Z"
```

💡 GCP Console → Cloud Logging → ログエクスプローラー に上記のクエリを入力して使います。

### Cloud Traceの確認

#### GCP Consoleから確認

1. [https://console.cloud.google.com/traces](https://console.cloud.google.com/traces) にアクセス
2. トレース一覧から確認したいトレースをクリック
3. 各スパン（処理ステップ）の実行時間が可視化されます

#### 本システムでのトレース構造

本システムの `src/infrastructure/monitoring/gcp_monitoring.py` では、OpenCensusを使用してCloud Traceにトレースを送信しています。

```
[クライアントリクエスト]
  └── [Cloud Run: evaluate]  ← ルートスパン
       ├── [Vertex AI: gemini-3-pro invocation]  ← AI推論スパン
       ├── [Document AI: OCR processing]  ← OCR処理スパン
       └── [Secret Manager: get secret]  ← シークレット取得スパン
```

💡 トレースのサンプリングレートはデフォルトで10%に設定されています（コスト最適化のため）。全リクエストをトレースする場合は、`gcp_monitoring.py` の `ProbabilitySampler(0.1)` を `ProbabilitySampler(1.0)` に変更してください。

### 基本的なクエリの実行

```bash
# gcloud CLIでログを検索
gcloud logging read \
  'resource.type="cloud_run_revision" AND severity>=ERROR' \
  --project=$PROJECT_ID \
  --limit=5 \
  --format="table(timestamp, severity, textPayload)"
```

✅ **期待される出力**（エラーがない場合）:
```
Listed 0 items.
```

### Cloud Monitoringダッシュボード

Terraformデプロイ後、自動的に以下のダッシュボードが作成されます。

| ウィジェット | 説明 |
|-------------|------|
| Cloud Run リクエスト数 | 1分ごとのリクエスト数 |
| Cloud Run エラー率 | エラー発生率 |
| Cloud Run レイテンシ | 平均処理時間 |

ダッシュボードURL:
```
https://console.cloud.google.com/monitoring/dashboards?project=<YOUR_PROJECT_ID>
```

### アラート設定

Terraformデプロイ後、以下のアラートが自動作成されます。

| アラート | 条件 | 説明 |
|---------|------|------|
| エラー率アラート | 5分間にエラー10回以上 | 異常なエラー発生時に通知 |
| 実行時間アラート | 平均3分以上 | パフォーマンス低下時に通知 |

💡 通知先（メール、Slack等）は、Terraformデプロイ後にGCP Console → Cloud Monitoring → アラートポリシーから設定してください。

---

## 12. Cloud Storage

### 📖 Cloud Storage とは

Cloud Storageは、GCPのオブジェクトストレージサービスです。ファイル（画像、PDF、ZIPなど）をクラウド上に保存・管理できます。本システムでは以下の用途で使用します。

| 用途 | バケット名 | 説明 |
|------|-----------|------|
| 証跡・ジョブ結果 | `ic-test-ai-prod-artifacts-*` | 証跡ファイルやジョブ結果の保存 |
| Terraformステート | `ic-test-ai-terraform-state` | Terraformの状態管理ファイル |

### バケットの作成

```bash
# 証跡・ジョブ結果用バケット（Terraform管理ではない場合の手動作成）
gcloud storage buckets create gs://ic-test-ai-prod-artifacts-${PROJECT_ID} \
  --project=$PROJECT_ID \
  --location=asia-northeast1 \
  --uniform-bucket-level-access

# Terraform State用バケット
gcloud storage buckets create gs://ic-test-ai-terraform-state \
  --project=$PROJECT_ID \
  --location=asia-northeast1 \
  --uniform-bucket-level-access

# バージョニングを有効化（Terraform State保護のため）
gcloud storage buckets update gs://ic-test-ai-terraform-state \
  --versioning
```

✅ **期待される出力**:
```
Creating gs://ic-test-ai-prod-artifacts-ic-test-ai-xxxxxx/...
Creating gs://ic-test-ai-terraform-state/...
Updating gs://ic-test-ai-terraform-state/...
```

📖 **バケット名はグローバルで一意** である必要があります。既に使用されている名前は使えないため、プロジェクトIDを含めることで一意性を確保しています。

### Python SDKからのアクセス

```bash
pip install google-cloud-storage
```

```python
# test_storage.py - Cloud Storageアクセステスト
from google.cloud import storage

client = storage.Client(project="ic-test-ai-xxxxxx")

# バケット一覧を表示
for bucket in client.list_buckets():
    print(f"バケット: {bucket.name}")

# ファイルのアップロード
bucket = client.bucket("ic-test-ai-prod-artifacts-ic-test-ai-xxxxxx")
blob = bucket.blob("test/hello.txt")
blob.upload_from_string("Hello, Cloud Storage!")
print("アップロード完了!")

# ファイルのダウンロード
content = blob.download_as_text()
print(f"ダウンロード内容: {content}")

# クリーンアップ
blob.delete()
print("テストファイルを削除しました")
```

### ライフサイクルルール

Terraformでは、90日後に古いオブジェクトが自動削除されるライフサイクルルールが設定されています（`storage_lifecycle_age = 90`）。

```bash
# ライフサイクルルールの確認
gcloud storage buckets describe gs://ic-test-ai-prod-artifacts-${PROJECT_ID} \
  --format="yaml(lifecycle)"
```

---

## 13. Terraformデプロイ

### 📖 Terraform とは

Terraformは、**Infrastructure as Code（IaC）** ツールです。クラウドリソースの構成を `.tf` ファイル（テキストファイル）に記述し、コマンド一つで環境を構築・変更・削除できます。

| 操作 | 手動（GCP Console） | Terraform |
|------|---------------------|-----------|
| 構築 | 画面操作を1つずつ実行 | `terraform apply` 1コマンド |
| 変更 | 画面で修正 | `.tf` ファイルを編集 → `terraform apply` |
| 削除 | 画面で削除 | `terraform destroy` 1コマンド |
| 再現性 | 操作手順書が必要 | コードが手順書の代わり |

### Terraformのインストール

#### Windows

```bash
# wingetでインストール
winget install HashiCorp.Terraform

# または Chocolateyでインストール
choco install terraform
```

#### Mac

```bash
brew install terraform
```

#### Linux

```bash
wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install terraform
```

### インストール確認

```bash
terraform version
```

✅ **期待される出力**:
```
Terraform v1.7.x
on windows_amd64
```

### プロジェクトのTerraform構成

本プロジェクトのTerraformファイルは `infrastructure/gcp/terraform/` ディレクトリにあります。

```
infrastructure/gcp/terraform/
├── backend.tf          # Terraform設定・プロバイダー定義
├── variables.tf        # 変数定義（プロジェクトID、リージョン等）
├── cloud-run.tf        # Cloud Run サービスリソース
├── secret-manager.tf   # Secret Manager・サービスアカウント
├── apigee.tf           # Apigee API管理（オプション）
├── cloud-logging.tf    # Cloud Logging/Monitoring アラート
└── outputs.tf          # 出力定義（URLなど）
```

### 変数ファイルの作成

```bash
# infrastructure/gcp/terraform/ ディレクトリに移動
cd infrastructure/gcp/terraform
```

`terraform.tfvars` ファイルを作成します。

```hcl
# terraform.tfvars - あなたのプロジェクト固有の設定

project_id   = "ic-test-ai-xxxxxx"    # あなたのGCPプロジェクトID
project_name = "ic-test-ai"
environment  = "prod"
region       = "asia-northeast1"

# Cloud Run設定
cloud_run_cpu       = "1"
cloud_run_memory    = "1Gi"
cloud_run_timeout   = 540
cloud_run_max_instances = 10
cloud_run_min_instances = 0

# Apigee（オプション: 開発段階ではfalse推奨）
enable_apigee = false

# Secret Manager（実際のAPIキーに置き換え）
vertex_ai_api_key   = "YOUR_VERTEX_AI_API_KEY"   # pragma: allowlist secret
document_ai_api_key = "YOUR_DOCUMENT_AI_API_KEY"  # pragma: allowlist secret
openai_api_key      = ""

# Cloud Logging設定
log_retention_days = 30
enable_cloud_trace = true

# コスト制御
enable_monitoring_alerts = true
budget_amount            = 100
```

⚠️ `terraform.tfvars` にはAPIキーが含まれるため、**Gitにコミットしないでください**。`.gitignore` に `terraform.tfvars` が含まれていることを確認しましょう。

### Terraform初期化

```bash
terraform init
```

✅ **期待される出力**:
```
Initializing the backend...

Initializing provider plugins...
- Finding hashicorp/google versions matching "~> 5.0"...
- Installing hashicorp/google v5.xx.x...
- Installed hashicorp/google v5.xx.x (signed by HashiCorp)

Terraform has been successfully initialized!
```

### デプロイ計画の確認（plan）

```bash
terraform plan -out=tfplan
```

📖 `terraform plan` は、実際にリソースを作成せずに「何が作成されるか」を表示するドライランコマンドです。本番環境では必ず plan を確認してから apply してください。

✅ **期待される出力**:
```
Terraform will perform the following actions:

  # google_cloud_run_v2_service.evaluate will be created
  + resource "google_cloud_run_v2_service" "evaluate" {
      + name     = "ic-test-ai-prod-evaluate"
      + location = "asia-northeast1"
      ...
    }

  # google_secret_manager_secret.vertex_ai_api_key will be created
  ...

  # google_service_account.cloud_run will be created
  ...

Plan: XX to add, 0 to change, 0 to destroy.
```

💡 `Plan: XX to add` の数字は作成されるリソース数です。内容を確認して問題なければ次のステップに進みます。

### デプロイ実行（apply）

```bash
terraform apply tfplan
```

✅ **期待される出力**:
```
google_service_account.cloud_run: Creating...
google_service_account.cloud_run: Creation complete after 2s
google_secret_manager_secret.vertex_ai_api_key: Creating...
google_secret_manager_secret.vertex_ai_api_key: Creation complete after 1s
...

Apply complete! Resources: XX added, 0 changed, 0 destroyed.

Outputs:

cloud_run_endpoint = "https://ic-test-ai-prod-evaluate-xxxxxxxx-an.a.run.app/evaluate"
cloud_logging_url = "https://console.cloud.google.com/logs/query;..."
cloud_trace_url = "https://console.cloud.google.com/traces/list?project=..."
service_name = "ic-test-ai-prod-evaluate"
project_id = "ic-test-ai-xxxxxx"
...
```

### 出力値の確認

```bash
# Terraformの出力値を確認
terraform output

# 特定の出力値を取得
terraform output cloud_run_endpoint
terraform output cloud_logging_url
```

### Terraform Stateのリモートバックエンド設定（推奨）

初回デプロイ後、Terraform Stateをクラウド上で管理することを推奨します。

1. `backend.tf` のコメントアウトされているバックエンド設定を有効化:

```hcl
terraform {
  # コメントを外す
  backend "gcs" {
    bucket = "ic-test-ai-terraform-state"
    prefix = "prod/terraform.tfstate"
  }
}
```

2. バックエンドの移行:

```bash
terraform init -reconfigure
```

### リソースの削除（destroy）

⚠️ **注意**: 以下のコマンドは全てのリソースを削除します。本番環境では慎重に実行してください。

```bash
# リソースの削除計画を確認
terraform plan -destroy

# リソースを削除
terraform destroy
```

確認プロンプトで `yes` を入力すると、全リソースが削除されます。

### よくあるエラーと対処法

| エラー | 原因 | 対処法 |
|--------|------|--------|
| `Error: Error creating Secret` | Secret Managerが未有効化 | セクション5のAPI有効化を実行 |
| `Error: googleapi: Error 403` | 権限不足 | 自分のアカウントに `roles/editor` を付与 |
| `Error: Error creating Service` | Artifact Registry API未有効化 | `gcloud services enable artifactregistry.googleapis.com` |
| `Error: Quota exceeded` | プロジェクトのクォータ超過 | GCP Consoleでクォータ増加をリクエスト |
| `State lock error` | 他のTerraform実行が進行中 | `terraform force-unlock <LOCK_ID>` |

---

## 14. 統合テスト

### テスト用環境変数の設定

```bash
# Cloud RunのエンドポイントURLを取得
export SERVICE_URL=$(terraform output -raw cloud_run_endpoint)

# Apigee使用時（オプション）
# export GCP_APIGEE_ENDPOINT="https://<APIGEE_ENDPOINT>"
# export GCP_API_KEY="<API_KEY>"

export GCP_PROJECT=$PROJECT_ID
```

### ヘルスチェック

```bash
curl -s "${SERVICE_URL%/evaluate}/health" | python -m json.tool
```

✅ **期待される出力**:
```json
{
    "status": "healthy",
    "platform": "gcp",
    "version": "1.0.0",
    "llm_provider": "GCP",
    "ocr_provider": "GCP"
}
```

### 設定確認

```bash
curl -s "${SERVICE_URL%/evaluate}/config" | python -m json.tool
```

✅ **期待される出力**:
```json
{
    "llm_provider": "GCP",
    "llm_model": "gemini-3-pro-preview",
    "ocr_provider": "GCP",
    "region": "asia-northeast1"
}
```

### /evaluate エンドポイントテスト

```bash
# 評価リクエストを送信
curl -X POST "${SERVICE_URL}" \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: test-integration-001" \
  -d '{
    "control_description": "購買承認プロセスにおいて、10万円以上の購買は部長承認が必要",
    "test_procedure": "サンプル25件の購買伝票を抽出し、承認者と金額を確認",
    "test_result": "25件中24件は適切に部長承認が得られていた。1件（伝票番号PO-2025-0842）は15万円の購買であったが、課長承認のみであった。",
    "task_type": "a1_semantic_search"
  }' | python -m json.tool
```

✅ **期待される出力**（例）:
```json
{
    "correlation_id": "test-integration-001",
    "status": "completed",
    "evaluation": {
        "result": "不備あり",
        "confidence": 0.95,
        "reasoning": "25件中1件（PO-2025-0842）で承認レベルの不備が確認されました...",
        "recommendations": [
            "承認権限テーブルの確認と是正",
            "システム制御の強化"
        ]
    },
    "processing_time_ms": 3500
}
```

### 相関IDの確認（Cloud Loggingで追跡）

```bash
# 相関IDで Cloud Logging を検索
gcloud logging read \
  'resource.type="cloud_run_revision" AND jsonPayload.correlation_id="test-integration-001"' \
  --project=$PROJECT_ID \
  --limit=10 \
  --format="table(timestamp, severity, jsonPayload.message)"
```

✅ 相関ID `test-integration-001` でフィルタリングされたログが表示されれば、エンドツーエンドのトレーサビリティが確保されています。

### 非同期評価テスト

```bash
# 非同期で評価をサブミット
JOB_RESPONSE=$(curl -s -X POST "${SERVICE_URL%/evaluate}/evaluate/submit" \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: test-async-001" \
  -d '{
    "control_description": "月次の在庫棚卸を実施し、帳簿残高との差異を確認する",
    "test_procedure": "直近6ヶ月の棚卸結果と帳簿残高の照合を実施",
    "test_result": "6ヶ月中5ヶ月は差異率0.5%以内であったが、3月は差異率2.3%であった"
  }')
echo $JOB_RESPONSE | python -m json.tool

# ジョブIDを取得
JOB_ID=$(echo $JOB_RESPONSE | python -c "import sys,json; print(json.load(sys.stdin)['job_id'])")

# ステータスを確認
curl -s "${SERVICE_URL%/evaluate}/evaluate/status/${JOB_ID}" | python -m json.tool

# 結果を取得（処理完了後）
curl -s "${SERVICE_URL%/evaluate}/evaluate/results/${JOB_ID}" | python -m json.tool
```

### デプロイ検証スクリプト

```bash
# プロジェクトルートに戻って検証スクリプトを実行
python scripts/validate_deployment.py --platform gcp
```

---

## 15. コスト管理

### GCPの無料枠

| サービス | 無料枠 | 超過時の料金 |
|---------|--------|-------------|
| Cloud Run | 180,000 vCPU秒/月, 360,000 GiB秒/月 | $0.00002400/vCPU秒 |
| Cloud Logging | 50GiB/月 | $0.50/GiB |
| Cloud Trace | 250万スパン/月 | $0.20/100万スパン |
| Cloud Storage | 5GB/月 | $0.020/GB |
| Secret Manager | 6アクティブバージョン | $0.06/バージョン/月 |
| Cloud Build | 120分/日 | $0.003/分 |

### 月額見積もり（本システム）

| サービス | 想定使用量 | 月額見積もり |
|---------|-----------|------------|
| Cloud Run | 3,000リクエスト/月 | ¥0（無料枠内） |
| Vertex AI (Gemini 3 Pro) | 100回/月 | 約¥100〜¥200 |
| Document AI | 50ページ/月 | 約¥50 |
| Cloud Logging | 1GB/月 | ¥0（無料枠内） |
| Cloud Trace | 1,000スパン/月 | ¥0（無料枠内） |
| Secret Manager | 3シークレット | ¥0（無料枠内） |
| Cloud Storage | 100MB/月 | ¥0（無料枠内） |
| Cloud Monitoring | アラート2件 | 約¥200 |
| **合計** | | **約¥350〜¥450** |

💡 Apigee評価版を含めても、**月額約¥1,300** が上限の見積もりです。3つのクラウドプラットフォーム（Azure、AWS、GCP）の中で最もコスト効率が良いです。

### 予算アラートの設定

Terraformデプロイで自動的に予算アラートが設定されます。

| 閾値 | アクション |
|------|-----------|
| 50%到達 | メール通知 |
| 90%到達 | メール通知 |
| 100%到達 | メール通知 |

```bash
# 予算アラートの確認
gcloud billing budgets list --billing-account=$(gcloud billing accounts list --format="value(name)" --limit=1)
```

### コスト最適化のヒント

1. **Cloud Runの最小インスタンスを0にする**: 使わない時はインスタンスが起動しないため課金されません（Terraform設定済み）。
2. **Gemini 2.5 Flash / Flash Liteを使用する**: 高精度が不要な場合は、軽量モデルでコストを削減できます。
3. **Cloud Traceのサンプリングレートを下げる**: デフォルトの10%で十分です。
4. **Cloud Storageのライフサイクルルール**: 90日後に自動削除（Terraform設定済み）。
5. **Apigee評価版を活用**: 開発段階では無料の評価版を使用しましょう。

### リソースの削除（コスト停止）

使用しなくなったリソースは速やかに削除しましょう。

```bash
# Terraformで全リソースを削除
cd infrastructure/gcp/terraform
terraform destroy

# 手動で作成したリソースの削除
gcloud storage rm -r gs://ic-test-ai-terraform-state
gcloud storage rm -r gs://ic-test-ai-prod-artifacts-${PROJECT_ID}

# プロジェクト自体の削除（全リソースが削除されます）
# ⚠️ 復旧不可能なため慎重に実行してください
# gcloud projects delete $PROJECT_ID
```

⚠️ プロジェクトの削除は30日間の猶予期間があり、その間は復元可能です。

---

## 16. まとめ・次のステップ

### セットアップ完了チェックリスト

| 項目 | 確認 |
|------|------|
| GCPアカウント作成・プロジェクト作成 | ☐ |
| gcloud CLIインストール・認証設定 | ☐ |
| サービスアカウント作成・ロール付与 | ☐ |
| 必要なAPI有効化 | ☐ |
| Cloud Run デプロイ | ☐ |
| Vertex AI 接続テスト | ☐ |
| Document AI プロセッサ作成 | ☐ |
| Secret Manager シークレット設定 | ☐ |
| Cloud Storage バケット作成 | ☐ |
| Terraform デプロイ | ☐ |
| 統合テスト（ヘルスチェック・/evaluate） | ☐ |
| Cloud Logging でログ確認 | ☐ |

### 学んだGCPスキル

このガイドを通じて、以下のGCPスキルを習得しました。

- **gcloud CLI**: GCPリソースのコマンドライン操作
- **IAM**: 権限管理とサービスアカウント
- **Cloud Run**: コンテナアプリケーション
- **Vertex AI**: AI/MLモデルの利用
- **Document AI**: OCR・文書処理
- **Secret Manager**: 機密情報の管理
- **Cloud Logging/Trace**: 監視・トレーシング
- **Cloud Storage**: オブジェクトストレージ
- **Terraform**: Infrastructure as Code

### 次のステップ

1. **本番環境の強化**: Apigeeの本番設定、カスタムドメイン設定
2. **CI/CDパイプライン**: Cloud Buildでの自動デプロイ
3. **他プラットフォームの構築**: [Azure セットアップガイド](./AZURE_SETUP.md)、[AWS セットアップガイド](./AWS_SETUP.md) を参照
4. **運用ガイド**: [デプロイメントガイド](../operations/DEPLOYMENT_GUIDE.md) を参照

### 参考資料

| 資料 | URL |
|------|-----|
| GCP公式ドキュメント | [https://cloud.google.com/docs](https://cloud.google.com/docs) |
| Cloud Run ドキュメント | [https://cloud.google.com/run/docs](https://cloud.google.com/run/docs) |
| Vertex AI ドキュメント | [https://cloud.google.com/vertex-ai/docs](https://cloud.google.com/vertex-ai/docs) |
| Document AI ドキュメント | [https://cloud.google.com/document-ai/docs](https://cloud.google.com/document-ai/docs) |
| Terraform GCPプロバイダー | [https://registry.terraform.io/providers/hashicorp/google/](https://registry.terraform.io/providers/hashicorp/google/) |
| Vertex AI 料金 | [https://cloud.google.com/vertex-ai/pricing](https://cloud.google.com/vertex-ai/pricing) |
| GCP 無料枠 | [https://cloud.google.com/free](https://cloud.google.com/free) |

---

> このガイドは [内部統制テスト評価AIシステム](../../README.md) プロジェクトの一部です。
> 質問やフィードバックは、プロジェクトのIssueでお知らせください。
