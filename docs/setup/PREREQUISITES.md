# 前提条件セットアップガイド

> **対象システム**: 内部統制テストAIエージェント (ic-test-ai-agent)
> **最終更新**: 2026-02-11
> **対象読者**: 開発者、システム管理者、初めて環境構築を行う方

---

## 目次

1. [はじめに](#1-はじめに)
2. [開発環境の準備](#2-開発環境の準備)
3. [プロジェクトセットアップ](#3-プロジェクトセットアップ)
4. [クラウドCLIツール](#4-クラウドcliツール)
5. [テスト環境の確認](#5-テスト環境の確認)
6. [各プラットフォーム共通の環境変数](#6-各プラットフォーム共通の環境変数)
7. [よくある問題と解決策](#7-よくある問題と解決策)
8. [次のステップ](#8-次のステップ)

---

## 1. はじめに

### 1.1 このドキュメントの概要

このドキュメントでは、内部統制テストAIエージェント（ic-test-ai-agent）の開発環境を
ゼロから構築するための手順を、初心者の方にもわかるよう詳しく説明します。

すべての手順は Windows 11 環境を前提としています。
各ツールのインストールからプロジェクトの動作確認まで、順番に進めてください。

### 1.2 対象者

- 本プロジェクトに初めて参加する開発者
- 内部統制テスト評価システムの環境構築を行うシステム管理者
- Python やクラウドサービスの経験が浅い方

### 1.3 全体の流れ

環境構築は以下の順序で進めます。各ステップは前のステップに依存しているため、
上から順に実施してください。

```text
1. 開発環境の準備（Python, Git, VS Code）
       |
2. プロジェクトセットアップ（クローン、仮想環境、依存関係）
       |
3. クラウドCLIツール（Azure CLI, AWS CLI, gcloud CLI）
       |
4. テスト実行で動作確認
       |
5. 環境変数の設定
```

---

## 2. 開発環境の準備

### 2.1 OSの確認

本プロジェクトは **Windows 11** での開発を推奨しています。
Windows 10 でも動作しますが、一部のPowerShell機能に制限がある場合があります。

現在のOSバージョンを確認するには、PowerShellで以下を実行してください。

```powershell
# Windowsバージョンの確認
[System.Environment]::OSVersion.Version
```

出力例:

```text
Major  Minor  Build  Revision
-----  -----  -----  --------
10     0      22631  0
```

`Build` が 22000 以上であれば Windows 11 です。

### 2.2 Python のインストール

本プロジェクトでは **Python 3.11** を推奨しています。
Python 3.10〜3.12 でも動作しますが、安定性の観点から 3.11 を推奨します。

> **Pythonとは**: プログラミング言語の一つです。本システムのバックエンド（サーバー側）は
> すべてPythonで書かれています。

#### 手順1: Python がインストール済みか確認する

PowerShellを開いて以下のコマンドを実行してください。

```powershell
python --version
```

`Python 3.11.x` と表示されればOKです。
`'python' は、内部コマンドまたは外部コマンド...として認識されていません` と表示された場合は、
Pythonをインストールする必要があります。

#### 手順2: Python 3.11 をインストールする

1. **Python公式サイト** にアクセスします
   - URL: `https://www.python.org/downloads/`

2. **Python 3.11.x** のインストーラーをダウンロードします
   - 「Download Python 3.11.x」ボタンをクリック
   - Windows用の `python-3.11.x-amd64.exe` を選択

3. **インストーラーを実行**します
   - **重要**: インストーラーの最初の画面で **「Add python.exe to PATH」にチェック** を入れてください
   - この設定を忘れると、PowerShellから `python` コマンドが認識されません
   - 「Install Now」をクリックしてインストールを開始します

4. **インストール完了後に確認**します

```powershell
# バージョン確認
python --version

# 出力例: Python 3.11.9
```

> **PATHとは**: OSがプログラムを探す場所のリストです。PATHに追加されていないと、
> プログラム名だけではコマンドを実行できず、フルパスの指定が必要になります。

#### 手順3: pip の確認と更新

**pip** はPythonのパッケージ管理ツールです。ライブラリ（追加機能）をインストールするために使います。

```powershell
# pipのバージョン確認
pip --version

# 出力例: pip 24.0 from C:\...\pip (python 3.11)
```

pipを最新版に更新しておきましょう。

```powershell
# pipの更新
python -m pip install --upgrade pip
```

### 2.3 Git のインストールと初期設定

**Git** はソースコードのバージョン管理ツールです。
複数の開発者がコードを共同編集するために使います。

> **Gitとは**: ファイルの変更履歴を管理するシステムです。「いつ」「誰が」「何を」
> 変更したかを記録し、過去の状態に戻したり、変更を統合したりできます。

#### 手順1: Git がインストール済みか確認する

```powershell
git --version
```

`git version 2.x.x` と表示されればOKです。

#### 手順2: Git をインストールする

1. **Git公式サイト** にアクセスします
   - URL: `https://git-scm.com/downloads/win`

2. **64-bit Git for Windows Setup** をダウンロードして実行します

3. **インストール時の設定**（初めての方はデフォルトのままでOK）
   - 「Default Branch Name」は `main` を推奨
   - 「Adjusting your PATH environment」は「Git from the command line and also from 3rd-party software」を選択
   - その他はデフォルトで問題ありません

4. **インストール完了後の初期設定**

```powershell
# ユーザー名とメールアドレスを設定（コミット時の記録に使われます）
git config --global user.name "あなたの名前"
git config --global user.email "your.email@example.com"

# 設定確認
git config --global --list
```

### 2.4 VS Code のインストールと推奨拡張機能

**VS Code（Visual Studio Code）** は、Microsoft が開発した無料のコードエディタです。
本プロジェクトの開発ではVS Codeの使用を推奨しています。

> **コードエディタとは**: プログラムのコードを書くための専用テキストエディタです。
> 色分け（シンタックスハイライト）やエラーの検出など、プログラミングに便利な機能があります。

#### 手順1: VS Code をインストールする

1. **VS Code公式サイト** にアクセスします
   - URL: `https://code.visualstudio.com/`

2. 「Download for Windows」ボタンをクリックしてインストーラーをダウンロード

3. インストーラーを実行してインストール
   - 「PATHへの追加」オプションにチェックを入れておくことを推奨

#### 手順2: 推奨拡張機能をインストールする

VS Codeを起動したら、以下の拡張機能をインストールしてください。
左サイドバーの拡張機能アイコン（四角が4つ並んだアイコン）をクリックし、
検索バーに名前を入力してインストールします。

| 拡張機能名 | 説明 |
| --- | --- |
| Python (ms-python.python) | Pythonの構文ハイライト、デバッグ、IntelliSense |
| Pylance (ms-python.vscode-pylance) | Python の高速な型チェックと補完 |
| GitLens (eamodio.gitlens) | Git の変更履歴を視覚的に表示 |
| Claude Code (anthropic.claude-code) | Claude AIとの統合開発環境 |
| Japanese Language Pack (MS-CEINTL.vscode-language-pack-ja) | VS Codeの日本語化 |
| Markdown All in One (yzhang.markdown-all-in-one) | Markdownの編集支援 |

---

## 3. プロジェクトセットアップ

### 3.1 リポジトリのクローン

Git を使ってプロジェクトのソースコードをローカル（自分のPC）にコピーします。
この操作を「クローン」と呼びます。

```powershell
# 作業ディレクトリに移動（お好みの場所に変更可）
cd C:\Users\goyos\OneDrive\ドキュメント\VSCode_Dev\PythonDev

# リポジトリをクローン
git clone <リポジトリURL> ic-test-ai-agent

# プロジェクトディレクトリに移動
cd ic-test-ai-agent
```

> **リポジトリURLがわからない場合**: プロジェクト管理者に確認してください。
> 通常は `https://github.com/組織名/ic-test-ai-agent.git` の形式です。

### 3.2 仮想環境の作成

#### なぜ仮想環境が必要か

Pythonでは、プロジェクトごとに使うライブラリのバージョンが異なることがあります。
例えば、プロジェクトAでは `langchain 1.2.9` を使い、プロジェクトBでは `langchain 1.0.0`
を使うかもしれません。

**仮想環境（venv）** を使うと、プロジェクトごとに独立したPython環境を作成でき、
ライブラリのバージョン競合を防ぐことができます。

```text
PC全体のPython環境
   |
   +-- プロジェクトA の仮想環境（langchain 1.2.9）
   |
   +-- プロジェクトB の仮想環境（langchain 1.0.0）
   |
   +-- ic-test-ai-agent の仮想環境 ← 今回作るのはこれ
```

#### 仮想環境の作成手順

```powershell
# プロジェクトルートディレクトリにいることを確認
cd C:\Users\goyos\OneDrive\ドキュメント\VSCode_Dev\PythonDev\ic-test-ai-agent

# 仮想環境を作成（.venv という名前のフォルダが作られます）
python -m venv .venv

# 仮想環境を有効化（Windowsの場合）
.\.venv\Scripts\Activate.ps1
```

仮想環境が有効になると、プロンプト（コマンド入力行）の先頭に `(.venv)` と表示されます。

```text
(.venv) PS C:\...\ic-test-ai-agent>
```

> **注意**: 仮想環境は使うたびに有効化する必要があります。
> PowerShellを閉じて再度開いた場合は、もう一度 `.\.venv\Scripts\Activate.ps1` を実行してください。

> **OneDriveとの注意点**: OneDrive配下で仮想環境を作成すると、大量の小さなファイルが
> 同期対象になり、PCの動作が遅くなることがあります。
> 問題が発生する場合は、セクション7「よくある問題と解決策」を参照してください。

### 3.3 依存関係のインストール

プロジェクトで使用するPythonライブラリをインストールします。

```powershell
# 仮想環境が有効であることを確認（プロンプトに (.venv) が表示されていること）

# 本番用の依存関係をインストール
pip install -r requirements.txt

# 開発用の依存関係も追加でインストール（テスト、リンター等）
pip install -r requirements-dev.txt
```

インストールには数分かかります。完了後、正常にインストールされたか確認しましょう。

```powershell
# インストール済みパッケージの一覧を表示
pip list
```

`langchain`, `fastapi`, `pytest` 等が表示されていればOKです。

### 3.4 環境変数の設定

本システムは `.env` ファイルで環境変数（APIキーやモデル名等）を管理します。

#### 手順1: .env ファイルを作成する

```powershell
# サンプルファイルをコピーして .env ファイルを作成
Copy-Item .env.example .env
```

#### 手順2: .env ファイルを編集する

VS Code で `.env` ファイルを開き、使用する環境に合わせて値を設定してください。

```powershell
# VS Code で .env を開く
code .env
```

最低限設定が必要な項目は以下の通りです。

```bash
# LLMプロバイダーの選択（いずれか一つ）
LLM_PROVIDER=AZURE_FOUNDRY

# === Azure AI Foundry を使う場合 ===
AZURE_FOUNDRY_ENDPOINT=https://your-project.region.models.ai.azure.com
AZURE_FOUNDRY_API_KEY=your-foundry-api-key
AZURE_FOUNDRY_MODEL=gpt-5.2

# === OCRプロバイダー（省略可、デフォルトはpypdf） ===
# OCR_PROVIDER=AZURE
# AZURE_DI_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
# AZURE_DI_KEY=your-document-intelligence-key
```

> **重要**: `.env` ファイルには機密情報（APIキー等）が含まれます。
> このファイルは `.gitignore` に登録されているため、Gitリポジトリにはコミットされません。
> **絶対に `.env` ファイルを他人と共有したり、Gitにコミットしたりしないでください。**

---

## 4. クラウドCLIツール

使用するクラウドプラットフォームに応じて、対応するCLIツールをインストールしてください。
すべてのプラットフォームをインストールする必要はありません。使用するもののみで大丈夫です。

### 4.1 Azure CLI のインストールと認証

Azure CLI は、コマンドラインからAzureリソースを管理するためのツールです。

#### インストール

```powershell
# winget（Windows パッケージマネージャー）でインストール
winget install -e --id Microsoft.AzureCLI
```

インストール後、PowerShellを再起動してから確認します。

```powershell
az --version
# 出力例: azure-cli 2.67.0
```

#### 認証（ログイン）

```powershell
# Azureにログイン（ブラウザが開きます）
az login

# サブスクリプションを設定（複数ある場合）
az account set --subscription "<サブスクリプション名またはID>"

# 現在のアカウント情報を確認
az account show
```

### 4.2 AWS CLI のインストールと認証

AWS CLI は、コマンドラインからAWSリソースを管理するためのツールです。

#### インストール

1. AWS CLI v2 のインストーラーをダウンロード
   - URL: `https://awscli.amazonaws.com/AWSCLIV2.msi`
2. ダウンロードした `.msi` ファイルを実行してインストール

```powershell
# インストール確認
aws --version
# 出力例: aws-cli/2.24.0 Python/3.12.6 Windows/10 ...
```

#### 認証（設定）

```powershell
# AWS認証情報を設定
aws configure
```

以下の情報を入力します（管理者から提供されます）。

```text
AWS Access Key ID [None]: YOUR_ACCESS_KEY_ID
AWS Secret Access Key [None]: YOUR_SECRET_ACCESS_KEY
Default region name [None]: ap-northeast-1
Default output format [None]: json
```

```powershell
# 認証確認
aws sts get-caller-identity
```

### 4.3 gcloud CLI のインストールと認証

gcloud CLI は、コマンドラインからGCPリソースを管理するためのツールです。

#### インストール

1. Google Cloud SDK のインストーラーをダウンロード
   - URL: `https://cloud.google.com/sdk/docs/install`
2. ダウンロードした `GoogleCloudSDKInstaller.exe` を実行

```powershell
# インストール確認
gcloud --version
# 出力例: Google Cloud SDK 505.0.0
```

#### 認証（ログイン）

```powershell
# GCPにログイン（ブラウザが開きます）
gcloud auth login

# プロジェクトを設定
gcloud config set project YOUR_PROJECT_ID

# Application Default Credentials を設定（Pythonから使用する場合に必要）
gcloud auth application-default login

# 認証確認
gcloud auth list
```

### 4.4 Terraform のインストール

Terraform はクラウドインフラをコードで管理する（Infrastructure as Code）ツールです。
本番環境の構築時に使用します。開発のみの場合はスキップ可能です。

#### インストール

```powershell
# winget でインストール
winget install -e --id Hashicorp.Terraform

# インストール確認（PowerShell再起動後）
terraform --version
# 出力例: Terraform v1.10.3
```

---

## 5. テスト環境の確認

環境構築が正しく完了したかを、テストを実行して確認しましょう。

### 5.1 pytest の実行

```powershell
# プロジェクトルートディレクトリで実行
# 仮想環境が有効であることを確認してください

# 全テストを実行（詳細表示モード）
python -m pytest tests/ -v
```

#### 期待される結果

```text
========================= test session starts =========================
...
============= 505 passed, 274 skipped in XXs =============
```

- **505 passed**: 505件のテストが成功
- **274 skipped**: 274件のテストがスキップ（クラウド接続が必要なテスト等）
- **failed が 0件**: エラーがないこと

> **テストが失敗する場合**: 依存関係が正しくインストールされていない可能性があります。
> `pip install -r requirements-dev.txt` を再度実行してみてください。

### 5.2 flake8 の実行

flake8 はPythonのコードスタイルチェックツール（リンター）です。
コードが規約に従っているかを確認します。

```powershell
# flake8 でコードスタイルを確認
flake8 src/ --max-line-length=120 --statistics
```

エラーが大量に出る場合でも、テストが通っていれば開発を進められます。
新しく書くコードではflake8のルールに従うことを推奨します。

### 5.3 ローカルサーバーの起動テスト（オプション）

APIサーバーをローカル環境で起動して動作確認することもできます。

```powershell
# ローカルサーバーの起動
python -m uvicorn src.main:app --reload --port 8000
```

ブラウザで `http://localhost:8000/docs` にアクセスすると、
Swagger UI（APIドキュメント画面）が表示されます。

---

## 6. 各プラットフォーム共通の環境変数

### 6.1 基本設定

`.env` ファイルで設定する共通の環境変数一覧です。

| 変数名 | 値の例 | 説明 |
| --- | --- | --- |
| `LLM_PROVIDER` | `AZURE_FOUNDRY` | LLMプロバイダーの選択。`AZURE_FOUNDRY`, `AZURE`, `GCP`, `AWS`, `LOCAL` のいずれか |
| `OCR_PROVIDER` | `AZURE` | OCRプロバイダーの選択。`AZURE`, `AWS`, `GCP`, `TESSERACT`, `YOMITOKU`, `NONE` のいずれか |
| `MAX_PLAN_REVISIONS` | `1` | 計画レビューの最大修正回数（0でスキップ） |
| `MAX_JUDGMENT_REVISIONS` | `1` | 判断レビューの最大修正回数（0でスキップ） |
| `SKIP_PLAN_CREATION` | `false` | 計画作成を省略するか（`true` / `false`） |

### 6.2 Azure 固有の環境変数

| 変数名 | 説明 |
| --- | --- |
| `AZURE_FOUNDRY_ENDPOINT` | Azure AI Foundry のエンドポイントURL |
| `AZURE_FOUNDRY_API_KEY` | Azure AI Foundry のAPIキー |
| `AZURE_FOUNDRY_MODEL` | 使用するモデル名（例: `gpt-5.2`） |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI Service のエンドポイント |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI Service のAPIキー |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | デプロイメント名 |
| `AZURE_DI_ENDPOINT` | Azure Document Intelligence のエンドポイント |
| `AZURE_DI_KEY` | Azure Document Intelligence のキー |
| `AZURE_STORAGE_CONNECTION_STRING` | Azure Storage の接続文字列（非同期ジョブ用） |

### 6.3 AWS 固有の環境変数

| 変数名 | 説明 |
| --- | --- |
| `AWS_REGION` | AWSリージョン（例: `ap-northeast-1`） |
| `AWS_ACCESS_KEY_ID` | AWSアクセスキーID |
| `AWS_SECRET_ACCESS_KEY` | AWSシークレットアクセスキー |
| `AWS_BEDROCK_MODEL_ID` | Bedrock モデルID（例: `global.anthropic.claude-opus-4-6-v1`） |
| `AWS_DYNAMODB_TABLE_NAME` | DynamoDB テーブル名（非同期ジョブ用） |
| `AWS_SQS_QUEUE_URL` | SQS キューURL（非同期ジョブ用） |

### 6.4 GCP 固有の環境変数

| 変数名 | 説明 |
| --- | --- |
| `GCP_PROJECT_ID` | GCPプロジェクトID |
| `GCP_LOCATION` | リージョン（例: `global` または `us-central1`） |
| `GCP_MODEL_NAME` | Vertex AI モデル名（例: `gemini-3-pro-preview`） |
| `GCP_DOCAI_PROJECT_ID` | Document AI のプロジェクトID |
| `GCP_DOCAI_LOCATION` | Document AI のリージョン |
| `GCP_DOCAI_PROCESSOR_ID` | Document AI のプロセッサID |
| `GCP_FIRESTORE_COLLECTION` | Firestore コレクション名（非同期ジョブ用） |
| `GCP_TASKS_QUEUE_PATH` | Cloud Tasks キューパス（非同期ジョブ用） |

### 6.5 非同期ジョブ処理の環境変数

大量データを処理する場合の非同期処理（504タイムアウト対策）に必要な設定です。

| 変数名 | 値の例 | 説明 |
| --- | --- | --- |
| `JOB_STORAGE_PROVIDER` | `AZURE` | ジョブ保存先。`AZURE`, `AWS`, `GCP`, `MEMORY` のいずれか |
| `JOB_QUEUE_PROVIDER` | `AZURE` | ジョブキュー。`AZURE`, `AWS`, `GCP`, `MEMORY` のいずれか |

> **MEMORY**: 開発・テスト用のインメモリ実装です。サーバーを再起動するとデータが消えます。
> 本番環境では使用しないでください。

---

## 7. よくある問題と解決策

### 7.1 OneDrive パス問題

**症状**: パスに日本語が含まれているためエラーが発生する

本プロジェクトのパスには `ドキュメント` という日本語が含まれています。

```text
C:\Users\goyos\OneDrive\ドキュメント\VSCode_Dev\PythonDev\ic-test-ai-agent
```

一部のツールやライブラリは日本語パスを正しく処理できないことがあります。

**対策**:

1. パスを引用符で囲んで使用する

```powershell
cd "C:\Users\goyos\OneDrive\ドキュメント\VSCode_Dev\PythonDev\ic-test-ai-agent"
```

2. 問題が解決しない場合は、日本語を含まないパスにプロジェクトをクローンする

```powershell
# 日本語を含まないパスにクローン
git clone <リポジトリURL> C:\Dev\ic-test-ai-agent
```

### 7.2 venv と OneDrive の競合

**症状**: 仮想環境の作成が非常に遅い、またはOneDriveの同期が終わらない

仮想環境（`.venv`）には数千個の小さなファイルが含まれます。
OneDriveがこれらを同期しようとすると、PCの動作が遅くなります。

**対策**:

方法1: `.venv` フォルダをOneDriveの同期対象から除外する

```text
1. タスクバーのOneDriveアイコンを右クリック
2. 「設定」を開く
3. 「同期とバックアップ」タブ
4. 「この PC のフォルダーをバックアップ」から、
   仮想環境フォルダを除外する
```

方法2: OneDrive外に仮想環境を作成する

```powershell
# OneDrive外のパスに仮想環境を作成
python -m venv C:\PythonEnvs\ic-test-ai-agent

# 仮想環境を有効化
C:\PythonEnvs\ic-test-ai-agent\Scripts\Activate.ps1
```

方法3: 一時的にOneDrive同期を停止してから作成する

```text
1. タスクバーのOneDriveアイコンを右クリック
2. 「同期の一時停止」→「2時間」を選択
3. 仮想環境を作成
4. .venv フォルダを同期除外に設定
5. OneDriveの同期を再開
```

### 7.3 import エラー

**症状**: `ModuleNotFoundError: No module named 'xxx'`

**原因と対策**:

1. **仮想環境が有効になっていない**

```powershell
# プロンプトに (.venv) が表示されているか確認
# 表示されていない場合は有効化する
.\.venv\Scripts\Activate.ps1
```

2. **依存関係がインストールされていない**

```powershell
pip install -r requirements.txt -r requirements-dev.txt
```

3. **PYTHONPATHが設定されていない**

テストを実行する際に `src` ディレクトリがPythonのモジュール検索パスに
含まれていない場合があります。

```powershell
# プロジェクトルートからテストを実行する場合
$env:PYTHONPATH = "."
python -m pytest tests/ -v
```

### 7.4 pip インストール失敗

**症状**: `pip install` 時にエラーが発生する

**対策1**: pip を最新版に更新する

```powershell
python -m pip install --upgrade pip
```

**対策2**: キャッシュをクリアして再インストール

```powershell
pip cache purge
pip install -r requirements.txt --no-cache-dir
```

**対策3**: プロキシ環境での設定

社内ネットワークでプロキシを使用している場合は、プロキシ設定が必要です。

```powershell
# プロキシ設定付きでインストール
pip install -r requirements.txt --proxy http://proxy.example.com:8080
```

または、環境変数で設定する方法もあります。

```powershell
$env:HTTP_PROXY = "http://proxy.example.com:8080"
$env:HTTPS_PROXY = "http://proxy.example.com:8080"
pip install -r requirements.txt
```

### 7.5 PowerShell の実行ポリシーエラー

**症状**: `.ps1` スクリプトが実行できない

```text
.\.venv\Scripts\Activate.ps1 : このシステムではスクリプトの実行が無効になっているため...
```

**対策**:

```powershell
# 現在のユーザーのみ実行ポリシーを変更
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

## 8. 次のステップ

環境構築が完了したら、使用するクラウドプラットフォームのセットアップガイドに進んでください。

| プラットフォーム | ガイド | 主なサービス |
| --- | --- | --- |
| Azure | [AZURE_SETUP.md](./AZURE_SETUP.md) | Azure Functions, Azure AI Foundry, APIM |
| AWS | [AWS_SETUP.md](./AWS_SETUP.md) | Lambda, API Gateway, Bedrock |
| GCP | [GCP_SETUP.md](./GCP_SETUP.md) | Cloud Functions, Vertex AI, Apigee |

クライアント（Excel VBA / PowerShell）の設定は以下を参照してください。

- [CLIENT_SETUP.md](./CLIENT_SETUP.md) - VBA / PowerShell クライアントの設定手順

その他の運用ガイド:

- [DEPLOYMENT_GUIDE.md](../operations/DEPLOYMENT_GUIDE.md) - デプロイ手順
- [TROUBLESHOOTING.md](../operations/TROUBLESHOOTING.md) - 問題解決ガイド
- [MONITORING_RUNBOOK.md](../operations/MONITORING_RUNBOOK.md) - 監視運用手順
- [CORRELATION_ID.md](../monitoring/CORRELATION_ID.md) - 相関IDの技術詳細

---

> **このドキュメントに関するフィードバック**: 不明点や改善提案がありましたら、
> プロジェクトのIssueとして報告してください。
