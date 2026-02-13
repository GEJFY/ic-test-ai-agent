# Azure環境セットアップガイド - 内部統制テスト評価AIシステム

---

## 目次

1. [はじめに](#1-はじめに)
2. [Azureとは](#2-azureとは)
3. [Azure CLIのセットアップ](#3-azure-cliのセットアップ)
4. [リソースグループの作成](#4-リソースグループの作成)
5. [Azure Container Apps](#5-azure-container-apps)
6. [Azure AI Foundry (GPT-5.2)](#6-azure-ai-foundry-gpt-52)
7. [Document Intelligence](#7-document-intelligence)
8. [API Management (APIM)](#8-api-management-apim)
9. [Key Vault](#9-key-vault)
10. [Application Insights](#10-application-insights)
11. [Storage Account](#11-storage-account)
12. [Bicepデプロイ（Infrastructure as Code）](#12-bicepデプロイinfrastructure-as-code)
13. [統合テスト](#13-統合テスト)
14. [コスト管理](#14-コスト管理)
15. [まとめ・次のステップ](#15-まとめ次のステップ)

---

## 1. はじめに

### このガイドの目的

このガイドは、**内部統制テスト評価AIシステム**をAzure上にデプロイするための**完全なチュートリアル**です。
Azure未経験の方でも、このガイドに沿って進めるだけで以下のスキルが身に付くよう設計されています。

- Azureクラウドの基本概念の理解
- Azure CLIを使ったリソース管理
- コンテナアーキテクチャの構築
- AI/MLサービスの設定と利用
- API Gatewayの構築と認証設定
- シークレット管理とセキュリティのベストプラクティス
- Infrastructure as Code（Bicep）による自動デプロイ
- 監視・ログ分析の基礎

### 前提条件チェックリスト

開始前に、以下が揃っているか確認してください。

- [ ] Microsoftアカウント（Outlookメールアドレス等）を持っている
- [ ] クレジットカード（Azure無料アカウント登録用、課金されない設定も可能）
- [ ] Windows 10/11、macOS、またはLinux環境
- [ ] インターネット接続
- [ ] Python 3.11がインストール済み
- [ ] Visual Studio Code（推奨）がインストール済み
- [ ] このリポジトリがclone済み

### 所要時間の目安

| セクション | 所要時間 | 難易度 |
|-----------|---------|--------|
| Azure CLIセットアップ | 15分 | ★☆☆ |
| リソースグループ作成 | 5分 | ★☆☆ |
| Azure Container Apps | 30分 | ★★☆ |
| Azure AI Foundry | 20分 | ★★☆ |
| Document Intelligence | 15分 | ★★☆ |
| API Management | 30分 | ★★★ |
| Key Vault | 20分 | ★★☆ |
| Application Insights | 15分 | ★★☆ |
| Storage Account | 10分 | ★☆☆ |
| Bicepデプロイ | 30分 | ★★★ |
| 統合テスト | 20分 | ★★☆ |
| **合計** | **約3.5時間** | |

### 記号の説明

| 記号 | 意味 |
|------|------|
| 💡 | ヒント・便利な情報 |
| ⚠️ | 注意・重要な警告 |
| ✅ | 確認ポイント（ここで動作確認を行う） |
| 📖 | 学習ポイント（概念の解説） |

---

## 2. Azureとは

### 📖 クラウドサービスの概要

**クラウドサービス**とは、インターネット経由でサーバー、ストレージ、データベース、AI/MLなどのITリソースを利用できるサービスです。自社でサーバーを購入・管理する必要がなく、必要な分だけ使って料金を支払う「従量課金制」が基本です。

世界の3大クラウドプロバイダーは以下の通りです。

| プロバイダー | 提供元 | シェア（概算） |
|------------|--------|-------------|
| AWS (Amazon Web Services) | Amazon | 約31% |
| **Microsoft Azure** | Microsoft | **約25%** |
| GCP (Google Cloud Platform) | Google | 約11% |

### なぜAzureを使うのか

本プロジェクトでAzureを選択した主な理由は以下の通りです。

1. **Azure AI Foundry** - GPT-5.2等の複数モデルをエンタープライズ環境で安全に利用可能
2. **Document Intelligence** - 日本語の業務文書（PDF、Excel等）のOCR処理に強い
3. **統合セキュリティ** - Key Vault、Managed Identity等でシークレット管理が容易
4. **日本リージョン** - japaneast（東日本）リージョンでデータ主権を確保
5. **エンタープライズ対応** - Active Directory統合、コンプライアンス対応が充実

### Azureアカウント作成手順

1. [Azure無料アカウント作成ページ](https://azure.microsoft.com/ja-jp/free/) にアクセス
2. 「無料で始める」をクリック
3. Microsoftアカウントでサインイン（なければ新規作成）
4. 電話番号認証とクレジットカード情報を入力
5. 利用規約に同意して登録完了

💡 **無料枠について**: Azureの無料アカウントには以下が含まれます。
- 最初の30日間で使える**200ドル（約30,000円）分のクレジット**
- 12か月間無料のサービス（一部のVMやStorage等）
- 永久無料のサービス（Azure Container Apps月180,000 vCPU秒無料、AI Services月5,000トランザクション等）

⚠️ **注意**: 無料クレジットを超過すると課金が開始されます。このガイドの「コスト管理」セクションを必ず確認してください。

### Azure Portalの基本操作

**Azure Portal** (https://portal.azure.com) は、Azureリソースを管理するためのWebベースの管理画面です。

ログイン後の主要な画面要素は以下の通りです。

- **ダッシュボード**: ホーム画面。ピン留めしたリソースが表示される
- **リソースグループ**: 関連するリソースをまとめるフォルダのようなもの
- **検索バー**: 画面上部。リソース名やサービス名で検索できる
- **Cloud Shell**: 画面上部の `>_` アイコン。ブラウザ内でCLIが使える

💡 **ヒント**: Azure Portalは便利ですが、このガイドでは主に**Azure CLI（コマンドライン）** を使います。理由は「再現性」と「自動化」のためです。GUIでの操作は手順書として残しにくいですが、コマンドなら正確に記録・再実行できます。

---

## 3. Azure CLIのセットアップ

### 📖 Azure CLIとは

**Azure CLI (Command Line Interface)** は、コマンドラインからAzureリソースを管理するためのツールです。
すべてのAzure操作を `az` コマンドで実行できます。

**なぜGUIではなくCLIを使うのか？**

| 観点 | GUI (Portal) | CLI |
|------|-------------|-----|
| 再現性 | 手順書が必要 | コマンドをコピペすれば再現可能 |
| 自動化 | 手動操作のみ | スクリプトで自動化可能 |
| 速度 | クリックを繰り返す | コマンド1行で完了 |
| バージョン管理 | 不可 | Git管理可能 |
| Infrastructure as Code | 非対応 | Bicep/Terraform連携可能 |

### インストール手順

#### Windows（推奨: PowerShell）

```powershell
# 方法1: wingetを使ったインストール（推奨）
winget install -e --id Microsoft.AzureCLI
```

上記コマンドの意味:
- `winget install`: Windowsパッケージマネージャーでインストール
- `-e`: 完全一致でパッケージを検索
- `--id Microsoft.AzureCLI`: Azure CLIのパッケージID

```powershell
# 方法2: MSIインストーラーを使う場合
# https://aka.ms/installazurecliwindows からダウンロード
```

#### macOS

```bash
# Homebrewを使ったインストール
brew update && brew install azure-cli
```

#### Linux (Ubuntu/Debian)

```bash
# Microsoft署名鍵のインストールとリポジトリ追加
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

### インストール確認

```powershell
az version
```

期待される出力:
```json
{
  "azure-cli": "2.67.0",
  "azure-cli-core": "2.67.0",
  "azure-cli-telemetry": "1.1.0",
  "extensions": {}
}
```

✅ **確認ポイント**: `az version` でバージョン番号が表示されればインストール成功です。

### Azure CLIログイン（認証フロー）

```powershell
az login
```

このコマンドを実行すると:
1. デフォルトブラウザが自動的に開きます
2. Microsoftアカウントでログイン画面が表示されます
3. ログイン完了後、ブラウザに「認証完了」のメッセージが表示されます
4. ターミナルに戻ると、サブスクリプション情報が表示されます

期待される出力:
```json
[
  {
    "cloudName": "AzureCloud",
    "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "isDefault": true,
    "name": "Azure subscription 1",
    "state": "Enabled",
    "tenantId": "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy",
    "user": {
      "name": "your-email@example.com",
      "type": "user"
    }
  }
]
```

📖 **学習ポイント**: ここに表示される `id` が**サブスクリプションID**です。Azureでは、すべてのリソースが必ずいずれかのサブスクリプションに所属します。サブスクリプションは「請求書の単位」と考えてください。

### サブスクリプション確認

```powershell
az account show --output table
```

このコマンドの意味:
- `az account show`: 現在選択中のサブスクリプションを表示
- `--output table`: 結果をテーブル形式で見やすく表示（他に `json`, `tsv`, `yaml` が指定可能）

期待される出力:
```
EnvironmentName    IsDefault    Name                  State    TenantId
-----------------  -----------  --------------------  -------  ------------------------------------
AzureCloud         True         Azure subscription 1  Enabled  yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy
```

### 複数サブスクリプションの切り替え

会社のAzure環境では、複数のサブスクリプション（開発用、本番用など）を持つことがあります。

```powershell
# 利用可能なサブスクリプション一覧を表示
az account list --output table

# 特定のサブスクリプションに切り替え
az account set --subscription "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

コマンドの意味:
- `az account list`: このアカウントで利用可能な全サブスクリプションを表示
- `az account set --subscription`: 操作対象のサブスクリプションを切り替え

💡 **ヒント**: サブスクリプションIDの代わりにサブスクリプション名も使えます:
```powershell
az account set --subscription "Azure subscription 1"
```

### よくあるエラーと対策

| エラー | 原因 | 対策 |
|--------|------|------|
| `az: command not found` | Azure CLIが未インストール | インストール手順を再実行 |
| `AADSTS50076` | 多要素認証(MFA)が必要 | `az login --tenant <TENANT_ID>` を試す |
| `No subscriptions found` | アカウントにサブスクリプションがない | Azure Portalで無料アカウント登録を確認 |
| `The subscription is disabled` | サブスクリプションが無効 | Azure Portalで支払い情報を確認 |

---

## 4. リソースグループの作成

### 📖 リソースグループとは

**リソースグループ (Resource Group)** は、Azureリソースをまとめて管理するための**論理的なコンテナ**です。

```
Azureサブスクリプション
  └── リソースグループ: rg-ic-test-ai-prod
        ├── Azure Container Apps（APIバックエンド）
        ├── Storage Account（データ保存）
        ├── Azure AI Foundry（GPT-5 Nano）
        ├── Document Intelligence（文書OCR）
        ├── API Management（API Gateway）
        ├── Key Vault（シークレット管理）
        ├── Application Insights（監視）
        └── Log Analytics Workspace（ログ集約）
```

**なぜリソースグループが必要なのか？**

1. **一括管理**: 関連リソースをグループ化して管理できる
2. **一括削除**: リソースグループを削除すると中のリソースがすべて削除される（テスト後のクリーンアップが簡単）
3. **アクセス制御**: リソースグループ単位でアクセス権限を設定できる
4. **コスト管理**: リソースグループ単位でコストを確認できる
5. **タグ付け**: 環境（dev/stg/prod）やプロジェクト名でタグを付けられる

### リソースグループの作成

```powershell
az group create --name rg-ic-test-ai-prod --location japaneast
```

各パラメータの意味:
- `az group create`: リソースグループを新規作成するコマンド
- `--name rg-ic-test-ai-prod`: リソースグループ名。命名規則 `rg-<プロジェクト名>-<環境>` を推奨
- `--location japaneast`: リソースのデプロイ先リージョン

期待される出力:
```json
{
  "id": "/subscriptions/xxxxxxxx/resourceGroups/rg-ic-test-ai-prod",
  "location": "japaneast",
  "managedBy": null,
  "name": "rg-ic-test-ai-prod",
  "properties": {
    "provisioningState": "Succeeded"
  },
  "tags": null,
  "type": "Microsoft.Resources/resourceGroups"
}
```

📖 **学習ポイント - リージョン選択の考慮事項**:

| リージョン | 場所 | 本プロジェクトでの推奨度 | 理由 |
|-----------|------|----------------------|------|
| japaneast | 東日本（東京/埼玉） | ★★★ **推奨** | 低遅延、データ主権確保 |
| japanwest | 西日本（大阪） | ★★☆ | DR用途に適切 |
| eastus | 米国東部 | ★☆☆ | AI系サービスが先行提供されるが遅延が大きい |

⚠️ **注意**: 一部のAzureサービス（Azure AI Foundry等）は特定リージョンでのみ利用可能な場合があります。japaneastは主要サービスを網羅しています。

### 作成確認

```powershell
az group show --name rg-ic-test-ai-prod --output table
```

期待される出力:
```
Location    Name                 ProvisioningState
----------  -------------------  -------------------
japaneast   rg-ic-test-ai-prod   Succeeded
```

✅ **確認ポイント**: `ProvisioningState` が `Succeeded` になっていれば成功です。

---

## 5. Azure Container Apps

### 📖 コンテナとは

**コンテナ** は、アプリケーションとその依存関係（ライブラリ、ランタイム等）を1つのパッケージにまとめる技術です。Dockerイメージとしてビルドし、どの環境でも同じように動作します。

| 観点 | 従来型サーバー | コンテナ（Azure Container Apps） |
|------|-------------|------------|
| サーバー管理 | 自分で管理（OS更新、パッチ適用等） | クラウドが自動管理 |
| スケーリング | 手動またはルール設定 | 自動スケーリング（ゼロスケール対応） |
| 課金 | 常時稼働分の費用 | **従量課金（Consumptionプラン）** |
| ポータビリティ | 環境依存 | **Dockerイメージで環境非依存** |

本プロジェクトでは、Azure Container Appsを「APIバックエンド」として使います。VBAやPowerShellからHTTPリクエストを受け取り、AI評価を実行して結果を返します。

### 📖 Azure Container Appsの仕組み

Azure Container Appsは**コンテナベース**のマネージドコンピューティングサービスです。

```
クライアント                    Azure Container Apps             AIサービス
(VBA/PowerShell)                (Docker + Python 3.11)
    │                               │                              │
    ├── HTTP POST /evaluate ──────→ │                              │
    │                               ├── コンテナで処理             │
    │                               ├── リクエスト解析             │
    │                               ├── GPT-5 Nano呼び出し ──────→ │
    │                               │ ←──── 評価結果 ─────────────┤
    │                               ├── レスポンス生成             │
    │ ←────── 評価結果JSON ─────────┤                              │
```

主要な概念:
- **Container App Environment**: Container Appsを実行する環境（ネットワーク等を共有）
- **コンテナイメージ**: アプリケーションをDockerイメージとしてパッケージ化
- **Ingress**: HTTPトラフィックの受信設定（外部/内部アクセス制御）
- **スケーリングルール**: HTTPリクエスト数に応じたオートスケール

### Dockerとaz CLIのインストール

ローカルでコンテナの開発・テストを行うために、DockerとAzure CLIをインストールします。

```powershell
# Docker Desktopのインストール（Windows推奨）
winget install -e --id Docker.DockerDesktop

# インストール確認
docker --version
```

期待される出力:
```
Docker version 27.x.x, build xxxxxxx
```

💡 **ヒント**: Docker Desktopのインストール後、WSL2バックエンドが有効になっていることを確認してください。設定 → General → 「Use the WSL 2 based engine」にチェック。

### ローカルでのプロジェクト作成と動作確認

本プロジェクトにはDockerfileが含まれており、`platforms/local/main.py`（FastAPI）をエントリーポイントとしてコンテナを起動します。

```powershell
# プロジェクトルートでDockerイメージをビルド
docker build -t ic-test-ai-agent .
```

ビルドに使用される主要ファイル:
```
ic-test-ai-agent/
├── Dockerfile              ← コンテナ定義ファイル
├── requirements.txt        ← Python依存パッケージ
├── src/                    ← 共通ソースコード
└── platforms/local/main.py ← FastAPIエントリーポイント
```

### 環境変数の設定

ローカル開発時の環境変数は `.env` ファイルで管理します。

```ini
# .env ファイル
LLM_PROVIDER=AZURE_FOUNDRY
AZURE_FOUNDRY_API_KEY=<後で設定>
AZURE_FOUNDRY_ENDPOINT=<後で設定>
AZURE_FOUNDRY_MODEL=gpt-5-nano
```

⚠️ **注意**: `.env` ファイルにはAPIキー等の機密情報が含まれます。`.gitignore` に必ず含めてください。

### ローカルテスト実行

```powershell
# Dockerコンテナをローカルで起動
docker run --env-file .env -p 8000:8000 ic-test-ai-agent
```

期待される出力:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

✅ **確認ポイント**: `http://localhost:8000/health` にアクセスしてヘルスチェックが成功すれば、ローカルでコンテナが正常に動作しています。

### クラウドへのデプロイ

Azure Container Registryにイメージをプッシュし、Container Appsにデプロイします。

```powershell
# Azure Container Registryの作成
az acr create `
  --resource-group rg-ic-test-ai-prod `
  --name acrictestaiprod `
  --sku Basic

# ACRにログイン
az acr login --name acrictestaiprod

# Dockerイメージをタグ付け＆プッシュ
docker tag ic-test-ai-agent acrictestaiprod.azurecr.io/ic-test-ai-agent:latest
docker push acrictestaiprod.azurecr.io/ic-test-ai-agent:latest

# Container App Environmentの作成
az containerapp env create `
  --name cae-ic-test-ai-prod `
  --resource-group rg-ic-test-ai-prod `
  --location japaneast

# Container Appの作成
az containerapp create `
  --name ca-ic-test-ai-prod `
  --resource-group rg-ic-test-ai-prod `
  --environment cae-ic-test-ai-prod `
  --image acrictestaiprod.azurecr.io/ic-test-ai-agent:latest `
  --registry-server acrictestaiprod.azurecr.io `
  --target-port 8000 `
  --ingress external `
  --cpu 1.0 --memory 2.0Gi `
  --min-replicas 0 --max-replicas 10
```

各パラメータの意味:
- `--resource-group`: デプロイ先のリソースグループ
- `--environment`: Container App Environment名
- `--image`: デプロイするDockerイメージ
- `--target-port 8000`: コンテナが待ち受けるポート
- `--ingress external`: 外部からのHTTPアクセスを許可
- `--cpu 1.0 --memory 2.0Gi`: コンテナに割り当てるCPU/メモリ
- `--min-replicas 0`: 最小レプリカ数（0でゼロスケール対応）
- `--max-replicas 10`: 最大レプリカ数

💡 **ヒント**: 本プロジェクトでは、このContainer AppをBicepテンプレートで自動作成します（セクション12参照）。ここでは理解のために手動手順を説明しています。

期待される出力:
```
Container app created. Access your app at https://ca-ic-test-ai-prod.xxxxx.japaneast.azurecontainerapps.io/
```

### よくあるエラーと対策

| エラー | 原因 | 対策 |
|--------|------|------|
| `docker: command not found` | Docker未インストール | Docker Desktopをインストール |
| `unauthorized: authentication required` | ACR認証が切れている | `az acr login --name <ACR名>` を再実行 |
| `Container app name already in use` | Container App名が既に使われている | 名前を変更（一意にする） |
| `ImagePullBackOff` | イメージのプルに失敗 | ACRのイメージタグとレジストリ設定を確認 |

---

## 6. Azure AI Foundry (GPT-5.2)

### Azure AI Foundryとは

**Azure AI Foundry**は、GPT-5.2、Claude、Phi-4、Mistral等の複数モデルをAzureのエンタープライズ環境で統合的に利用できるプラットフォームです。

**本システムではAzure AI Foundry（`LLM_PROVIDER=AZURE_FOUNDRY`）を推奨します。**

| 観点 | OpenAI API直接 | Azure AI Foundry |
|------|---------------|-----------------|
| データ所在地 | 米国 | **選択したリージョン（japaneast等）** |
| SLA | なし | **99.9%のSLA保証** |
| コンプライアンス | 限定的 | **SOC2, ISO27001等** |
| ネットワーク | パブリック | **VNet統合、Private Endpoint対応** |
| データ利用 | 学習に使われる可能性 | **学習には使われない** |
| モデル選択 | OpenAIのみ | **GPT-5.2, Claude, Phi-4, Mistral等** |

### Azure AI Foundryリソースの作成

```powershell
# Azure AI Foundryリソース作成
az cognitiveservices account create `
  --name ic-test-ai-foundry `
  --resource-group rg-ic-test-ai-prod `
  --kind OpenAI `
  --sku S0 `
  --location japaneast
```

各パラメータの意味:

- `--name ic-test-ai-foundry`: リソース名
- `--kind OpenAI`: サービスの種類（Azure AI Foundryの内部種別）
- `--sku S0`: 料金プラン。S0は標準プラン
- `--location japaneast`: 東日本リージョン

期待される出力:
```json
{
  "id": "/subscriptions/.../resourceGroups/rg-ic-test-ai-prod/providers/Microsoft.CognitiveServices/accounts/ic-test-ai-foundry",
  "kind": "OpenAI",
  "location": "japaneast",
  "name": "ic-test-ai-foundry",
  "properties": {
    "provisioningState": "Succeeded"
  },
  "sku": {
    "name": "S0"
  }
}
```

### GPT-5.2モデルのデプロイ

リソースを作成しただけではモデルは使えません。次に、モデルを**デプロイ**します。

```powershell
# GPT-5 Nanoモデルをデプロイ（コスト効率重視の推奨モデル）
az cognitiveservices account deployment create `
  --name ic-test-ai-foundry `
  --resource-group rg-ic-test-ai-prod `
  --deployment-name gpt-5-nano `
  --model-name gpt-5-nano `
  --model-version "2026-01-01" `
  --model-format OpenAI `
  --sku-capacity 10 `
  --sku-name "Standard"
```

各パラメータの意味:

- `--deployment-name gpt-5-nano`: デプロイメント名（API呼び出し時に使用）
- `--model-name gpt-5-nano`: GPT-5 Nano（高速・低レイテンシ、推奨）
- `--model-version "2026-01-01"`: モデルバージョン
- `--sku-capacity 10`: トークン/分の割当量（1000トークン/分単位）。10 = 10K TPM
- `--sku-name "Standard"`: デプロイメントの種類

### エンドポイントとAPIキーの取得

```powershell
# エンドポイントの取得
az cognitiveservices account show `
  --name ic-test-ai-foundry `
  --resource-group rg-ic-test-ai-prod `
  --query "properties.endpoint" `
  --output tsv
```

期待される出力:
```
https://ic-test-ai-foundry.openai.azure.com/
```

```powershell
# APIキーの取得
az cognitiveservices account keys list `
  --name ic-test-ai-foundry `
  --resource-group rg-ic-test-ai-prod `
  --query "key1" `
  --output tsv
```

### Python SDKでの呼び出しテスト

```python
# test_foundry.py - Azure AI Foundry接続テスト
from openai import AzureOpenAI

client = AzureOpenAI(
    api_key="<取得したAPIキー>",
    api_version="2024-08-01-preview",
    azure_endpoint="https://ic-test-ai-foundry.openai.azure.com/"
)

response = client.chat.completions.create(
    model="gpt-5-nano",  # デプロイメント名
    messages=[
        {"role": "system", "content": "あなたは内部統制の専門家です。"},
        {"role": "user", "content": "内部統制テストの目的を簡潔に説明してください。"}
    ],
    max_tokens=500
)

print(response.choices[0].message.content)
```

```powershell
# テスト実行
pip install openai
python test_foundry.py
```

期待される出力例:
```
内部統制テストの目的は、組織内の業務プロセスに設計された統制活動が、
実際に有効に機能しているかを検証することです。具体的には...
```

✅ **確認ポイント**: GPT-5 Nanoからの応答が日本語で返ってくれば、Azure AI Foundryの設定は成功です。

### 環境変数の設定

以下の環境変数をFunction Appまたはローカル開発環境に設定します。

| 環境変数名 | 説明 | 例 |
|-----------|------|-----|
| `LLM_PROVIDER` | LLMプロバイダー指定 | `AZURE_FOUNDRY` |
| `AZURE_FOUNDRY_API_KEY` | APIキー | `abcdef1234...` |
| `AZURE_FOUNDRY_ENDPOINT` | エンドポイントURL | `https://ic-test-ai-foundry.openai.azure.com/` |
| `AZURE_FOUNDRY_MODEL` | モデル名 | `gpt-5-nano` |

### トークン使用量とコスト管理

GPT-5シリーズの料金はトークン数に基づきます。

| モデル | 入力トークン | 出力トークン |
|--------|------------|------------|
| GPT-5.2 | $2.50 / 100万トークン | $10.00 / 100万トークン |
| GPT-5 Nano | $0.10 / 100万トークン | $0.40 / 100万トークン |

💡 **ヒント**: 内部統制テスト1件あたり約2,000~5,000トークンを使用します。GPT-5 Nanoで1000件の評価で約$1~$3（約150~450円）が目安です。

---

## 7. Document Intelligence

### 📖 Document Intelligence（旧Form Recognizer）とは

**Azure AI Document Intelligence** は、PDF、画像、Office文書からテキストや構造化データを抽出するAIサービスです。
内部統制テストでは、証跡として提出された業務文書（稟議書、承認書、チェックリスト等）を読み取るために使用します。

主な機能:
- **OCR（光学文字認識）**: 画像やスキャンPDFからテキストを抽出
- **レイアウト分析**: テーブル、段落、見出しの構造を認識
- **文書分類**: 文書の種類を自動判定
- **日本語対応**: 日本語の印刷文字・手書き文字に対応

### リソース作成

```powershell
az cognitiveservices account create `
  --name ic-test-doc-intel `
  --resource-group rg-ic-test-ai-prod `
  --kind FormRecognizer `
  --sku S0 `
  --location japaneast
```

各パラメータの意味:
- `--kind FormRecognizer`: Document Intelligenceの内部サービス名は `FormRecognizer`
- `--sku S0`: 標準プラン。無料プラン (F0) もあるが月500ページまで

期待される出力:
```json
{
  "kind": "FormRecognizer",
  "location": "japaneast",
  "name": "ic-test-doc-intel",
  "properties": {
    "provisioningState": "Succeeded"
  }
}
```

### エンドポイントとキー取得

```powershell
# エンドポイント取得
az cognitiveservices account show `
  --name ic-test-doc-intel `
  --resource-group rg-ic-test-ai-prod `
  --query "properties.endpoint" `
  --output tsv
```

期待される出力:
```
https://ic-test-doc-intel.cognitiveservices.azure.com/
```

```powershell
# APIキー取得
az cognitiveservices account keys list `
  --name ic-test-doc-intel `
  --resource-group rg-ic-test-ai-prod `
  --query "key1" `
  --output tsv
```

### Python SDKインストールとテスト

```powershell
pip install azure-ai-documentintelligence
```

```python
# test_doc_intel.py - Document Intelligence接続テスト
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential

endpoint = "https://ic-test-doc-intel.cognitiveservices.azure.com/"
key = "<取得したAPIキー>"

client = DocumentIntelligenceClient(
    endpoint=endpoint,
    credential=AzureKeyCredential(key)
)

# サンプルPDFの分析
with open("sample.pdf", "rb") as f:
    poller = client.begin_analyze_document(
        "prebuilt-layout",  # レイアウト分析モデル
        body=f,
        content_type="application/pdf"
    )
    result = poller.result()

# 結果表示
for page in result.pages:
    print(f"--- ページ {page.page_number} ---")
    for line in page.lines:
        print(f"  {line.content}")
```

### 対応ドキュメント形式

| 形式 | 拡張子 | 備考 |
|------|--------|------|
| PDF | `.pdf` | スキャンPDF対応 |
| JPEG/PNG | `.jpg`, `.png` | 写真・スクリーンショット |
| TIFF | `.tiff` | 高解像度スキャン |
| BMP | `.bmp` | ビットマップ画像 |
| Microsoft Office | `.docx`, `.xlsx`, `.pptx` | Office文書直接 |

✅ **確認ポイント**: PDFファイルを読み込んでテキストが抽出できれば成功です。

### 環境変数設定

| 環境変数名 | 説明 |
|-----------|------|
| `AZURE_DOCUMENT_INTELLIGENCE_KEY` | APIキー |
| `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT` | エンドポイントURL |
| `OCR_PROVIDER` | `AZURE` を設定 |

---

## 8. API Management (APIM)

### 📖 API Managementとは

**Azure API Management (APIM)** は、APIの公開・管理・保護・監視を一元的に行う**API Gateway**サービスです。

```
クライアント          APIM                    Azure Container Apps
(VBA/PowerShell)     (API Gateway)            (バックエンド)
    │                    │                         │
    ├── API Key認証 ───→ │                         │
    │                    ├── 認証チェック           │
    │                    ├── レート制限チェック      │
    │                    ├── 相関ID付与             │
    │                    ├── リクエスト転送 ──────→ │
    │                    │ ←──── レスポンス ────────┤
    │                    ├── ログ記録               │
    │ ←──── レスポンス ──┤                         │
```

### なぜAPIMが必要か

Azure Container AppsのURLを直接公開するのではなく、APIMを経由させる理由は以下の通りです。

1. **認証 (Authentication)**: Subscription Keyによるアクセス制御
2. **レート制限 (Rate Limiting)**: 過剰なリクエストからバックエンドを保護
3. **監視 (Monitoring)**: 全APIコールのログをApplication Insightsに記録
4. **相関ID管理**: クライアントからバックエンドまでリクエストを追跡
5. **CORS設定**: ブラウザからのクロスオリジンリクエストを制御
6. **バージョン管理**: APIのバージョニングとリビジョン管理

### APIMインスタンス作成

```powershell
az apim create `
  --name apim-ic-test-ai-prod `
  --resource-group rg-ic-test-ai-prod `
  --publisher-email "admin@example.com" `
  --publisher-name "Internal Control Test AI" `
  --sku-name Consumption `
  --location japaneast
```

各パラメータの意味:
- `--name`: APIM名（**グローバルで一意**）
- `--publisher-email`: API発行者のメールアドレス（必須）
- `--publisher-name`: API発行者の組織名
- `--sku-name Consumption`: 料金プラン

📖 **学習ポイント - APIM SKUの比較**:

| SKU | 月額（概算） | 適用場面 |
|-----|------------|---------|
| **Consumption** | **実行数課金（100万回まで無料）** | **開発・小規模運用（推奨）** |
| Developer | 約$50/月 | 開発・テスト |
| Basic | 約$150/月 | 小規模本番 |
| Standard | 約$700/月 | 中規模本番 |
| Premium | 約$2,800/月 | 大規模エンタープライズ |

⚠️ **注意**: APIMのデプロイには**30~60分**かかる場合があります（特にConsumption以外のSKU）。Consumptionプランは比較的速く完了します。

### API定義の確認

本プロジェクトのBicepテンプレート（`apim.bicep`）では、以下のAPIエンドポイントが自動的に定義されます。

| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/api/evaluate` | テスト項目を同期的に評価 |
| POST | `/api/evaluate/submit` | 評価ジョブを非同期で送信 |
| GET | `/api/evaluate/status/{job_id}` | ジョブの進捗状況を取得 |
| GET | `/api/evaluate/results/{job_id}` | ジョブの評価結果を取得 |
| GET | `/api/health` | ヘルスチェック |
| GET | `/api/config` | 設定状態確認 |

### 製品（Product）とサブスクリプション

APIMでは、APIを**製品 (Product)** にグループ化し、利用者は**サブスクリプション**を通じてアクセスします。

```
製品: IC Test AI Product
  └── API: IC Test AI API
        ├── POST /evaluate
        ├── POST /evaluate/submit
        ├── GET /evaluate/status/{job_id}
        ├── GET /evaluate/results/{job_id}
        ├── GET /health
        └── GET /config

サブスクリプション: ic-test-ai-subscription
  └── Primary Key: xxxxxxxx（APIアクセス時に使用）
```

### Subscription Key取得

Bicepデプロイ後、以下のコマンドでSubscription Keyを取得します。

```powershell
# APIM名を取得（Bicepが生成した名前）
$APIM_NAME = az apim list `
  --resource-group rg-ic-test-ai-prod `
  --query "[0].name" `
  --output tsv

# Subscription Keyを取得
az apim subscription show `
  --resource-group rg-ic-test-ai-prod `
  --service-name $APIM_NAME `
  --subscription-id ic-test-ai-subscription `
  --query "primaryKey" `
  --output tsv
```

⚠️ **注意**: Subscription Keyは機密情報です。環境変数またはKey Vaultで管理してください。

### ポリシー設定

APIMポリシーは、APIリクエスト/レスポンスの処理ルールを定義するXMLです。本プロジェクトでは以下のポリシーを適用します。

```xml
<!-- APIMポリシーの概要 -->
<policies>
    <inbound>
        <!-- レート制限: IPアドレスあたり60回/分 -->
        <rate-limit-by-key
            calls="60"
            renewal-period="60"
            counter-key="@(context.Request.IpAddress)" />

        <!-- 相関IDの管理 -->
        <set-header name="X-Correlation-ID" exists-action="skip">
            <value>@(Guid.NewGuid().ToString())</value>
        </set-header>

        <!-- CORS設定 -->
        <cors allow-credentials="false">
            <allowed-origins><origin>*</origin></allowed-origins>
            <allowed-methods><method>*</method></allowed-methods>
            <allowed-headers><header>*</header></allowed-headers>
        </cors>
    </inbound>
    <backend>
        <forward-request />
    </backend>
    <outbound>
        <!-- 相関IDをレスポンスにも含める -->
        <set-header name="X-Correlation-ID" exists-action="override">
            <value>@(context.Request.Headers
                .GetValueOrDefault("X-Correlation-ID",""))</value>
        </set-header>
    </outbound>
</policies>
```

### テスト呼び出し

```powershell
# APIMのゲートウェイURLを取得
$APIM_URL = az apim show `
  --name $APIM_NAME `
  --resource-group rg-ic-test-ai-prod `
  --query "gatewayUrl" `
  --output tsv

# ヘルスチェックを実行
curl -H "Ocp-Apim-Subscription-Key: <YOUR_SUBSCRIPTION_KEY>" `
     "$APIM_URL/api/health"
```

期待される出力:
```json
{
  "status": "healthy",
  "version": "2.4.0-multiplatform",
  "llm": {"provider": "AZURE", "configured": true},
  "platform": "Azure Container Apps"
}
```

✅ **確認ポイント**: Subscription Key付きでヘルスチェックが成功すれば、APIMの設定は正しく動作しています。

### よくあるエラーと対策

| エラー | 原因 | 対策 |
|--------|------|------|
| `401 Access Denied` | Subscription Keyが間違っている | キーを再確認 |
| `429 Too Many Requests` | レート制限超過 | 1分待ってから再試行 |
| `404 Resource Not Found` | APIパスが間違っている | `/api/health` 等の正しいパスを確認 |
| APIM作成が長時間かかる | 正常な動作（特にDeveloper SKU） | 30~60分待つ |

---

## 9. Key Vault

### 📖 Key Vaultとは

**Azure Key Vault** は、APIキー、パスワード、証明書などの**機密情報（シークレット）** を安全に保管・管理するサービスです。

**なぜ環境変数ではなくKey Vaultを使うのか？**

| 観点 | 環境変数 | Key Vault |
|------|---------|-----------|
| セキュリティ | プロセスメモリに平文保存 | **暗号化されて保存** |
| アクセス制御 | OS権限に依存 | **Azure RBAC/ポリシーで厳密制御** |
| 監査ログ | なし | **全アクセスが記録される** |
| ローテーション | 手動変更 | **自動ローテーション対応** |
| 一元管理 | 各サーバーに個別設定 | **一箇所で集中管理** |
| Git漏洩リスク | `.env`が誤コミットされる | **コードにシークレットを含めない** |

本プロジェクトのBicepテンプレート（`key-vault.bicep`）では、Container AppのManaged IdentityにKey Vaultの読み取り権限を自動付与します。

### Key Vault作成

```powershell
az keyvault create `
  --name kv-ic-test-ai-prod `
  --resource-group rg-ic-test-ai-prod `
  --location japaneast `
  --sku standard `
  --enable-soft-delete true `
  --retention-days 90
```

各パラメータの意味:
- `--name`: Key Vault名（**グローバルで一意**、3~24文字、英数字とハイフンのみ）
- `--sku standard`: 標準プラン（premium はHSMバックアップ対応）
- `--enable-soft-delete true`: 誤削除時にシークレットを復元可能にする
- `--retention-days 90`: ソフトデリート後の保持期間（日数）

期待される出力:
```json
{
  "id": "/subscriptions/.../resourceGroups/rg-ic-test-ai-prod/providers/Microsoft.KeyVault/vaults/kv-ic-test-ai-prod",
  "location": "japaneast",
  "name": "kv-ic-test-ai-prod",
  "properties": {
    "provisioningState": "Succeeded",
    "vaultUri": "https://kv-ic-test-ai-prod.vault.azure.net/"
  }
}
```

### シークレットの登録

```powershell
# Azure Foundry API Keyを登録
az keyvault secret set `
  --vault-name kv-ic-test-ai-prod `
  --name "AZURE-FOUNDRY-API-KEY" `
  --value "<実際のAPIキー>"
```

コマンドの意味:
- `az keyvault secret set`: Key Vaultにシークレットを設定（新規作成 or 更新）
- `--vault-name`: 対象のKey Vault名
- `--name`: シークレット名（ハイフン区切りが推奨。アンダースコアも使用可）
- `--value`: シークレットの値

```powershell
# Azure Foundry エンドポイントを登録
az keyvault secret set `
  --vault-name kv-ic-test-ai-prod `
  --name "AZURE-FOUNDRY-ENDPOINT" `
  --value "https://ic-test-ai-foundry.openai.azure.com/"

# Document Intelligence API Keyを登録
az keyvault secret set `
  --vault-name kv-ic-test-ai-prod `
  --name "AZURE-DOCUMENT-INTELLIGENCE-KEY" `
  --value "<実際のAPIキー>"

# Document Intelligence エンドポイントを登録
az keyvault secret set `
  --vault-name kv-ic-test-ai-prod `
  --name "AZURE-DOCUMENT-INTELLIGENCE-ENDPOINT" `
  --value "https://ic-test-doc-intel.cognitiveservices.azure.com/"
```

### 登録確認

```powershell
# 登録済みシークレット一覧
az keyvault secret list `
  --vault-name kv-ic-test-ai-prod `
  --query "[].name" `
  --output table
```

期待される出力:
```
Result
-----------------------------------------
AZURE-FOUNDRY-API-KEY
AZURE-FOUNDRY-ENDPOINT
AZURE-DOCUMENT-INTELLIGENCE-KEY
AZURE-DOCUMENT-INTELLIGENCE-ENDPOINT
```

### 📖 Managed Identity（マネージドID）によるアクセス

**Managed Identity** は、AzureサービスがKey Vaultなどの他サービスに**パスワードなしで安全に接続**するための仕組みです。

```
Container App（Managed Identity有効）
    │
    ├── "私はca-ic-test-ai-prodです" と名乗る
    │
    ↓
Key Vault（アクセスポリシー設定済み）
    │
    ├── "ca-ic-test-ai-prodにはget/listの権限があります" → アクセス許可
    │
    ↓
シークレットの値を返す
```

本プロジェクトの `key-vault.bicep` では、以下のアクセスポリシーが自動設定されます:

```
// Container AppのManaged Identityに対してシークレット読み取り権限を付与
accessPolicies: [
  {
    objectId: containerAppPrincipalId  // Container AppのManaged Identity ID
    permissions: {
      secrets: ['get', 'list']        // 取得と一覧のみ（書き込み不可）
    }
  }
]
```

### Pythonからのアクセス

Container Appのコードからは、Managed Identityを使って透過的にKey Vaultにアクセスします。

```python
# src/infrastructure/secrets/azure_keyvault.py で使用されるパターン
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

# DefaultAzureCredential は Managed Identity を自動検出
credential = DefaultAzureCredential()
client = SecretClient(
    vault_url="https://kv-ic-test-ai-prod.vault.azure.net/",
    credential=credential
)

# シークレットを取得（パスワード不要！）
secret = client.get_secret("AZURE-FOUNDRY-API-KEY")
print(f"APIキー: {secret.value[:10]}...")
```

💡 **ヒント**: Container Appでは、Key Vault参照をシークレット設定に組み込むことで直接シークレットを参照できます:

```powershell
az containerapp secret set --name ca-ic-test-ai-prod --resource-group rg-ic-test-ai-prod \
  --secrets "foundry-api-key=keyvaultref:https://kv-ic-test-ai-prod.vault.azure.net/secrets/AZURE-FOUNDRY-API-KEY,identityref:/subscriptions/.../userAssignedIdentities/..."
```

### 登録すべきシークレット一覧

| シークレット名 | 用途 | 設定元 |
|--------------|------|--------|
| `AZURE-FOUNDRY-API-KEY` | Azure AI Foundry APIキー | セクション6で取得 |
| `AZURE-FOUNDRY-ENDPOINT` | Azure AI Foundryエンドポイント | セクション6で取得 |
| `AZURE-DOCUMENT-INTELLIGENCE-KEY` | Document Intelligence APIキー | セクション7で取得 |
| `AZURE-DOCUMENT-INTELLIGENCE-ENDPOINT` | Document Intelligenceエンドポイント | セクション7で取得 |

✅ **確認ポイント**: `az keyvault secret list` で全シークレットが登録されていることを確認してください。

---

## 10. Application Insights

### 📖 Application Insightsとは

**Application Insights** は、アプリケーションの**パフォーマンス監視 (APM: Application Performance Monitoring)** サービスです。

主な機能:
- **リクエスト追跡**: 各API呼び出しの成功/失敗、レスポンスタイムを記録
- **例外監視**: アプリケーションで発生したエラーを自動記録
- **依存関係追跡**: 外部サービス（Azure AI Foundry、Document Intelligence等）への呼び出しを記録
- **カスタムメトリクス**: 評価件数、処理時間等のビジネスメトリクスを記録
- **分散トレーシング**: 相関IDを使ったリクエストの追跡
- **ログクエリ**: KQL（Kusto Query Language）でログを分析

本プロジェクトでは、VBAからの相関IDをAPIM → Container Apps → Application Insightsまで追跡できます。

### リソース作成（Log Analytics Workspace含む）

Application Insightsのバックエンドとして、Log Analytics Workspaceが必要です。

```powershell
# Log Analytics Workspace作成
az monitor log-analytics workspace create `
  --workspace-name log-ic-test-ai-prod `
  --resource-group rg-ic-test-ai-prod `
  --location japaneast `
  --retention-time 30
```

コマンドの意味:
- `--workspace-name`: ワークスペース名
- `--retention-time 30`: ログ保持期間（日数）。30日が無料枠

```powershell
# Application Insights作成
az monitor app-insights component create `
  --app appi-ic-test-ai-prod `
  --resource-group rg-ic-test-ai-prod `
  --location japaneast `
  --workspace log-ic-test-ai-prod `
  --kind web
```

コマンドの意味:
- `--app`: Application Insights名
- `--workspace`: 紐付けるLog Analytics Workspace
- `--kind web`: Web アプリケーション用の設定

### 接続文字列の取得

```powershell
az monitor app-insights component show `
  --app appi-ic-test-ai-prod `
  --resource-group rg-ic-test-ai-prod `
  --query "connectionString" `
  --output tsv
```

期待される出力:
```
InstrumentationKey=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx;IngestionEndpoint=https://japaneast-1.in.applicationinsights.azure.com/;LiveEndpoint=https://japaneast.livediagnostics.monitor.azure.com/;ApplicationId=yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy
```

💡 **ヒント**: 以前は `InstrumentationKey` のみで接続していましたが、現在は `ConnectionString` の使用が推奨されています。

### Container Apps統合設定

Container Appの環境変数に接続文字列を設定すると、Application Insightsへのテレメトリ送信が有効になります。

```powershell
az containerapp update `
  --name ca-ic-test-ai-prod `
  --resource-group rg-ic-test-ai-prod `
  --set-env-vars APPLICATIONINSIGHTS_CONNECTION_STRING="<接続文字列>"
```

💡 **ヒント**: Bicepテンプレートでは、この設定は `container-app.bicep` で自動的に行われます。

### 基本的なKustoクエリ（KQL）

Azure Portalの Application Insights → ログ で、以下のクエリを実行できます。

```kusto
// 過去24時間のリクエスト一覧
requests
| where timestamp > ago(24h)
| project timestamp, name, resultCode, duration, operation_Id
| order by timestamp desc
| take 50
```

```kusto
// 相関IDでリクエストを追跡
traces
| where customDimensions.correlation_id == "<X-Correlation-IDの値>"
| project timestamp, message, customDimensions, operation_Name
| order by timestamp asc
```

```kusto
// エラー一覧
exceptions
| where timestamp > ago(24h)
| project timestamp, type, outerMessage, details
| order by timestamp desc
```

```kusto
// 平均レスポンスタイム（エンドポイント別）
requests
| where timestamp > ago(7d)
| summarize avg(duration), count() by name
| order by avg_duration desc
```

📖 **学習ポイント**: KQL (Kusto Query Language) はSQLに似た構文のクエリ言語です。パイプ `|` でデータを変換していくのが特徴です。

### カスタムメトリクスの確認

本プロジェクトの `azure_monitor.py` では、以下のカスタムメトリクスを送信します。

| メトリクス名 | 説明 |
|-------------|------|
| `evaluation_duration` | 評価処理の所要時間 |
| `evaluation_count` | 評価件数 |
| `llm_token_usage` | LLMトークン使用量 |
| `error_count` | エラー発生数 |

### アラートルール（Bicep自動設定）

`app-insights.bicep` では以下の2つのアラートルールが自動作成されます。

| アラート名 | 条件 | 重要度 | 評価間隔 |
| --- | --- | --- | --- |
| エラー率アラート | 5分間に例外が10件超過 | Warning (2) | 5分毎 |
| レスポンスタイムアラート | 15分間の平均レスポンスタイムが3秒超過 | Informational (3) | 5分毎 |

### Key Vault診断ログ（Bicep自動設定）

`key-vault.bicep` では、Key VaultのすべてのログとメトリクスをLog Analytics Workspaceに送信する診断設定が自動作成されます。

- **送信先**: Log Analytics Workspace
- **ログカテゴリ**: allLogs（全カテゴリ）
- **メトリクス**: AllMetrics
- **保持期間**: 30日

```kusto
// Key Vaultのシークレットアクセスログ確認
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.KEYVAULT"
| where OperationName == "SecretGet"
| summarize Count = count() by Identity, OperationName
```

✅ **確認ポイント**: Azure Portal → Application Insights → ログ でクエリが実行でき、データが表示されれば成功です。

---

## 11. Storage Account

### 📖 Storage Accountとは

**Azure Storage Account** は、クラウド上にデータを保存するためのサービスです。4種類のストレージを提供します。

| 種類 | 用途 | 本プロジェクトでの使用 |
|------|------|---------------------|
| **Blob Storage** | ファイル保存（画像、PDF、ログ等） | 証跡ファイル保存、ジョブ結果保存 |
| **Queue Storage** | メッセージキュー | 非同期ジョブのキューイング |
| **Table Storage** | NoSQLテーブル | ジョブステータス管理 |
| **File Storage** | ファイル共有 | 本プロジェクトでは未使用 |

Azure Container Appsでは、証跡ファイルやジョブ結果の保存にStorage Accountを使用します。

### 作成手順

```powershell
az storage account create `
  --name stictestaiprod `
  --resource-group rg-ic-test-ai-prod `
  --location japaneast `
  --sku Standard_LRS `
  --kind StorageV2 `
  --min-tls-version TLS1_2 `
  --allow-blob-public-access false
```

各パラメータの意味:
- `--name`: ストレージアカウント名（**グローバルで一意**、3~24文字、**小文字英数字のみ**）
- `--sku Standard_LRS`: ローカル冗長ストレージ（同一データセンター内で3重複製）
- `--kind StorageV2`: 汎用v2（最新の推奨オプション）
- `--min-tls-version TLS1_2`: セキュリティ設定。TLS 1.2以上を強制
- `--allow-blob-public-access false`: パブリックアクセスを無効化

📖 **学習ポイント - 冗長性オプション**:

| SKU | 冗長性 | コスト | 適用場面 |
|-----|--------|--------|---------|
| Standard_LRS | ローカル冗長（3重複製） | 最安 | 開発・テスト |
| Standard_ZRS | ゾーン冗長（3ゾーン） | 中 | 本番（推奨） |
| Standard_GRS | 地理的冗長（2リージョン） | 高 | DR対応 |

### Blobコンテナ作成

```powershell
# 証跡ファイル保存用コンテナ
az storage container create `
  --name evidence-files `
  --account-name stictestaiprod `
  --auth-mode login

# ジョブ結果保存用コンテナ
az storage container create `
  --name job-results `
  --account-name stictestaiprod `
  --auth-mode login
```

コマンドの意味:
- `--name`: コンテナ名（小文字英数字とハイフンのみ）
- `--auth-mode login`: Azure CLIの認証情報を使用（アクセスキーの代わり）

### Python SDKでのアクセス

```python
# Storage Accountへのアクセス例
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
blob_service = BlobServiceClient(
    account_url="https://stictestaiprod.blob.core.windows.net",
    credential=credential
)

# ファイルのアップロード
container_client = blob_service.get_container_client("evidence-files")
with open("sample.pdf", "rb") as f:
    container_client.upload_blob(name="test/sample.pdf", data=f)
    print("アップロード完了")
```

✅ **確認ポイント**: コンテナが作成され、ファイルのアップロード/ダウンロードができれば成功です。

---

## 12. Bicepデプロイ（Infrastructure as Code）

### 📖 Infrastructure as Code (IaC) とは

**Infrastructure as Code (IaC)** は、インフラストラクチャの構築をコード（テンプレートファイル）で定義し、自動的にデプロイする手法です。

**IaCのメリット:**

| 観点 | 手動構築 | IaC (Bicep) |
|------|---------|-------------|
| 再現性 | 手順書を見て手動操作 | **コマンド1つで同一環境を再現** |
| バージョン管理 | 変更履歴が不明 | **Gitで全変更を追跡** |
| レビュー | 目視確認のみ | **Pull Requestでコードレビュー** |
| 一貫性 | 人的ミスが発生 | **毎回同じ結果** |
| スピード | 1時間以上 | **数分で完了** |

### 📖 BicepとARMテンプレートの違い

| 観点 | ARM テンプレート | Bicep |
|------|-----------------|-------|
| 形式 | JSON（冗長） | **独自DSL（簡潔）** |
| 可読性 | 低い（ネストが深い） | **高い** |
| モジュール | 制限あり | **ファイル分割が容易** |
| 型チェック | なし | **コンパイル時に検出** |
| 学習コスト | 高い | **比較的低い** |

💡 **ヒント**: BicepはAzure Resource Manager (ARM) テンプレートの上位互換です。Bicepコードは内部的にARMテンプレート（JSON）に変換されてデプロイされます。

### 本プロジェクトのBicepファイル構成

```
infrastructure/azure/bicep/
├── main.bicep           ← エントリーポイント（全モジュールを統合）
├── app-insights.bicep   ← Application Insights + Log Analytics
├── container-app.bicep  ← Azure Container Apps + Container App Environment + ACR
├── key-vault.bicep      ← Key Vault + アクセスポリシー + シークレット雛形
└── apim.bicep           ← API Management + API定義 + サブスクリプション
```

**デプロイ順序（依存関係）:**

```
1. app-insights.bicep     ← 最初にデプロイ（他から参照される）
      ↓
2. container-app.bicep    ← App Insights接続文字列を参照
      ↓
3. key-vault.bicep        ← Container AppのManaged Identity IDを参照
      ↓
4. apim.bicep             ← Container AppのURL、App Insights IDを参照
```

この依存関係は `main.bicep` で `dependsOn` を使って自動管理されます。

### パラメータファイルの作成

デプロイ時に渡すパラメータを定義します。

```powershell
# infrastructure/azure/bicep/ にパラメータファイルを作成
```

```json
{
  "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
  "contentVersion": "1.0.0.0",
  "parameters": {
    "projectName": {
      "value": "ic-test-ai"
    },
    "environment": {
      "value": "prod"
    },
    "apimPublisherEmail": {
      "value": "admin@example.com"
    },
    "apimPublisherName": {
      "value": "Internal Control Test AI Team"
    },
    "apimSkuName": {
      "value": "Consumption"
    },
    "apimSkuCapacity": {
      "value": 0
    },
    "containerAppSkuName": {
      "value": "Consumption"
    },
    "pythonVersion": {
      "value": "3.11"
    }
  }
}
```

各パラメータの説明:

| パラメータ | 説明 | 推奨値 |
|-----------|------|--------|
| `projectName` | プロジェクト名（リソース名のプレフィックス） | `ic-test-ai` |
| `environment` | 環境名 | `dev`, `stg`, `prod` |
| `apimPublisherEmail` | APIM発行者メール | 管理者のメールアドレス |
| `apimPublisherName` | APIM発行者名 | チーム名・組織名 |
| `apimSkuName` | APIM料金プラン | `Consumption`（開発時推奨） |
| `containerAppSkuName` | Container Apps料金プラン | `Consumption`（従量課金） |
| `pythonVersion` | Pythonバージョン | `3.11` |

### Bicepのバリデーション（デプロイ前の検証）

デプロイ前にテンプレートの構文エラーをチェックします。

```powershell
az deployment group validate `
  --resource-group rg-ic-test-ai-prod `
  --template-file infrastructure/azure/bicep/main.bicep `
  --parameters @infrastructure/azure/bicep/parameters.json
```

期待される出力（成功時）:
```json
{
  "id": "/subscriptions/.../providers/Microsoft.Resources/deployments/main",
  "properties": {
    "provisioningState": "Succeeded"
  }
}
```

### デプロイ実行

```powershell
az deployment group create `
  --resource-group rg-ic-test-ai-prod `
  --template-file infrastructure/azure/bicep/main.bicep `
  --parameters @infrastructure/azure/bicep/parameters.json `
  --name ic-test-ai-deployment `
  --verbose
```

各パラメータの意味:
- `az deployment group create`: リソースグループレベルのデプロイを実行
- `--template-file`: Bicepテンプレートファイルのパス
- `--parameters`: パラメータファイル（`@` プレフィックスでファイル参照）
- `--name`: デプロイメント名（履歴として残る）
- `--verbose`: 詳細ログを表示

⚠️ **注意**: デプロイには**10~45分**かかります（特にAPIMが時間を要します）。`--verbose` オプションで進行状況を確認できます。

期待される出力（最終部分）:
```json
{
  "properties": {
    "provisioningState": "Succeeded",
    "outputs": {
      "resourceGroupName": { "value": "rg-ic-test-ai-prod" },
      "containerAppName": { "value": "ca-ic-test-ai-prod-xxxxxx" },
      "containerAppUrl": { "value": "https://ca-ic-test-ai-prod-xxxxxx.japaneast.azurecontainerapps.io" },
      "keyVaultName": { "value": "kv-ic-test-ai-xxxxxxxx" },
      "keyVaultUri": { "value": "https://kv-ic-test-ai-xxxxxxxx.vault.azure.net/" },
      "apimName": { "value": "apim-ic-test-ai-prod-xxxxxx" },
      "apimGatewayUrl": { "value": "https://apim-ic-test-ai-prod-xxxxxx.azure-api.net" },
      "apiEndpoint": { "value": "https://apim-ic-test-ai-prod-xxxxxx.azure-api.net/api/evaluate" }
    }
  }
}
```

### デプロイ結果の確認

```powershell
# デプロイ結果（出力値）を取得
az deployment group show `
  --resource-group rg-ic-test-ai-prod `
  --name ic-test-ai-deployment `
  --query "properties.outputs" `
  --output json
```

```powershell
# リソースグループ内の全リソースを確認
az resource list `
  --resource-group rg-ic-test-ai-prod `
  --output table
```

期待される出力:
```
Name                              ResourceGroup        Location    Type
--------------------------------  -------------------  ----------  ------------------------------------------
log-ic-test-ai-prod-xxxxxx       rg-ic-test-ai-prod   japaneast   Microsoft.OperationalInsights/workspaces
appi-ic-test-ai-prod-xxxxxx      rg-ic-test-ai-prod   japaneast   Microsoft.Insights/components
stictestaiprodxxxxxx              rg-ic-test-ai-prod   japaneast   Microsoft.Storage/storageAccounts
cae-ic-test-ai-prod-xxxxxx      rg-ic-test-ai-prod   japaneast   Microsoft.App/managedEnvironments
ca-ic-test-ai-prod-xxxxxx       rg-ic-test-ai-prod   japaneast   Microsoft.App/containerApps
kv-ic-test-ai-xxxxxxxx           rg-ic-test-ai-prod   japaneast   Microsoft.KeyVault/vaults
apim-ic-test-ai-prod-xxxxxx      rg-ic-test-ai-prod   japaneast   Microsoft.ApiManagement/service
```

✅ **確認ポイント**: 上記7種類のリソースが全てデプロイされていれば成功です。

### デプロイ後の必須手順

Bicepデプロイ後、以下の手順を実施してください:

```powershell
# 1. Key Vaultに実際のシークレット値を設定
$KV_NAME = az deployment group show `
  --resource-group rg-ic-test-ai-prod `
  --name ic-test-ai-deployment `
  --query "properties.outputs.keyVaultName.value" `
  --output tsv

az keyvault secret set --vault-name $KV_NAME --name "AZURE-FOUNDRY-API-KEY" --value "<実際のAPIキー>"
az keyvault secret set --vault-name $KV_NAME --name "AZURE-FOUNDRY-ENDPOINT" --value "<実際のエンドポイント>"
az keyvault secret set --vault-name $KV_NAME --name "AZURE-DOCUMENT-INTELLIGENCE-KEY" --value "<実際のAPIキー>"
az keyvault secret set --vault-name $KV_NAME --name "AZURE-DOCUMENT-INTELLIGENCE-ENDPOINT" --value "<実際のエンドポイント>"
```

```powershell
# 2. Container Appにコンテナイメージをデプロイ
$CA_NAME = az deployment group show `
  --resource-group rg-ic-test-ai-prod `
  --name ic-test-ai-deployment `
  --query "properties.outputs.containerAppName.value" `
  --output tsv

# Dockerイメージをビルド＆ACRにプッシュ（セクション5参照）
docker build -t ic-test-ai-agent .
docker tag ic-test-ai-agent crictestaiprod.azurecr.io/ic-test-ai-agent:latest
az acr login --name crictestaiprod
docker push crictestaiprod.azurecr.io/ic-test-ai-agent:latest

# Container Appを更新
az containerapp update `
  --name $CA_NAME `
  --resource-group rg-ic-test-ai-prod `
  --image crictestaiprod.azurecr.io/ic-test-ai-agent:latest
```

---

## 13. 統合テスト

### ヘルスチェック確認

すべてのリソースがデプロイされたら、エンドツーエンドの動作確認を行います。

```powershell
# デプロイ出力からAPIM URLを取得
$APIM_URL = az deployment group show `
  --resource-group rg-ic-test-ai-prod `
  --name ic-test-ai-deployment `
  --query "properties.outputs.apimGatewayUrl.value" `
  --output tsv

# Subscription Keyを取得
$APIM_NAME = az deployment group show `
  --resource-group rg-ic-test-ai-prod `
  --name ic-test-ai-deployment `
  --query "properties.outputs.apimName.value" `
  --output tsv

$SUB_KEY = az apim subscription show `
  --resource-group rg-ic-test-ai-prod `
  --service-name $APIM_NAME `
  --subscription-id ic-test-ai-subscription `
  --query "primaryKey" `
  --output tsv

# 1. ヘルスチェック
curl -H "Ocp-Apim-Subscription-Key: $SUB_KEY" "$APIM_URL/api/health"
```

期待される出力:
```json
{
  "status": "healthy",
  "version": "2.4.0-multiplatform",
  "llm": {
    "provider": "AZURE",
    "configured": true,
    "model": "gpt-5-nano"
  },
  "ocr": {
    "provider": "AZURE",
    "configured": true
  },
  "platform": "Azure Container Apps"
}
```

### /evaluate エンドポイントテスト

```powershell
# 2. 評価エンドポイントテスト
curl -X POST `
  -H "Content-Type: application/json" `
  -H "Ocp-Apim-Subscription-Key: $SUB_KEY" `
  -H "X-Correlation-ID: TEST-20260211-001" `
  -d '[{"ID":"TEST-001","controlObjective":"売上計上の正確性","testProcedure":"売上伝票と出荷記録を照合する","acceptanceCriteria":"日付と金額が一致すること"}]' `
  "$APIM_URL/api/evaluate"
```

期待される出力:
```json
[
  {
    "ID": "TEST-001",
    "evaluationResult": true,
    "judgmentBasis": "売上伝票と出荷記録の照合により...",
    "documentReference": "...",
    "fileName": ""
  }
]
```

### 相関ID伝播確認

テストで送信した相関ID `TEST-20260211-001` がApplication Insightsまで伝播しているか確認します。

Azure Portal → Application Insights → ログ で以下のクエリを実行:

```kusto
traces
| where customDimensions.correlation_id == "TEST-20260211-001"
| project timestamp, message, customDimensions, operation_Name
| order by timestamp asc
```

期待される結果:
```
timestamp            | message                        | operation_Name
2026-02-11 10:00:01  | リクエスト受信: 1件             | evaluate
2026-02-11 10:00:02  | LLMインスタンスの取得を開始     | evaluate
2026-02-11 10:00:03  | [TEST-001] 評価を開始           | evaluate
2026-02-11 10:00:15  | [TEST-001] 評価完了: 有効        | evaluate
```

### 設定状態確認

```powershell
# 3. 設定状態確認
curl -H "Ocp-Apim-Subscription-Key: $SUB_KEY" "$APIM_URL/api/config"
```

期待される出力:
```json
{
  "llm": {
    "status": {
      "provider": "AZURE",
      "configured": true,
      "model": "gpt-5-nano"
    }
  },
  "ocr": {
    "status": {
      "provider": "AZURE",
      "configured": true
    }
  },
  "orchestrator": {
    "type": "GraphAuditOrchestrator",
    "self_reflection_enabled": true,
    "max_concurrent_evaluations": 10,
    "default_timeout_seconds": 300
  }
}
```

✅ **確認ポイント**: 以下のすべてが成功していれば、統合テストは完了です。
- [ ] `/health` が `"status": "healthy"` を返す
- [ ] `/evaluate` が評価結果を返す
- [ ] `/config` でLLM/OCRが `"configured": true` を返す
- [ ] Application Insightsで相関IDが追跡できる

---

## 14. コスト管理

### 無料枠の範囲

Azureの無料枠と、本プロジェクトの各サービスのコストを把握しておきましょう。

| サービス | 無料枠 | 超過時の料金（概算） |
|---------|--------|---------------------|
| Azure Container Apps | **月180,000 vCPU秒 + 360,000 GiB秒** | $0.000024/vCPU秒 |
| API Management (Consumption) | **月100万回** | $3.50/100万回 |
| Application Insights | **月5GBまで** | $2.30/GB |
| Storage Account | **5GB (LRS)** | $0.018/GB/月 |
| Key Vault | **月1万トランザクション** | $0.03/1万トランザクション |
| Azure AI Foundry (GPT-5 Nano) | なし | 入力$0.10/出力$0.40 per 100万トークン |
| Document Intelligence | **月500ページ (F0)** | $1.50/1000ページ (S0) |

### コスト見積もり（月間）

開発・テスト環境での想定月間コスト:

| サービス | 想定利用量 | 月額コスト（概算） |
|---------|-----------|------------------|
| Azure Container Apps | 少量利用/月 | **無料** |
| APIM (Consumption) | 1万回/月 | **無料** |
| Application Insights | 1GB/月 | **無料** |
| Storage Account | 1GB | **$0.02** |
| Key Vault | 1000回/月 | **無料** |
| GPT-5 Nano | 50万トークン | **約$0.25** |
| Document Intelligence | 100ページ | **無料 (F0)** |
| **合計** | | **約$4~5/月（約600~750円）** |

⚠️ **注意**: 本番運用では利用量に応じてコストが増加します。Azure Cost Managementで予算アラートを設定することを推奨します。

### コスト削減のヒント

1. **Consumptionプランを使う**: Container Apps、APIMともに従量課金で無駄がない
2. **Application Insightsのサンプリング**: 本番環境ではサンプリング率を10~20%に設定
3. **Log Analytics保持期間**: 30日（無料枠）を超えないよう設定
4. **GPT-5 Nanoの活用**: 単純な評価にはGPT-5 Nano（高速・低コスト）を使用
5. **リソースの停止/削除**: テスト後は不要なリソースを削除

### 予算アラートの設定

```powershell
# 月額$10の予算アラートを設定
az consumption budget create `
  --budget-name ic-test-ai-budget `
  --amount 10 `
  --time-grain Monthly `
  --start-date 2026-02-01 `
  --end-date 2027-02-01 `
  --resource-group rg-ic-test-ai-prod `
  --category Cost
```

### 不要リソースの一括削除

⚠️ **注意**: 以下のコマンドは**リソースグループ内のすべてのリソースを完全に削除**します。実行前に必ず確認してください。

```powershell
# リソースグループごと削除（全リソースが削除される）
az group delete --name rg-ic-test-ai-prod --yes --no-wait
```

コマンドの意味:
- `az group delete`: リソースグループとその中の全リソースを削除
- `--yes`: 確認プロンプトをスキップ
- `--no-wait`: 削除完了を待たずにコマンドを終了

💡 **ヒント**: リソースグループ単位で管理している最大の利点がここにあります。テスト後のクリーンアップが1コマンドで完了します。

---

## 15. まとめ・次のステップ

### このガイドで学んだこと

おめでとうございます！このガイドを通じて、以下のスキルを習得しました。

| # | 学んだスキル | 関連セクション |
|---|------------|--------------|
| 1 | Azure CLIによるクラウドリソース管理 | セクション3 |
| 2 | リソースグループによるリソースの論理的管理 | セクション4 |
| 3 | コンテナアーキテクチャ（Azure Container Apps） | セクション5 |
| 4 | AIサービスの設定と利用（GPT-5 Nano） | セクション6 |
| 5 | 文書OCR処理（Document Intelligence） | セクション7 |
| 6 | API Gatewayの構築と認証（APIM） | セクション8 |
| 7 | シークレット管理のベストプラクティス（Key Vault） | セクション9 |
| 8 | アプリケーション監視とログ分析（Application Insights） | セクション10 |
| 9 | クラウドストレージの利用（Storage Account） | セクション11 |
| 10 | Infrastructure as Code（Bicep） | セクション12 |
| 11 | エンドツーエンドの統合テスト | セクション13 |
| 12 | クラウドコスト管理 | セクション14 |

### アーキテクチャの全体像（復習）

```
┌─────────────────────────────────────────────────────────────────┐
│                    Azure リソースグループ                        │
│                   rg-ic-test-ai-prod                            │
│                                                                 │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────────┐     │
│  │  APIM    │───→│ Azure        │───→│ Azure AI Foundry  │     │
│  │ (Gateway)│    │ Container   │    │ (GPT-5 Nano)      │     │
│  └──────────┘    │ Apps (Docker)│    └───────────────────┘     │
│       ↑          └──────┬───────┘    ┌───────────────────┐     │
│       │                 │       └───→│ Document          │     │
│  Subscription     ┌─────┴─────┐      │ Intelligence      │     │
│  Key認証         │           │      └───────────────────┘     │
│                   ↓           ↓                                 │
│            ┌──────────┐ ┌──────────┐  ┌──────────────────┐     │
│            │ Key Vault│ │ Storage  │  │ Application      │     │
│            │ (秘密管理)│ │ Account  │  │ Insights (監視)  │     │
│            └──────────┘ └──────────┘  └──────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

### 次に読むべきドキュメント

1. **運用ガイド**: `docs/operations/DEPLOYMENT_GUIDE.md` - CI/CDパイプラインの構築
2. **API Gateway設計**: `docs/architecture/API_GATEWAY_DESIGN.md` - APIM/API Gateway/Apigee設計
3. **監視ダッシュボード**: Application Insightsでのダッシュボード作成方法

### 参考リンク（公式ドキュメント）

| リソース | URL |
|---------|-----|
| Azure CLI リファレンス | https://learn.microsoft.com/ja-jp/cli/azure/ |
| Azure Container Apps ドキュメント | https://learn.microsoft.com/ja-jp/azure/container-apps/ |
| Azure AI Foundry ドキュメント | https://learn.microsoft.com/ja-jp/azure/ai-services/openai/ |
| Document Intelligence ドキュメント | https://learn.microsoft.com/ja-jp/azure/ai-services/document-intelligence/ |
| API Management ドキュメント | https://learn.microsoft.com/ja-jp/azure/api-management/ |
| Key Vault ドキュメント | https://learn.microsoft.com/ja-jp/azure/key-vault/ |
| Application Insights ドキュメント | https://learn.microsoft.com/ja-jp/azure/azure-monitor/app/app-insights-overview |
| Bicep ドキュメント | https://learn.microsoft.com/ja-jp/azure/azure-resource-manager/bicep/ |
| Azure 料金計算ツール | https://azure.microsoft.com/ja-jp/pricing/calculator/ |

---

*このガイドは内部統制テスト評価AIシステム (ic-test-ai-agent) プロジェクトの一部です。*
*最終更新: 2026-02-11*
