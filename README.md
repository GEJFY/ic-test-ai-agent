# 内部統制テスト評価AIシステム

[![Tests](https://github.com/goyosystems/ic-test-ai-agent/actions/workflows/test.yml/badge.svg)](https://github.com/goyosystems/ic-test-ai-agent/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

企業の内部監査業務を支援するマルチクラウド対応AIツールです。大規模言語モデル(LLM)を活用し、内部統制テストの自動評価を実現します。

## 主要機能

- **Excel統合**: VBAマクロによる自動データ読み込み・結果書き戻し
- **マルチクラウド対応**: Azure AI Foundry、AWS Bedrock、GCP Vertex AIをサポート
- **AI評価**: 8種類の監査タスク（A1-A8）を自動実行
- **証跡ハイライト**: PDF/Excel/テキストのエビデンス該当箇所を自動ハイライト
- **非同期処理**: 大量テスト項目のタイムアウト回避
- **監視統合**: Application Insights、X-Ray、Cloud Loggingによるトレース
- **セキュリティ**: Key Vault/Secrets Manager統合、相関ID追跡

## 対応クラウドプロバイダー

| プロバイダー | LLMモデル | OCRサービス | 環境変数値 |
|-------------|-----------|------------|-----------|
| Azure AI Foundry | GPT-5.2 / GPT-5 Nano | Document Intelligence | `AZURE_FOUNDRY` |
| AWS Bedrock | Claude Opus 4.6 / Sonnet 4.5 | Textract | `AWS` |
| GCP Vertex AI | Gemini 3 Pro | Document AI | `GCP` |
| Azure OpenAI | GPT-5.2 (レガシー) | Document Intelligence | `AZURE` |

## クイックスタート

### 前提条件

- Python 3.11+
- Excel (VBAマクロ対応)
- PowerShell 5.1+
- Azure/AWS/GCPアカウント（いずれか1つ）

### インストール

```bash
# リポジトリをクローン
git clone https://github.com/goyosystems/ic-test-ai-agent.git
cd ic-test-ai-agent

# 依存パッケージをインストール
pip install -r requirements.txt -r requirements-dev.txt

# 環境変数を設定
cp .env.example .env
# .envファイルを編集して、クラウドプロバイダーのAPIキー等を設定

# テストを実行
pytest -v
```

### ローカル実行

```bash
# ローカルサーバーを起動
uvicorn platforms.local.main:app --reload --port 8000

# 別のターミナルで健全性チェック
curl http://localhost:8000/api/health
```

### クラウドデプロイ

各プラットフォームのセットアップガイドを参照してください：

- [前提条件・開発環境セットアップ](docs/setup/PREREQUISITES.md)
- [Azure セットアップガイド](docs/setup/AZURE_SETUP.md)
- [AWS セットアップガイド](docs/setup/AWS_SETUP.md)
- [GCP セットアップガイド](docs/setup/GCP_SETUP.md)
- [クライアント（VBA/PowerShell）セットアップ](docs/setup/CLIENT_SETUP.md)

## 監査タスク (A1-A8)

本システムは8種類の監査タスクをサポートします：

| タスク | 説明 | 技術 |
|--------|------|------|
| A1 | 意味検索 | セマンティックサーチによる文書検索 |
| A2 | 画像認識 | 承認印・署名・日付の抽出（Vision API/OCR） |
| A3 | データ抽出 | 表からの数値抽出と突合 |
| A4 | 段階的推論 | ステップバイステップの計算・検証 |
| A5 | 意味推論 | 意味検索+推論の組み合わせ |
| A6 | 複数文書統合 | 複数ドキュメントの統合理解 |
| A7 | パターン分析 | 時系列データのパターン検出 |
| A8 | SoD検出 | 職務分掌違反の検出 |

## アーキテクチャ

```
VBA/PowerShell → API Gateway (APIM/API Gateway/Apigee)
                     ↓
               Backend (Azure Functions/Lambda/Cloud Functions)
                     ↓
               LLM/OCR APIs (Azure AI/Bedrock/Vertex AI)
                     ↓
               Monitoring (Application Insights/X-Ray/Cloud Logging)
```

詳細は [システムアーキテクチャ](SYSTEM_SPECIFICATION.md) を参照してください。

## ドキュメント

### セットアップガイド

- [前提条件・開発環境](docs/setup/PREREQUISITES.md) - Python、CLI、Git等のインストール
- [Azure セットアップ](docs/setup/AZURE_SETUP.md) - Azure環境構築チュートリアル
- [AWS セットアップ](docs/setup/AWS_SETUP.md) - AWS環境構築チュートリアル
- [GCP セットアップ](docs/setup/GCP_SETUP.md) - GCP環境構築チュートリアル
- [クライアントセットアップ](docs/setup/CLIENT_SETUP.md) - VBA/PowerShellクライアント設定
- [GitHub Secrets設定](docs/setup/GITHUB_SECRETS_SETUP.md) - CI/CD用シークレット設定

### 設計・運用ドキュメント

- [システム仕様書](SYSTEM_SPECIFICATION.md) - 完全な仕様とアーキテクチャ
- [システムアーキテクチャ](docs/architecture/SYSTEM_ARCHITECTURE.md) - 全体設計図
- [API Gateway設計](docs/architecture/API_GATEWAY_DESIGN.md) - APIM/API Gateway/Apigee設計
- [クラウドコスト見積もり](docs/CLOUD_COST_ESTIMATION.md) - 運用コスト試算

### 監視・セキュリティ

- [相関ID設計](docs/monitoring/CORRELATION_ID.md) - リクエスト追跡の仕組み
- [エラーハンドリング](docs/monitoring/ERROR_HANDLING.md) - エラー処理ガイド
- [クエリサンプル集](docs/monitoring/QUERY_SAMPLES.md) - ログ検索クエリ
- [シークレット管理](docs/security/SECRET_MANAGEMENT.md) - Key Vault/Secrets Manager統合

### 運用ガイド

- [デプロイメントガイド](docs/operations/DEPLOYMENT_GUIDE.md) - デプロイ手順
- [監視運用手順書](docs/operations/MONITORING_RUNBOOK.md) - アラート対応
- [トラブルシューティング](docs/operations/TROUBLESHOOTING.md) - 問題解決

## テスト

```bash
# 全テスト実行（792テスト）
python -m pytest tests/ -v

# カバレッジレポート生成
python -m pytest tests/ --cov=src --cov-report=html

# 統合テスト（クラウド接続が必要）
python -m pytest tests/integration/ -v --integration

# ユニットテストのみ
python -m pytest tests/unit/ -v
```

## コスト見積もり

年間1,328件処理（月間約110件）の場合：

- **Azure**: 約$50.62/月
- **AWS**: 約$69.25/月
- **GCP**: 約$26.75/月

詳細は [コスト見積もりドキュメント](docs/CLOUD_COST_ESTIMATION.md) を参照してください。

## セキュリティ

- API キーは環境変数または Key Vault/Secrets Manager に格納
- 相関IDによる完全なリクエスト追跡
- エラーレスポンスでのトレースバック非表示（本番環境）
- API Gateway層での認証・レート制限

詳細は [セキュリティガイド](docs/security/SECRET_MANAGEMENT.md) を参照してください。

## コントリビューション

1. このリポジトリをフォーク
2. フィーチャーブランチを作成 (`git checkout -b feature/amazing-feature`)
3. 変更をコミット (`git commit -m 'Add amazing feature'`)
4. ブランチにプッシュ (`git push origin feature/amazing-feature`)
5. プルリクエストを作成

## ライセンス

このプロジェクトは [MIT License](LICENSE) の下でライセンスされています。

## サポート

- 問題報告: [GitHub Issues](https://github.com/goyosystems/ic-test-ai-agent/issues)
- ドキュメント: [Wiki](https://github.com/goyosystems/ic-test-ai-agent/wiki)
- 質問: [Discussions](https://github.com/goyosystems/ic-test-ai-agent/discussions)

## 更新履歴

### Version 2.5.0 (2026-02-12)

- 証跡ハイライト機能追加（PDF/Excel/テキスト対応）
- Azureデプロイ用ソースコード追加（platforms/azure/src/）
- クラウドコスト見積もり v9.0（為替¥152/USD）
- セットアップガイドをアーキテクチャと整合性更新
- 792テストケース

### Version 2.4.0 (2026-02-11)

- コードベース品質改善・ファイル構成整理
- ドキュメント完全版作成（アーキテクチャ、監視、セキュリティ、運用）
- セットアップガイドを初心者向け超詳細チュートリアルに刷新

### Version 1.2.0 (2026-02-08)

- API Gateway層統合（APIM/API Gateway/Apigee）
- 監視強化（Application Insights/X-Ray/Cloud Logging）
- シークレット管理統合（Key Vault/Secrets Manager/Secret Manager）
- 相関ID実装（完全なリクエスト追跡）

### Version 1.0.0 (2025-12-15)

- 初期リリース
- 8種類の監査タスク実装
- マルチクラウド対応（Azure/AWS/GCP）
- VBA/PowerShell統合

---

**開発**: Goyo Systems | **更新日**: 2026-02-12
