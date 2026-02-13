# AWS環境セットアップガイド - 内部統制テスト評価AIシステム

> **対象読者**: AWSを初めて使う方でも、このガイドに沿って進めれば環境構築が完了します。
> **所要時間**: 約3〜5時間（Bedrockモデルアクセス承認の待ち時間を除く）
> **最終更新**: 2026年2月

---

## 目次

1. [はじめに](#1-はじめに)
2. [AWSとは](#2-awsとは)
3. [AWS CLIのセットアップ](#3-aws-cliのセットアップ)
4. [IAM（Identity and Access Management）](#4-iamidentity-and-access-management)
5. [AWS App Runner](#5-aws-app-runner)
6. [Amazon Bedrock](#6-amazon-bedrock)
7. [Amazon Textract](#7-amazon-textract)
8. [API Gateway](#8-api-gateway)
9. [Secrets Manager](#9-secrets-manager)
10. [CloudWatch / X-Ray](#10-cloudwatch--x-ray)
11. [S3](#11-s3)
12. [Terraformデプロイ](#12-terraformデプロイ)
13. [統合テスト](#13-統合テスト)
14. [コスト管理](#14-コスト管理)
15. [まとめ・次のステップ](#15-まとめ次のステップ)

---

## 記号の説明

| 記号 | 意味 |
|------|------|
| 💡 | ヒント・補足情報 |
| ⚠️ | 注意・警告 |
| ✅ | 確認ポイント・検証手順 |
| 📋 | 前提条件・準備事項 |
| 🔧 | トラブルシューティング |

---

## 1. はじめに

### このガイドの目的

このガイドは、**内部統制テスト評価AIシステム**をAWS上にデプロイするための手順書です。
クラウド経験が全くない方でも、1つずつ手順を追えば環境構築が完了するよう設計されています。

このシステムは以下のAWSサービスを使用します：

| AWSサービス | 役割 |
|-------------|------|
| **IAM** | アクセス制御・権限管理 |
| **App Runner** | バックエンドAPI処理（コンテナ） |
| **Bedrock** | AI/LLM（Claude Sonnet）による評価 |
| **Textract** | 書類のOCR（文字認識） |
| **API Gateway** | REST APIエンドポイント公開 |
| **Secrets Manager** | APIキー・機密情報の安全な管理 |
| **CloudWatch** | ログ・メトリクス・アラーム |
| **X-Ray** | 分散トレーシング（処理追跡） |
| **S3** | ファイルストレージ |

### 📋 前提条件チェックリスト

開始前に以下を確認してください：

- [ ] クレジットカードを用意している（AWSアカウント作成に必要）
- [ ] Python 3.11がインストールされている
- [ ] Git がインストールされている
- [ ] テキストエディタ（VS Code推奨）がある
- [ ] ターミナル/コマンドプロンプトを開ける
- [ ] 本プロジェクトのリポジトリをクローン済みである

### 所要時間の目安

| セクション | 目安 |
|-----------|------|
| AWSアカウント作成 | 15分 |
| AWS CLI設定 | 20分 |
| IAM設定 | 20分 |
| Bedrockモデル申請 | 10分（承認まで数時間〜1営業日） |
| Terraformデプロイ | 30分 |
| 統合テスト・検証 | 30分 |

---

## 2. AWSとは

### クラウドサービスの概要

**AWS（Amazon Web Services）** は、Amazonが提供するクラウドコンピューティングサービスです。
自社でサーバーを購入・管理する代わりに、インターネット経由でコンピュータリソースを必要な分だけ「借りる」ことができます。

主要なサービスカテゴリ：

| カテゴリ | 代表サービス | 説明 |
|---------|-------------|------|
| コンピューティング | EC2, App Runner | サーバー・コンテナ実行 |
| ストレージ | S3 | ファイル保存 |
| データベース | DynamoDB, RDS | データ管理 |
| AI/ML | Bedrock, Textract | AI・機械学習 |
| ネットワーク | API Gateway, VPC | 通信・API公開 |
| セキュリティ | IAM, Secrets Manager | 認証・機密管理 |
| 監視 | CloudWatch, X-Ray | ログ・トレーシング |

### なぜAWSを使うのか

- **スケーラビリティ**: 利用量に応じて自動でリソースが増減する
- **従量課金**: 使った分だけ料金が発生（初期費用不要）
- **マネージドサービス**: サーバー管理はAWSが行う（特にApp Runner）
- **セキュリティ**: エンタープライズ級のセキュリティ基盤
- **Bedrock**: Claude Sonnetなどの最新AIモデルをAPIで利用可能

### AWSアカウント作成手順

1. **[AWS公式サイト](https://aws.amazon.com/)** にアクセス
2. 「無料でサインアップ」をクリック
3. メールアドレス、パスワード、アカウント名を入力
4. 連絡先情報を入力
5. クレジットカード情報を入力（無料枠内であれば課金なし）
6. 電話番号認証を完了
7. サポートプランは **「ベーシック（無料）」** を選択

💡 **無料枠について**: AWSは新規アカウント作成から12か月間、多くのサービスで無料枠を提供しています。
App Runner は自動スケーリング対応のコンテナ実行サービスで、従量課金制です。

⚠️ **注意**: ルートアカウント（最初に作成したアカウント）は日常作業には使わず、
後述のIAMユーザーを作成して使用してください。ルートアカウントの漏洩は全リソースへの不正アクセスにつながります。

### AWS Management Consoleの基本操作

AWSアカウントを作成したら、[AWS Management Console](https://console.aws.amazon.com/) にログインします。

- **検索バー**: 画面上部の検索バーでサービス名を入力するとすぐにアクセスできます
- **リージョン選択**: 右上のリージョンメニューから **「アジアパシフィック (東京) ap-northeast-1」** を選択してください
- **サービスメニュー**: 左上のメニューから全サービスを一覧できます

✅ **確認ポイント**: コンソール右上のリージョンが「東京（ap-northeast-1）」になっていることを確認してください。
リージョンが違うと、作成したリソースが見つからなくなります。

---

## 3. AWS CLIのセットアップ

### AWS CLIとは

**AWS CLI（Command Line Interface）** は、コマンドライン（ターミナル）からAWSサービスを操作するためのツールです。
ブラウザのコンソール画面でも同じ操作ができますが、CLIを使う理由は：

- **自動化**: スクリプトで反復作業を自動化できる
- **再現性**: 同じコマンドを実行すれば同じ結果になる
- **効率性**: ブラウザ操作より高速
- **Terraform連携**: Infrastructure as Codeに必須

### インストール手順

#### Windows の場合

```bash
# MSIインストーラーをダウンロードして実行
# 公式ページ: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html

# PowerShellで以下を実行
msiexec.exe /i https://awscli.amazonaws.com/AWSCLIV2.msi

# インストール確認
aws --version
```

期待される出力：
```
aws-cli/2.x.x Python/3.x.x Windows/10 exe/AMD64
```

#### macOS の場合

```bash
# Homebrewを使う場合
brew install awscli

# またはpkgインストーラー
curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
sudo installer -pkg AWSCLIV2.pkg -target /

# インストール確認
aws --version
```

#### Linux の場合

```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# インストール確認
aws --version
```

### IAMユーザー作成とアクセスキー取得

AWS CLIの認証設定をする前に、まずIAMユーザーを作成し、アクセスキーを取得します。

1. AWS Management Console にルートアカウントでログイン
2. 検索バーに「IAM」と入力し、IAMサービスを開く
3. 左メニューの「ユーザー」をクリック
4. 「ユーザーを追加」をクリック
5. ユーザー名を入力（例: `ic-test-admin`）
6. 「AWS マネジメントコンソールへのユーザーアクセスを提供する」にチェック
7. 「ポリシーを直接アタッチする」を選択
8. `AdministratorAccess` ポリシーを検索してチェック
9. 「ユーザーの作成」をクリック

⚠️ **注意**: `AdministratorAccess` は開発・セットアップ段階では便利ですが、
本番環境では最小権限の原則に従い、必要なポリシーだけを付与してください。

次に、アクセスキーを作成します：

1. 作成したユーザー名をクリック
2. 「セキュリティ認証情報」タブをクリック
3. 「アクセスキーを作成」をクリック
4. ユースケースで「コマンドラインインターフェイス (CLI)」を選択
5. 「アクセスキーを作成」をクリック
6. **アクセスキーID** と **シークレットアクセスキー** を安全に保存

⚠️ **重要**: シークレットアクセスキーは、この画面でしか表示されません。
必ずメモを取るか、CSVファイルをダウンロードしてください。
紛失した場合は、新しいアクセスキーを再作成する必要があります。

### aws configure（認証設定）

取得したアクセスキーを使ってAWS CLIを設定します。

```bash
aws configure
```

以下のように順番に入力を求められます：

```
AWS Access Key ID [None]: AKIAIOSFODNN7EXAMPLE        # 取得したアクセスキーID  # pragma: allowlist secret
AWS Secret Access Key [None]: wJalrXUtnFEMI/K7MDENG... # 取得したシークレットアクセスキー  # pragma: allowlist secret
Default region name [None]: ap-northeast-1              # 東京リージョン
Default output format [None]: json                      # JSON形式で出力
```

💡 **リージョンについて**: `ap-northeast-1` は東京リージョンです。
日本からのアクセスでは最も低レイテンシで利用できます。
本プロジェクトではこのリージョンの使用を推奨しています。

### 認証確認

設定が正しいか確認します。

```bash
aws sts get-caller-identity
```

期待される出力：
```json
{
    "UserId": "AIDAIOSFODNN7EXAMPLE",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/ic-test-admin"
}
```

✅ **確認ポイント**:
- `Account` にAWSアカウントIDが表示されている
- `Arn` に作成したIAMユーザー名が含まれている
- エラーが発生しない

### 🔧 よくあるエラー

| エラー | 原因 | 解決方法 |
|--------|------|----------|
| `Unable to locate credentials` | aws configureが未実行 | `aws configure` を再実行 |
| `InvalidClientTokenId` | アクセスキーが間違っている | IAMコンソールでキーを再確認 |
| `SignatureDoesNotMatch` | シークレットキーが間違っている | 新しいアクセスキーを再作成 |
| `ExpiredToken` | 一時認証情報の期限切れ | `aws configure` で再設定 |
| コマンドが見つからない | AWS CLIが未インストール | インストール手順を再実行 |

---

## 4. IAM（Identity and Access Management）

### IAMとは

**IAM（Identity and Access Management）** は、AWSリソースへの「誰が」「何を」できるかを制御するサービスです。

主要な概念：

```
┌─────────────────────────────────────────────────────────┐
│                     AWSアカウント                         │
│                                                          │
│  ┌──────────┐    ┌──────────┐    ┌───────────────────┐  │
│  │ IAMユーザー│    │ IAMロール │    │ IAMポリシー        │  │
│  │           │    │           │    │                    │  │
│  │ 人が使う   │    │ サービスが │    │ 権限を定義する     │  │
│  │ 認証情報   │    │ 使う認証  │    │ JSONドキュメント   │  │
│  └──────────┘    └──────────┘    └───────────────────┘  │
│                                                          │
│  ユーザー/ロール にポリシーを「アタッチ」して権限を付与     │
└─────────────────────────────────────────────────────────┘
```

- **IAMユーザー**: 人間がAWSにログインするためのアカウント
- **IAMロール**: AWSサービス（App Runner等）がAWSリソースにアクセスするための権限セット
- **IAMポリシー**: 「何のサービスの」「何の操作を」「許可/拒否する」かを定義するJSONドキュメント

### App Runnerインスタンスロール作成

App Runnerサービスが他のAWSサービス（Bedrock、Textract等）にアクセスするためのIAMロールを作成します。

💡 **Terraformで自動作成される場合**: 後述のTerraformデプロイを使う場合、このロールは自動的に作成されます。
ここでは手動で作成する方法を学習目的で説明しています。

#### 信頼ポリシーの作成

まず、信頼ポリシー（Trust Policy）のJSONファイルを作成します。
信頼ポリシーは「誰がこのロールを引き受けることができるか」を定義します。

```bash
# 信頼ポリシーファイルを作成
# Windowsの場合はPowerShellでOut-Fileを使用してください
```

以下の内容で `trust-policy.json` を作成します：

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": [
          "apprunner.amazonaws.com",
          "build.apprunner.amazonaws.com",
          "tasks.apprunner.amazonaws.com"
        ]
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

💡 **解説**: この信頼ポリシーは「App Runner サービスがこのロールを引き受けることを許可する」という意味です。
`Principal.Service` に `tasks.apprunner.amazonaws.com` を指定することで、App Runnerのタスクがこのロールを使えるようになります。

#### IAMロール作成

```bash
aws iam create-role \
  --role-name ic-test-ai-prod-apprunner-instance-role \
  --assume-role-policy-document file://trust-policy.json \
  --description "内部統制テスト評価AI App Runnerインスタンスロール"
```

期待される出力：
```json
{
    "Role": {
        "RoleName": "ic-test-ai-prod-apprunner-instance-role",
        "Arn": "arn:aws:iam::123456789012:role/ic-test-ai-prod-apprunner-instance-role",
        ...
    }
}
```

### 必要なポリシーのアタッチ

App Runnerサービスに必要な権限をロールに追加します。

```bash
# 1. X-Rayトレーシング権限
aws iam attach-role-policy \
  --role-name ic-test-ai-prod-apprunner-instance-role \
  --policy-arn arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess
```

💡 **AWS管理ポリシーとは**: `arn:aws:iam::aws:policy/...` で始まるポリシーはAWSが事前に用意してくれているポリシーです。
よく使われる権限セットがまとめられており、自分で一から書く必要がありません。

#### カスタムポリシーの作成（Bedrock・Textract用）

Bedrock と Textract のアクセス権限はカスタムポリシーとして作成します。

```bash
# Bedrock呼び出しポリシー
aws iam put-role-policy \
  --role-name ic-test-ai-prod-apprunner-instance-role \
  --policy-name ic-test-ai-prod-apprunner-bedrock \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ],
        "Resource": "*"
      }
    ]
  }'

# Textract呼び出しポリシー
aws iam put-role-policy \
  --role-name ic-test-ai-prod-apprunner-instance-role \
  --policy-name ic-test-ai-prod-apprunner-textract \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": [
          "textract:AnalyzeDocument",
          "textract:DetectDocumentText"
        ],
        "Resource": "*"
      }
    ]
  }'
```

### ポリシー一覧と最小権限の原則

本プロジェクトのApp Runnerサービスに必要なポリシーの全一覧：

| ポリシー | 種類 | 目的 |
|---------|------|------|
| `AWSXRayDaemonWriteAccess` | AWS管理 | X-Rayトレースデータの送信 |
| `apprunner-bedrock`（カスタム） | インライン | Bedrockモデル呼び出し |
| `apprunner-textract`（カスタム） | インライン | Textract OCR呼び出し |
| `apprunner-secrets-read`（カスタム） | カスタム管理 | Secrets Managerからの読み取り |

⚠️ **最小権限の原則**: セキュリティのベストプラクティスとして、必要最低限の権限だけを付与してください。
`AdministratorAccess` や `*`（全リソース）の指定は、開発段階以外では避けるべきです。
本番環境では、`Resource` に具体的なARNを指定してリソースを限定してください。

✅ **確認ポイント**: ロールに付与されたポリシーを確認します。

```bash
aws iam list-attached-role-policies \
  --role-name ic-test-ai-prod-apprunner-instance-role
```

```bash
aws iam list-role-policies \
  --role-name ic-test-ai-prod-apprunner-instance-role
```

---

## 5. AWS App Runner

### コンテナサービスとApp Runnerの仕組み

**AWS App Runner** は、コンテナ化されたWebアプリケーションを簡単にデプロイ・実行できるマネージドサービスです。

**従来のサーバー方式**:
```
リクエスト → [常時稼働サーバー] → レスポンス
（サーバーが無くても料金が発生）
```

**App Runner方式**:
```
Dockerイメージ → [App Runner] → HTTPS URL自動発行
（自動スケーリング・ロードバランシング込み）
```

App Runnerの特徴：
- **サーバー管理不要**: OS、パッチ適用、スケーリングをAWSが自動管理
- **Dockerイメージ対応**: ECRからコンテナイメージをデプロイ
- **自動HTTPS**: SSL/TLS証明書が自動発行される
- **自動スケーリング**: リクエスト数に応じてコンテナインスタンスが増減
- **ヘルスチェック**: 自動的にコンテナのヘルスを監視

💡 **App RunnerとECSの違い**: App RunnerはECS/Fargateよりもシンプルで、VPCやロードバランサーの設定が不要です。
Web APIのデプロイに最適化されており、本プロジェクトのようなFastAPIアプリケーションに適しています。

### App Runnerサービスの設定（本プロジェクト）

本プロジェクトのTerraform設定に基づくApp Runnerサービスのパラメータ：

| パラメータ | 値 | 説明 |
|-----------|-----|------|
| サービス名 | `ic-test-ai-prod` | 内部統制テスト評価サービス |
| コンテナポート | `8000` | FastAPIデフォルトポート |
| CPU | `1 vCPU` | コンテナCPU割り当て |
| メモリ | `2 GB` | Bedrock呼び出しに十分なメモリ |
| ヘルスチェック | `/api/health` | HTTPヘルスチェックパス |
| イメージソース | ECR | Amazon ECRからDockerイメージをプル |

### Dockerイメージのビルドとプッシュ

App Runnerにデプロイするには、DockerイメージをビルドしてECR（Elastic Container Registry）にプッシュします。

```bash
# プロジェクトルートに移動
cd ic-test-ai-agent

# Dockerイメージをビルド
docker build -t ic-test-ai-agent .

# ローカルでテスト実行
docker run -p 8000:8000 --env-file .env ic-test-ai-agent

# 別ターミナルからヘルスチェック
curl http://localhost:8000/api/health
```

💡 **Dockerfile について**: プロジェクトルートにDockerfileが含まれています。
`platforms/local/main.py` をエントリーポイントとするFastAPIアプリケーションとしてビルドされます。

### ECRリポジトリの作成とプッシュ

```bash
# ECRリポジトリを作成
aws ecr create-repository \
  --repository-name ic-test-ai-agent \
  --region ap-northeast-1

# ECRにログイン
aws ecr get-login-password --region ap-northeast-1 | \
  docker login --username AWS --password-stdin \
  123456789012.dkr.ecr.ap-northeast-1.amazonaws.com

# イメージにタグを付与
docker tag ic-test-ai-agent:latest \
  123456789012.dkr.ecr.ap-northeast-1.amazonaws.com/ic-test-ai-agent:latest

# ECRにプッシュ
docker push \
  123456789012.dkr.ecr.ap-northeast-1.amazonaws.com/ic-test-ai-agent:latest
```

### ローカルテスト

デプロイ前にローカルでコンテナをテストします。

```bash
# Dockerコンテナをローカルで実行
docker run -p 8000:8000 --env-file .env ic-test-ai-agent

# または、pytestでユニットテストを実行
python -m pytest tests/ -v
```

### App Runnerサービスの手動作成

⚠️ **Terraformを使う場合は不要**: 後述のTerraformデプロイ（セクション12）では、App Runnerサービスが自動作成されます。
ここでは学習目的で手動デプロイの方法を説明しています。

```bash
# App Runnerサービスを作成
aws apprunner create-service \
  --service-name ic-test-ai-prod \
  --source-configuration '{
    "AuthenticationConfiguration": {
      "AccessRoleArn": "arn:aws:iam::123456789012:role/ic-test-ai-prod-apprunner-access-role"
    },
    "ImageRepository": {
      "ImageIdentifier": "123456789012.dkr.ecr.ap-northeast-1.amazonaws.com/ic-test-ai-agent:latest",
      "ImageRepositoryType": "ECR",
      "ImageConfiguration": {
        "Port": "8000",
        "RuntimeEnvironmentVariables": {
          "LLM_PROVIDER": "AWS",
          "OCR_PROVIDER": "AWS",
          "AWS_REGION_NAME": "ap-northeast-1"
        }
      }
    }
  }' \
  --instance-configuration '{
    "Cpu": "1024",
    "Memory": "2048",
    "InstanceRoleArn": "arn:aws:iam::123456789012:role/ic-test-ai-prod-apprunner-instance-role"
  }' \
  --health-check-configuration '{
    "Protocol": "HTTP",
    "Path": "/api/health",
    "Interval": 10,
    "Timeout": 5,
    "HealthyThreshold": 1,
    "UnhealthyThreshold": 5
  }'
```

期待される出力：
```json
{
    "Service": {
        "ServiceName": "ic-test-ai-prod",
        "ServiceUrl": "xxxxxxxx.ap-northeast-1.awsapprunner.com",
        "Status": "OPERATION_IN_PROGRESS",
        ...
    }
}
```

### テスト実行

```bash
# App RunnerサービスのURLを取得
SERVICE_URL=$(aws apprunner describe-service \
  --service-arn <サービスARN> \
  --query "Service.ServiceUrl" \
  --output text)

# ヘルスチェック
curl -s "https://$SERVICE_URL/api/health" | python -m json.tool
```

✅ **確認ポイント**:
- ステータスコードが `200` であること
- ヘルスチェック結果が `"status": "healthy"` を含むこと

### 環境変数設定

App Runnerサービスの環境変数は、Terraform設定（`app-runner.tf`）で以下のように定義されています：

| 環境変数 | 値 | 説明 |
|---------|-----|------|
| `LLM_PROVIDER` | `AWS` | Bedrock使用を指定 |
| `OCR_PROVIDER` | `AWS` | Textract使用を指定 |
| `AWS_REGION_NAME` | `ap-northeast-1` | 東京リージョン |
| `DEBUG` | `false` | デバッグモード |
| `PORT` | `8000` | FastAPIリスンポート |

---

## 6. Amazon Bedrock

### Bedrockとは

**Amazon Bedrock** は、AWSが提供するマネージドAI基盤モデルサービスです。
API呼び出しだけでClaude、Titan、Mistralなどの大規模言語モデル（LLM）を利用できます。

**Bedrockの利点**:
- サーバー管理不要（API呼び出しのみ）
- IAMによるアクセス制御
- VPCエンドポイントによるプライベートアクセス
- 入出力データがモデルの学習に使われない（プライバシー保護）

### モデルアクセス申請

Bedrockのモデルを使用するには、事前にアクセス申請が必要です。

1. AWS Management Console にログイン
2. リージョンが **ap-northeast-1（東京）** であることを確認
3. 検索バーに「Bedrock」と入力し、Amazon Bedrockを開く
4. 左メニューの「Model access（モデルアクセス）」をクリック
5. 「Manage model access（モデルアクセスを管理）」をクリック
6. **Anthropic** セクションを見つけ、以下のモデルにチェック：
   - `Claude Haiku 4.5`（高速・低コスト）
   - `Claude Sonnet 4.5`（推奨・バランス型）
   - `Claude Opus 4.5`（高精度）
   - `Claude Opus 4.6`（最新・最高性能）
7. 「Request model access（モデルアクセスをリクエスト）」をクリック
8. 利用規約に同意

⚠️ **承認待ち時間**: 通常は数分〜数時間で承認されますが、最大1営業日かかる場合があります。
ステータスが「Access granted」になるまで待ってください。

💡 **リージョンに注意**: モデルの利用可能性はリージョンによって異なります。
東京リージョン（ap-northeast-1）では、日本リージョン推論プロファイル（`jp.*`）が利用できます。

### 本プロジェクトで利用可能なモデル一覧

| モデルID | 説明 | 用途 |
|---------|------|------|
| `jp.anthropic.claude-sonnet-4-5-20250929-v1:0` | Claude Sonnet 4.5 (JP) | **推奨**: デフォルトモデル |
| `global.anthropic.claude-opus-4-6-v1` | Claude Opus 4.6 | ハイエンド: 最高精度 |
| `global.anthropic.claude-opus-4-5-20251101-v1:0` | Claude Opus 4.5 | 高精度モデル |
| `global.anthropic.claude-haiku-4-5-v1` | Claude Haiku 4.5 | コスト重視: 高速・低コスト |
| `global.anthropic.claude-haiku-4-5-v1` | Claude Haiku 4.5 | 高速・低コスト |

💡 **推論プロファイルIDについて**: `jp.*` や `global.*` で始まるIDは推論プロファイルIDです。
On-demandスループットでは、モデルIDではなく推論プロファイルIDを使用する必要があります。

### Python boto3でのAPI呼び出しテスト

Bedrockのモデルアクセスが承認されたら、Pythonから呼び出しをテストします。

```bash
# boto3がインストールされていることを確認
pip install boto3
```

```python
# bedrock_test.py - Bedrock接続テスト
import boto3
import json

# Bedrockランタイムクライアントを作成
bedrock = boto3.client(
    service_name='bedrock-runtime',
    region_name='ap-northeast-1'
)

# Claude Sonnet 4.5にリクエスト
response = bedrock.invoke_model(
    modelId='jp.anthropic.claude-sonnet-4-5-20250929-v1:0',
    contentType='application/json',
    accept='application/json',
    body=json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 256,
        "messages": [
            {
                "role": "user",
                "content": "内部統制テストとは何ですか？50文字以内で回答してください。"
            }
        ]
    })
)

# レスポンスを表示
result = json.loads(response['body'].read())
print("応答:", result['content'][0]['text'])
print("使用トークン:", result['usage'])
```

```bash
python bedrock_test.py
```

期待される出力：
```
応答: 内部統制テストは、企業の内部統制の有効性を検証する評価手続きです。
使用トークン: {'input_tokens': 32, 'output_tokens': 28}
```

✅ **確認ポイント**:
- エラーなく応答が返ること
- `usage` にトークン使用量が表示されること

### 🔧 よくあるエラー

| エラー | 原因 | 解決方法 |
|--------|------|----------|
| `AccessDeniedException` | モデルアクセスが未承認 | Bedrockコンソールでアクセス状態を確認 |
| `ResourceNotFoundException` | モデルIDが間違い | 正しい推論プロファイルIDを使用 |
| `ThrottlingException` | リクエスト制限超過 | リトライ間隔を空ける |
| `ValidationException` | リクエストフォーマット不正 | anthropic_versionを確認 |

### 環境変数設定（本プロジェクト用）

本プロジェクトでBedrockを使用するには、以下の環境変数を設定します：

```bash
# .envファイルに記載
LLM_PROVIDER=AWS
AWS_REGION=ap-northeast-1

# オプション: モデルIDを変更する場合
AWS_BEDROCK_MODEL_ID=jp.anthropic.claude-sonnet-4-5-20250929-v1:0
```

### トークン使用量とコスト

| モデル | 入力コスト (1Kトークン) | 出力コスト (1Kトークン) |
|--------|------------------------|------------------------|
| Claude Haiku 4.5 | $0.0008 | $0.004 |
| Claude Sonnet 4.5 | $0.003 | $0.015 |
| Claude Opus 4.6 | $0.015 | $0.075 |

💡 **1000トークンは約750単語**（英語）、日本語では約500〜600文字程度です。
内部統制テスト1件あたりの処理コストは、Claude Sonnet 4.5で約$0.01〜$0.05です。

---

## 7. Amazon Textract

### Textractとは

**Amazon Textract** は、AWSが提供するOCR（光学文字認識）サービスです。
スキャンされた書類やPDFから、テキスト、表、フォームデータを自動的に抽出します。

本プロジェクトでは、内部統制テストの証拠書類（紙のスキャン等）からテキストを抽出するために使用します。

### 使用可能な分析タイプ

| API | 機能 | 本プロジェクトでの使用 |
|-----|------|---------------------|
| `DetectDocumentText` | テキスト抽出（行・単語） | ✅ 使用 |
| `AnalyzeDocument` | テキスト + 表 + フォーム | ✅ 使用 |
| `AnalyzeExpense` | 領収書・請求書の解析 | 対象外 |
| `AnalyzeID` | 身分証明書の解析 | 対象外 |

### Python boto3での呼び出しテスト

```python
# textract_test.py - Textract接続テスト
import boto3

# Textractクライアントを作成
textract = boto3.client(
    service_name='textract',
    region_name='ap-northeast-1'
)

# テスト画像ファイルを読み込み（JPEG/PNG/PDF対応）
with open('test_document.png', 'rb') as f:
    document_bytes = f.read()

# テキスト抽出
response = textract.detect_document_text(
    Document={'Bytes': document_bytes}
)

# 結果を表示
for block in response['Blocks']:
    if block['BlockType'] == 'LINE':
        print(f"  テキスト: {block['Text']}")
        print(f"  信頼度: {block['Confidence']:.1f}%")
        print()
```

```bash
python textract_test.py
```

期待される出力：
```
  テキスト: 内部統制テスト結果報告書
  信頼度: 99.8%

  テキスト: 承認日: 2026年1月15日
  信頼度: 98.5%
```

### 対応ドキュメント形式

| 形式 | DetectDocumentText | AnalyzeDocument |
|------|-------------------|-----------------|
| JPEG | ✅ | ✅ |
| PNG | ✅ | ✅ |
| PDF（1ページ） | ✅ | ✅ |
| PDF（複数ページ） | 非同期APIが必要 | 非同期APIが必要 |
| TIFF | ✅ | ✅ |

⚠️ **ファイルサイズ制限**: 同期APIの場合、ドキュメントサイズは最大10MBです。
それ以上の場合は、S3にアップロードして非同期APIを使用してください。

✅ **確認ポイント**: Textractがテキストを正しく抽出できることを確認してください。
日本語の認識精度は英語に比べて若干低い場合があります。
高精度な日本語OCRが必要な場合は、YomiToku等の専用サービスの利用も検討してください。

---

## 8. API Gateway

### API Gatewayとは

**Amazon API Gateway** は、REST/HTTP APIを作成・公開・管理するためのサービスです。
外部からのHTTPリクエストを受け取り、App Runnerサービスに転送する「入り口」の役割を果たします。

```
クライアント → [API Gateway] → [App Runner] → [Bedrock/Textract]
  (VBA/        (認証・制限)   (コンテナ)     (AI/OCR)
   PowerShell)
```

| 種類 | 特徴 | 本プロジェクト |
|------|------|--------------|
| REST API | 機能豊富（API Key、Usage Plan、WAF統合） | ✅ 使用 |
| HTTP API | シンプル・低コスト・高速 | 不使用 |
| WebSocket API | リアルタイム双方向通信 | 不使用 |

### 本プロジェクトのAPI構成

| エンドポイント | メソッド | 説明 | API Key |
|---------------|---------|------|---------|
| `/evaluate` | POST | 内部統制テスト評価（同期） | 必要 |
| `/evaluate/submit` | POST | 評価ジョブ投入（非同期） | 必要 |
| `/evaluate/status/{job_id}` | GET | ジョブ状態確認 | 必要 |
| `/evaluate/results/{job_id}` | GET | 評価結果取得 | 必要 |
| `/health` | GET | ヘルスチェック | 不要 |
| `/config` | GET | 設定情報取得 | 不要 |

### REST APIの手動作成

⚠️ **Terraformを使う場合は不要**: 後述のTerraformデプロイではAPI Gatewayが自動作成されます。
以下は学習目的の手動手順です。

```bash
# REST APIを作成
aws apigateway create-rest-api \
  --name "ic-test-ai-prod-api" \
  --description "内部統制テスト評価AI API Gateway" \
  --endpoint-configuration '{"types":["REGIONAL"]}'
```

期待される出力：
```json
{
    "id": "abc123def4",  # pragma: allowlist secret
    "name": "ic-test-ai-prod-api",
    "description": "内部統制テスト評価AI API Gateway",
    ...
}
```

💡 **REGIONAL vs EDGE**: REGIONALエンドポイントは特定リージョンにデプロイされます。
日本国内のユーザーが主な場合はREGIONALが適切です。
EDGEはCloudFrontを使ったグローバル配信で、世界中からのアクセスに適しています。

### リソースとメソッド定義

```bash
# REST API IDを変数に格納
API_ID="abc123def4"  # 作成時に返されたID

# ルートリソースIDを取得
ROOT_ID=$(aws apigateway get-resources \
  --rest-api-id $API_ID \
  --query "items[?path=='/'].id" \
  --output text)

# /evaluate リソースを作成
aws apigateway create-resource \
  --rest-api-id $API_ID \
  --parent-id $ROOT_ID \
  --path-part "evaluate"
```

### App Runner統合設定

```bash
# /evaluate リソースIDを取得
EVAL_ID=$(aws apigateway get-resources \
  --rest-api-id $API_ID \
  --query "items[?path=='/evaluate'].id" \
  --output text)

# POSTメソッドを作成（API Key必須）
aws apigateway put-method \
  --rest-api-id $API_ID \
  --resource-id $EVAL_ID \
  --http-method POST \
  --authorization-type NONE \
  --api-key-required

# App Runnerへの HTTP統合を設定
SERVICE_URL="https://xxxxxxxx.ap-northeast-1.awsapprunner.com"
aws apigateway put-integration \
  --rest-api-id $API_ID \
  --resource-id $EVAL_ID \
  --http-method POST \
  --type HTTP_PROXY \
  --integration-http-method POST \
  --uri "$SERVICE_URL/api/evaluate"
```

💡 **HTTPプロキシ統合（HTTP_PROXY）とは**: API Gatewayが受け取ったHTTPリクエスト全体を
そのままバックエンド（App Runner）に転送する方式です。App Runner側でリクエストの処理を行います。
設定がシンプルで、コンテナベースのバックエンドに適しています。

### ステージ作成とデプロイ

```bash
# デプロイを作成
aws apigateway create-deployment \
  --rest-api-id $API_ID \
  --stage-name prod \
  --description "本番環境デプロイ"
```

デプロイ後のエンドポイントURL：
```
https://{API_ID}.execute-api.ap-northeast-1.amazonaws.com/prod/evaluate
```

### API Key作成とUsage Plan

API Keyは、APIへのアクセスを認証するための文字列です。
Usage Planは、API Keyごとにリクエスト数の制限を設定します。

```bash
# API Keyを作成
aws apigateway create-api-key \
  --name "ic-test-ai-prod-api-key" \
  --description "内部統制テスト評価AI APIキー" \
  --enabled

# Usage Planを作成
aws apigateway create-usage-plan \
  --name "ic-test-ai-prod-usage-plan" \
  --description "内部統制テスト評価AI Usage Plan" \
  --api-stages '[{"apiId":"'$API_ID'","stage":"prod"}]' \
  --quota '{"limit":10000,"period":"MONTH"}' \
  --throttle '{"burstLimit":100,"rateLimit":50}'
```

💡 **Usage Planの設定値**:
- `quota.limit=10000`: 月間最大10,000リクエスト
- `throttle.burstLimit=100`: バースト時最大100リクエスト/秒
- `throttle.rateLimit=50`: 定常時最大50リクエスト/秒

### テスト呼び出し

```bash
# API KeyとエンドポイントURLを設定
API_KEY="your-api-key-here"  # pragma: allowlist secret
API_URL="https://{API_ID}.execute-api.ap-northeast-1.amazonaws.com/prod"

# ヘルスチェック（API Key不要）
curl -s "$API_URL/health" | python -m json.tool

# 評価リクエスト（API Key必要）
curl -s -X POST "$API_URL/evaluate" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -H "X-Correlation-ID: test-$(date +%s)" \
  -d '{
    "test_type": "walkthrough",
    "control_description": "承認プロセスの整備状況テスト",
    "evidence": "承認ワークフローの設定画面スクリーンショット"
  }' | python -m json.tool
```

✅ **確認ポイント**:
- ヘルスチェックが `200 OK` を返すこと
- API Key付きリクエストが正常に処理されること
- API KeyなしのPOSTリクエストが `403 Forbidden` を返すこと

---

## 9. Secrets Manager

### Secrets Managerとは

**AWS Secrets Manager** は、APIキー、データベースパスワード、その他の機密情報を安全に保存・管理するサービスです。

**なぜSecrets Managerを使うのか**:
- コードに直接APIキーを書くのはセキュリティリスク
- 環境変数は設定ミスで漏洩しやすい
- Secrets Managerは暗号化・アクセス制御・監査ログを提供
- 自動ローテーション（定期的なキー更新）に対応

### シークレット作成

本プロジェクトでは、Terraformによって以下のシークレットが自動作成されます。

```bash
# Bedrock API Key（IAMロール認証を使用する場合は不要）
aws secretsmanager create-secret \
  --name "ic-test-ai-prod-bedrock-api-key" \
  --description "AWS Bedrock API Key for LLM operations" \
  --secret-string "REPLACE_WITH_ACTUAL_API_KEY" \
  --region ap-northeast-1

# Textract API Key（IAMロール認証を使用する場合は不要）
aws secretsmanager create-secret \
  --name "ic-test-ai-prod-textract-api-key" \
  --description "AWS Textract API Key for OCR operations" \
  --secret-string "REPLACE_WITH_ACTUAL_API_KEY" \
  --region ap-northeast-1

# OpenAI API Key（フォールバック用・オプション）
aws secretsmanager create-secret \
  --name "ic-test-ai-prod-openai-api-key" \
  --description "OpenAI API Key (fallback)" \
  --secret-string "NOT_CONFIGURED" \
  --region ap-northeast-1
```

💡 **Bedrock/Textractの認証について**: App RunnerサービスはIAMインスタンスロールによってBedrock/Textractにアクセスします。
そのため、API Keyをシークレットに保存する必要は通常ありません。
Secrets Managerは主に、外部サービス（OpenAI等）のAPIキー管理に使用します。

### シークレットの値を更新

```bash
# シークレットの値を更新
aws secretsmanager put-secret-value \
  --secret-id "ic-test-ai-prod-bedrock-api-key" \
  --secret-string "実際のAPIキー値"
```

### Python boto3でのアクセス

```python
# secrets_test.py - Secrets Manager接続テスト
import boto3
import json

# Secrets Managerクライアントを作成
client = boto3.client(
    service_name='secretsmanager',
    region_name='ap-northeast-1'
)

# シークレットを取得
response = client.get_secret_value(
    SecretId='ic-test-ai-prod-bedrock-api-key'  # pragma: allowlist secret
)

# 値を表示（本番では絶対にログ出力しないこと）
secret = response['SecretString']
print(f"シークレット取得成功: {secret[:10]}...")
```

### App Runnerサービスからのアクセス設定

App RunnerサービスからSecrets Managerにアクセスするには、IAMポリシーが必要です。
本プロジェクトのTerraformでは、`apprunner_secrets_read` ポリシーが自動作成され、
以下の権限がApp Runnerインスタンスロールに付与されます：

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": [
        "arn:aws:secretsmanager:ap-northeast-1:123456789012:secret:ic-test-ai-prod-bedrock-api-key-*",
        "arn:aws:secretsmanager:ap-northeast-1:123456789012:secret:ic-test-ai-prod-textract-api-key-*",
        "arn:aws:secretsmanager:ap-northeast-1:123456789012:secret:ic-test-ai-prod-openai-api-key-*"
      ]
    }
  ]
}
```

⚠️ **最小権限**: `Resource` に具体的なシークレットARNを指定することで、
App Runnerサービスがアクセスできるシークレットを限定しています。`"Resource": "*"` は避けてください。

### 登録すべきシークレット一覧

| シークレット名 | 必須 | 説明 |
|---------------|------|------|
| `ic-test-ai-prod-bedrock-api-key` | いいえ（IAMロール使用時） | Bedrock API Key |
| `ic-test-ai-prod-textract-api-key` | いいえ（IAMロール使用時） | Textract API Key |
| `ic-test-ai-prod-openai-api-key` | いいえ | OpenAI APIキー（フォールバック用） |

✅ **確認ポイント**: 以下のコマンドでシークレットが作成されていることを確認します。

```bash
aws secretsmanager list-secrets \
  --filter Key="name",Values="ic-test-ai" \
  --query "SecretList[].Name" \
  --output table
```

---

## 10. CloudWatch / X-Ray

### CloudWatchとは

**Amazon CloudWatch** は、AWSリソースの監視サービスです。
3つの主要機能があります：

| 機能 | 説明 |
|------|------|
| **CloudWatch Logs** | アプリケーションログの収集・保存・検索 |
| **CloudWatch Metrics** | メトリクス（数値データ）の収集・グラフ表示 |
| **CloudWatch Alarms** | メトリクスが閾値を超えた場合に通知 |

### 本プロジェクトのCloudWatch設定

Terraformで以下のリソースが自動作成されます：

**ロググループ**:
- `/aws/apprunner/ic-test-ai-prod` - App Runnerサービスログ（保持期間: 30日）
- `/aws/apigateway/ic-test-ai-prod-api` - API Gatewayアクセスログ（保持期間: 30日）

**アラーム**:
| アラーム名 | 監視対象 | 閾値 |
|-----------|---------|------|
| `apprunner-errors` | App Runnerエラー数 | 5分間で10回以上 |
| `apprunner-5xx` | App Runner 5xxエラー | 5分間で5回以上 |
| `apprunner-latency` | App Runnerレスポンスタイム | 平均3分以上 |
| `api-gateway-4xx` | API 4xxエラー | 5分間で20回以上 |
| `api-gateway-5xx` | API 5xxエラー | 5分間で5回以上 |

**ダッシュボード**:
`ic-test-ai-prod-dashboard` にApp RunnerとAPI Gatewayのメトリクスが一覧表示されます。

### X-Rayとは

**AWS X-Ray** は、分散トレーシング（リクエストの経路追跡）サービスです。
APIリクエストがどのサービスを経由し、各ステップで何秒かかったかを可視化します。

```
リクエスト → API Gateway (50ms) → App Runner (2500ms) → Bedrock (2000ms)
                                                      → Textract (800ms)
```

X-Rayを使うと：
- **ボトルネック特定**: どのステップが遅いかが一目で分かる
- **エラー追跡**: どのステップでエラーが発生したか特定できる
- **サービスマップ**: サービス間の依存関係を可視化

### App RunnerのX-Ray有効化

Terraformでは App Runner の observability configuration で自動有効化されます。
手動で有効化する場合：

```bash
aws apprunner update-service \
  --service-arn <サービスARN> \
  --observability-configuration '{
    "ObservabilityEnabled": true,
    "ObservabilityConfigurationArn": "<X-Ray設定ARN>"
  }'
```

期待されるステータス：
```json
{
    "Service": {
        "Status": "OPERATION_IN_PROGRESS"
    }
}
```

### CloudWatch Logsクエリ例

CloudWatch Logs Insightsを使って、ログを検索・分析できます。

```bash
# AWS CLIからCloudWatch Logs Insightsクエリを実行
aws logs start-query \
  --log-group-name "/aws/apprunner/ic-test-ai-prod" \
  --start-time $(date -d '1 hour ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc | limit 20'
```

よく使うクエリパターン：

```
# エラーログの検索
fields @timestamp, @message
| filter @message like /ERROR/
| sort @timestamp desc
| limit 20

# 相関IDによるリクエスト追跡
fields @timestamp, @message, correlation_id
| filter correlation_id like /your-correlation-id-here/
| sort @timestamp asc

# リクエスト処理時間の統計
stats avg(duration), max(duration), min(duration), count(*) as requests
by bin(5m) as time_window

# コンテナ起動ログの検出
fields @timestamp, @message
| filter @message like /Starting/
| sort @timestamp desc
```

💡 **コンソールからの確認方法**:
1. AWS Console → CloudWatch → Log Insights
2. ロググループで `/aws/apprunner/ic-test-ai-prod` を選択
3. 上記クエリをコピー&ペーストして「Run query」

### X-Rayサービスマップの見方

1. AWS Console → X-Ray → Service map
2. 時間範囲を選択（過去1時間など）
3. サービスマップが表示される

サービスマップの読み方：
- **ノード**: 各サービス（API Gateway、App Runner、Bedrock等）
- **エッジ**: サービス間のリクエストフロー
- **色**: 緑=正常、黄=4xxエラー、赤=5xxエラー
- **レイテンシ**: 各ノードの平均応答時間

✅ **確認ポイント**:
```bash
# Terraform出力からダッシュボードURLを取得
# (Terraformデプロイ後に使用)
terraform output cloudwatch_dashboard_url
terraform output xray_service_map_url
```

---

## 11. S3

### S3とは

**Amazon S3（Simple Storage Service）** は、AWSのオブジェクトストレージサービスです。
ファイル（オブジェクト）を安全に保存・取得できます。

基本概念：
- **バケット**: ファイルを入れる「箱」（グローバルでユニークな名前が必要）
- **オブジェクト**: バケット内のファイル
- **キー**: オブジェクトの識別名（ファイルパスに相当）

本プロジェクトでは、証跡ファイルやジョブ結果の保存にS3を使用します。

### バケット作成

```bash
# S3バケットを作成（東京リージョン）
# バケット名はグローバルでユニークである必要があります
aws s3api create-bucket \
  --bucket ic-test-ai-prod-lambda-deployments-123456789012 \
  --region ap-northeast-1 \
  --create-bucket-configuration LocationConstraint=ap-northeast-1
```

💡 **バケット名のルール**:
- グローバルでユニーク（他のAWSアカウントと重複不可）
- 3〜63文字
- 小文字、数字、ハイフンのみ使用可能
- 本プロジェクトでは末尾にAWSアカウントIDを付けてユニーク性を確保しています

```bash
# バージョニングを有効化（誤削除防止）
aws s3api put-bucket-versioning \
  --bucket ic-test-ai-prod-lambda-deployments-123456789012 \
  --versioning-configuration Status=Enabled
```

### Python boto3でのアクセス

```python
# s3_test.py - S3接続テスト
import boto3

s3 = boto3.client('s3', region_name='ap-northeast-1')

# バケット内のオブジェクト一覧
response = s3.list_objects_v2(
    Bucket='ic-test-ai-prod-lambda-deployments-123456789012',
    MaxKeys=10
)

for obj in response.get('Contents', []):
    print(f"  {obj['Key']} ({obj['Size']:,} bytes)")
```

✅ **確認ポイント**: バケットが作成され、デプロイパッケージがアップロードできることを確認。

```bash
# テストファイルをアップロード
echo "test" > /tmp/test.txt
aws s3 cp /tmp/test.txt s3://ic-test-ai-prod-lambda-deployments-123456789012/test.txt

# アップロード確認
aws s3 ls s3://ic-test-ai-prod-lambda-deployments-123456789012/

# テストファイルを削除
aws s3 rm s3://ic-test-ai-prod-lambda-deployments-123456789012/test.txt
```

---

## 12. Terraformデプロイ

### IaCとTerraformの概要

**IaC（Infrastructure as Code）** とは、インフラ構成をコードとして管理する手法です。
手動でAWSコンソールを操作する代わりに、コードを書いてインフラを定義・構築します。

**Terraformの利点**:
- **再現性**: 同じコードから同じ環境を何度でも作成できる
- **バージョン管理**: Gitでインフラの変更履歴を追跡できる
- **自動化**: コマンド1つで全リソースを一括作成/削除できる
- **マルチクラウド**: AWS、Azure、GCPを同じツールで管理できる

### Terraformインストール

#### Windows の場合

```bash
# Chocolateyを使う場合
choco install terraform

# または手動ダウンロード
# https://developer.hashicorp.com/terraform/downloads

# インストール確認
terraform --version
```

期待される出力：
```
Terraform v1.x.x
on windows_amd64
```

#### macOS の場合

```bash
brew install terraform
terraform --version
```

#### Linux の場合

```bash
# HashiCorp GPGキーを追加
wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg

# リポジトリを追加
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list

# インストール
sudo apt update && sudo apt install terraform
terraform --version
```

### 本プロジェクトのTerraformファイル構成

```
infrastructure/aws/terraform/
├── backend.tf          # Terraformバックエンド設定（State管理）
├── variables.tf        # 変数定義（プロジェクト名、リージョン等）
├── app-runner.tf       # App Runnerサービス + IAMロール + ECR
├── api-gateway.tf      # API Gateway + API Key + Usage Plan
├── secrets-manager.tf  # Secrets Manager + IAMポリシー
├── cloudwatch.tf       # CloudWatch Alarms + Dashboard + X-Ray
└── outputs.tf          # 出力値定義（URL、ARN等）
```

各ファイルの役割：

| ファイル | 作成されるリソース |
|---------|-------------------|
| `backend.tf` | Terraform設定（プロバイダーバージョン、State保存先） |
| `variables.tf` | 設定パラメータ定義（デフォルト値含む） |
| `app-runner.tf` | App Runnerサービス、IAMロール、ECR、CloudWatch Logs |
| `api-gateway.tf` | REST API、リソース、メソッド、ステージ、API Key |
| `secrets-manager.tf` | シークレット3種 + App Runner読み取りポリシー |
| `cloudwatch.tf` | アラーム5種 + ダッシュボード + X-Rayサンプリングルール |
| `outputs.tf` | デプロイ後の重要情報（URL、ARN等） |

### terraform init（初期化）

Terraformの初期化を行います。プロバイダープラグインのダウンロードが行われます。

```bash
cd infrastructure/aws/terraform
terraform init
```

期待される出力：
```
Initializing the backend...

Initializing provider plugins...
- Finding hashicorp/aws versions matching "~> 5.0"...
- Installing hashicorp/aws v5.x.x...
- Installed hashicorp/aws v5.x.x (signed by HashiCorp)

Terraform has been successfully initialized!
```

💡 **`terraform init` は以下のタイミングで実行します**:
- 初回セットアップ時
- `backend.tf` を変更した時
- 新しいプロバイダーを追加した時

### terraform plan（実行計画の確認）

実際にリソースを作成する前に、何が作成されるかを確認します。

```bash
# 変数を設定（環境変数またはterraform.tfvars）
export TF_VAR_project_name="ic-test-ai"
export TF_VAR_environment="prod"
export TF_VAR_region="ap-northeast-1"

# 実行計画を表示
terraform plan -out=tfplan
```

期待される出力（一部）：
```
Terraform used the selected providers to generate the following execution plan.

  # aws_api_gateway_api_key.ic_test_ai will be created
  + resource "aws_api_gateway_api_key" "ic_test_ai" {
      + name    = "ic-test-ai-prod-api-key"
      + enabled = true
      ...
    }

  # aws_apprunner_service.ic_test_ai will be created
  + resource "aws_apprunner_service" "ic_test_ai" {
      + service_name = "ic-test-ai-prod"
      + status       = "RUNNING"
      ...
    }

Plan: 25 to add, 0 to change, 0 to destroy.
```

⚠️ **必ず `plan` の出力を確認してください**: 予期しないリソースの削除（destroy）がないことを確認します。
特に `to destroy` のカウントが0であることが重要です。

### terraform apply（リソース作成）

```bash
# 確認済みのプランを適用
terraform apply tfplan
```

途中でプランなしで直接適用する場合：
```bash
terraform apply
```

「Do you want to perform these actions?」と確認されるので `yes` と入力します。

期待される出力（完了後）：
```
Apply complete! Resources: 25 added, 0 changed, 0 destroyed.

Outputs:

api_gateway_endpoint = "https://abc123def4.execute-api.ap-northeast-1.amazonaws.com/prod/evaluate"
api_key = <sensitive>
cloudwatch_dashboard_url = "https://console.aws.amazon.com/cloudwatch/..."
apprunner_service_url = "https://xxxxxxxx.ap-northeast-1.awsapprunner.com"
xray_service_map_url = "https://console.aws.amazon.com/xray/..."
```

### 出力値の確認

```bash
# 全出力値を表示
terraform output

# API Keyを表示（sensitive値）
terraform output -raw api_key

# エンドポイントURLを表示
terraform output api_gateway_endpoint
```

重要な出力値：

| 出力名 | 用途 |
|--------|------|
| `api_gateway_endpoint` | VBA/PowerShellに設定するAPIエンドポイント |
| `api_key` | VBA/PowerShellに設定するAPI Key |
| `apprunner_service_url` | App RunnerサービスのURL |
| `ecr_repository_url` | Dockerイメージのプッシュ先 |
| `cloudwatch_dashboard_url` | 監視ダッシュボードのURL |

### Terraform State管理（S3バックエンド）

⚠️ **チーム開発時は必須**: デフォルトではTerraform StateがローカルPCに保存されます。
チームで開発する場合は、S3にStateを保存して共有します。

```bash
# State保存用S3バケットを作成
aws s3api create-bucket \
  --bucket ic-test-ai-terraform-state \
  --region ap-northeast-1 \
  --create-bucket-configuration LocationConstraint=ap-northeast-1

# バージョニングを有効化
aws s3api put-bucket-versioning \
  --bucket ic-test-ai-terraform-state \
  --versioning-configuration Status=Enabled

# State ロック用DynamoDBテーブルを作成
aws dynamodb create-table \
  --table-name ic-test-ai-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --provisioned-throughput ReadCapacityUnits=1,WriteCapacityUnits=1 \
  --region ap-northeast-1
```

その後、`backend.tf` のS3バックエンド設定のコメントを外して `terraform init -reconfigure` を実行します。

### terraform destroy（クリーンアップ）

全リソースを削除する場合：

```bash
terraform destroy
```

⚠️ **注意**: `terraform destroy` は作成した全リソースを削除します。
本番環境では実行しないでください。確認プロンプトで `yes` を入力すると削除が開始されます。

💡 **一部のリソースだけを削除する場合**:
```bash
# 特定のリソースだけを削除
terraform destroy -target=aws_cloudwatch_metric_alarm.lambda_errors
```

---

## 13. 統合テスト

### ヘルスチェック

デプロイが完了したら、まずヘルスチェックでシステムの状態を確認します。

```bash
# Terraform出力からエンドポイントを取得
API_URL=$(terraform output -raw api_gateway_endpoint | sed 's|/evaluate||')
API_KEY=$(terraform output -raw api_key)

# ヘルスチェック
curl -s "$API_URL/health" | python -m json.tool
```

期待される出力：
```json
{
    "status": "healthy",
    "platform": "aws",
    "llm_provider": "AWS",
    "ocr_provider": "AWS",
    "timestamp": "2026-02-11T10:00:00Z"
}
```

### /evaluate テスト

```bash
# 同期評価リクエスト
curl -s -X POST "$API_URL/evaluate" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -H "X-Correlation-ID: integration-test-001" \
  -d '{
    "test_type": "walkthrough",
    "control_description": "購買承認プロセスにおける承認権限の適切な設定を確認する",
    "evidence": "承認権限マトリックス、ワークフロー設定画面のスクリーンショット、テスト期間中の承認ログ10件",
    "assertion": "全ての購買申請が適切な権限者により承認されている"
  }' | python -m json.tool
```

期待される出力（一部）：
```json
{
    "correlation_id": "integration-test-001",
    "evaluation_result": {
        "test_type": "walkthrough",
        "effectiveness": "effective",
        "confidence_score": 0.85,
        "findings": [...],
        "recommendations": [...]
    }
}
```

### 相関ID伝播確認

相関ID（Correlation ID）は、1つのリクエストが複数サービスを通過する際に、
そのリクエストを追跡するための一意のIDです。

```bash
# 一意の相関IDを生成
CORR_ID="trace-$(date +%s)-$(openssl rand -hex 4)"
echo "相関ID: $CORR_ID"

# 相関ID付きリクエストを送信
curl -s -X POST "$API_URL/evaluate" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -H "X-Correlation-ID: $CORR_ID" \
  -d '{"test_type": "walkthrough", "control_description": "テスト"}' \
  | python -m json.tool

# CloudWatch Logsで相関IDを検索
aws logs start-query \
  --log-group-name "/aws/apprunner/ic-test-ai-prod" \
  --start-time $(date -d '10 minutes ago' +%s) \
  --end-time $(date +%s) \
  --query-string "fields @timestamp, @message | filter @message like /$CORR_ID/ | sort @timestamp asc"
```

✅ **確認ポイント**:
- レスポンスに同じ `correlation_id` が含まれていること
- CloudWatch Logsで相関IDを含むログエントリが見つかること
- X-Rayトレースにも相関IDがアノテーションとして記録されていること

### CloudWatchでログ確認

```bash
# App Runnerサービスの最新ログを確認
aws logs tail "/aws/apprunner/ic-test-ai-prod" \
  --since 10m \
  --format short
```

💡 **ブラウザでの確認**: Terraform出力の `cloudwatch_logs_url` をブラウザで開くと、
CloudWatch Logsコンソールで直接ログを確認できます。

### 🔧 統合テストのトラブルシューティング

| 問題 | 確認ポイント | 解決方法 |
|------|------------|----------|
| 502 Bad Gateway | App Runnerコンテナエラー | コンテナログを確認、Dockerイメージが正しいか確認 |
| 403 Forbidden | API Key | `x-api-key` ヘッダーの値を確認 |
| 504 Gateway Timeout | App Runner タイムアウト | ヘルスチェック設定とリクエストタイムアウトを確認 |
| Internal Server Error | App Runner実行エラー | CloudWatch Logsを確認 |
| Bedrockアクセスエラー | IAMポリシー | Bedrockポリシーがインスタンスロールにアタッチされているか確認 |

---

## 14. コスト管理

### 無料枠の範囲

AWSの無料枠（12か月間）：

| サービス | 無料枠 |
|---------|--------|
| App Runner | 自動一時停止で未使用時は最小課金 |
| API Gateway | 100万API呼び出し/月（12か月間） |
| CloudWatch | 基本モニタリング無料、ログ5GB/月 |
| S3 | 5GB標準ストレージ |
| Secrets Manager | 30日間無料トライアル |
| X-Ray | 10万トレース/月 |

⚠️ **Bedrockは無料枠なし**: Bedrockのモデル呼び出しは最初から課金されます。
テスト段階ではClaude Haiku 4.5（最安）を使用することを推奨します。

### コスト見積もり（月間100リクエストの場合）

| サービス | 概算コスト |
|---------|-----------|
| App Runner（1 vCPU, 2GB, 低トラフィック） | ~$5.00 |
| API Gateway（100リクエスト） | ~$0.001 |
| Bedrock - Claude Sonnet 4.5（100回） | ~$1.00〜$5.00 |
| Bedrock - Claude Haiku 4.5（100回） | ~$0.10〜$0.30 |
| CloudWatch Logs | ~$0.50 |
| Secrets Manager（3シークレット） | ~$1.20 |
| S3 | ~$0.01 |
| **合計（Sonnet 4.5使用時）** | **~$8〜$12/月** |
| **合計（Haiku 4.5使用時）** | **~$7〜$8/月** |

💡 **コスト最適化のヒント**:

- 開発・テスト段階ではClaude Haiku 4.5 を使用
- 不要なCloudWatch Logsは保持期間を短縮（30日→7日）
- 使わなくなった環境は `terraform destroy` で削除

### Billing Dashboardの確認

```bash
# 現在の月間コストを確認（Cost Explorer API）
aws ce get-cost-and-usage \
  --time-period Start=2026-02-01,End=2026-02-28 \
  --granularity MONTHLY \
  --metrics "BlendedCost" \
  --group-by Type=DIMENSION,Key=SERVICE
```

⚠️ **コストアラートの設定を推奨**: 予期しない課金を防ぐため、
AWS Budgets でアラートを設定してください。

1. AWS Console → Billing → Budgets
2. 「Create a budget」をクリック
3. 月間予算を設定（例: $10）
4. 予算の80%に達したらメール通知

本プロジェクトのTerraformでは、`cost_alert_threshold` 変数（デフォルト: $100/月）で
コストアラームが設定されています。

---

## 15. まとめ・次のステップ

### セットアップ完了チェックリスト

- [ ] AWSアカウントを作成した
- [ ] AWS CLIをインストールし、`aws configure`を完了した
- [ ] `aws sts get-caller-identity` が正常に動作する
- [ ] Bedrockモデルアクセスが「Access granted」になった
- [ ] Terraformをインストールした
- [ ] `terraform init` / `plan` / `apply` が成功した
- [ ] ヘルスチェック（`/health`）が `200 OK` を返す
- [ ] `/evaluate` エンドポイントが正しく応答する
- [ ] CloudWatch Logsにログが記録されている
- [ ] X-Rayサービスマップにトレースが表示される
- [ ] コストアラートを設定した

### 重要な出力値の保存

以下の値をVBA/PowerShellクライアントに設定してください：

```bash
# エンドポイントURL
terraform output api_gateway_endpoint

# API Key
terraform output -raw api_key
```

### 次のステップ

1. **VBA/PowerShellクライアントの設定**: エンドポイントURLとAPI Keyを設定
2. **運用ドキュメントの確認**: [DEPLOYMENT_GUIDE.md](../operations/DEPLOYMENT_GUIDE.md)
3. **CI/CDパイプラインの構築**: GitHub Actionsとの連携
4. **本番環境のセキュリティ強化**: WAF、VPCエンドポイント、IAMポリシーの絞り込み
5. **マルチ環境（dev/stg/prod）の構築**: Terraform workspaces の活用

### 参考資料

- [AWS公式ドキュメント](https://docs.aws.amazon.com/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/)
- [Amazon Bedrock ドキュメント](https://docs.aws.amazon.com/bedrock/)
- [AWS App Runner ドキュメント](https://docs.aws.amazon.com/apprunner/)
- [API Gateway ドキュメント](https://docs.aws.amazon.com/apigateway/)
- [本プロジェクト Deployment Guide](../operations/DEPLOYMENT_GUIDE.md)
- [本プロジェクト AWS Terraform README](../../infrastructure/aws/README.md)

---

> このドキュメントは内部統制テスト評価AIシステムのAWS環境セットアップガイドです。
> 質問やフィードバックがある場合は、プロジェクトのIssueに報告してください。
