# 内部統制テスト評価AIシステム

[![Tests](https://github.com/goyosystems/ic-test-ai-agent/actions/workflows/test.yml/badge.svg)](https://github.com/goyosystems/ic-test-ai-agent/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

企業の内部監査業務を支援するマルチクラウド対応AIツールです。大規模言語モデル(LLM)を活用し、内部統制テストの自動評価を実現します。

## 主要機能

- **Excel統合**: VBAマクロによる自動データ読み込み・結果書き戻し
- **マルチクラウド対応**: Azure AI Foundry、AWS Bedrock、GCP Vertex AIをサポート
- **AI評価**: 8種類の監査タスク（A1-A8）を自動実行
- **非同期処理**: 大量テスト項目のタイムアウト回避
- **監視統合**: Application Insights、X-Ray、Cloud Loggingによるトレース
- **セキュリティ**: Key Vault/Secrets Manager統合、相関ID追跡

## 対応クラウドプロバイダー

| プロバイダー | モデル | 環境変数値 |
|-------------|--------|-----------|
| Azure AI Foundry | GPT-5.2 / GPT-5-nano | `AZURE_FOUNDRY` |
| AWS Bedrock | Claude Sonnet 4.5 / Opus 4.6 | `AWS` |
| GCP Vertex AI | Gemini 2.5 Pro / 3 Pro | `GCP` |
| Azure OpenAI | GPT-4o (レガシー) | `AZURE` |

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

- [Azure セットアップガイド](platforms/azure/README.md)
- [AWS セットアップガイド](platforms/aws/README.md)
- [GCP セットアップガイド](platforms/gcp/README.md)

## 監査タスク (A1-A8)

本システムは8種類の監査タスクをサポートします：

| タスク | 説明 | 技術 |
|--------|------|------|
| A1 | 意味検索 | セマンティックサーチ |
| A2 | 画像認識 | Vision API / OCR |
| A3 | 照合検証 | 複数文書間の整合性確認 |
| A4 | 書類完全性確認 | 必須フィールドの存在確認 |
| A5 | 根拠文書存在確認 | エビデンスファイルの検証 |
| A6 | 署名検証 | 承認・署名の有無確認 |
| A7 | 計算検証 | 数値計算の正確性確認 |
| A8 | 期間検証 | 日付範囲の妥当性確認 |

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

- [システム仕様書](SYSTEM_SPECIFICATION.md) - 完全な仕様とアーキテクチャ
- [クラウドコスト見積もり](docs/CLOUD_COST_ESTIMATION.md) - 運用コスト試算
- [アーキテクチャドキュメント](docs/architecture/) - 設計書
- [監視ガイド](docs/monitoring/) - ログ・メトリクス
- [運用ガイド](docs/operations/) - デプロイ・トラブルシューティング
- [セキュリティガイド](docs/security/) - シークレット管理

## テスト

```bash
# 全テスト実行
pytest -v

# カバレッジレポート生成
pytest --cov=src --cov-report=html

# E2Eテスト（統合テスト）
pytest tests/e2e/ -v --integration

# 特定プラットフォームのテスト
pytest tests/test_platform_azure.py -v
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

### Version 1.2.0 (2026-02-08)
- API Gateway層統合（APIM/API Gateway/Apigee）
- 監視強化（Application Insights/X-Ray/Cloud Logging）
- シークレット管理統合（Key Vault/Secrets Manager/Secret Manager）
- 相関ID実装（完全なリクエスト追跡）
- 467テストケース（カバレッジ80%以上）

### Version 1.0.0 (2025-12-15)
- 初期リリース
- 8種類の監査タスク実装
- マルチクラウド対応（Azure/AWS/GCP）
- VBA/PowerShell統合

---

**開発**: Goyo Systems | **更新日**: 2026-02-09
