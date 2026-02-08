# クラウドリソース見積書

## 内部統制テスト評価AIシステム

**作成日:** 2025年1月
**バージョン:** 2.0
**対象システム:** 内部統制テスト評価AI（ic-test-ai-agent）
**対応プラットフォーム:** Azure / GCP / AWS

---

## 目次

- [Part 1: Azure](#part-1-azure)
- [Part 2: GCP (Google Cloud Platform)](#part-2-gcp-google-cloud-platform)
- [Part 3: AWS (Amazon Web Services)](#part-3-aws-amazon-web-services)
- [Part 4: プラットフォーム比較](#part-4-プラットフォーム比較)

---

# Part 1: Azure

## 1. システム概要

### 1.1 システムの目的

本システムは、内部統制テストの評価業務をAIで自動化するものです。Excelに入力されたテスト項目と証跡ファイルをクラウドAPIに送信し、AI（LLM）による評価結果を取得してExcelに書き戻します。

### 1.2 アーキテクチャ概要

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ユーザー環境                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Excel + VBAマクロ                                                         │
│        │                                                                    │
│        ├─── [POWERSHELLモード] PowerShellスクリプト経由                      │
│        ├─── [VBAモード] VBA COMオブジェクト経由                              │
│        └─── [EXPORTモード] JSONファイル手動交換 → Webブラウザ                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ HTTPS (TLS 1.2+)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Azure クラウド                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐        │
│   │ Azure Functions │───▶│ Azure OpenAI    │    │ Azure Document  │        │
│   │ (API ホスト)    │    │ Service         │    │ Intelligence    │        │
│   └─────────────────┘    │ (LLM処理)       │    │ (OCR処理)       │        │
│           │              └─────────────────┘    └─────────────────┘        │
│           │                                                                 │
│           ▼                                                                 │
│   ┌─────────────────────────────────────────┐                              │
│   │ Azure Storage (非同期モード時)           │                              │
│   │ - Table Storage (ジョブ状態)            │                              │
│   │ - Queue Storage (ジョブキュー)          │                              │
│   │ - Blob Storage  (大容量ファイル)        │                              │
│   └─────────────────────────────────────────┘                              │
│                                                                             │
│   ┌─────────────────┐                                                       │
│   │ Azure AD        │ ← 本番環境推奨（認証・認可）                          │
│   └─────────────────┘                                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 動作モード一覧

### 2.1 クライアント実行モード

| モード | 説明 | 必要な権限 | 推奨環境 |
|--------|------|-----------|---------|
| **POWERSHELL** | PowerShellスクリプト経由でAPI呼び出し | PowerShell実行権限 | 標準環境（推奨） |
| **VBA** | VBA COMオブジェクト経由でAPI呼び出し | COM オブジェクト使用権限 | PowerShell禁止環境 |
| **EXPORT** | JSONファイルエクスポート＋Webブラウザ | ファイル保存権限のみ | 最高セキュリティ環境 |

### 2.2 サーバー処理モード

| モード | 説明 | タイムアウト | 推奨用途 |
|--------|------|-------------|---------|
| **同期** | API呼び出しで即時応答を待機 | 最大230秒 | 少量データ（10項目以下） |
| **非同期** | ジョブID返却→ポーリングで結果取得 | 制限なし | 大量データ、504タイムアウト対策 |

### 2.3 モード組み合わせマトリクス

| クライアントモード | 同期処理 | 非同期処理 |
|-------------------|---------|-----------|
| POWERSHELL | ✅ 対応 | ✅ 対応（推奨） |
| VBA | ✅ 対応 | ✅ 対応 |
| EXPORT | ✅ 対応 | ✅ 対応 |

---

## 3. 必要なAzureリソース

### 3.1 必須リソース（全モード共通）

| リソース | Azure サービス名 | SKU/プラン | 用途 |
|---------|-----------------|-----------|------|
| APIホスティング | Azure Functions | Consumption / Premium | REST API エンドポイント |
| LLM処理 | Azure OpenAI Service | Standard S0 | AI評価（GPT-4o等） |
| OCR処理 | Azure Document Intelligence | S0 | PDF・画像からのテキスト抽出 |
| ファイル保存 | Azure Storage Account | Standard LRS | 一時ファイル、ログ |

### 3.2 非同期モード追加リソース

| リソース | Azure サービス名 | SKU/プラン | 用途 |
|---------|-----------------|-----------|------|
| ジョブ状態管理 | Azure Table Storage | Standard | ジョブID、ステータス、結果保存 |
| ジョブキュー | Azure Queue Storage | Standard | 処理待ちジョブの管理 |
| 大容量ファイル | Azure Blob Storage | Standard | 大きな証跡ファイルの一時保存 |

### 3.3 本番環境推奨リソース

| リソース | Azure サービス名 | SKU/プラン | 用途 |
|---------|-----------------|-----------|------|
| ユーザー認証 | Azure Active Directory | Free / P1 | OAuth 2.0 認証 |
| アプリ登録 | App Registration | - | クライアント認証設定 |

### 3.4 監視・ログリソース（本番環境必須）

| リソース | Azure サービス名 | SKU/プラン | 用途 |
|---------|-----------------|-----------|------|
| APM・ログ収集 | Application Insights | Basic / Standard | Functions 監視、トレース |
| ログ分析 | Log Analytics Workspace | 従量課金 | 統合ログ保存・クエリ |
| メトリクス・アラート | Azure Monitor | 従量課金 | アラート通知 |
| 診断ログ | Diagnostic Settings | - | OpenAI/DI のログ収集 |

### 3.5 オプションリソース

| リソース | Azure サービス名 | SKU/プラン | 用途 |
|---------|-----------------|-----------|------|
| Webフロントエンド | Azure Static Web Apps | Free / Standard | EXPORTモード用WebUI |
| API管理 | Azure API Management | Consumption | レート制限、アクセス制御 |
| シークレット管理 | Azure Key Vault | Standard | APIキー、接続文字列の安全な保存 |

---

## 4. 詳細コスト見積もり

### 4.1 Azure Functions

#### 4.1.1 Consumption Plan（従量課金）

| 項目 | 単価 | 無料枠 |
|-----|------|-------|
| 実行回数 | ¥0.028 / 100万回 | 100万回/月 |
| 実行時間 | ¥0.0000224 / GB-秒 | 40万GB-秒/月 |
| ストレージ | ¥3.36 / GB/月 | 最初の1GB無料 |

**計算例（月1,000項目処理）:**
```
実行回数: 1,000回 × 2（evaluate + status） = 2,000回 → 無料枠内
実行時間: 2,000回 × 60秒 × 0.5GB = 60,000 GB-秒 → 無料枠内
月額: ¥0（無料枠内）
```

#### 4.1.2 Premium Plan（EP1）

| 項目 | 月額（東日本リージョン） |
|-----|------------------------|
| vCPU | ¥18,340 / vCPU |
| メモリ | ¥1,306 / GB |
| EP1（1vCPU, 3.5GB）| 約 ¥22,910/月 |

**推奨ケース:** 月10,000項目以上、または常時稼働が必要な場合

---

### 4.2 Azure OpenAI Service

#### 4.2.1 GPT-4o 価格（2025年1月時点）

| 項目 | 単価（USD） | 単価（JPY換算@150） |
|-----|-----------|-------------------|
| 入力トークン | $2.50 / 1M tokens | ¥375 / 1M tokens |
| 出力トークン | $10.00 / 1M tokens | ¥1,500 / 1M tokens |

#### 4.2.2 GPT-4o-mini 価格（低コスト版）

| 項目 | 単価（USD） | 単価（JPY換算@150） |
|-----|-----------|-------------------|
| 入力トークン | $0.15 / 1M tokens | ¥22.5 / 1M tokens |
| 出力トークン | $0.60 / 1M tokens | ¥90 / 1M tokens |

#### 4.2.3 トークン消費量の目安

| 処理フェーズ | 入力トークン | 出力トークン |
|-------------|------------|-------------|
| テスト計画作成 | 約800 | 約400 |
| 計画レビュー | 約1,000 | 約300 |
| タスク実行（A1-A8） | 約1,500 | 約500 |
| 最終判断 | 約1,200 | 約600 |
| 判断レビュー | 約1,000 | 約300 |
| **1項目あたり合計** | **約5,500** | **約2,100** |

**計算例（月1,000項目、GPT-4o）:**
```
入力: 5,500 × 1,000 = 5.5M tokens → ¥375 × 5.5 = ¥2,063
出力: 2,100 × 1,000 = 2.1M tokens → ¥1,500 × 2.1 = ¥3,150
月額: 約 ¥5,213
```

---

### 4.3 Azure Document Intelligence

#### 4.3.1 価格表

| モデル | 単価（1,000ページあたり） |
|-------|------------------------|
| Read（テキスト抽出） | ¥225 |
| Layout（レイアウト解析） | ¥1,500 |
| Prebuilt（定型文書） | ¥1,500 |
| Custom（カスタムモデル） | ¥2,250 |

#### 4.3.2 使用量の目安

| 証跡タイプ | 平均ページ数 | 使用モデル |
|-----------|------------|-----------|
| PDF文書 | 2-5ページ | Layout |
| スキャン画像 | 1ページ | Read/Layout |
| Excel/Word | 1-3ページ | Layout |

**計算例（月1,000項目、平均2ページ/項目）:**
```
処理ページ数: 1,000 × 2 = 2,000ページ
月額: ¥1,500 × 2 = ¥3,000
```

---

### 4.4 Azure Storage

#### 4.4.1 価格表（Standard LRS、東日本リージョン）

| サービス | 項目 | 単価 |
|---------|-----|------|
| Blob Storage | 容量 | ¥2.8 / GB/月 |
| Blob Storage | 読み取り（10,000回） | ¥0.56 |
| Blob Storage | 書き込み（10,000回） | ¥7.0 |
| Table Storage | 容量 | ¥8.4 / GB/月 |
| Table Storage | トランザクション（10,000回） | ¥0.056 |
| Queue Storage | 容量 | ¥8.4 / GB/月 |
| Queue Storage | トランザクション（10,000回） | ¥0.056 |

**計算例（月1,000項目、非同期モード）:**
```
Blob: 1GB × ¥2.8 + 2,000回書込 × ¥0.0007 = ¥4.2
Table: 0.1GB × ¥8.4 + 10,000回 × ¥0.000056 = ¥1.4
Queue: 0.01GB × ¥8.4 + 5,000回 × ¥0.000056 = ¥0.4
月額: 約 ¥500（最小課金単位による）
```

---

### 4.5 Azure Active Directory

#### 4.5.1 価格表

| プラン | 月額/ユーザー | 機能 |
|-------|-------------|------|
| Free | ¥0 | 基本認証、50,000オブジェクト |
| P1 | 約 ¥900 | 条件付きアクセス、グループ管理 |
| P2 | 約 ¥1,350 | ID保護、特権ID管理 |

**推奨:**
- 開発環境: Free
- 本番環境: P1（条件付きアクセスでセキュリティ強化）

---

### 4.6 監視・ログサービス

#### 4.6.1 Application Insights

| 項目 | 単価 | 無料枠 |
|-----|------|-------|
| データ取り込み | ¥336 / GB | 5GB/月 |
| データ保持（90日超） | ¥16.8 / GB/月 | 90日まで無料 |
| 連続エクスポート | ¥0.056 / GB | - |

**計算例（月1,000項目処理）:**
```
ログデータ量: 約2GB/月（API呼出しログ、トレース、例外）
月額: (2GB - 5GB無料枠) = ¥0（無料枠内）
※大規模利用(10,000項目)の場合: 約10GB → (10-5) × ¥336 = ¥1,680
```

#### 4.6.2 Log Analytics Workspace

| 項目 | 単価 | 無料枠 |
|-----|------|-------|
| データ取り込み | ¥336 / GB | 5GB/日（最初の31日） |
| データ保持（90日超） | ¥16.8 / GB/月 | 90日まで無料 |
| データエクスポート | ¥0.168 / GB | - |

**計算例（月1,000項目処理）:**
```
Azure OpenAI診断ログ: 約1GB/月
Document Intelligence診断ログ: 約0.5GB/月
Functions診断ログ: 約0.5GB/月
合計: 約2GB/月 → 無料枠内
※大規模利用(10,000項目)の場合: 約15GB → ¥336 × 15 = ¥5,040
```

#### 4.6.3 Azure Monitor

| 項目 | 単価 | 無料枠 |
|-----|------|-------|
| メトリクスアラートルール | ¥15 / ルール/月 | 最初の10ルール無料 |
| ログアラートルール（5分間隔） | ¥75 / ルール/月 | - |
| 通知（Email） | ¥0.28 / 1,000件 | 1,000件/月無料 |
| 通知（SMS） | ¥11 / 100件 | - |
| 通知（Webhook） | 無料 | - |

**推奨アラート構成:**
```
必須アラート（3ルール）:
- Functions エラー率 > 5%: メトリクスアラート（無料枠内）
- Functions 応答時間 > 30秒: メトリクスアラート（無料枠内）
- OpenAI API エラー: メトリクスアラート（無料枠内）

オプションアラート（2ルール）:
- 日次使用量レポート: ログアラート ¥75
- 週次コストサマリー: ログアラート ¥75
合計: ¥150/月（オプション利用時）
```

#### 4.6.4 診断設定（Diagnostic Settings）

| 項目 | 料金 |
|-----|------|
| 診断設定の構成 | 無料 |
| ログ転送 | 転送先サービスの料金に含まれる |

**必須診断設定:**
- Azure Functions → Log Analytics
- Azure OpenAI Service → Log Analytics
- Document Intelligence → Log Analytics
- Storage Account → Log Analytics（オプション）

#### 4.6.5 監視コストまとめ

| 規模 | Application Insights | Log Analytics | Azure Monitor | 合計 |
|-----|---------------------|---------------|---------------|------|
| 小規模（100項目） | ¥0（無料枠内） | ¥0（無料枠内） | ¥0（無料枠内） | **¥0** |
| 中規模（1,000項目） | ¥0（無料枠内） | ¥0（無料枠内） | ¥150（オプション） | **¥150** |
| 大規模（10,000項目） | ¥1,680 | ¥5,040 | ¥150 | **¥6,870** |

---

## 5. 規模別総合見積もり

### 5.1 小規模利用（月100項目）

| リソース | 構成 | 月額（JPY） |
|---------|-----|------------|
| Azure Functions | Consumption Plan | ¥0 |
| Azure OpenAI (GPT-4o) | 0.77M tokens | ¥550 |
| Document Intelligence | 200ページ | ¥300 |
| Storage | 最小構成 | ¥100 |
| Azure AD | Free | ¥0 |
| Application Insights | 無料枠内 | ¥0 |
| Log Analytics | 無料枠内 | ¥0 |
| Azure Monitor | 無料枠内 | ¥0 |
| **合計** | | **¥950/月** |

### 5.2 中規模利用（月1,000項目）

| リソース | 構成 | 月額（JPY） |
|---------|-----|------------|
| Azure Functions | Consumption Plan | ¥500 |
| Azure OpenAI (GPT-4o) | 7.6M tokens | ¥5,500 |
| Document Intelligence | 2,000ページ | ¥3,000 |
| Storage（非同期） | 標準構成 | ¥500 |
| Azure AD | Free | ¥0 |
| Application Insights | 無料枠内（2GB） | ¥0 |
| Log Analytics | 無料枠内（2GB） | ¥0 |
| Azure Monitor | アラート3ルール | ¥0 |
| **合計** | | **¥9,500/月** |

### 5.3 大規模利用（月10,000項目）

| リソース | 構成 | 月額（JPY） |
|---------|-----|------------|
| Azure Functions | Premium EP1 | ¥23,000 |
| Azure OpenAI (GPT-4o) | 76M tokens | ¥55,000 |
| Document Intelligence | 20,000ページ | ¥30,000 |
| Storage（非同期） | 拡張構成 | ¥2,000 |
| Azure AD | P1 × 10ユーザー | ¥9,000 |
| Application Insights | 10GB（5GB超過分課金） | ¥1,680 |
| Log Analytics | 15GB | ¥5,040 |
| Azure Monitor | アラート5ルール | ¥150 |
| **合計** | | **¥125,870/月** |

### 5.4 コスト削減オプション

| オプション | 削減効果 | 適用条件 |
|-----------|---------|---------|
| GPT-4o-mini使用 | LLMコスト約90%削減 | 精度許容範囲内 |
| Reserved Capacity | 最大30%削減 | 1年以上の利用確約 |
| セルフリフレクション無効化 | LLMコスト約40%削減 | 品質許容範囲内 |
| OCRスキップ（テキストPDF） | OCRコスト削減 | テキスト抽出可能なPDF |

---

## 6. 初期構築費用

### 6.1 リソースプロビジョニング

| 項目 | 作業時間目安 | 備考 |
|-----|------------|------|
| Azure サブスクリプション設定 | 1時間 | 既存サブスクリプション利用可 |
| リソースグループ作成 | 0.5時間 | |
| Azure Functions デプロイ | 2時間 | ARM/Bicep テンプレート利用可 |
| Azure OpenAI 申請・設定 | 1-5営業日 | 申請承認待ち時間含む |
| Document Intelligence 設定 | 1時間 | |
| Storage Account 設定 | 0.5時間 | |
| Azure AD 設定（オプション） | 2時間 | App Registration含む |
| **合計** | **約1営業日** | 承認待ち除く |

### 6.2 初期費用概算

| 項目 | 費用（JPY） |
|-----|------------|
| リソース作成 | ¥0（従量課金） |
| 初月利用料（テスト含む） | ¥5,000-10,000 |
| 技術支援（オプション） | 要相談 |

---

## 7. SLA（サービスレベル）

### 7.1 各サービスのSLA

| サービス | SLA |
|---------|-----|
| Azure Functions (Consumption) | 99.95% |
| Azure Functions (Premium) | 99.95% |
| Azure OpenAI Service | 99.9% |
| Azure Document Intelligence | 99.9% |
| Azure Storage | 99.9% (LRS) |
| Azure AD | 99.99% |

### 7.2 複合SLA計算

```
複合SLA = 99.95% × 99.9% × 99.9% × 99.9%
        = 99.65%
        = 月間ダウンタイム最大約2.5時間
```

---

## 8. リージョン選択

### 8.1 推奨リージョン

| リージョン | 理由 | 注意点 |
|-----------|------|-------|
| **東日本（Japan East）** | 低レイテンシ、データ主権 | Azure OpenAI 利用可 |
| 西日本（Japan West） | DR用途 | 一部サービス制限 |

### 8.2 マルチリージョン構成（オプション）

| 構成 | 用途 | 追加コスト |
|-----|------|-----------|
| アクティブ-パッシブ | DR対策 | 約+50% |
| アクティブ-アクティブ | 高可用性 | 約+100% |

---

## 9. 承認・発注に向けて

### 9.1 必要な承認

- [ ] IT部門によるアーキテクチャレビュー
- [ ] セキュリティ部門による審査
- [ ] 予算承認（年間見積もり）
- [ ] Azure OpenAI Service 利用申請

### 9.2 発注情報

| 項目 | 内容 |
|-----|------|
| 契約形態 | 従量課金（PAYG）または EA |
| 支払い通貨 | JPY または USD |
| 請求サイクル | 月次 |
| サポートプラン | Standard（推奨）または Professional |

---

## 付録A: 環境変数設定例

```env
# LLM Provider
LLM_PROVIDER=AZURE_FOUNDRY
AZURE_FOUNDRY_ENDPOINT=https://your-project.japaneast.models.ai.azure.com
AZURE_FOUNDRY_API_KEY=your-api-key
AZURE_FOUNDRY_MODEL=gpt-4o

# OCR Provider
OCR_PROVIDER=AZURE
AZURE_DI_ENDPOINT=https://your-di.cognitiveservices.azure.com/
AZURE_DI_KEY=your-di-key

# Storage (非同期モード)
JOB_STORAGE_PROVIDER=AZURE
JOB_QUEUE_PROVIDER=AZURE
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;...

# Performance Tuning
MAX_PLAN_REVISIONS=1
MAX_JUDGMENT_REVISIONS=1
```

---

## 付録B: 参考リンク

- [Azure Functions 価格](https://azure.microsoft.com/ja-jp/pricing/details/functions/)
- [Azure OpenAI Service 価格](https://azure.microsoft.com/ja-jp/pricing/details/cognitive-services/openai-service/)
- [Azure Document Intelligence 価格](https://azure.microsoft.com/ja-jp/pricing/details/ai-document-intelligence/)
- [Azure Storage 価格](https://azure.microsoft.com/ja-jp/pricing/details/storage/)
- [Azure AD 価格](https://azure.microsoft.com/ja-jp/pricing/details/active-directory/)
- [Application Insights 価格](https://azure.microsoft.com/ja-jp/pricing/details/monitor/)
- [Log Analytics 価格](https://azure.microsoft.com/ja-jp/pricing/details/monitor/)
- [Azure Monitor 価格](https://azure.microsoft.com/ja-jp/pricing/details/monitor/)

---

# Part 2: GCP (Google Cloud Platform)

## 1. GCPリソース概要

### 1.1 必須リソース

| リソース | GCP サービス名 | 用途 |
|---------|---------------|------|
| APIホスティング | Cloud Functions (2nd gen) | REST API エンドポイント |
| LLM処理 | Vertex AI (Gemini) | AI評価 |
| OCR処理 | Document AI | PDF・画像からのテキスト抽出 |
| ファイル保存 | Cloud Storage | 一時ファイル、ログ |

### 1.2 非同期モード追加リソース

| リソース | GCP サービス名 | 用途 |
|---------|---------------|------|
| ジョブ状態管理 | Firestore | ジョブID、ステータス、結果保存 |
| ジョブキュー | Cloud Tasks | 処理待ちジョブの管理 |

## 2. GCPコスト概算

### 2.1 Cloud Functions

| 項目 | 単価 | 無料枠 |
|-----|------|-------|
| 呼び出し回数 | $0.40 / 100万回 | 200万回/月 |
| コンピューティング時間 | $0.000016 / GB-秒 | 40万GB-秒/月 |

### 2.2 Vertex AI (Gemini 1.5 Pro)

| 項目 | 単価（USD） |
|-----|-----------|
| 入力トークン | $1.25 / 1M tokens |
| 出力トークン | $5.00 / 1M tokens |

### 2.3 Document AI

| モデル | 単価（1,000ページあたり） |
|-------|------------------------|
| Document OCR | $1.50 |
| Form Parser | $30.00 |
| Layout Parser | $10.00 |

### 2.4 規模別概算

| 規模 | 月額（USD） | 月額（JPY換算@150） |
|-----|-----------|-------------------|
| 小規模（100項目） | $5-10 | ¥750-1,500 |
| 中規模（1,000項目） | $40-60 | ¥6,000-9,000 |
| 大規模（10,000項目） | $400-600 | ¥60,000-90,000 |

## 3. GCP参考リンク

- [Cloud Functions 価格](https://cloud.google.com/functions/pricing)
- [Vertex AI 価格](https://cloud.google.com/vertex-ai/pricing)
- [Document AI 価格](https://cloud.google.com/document-ai/pricing)
- [Cloud Storage 価格](https://cloud.google.com/storage/pricing)
- [Firestore 価格](https://cloud.google.com/firestore/pricing)

---

# Part 3: AWS (Amazon Web Services)

## 1. AWSリソース概要

### 1.1 必須リソース

| リソース | AWS サービス名 | 用途 |
|---------|---------------|------|
| APIホスティング | Lambda + API Gateway | REST API エンドポイント |
| LLM処理 | Amazon Bedrock (Claude) | AI評価 |
| OCR処理 | Amazon Textract | PDF・画像からのテキスト抽出 |
| ファイル保存 | S3 | 一時ファイル、ログ |

### 1.2 非同期モード追加リソース

| リソース | AWS サービス名 | 用途 |
|---------|---------------|------|
| ジョブ状態管理 | DynamoDB | ジョブID、ステータス、結果保存 |
| ジョブキュー | SQS | 処理待ちジョブの管理 |

## 2. AWSコスト概算

### 2.1 Lambda

| 項目 | 単価 | 無料枠 |
|-----|------|-------|
| リクエスト数 | $0.20 / 100万回 | 100万回/月 |
| 実行時間 | $0.0000167 / GB-秒 | 40万GB-秒/月 |

### 2.2 Amazon Bedrock (Claude 3.5 Sonnet)

| 項目 | 単価（USD） |
|-----|-----------|
| 入力トークン | $3.00 / 1M tokens |
| 出力トークン | $15.00 / 1M tokens |

### 2.3 Amazon Textract

| API | 単価（1,000ページあたり） |
|-----|------------------------|
| Detect Document Text | $1.50 |
| Analyze Document | $15.00 |
| Analyze Expense | $10.00 |

### 2.4 規模別概算

| 規模 | 月額（USD） | 月額（JPY換算@150） |
|-----|-----------|-------------------|
| 小規模（100項目） | $10-15 | ¥1,500-2,250 |
| 中規模（1,000項目） | $80-120 | ¥12,000-18,000 |
| 大規模（10,000項目） | $800-1,200 | ¥120,000-180,000 |

## 3. AWS参考リンク

- [Lambda 価格](https://aws.amazon.com/lambda/pricing/)
- [Amazon Bedrock 価格](https://aws.amazon.com/bedrock/pricing/)
- [Amazon Textract 価格](https://aws.amazon.com/textract/pricing/)
- [S3 価格](https://aws.amazon.com/s3/pricing/)
- [DynamoDB 価格](https://aws.amazon.com/dynamodb/pricing/)

---

# Part 4: プラットフォーム比較

## 1. 機能比較

| 機能 | Azure | GCP | AWS |
|-----|-------|-----|-----|
| サーバーレス関数 | Azure Functions | Cloud Functions | Lambda |
| LLM | Azure OpenAI (GPT-4o) | Vertex AI (Gemini) | Bedrock (Claude) |
| OCR | Document Intelligence | Document AI | Textract |
| ジョブストレージ | Table Storage | Firestore | DynamoDB |
| ジョブキュー | Queue Storage | Cloud Tasks | SQS |

## 2. コスト比較（中規模：月1,000項目）

| 項目 | Azure | GCP | AWS |
|-----|-------|-----|-----|
| サーバーレス関数 | ¥500 | ¥0（無料枠） | ¥0（無料枠） |
| LLM | ¥5,500 | ¥4,500 | ¥13,500 |
| OCR | ¥3,000 | ¥1,500 | ¥3,000 |
| ストレージ | ¥500 | ¥300 | ¥300 |
| **合計** | **¥9,500** | **¥6,300** | **¥16,800** |

※ LLMモデル・使用量により大きく変動します

## 3. 選択ガイド

| シナリオ | 推奨プラットフォーム | 理由 |
|---------|-------------------|------|
| Microsoft環境統合 | Azure | Azure AD、M365との連携 |
| コスト重視 | GCP | Geminiの低価格 |
| Claude利用 | AWS | Bedrock経由でClaude利用可 |
| 既存インフラ活用 | 既存クラウド | 運用ノウハウ活用 |

---

**改訂履歴**

| バージョン | 日付 | 変更内容 |
|-----------|------|---------|
| 1.0 | 2025年1月 | 初版作成（Azure のみ） |
| 1.1 | 2025年1月 | 監視・ログリソース追加、規模別見積もり更新 |
| 2.0 | 2025年1月 | マルチクラウド対応（GCP、AWS追加）、プラットフォーム比較追加 |
