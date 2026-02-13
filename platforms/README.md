# マルチクラウドプラットフォーム対応ガイド

## 目次

1. [はじめに](#はじめに)
2. [システム概要](#システム概要)
3. [前提条件](#前提条件)
4. [ディレクトリ構成](#ディレクトリ構成)
5. [設定ファイル](#設定ファイル)
6. [初期セットアップ（共通）](#初期セットアップ共通)
7. [Azure Container Apps セットアップ](#azure-container-apps-セットアップ)
8. [GCP Cloud Run セットアップ](#gcp-cloud-run-セットアップ)
9. [AWS App Runner セットアップ](#aws-app-runner-セットアップ)
10. [ローカル/オンプレミス セットアップ](#ローカルオンプレミス-セットアップ)
11. [環境変数リファレンス](#環境変数リファレンス)
12. [Excel VBAマクロの設定](#excel-vbaマクロの設定)
13. [動作確認](#動作確認)
14. [トラブルシューティング](#トラブルシューティング)
15. [推奨構成パターン](#推奨構成パターン)

---

## はじめに

このガイドでは、内部統制テスト評価AIシステムを各クラウドプラットフォームにデプロイする方法を説明します。

### このガイドの対象者

- Azure Container Apps、GCP Cloud Run、AWS App Runner のいずれかにシステムをデプロイしたい方
- ローカル環境で開発・テストを行いたい方
- 複数のクラウドプロバイダーを比較検討している方

### 所要時間の目安

| 作業 | 時間 |
|------|------|
| 初期セットアップ（共通） | 約10分 |
| 各プラットフォームのローカル実行 | 約15分 |
| クラウドへのデプロイ | 約30分 |

---

## システム概要

### アーキテクチャ

```
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│  Excel VBA      │────▶│  クラウドAPI         │────▶│  AI (LLM)       │
│  クライアント    │◀────│  (Azure/GCP/AWS)     │◀────│  評価エンジン    │
└─────────────────┘     └──────────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │  OCR            │
                        │  (PDF/画像解析)  │
                        └─────────────────┘
```

### 処理フロー

1. **Excel VBA** がテストデータとエビデンスファイルを収集
2. **クラウドAPI** にJSON形式でリクエスト送信
3. **AI評価エンジン** がLLMを使用して評価を実行
4. **OCR** が必要に応じてPDF/画像からテキストを抽出
5. 評価結果をExcelに書き戻し

### マルチクラウド対応

このシステムは以下の4つのプラットフォームに対応しています：

| プラットフォーム | 特徴 | 推奨ケース | 詳細ガイド |
|-----------------|------|-----------|-----------|
| **Azure Container Apps** | Microsoft統合、日本語OCR強力 | Azure/Microsoft 365環境 | [Azure README](azure/README.md) |
| **GCP Cloud Run** | Gemini、高速処理 | GCP既存ユーザー | [GCP README](gcp/README.md) |
| **AWS App Runner** | Claude、豊富なサービス連携 | AWS既存ユーザー | [AWS README](aws/README.md) |
| **ローカル/オンプレミス** | Ollama、プライバシー重視、無料 | オフライン環境、機密データ | [Local README](local/README.md) |

各プラットフォームの詳細なデプロイ手順、非同期処理設定、トラブルシューティングは上記の個別ガイドを参照してください。

---

## 前提条件

### 必須ソフトウェア

以下のソフトウェアがインストールされている必要があります。

| ソフトウェア | バージョン | 確認コマンド | インストール方法 |
|-------------|-----------|-------------|-----------------|
| **Python** | 3.11以上 | `python --version` | [python.org](https://www.python.org/downloads/) |
| **pip** | 最新 | `pip --version` | Python に同梱 |
| **Git** | 最新 | `git --version` | [git-scm.com](https://git-scm.com/) |

### プラットフォーム別の追加要件

#### Docker（クラウドデプロイ時に必要）

全クラウドプラットフォームはDockerコンテナベースでデプロイします。

| ソフトウェア | 確認コマンド | インストール方法 |
|-------------|-------------|-----------------|
| Docker | `docker --version` | [Docker Desktop](https://www.docker.com/products/docker-desktop/) |

#### Azure Container Apps を使用する場合

| ソフトウェア | 確認コマンド | インストール方法 |
|-------------|-------------|-----------------|
| Azure CLI | `az --version` | [公式ドキュメント](https://docs.microsoft.com/ja-jp/cli/azure/install-azure-cli) |

#### GCP Cloud Run を使用する場合

| ソフトウェア | 確認コマンド | インストール方法 |
|-------------|-------------|-----------------|
| Google Cloud SDK | `gcloud --version` | [公式ドキュメント](https://cloud.google.com/sdk/docs/install) |

#### AWS App Runner を使用する場合

| ソフトウェア | 確認コマンド | インストール方法 |
|-------------|-------------|-----------------|
| AWS CLI | `aws --version` | [公式ドキュメント](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) |

### クラウドサービスのセットアップ

#### LLM（大規模言語モデル）

以下のいずれか1つが必要です：

| サービス | 必要なもの | 取得方法 |
|---------|-----------|---------|
| Azure AI Foundry | エンドポイントURL、APIキー | [Azure Portal](https://portal.azure.com/) → AI Foundry |
| GCP Vertex AI | プロジェクトID、サービスアカウント | [GCP Console](https://console.cloud.google.com/) |
| AWS Bedrock | リージョン、IAM権限 | [AWS Console](https://console.aws.amazon.com/) |

#### OCR（オプション）

PDF/画像からテキストを抽出する場合は以下のいずれかが必要です：

| サービス | 必要なもの | 用途 |
|---------|-----------|-----|
| Azure Document Intelligence | エンドポイントURL、キー | 高精度日本語OCR |
| AWS Textract | IAM権限 | AWS統合環境 |
| GCP Document AI | プロセッサーID | GCP統合環境 |
| Tesseract | ローカルインストール | オフライン/コスト重視 |
| なし | - | テキストベースPDFのみ |

---

## ディレクトリ構成

```
ic-test-ai-agent/
│
├── src/                              # 共通コード（全プラットフォーム共有）
│   │                                 # ※ 唯一のソースオブトゥルース
│   │                                 # ※ 各デプロイスクリプトがここからコピー
│   │
│   ├── core/                         # ビジネスロジック
│   │   ├── __init__.py
│   │   ├── handlers.py               # プラットフォーム非依存ハンドラー
│   │   ├── auditor_agent.py          # 監査エージェント
│   │   ├── graph_orchestrator.py     # LangGraphオーケストレーター
│   │   ├── document_processor.py     # ドキュメント処理
│   │   ├── highlighting_service.py   # 証跡ハイライト（PDF/Excel/テキスト）
│   │   └── tasks/                    # 評価タスク定義（A1-A8）
│   │       ├── base_task.py
│   │       ├── a1_semantic_search.py
│   │       ├── a2_image_recognition.py
│   │       ├── a3_data_extraction.py
│   │       ├── a4_stepwise_reasoning.py
│   │       ├── a5_semantic_reasoning.py
│   │       ├── a6_multi_document.py
│   │       ├── a7_pattern_analysis.py
│   │       └── a8_sod_detection.py
│   │
│   └── infrastructure/               # インフラ抽象化レイヤー
│       ├── llm_factory.py            # マルチLLM対応ファクトリー
│       ├── ocr_factory.py            # マルチOCR対応ファクトリー
│       └── job_storage/              # 非同期ジョブストレージ
│
├── platforms/                        # プラットフォーム別設定・デプロイガイド
│   │
│   ├── azure/                        # Azure Container Apps
│   │   ├── README.md                 # Azure デプロイガイド
│   │   └── deploy.ps1                # デプロイスクリプト
│   │
│   ├── gcp/                          # GCP Cloud Run
│   │   ├── README.md                 # GCP デプロイガイド
│   │   └── deploy.ps1                # デプロイスクリプト
│   │
│   ├── aws/                          # AWS App Runner
│   │   ├── README.md                 # AWS デプロイガイド
│   │   └── deploy.ps1                # デプロイスクリプト
│   │
│   └── local/                        # ローカル/オンプレミス（共通Dockerイメージ）
│       ├── main.py                   # 共通エントリーポイント（FastAPI/Uvicorn）
│       ├── Dockerfile                # 全プラットフォーム共通Dockerイメージ
│       └── requirements.txt          # Python依存関係
│
├── .env.example                      # 環境変数サンプル（★コピーして使用）
├── setting.json.example              # VBAマクロ設定サンプル（★コピーして使用）
├── requirements.txt                  # 共通Python依存関係
├── .gitignore                        # Git除外設定
└── SYSTEM_SPECIFICATION.md           # システム仕様書
```

### 各ディレクトリの役割

| ディレクトリ | 役割 | 編集が必要か |
|-------------|------|-------------|
| `src/core/` | ビジネスロジック（評価処理） | 通常は不要 |
| `src/infrastructure/` | クラウドサービス抽象化 | 通常は不要 |
| `platforms/azure/` | Azure Container Apps デプロイ設定 | 通常は不要 |
| `platforms/gcp/` | GCP Cloud Run デプロイ設定 | 通常は不要 |
| `platforms/aws/` | AWS App Runner デプロイ設定 | 通常は不要 |
| `platforms/local/` | ローカル/オンプレミス エントリーポイント | 通常は不要 |
| プロジェクトルート | 設定ファイル | **編集が必要** |

---

## 設定ファイル

### 設定ファイル一覧

このシステムでは、**環境変数は全プラットフォーム共通で `.env` ファイルを使用**します。

| ファイル | 用途 | 編集が必要か |
|---------|------|-------------|
| `.env` | サーバー側設定（LLM/OCR等） | **必須** |
| `setting.json` | クライアント側設定（Excel VBA） | VBA使用時のみ |

### `.env` ファイルとは

`.env` ファイルは、APIキーやエンドポイントなどの**機密情報を含む設定ファイル**です。

- **ローカル開発時**: 各エントリーポイントが自動的に読み込みます
- **クラウドデプロイ時**: 各クラウドの環境変数設定機能を使用します

### 環境変数の読み込みの仕組み

```
┌─────────────────────────────────────────────────────────────┐
│ ローカル開発時                                               │
│                                                             │
│   .env ファイル                                              │
│       ↓                                                     │
│   python-dotenv が読み込み                                   │
│       ↓                                                     │
│   os.environ に設定                                         │
│       ↓                                                     │
│   アプリケーションが使用                                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ クラウドデプロイ時                                           │
│                                                             │
│   クラウドの環境変数設定                                      │
│   (Azure: Container Apps --env-vars)                        │
│   (GCP: Cloud Run --set-env-vars)                           │
│   (AWS: App Runner RuntimeEnvironmentVariables)             │
│       ↓                                                     │
│   os.environ に自動設定                                      │
│       ↓                                                     │
│   アプリケーションが使用                                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 初期セットアップ（共通）

以下の手順は、どのプラットフォームを使用する場合でも最初に行ってください。

### ステップ 1: リポジトリのクローン

```bash
# リポジトリをクローン
git clone https://github.com/your-org/ic-test-ai-agent.git

# ディレクトリに移動
cd ic-test-ai-agent
```

### ステップ 2: 環境変数ファイルの作成

```bash
# サンプルファイルをコピー
cp .env.example .env
```

### ステップ 3: 環境変数の編集

`.env` ファイルをテキストエディタで開き、使用するサービスの設定を入力します。

```bash
# Windows の場合
notepad .env

# Mac/Linux の場合
nano .env
# または
code .env  # VS Code
```

#### 最小限の設定例（Azure AI Foundry を使用する場合）

```ini
# LLM設定
LLM_PROVIDER=AZURE_FOUNDRY
AZURE_FOUNDRY_ENDPOINT=https://your-project.region.models.ai.azure.com
AZURE_FOUNDRY_API_KEY=your-api-key-here
AZURE_FOUNDRY_MODEL=gpt-5-nano

# OCR設定（PDFのテキスト抽出のみの場合は NONE でOK）
OCR_PROVIDER=NONE
```

### ステップ 4: 設定の確認

環境変数が正しく設定されているか確認します：

```bash
# Windows PowerShell
Get-Content .env | Select-String "LLM_PROVIDER|OCR_PROVIDER"

# Mac/Linux
grep -E "LLM_PROVIDER|OCR_PROVIDER" .env
```

期待される出力：
```
LLM_PROVIDER=AZURE_FOUNDRY
OCR_PROVIDER=NONE
```

---

## Azure Container Apps セットアップ

### 概要

Azure Container Apps は、Microsoft のコンテナベースアプリケーションホスティングサービスです。

**メリット:**
- Azure Portal での統合管理
- Azure AI サービスとの連携が容易
- 日本語OCR（Document Intelligence）が高精度
- 全プラットフォーム共通のDockerイメージを使用

### ローカル開発環境の構築

#### ステップ 1: ディレクトリ移動

```bash
cd platforms/local
```

#### ステップ 2: 仮想環境の作成（推奨）

```bash
# 仮想環境を作成
python -m venv .venv

# 仮想環境を有効化
# Windows PowerShell の場合
.\.venv\Scripts\Activate.ps1

# Windows コマンドプロンプトの場合
.\.venv\Scripts\activate.bat

# Mac/Linux の場合
source .venv/bin/activate
```

#### ステップ 3: 依存関係のインストール

```bash
pip install -r requirements.txt
```

インストールされる主なパッケージ：
- `fastapi`: Webフレームワーク
- `uvicorn`: ASGIサーバー
- `langchain`: LLMフレームワーク
- `langchain-openai`: Azure AI Foundry 連携
- `python-dotenv`: 環境変数読み込み

#### ステップ 4: ローカルサーバーの起動

```bash
python main.py
```

成功すると以下のような出力が表示されます：

```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

#### ステップ 5: 動作確認

別のターミナルを開いて、APIをテストします：

```bash
# ヘルスチェック
curl http://localhost:8000/health

# Windows PowerShell の場合
Invoke-RestMethod -Uri http://localhost:8000/health
```

### Azure へのデプロイ

#### 前提条件

- Azure サブスクリプション
- Azure CLI がインストール済み
- Docker がインストール済み
- `az login` でログイン済み

#### ステップ 1: リソースグループの作成（初回のみ）

```bash
az group create --name rg-ic-test --location japaneast
```

#### ステップ 2: ACR（Azure Container Registry）の作成（初回のみ）

```bash
ACR_NAME="<ACR名>"
az acr create --name $ACR_NAME --resource-group rg-ic-test --sku Basic
az acr login --name $ACR_NAME
```

#### ステップ 3: Dockerイメージのビルド・プッシュ

```bash
# プロジェクトルートで実行
docker build -t "$ACR_NAME.azurecr.io/ic-test-ai:latest" -f platforms/local/Dockerfile .
docker push "$ACR_NAME.azurecr.io/ic-test-ai:latest"
```

#### ステップ 4: Container Apps環境の作成（初回のみ）

```bash
az containerapp env create \
  --name ic-test-env \
  --resource-group rg-ic-test \
  --location japaneast
```

#### ステップ 5: Container Appsの作成・デプロイ

```bash
az containerapp create \
  --name ic-test-eval \
  --resource-group rg-ic-test \
  --environment ic-test-env \
  --image "$ACR_NAME.azurecr.io/ic-test-ai:latest" \
  --registry-server "$ACR_NAME.azurecr.io" \
  --target-port 8000 \
  --ingress external \
  --cpu 1.0 --memory 2.0Gi \
  --min-replicas 0 --max-replicas 3 \
  --env-vars \
    LLM_PROVIDER=AZURE_FOUNDRY \
    AZURE_FOUNDRY_ENDPOINT=https://your-project.region.models.ai.azure.com \
    AZURE_FOUNDRY_API_KEY=your-api-key \
    AZURE_FOUNDRY_MODEL=gpt-5-nano \
    OCR_PROVIDER=NONE
```

#### ステップ 6: 更新デプロイ（2回目以降）

```bash
# イメージをビルド・プッシュ
docker build -t "$ACR_NAME.azurecr.io/ic-test-ai:latest" -f platforms/local/Dockerfile .
docker push "$ACR_NAME.azurecr.io/ic-test-ai:latest"

# Container Appsを更新
az containerapp update \
  --name ic-test-eval \
  --resource-group rg-ic-test \
  --image "$ACR_NAME.azurecr.io/ic-test-ai:latest"
```

---

## GCP Cloud Run セットアップ

### 概要

GCP Cloud Run は、Google のコンテナベースアプリケーションホスティングサービスです。

**メリット:**
- Gemini モデルへのアクセス
- 高速な応答時間
- GCP の他サービスとの連携
- 全プラットフォーム共通のDockerイメージを使用

### ローカル開発環境の構築

#### ステップ 1: ディレクトリ移動

```bash
cd platforms/local
```

#### ステップ 2: 仮想環境の作成（推奨）

```bash
python -m venv .venv

# Windows
.\.venv\Scripts\Activate.ps1

# Mac/Linux
source .venv/bin/activate
```

#### ステップ 3: 依存関係のインストール

```bash
pip install -r requirements.txt
```

#### ステップ 4: ローカルサーバーの起動

```bash
python main.py
```

成功すると以下のような出力が表示されます：

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### GCP へのデプロイ

#### 前提条件

- GCP プロジェクト
- Docker がインストール済み
- `gcloud auth login` でログイン済み
- Cloud Run API が有効化済み

#### ステップ 1: Artifact Registry リポジトリ作成（初回のみ）

```bash
gcloud artifacts repositories create ic-test-ai \
  --repository-format=docker \
  --location=asia-northeast1 \
  --description="IC Test AI Docker images"

gcloud auth configure-docker asia-northeast1-docker.pkg.dev
```

#### ステップ 2: Dockerイメージのビルド・プッシュ

```bash
PROJECT_ID="your-project-id"
AR_REPO="asia-northeast1-docker.pkg.dev/$PROJECT_ID/ic-test-ai"

# プロジェクトルートで実行
docker build -t "${AR_REPO}/ic-test-ai:latest" -f platforms/local/Dockerfile .
docker push "${AR_REPO}/ic-test-ai:latest"
```

#### ステップ 3: Cloud Run サービスの作成・デプロイ

```bash
gcloud run deploy ic-test-evaluate \
  --image="${AR_REPO}/ic-test-ai:latest" \
  --region=asia-northeast1 \
  --port=8000 \
  --cpu=1 \
  --memory=2Gi \
  --timeout=540 \
  --min-instances=0 \
  --max-instances=3 \
  --allow-unauthenticated \
  --set-env-vars "LLM_PROVIDER=GCP,GCP_PROJECT_ID=$PROJECT_ID,OCR_PROVIDER=NONE"
```

#### ステップ 4: 更新デプロイ（2回目以降）

```bash
# イメージをビルド・プッシュ
docker build -t "${AR_REPO}/ic-test-ai:latest" -f platforms/local/Dockerfile .
docker push "${AR_REPO}/ic-test-ai:latest"

# Cloud Runサービスを更新
gcloud run deploy ic-test-evaluate \
  --image="${AR_REPO}/ic-test-ai:latest" \
  --region=asia-northeast1
```

---

## AWS App Runner セットアップ

### 概要

AWS App Runner は、Amazon のコンテナベースアプリケーションホスティングサービスです。

**メリット:**
- Claude モデル（Bedrock）へのアクセス
- AWS の豊富なサービスとの連携
- ECR へのプッシュで自動デプロイ
- 全プラットフォーム共通のDockerイメージを使用

### ローカル開発環境の構築

#### ステップ 1: ディレクトリ移動

```bash
cd platforms/local
```

#### ステップ 2: 仮想環境の作成（推奨）

```bash
python -m venv .venv

# Windows
.\.venv\Scripts\Activate.ps1

# Mac/Linux
source .venv/bin/activate
```

#### ステップ 3: 依存関係のインストール

```bash
pip install -r requirements.txt
```

#### ステップ 4: ローカルサーバーの起動

```bash
python main.py
```

成功すると以下のような出力が表示されます：

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### AWS へのデプロイ

#### 前提条件

- AWS アカウント
- Docker がインストール済み
- `aws configure` で認証情報設定済み

#### ステップ 1: ECRリポジトリの作成（初回のみ）

```bash
aws ecr create-repository --repository-name ic-test-ai --region ap-northeast-1
```

#### ステップ 2: ECRにログイン

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION="ap-northeast-1"

aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
```

#### ステップ 3: Dockerイメージのビルド・プッシュ

```bash
ECR_REPO="$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/ic-test-ai"

# プロジェクトルートで実行
docker build -t "${ECR_REPO}:latest" -f platforms/local/Dockerfile .
docker push "${ECR_REPO}:latest"
```

#### ステップ 4: App Runner サービスの作成

詳細な IAM ロール作成手順やサービス作成コマンドは [AWS README](aws/README.md) を参照してください。

#### ステップ 5: 更新デプロイ（2回目以降）

AutoDeploymentsEnabled が true の場合、ECR に新しいイメージをプッシュすると自動デプロイされます。

```bash
# イメージをビルド・プッシュするだけでOK
docker build -t "${ECR_REPO}:latest" -f platforms/local/Dockerfile .
docker push "${ECR_REPO}:latest"
```

---

## ローカル/オンプレミス セットアップ

### 概要

ローカル/オンプレミス環境では、クラウドサービスを使用せずに内部統制テスト評価システムを運用できます。

**メリット:**
- クラウド依存なし（完全オフライン動作可能）
- データが外部に送信されない（セキュリティ要件の厳しい環境向け）
- ランニングコストなし（初期ハードウェアコストのみ）

**必要なコンポーネント:**
- **LLM**: Ollama（ローカルLLMサーバー）
- **OCR**: Tesseract（ローカルOCR）

### ローカル開発環境の構築

#### ステップ 1: Ollama のインストール

**Windows:**
```powershell
# Ollama 公式サイトからインストーラーをダウンロード
# https://ollama.ai/download/windows

# または winget を使用
winget install Ollama.Ollama
```

**Mac:**
```bash
brew install ollama
```

**Linux:**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

#### ステップ 2: LLM モデルのダウンロード

```bash
# テキスト処理用モデル
ollama pull llama3.1:8b

# Vision（画像認識）用モデル
ollama pull llava:13b
```

#### ステップ 3: Ollama サービスの起動

```bash
# フォアグラウンドで起動
ollama serve

# Windows ではインストール時に自動起動サービスとして登録されます
```

#### ステップ 4: Tesseract のインストール（OCR 機能を使用する場合）

**Windows:**
```powershell
# Chocolatey を使用
choco install tesseract

# または UB Mannheim からインストーラーをダウンロード
# https://github.com/UB-Mannheim/tesseract/wiki
```

**Mac:**
```bash
brew install tesseract tesseract-lang
```

**Linux:**
```bash
sudo apt-get install tesseract-ocr tesseract-ocr-jpn tesseract-ocr-eng
```

#### ステップ 5: ディレクトリ移動と依存関係インストール

```bash
cd platforms/local
pip install -r requirements.txt
```

#### ステップ 6: ローカルサーバーの起動

```bash
# 直接起動
python main.py

# または uvicorn を使用
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Windows PowerShell:**
```powershell
.\start.ps1
```

成功すると以下のような出力が表示されます：

```
================================================================================
[LOCAL] 内部統制テスト評価AIシステム - ローカルサーバー
================================================================================
環境変数が未設定のため、以下のデフォルト値を使用します:
  LLM_PROVIDER=LOCAL (Ollama)
  OCR_PROVIDER=TESSERACT (ローカルOCR)

Ollamaへの接続を確認中...
  ✓ Ollama (http://localhost:11434) に接続成功

INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### 動作確認

#### ヘルスチェック

```bash
curl http://localhost:8000/health
```

期待されるレスポンス:

```json
{
  "status": "healthy",
  "llm_configured": true,
  "platform": "Local/On-Premise (FastAPI)",
  "ollama_status": "connected"
}
```

#### 設定確認

```bash
curl http://localhost:8000/config
```

#### 評価リクエスト

```bash
curl -X POST http://localhost:8000/evaluate \
  -H "Content-Type: application/json" \
  -d '[{
    "id": "IC-001",
    "controlDescription": "月次で売上レポートを作成し、マネージャーが承認する",
    "testProcedure": "承認済みのレポートを確認する",
    "evidenceText": "承認印と日付が記載されたレポートを確認"
  }]'
```

### ハードウェア要件

| コンポーネント | 最小要件 | 推奨要件 |
|--------------|---------|---------|
| RAM | 8GB | 16GB以上 |
| GPU | - | NVIDIA GPU (VRAM 6GB以上) |
| ストレージ | 20GB | 50GB SSD |
| CPU | 4コア | 8コア以上 |

> **注意**: GPU がない場合は CPU で動作しますが、処理速度が大幅に低下します。

### トラブルシューティング

#### Ollama に接続できない

```bash
# Ollama サービスが起動しているか確認
ollama list

# サービスを再起動
ollama serve
```

#### Tesseract が見つからない

```bash
# パスを確認
tesseract --version

# 環境変数で明示的にパスを指定
export TESSERACT_CMD=/usr/bin/tesseract
```

#### モデルが見つからない

```bash
# インストール済みモデルを確認
ollama list

# モデルを再ダウンロード
ollama pull llama3.1:8b
```

---

## 環境変数リファレンス

### 共通設定

| 環境変数 | 必須 | 説明 | 設定値 | デフォルト |
|---------|------|------|-------|-----------|
| `LLM_PROVIDER` | **必須** | 使用するLLMプロバイダー | `AZURE_FOUNDRY`, `AZURE`, `GCP`, `AWS`, `LOCAL` | なし |
| `OCR_PROVIDER` | 任意 | 使用するOCRプロバイダー | `AZURE`, `AWS`, `GCP`, `TESSERACT`, `NONE` | `NONE` |

### Azure AI Foundry 設定

`LLM_PROVIDER=AZURE_FOUNDRY` の場合に使用

| 環境変数 | 必須 | 説明 | 例 |
|---------|------|------|-----|
| `AZURE_FOUNDRY_ENDPOINT` | **必須** | AI Foundry エンドポイント | `https://your-project.region.models.ai.azure.com` |
| `AZURE_FOUNDRY_API_KEY` | **必須** | APIキー | `xxxxxxxxxxxxxxxx` |
| `AZURE_FOUNDRY_MODEL` | **必須** | モデル名 | `gpt-5-nano`, `gpt-5.2` |
| `AZURE_FOUNDRY_API_VERSION` | 任意 | APIバージョン | `2024-08-01-preview` |

### GCP Vertex AI 設定

`LLM_PROVIDER=GCP` の場合に使用

| 環境変数 | 必須 | 説明 | 例 |
|---------|------|------|-----|
| `GCP_PROJECT_ID` | **必須** | GCPプロジェクトID | `my-project-123456` |
| `GCP_LOCATION` | 任意 | リージョン | `us-central1` |
| `GCP_MODEL_NAME` | 任意 | モデル名 | `gemini-3-pro-preview` |

> **認証**: `GOOGLE_APPLICATION_CREDENTIALS` 環境変数にサービスアカウントキーのパスを設定するか、
> Application Default Credentials を使用してください。

### AWS Bedrock 設定

`LLM_PROVIDER=AWS` の場合に使用

| 環境変数 | 必須 | 説明 | 例 |
|---------|------|------|-----|
| `AWS_REGION` | **必須** | AWSリージョン | `us-east-1`, `ap-northeast-1` |
| `AWS_BEDROCK_MODEL_ID` | 任意 | モデルID | `jp.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| `AWS_ACCESS_KEY_ID` | 条件付き | アクセスキー | App Runner では IAM ロール使用 |
| `AWS_SECRET_ACCESS_KEY` | 条件付き | シークレットキー | App Runner では IAM ロール使用 |

### LOCAL (Ollama) 設定

`LLM_PROVIDER=LOCAL` の場合に使用

| 環境変数 | 必須 | 説明 | 例 |
|---------|------|------|-----|
| `OLLAMA_BASE_URL` | 任意 | Ollama サーバーURL | `http://localhost:11434` |
| `OLLAMA_MODEL` | 任意 | テキスト処理用モデル | `llama3.1:8b` |
| `OLLAMA_VISION_MODEL` | 任意 | 画像認識用モデル | `llava:13b` |

> **注意**: Ollama はデフォルトで `http://localhost:11434` で動作するため、環境変数の設定は任意です。

### OCR 設定

#### Azure Document Intelligence

`OCR_PROVIDER=AZURE` の場合に使用

| 環境変数 | 必須 | 説明 | 例 |
|---------|------|------|-----|
| `AZURE_DI_ENDPOINT` | **必須** | Document Intelligence エンドポイント | `https://your-resource.cognitiveservices.azure.com/` |
| `AZURE_DI_KEY` | **必須** | APIキー | `xxxxxxxxxxxxxxxx` |

#### GCP Document AI

`OCR_PROVIDER=GCP` の場合に使用

| 環境変数 | 必須 | 説明 | 例 |
|---------|------|------|-----|
| `GCP_DOCAI_PROJECT_ID` | **必須** | プロジェクトID | `my-project-123456` |
| `GCP_DOCAI_LOCATION` | **必須** | リージョン | `us`, `eu` |
| `GCP_DOCAI_PROCESSOR_ID` | **必須** | プロセッサーID | `xxxxxxxxxxxxxxxx` |

#### Tesseract OCR

`OCR_PROVIDER=TESSERACT` の場合に使用

| 環境変数 | 必須 | 説明 | 例 |
|---------|------|------|-----|
| `TESSERACT_LANG` | 任意 | 認識言語 | `jpn+eng` |
| `TESSERACT_CMD` | 任意 | Tesseract実行パス | `/usr/bin/tesseract` |

---

## Excel VBAマクロの設定

### 設定ファイルの作成

```bash
# プロジェクトルートで実行
cp setting.json.example setting.json
```

### setting.json の編集

```json
{
    "dataStartRow": 2,
    "sheetName": "",
    "batchSize": 3,
    "columns": {
        "ID": "A",
        "ControlDescription": "C",
        "TestProcedure": "D",
        "EvidenceLink": "E"
    },
    "api": {
        "provider": "AZURE",
        "endpoint": "https://your-container-app.japaneast.azurecontainerapps.io/evaluate",
        "apiKey": "your-api-key",  # pragma: allowlist secret
        "authHeader": "x-api-key"
    },
    "responseMapping": {
        "evaluationResult": "F",
        "judgmentBasis": "G",
        "documentReference": "H",
        "fileName": "I"
    },
    "booleanDisplayTrue": "有効",
    "booleanDisplayFalse": "非有効"
}
```

### 設定項目の説明

| 項目 | 説明 |
|------|------|
| `dataStartRow` | データの開始行（ヘッダーの次の行） |
| `sheetName` | 対象シート名（空の場合はアクティブシート） |
| `batchSize` | 一度に処理する件数 |
| `columns` | Excel列とデータフィールドのマッピング |
| `api.provider` | クラウドプロバイダー（`AZURE`, `GCP`, `AWS`） |
| `api.endpoint` | APIエンドポイントURL |
| `api.apiKey` | 認証キー |
| `api.authHeader` | 認証ヘッダー名 |
| `responseMapping` | レスポンスの出力先列 |

### プラットフォーム別の認証設定

| プラットフォーム | provider | authHeader | apiKey の取得方法 |
|-----------------|----------|------------|------------------|
| Azure Container Apps | `AZURE` | `x-api-key` | Azure Portal → Container Apps → 認証設定 |
| GCP Cloud Run | `GCP` | `Authorization` | `gcloud auth print-identity-token` で取得し `Bearer ` を付与 |
| AWS App Runner | `AWS` | `x-api-key` | API Gateway → APIキー |

### 認証オプション（エンタープライズ向け）

認証は**オプション**であり、デプロイ時に有効/無効を選択できます。

| プラットフォーム | 認証なし（開発/テスト用） | 認証あり（本番推奨） | セットアップスクリプト |
|-----------------|------------------------|---------------------|---------------------|
| **Azure** | `--ingress external` | Azure AD (Entra ID) | `scripts/setup-azure-ad-auth.ps1` |
| **GCP** | `--allow-unauthenticated` | IAM / Identity Platform | `scripts/setup-gcp-iap-auth.ps1` |
| **AWS** | API Gateway認証なし | Amazon Cognito | `scripts/setup-aws-cognito-auth.ps1` |

#### 認証なしでデプロイ（開発/テスト環境）

```powershell
# Azure - パブリックアクセス
az containerapp create --ingress external ...

# GCP - パブリックアクセス
gcloud run deploy --allow-unauthenticated ...

# AWS - App Runner パブリックアクセス
# App Runnerサービス作成時にパブリックエンドポイントが自動付与
```

#### 認証ありでデプロイ（本番環境）

```powershell
# Azure AD認証を設定
.\scripts\setup-azure-ad-auth.ps1 -ContainerAppName "app-name" -ResourceGroup "rg-name"

# GCP IAM認証を設定
.\scripts\setup-gcp-iap-auth.ps1 -ProjectId "your-project"

# AWS Cognito認証を設定
.\scripts\setup-aws-cognito-auth.ps1 -ServiceName "service-name"
```

> **推奨**: 本番環境ではエンタープライズ認証を有効化し、特定のユーザー/グループのみアクセスを許可してください。

---

## 動作確認

### API エンドポイント

| エンドポイント | メソッド | 説明 |
|---------------|---------|------|
| `/evaluate` | POST | テスト評価を実行 |
| `/health` | GET | システム状態を確認 |
| `/config` | GET | 設定状態を確認 |

### ヘルスチェック

```bash
# ローカル（全プラットフォーム共通）
curl http://localhost:8000/health

# デプロイ後（例: Azure Container Apps）
curl https://your-container-app.japaneast.azurecontainerapps.io/health
```

期待されるレスポンス：

```json
{
    "status": "healthy",
    "version": "2.4.0-multiplatform",
    "llm": {
        "provider": "AZURE_FOUNDRY",
        "configured": true
    },
    "ocr": {
        "provider": "NONE",
        "configured": true
    }
}
```

### 非同期APIエンドポイント（推奨）

504タイムアウト対策として、非同期処理モードが追加されました。

| エンドポイント | メソッド | 説明 |
|---------------|---------|------|
| `/evaluate/submit` | POST | ジョブ送信（即座にjob_idを返却） |
| `/evaluate/status/{job_id}` | GET | ジョブステータス確認 |
| `/evaluate/results/{job_id}` | GET | ジョブ結果取得 |

setting.jsonで `"asyncMode": true` を設定すると、自動的に非同期APIが使用されます。

### 評価リクエストのテスト

```bash
curl -X POST http://localhost:8000/evaluate \
  -H "Content-Type: application/json" \
  -d '[{
    "ID": "TEST-001",
    "ControlDescription": "アクセス権限の承認プロセスが存在する",
    "TestProcedure": "承認記録を確認し、適切な承認者による承認があることを検証する",
    "EvidenceFiles": []
  }]'
```

---

## トラブルシューティング

### よくあるエラーと解決方法

#### 1. `ModuleNotFoundError: No module named 'core'`

**原因**: Python パスが正しく設定されていない

**解決方法**:
- 仮想環境が有効化されているか確認
- `pip install -r requirements.txt` を再実行
- Dockerイメージのビルドが正常に完了しているか確認

#### 2. `LLM未設定のため、モック評価を実行します`

**原因**: LLM の環境変数が設定されていない

**解決方法**:
- `.env` ファイルが存在するか確認
- `LLM_PROVIDER` と必要なAPI設定が記載されているか確認
- ローカル実行時は仮想環境を有効化しているか確認

#### 3. `Azure Container Apps: 401 Unauthorized`

**原因**: 認証設定が正しくない

**解決方法**:
- Azure Portal で Container Apps の認証設定を再確認
- `setting.json` の `apiKey` を更新

#### 4. `タイムアウトエラー`

**原因**: 処理時間が制限を超えた

**解決方法**:

| プラットフォーム | 設定方法 | 推奨値 | 最大値 |
|-----------------|---------|-------|-------|
| Azure Container Apps | `--request-timeout` | `600` | `3600` |
| GCP Cloud Run | `--timeout` オプション | `300` | `3600` |
| AWS App Runner | App Runner 設定 | `300` | `900` |

#### 5. `メモリ不足エラー`

**原因**: OCR処理やLLM呼び出しでメモリが不足

**解決方法**:

| プラットフォーム | 推奨メモリ | 設定方法 |
|-----------------|-----------|---------|
| Azure Container Apps | 2GB以上 | `--memory 4.0Gi` |
| GCP Cloud Run | 2GB以上 | `--memory 4Gi` |
| AWS App Runner | 2GB以上 | `--instance-configuration "Memory=4 GB"` |

### ログの確認方法

| プラットフォーム | ローカル | クラウド |
|-----------------|---------|---------|
| Azure Container Apps | `python main.py` のコンソール出力 | Azure Portal → Container Apps → ログストリーム |
| GCP Cloud Run | `python main.py` のコンソール出力 | `gcloud run services logs read ic-test-evaluate` |
| AWS App Runner | `python main.py` のコンソール出力 | `aws apprunner list-operations --service-arn <ARN>` |

---

## 推奨構成パターン

### 用途別の推奨構成

| 用途 | プラットフォーム | LLM | OCR | 理由 |
|-----|-----------------|-----|-----|-----|
| **Azure統合環境** | Azure Container Apps | AZURE_FOUNDRY | AZURE | 統合管理、日本語OCR高精度 |
| **GCP統合環境** | Cloud Run | GCP | GCP | Gemini、高速処理 |
| **AWS統合環境** | App Runner | AWS | AWS | Claude、豊富なサービス連携 |
| **コスト重視** | 任意 | 任意 | TESSERACT | OSS OCR、オフライン対応 |
| **OCR不要** | 任意 | 任意 | NONE | テキストPDFのみ、最速 |

### コスト比較（目安）

| 構成 | 月額目安（1000リクエスト） | 備考 |
|-----|-------------------------|------|
| Azure Container Apps + GPT-5 Nano | $40-90 | LLMコストが主 |
| GCP Cloud Run + Gemini | $30-60 | Gemini は比較的安価 |
| AWS App Runner + Claude | $60-130 | Claude は高品質だがコスト高め |
| 任意 + Tesseract | $10-50 | OCRコスト削減 |

---

## 付録

---

## 現在のデプロイ状況

### デプロイ済みエンドポイント

| プラットフォーム | エンドポイント | ステータス | LLMモデル | 認証 |
|----------------|--------------|----------|----------|------|
| **Azure Container Apps** | `ic-test-eval.japaneast.azurecontainerapps.io` | Active | Azure AI Foundry GPT-5 Nano | Azure AD |
| **GCP Cloud Run** | `ic-test-evaluate-a3nd27leoa-an.a.run.app` | Active | Gemini 3 Pro | AllowUnauthenticated |
| **AWS App Runner** | `ic-test-evaluate.ap-northeast-1.awsapprunner.com` | Active | Claude Sonnet 4.5 (JP) | API Key |

### モデル設定（llm_factory.py）- 2026年2月最新

| プロバイダー | ハイエンドモデル | コスト重視モデル | 備考 |
|------------|-----------------|-----------------|------|
| Azure Foundry | gpt-5.2 | gpt-5-nano | GPT-5シリーズ対応 |
| GCP | gemini-3-pro | gemini-3-flash | Gemini 3シリーズ対応 |
| AWS | claude-opus-4-6 | claude-haiku-4-5 | Claude 4シリーズ対応 |
| LOCAL | llama3.2:70b | phi4:3.8b | Ollama対応 |

#### 利用可能なモデル一覧

**Azure AI Foundry:**
- `gpt-5.2` - フラッグシップ（企業エージェント・コーディング）
- `gpt-5.2-codex` - コード特化
- `gpt-5.1` - 推論機能付き
- `gpt-5` - ロジック・マルチステップ向け
- `gpt-5-nano` - 高速・低コスト（推奨）
- `gpt-5-mini` - 軽量版
- `claude-opus-4-6` - Anthropic最高性能（エージェントチーム、1Mトークン）
- `claude-opus-4-5` - Anthropic高性能モデル
- `claude-sonnet-4-5` - Anthropicバランス型
- `claude-haiku-4-5` - Anthropic高速・低コスト

> **Note**: 2026年2月より、AnthropicのClaudeモデルがMicrosoft Foundry経由でAzureから直接利用可能になりました。

**GCP Vertex AI:**

- `gemini-3-pro-preview` - 最高性能（動作確認済み・globalリージョン必須）
- `gemini-3-flash-preview` - 高速・マルチモーダル（globalリージョン必須）
- `gemini-2.5-pro` - 高度な推論・コーディング（動作確認済み）
- `gemini-2.5-flash` - 高速・コスト効率（動作確認済み）
- `gemini-2.5-flash-lite` - 超軽量（動作確認済み）

> **Note**: Gemini 3.x を使用するには `GCP_LOCATION=global` の設定が必要です。

**AWS Bedrock:**
- `global.anthropic.claude-opus-4-6-v1` - 最高性能
- `global.anthropic.claude-opus-4-5-v1` - 高性能
- `global.anthropic.claude-sonnet-4-5-v1` - バランス型
- `global.anthropic.claude-haiku-4-5-v1` - 高速・低コスト

### モデルアクセス設定（初回セットアップ）

各クラウドプロバイダーでLLMモデルを使用するには、事前にモデルアクセスを有効化する必要があります。

#### GCP Vertex AI (Gemini)

Gemini 3 Pro / 2.5 Flash (GA) は追加設定なしで利用可能です。

1. [Vertex AI API](https://console.cloud.google.com/apis/library/aiplatform.googleapis.com?project=ic-test-ai-agent) が有効であることを確認
2. サービスアカウントに「Vertex AI User」ロールがあることを確認

#### AWS Bedrock (Claude)

1. [AWS Bedrock Console - Model Access](https://ap-northeast-1.console.aws.amazon.com/bedrock/home?region=ap-northeast-1#/modelaccess) を開く
2. 「Model Access」→「Manage model access」をクリック
3. 「Anthropic Claude Sonnet 4.5」にチェックを入れて「Request model access」
4. 承認完了まで数分待機
5. App Runner インスタンスロールに `AmazonBedrockFullAccess` ポリシーをアタッチ

### AWS API Gateway タイムアウト制限

AWS API Gateway HTTP API には **30秒のタイムアウト制限** があります。これはAWSの仕様であり変更できません。

#### 影響

- 内部統制テスト評価は通常 30〜60秒かかるため、同期モード（`/evaluate`）ではタイムアウトエラーになる可能性があります
- App Runner自体はより長時間実行可能ですが、API Gateway経由のレスポンスが30秒でカットされます

#### 推奨対応

| 方式 | エンドポイント | 説明 |
|-----|--------------|------|
| **非同期モード（推奨）** | `/evaluate/submit` | ジョブをキューに登録し、後で結果を取得 |
| 同期モード | `/evaluate` | 30秒以内の軽量リクエストのみ対応 |

**非同期モードの使用例：**

```bash
# 1. ジョブ送信
curl -X POST https://your-api-gateway/evaluate/submit \
  -H "Content-Type: application/json" \
  -d @request.json
# Response: {"job_id": "abc123", "status": "submitted"}

# 2. ステータス確認（ポーリング）
curl https://your-api-gateway/evaluate/status/abc123
# Response: {"job_id": "abc123", "status": "processing"}

# 3. 結果取得（完了後）
curl https://your-api-gateway/evaluate/results/abc123
# Response: {"job_id": "abc123", "status": "completed", "result": {...}}
```

#### 代替案

| 方式 | 説明 | メリット | デメリット |
|-----|------|---------|-----------|
| ALB (Application Load Balancer) | タイムアウト最大4000秒 | 長時間処理対応 | コスト増（月額$20〜） |
| App Runner 直接アクセス | タイムアウト最大120秒 | 追加コストなし | API Gateway バイパス |
| API Gateway WebSocket | 双方向通信 | リアルタイム更新 | 実装複雑 |

### 監視設定（ログアラート）

本番運用では、WARNING/ERRORログを検知してアラートを設定することを推奨します。

#### ログレベル定義

| レベル | 用途 | アクション |
|-------|------|-----------|
| DEBUG | デバッグ情報 | 開発時のみ有効化 |
| INFO | 正常処理ログ | 監視不要 |
| **WARNING** | 潜在的問題 | 日次レビュー推奨 |
| **ERROR** | 処理失敗 | 即座に対応 |
| CRITICAL | システム停止 | 緊急対応 |

#### Azure Monitor 設定

```kusto
// Log Analytics クエリ - WARNING以上のログを検出
ContainerAppConsoleLogs_CL
| where Log_s has_any ("WARNING", "ERROR", "CRITICAL")
| where TimeGenerated > ago(1h)
| project TimeGenerated, Log_s, ContainerAppName_s
| order by TimeGenerated desc
```

アラートルール設定：
1. Azure Portal → Container Apps → 「ログ」→ 上記クエリを実行
2. 「新しいアラートルール」→ 条件: 結果数 > 0
3. アクション: メール通知またはTeams Webhook

#### GCP Cloud Monitoring 設定

```
# ログベースのアラートポリシー
resource.type="cloud_run_revision"
severity >= WARNING
```

設定手順：
1. Cloud Console → Monitoring → アラートポリシー
2. 「ポリシーを作成」→ ログベースのアラート
3. フィルター: 上記のクエリを設定
4. 通知チャネル: Email / Slack / PagerDuty

#### AWS CloudWatch 設定

```
# メトリクスフィルター（WARNING検出）
{ $.level = "WARNING" }

# メトリクスフィルター（ERROR検出）
{ $.level = "ERROR" }
```

設定手順：
1. CloudWatch → ログ → ロググループ → `/aws/apprunner/ic-test-evaluate`
2. 「メトリクスフィルターを作成」→ 上記パターンを設定
3. CloudWatch Alarms → フィルターメトリクスに基づくアラート作成
4. SNSトピック経由でメール/Slack通知

#### 推奨アラート閾値

| メトリクス | 閾値 | 期間 | 通知先 |
|-----------|------|------|--------|
| ERROR ログ数 | > 0 | 5分 | 即座に運用チーム |
| WARNING ログ数 | > 10 | 1時間 | 日次サマリー |
| 実行時間 | > 300秒 | 5分 | 運用チーム |
| エラー率 | > 5% | 15分 | 運用チーム |

### 利用可能なAPI

| パス | メソッド | 説明 |
|------|---------|------|
| `/health` | GET | ヘルスチェック |
| `/config` | GET | 設定状態確認 |
| `/evaluate` | POST | テスト評価（同期） |
| `/evaluate/submit` | POST | ジョブ送信（非同期） |
| `/evaluate/status/{job_id}` | GET | ステータス確認 |
| `/evaluate/results/{job_id}` | GET | 結果取得 |

### クイックテスト

```bash
# GCP Cloud Run ヘルスチェック
curl https://ic-test-evaluate-a3nd27leoa-an.a.run.app/health

# AWS App Runner ヘルスチェック
curl https://ic-test-evaluate.ap-northeast-1.awsapprunner.com/health

# Azure Container Apps ヘルスチェック（Azure AD認証が必要）
# curl -H "Authorization: Bearer <token>" https://ic-test-eval.japaneast.azurecontainerapps.io/health
```

---

## 付録

### A. 使用技術一覧（2026年2月最新）

| カテゴリ | 技術 | バージョン | 用途 |
|---------|------|-----------|-----|
| 言語 | Python | 3.11+ | バックエンド実装 |
| LLMフレームワーク | LangChain | 1.2.9+ | LLM抽象化 |
| ワークフロー | LangGraph | 1.0.8+ | セルフリフレクション |
| Azure LLM | langchain-openai | 0.3.0+ | Azure AI Foundry (GPT-5.x) |
| GCP LLM | langchain-google-vertexai | 3.0.0+ | Vertex AI (Gemini 3.x) |
| AWS LLM | langchain-aws | 0.3.0+ | Bedrock (Claude 4.x) |
| Local LLM | langchain-ollama | 0.3.0+ | Ollama連携 |
| PDF処理 | pypdf | 3.0+ | PDFテキスト抽出 |
| Excel処理 | openpyxl | 3.1+ | Excelファイル処理 |
| 環境変数 | python-dotenv | 1.0+ | .env ファイル読み込み |

### B. 関連ドキュメント

- [SYSTEM_SPECIFICATION.md](../SYSTEM_SPECIFICATION.md) - システム仕様書
- [.env.example](../.env.example) - 環境変数サンプル
- [setting.json.example](../setting.json.example) - VBA設定サンプル

### C. LLMモデル結合テスト

各LLMモデルの動作確認は以下のテストで実施できます。

#### テスト実行方法

```bash
# 全モデルの結合テスト（設定されたプロバイダーのみ実行）
pytest tests/test_integration_models.py -v -m llm

# Azure Foundryモデルのみ
pytest tests/test_integration_models.py -v -m "azure and llm"

# AWS Bedrockモデルのみ
pytest tests/test_integration_models.py -v -m "aws and llm"

# GCP Vertex AIモデルのみ
pytest tests/test_integration_models.py -v -m "gcp and llm"

# ローカル（Ollama）モデルのみ
pytest tests/test_integration_models.py -v -m "local and llm"
```

#### テスト対象モデル一覧

| プロバイダー | モデル | テスト名 | 備考 |
|------------|--------|---------|------|
| Azure Foundry | gpt-5.2 | `test_gpt_5_2` | フラッグシップ |
| Azure Foundry | gpt-5-nano | `test_gpt_5_nano` | 高速・低コスト |
| Azure Foundry | claude-opus-4-6 | `test_claude_opus_4_6_azure` | Anthropic最高性能（Azure経由） |
| Azure Foundry | claude-sonnet-4-5 | `test_claude_sonnet_4_5_azure` | Anthropicバランス型 |
| Azure Foundry | claude-haiku-4-5 | `test_claude_haiku_4_5_azure` | Anthropic高速 |
| AWS Bedrock | claude-opus-4-6-v1 | `test_claude_opus_4_6` | 最高性能 |
| AWS Bedrock | claude-opus-4-5-v1 | `test_claude_opus_4_5` | 高性能 |
| AWS Bedrock | claude-sonnet-4-5-v1 | `test_claude_sonnet_4_5` | バランス型 |
| AWS Bedrock | claude-haiku-4-5-v1 | `test_claude_haiku_4_5` | 高速・低コスト |
| GCP Vertex AI | gemini-3-pro | `test_gemini_3_pro` | 高度な推論 |
| GCP Vertex AI | gemini-3-flash | `test_gemini_3_flash` | コスト効率 |
| LOCAL (Ollama) | phi4:3.8b | `test_phi4_lightweight` | 超軽量 |
| LOCAL (Ollama) | mistral:7b | `test_mistral_lightweight` | 軽量高速 |

> **Note**: 重いローカルモデル（llama3.2:70bなど）は結合テスト対象外です。

### D. サポート・問い合わせ

問題が解決しない場合は、以下の情報を添えてお問い合わせください：

1. 使用しているプラットフォーム（Azure/GCP/AWS）
2. エラーメッセージの全文
3. `.env` ファイルの内容（APIキーは伏せてください）
4. 実行したコマンド
