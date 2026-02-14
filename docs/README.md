# ドキュメント一覧

内部統制テスト評価AIシステムの各種ドキュメントです。

## 導入・計画

| ドキュメント | 説明 | 対象者 |
|------------|------|-------|
| [CLOUD_COST_ESTIMATION.md](./CLOUD_COST_ESTIMATION.md) | クラウドリソース見積書（Azure/GCP/AWS） | IT部門、経理部門 |
| [EXCEPTION_APPROVAL_REQUEST.md](./EXCEPTION_APPROVAL_REQUEST.md) | セキュリティ例外承認申請書 | セキュリティ部門、IT部門 |

## ドキュメント概要

### クラウドリソース見積書
- システムアーキテクチャ図
- 動作モード一覧（POWERSHELL/VBA/EXPORT、同期/非同期）
- マルチクラウド対応（Azure/GCP/AWS）
- 詳細コスト見積もり（小規模〜大規模）
- SLA、リージョン選択

### セキュリティ例外承認申請書
- 使用するCOMオブジェクト一覧
- 使用するPowerShellコマンドレット一覧
- 各オブジェクト/コマンドの用途と権限
- 通信先ホワイトリスト
- リスク評価と軽減策
- 承認欄テンプレート

## プラットフォーム別ガイド

| プラットフォーム | 手順書 | 特徴 |
|----------------|--------|------|
| Azure | [platforms/azure/README.md](../platforms/azure/README.md) | Container Apps、Azure AI Foundry対応 |
| GCP | [platforms/gcp/README.md](../platforms/gcp/README.md) | Cloud Run、Vertex AI対応 |
| AWS | [platforms/aws/README.md](../platforms/aws/README.md) | App Runner、Bedrock対応 |
| Local | [platforms/local/README.md](../platforms/local/README.md) | オンプレミス、Ollama + Tesseract対応 |

## 関連ファイル

- [../SYSTEM_SPECIFICATION.md](../SYSTEM_SPECIFICATION.md) - システム仕様書
- [../setting.json.example](../setting.json.example) - 設定ファイルサンプル
- [../platforms/README.md](../platforms/README.md) - プラットフォーム選択ガイド
- [../web/README.md](../web/README.md) - Webフロントエンド（EXPORTモード用）
