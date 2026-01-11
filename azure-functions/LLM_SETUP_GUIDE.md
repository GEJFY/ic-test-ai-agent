# LLM設定ガイド - クラウドプロバイダー別詳細手順

内部統制テスト評価AIのLLM（大規模言語モデル）接続設定ガイドです。
Azure AI Foundry、Azure OpenAI、GCP Vertex AI、AWS Bedrockから選択できます。

---

## 目次

1. [Azure AI Foundry（推奨）](#1-azure-ai-foundry推奨)
2. [Azure OpenAI Service](#2-azure-openai-service)
3. [GCP Vertex AI (Gemini)](#3-gcp-vertex-ai-gemini)
4. [AWS Bedrock](#4-aws-bedrock)
5. [Azure Functions環境変数の設定](#5-azure-functions環境変数の設定)
6. [動作確認](#6-動作確認)

---

## 1. Azure AI Foundry（推奨）

Azure AI Foundryは、Microsoftの統合AIプラットフォームです。OpenAI、Microsoft、オープンソースのモデルを一元管理できます。

### 1.1 前提条件

- Azureサブスクリプション
- Azure AI Foundryへのアクセス

### 1.2 Azure AI Foundryプロジェクトの作成

#### Step 1: Azure AI Foundryポータルにアクセス

1. [Azure AI Foundry](https://ai.azure.com) にアクセス
2. Azureアカウントでサインイン

#### Step 2: ハブの作成

1. 左メニュー「すべてのハブ」をクリック
2. 「+ 新しいハブ」をクリック
3. 以下を設定：

| 項目 | 設定値 |
|------|--------|
| ハブ名 | `hub-audit-ai`（任意） |
| サブスクリプション | 使用するサブスクリプション |
| リソースグループ | 既存または新規作成 |
| リージョン | Japan East または East US（モデル可用性確認） |

4. 「次へ」→「作成」をクリック

#### Step 3: プロジェクトの作成

1. 作成したハブを開く
2. 「+ 新しいプロジェクト」をクリック
3. プロジェクト名を入力（例: `project-audit-eval`）
4. 「作成」をクリック

#### Step 4: モデルのデプロイ

1. 左メニュー「モデル カタログ」をクリック
2. 使用するモデルを選択：
   - **gpt-4o**（推奨）
   - **gpt-4o-mini**（低コスト）
   - **Phi-4**（Microsoft製）
   - **DeepSeek-R1**（推論特化）
3. 「デプロイ」をクリック
4. デプロイ設定：

| 項目 | 推奨設定 |
|------|----------|
| デプロイ名 | `gpt-4o`（モデル名と同じが推奨） |
| デプロイの種類 | Standard |
| レート制限 | 10K TPM以上 |

5. 「デプロイ」をクリック

#### Step 5: エンドポイントとキーの取得

1. 左メニュー「デプロイ」をクリック
2. デプロイしたモデルを選択
3. 「エンドポイント」タブで以下を確認：

| 項目 | 形式 |
|------|------|
| エンドポイントURL | `https://<project-name>.<region>.models.ai.azure.com` |
| APIキー | `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` |

**重要**: エンドポイントURLはプロジェクト単位で発行されます。

### 1.3 必要な環境変数

```
LLM_PROVIDER=AZURE_FOUNDRY
AZURE_FOUNDRY_ENDPOINT=https://your-project.eastus.models.ai.azure.com
AZURE_FOUNDRY_API_KEY=your-api-key
```

### 1.4 オプション設定

```
# 使用するモデル名（デフォルト: gpt-4o）
AZURE_FOUNDRY_MODEL=gpt-4o

# 画像認識用モデル（デフォルト: AZURE_FOUNDRY_MODELと同じ）
AZURE_FOUNDRY_VISION_MODEL=gpt-4o

# APIバージョン
AZURE_FOUNDRY_API_VERSION=2024-08-01-preview
```

### 1.5 利用可能なモデル

| モデル | 説明 | 推奨用途 |
|--------|------|----------|
| gpt-4o | OpenAI最新マルチモーダル | 画像含む複雑な評価（推奨） |
| gpt-4o-mini | 軽量版GPT-4o | 大量処理・低コスト |
| Phi-4 | Microsoft製小型モデル | エッジ・低レイテンシ |
| DeepSeek-R1 | 推論特化モデル | 複雑な論理評価 |

### 1.6 Azure OpenAI Serviceとの違い

| 項目 | Azure AI Foundry | Azure OpenAI Service |
|------|------------------|----------------------|
| 管理ポータル | ai.azure.com | portal.azure.com |
| エンドポイント形式 | `*.models.ai.azure.com` | `*.openai.azure.com` |
| モデルカタログ | OpenAI + OSS + Microsoft | OpenAIのみ |
| 推奨度 | 新規プロジェクト向け | 既存環境向け |

---

## 2. Azure OpenAI Service

### 2.1 前提条件（Azure OpenAI）

- Azureサブスクリプション
- Azure OpenAI Serviceへのアクセス承認（申請が必要な場合あり）

### 2.2 Azure OpenAIリソースの作成

#### Step 1: Azure Portalにログイン

1. [Azure Portal](https://portal.azure.com) にアクセス
2. Azureアカウントでサインイン

#### Step 2: Azure OpenAIリソースの作成

1. 左上の「リソースの作成」をクリック
2. 検索ボックスに「Azure OpenAI」と入力
3. 「Azure OpenAI」を選択し、「作成」をクリック
4. 以下を設定：

| 項目 | 設定値 |
|------|--------|
| サブスクリプション | 使用するサブスクリプション |
| リソースグループ | 既存または新規作成（例: `rg-openai-audit`） |
| リージョン | Japan East（推奨）または利用可能なリージョン |
| 名前 | グローバルで一意の名前（例: `openai-audit-eval`） |
| 価格レベル | Standard S0 |

5. 「確認および作成」→「作成」をクリック

#### Step 3: モデルのデプロイ

1. 作成したAzure OpenAIリソースを開く
2. 左メニュー「モデル デプロイ」→「デプロイの管理」をクリック
3. Azure OpenAI Studioが開く
4. 「新しいデプロイの作成」をクリック
5. 以下を設定：

| 項目 | 推奨設定 |
|------|----------|
| モデル | gpt-4o |
| デプロイ名 | `gpt-4o`（任意の名前） |
| モデルバージョン | 最新版を選択 |
| デプロイの種類 | Standard |
| 1分あたりのトークンレート制限 | 10K以上推奨 |

6. 「作成」をクリック

#### Step 4: 接続情報の取得

1. Azure OpenAIリソースの「概要」ページで：
   - **エンドポイント**: `https://your-resource.openai.azure.com/` の形式

2. 左メニュー「キーとエンドポイント」で：
   - **キー1** または **キー2** をコピー

### 2.3 必要な環境変数（Azure OpenAI）

```
LLM_PROVIDER=AZURE
AZURE_OPENAI_API_KEY=<キー1またはキー2>
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
```

### 2.4 オプション設定（Azure OpenAI）

```
# APIバージョン（通常は変更不要）
AZURE_OPENAI_API_VERSION=2024-08-01-preview

# 画像認識用に別のデプロイを使用する場合
AZURE_OPENAI_VISION_DEPLOYMENT=gpt-4o-vision
```

---

## 3. GCP Vertex AI (Gemini)

### 3.1 前提条件（GCP）

- Google Cloudアカウント
- 課金が有効なプロジェクト

### 3.2 GCPプロジェクトの設定

#### Step 1: Google Cloud Consoleにログイン

1. [Google Cloud Console](https://console.cloud.google.com) にアクセス
2. Googleアカウントでサインイン

#### Step 2: プロジェクトの作成または選択

1. 画面上部のプロジェクトセレクタをクリック
2. 「新しいプロジェクト」を作成、または既存プロジェクトを選択
3. プロジェクトIDをメモ（例: `my-audit-project-123`）

#### Step 3: Vertex AI APIの有効化

1. 左メニュー「APIとサービス」→「ライブラリ」
2. 検索ボックスに「Vertex AI API」と入力
3. 「Vertex AI API」を選択
4. 「有効にする」をクリック

#### Step 4: サービスアカウントの作成

1. 左メニュー「IAMと管理」→「サービスアカウント」
2. 「サービスアカウントを作成」をクリック
3. 以下を設定：

| 項目 | 設定値 |
|------|--------|
| サービスアカウント名 | `audit-ai-agent` |
| サービスアカウントID | 自動生成される |
| 説明 | 内部統制評価AI用 |

4. 「作成して続行」をクリック

#### Step 5: 権限の付与

1. 「ロールを選択」で以下を追加：
   - `Vertex AI ユーザー` (roles/aiplatform.user)

2. 「続行」→「完了」をクリック

#### Step 6: サービスアカウントキーの作成

1. 作成したサービスアカウントをクリック
2. 「キー」タブを選択
3. 「鍵を追加」→「新しい鍵を作成」
4. キーのタイプ: JSON
5. 「作成」をクリック
6. JSONファイルが自動ダウンロードされる（安全に保管）

### 3.3 必要な環境変数（GCP）

```
LLM_PROVIDER=GCP
GCP_PROJECT_ID=my-audit-project-123
GCP_LOCATION=us-central1
```

### 3.4 認証方法（GCP）

#### 方法A: サービスアカウントキーファイル（推奨）

```
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

**Azure Functionsの場合：**
1. サービスアカウントキーJSONの内容を環境変数に設定
2. コード内でJSONをファイルに書き出すか、直接認証に使用

#### 方法B: Workload Identity Federation（本番環境推奨）

Azure FunctionsからGCPへのWorkload Identity Federationを設定することで、
キーファイルなしで認証可能。詳細は[GCP公式ドキュメント](https://cloud.google.com/iam/docs/workload-identity-federation)参照。

### 3.5 利用可能なモデル（GCP）

| モデル名 | 説明 | 推奨用途 |
|----------|------|----------|
| gemini-1.5-pro | 高性能・長コンテキスト | 複雑な監査評価 |
| gemini-1.5-flash | 高速・低コスト | 大量処理 |
| gemini-2.0-flash-exp | 最新実験版 | テスト用 |

### 3.6 リージョン一覧（GCP）

| リージョン | 場所 |
|------------|------|
| us-central1 | アイオワ（デフォルト） |
| us-east4 | バージニア |
| europe-west1 | ベルギー |
| asia-northeast1 | 東京 |

---

## 4. AWS Bedrock

### 4.1 前提条件（AWS）

- AWSアカウント
- Bedrockへのアクセス権限

### 4.2 Bedrockの設定

#### Step 1: AWS Management Consoleにログイン

1. [AWS Console](https://console.aws.amazon.com) にアクセス
2. AWSアカウントでサインイン
3. リージョンを選択（例: us-east-1）

#### Step 2: Bedrockモデルアクセスの有効化

1. 検索バーに「Bedrock」と入力し、Amazon Bedrockを開く
2. 左メニュー「Model access」をクリック
3. 「Manage model access」をクリック
4. 使用するモデルにチェック：
   - **Anthropic Claude 3.5 Sonnet**（推奨）
   - **Anthropic Claude 3 Haiku**（高速・低コスト）
   - **Amazon Titan**（Amazon製）
5. 「Request model access」をクリック
6. 承認を待つ（即時〜数時間）

#### Step 3: IAMユーザー/ロールの設定

##### 方法A: IAMユーザー（開発・テスト用）

1. IAMコンソールを開く
2. 「ユーザー」→「ユーザーを追加」
3. ユーザー名: `audit-ai-agent`
4. 「アクセスキー - プログラムによるアクセス」にチェック
5. 「次へ」→「ポリシーを直接アタッチ」
6. 以下のポリシーを作成してアタッチ：

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream"
            ],
            "Resource": [
                "arn:aws:bedrock:*::foundation-model/anthropic.claude-*",
                "arn:aws:bedrock:*::foundation-model/amazon.titan-*"
            ]
        }
    ]
}
```

7. 「次へ」→「ユーザーの作成」
8. アクセスキーIDとシークレットアクセスキーをメモ

##### 方法B: IAMロール（本番環境推奨）

Azure FunctionsにIAMロールを割り当てる場合は、
AWS STSのAssumeRoleを使用。

### 4.3 必要な環境変数（AWS）

```
LLM_PROVIDER=AWS
AWS_REGION=us-east-1
```

### 4.4 認証方法（AWS）

#### 方法A: アクセスキー（開発用）

```
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```

#### 方法B: プロファイル

```
AWS_PROFILE=audit-profile
```

#### 方法C: IAMロール（本番推奨）

Azure FunctionsからAWSへのクロスアカウントアクセスを設定。

### 4.5 利用可能なモデル（AWS）

| モデルID | 説明 | 推奨用途 |
|----------|------|----------|
| anthropic.claude-3-5-sonnet-20241022-v2:0 | Claude 3.5 Sonnet | 高精度評価（推奨） |
| anthropic.claude-3-haiku-20240307-v1:0 | Claude 3 Haiku | 高速・低コスト |
| amazon.titan-text-express-v1 | Amazon Titan | 基本的な処理 |

### 4.6 リージョン別モデル可用性

| リージョン | Claude 3.5 | Claude 3 Haiku | Titan |
|------------|------------|----------------|-------|
| us-east-1 | ✓ | ✓ | ✓ |
| us-west-2 | ✓ | ✓ | ✓ |
| eu-west-1 | ✓ | ✓ | ✓ |
| ap-northeast-1 | ✓ | ✓ | ✓ |

---

## 5. Azure Functions環境変数の設定

### 5.1 Azure Portalでの設定手順

#### Step 1: Function Appを開く

1. [Azure Portal](https://portal.azure.com) にログイン
2. 「Function App」を検索
3. `func-ic-test-evaluation` を選択

#### Step 2: 環境変数の設定

1. 左メニュー「設定」→「環境変数」をクリック
2. 「アプリケーション設定」タブを選択
3. 「追加」をクリックして各環境変数を設定

### 5.2 プロバイダー別設定例

#### Azure AI Foundry の場合（推奨）

| 名前 | 値 |
|------|-----|
| LLM_PROVIDER | AZURE_FOUNDRY |
| AZURE_FOUNDRY_ENDPOINT | `https://your-project.region.models.ai.azure.com` |
| AZURE_FOUNDRY_API_KEY | your-api-key |

#### Azure OpenAI の場合

| 名前 | 値 |
|------|-----|
| LLM_PROVIDER | AZURE |
| AZURE_OPENAI_API_KEY | sk-xxxxxxxxxxxxx |
| AZURE_OPENAI_ENDPOINT | https://your-resource.openai.azure.com/ |
| AZURE_OPENAI_DEPLOYMENT_NAME | gpt-4o |

#### GCP Vertex AI の場合

| 名前 | 値 |
|------|-----|
| LLM_PROVIDER | GCP |
| GCP_PROJECT_ID | my-project-123 |
| GCP_LOCATION | us-central1 |
| GOOGLE_APPLICATION_CREDENTIALS_JSON | {"type":"service_account",...} |

**注意**: GCPの場合、サービスアカウントキーJSONの内容を環境変数に設定し、
コード側で処理する必要があります。

#### AWS Bedrock の場合

| 名前 | 値 |
|------|-----|
| LLM_PROVIDER | AWS |
| AWS_REGION | us-east-1 |
| AWS_ACCESS_KEY_ID | AKIAIOSFODNN7EXAMPLE |
| AWS_SECRET_ACCESS_KEY | wJalrXUtnFEMI/... |

### 5.3 設定の保存と反映

1. すべての環境変数を追加後、「保存」をクリック
2. 確認ダイアログで「確認」をクリック
3. Function Appが自動的に再起動
4. 約1〜2分で設定が反映

### 5.4 Azure CLIでの設定（代替方法）

```powershell
# Azure OpenAI の場合
az functionapp config appsettings set `
    --name func-ic-test-evaluation `
    --resource-group rg-ic-test-evaluation `
    --settings `
        LLM_PROVIDER=AZURE `
        AZURE_OPENAI_API_KEY="your-api-key" `
        AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/" `
        AZURE_OPENAI_DEPLOYMENT_NAME="gpt-4o"
```

---

## 6. 動作確認

### 6.1 設定状態の確認

ブラウザまたはPowerShellで `/api/config` エンドポイントにアクセス：

```powershell
Invoke-RestMethod -Uri "https://func-ic-test-evaluation.azurewebsites.net/api/config" -Method GET
```

#### 正常な応答例（設定完了時）

```json
{
  "current_status": {
    "provider": "AZURE",
    "configured": true,
    "missing_vars": []
  },
  "supported_providers": { ... }
}
```

#### 未設定時の応答例

```json
{
  "current_status": {
    "provider": "NOT_SET",
    "configured": false,
    "missing_vars": []
  }
}
```

### 6.2 ヘルスチェック

```powershell
Invoke-RestMethod -Uri "https://func-ic-test-evaluation.azurewebsites.net/api/health" -Method GET
```

#### 応答例

```json
{
  "status": "healthy",
  "version": "2.0.0-ai",
  "llm": {
    "provider": "AZURE",
    "configured": true,
    "missing_vars": []
  },
  "features": {
    "a1_semantic_search": true,
    "a2_image_recognition": true,
    ...
  }
}
```

### 6.3 評価APIのテスト

```powershell
$headers = @{
    "Content-Type" = "application/json; charset=utf-8"
    "x-functions-key" = "your-function-key"
}

$body = @'
[
    {
        "ID": "TEST-001",
        "ControlDescription": "経営層は年度計画策定時に事業リスク評価を行い、取締役会にて承認されている。",
        "TestProcedure": "取締役会議事録を閲覧し、リスクアセスメントの結果が報告され、承認を得ていることを確認する。",
        "EvidenceLink": "",
        "EvidenceFiles": []
    }
]
'@

$response = Invoke-RestMethod `
    -Uri "https://func-ic-test-evaluation.azurewebsites.net/api/evaluate" `
    -Method POST `
    -Headers $headers `
    -Body $body

$response | ConvertTo-Json -Depth 5
```

### 6.4 トラブルシューティング

#### 問題: `LLM not configured` と表示される

**原因**: 環境変数が設定されていない、または不足している

**解決策**:
1. `/api/config` で `missing_vars` を確認
2. 不足している環境変数を追加
3. Function Appを再起動

#### 問題: 認証エラー（401/403）

**Azure OpenAI**:
- APIキーが正しいか確認
- エンドポイントURLの末尾に `/` があるか確認

**GCP**:
- サービスアカウントに `Vertex AI ユーザー` 権限があるか確認
- プロジェクトIDが正しいか確認

**AWS**:
- アクセスキーが有効か確認
- Bedrockモデルへのアクセスが承認されているか確認
- IAMポリシーに `bedrock:InvokeModel` 権限があるか確認

#### 問題: タイムアウト

**解決策**:
- Azure Functionsのタイムアウト設定を延長
- より高速なモデル（Haiku/Flash）を使用

---

## 6. コスト見積もり

### 6.1 Azure OpenAI (GPT-4o)

| 項目 | 価格 |
|------|------|
| 入力トークン | $2.50 / 100万トークン |
| 出力トークン | $10.00 / 100万トークン |

### 6.2 GCP Vertex AI (Gemini 1.5 Pro)

| 項目 | 価格 |
|------|------|
| 入力トークン | $1.25 / 100万トークン |
| 出力トークン | $5.00 / 100万トークン |

### 6.3 AWS Bedrock (Claude 3.5 Sonnet)

| 項目 | 価格 |
|------|------|
| 入力トークン | $3.00 / 100万トークン |
| 出力トークン | $15.00 / 100万トークン |

**注意**: 価格は変動する可能性があります。最新情報は各クラウドプロバイダーの公式サイトをご確認ください。

---

## 7. セキュリティベストプラクティス

1. **APIキーのローテーション**: 定期的にAPIキーを更新
2. **最小権限の原則**: 必要最小限の権限のみ付与
3. **監査ログ**: クラウドプロバイダーの監査ログを有効化
4. **ネットワーク制限**: 可能な場合、VNet統合やプライベートエンドポイントを使用
5. **Key Vault**: 本番環境ではAzure Key Vaultでシークレットを管理

---

## 更新履歴

| 日付 | バージョン | 変更内容 |
|------|------------|----------|
| 2024-01-04 | 2.0 | Azure/GCP/AWS対応版作成 |
