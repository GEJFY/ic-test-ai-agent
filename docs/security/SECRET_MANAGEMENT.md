# シークレット管理ガイド

> 内部統制テストAIシステム -- シークレット管理アーキテクチャと運用手順

**最終更新日**: 2026-02-11
**対象バージョン**: ic-test-ai-agent v3.x
**ステータス**: 本番運用ドキュメント

---

## 目次

1. [シークレット管理概要](#1-シークレット管理概要)
2. [アーキテクチャ](#2-アーキテクチャ)
3. [SecretProvider インターフェース](#3-secretprovider-インターフェース)
4. [プラットフォーム別実装](#4-プラットフォーム別実装)
   - [Azure Key Vault](#41-azure-key-vault)
   - [AWS Secrets Manager](#42-aws-secrets-manager)
   - [GCP Secret Manager](#43-gcp-secret-manager)
5. [EnvironmentSecretProvider](#5-environmentsecretprovider)
6. [ファクトリーパターン](#6-ファクトリーパターン)
7. [シングルトンパターン](#7-シングルトンパターン)
8. [シークレット一覧](#8-シークレット一覧)
9. [セキュリティベストプラクティス](#9-セキュリティベストプラクティス)
10. [トラブルシューティング](#10-トラブルシューティング)

---

## 1. シークレット管理概要

### なぜ一元的なシークレット管理が必要か

内部統制テストAIシステムは、複数のLLM API（Azure AI Foundry、Amazon Bedrock、Google Vertex AI）やOCRサービスとの連携を必要とします。これらのサービスに接続するためのAPIキー、接続文字列、認証トークンは機密情報であり、適切に管理しなければなりません。

従来のシークレット管理における典型的な問題点は以下の通りです。

- **ソースコードへの直接埋め込み**: GitHubへの漏洩リスク
- **環境変数への直接設定**: サーバー間での管理が煩雑、ローテーション困難
- **設定ファイルでの管理**: アクセス制御不足、暗号化されない状態での保存
- **チーム間のシークレット共有**: メールやチャットでの非安全な共有

### クラウドネイティブなアプローチ

本システムでは、各クラウドプラットフォームが提供するマネージドシークレット管理サービスを活用します。

| 特徴 | 説明 |
|------|------|
| **暗号化** | 保存時・転送時ともにAES-256で暗号化 |
| **アクセス制御** | IAM/RBAC による細粒度のアクセス管理 |
| **監査ログ** | 全アクセスの記録・追跡 |
| **自動ローテーション** | 定期的なシークレット更新の自動化 |
| **高可用性** | クラウドプロバイダーのSLAに準拠した可用性保証 |

本システムは **抽象インターフェースによるプロバイダーパターン** を採用しており、アプリケーションコードを変更することなくクラウドプラットフォームを切り替えることが可能です。

---

## 2. アーキテクチャ

### 全体構成図

```mermaid
graph TB
    subgraph Application["アプリケーション層"]
        App["内部統制テストAIエンジン"]
        Factory["get_secret_provider()"]
        Singleton["get_default_provider()"]
    end

    subgraph Interface["抽象インターフェース層"]
        SP["SecretProvider (ABC)"]
    end

    subgraph Providers["プロバイダー実装層"]
        AKV["AzureKeyVaultProvider"]
        ASM["AWSSecretsManagerProvider"]
        GSM["GCPSecretManagerProvider"]
        ENV["EnvironmentSecretProvider"]
    end

    subgraph CloudServices["クラウドシークレット管理サービス"]
        Azure["Azure Key Vault"]
        AWS["AWS Secrets Manager"]
        GCP["GCP Secret Manager"]
    end

    subgraph Local["ローカル環境"]
        EnvVars["OS 環境変数"]
    end

    App --> Singleton
    Singleton --> Factory
    Factory --> SP

    SP --> AKV
    SP --> ASM
    SP --> GSM
    SP --> ENV

    AKV -->|"azure-keyvault-secrets SDK"| Azure
    ASM -->|"boto3 SDK"| AWS
    GSM -->|"google-cloud-secret-manager SDK"| GCP
    ENV -->|"os.environ"| EnvVars

    Factory -.->|"フォールバック"| ENV

    style SP fill:#f9f,stroke:#333,stroke-width:2px
    style ENV fill:#ff9,stroke:#333,stroke-width:1px
    style Factory fill:#9cf,stroke:#333,stroke-width:1px
```

### ファイル構成

```
src/infrastructure/secrets/
    __init__.py                  # モジュール公開インターフェース
    secrets_provider.py          # 抽象基底クラス + ファクトリー + シングルトン
    azure_keyvault.py            # Azure Key Vault 実装
    aws_secrets.py               # AWS Secrets Manager 実装
    gcp_secrets.py               # GCP Secret Manager 実装
```

### プロバイダー選択フロー

```mermaid
flowchart TD
    A["get_secret_provider() 呼び出し"] --> B{provider_type が指定されているか?}
    B -->|Yes| C{Platform enum か?}
    B -->|No| D["環境変数から判定"]
    C -->|Yes| E["enum.value で文字列に変換"]
    C -->|No| F["そのまま文字列として使用"]
    E --> F
    D --> G{"SECRET_PROVIDER 環境変数"}
    G -->|設定あり| F
    G -->|未設定| H{"CLOUD_PLATFORM 環境変数"}
    H -->|設定あり| F
    H -->|未設定| I["'env' をデフォルト値として使用"]
    I --> F
    F --> J{provider_type の値}
    J -->|"azure"| K["AzureKeyVaultProvider を生成"]
    J -->|"aws"| L["AWSSecretsManagerProvider を生成"]
    J -->|"gcp"| M["GCPSecretManagerProvider を生成"]
    J -->|"env"| N["EnvironmentSecretProvider を生成"]
    J -->|その他| O["ValueError 発生"]
    K --> P{初期化成功?}
    L --> P
    M --> P
    P -->|Yes| Q["プロバイダーを返却"]
    P -->|No| R{fallback_to_env = True?}
    R -->|Yes| N
    R -->|No| S["例外を再送出"]
    N --> Q
```

---

## 3. SecretProvider インターフェース

`SecretProvider` は全プロバイダー実装が継承する抽象基底クラスです。

**ソースファイル**: `src/infrastructure/secrets/secrets_provider.py`

### クラス定義

```python
from abc import ABC, abstractmethod
from typing import Optional

class SecretProvider(ABC):
    """
    シークレット管理プロバイダーの抽象基底クラス

    各クラウドプロバイダーのシークレット管理サービスの統一インターフェースです。
    """
```

### 抽象メソッド一覧

#### `get_secret(secret_name: str) -> Optional[str]`

シークレット値を取得します。

| 項目 | 内容 |
|------|------|
| **引数** | `secret_name` -- シークレットの識別名 |
| **戻り値** | シークレット値の文字列。取得できない場合は `None` |
| **例外** | `Exception` -- シークレット取得に失敗した場合 |

#### `set_secret(secret_name: str, secret_value: str) -> bool`

シークレットを作成または更新します。

| 項目 | 内容 |
|------|------|
| **引数** | `secret_name` -- シークレットの識別名, `secret_value` -- 設定する値 |
| **戻り値** | 成功時 `True`、失敗時 `False` |
| **例外** | `Exception` -- シークレット設定に失敗した場合 |

#### `delete_secret(secret_name: str) -> bool`

シークレットを削除します。

| 項目 | 内容 |
|------|------|
| **引数** | `secret_name` -- シークレットの識別名 |
| **戻り値** | 成功時 `True`、失敗時 `False` |
| **例外** | `Exception` -- シークレット削除に失敗した場合 |
| **注意** | Azure/AWSではソフトデリートにより一定期間保持されます |

#### `list_secrets() -> list[str]`

登録されている全シークレットの名前リストを取得します。

| 項目 | 内容 |
|------|------|
| **引数** | なし |
| **戻り値** | シークレット名の文字列リスト |
| **例外** | `Exception` -- リスト取得に失敗した場合 |

### Platform 列挙型

プロバイダータイプの指定に使用する列挙型です。

```python
from enum import Enum

class Platform(Enum):
    AZURE = "azure"
    AWS = "aws"
    GCP = "gcp"
```

---

## 4. プラットフォーム別実装

### 4.1 Azure Key Vault

**ソースファイル**: `src/infrastructure/secrets/azure_keyvault.py`
**クラス名**: `AzureKeyVaultProvider`

#### 前提条件

以下のPythonパッケージが必要です。

```bash
pip install azure-keyvault-secrets azure-identity
```

パッケージが未インストールの場合、`ImportError` が発生します。`fallback_to_env=True`（デフォルト）の場合は `EnvironmentSecretProvider` に自動フォールバックします。

#### 環境変数

| 環境変数名 | 必須 | 説明 | 例 |
|-----------|------|------|-----|
| `AZURE_KEY_VAULT_URL` | Yes | Key VaultのURL | `https://my-vault.vault.azure.net/` |
| `AZURE_TENANT_ID` | No* | Azure ADテナントID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `AZURE_CLIENT_ID` | No* | サービスプリンシパルのクライアントID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `AZURE_CLIENT_SECRET` | No* | サービスプリンシパルのクライアントシークレット | `xxxxxxxxxxxxxxxxxxxxxxxxx` |

> *No*: Managed IdentityやAzure CLI認証を使用する場合は不要です。サービスプリンシパル認証時のみ必要です。

#### 認証方式

`AzureKeyVaultProvider` は Azure SDK の `DefaultAzureCredential` を使用します。以下の順序で認証を試行します。

1. **環境変数**: `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`
2. **Managed Identity**: Azure VM、App Service、Container Apps で自動検出
3. **Azure CLI**: `az login` でログイン済みの場合
4. **Visual Studio Code**: Azure拡張機能でログイン済みの場合
5. **Azure PowerShell**: `Connect-AzAccount` でログイン済みの場合

```python
# 認証の優先順位を理解したうえで、コンストラクタに credential を渡すことも可能
from azure.identity import ManagedIdentityCredential

provider = AzureKeyVaultProvider(
    vault_url="https://my-vault.vault.azure.net/",
    credential=ManagedIdentityCredential()
)
```

#### 使用例

```python
from src.infrastructure.secrets.azure_keyvault import AzureKeyVaultProvider

# 基本的な使用方法（環境変数 AZURE_KEY_VAULT_URL を参照）
provider = AzureKeyVaultProvider()

# シークレットの取得
api_key = provider.get_secret("AZURE-FOUNDRY-API-KEY")

# シークレットの設定
provider.set_secret("MY-NEW-SECRET", "secret-value-here")

# シークレットの一覧取得
all_secrets = provider.list_secrets()
# ['AZURE-FOUNDRY-API-KEY', 'AZURE-DI-KEY', ...]

# シークレットの削除（ソフトデリート: 一定期間保持）
provider.delete_secret("OLD-SECRET")

# リトライ機能付き取得（指数バックオフ + 環境変数フォールバック）
api_key = provider.get_secret_with_retry(
    "AZURE-FOUNDRY-API-KEY",
    max_retries=3,
    fallback_env=True
)
```

#### Key Vault アクセスポリシー設定

Azure CLI を使用して Key Vault のアクセスポリシーを設定します。

```bash
# Key Vault の作成
az keyvault create \
  --name ic-test-ai-vault \
  --resource-group ic-test-ai-rg \
  --location japaneast \
  --sku standard

# アプリケーション（サービスプリンシパル）にアクセス権を付与
az keyvault set-policy \
  --name ic-test-ai-vault \
  --spn <サービスプリンシパルのクライアントID> \
  --secret-permissions get list set delete

# Managed Identity にアクセス権を付与（App Service 等）
az keyvault set-policy \
  --name ic-test-ai-vault \
  --object-id <Managed Identity のオブジェクトID> \
  --secret-permissions get list

# RBAC ベースのアクセス制御を有効にする場合
az keyvault update \
  --name ic-test-ai-vault \
  --enable-rbac-authorization true

# Key Vault Secrets User ロールの付与
az role assignment create \
  --role "Key Vault Secrets User" \
  --assignee <サービスプリンシパルのクライアントID> \
  --scope /subscriptions/<subscription-id>/resourceGroups/ic-test-ai-rg/providers/Microsoft.KeyVault/vaults/ic-test-ai-vault
```

#### 削除時の注意事項

Azure Key Vault ではソフトデリートが有効になっており、削除されたシークレットは既定で90日間保持されます。`begin_delete_secret()` による削除操作は非同期で、`poller.wait()` で完了を待機します。

---

### 4.2 AWS Secrets Manager

**ソースファイル**: `src/infrastructure/secrets/aws_secrets.py`
**クラス名**: `AWSSecretsManagerProvider`

#### 前提条件

以下のPythonパッケージが必要です。

```bash
pip install boto3
```

#### 環境変数

| 環境変数名 | 必須 | 説明 | デフォルト値 |
|-----------|------|------|-------------|
| `AWS_REGION` | No | AWSリージョン | `us-east-1` |
| `AWS_DEFAULT_REGION` | No | AWSリージョン（代替） | - |
| `AWS_ACCESS_KEY_ID` | No* | アクセスキーID | - |
| `AWS_SECRET_ACCESS_KEY` | No* | シークレットアクセスキー | - |

> *No*: IAMロールを使用する場合（EC2、ECS、App Runner等）は不要です。

#### 認証方式

boto3 は以下の順序で認証情報を検索します。

1. **コンストラクタ引数**: `aws_access_key_id`, `aws_secret_access_key` の直接指定
2. **環境変数**: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
3. **共有認証情報ファイル**: `~/.aws/credentials`
4. **AWS設定ファイル**: `~/.aws/config`
5. **IAMロール**: EC2インスタンスプロファイル、ECSタスクロール、App Runner Instance Role
6. **コンテナ認証情報**: ECSタスクの認証情報プロバイダー

```python
# IAMロール認証（EC2/ECS/App Runner環境で推奨）
provider = AWSSecretsManagerProvider(region_name="ap-northeast-1")

# 明示的な認証情報指定（開発用途のみ）
provider = AWSSecretsManagerProvider(
    region_name="ap-northeast-1",
    aws_access_key_id="AKIAIOSFODNN7EXAMPLE",  # pragma: allowlist secret
    aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"  # pragma: allowlist secret
)
```

#### 使用例

```python
from src.infrastructure.secrets.aws_secrets import AWSSecretsManagerProvider

# 基本的な使用方法
provider = AWSSecretsManagerProvider(region_name="ap-northeast-1")

# シークレットの取得
api_key = provider.get_secret("bedrock-api-key")

# JSON形式のシークレット取得
# AWS Secrets Manager に {"api_key": "sk-..."} として保存されている場合、  # pragma: allowlist secret
# 辞書の最初の値 "sk-..." が返されます
api_key = provider.get_secret("bedrock-config")

# シークレットの設定（存在する場合は更新、存在しない場合は新規作成）
provider.set_secret("my-api-key", "sk-new-value")

# シークレットの一覧取得（ページネーション自動処理）
all_secrets = provider.list_secrets()
# ['bedrock-api-key', 'textract-config', ...]

# シークレットの削除（30日間の猶予期間付き）
provider.delete_secret("old-secret")

# 即座に完全削除
provider.delete_secret("old-secret", force_delete=True)

# リトライ機能付き取得
api_key = provider.get_secret_with_retry(
    "bedrock-api-key",
    max_retries=3,
    fallback_env=True
)
```

#### IAM ポリシー設定

アプリケーションに必要な最小権限のIAMポリシーを設定します。

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "ICTestAISecretsReadOnly",
            "Effect": "Allow",
            "Action": [
                "secretsmanager:GetSecretValue",
                "secretsmanager:DescribeSecret",
                "secretsmanager:ListSecrets"
            ],
            "Resource": "arn:aws:secretsmanager:ap-northeast-1:123456789012:secret:ic-test-ai-*"
        }
    ]
}
```

書き込み権限も必要な場合（管理用途）:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "ICTestAISecretsFullAccess",
            "Effect": "Allow",
            "Action": [
                "secretsmanager:GetSecretValue",
                "secretsmanager:DescribeSecret",
                "secretsmanager:ListSecrets",
                "secretsmanager:CreateSecret",
                "secretsmanager:PutSecretValue",
                "secretsmanager:DeleteSecret"
            ],
            "Resource": "arn:aws:secretsmanager:ap-northeast-1:123456789012:secret:ic-test-ai-*"
        }
    ]
}
```

```bash
# IAMポリシーの作成
aws iam create-policy \
  --policy-name ICTestAISecretsReadOnly \
  --policy-document file://secrets-read-policy.json

# IAMロールにポリシーをアタッチ
aws iam attach-role-policy \
  --role-name ic-test-ai-role \
  --policy-arn arn:aws:iam::123456789012:policy/ICTestAISecretsReadOnly
```

#### 削除時の注意事項

AWS Secrets Manager ではデフォルトで30日間の猶予期間が設けられています。`force_delete=True` を指定すると `ForceDeleteWithoutRecovery` フラグにより即座に完全削除されます。復元不可能なため、本番環境での使用には十分注意してください。

---

### 4.3 GCP Secret Manager

**ソースファイル**: `src/infrastructure/secrets/gcp_secrets.py`
**クラス名**: `GCPSecretManagerProvider`

#### 前提条件

以下のPythonパッケージが必要です。

```bash
pip install google-cloud-secret-manager
```

#### 環境変数

| 環境変数名 | 必須 | 説明 | 例 |
|-----------|------|------|-----|
| `GCP_PROJECT_ID` | Yes* | GCPプロジェクトID | `my-project-123456` |
| `GOOGLE_CLOUD_PROJECT` | Yes* | GCPプロジェクトID（代替） | `my-project-123456` |
| `GOOGLE_APPLICATION_CREDENTIALS` | No** | サービスアカウントキーのJSONファイルパス | `/path/to/sa-key.json` |

> *Yes*: `GCP_PROJECT_ID` または `GOOGLE_CLOUD_PROJECT` のいずれかが必要です。コンストラクタ引数 `project_id` で直接指定することもできます。
> **No**: Application Default Credentials（ADC）を使用する場合は不要です。

#### 認証方式

GCP Secret Manager は以下の認証方式をサポートします。

1. **サービスアカウントキー**: `credentials_path` 引数またはで `GOOGLE_APPLICATION_CREDENTIALS` 環境変数で指定
2. **Application Default Credentials (ADC)**: `gcloud auth application-default login` で設定
3. **Compute Engine / Cloud Run**: メタデータサーバー経由の自動認証
4. **GKE Workload Identity**: Kubernetes サービスアカウントとの連携

```python
# ADC認証（推奨）
provider = GCPSecretManagerProvider(project_id="my-project-123456")

# サービスアカウントキー指定
provider = GCPSecretManagerProvider(
    project_id="my-project-123456",
    credentials_path="/path/to/service-account-key.json"
)
```

#### 使用例

```python
from src.infrastructure.secrets.gcp_secrets import GCPSecretManagerProvider

# 基本的な使用方法
provider = GCPSecretManagerProvider(project_id="my-project")

# シークレットの取得（最新バージョン）
api_key = provider.get_secret("gemini-api-key")

# 特定バージョンの取得
api_key_v2 = provider.get_secret("gemini-api-key", version="2")

# シークレットの設定（存在する場合は新バージョン追加、存在しない場合は新規作成）
provider.set_secret("my-api-key", "sk-new-value")

# シークレットの一覧取得
all_secrets = provider.list_secrets()
# ['gemini-api-key', 'document-ai-config', ...]

# バージョンリストの取得
versions = provider.list_secret_versions("gemini-api-key")
# ['1', '2', '3']

# シークレットの削除（全バージョン完全削除）
provider.delete_secret("old-secret")

# リトライ機能付き取得
api_key = provider.get_secret_with_retry(
    "gemini-api-key",
    max_retries=3,
    fallback_env=True
)
```

#### IAM 権限設定

GCP Secret Manager に必要な IAM ロールを設定します。

```bash
# 読み取り専用アクセス（推奨: アプリケーション用）
gcloud projects add-iam-policy-binding my-project \
  --member="serviceAccount:ic-test-ai@my-project.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# シークレットのメタデータ閲覧（list_secrets に必要）
gcloud projects add-iam-policy-binding my-project \
  --member="serviceAccount:ic-test-ai@my-project.iam.gserviceaccount.com" \
  --role="roles/secretmanager.viewer"

# 書き込み権限（管理用途）
gcloud projects add-iam-policy-binding my-project \
  --member="serviceAccount:ic-test-ai@my-project.iam.gserviceaccount.com" \
  --role="roles/secretmanager.admin"
```

特定のシークレットに限定したアクセス制御:

```bash
# 特定のシークレットへの読み取り権限のみ付与
gcloud secrets add-iam-policy-binding gemini-api-key \
  --project=my-project \
  --member="serviceAccount:ic-test-ai@my-project.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

#### GCP 固有の特徴: バージョン管理

GCP Secret Manager はシークレットのバージョン管理をネイティブにサポートします。`set_secret()` で値を更新すると、既存のシークレットに新しいバージョンが追加されます。`get_secret()` はデフォルトで最新バージョン (`latest`) を取得しますが、`version` 引数で特定バージョンを指定できます。

シークレットのリソースパス形式:

```
projects/{project_id}/secrets/{secret_name}/versions/{version}
```

#### 削除時の注意事項

GCP Secret Manager では `delete_secret()` の呼び出しにより、シークレットと全バージョンが即座に完全削除されます。Azure や AWS とは異なりソフトデリートの仕組みはないため、削除操作には特に注意が必要です。

---

## 5. EnvironmentSecretProvider

**ソースファイル**: `src/infrastructure/secrets/secrets_provider.py`
**クラス名**: `EnvironmentSecretProvider`

### 概要

`EnvironmentSecretProvider` はOS環境変数 (`os.environ`) をバックエンドとするシークレットプロバイダーです。以下の用途で使用します。

- **ローカル開発環境**: クラウドサービスへの接続が不要な場合
- **テスト環境**: ユニットテストやCI/CDパイプラインでのモック代替
- **フォールバック**: クラウドプロバイダーのSDKが未インストール、または接続に失敗した場合の代替

### 動作仕様

| メソッド | 動作 |
|---------|------|
| `get_secret(name)` | `os.getenv(name)` で環境変数を取得。未設定の場合は `None` を返す |
| `set_secret(name, value)` | `os.environ[name] = value` で設定。実行プロセス内でのみ有効。常に `True` を返す |
| `delete_secret(name)` | `del os.environ[name]` で削除。環境変数が存在しない場合は `False` を返す |
| `list_secrets()` | `os.environ.keys()` の全環境変数名リストを返す |

### 使用例

```python
from src.infrastructure.secrets.secrets_provider import EnvironmentSecretProvider

# ローカル開発用のプロバイダー
provider = EnvironmentSecretProvider()

# .env ファイルと組み合わせて使用
# (.env ファイルは python-dotenv 等で事前にロード)
api_key = provider.get_secret("AZURE_FOUNDRY_API_KEY")

# テスト用にシークレットを一時設定
provider.set_secret("TEST_API_KEY", "test-value-123")
assert provider.get_secret("TEST_API_KEY") == "test-value-123"

# クリーンアップ
provider.delete_secret("TEST_API_KEY")
```

### 制限事項

- `set_secret()` による設定は現在のプロセスとその子プロセスにのみ反映されます
- `list_secrets()` はシステム全体の環境変数を返すため、本アプリケーションに無関係な変数も含まれます
- 環境変数は暗号化されず、プロセスメモリ内に平文で保持されます
- **本番環境での使用は推奨しません**

---

## 6. ファクトリーパターン

### `get_secret_provider()` 関数

**ソースファイル**: `src/infrastructure/secrets/secrets_provider.py`

#### シグネチャ

```python
def get_secret_provider(
    provider_type: Optional[str | Platform] = None,
    fallback_to_env: bool = True,
    **kwargs
) -> SecretProvider:
```

#### 引数

| 引数 | 型 | 必須 | デフォルト | 説明 |
|------|-----|------|----------|------|
| `provider_type` | `str \| Platform \| None` | No | `None` | プロバイダータイプ。`"azure"`, `"aws"`, `"gcp"`, `"env"` または `Platform` enum |
| `fallback_to_env` | `bool` | No | `True` | クラウドプロバイダー初期化失敗時に `EnvironmentSecretProvider` にフォールバックするか |
| `**kwargs` | `dict` | No | - | プロバイダー固有の初期化パラメータ |

#### 自動検出ロジック

`provider_type=None` の場合、以下の順序で環境変数からプロバイダータイプを自動検出します。

1. `SECRET_PROVIDER` 環境変数を確認
2. `CLOUD_PLATFORM` 環境変数を確認
3. いずれも未設定の場合は `"env"` をデフォルト値として使用

#### フォールバック動作

`fallback_to_env=True`（デフォルト）の場合、以下のエラーが発生すると `EnvironmentSecretProvider` に自動的にフォールバックします。

- `ImportError`: 必要なSDKパッケージが未インストール
- `ValueError`: 必須の環境変数（Vault URL、プロジェクトID等）が未設定
- `Exception`: ネットワークエラー、認証エラー等のランタイムエラー

```python
# フォールバック有効（デフォルト）-- 本番環境では非推奨
provider = get_secret_provider(provider_type="azure", fallback_to_env=True)
# → AzureKeyVaultProvider の初期化に失敗しても EnvironmentSecretProvider が返される

# フォールバック無効 -- 本番環境で推奨
provider = get_secret_provider(provider_type="azure", fallback_to_env=False)
# → AzureKeyVaultProvider の初期化に失敗すると例外が送出される
```

#### 使用例

```python
from src.infrastructure.secrets.secrets_provider import (
    get_secret_provider,
    Platform
)

# 環境変数から自動検出
provider = get_secret_provider()

# 文字列で明示的に指定
provider = get_secret_provider(provider_type="azure")

# Platform enum で指定
provider = get_secret_provider(provider_type=Platform.AZURE)

# プロバイダー固有のパラメータを渡す
provider = get_secret_provider(
    provider_type="azure",
    vault_url="https://my-vault.vault.azure.net/"
)

provider = get_secret_provider(
    provider_type="aws",
    region_name="ap-northeast-1"
)

provider = get_secret_provider(
    provider_type="gcp",
    project_id="my-project-123456"
)
```

---

## 7. シングルトンパターン

### `get_default_provider()` 関数

**ソースファイル**: `src/infrastructure/secrets/secrets_provider.py`

#### シグネチャ

```python
def get_default_provider(force_reinitialize: bool = False) -> SecretProvider:
```

#### 動作

グローバル変数 `_global_provider` にキャッシュされたシングルトンインスタンスを返します。

```mermaid
flowchart TD
    A["get_default_provider() 呼び出し"] --> B{force_reinitialize = True?}
    B -->|Yes| D["get_secret_provider() で新規作成"]
    B -->|No| C{_global_provider is None?}
    C -->|Yes| D
    C -->|No| E["キャッシュ済みインスタンスを返却"]
    D --> F["_global_provider に保存"]
    F --> E
```

#### 使用例

```python
from src.infrastructure.secrets.secrets_provider import get_default_provider

# 最初の呼び出しで初期化（環境変数から自動検出）
provider1 = get_default_provider()

# 2回目以降は同一インスタンスが返される
provider2 = get_default_provider()
assert provider1 is provider2  # True

# 強制的に再初期化（環境変数の変更後など）
provider3 = get_default_provider(force_reinitialize=True)
assert provider1 is not provider3  # True
```

#### キャッシュ無効化

以下のシナリオでは `force_reinitialize=True` を指定してプロバイダーを再初期化してください。

- 環境変数 `SECRET_PROVIDER` または `CLOUD_PLATFORM` を変更した場合
- テストケースでプロバイダーをリセットする必要がある場合
- 認証情報の有効期限切れでプロバイダーの再接続が必要な場合

---

## 8. シークレット一覧

本システムで管理するシークレットの一覧です。

### LLM API キー

| シークレット名 | 説明 | 使用コンポーネント | プラットフォーム |
|---------------|------|-------------------|----------------|
| `azure-foundry-api-key` | Azure AI Foundry APIキー | LLMエンジン | Azure |
| `bedrock-api-key` | Amazon Bedrock APIキー | LLMエンジン | AWS |
| `vertex-ai-key` | Google Vertex AI APIキー | LLMエンジン | GCP |

### OCR API キー

| シークレット名 | 説明 | 使用コンポーネント | プラットフォーム |
|---------------|------|-------------------|----------------|
| `azure-di-key` | Azure Document Intelligence APIキー | OCRプロセッサー | Azure |
| `textract-config` | Amazon Textract 設定情報 | OCRプロセッサー | AWS |
| `document-ai-config` | Google Document AI 設定情報 | OCRプロセッサー | GCP |

### ストレージ接続文字列

| シークレット名 | 説明 | 使用コンポーネント | プラットフォーム |
|---------------|------|-------------------|----------------|
| `storage-connection-string` | ストレージアカウント接続文字列 | ジョブストレージ | Azure |
| `s3-access-config` | S3アクセス設定 | ジョブストレージ | AWS |
| `gcs-access-config` | GCSアクセス設定 | ジョブストレージ | GCP |

### 環境変数名の対応関係

Key Vault等のシークレット名と環境変数名のマッピング:

| Key Vault名 | 環境変数名 | 備考 |
|-------------|-----------|------|
| `azure-foundry-api-key` | `AZURE_FOUNDRY_API_KEY` | ハイフンをアンダースコアに変換、大文字化 |
| `bedrock-api-key` | `BEDROCK_API_KEY` | 同上 |
| `vertex-ai-key` | `VERTEX_AI_KEY` | 同上 |

> **注意**: Azure Key Vault ではシークレット名にアンダースコアを使用できないため、ハイフン区切りの命名規則を採用しています。`EnvironmentSecretProvider` にフォールバックする際は、アンダースコア形式の環境変数名を使用してください。

---

## 9. セキュリティベストプラクティス

### 9.1 ログにシークレットを出力しない

本システムのプロバイダー実装では、シークレットの**名前**はログに記録しますが、**値**は一切ログに出力しません。アプリケーションコードでも同様の原則に従ってください。

```python
# 正しい例
logger.info(f"シークレットを取得しました: {secret_name}")

# 誤った例 -- 絶対に行わないでください
logger.info(f"シークレット値: {secret_value}")        # 値をログ出力
logger.debug(f"API Key = {provider.get_secret(name)}")  # 値をログ出力
print(f"接続文字列: {connection_string}")               # 標準出力に値を出力
```

### 9.2 環境変数に直接APIキーを設定しない（本番環境）

本番環境では必ずクラウドネイティブのシークレット管理サービスを使用してください。

```bash
# 本番環境: クラウドプロバイダーを指定（環境変数にはシークレット値を設定しない）
SECRET_PROVIDER=azure

# 開発環境のみ: 環境変数に直接設定可
AZURE_FOUNDRY_API_KEY=sk-dev-key-for-testing
```

`fallback_to_env` パラメータは開発環境での利便性のために提供されています。本番環境では `fallback_to_env=False` を指定するか、環境変数 `SECRET_PROVIDER` を正しく設定して常にクラウドプロバイダーが選択されるようにしてください。

### 9.3 アクセスポリシーは最小権限の原則

各コンポーネントに必要最小限の権限のみを付与してください。

| コンポーネント | 必要な権限 |
|---------------|-----------|
| アプリケーション（実行時） | `get`, `list` のみ |
| 管理者/デプロイパイプライン | `get`, `list`, `set`, `delete` |
| 監視/監査システム | `list` のみ |

```bash
# 悪い例: 全権限を付与
az keyvault set-policy --secret-permissions all

# 良い例: 必要最小限の権限のみ付与
az keyvault set-policy --secret-permissions get list
```

### 9.4 シークレットのローテーション

APIキーは定期的にローテーションしてください。推奨サイクルは以下の通りです。

| シークレット種別 | ローテーション間隔 | 備考 |
|----------------|-------------------|------|
| LLM APIキー | 90日 | プロバイダーのポリシーに準拠 |
| ストレージ接続文字列 | 180日 | Managed Identity 使用時は不要 |
| サービスプリンシパルシークレット | 365日 | 証明書ベースの認証を推奨 |

ローテーション手順:

1. 新しいシークレット値を生成/取得
2. `set_secret()` で新しい値を設定
3. アプリケーションの動作確認
4. 古いシークレットの無効化/削除
5. `get_default_provider(force_reinitialize=True)` でキャッシュを更新

### 9.5 CI/CD での GitHub Secrets 利用

CI/CDパイプラインでは GitHub Secrets を使用してシークレットを安全に管理してください。

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    env:
      SECRET_PROVIDER: env
      AZURE_FOUNDRY_API_KEY: ${{ secrets.AZURE_FOUNDRY_API_KEY }}
      BEDROCK_API_KEY: ${{ secrets.BEDROCK_API_KEY }}
      VERTEX_AI_KEY: ${{ secrets.VERTEX_AI_KEY }}

    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: pytest tests/
```

本番デプロイでは GitHub Secrets からクラウドプロバイダーの認証情報を取得し、アプリケーションをクラウド環境にデプロイすることで、実行時にはクラウドネイティブのシークレット管理サービスを使用します。

```yaml
# 本番デプロイの例（Azure）
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Azure Login
        uses: azure/login@v2
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Deploy to App Service
        uses: azure/webapps-deploy@v3
        with:
          app-name: ic-test-ai-app
        env:
          SECRET_PROVIDER: azure
          AZURE_KEY_VAULT_URL: https://ic-test-ai-vault.vault.azure.net/
```

### 9.6 .gitignore の設定

シークレット関連ファイルが誤ってリポジトリにコミットされないよう、`.gitignore` を適切に設定してください。

```gitignore
# 環境変数ファイル
.env
.env.local
.env.production
*.env

# クラウド認証情報ファイル
*-sa-key.json
*-credentials.json
service-account-*.json
```

---

## 10. トラブルシューティング

### エラー: ImportError -- SDK未インストール

```
ImportError: azure-keyvault-secrets と azure-identity がインストールされていません。
```

**原因**: 指定されたクラウドプロバイダーのSDKパッケージがインストールされていません。

**解決方法**:

```bash
# Azure の場合
pip install azure-keyvault-secrets azure-identity

# AWS の場合
pip install boto3

# GCP の場合
pip install google-cloud-secret-manager
```

`fallback_to_env=True`（デフォルト）の場合、このエラーは自動的にキャッチされ `EnvironmentSecretProvider` にフォールバックします。ログに以下のような警告が出力されます。

```
WARNING - 環境変数ベースのプロバイダーにフォールバックします
```

---

### エラー: ValueError -- 必須環境変数の未設定

```
ValueError: Key Vault URLが指定されていません。
引数 vault_url または環境変数 AZURE_KEY_VAULT_URL を設定してください。
```

**原因**: プロバイダーの初期化に必要な環境変数が設定されていません。

**解決方法**:

```bash
# Azure の場合
export AZURE_KEY_VAULT_URL="https://my-vault.vault.azure.net/"

# GCP の場合
export GCP_PROJECT_ID="my-project-123456"
# または
export GOOGLE_CLOUD_PROJECT="my-project-123456"
```

各プロバイダーの必須環境変数はセクション4を参照してください。

---

### エラー: AccessDenied / 403 Forbidden

```
azure.core.exceptions.HttpResponseError: (Forbidden) Access denied
```

**原因**: 認証されたIDにシークレットへのアクセス権限がありません。

**解決方法**:

**Azure の場合**:
```bash
# アクセスポリシーの確認
az keyvault show --name ic-test-ai-vault --query "properties.accessPolicies"

# 権限の付与
az keyvault set-policy \
  --name ic-test-ai-vault \
  --object-id <オブジェクトID> \
  --secret-permissions get list
```

**AWS の場合**:
```bash
# IAMポリシーのシミュレーション
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:role/ic-test-ai-role \
  --action-names secretsmanager:GetSecretValue \
  --resource-arns "arn:aws:secretsmanager:ap-northeast-1:123456789012:secret:*"
```

**GCP の場合**:
```bash
# IAMバインディングの確認
gcloud secrets get-iam-policy gemini-api-key --project=my-project

# 権限の付与
gcloud secrets add-iam-policy-binding gemini-api-key \
  --project=my-project \
  --member="serviceAccount:ic-test-ai@my-project.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

---

### エラー: ResourceNotFoundException -- シークレットが見つからない

```
botocore.exceptions.ClientError: ResourceNotFoundException: Secrets Manager can't find the specified secret.
```

**原因**: 指定されたシークレット名がサービスに存在しません。

**解決方法**:

1. シークレット名のスペルを確認してください
2. 正しいリージョン/プロジェクトに接続しているか確認してください
3. シークレットが削除されていないか確認してください

```bash
# AWS: シークレットの存在確認
aws secretsmanager describe-secret --secret-id bedrock-api-key --region ap-northeast-1

# Azure: シークレットの存在確認
az keyvault secret show --vault-name ic-test-ai-vault --name azure-foundry-api-key

# GCP: シークレットの存在確認
gcloud secrets describe gemini-api-key --project=my-project
```

---

### エラー: ネットワーク接続エラー

```
requests.exceptions.ConnectionError: Failed to establish a new connection
```

**原因**: クラウドサービスのエンドポイントに接続できません。

**解決方法**:

1. ネットワーク接続を確認してください
2. プロキシ設定が必要な場合は `HTTPS_PROXY` 環境変数を設定してください
3. ファイアウォールの設定を確認してください
4. `get_secret_with_retry()` メソッドの使用を検討してください（指数バックオフ付きリトライ）

```python
# リトライ付きでシークレットを取得
api_key = provider.get_secret_with_retry(
    "azure-foundry-api-key",
    max_retries=3,     # 最大3回リトライ
    fallback_env=True  # 全リトライ失敗後は環境変数にフォールバック
)
```

---

### エラー: プロバイダータイプが不正

```
ValueError: 不正なシークレットプロバイダータイプ: invalid_type。有効な値: azure, aws, gcp, env
```

**原因**: `get_secret_provider()` に無効なプロバイダータイプが指定されました。

**解決方法**:

```bash
# 有効な値: azure, aws, gcp, env
export SECRET_PROVIDER=azure

# Platform enum の使用も可能
# Platform.AZURE, Platform.AWS, Platform.GCP
```

---

### デバッグ: プロバイダーの初期化ログの確認

問題の切り分けのため、ログレベルを `DEBUG` に設定してプロバイダーの初期化プロセスを確認してください。

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# プロバイダーの初期化
provider = get_secret_provider()
```

出力例:

```
INFO - シークレットプロバイダーを初期化: azure
DEBUG - Key Vaultからシークレットを取得: azure-foundry-api-key
INFO - Azure Key Vault に接続しました: https://my-vault.vault.azure.net/
```

フォールバックが発生した場合:

```
INFO - シークレットプロバイダーを初期化: azure
ERROR - シークレットプロバイダーの初期化に失敗: azure-keyvault-secrets と azure-identity がインストールされていません。
WARNING - 環境変数ベースのプロバイダーにフォールバックします
INFO - 環境変数ベースのシークレットプロバイダーを初期化しました
```

---

## 付録: クイックリファレンス

### 環境変数チートシート

```bash
# --- プロバイダー選択 ---
SECRET_PROVIDER=azure          # azure | aws | gcp | env
CLOUD_PLATFORM=azure           # SECRET_PROVIDER 未設定時のフォールバック

# --- Azure Key Vault ---
AZURE_KEY_VAULT_URL=https://my-vault.vault.azure.net/
AZURE_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxx

# --- AWS Secrets Manager ---
AWS_REGION=ap-northeast-1
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY

# --- GCP Secret Manager ---
GCP_PROJECT_ID=my-project-123456
GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa-key.json
```

### 最小構成での起動

```bash
# ローカル開発（環境変数プロバイダー）
export AZURE_FOUNDRY_API_KEY="sk-dev-key"  # pragma: allowlist secret
python -m src.main

# Azure 本番
export SECRET_PROVIDER=azure
export AZURE_KEY_VAULT_URL=https://ic-test-ai-vault.vault.azure.net/
python -m src.main
```
