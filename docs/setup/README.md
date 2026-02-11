# セットアップガイド

本システムの環境構築に関するドキュメントです。各ガイドは初心者向けに詳細な解説付きで記述されています。

## 初めての方へ

以下の順序でセットアップを進めてください：

1. **[PREREQUISITES.md](PREREQUISITES.md)** - 開発環境の準備（Python、Git、CLI等）
2. クラウドプラットフォームを1つ選択（Azure/AWS/GCPのいずれか）
3. **[CLIENT_SETUP.md](CLIENT_SETUP.md)** - クライアント（Excel VBA/PowerShell）設定

## ドキュメント一覧

### 共通

- [PREREQUISITES.md](PREREQUISITES.md) - 前提条件・開発環境セットアップ

### クラウドプラットフォーム別

- [AZURE_SETUP.md](AZURE_SETUP.md) - Azure環境セットアップ（Functions、AI Foundry、APIM、Key Vault等）
- [AWS_SETUP.md](AWS_SETUP.md) - AWS環境セットアップ（Lambda、Bedrock、API Gateway、Secrets Manager等）
- [GCP_SETUP.md](GCP_SETUP.md) - GCP環境セットアップ（Cloud Functions、Vertex AI、Apigee、Secret Manager等）

### クライアント・CI/CD

- [CLIENT_SETUP.md](CLIENT_SETUP.md) - VBA/PowerShellクライアントセットアップ
- [GITHUB_SECRETS_SETUP.md](GITHUB_SECRETS_SETUP.md) - GitHub Actions CI/CD用シークレット設定

## 関連ドキュメント

- [デプロイメントガイド](../operations/DEPLOYMENT_GUIDE.md) - クラウドデプロイ手順
- [トラブルシューティング](../operations/TROUBLESHOOTING.md) - 問題解決
