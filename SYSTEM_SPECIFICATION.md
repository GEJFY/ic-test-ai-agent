# 内部統制テスト評価AIシステム 仕様書

================================================================================
**バージョン**: 3.0
**最終更新**: 2024年1月
**対象読者**: システム管理者、開発者、内部監査担当者
================================================================================

## 目次

1. [システム概要](#1-システム概要)
2. [システムアーキテクチャ](#2-システムアーキテクチャ)
3. [ファイル構成](#3-ファイル構成)
4. [コンポーネント詳細](#4-コンポーネント詳細)
5. [監査タスク詳細 (A1-A8)](#5-監査タスク詳細-a1-a8)
6. [環境構築](#6-環境構築)
7. [使用方法](#7-使用方法)
8. [トラブルシューティング](#8-トラブルシューティング)
9. [セキュリティ考慮事項](#9-セキュリティ考慮事項)
10. [技術解説](#10-技術解説)
11. [用語集](#11-用語集)
12. [更新履歴](#12-更新履歴)

---

## 1. システム概要

### 1.1 このシステムは何をするものか？

**内部統制テスト評価AIシステム**は、企業の内部監査業務を支援するAIツールです。

#### 従来の監査業務の課題

```
従来の手作業による監査:
┌─────────────────────────────────────────────────────────────┐
│  監査担当者                                                  │
│    │                                                        │
│    ├── ① テスト項目を確認（Excel）                          │
│    ├── ② エビデンス資料を1つずつ開く                        │
│    ├── ③ 内容を読み込み、理解する                           │
│    ├── ④ テスト手続きと照合して判断                         │
│    ├── ⑤ 判定結果と根拠をExcelに記入                        │
│    └── ⑥ 次のテスト項目へ（①に戻る）                       │
│                                                              │
│  問題点:                                                     │
│    - 1件あたり15-30分かかる                                  │
│    - 担当者による判断のばらつき                              │
│    - 大量の文書を読む負担                                    │
│    - 見落としリスク                                          │
└─────────────────────────────────────────────────────────────┘
```

#### AIシステムによる自動化

```
AIシステムによる監査:
┌─────────────────────────────────────────────────────────────┐
│  監査担当者                      AIシステム                  │
│    │                               │                        │
│    ├── ① Excelでテスト項目準備 ──▶│                        │
│    │                               ├── ② エビデンス自動収集 │
│    │                               ├── ③ AI分析・評価       │
│    │◀── ⑤ 結果確認・承認 ────────├── ④ 結果をExcelに記入  │
│    │                               │                        │
│  メリット:                                                   │
│    - 1件あたり1-3分に短縮                                    │
│    - 一貫した判断基準                                        │
│    - 24時間稼働可能                                          │
│    - 判断根拠の自動記録                                      │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 主要機能

本システムは以下の4つの主要機能を提供します:

| 機能 | 説明 | 技術 |
|------|------|------|
| **データ読み込み** | Excelシートからテストデータを自動取得 | VBA マクロ |
| **エビデンス収集** | 指定フォルダからPDF・画像等を自動収集 | PowerShell |
| **AI評価** | 大規模言語モデル(LLM)による自動評価 | LangChain + クラウドAI |
| **結果書き戻し** | 評価結果をExcelに自動記入 | VBA マクロ |

### 1.3 対応クラウドプロバイダー

本システムは「マルチクラウド対応」を特徴としており、以下のAIサービスを利用できます:

| プロバイダー | 環境変数値 | 説明 | 推奨用途 |
|-------------|-----------|------|---------|
| **Azure AI Foundry** | `AZURE_FOUNDRY` | Microsoft統合AIプラットフォーム | **推奨** - GPT-4o利用 |
| Azure OpenAI | `AZURE` | Azure OpenAI Service | GPT-4/GPT-3.5利用 |
| GCP Vertex AI | `GCP` | Google Cloud Gemini | Gemini Pro利用 |
| AWS Bedrock | `AWS` | Amazon Bedrock | Claude/Titan利用 |

#### なぜマルチクラウド対応なのか？

```
マルチクラウド対応のメリット:

1. ベンダーロックイン回避
   ┌──────────┐    ┌──────────┐    ┌──────────┐
   │  Azure   │ or │   GCP    │ or │   AWS    │
   └──────────┘    └──────────┘    └──────────┘
        ↓               ↓               ↓
   ┌─────────────────────────────────────────┐
   │          同じソースコード               │
   └─────────────────────────────────────────┘

2. コスト最適化
   - プロバイダーごとの料金比較が可能
   - 契約条件に応じて選択

3. 可用性向上
   - 1つのサービスが停止しても他で継続可能
```

---

## 2. システムアーキテクチャ

### 2.1 システム構成の概念

本システムは「クライアント・サーバー型」のアーキテクチャを採用しています。

```text
【クライアント・サーバー型とは？】

┌────────────────────┐         ┌────────────────────┐
│    クライアント     │ ──────▶ │     サーバー        │
│  （あなたのPC）     │ ◀────── │  （クラウド上）     │
└────────────────────┘         └────────────────────┘
     Excel + VBA                Azure Functions

・クライアント: リクエストを送る側（ユーザーのPC）
・サーバー: リクエストを処理する側（クラウド上のAI）
```

### 2.2 全体構成図

```text
┌─────────────────────────────────────────────────────────────────┐
│                      クライアント側（Excel VBA）                 │
├─────────────────────────────────────────────────────────────────┤
│  Excel VBA (ExcelToJson.bas)                                    │
│    ├── setting.json 読み込み                                    │
│    ├── Excelデータ → JSON変換                                   │
│    ├── バッチ処理（batchSize件ずつ）                            │
│    └── PowerShellスクリプト呼び出し                             │
│                                                                 │
│  PowerShell (CallCloudApi.ps1)                                  │
│    ├── EvidenceLinkフォルダからファイル収集                     │
│    ├── ファイル → Base64変換                                    │
│    └── Azure Functions API呼び出し                              │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTPS POST（暗号化通信）
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│               サーバー側（クラウド Functions）                   │
├─────────────────────────────────────────────────────────────────┤
│  function_app.py (エントリポイント)                             │
│    ├── /api/evaluate - 評価エンドポイント                       │
│    ├── /api/health - ヘルスチェック                             │
│    └── /api/config - 設定状態確認                               │
│                                                                 │
│  infrastructure/llm_factory.py                                  │
│    └── マルチクラウドLLMインスタンス生成                        │
│                                                                 │
│  core/auditor_agent.py (AuditOrchestrator)                      │
│    ├── タスク分解プランナー                                     │
│    ├── A1-A8タスク実行制御                                      │
│    └── 結果集約・最終判定                                       │
│                                                                 │
│  core/tasks/ (監査タスク A1-A8)                                 │
│    ├── a1_semantic_search.py    - 意味検索                      │
│    ├── a2_image_recognition.py  - 画像認識                      │
│    ├── a3_data_extraction.py    - データ抽出                    │
│    ├── a4_stepwise_reasoning.py - 段階的推論                    │
│    ├── a5_semantic_reasoning.py - 意味推論                      │
│    ├── a6_multi_document.py     - 複数文書統合                  │
│    ├── a7_pattern_analysis.py   - パターン分析                  │
│    └── a8_sod_detection.py      - 職務分掌検出                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ LangChain（AIフレームワーク）
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                       LLM プロバイダー                          │
│  Azure AI Foundry / Azure OpenAI / GCP Vertex AI / AWS Bedrock │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 各コンポーネントの役割

| コンポーネント | 役割 | 技術 |
| -------------- | ---- | ---- |
| Excel VBA | テストデータの入出力、ユーザーインターフェース | VBA マクロ |
| PowerShell | ファイル収集、API通信 | PowerShell 5.1+ |
| Azure Functions | API エンドポイント、リクエスト処理 | Python 3.11 |
| LLM Factory | AIモデルの切り替え管理 | LangChain |
| Auditor Agent | 監査タスクのオーケストレーション | LangGraph |
| Tasks (A1-A8) | 個別の監査評価ロジック | Python |

### 2.4 データフロー詳細

処理は以下の4ステップで行われます。

```text
【ステップ1】Excel → JSON変換
┌──────────────────────────────────────────────────────────────────┐
│  Excelシート                         JSON配列                    │
│  ┌────┬────────┬────────┐           [                           │
│  │ ID │ 統制   │ 手続き │    ──▶     { "ID": "CLC-01", ... },   │
│  ├────┼────────┼────────┤             { "ID": "CLC-02", ... }   │
│  │CLC1│ ...    │ ...    │           ]                           │
│  └────┴────────┴────────┘                                       │
└──────────────────────────────────────────────────────────────────┘

【ステップ2】エビデンス収集（PowerShell）
┌──────────────────────────────────────────────────────────────────┐
│  EvidenceLink: C:\SampleData\CLC-01\                            │
│                                                                  │
│  フォルダ内のファイル:              Base64エンコード後:          │
│  ├── 議事録.pdf          ──▶       "JVBERi0xLjQK..."            │
│  ├── 承認書.xlsx         ──▶       "UEsDBBQAAAA..."             │
│  └── スクリーンショット.png ──▶     "iVBORw0KGgo..."             │
└──────────────────────────────────────────────────────────────────┘

【ステップ3】API呼び出し・AI評価
┌──────────────────────────────────────────────────────────────────┐
│  リクエスト                          レスポンス                  │
│  {                                   {                          │
│    "ID": "CLC-01",                     "ID": "CLC-01",          │
│    "ControlDescription": "...",        "evaluationResult": true,│
│    "TestProcedure": "...",             "judgmentBasis": "...",  │
│    "EvidenceFiles": [...]              "confidence": 0.85       │
│  }                                   }                          │
│                                                                  │
│         ┌─────────────────────────────────┐                     │
│         │  AI が以下を実行:                │                     │
│         │  1. エビデンス内容を理解         │                     │
│         │  2. テスト手続きと照合           │                     │
│         │  3. 有効/非有効を判定            │                     │
│         │  4. 判定根拠を生成               │                     │
│         └─────────────────────────────────┘                     │
└──────────────────────────────────────────────────────────────────┘

【ステップ4】Excel書き戻し
┌──────────────────────────────────────────────────────────────────┐
│  レスポンスJSON                      Excelシート（結果列）       │
│  {                                   ┌────┬────┬────┬────┐      │
│    "evaluationResult": true,         │結果│根拠│参照│ファ│      │
│    "judgmentBasis": "有効...",  ──▶  ├────┼────┼────┼────┤      │
│    "documentReference": "...",       │有効│...│...│...│       │
│    "fileName": "議事録.pdf"          └────┴────┴────┴────┘      │
│  }                                                               │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. ファイル構成

```
ic-test-ai-agent/
├── ExcelToJson.bas          # Excel VBAモジュール（クライアント）
├── CallCloudApi.ps1         # PowerShellスクリプト（API呼び出し）
├── setting.json             # 設定ファイル（APIキー含む、Git除外）
├── setting.json.example     # 設定ファイルサンプル
├── .env                     # 環境変数（Git除外）
├── .env.example             # 環境変数サンプル
├── test_api.ps1             # APIテストスクリプト
│
├── src/                     # 共通コード（全プラットフォーム共有）
│   ├── core/                # ビジネスロジック
│   │   ├── handlers.py          # プラットフォーム非依存ハンドラー
│   │   ├── auditor_agent.py     # 監査オーケストレーター
│   │   ├── graph_orchestrator.py# LangGraphオーケストレーター
│   │   ├── document_processor.py# ドキュメント処理
│   │   └── tasks/
│   │       ├── base_task.py           # 基底クラス
│   │       ├── a1_semantic_search.py  # A1: 意味検索
│   │       ├── a2_image_recognition.py# A2: 画像認識
│   │       ├── a3_data_extraction.py  # A3: データ抽出
│   │       ├── a4_stepwise_reasoning.py# A4: 段階的推論
│   │       ├── a5_semantic_reasoning.py# A5: 意味推論
│   │       ├── a6_multi_document.py   # A6: 複数文書統合
│   │       ├── a7_pattern_analysis.py # A7: パターン分析
│   │       └── a8_sod_detection.py    # A8: 職務分掌検出
│   └── infrastructure/      # インフラ抽象化
│       ├── llm_factory.py       # マルチLLM対応ファクトリー
│       └── ocr_factory.py       # マルチOCR対応ファクトリー
│
├── platforms/               # プラットフォーム別エントリーポイント
│   ├── azure/               # Azure Functions
│   │   ├── function_app.py      # エントリーポイント
│   │   ├── host.json            # Functions設定
│   │   └── requirements.txt     # Azure用依存関係
│   ├── gcp/                 # GCP Cloud Functions
│   │   ├── main.py              # エントリーポイント
│   │   └── requirements.txt     # GCP用依存関係
│   └── aws/                 # AWS Lambda
│       ├── lambda_handler.py    # エントリーポイント
│       └── requirements.txt     # AWS用依存関係
│
├── requirements.txt         # 共通依存関係
│
└── SampleData/              # テスト用サンプルデータ
    ├── CLC-01/              # テストケース別フォルダ
    ├── CLC-02/
    └── ...
```

---

## 4. コンポーネント詳細

### 4.1 ExcelToJson.bas（VBAモジュール）

#### 目的
Excelシートのテストデータを読み込み、JSON形式に変換してAPIを呼び出す。

#### 主要関数

| 関数名 | 説明 |
|--------|------|
| `ProcessWithApi()` | メイン処理。バッチ処理でAPIを呼び出す |
| `LoadSettings()` | setting.jsonから設定を読み込む |
| `GenerateJsonForBatch()` | 指定範囲のデータをJSON変換 |
| `CallPowerShellApi()` | PowerShellスクリプトを実行 |
| `WriteResponseToExcel()` | APIレスポンスをExcelに書き戻す |

#### バッチ処理フロー

```
1. setting.json読み込み（batchSize取得）
2. Excelの有効データ行を収集
3. batchSize件ずつループ:
   a. JSON生成（GenerateJsonForBatch）
   b. 一時ファイルに保存
   c. PowerShell呼び出し（CallPowerShellApi）
   d. レスポンスをExcelに反映
4. 完了メッセージ表示
```

#### 設定構造 (SettingConfig)

```vba
Private Type SettingConfig
    DataStartRow As Long        ' データ開始行（通常2）
    SheetName As String         ' 対象シート名（空白=アクティブシート）
    BatchSize As Long           ' バッチサイズ（デフォルト3）
    ColID As String             ' ID列（例: "A"）
    ColControlDescription As String
    ColTestProcedure As String
    ColEvidenceLink As String
    ApiProvider As String       ' AZURE/GCP/AWS
    ApiEndpoint As String       ' API URL
    ApiKey As String            ' APIキー
    ApiAuthHeader As String     ' 認証ヘッダー名
    ColEvaluationResult As String
    ColJudgmentBasis As String
    ColDocumentReference As String
    ColFileName As String
    BooleanDisplayTrue As String   ' true表示（例: "有効"）
    BooleanDisplayFalse As String  ' false表示（例: "非有効"）
End Type
```

---

### 4.2 CallCloudApi.ps1（PowerShellスクリプト）

#### 目的
VBAから呼び出され、エビデンスファイルを収集してAPIを呼び出す。

#### パラメータ

| パラメータ | 必須 | 説明 |
|-----------|------|------|
| `-JsonFilePath` | Yes | 入力JSONファイルパス |
| `-Endpoint` | Yes | API URL |
| `-ApiKey` | Yes | APIキー |
| `-OutputFilePath` | Yes | 出力JSONファイルパス |
| `-Provider` | Yes | プロバイダー名（AZURE/GCP/AWS） |
| `-AuthHeader` | No | 認証ヘッダー名（デフォルトはプロバイダー依存） |

#### 処理フロー

```
1. JSONファイル読み込み
2. 各アイテムのEvidenceLinkフォルダを走査
3. ファイルをBase64変換してEvidenceFiles配列に追加
4. プロバイダー別の認証ヘッダーを設定
5. API呼び出し（Invoke-WebRequest）
6. レスポンスを出力ファイルに保存
```

#### 対応ファイル形式

| カテゴリ | 拡張子 |
|---------|--------|
| ドキュメント | .pdf, .doc, .docx |
| スプレッドシート | .xls, .xlsx, .xlsm, .csv |
| 画像 | .jpg, .jpeg, .png, .gif, .bmp, .webp, .tiff |
| テキスト | .txt, .log, .json, .xml |
| メール | .msg, .eml |

---

### 4.3 setting.json（設定ファイル）

```json
{
    "dataStartRow": 2,
    "sheetName": "",
    "batchSize": 3,
    "columns": {
        "ID": "A",
        "ControlDescription": "C",
        "TestProcedure": "D",
        "EvidenceLink": "E"
    },
    "api": {
        "provider": "AZURE",
        "endpoint": "https://func-ic-test-evaluation.azurewebsites.net/api/evaluate",
        "apiKey": "your-function-key",
        "authHeader": "x-functions-key"
    },
    "responseMapping": {
        "evaluationResult": "F",
        "judgmentBasis": "G",
        "documentReference": "H",
        "fileName": "I"
    },
    "booleanDisplayTrue": "有効",
    "booleanDisplayFalse": "非有効"
}
```

#### 設定項目

| 項目 | 説明 | デフォルト |
|------|------|----------|
| `dataStartRow` | データ開始行 | 2 |
| `sheetName` | 対象シート名（空=アクティブ） | "" |
| `batchSize` | 1回のAPI呼び出しで処理する件数 | 3 |
| `columns.*` | 入力列マッピング | - |
| `api.*` | API接続設定 | - |
| `responseMapping.*` | 出力列マッピング | - |
| `booleanDisplayTrue/False` | Boolean表示形式 | "有効"/"非有効" |

---

### 4.4 function_app.py（Azure Functions）

#### エンドポイント

| パス | メソッド | 説明 |
|------|---------|------|
| `/api/evaluate` | POST | テスト評価実行 |
| `/api/health` | GET | ヘルスチェック |
| `/api/config` | GET | 設定状態確認 |

#### /api/evaluate リクエスト形式

```json
[
    {
        "ID": "CLC-01",
        "ControlDescription": "取締役会は四半期ごとに経営成績をレビューし...",
        "TestProcedure": "取締役会議事録を閲覧し、レビューの実施を確認する",
        "EvidenceLink": "C:\\SampleData\\CLC-01",
        "EvidenceFiles": [
            {
                "fileName": "議事録.pdf",
                "extension": ".pdf",
                "mimeType": "application/pdf",
                "base64": "JVBERi0xLjQK..."
            }
        ]
    }
]
```

#### /api/evaluate レスポンス形式

```json
[
    {
        "ID": "CLC-01",
        "evaluationResult": true,
        "judgmentBasis": "[A5:意味検索 + 推論] 有効 - 取締役会議事録に経営成績レビューの記載あり...",
        "documentReference": "取締役会議事録 2024年第3四半期",
        "fileName": "議事録.pdf",
        "_debug": {
            "confidence": 0.85,
            "executionPlan": {
                "analysis": { "control_type": "全社統制", ... },
                "steps": [ { "task_type": "A5", ... } ],
                "reasoning": "..."
            },
            "taskResults": [
                {
                    "taskType": "A5",
                    "taskName": "意味検索 + 推論",
                    "success": true,
                    "confidence": 0.85,
                    "reasoning": "...",
                    "evidenceReferences": ["議事録.pdf"]
                }
            ]
        }
    }
]
```

#### 非同期処理・タイムアウト制御

```python
# サーバー側の同時実行制御
semaphore = asyncio.Semaphore(3)  # 最大3並列

# アイテム単位のタイムアウト
timeout_seconds = 90

# Functions全体のタイムアウト（host.json）
"functionTimeout": "00:10:00"  # 10分
```

---

### 4.5 llm_factory.py（LLMファクトリ）

#### プロバイダー設定

| プロバイダー | 必須環境変数 |
|-------------|-------------|
| `AZURE` | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT_NAME` |
| `AZURE_FOUNDRY` | `AZURE_FOUNDRY_ENDPOINT`, `AZURE_FOUNDRY_API_KEY` |
| `GCP` | `GCP_PROJECT_ID`, `GCP_LOCATION` |
| `AWS` | `AWS_REGION` |

#### Temperature非対応モデル

以下のモデルは`temperature`パラメータをサポートしないため、自動的にスキップ:

```python
MODELS_WITHOUT_TEMPERATURE = ["gpt-5-nano", "o1", "o1-mini", "o1-preview"]
```

---

### 4.6 auditor_agent.py（監査オーケストレーター）

#### 処理フロー

```
1. _create_plan(): LLMでタスク分解計画を作成
   - 統制記述・テスト手続きを分析
   - A1-A8から適切なタスクを選択
   - 依存関係を考慮した実行順序を決定

2. _execute_plan(): 計画に従いタスクを実行
   - 各タスクを順次実行
   - 結果をログ出力

3. _aggregate_results(): 結果を集約
   - 成功タスクの割合を計算
   - 信頼度加重平均を算出
   - 最終判定（有効/非有効）を決定
```

#### プランナープロンプト

```
あなたは内部統制監査のAIプランナーです。
与えられた統制記述とテスト手続きを分析し、最適な評価タスクの実行計画を立案してください。

【利用可能なタスクタイプ】
A1: 意味検索（セマンティックサーチ）
A2: 画像認識 + 情報抽出
A3: 構造化データ抽出
A4: 段階的推論 + 計算
A5: 意味検索 + 推論
A6: 複数文書統合理解
A7: パターン分析（時系列）
A8: 競合検出（SoD/職務分掌）
```

---

## 5. 監査タスク詳細 (A1-A8)

### 5.1 タスク一覧

| ID | タスク名 | 説明 | 主な用途 |
|----|---------|------|---------|
| A1 | 意味検索 | キーワード完全一致に頼らない意味的検索 | 規程文書の検索 |
| A2 | 画像認識 | PDF/画像から承認印・日付・氏名を抽出 | 承認証跡の確認 |
| A3 | データ抽出 | 表から数値抽出、単位・科目名の正規化 | 財務データの突合 |
| A4 | 段階的推論 | Chain-of-Thoughtで複雑な計算を検証 | 計算ロジックの確認 |
| A5 | 意味推論 | 抽象的な規程要求と実施記録の整合性判定 | コンプライアンス評価 |
| A6 | 複数文書統合 | バラバラな証跡からプロセスを再構成 | ワークフロー確認 |
| A7 | パターン分析 | 継続性確認、記録欠落の検出 | 定期処理の確認 |
| A8 | 職務分掌検出 | 権限の競合・SoD違反の検出 | 権限管理の確認 |

### 5.2 基底クラス (BaseAuditTask)

```python
class BaseAuditTask(ABC):
    task_type: TaskType      # タスク種別（A1-A8）
    task_name: str           # 日本語名
    description: str         # 説明

    def __init__(self, llm=None): ...
    async def execute(self, context: AuditContext) -> TaskResult: ...
```

### 5.3 データ構造

#### AuditContext（入力）

```python
@dataclass
class AuditContext:
    item_id: str                    # テストID（例: "CLC-01"）
    control_description: str        # 統制記述
    test_procedure: str             # テスト手続き
    evidence_link: str              # エビデンスフォルダパス
    evidence_files: List[EvidenceFile]  # エビデンスファイル群
    additional_context: Dict[str, Any]   # 追加コンテキスト
```

#### TaskResult（出力）

```python
@dataclass
class TaskResult:
    task_type: TaskType             # タスク種別
    task_name: str                  # タスク名
    success: bool                   # 成功/失敗
    result: Any                     # 詳細結果（JSON）
    reasoning: str                  # 判定根拠
    confidence: float               # 信頼度（0.0-1.0）
    evidence_references: List[str]  # 参照エビデンス
```

---

## 6. 環境構築

### 6.1 前提条件

本システムを動作させるために必要なソフトウェアの一覧です。

| ソフトウェア | バージョン | 用途 | インストール方法 |
| ------------ | ---------- | ---- | ---------------- |
| Python | 3.11以上 | サーバーサイド実行 | python.org からダウンロード |
| Azure Functions Core Tools | v4以上 | ローカル開発・デプロイ | npm または直接インストール |
| PowerShell | 5.1以上 | API呼び出しスクリプト | Windows標準搭載 |
| Excel | 2016以上 | VBAマクロ実行 | Microsoft Office |
| Git | 最新版 | ソースコード管理 | git-scm.com |

#### 各ソフトウェアのインストール確認方法

```powershell
# Pythonバージョン確認
python --version
# 出力例: Python 3.11.5

# Azure Functions Core Toolsバージョン確認
func --version
# 出力例: 4.0.5455

# PowerShellバージョン確認
$PSVersionTable.PSVersion
# 出力例: 5.1.22621.2506

# Gitバージョン確認
git --version
# 出力例: git version 2.42.0.windows.2
```

### 6.2 ローカル環境セットアップ（詳細手順）

#### ステップ1: プロジェクトのクローン

```powershell
# 作業ディレクトリに移動
cd C:\Users\your-name\Documents\VSCode_Dev

# リポジトリをクローン
git clone https://github.com/your-org/ic-test-ai-agent.git

# プロジェクトディレクトリに移動
cd ic-test-ai-agent
```

#### ステップ2: Python仮想環境の作成

```powershell
# プラットフォームディレクトリに移動
cd platforms\azure

# 仮想環境を作成
python -m venv .venv

# 仮想環境を有効化
.\.venv\Scripts\Activate.ps1

# 有効化の確認（プロンプトに(.venv)が表示される）
# (.venv) PS C:\...\platforms\azure>
```

#### ステップ3: 依存パッケージのインストール

```powershell
# pipを最新版に更新
python -m pip install --upgrade pip

# 依存パッケージをインストール
pip install -r requirements.txt

# インストール確認
pip list
```

#### ステップ4: 環境変数の設定

```powershell
# プロジェクトルートに戻る
cd ..\..

# サンプルファイルをコピー
Copy-Item .env.example .env

# .envファイルを編集
notepad .env
```

.envファイルの設定例:

```ini
# ==================================================
# LLMプロバイダー設定
# ==================================================
LLM_PROVIDER=AZURE_FOUNDRY

# Azure AI Foundry設定
AZURE_FOUNDRY_ENDPOINT=https://your-project.openai.azure.com/
AZURE_FOUNDRY_API_KEY=your-api-key-here
AZURE_FOUNDRY_MODEL=gpt-4o
AZURE_FOUNDRY_API_VERSION=2024-02-15-preview

# ==================================================
# OCRプロバイダー設定（オプション）
# ==================================================
OCR_PROVIDER=AZURE
AZURE_DOC_INTELLIGENCE_ENDPOINT=https://your-doc-intel.cognitiveservices.azure.com/
AZURE_DOC_INTELLIGENCE_KEY=your-key-here
```

#### ステップ5: Azure Functionsランタイム設定

```powershell
# platforms/azureディレクトリに移動
cd platforms\azure

# local.settings.jsonを作成
@"
{
    "IsEncrypted": false,
    "Values": {
        "AzureWebJobsStorage": "UseDevelopmentStorage=true",
        "FUNCTIONS_WORKER_RUNTIME": "python"
    }
}
"@ | Out-File -FilePath local.settings.json -Encoding utf8
```

#### ステップ6: ローカルサーバーの起動

```powershell
# Azure Functionsをローカルで起動
func start

# 正常起動時の出力例:
# Azure Functions Core Tools
# Core Tools Version: 4.0.5455
# Function Runtime Version: 4.27.5.21554
#
# Functions:
#   evaluate: [POST] http://localhost:7071/api/evaluate
#   health: [GET] http://localhost:7071/api/health
#   config: [GET] http://localhost:7071/api/config
```

#### ステップ7: 動作確認

```powershell
# 別のPowerShellウィンドウを開いて実行

# ヘルスチェック
Invoke-RestMethod -Uri "http://localhost:7071/api/health" -Method GET

# 設定確認
Invoke-RestMethod -Uri "http://localhost:7071/api/config" -Method GET
```

### 6.3 Azureへのデプロイ（詳細手順）

#### ステップ1: Azureリソースの作成

```powershell
# Azureにログイン
az login

# リソースグループを作成
az group create --name rg-ic-test-evaluation --location japaneast

# ストレージアカウントを作成
az storage account create `
    --name stictestevaluation `
    --resource-group rg-ic-test-evaluation `
    --location japaneast `
    --sku Standard_LRS

# Function Appを作成
az functionapp create `
    --name func-ic-test-evaluation `
    --resource-group rg-ic-test-evaluation `
    --storage-account stictestevaluation `
    --consumption-plan-location japaneast `
    --runtime python `
    --runtime-version 3.11 `
    --functions-version 4
```

#### ステップ2: 環境変数の設定

```powershell
# 環境変数を設定
az functionapp config appsettings set `
    --name func-ic-test-evaluation `
    --resource-group rg-ic-test-evaluation `
    --settings `
        LLM_PROVIDER=AZURE_FOUNDRY `
        AZURE_FOUNDRY_ENDPOINT=https://your-project.openai.azure.com/ `
        AZURE_FOUNDRY_API_KEY=your-api-key `
        AZURE_FOUNDRY_MODEL=gpt-4o
```

#### ステップ3: デプロイ

```powershell
# platforms/azureディレクトリから実行
cd platforms\azure

# デプロイ
func azure functionapp publish func-ic-test-evaluation

# デプロイ確認
az functionapp show --name func-ic-test-evaluation --resource-group rg-ic-test-evaluation
```

---

## 7. 使用方法

### 7.1 Excelシートの準備（詳細）

#### 7.1.1 シートの列構成

テストデータシートは以下の列構成で作成します:

| 列 | ヘッダー名 | 説明 | 入力例 |
| -- | ---------- | ---- | ------ |
| A | ID | テスト項目の一意識別子 | CLC-01 |
| B | (予備) | 必要に応じて使用 | - |
| C | ControlDescription | 統制の説明文 | 取締役会は四半期ごとに... |
| D | TestProcedure | テスト手続きの説明 | 取締役会議事録を閲覧し... |
| E | EvidenceLink | エビデンスフォルダのパス | C:\SampleData\CLC-01 |
| F | EvaluationResult | 【出力】評価結果 | 有効 / 非有効 |
| G | JudgmentBasis | 【出力】判定根拠 | AI生成テキスト |
| H | DocumentReference | 【出力】参照文書 | 議事録2024年Q3 |
| I | FileName | 【出力】参照ファイル名 | 議事録.pdf |

#### 7.1.2 エビデンスフォルダの準備

```text
C:\SampleData\
├── CLC-01\                    ← テストID別フォルダ
│   ├── 議事録.pdf             ← エビデンスファイル
│   ├── 承認書.xlsx
│   └── スクリーンショット.png
├── CLC-02\
│   └── 申請書.pdf
└── CLC-03\
    ├── 規程.docx
    └── 実施記録.xlsx
```

#### 7.1.3 対応ファイル形式

| カテゴリ | 拡張子 | 処理方法 |
| -------- | ------ | -------- |
| PDF | .pdf | テキスト抽出 + OCR（必要時） |
| Word | .doc, .docx | テキスト抽出 |
| Excel | .xls, .xlsx, .xlsm, .csv | セルデータ抽出 |
| 画像 | .jpg, .jpeg, .png, .gif, .bmp, .webp, .tiff | OCR + 画像認識 |
| テキスト | .txt, .log, .json, .xml | 直接読み込み |
| メール | .msg, .eml | 本文・添付抽出 |

### 7.2 VBAマクロの実行

#### ステップ1: VBAモジュールのインポート

```text
1. Excelを開く
2. Alt + F11 でVBAエディタを開く
3. [ファイル] → [ファイルのインポート]
4. ExcelToJson.bas を選択
5. VBAエディタを閉じる
```

#### ステップ2: 設定ファイルの確認

setting.jsonがプロジェクトルートに存在することを確認:

```json
{
    "dataStartRow": 2,
    "sheetName": "",
    "batchSize": 3,
    "columns": {
        "ID": "A",
        "ControlDescription": "C",
        "TestProcedure": "D",
        "EvidenceLink": "E"
    },
    "api": {
        "provider": "AZURE",
        "endpoint": "https://func-ic-test-evaluation.azurewebsites.net/api/evaluate",
        "apiKey": "your-function-key",
        "authHeader": "x-functions-key"
    },
    "responseMapping": {
        "evaluationResult": "F",
        "judgmentBasis": "G",
        "documentReference": "H",
        "fileName": "I"
    },
    "booleanDisplayTrue": "有効",
    "booleanDisplayFalse": "非有効"
}
```

#### ステップ3: マクロの実行

```text
1. Alt + F8 でマクロダイアログを開く
2. ProcessWithApi を選択
3. [実行] をクリック
4. 処理完了を待つ（進捗がステータスバーに表示）
5. F〜I列に結果が書き込まれる
```

### 7.3 バッチサイズの調整

バッチサイズは1回のAPI呼び出しで処理するテスト項目数です。

| バッチサイズ | 処理速度 | タイムアウトリスク | 推奨ケース |
| ------------ | -------- | ------------------ | ---------- |
| 1 | 遅い | 低い | 大きなエビデンスファイル |
| 3 | 中程度 | 中程度 | 標準的な使用 |
| 5 | 速い | 高い | 小さなファイルのみ |

---

## 8. トラブルシューティング

### 8.1 エラー別対処法

#### 8.1.1 504 Gateway Timeout

```text
【症状】
API呼び出しが「504 Gateway Timeout」でエラー終了する

【原因】
処理時間がタイムアウト設定（デフォルト5分）を超過

【対策】
1. setting.json の batchSize を減らす（3 → 1）
2. host.json の functionTimeout を延長:
   {
     "functionTimeout": "00:10:00"  // 10分に延長
   }
3. エビデンスファイルを軽量化（PDFの最適化等）
```

#### 8.1.2 401 Unauthorized

```text
【症状】
「401 Unauthorized」または「認証エラー」

【原因】
APIキーが無効または未設定

【対策】
1. setting.json の api.apiKey を確認
2. Azure Portalで Function App のキーを再取得
3. .env の LLM関連キーを確認
```

#### 8.1.3 LLM not configured

```text
【症状】
「LLM not configured」エラー

【原因】
LLMプロバイダーの環境変数が未設定

【対策】
1. /api/config エンドポイントにアクセス
2. missing_vars を確認
3. 不足している環境変数を .env に追加
```

#### 8.1.4 Temperature parameter error

```text
【症状】
「Temperature parameter not supported」

【原因】
o1シリーズなど一部モデルはtemperatureパラメータ非対応

【対策】
自動対応済み。llm_factory.py で自動スキップ。
手動対応が必要な場合は MODELS_WITHOUT_TEMPERATURE に追加。
```

### 8.2 ログの確認方法

#### ローカル環境

```powershell
# func start のコンソール出力を確認
# または Application Insights をローカルに設定
```

#### Azure環境

```powershell
# Azure Portal → Function App → ログストリーム

# または CLI で確認
az functionapp log tail --name func-ic-test-evaluation --resource-group rg-ic-test-evaluation
```

---

## 9. セキュリティ考慮事項

### 9.1 APIキーの管理

| 方法 | セキュリティレベル | 推奨環境 |
| ---- | ------------------ | -------- |
| .envファイル | 低（開発用） | ローカル開発 |
| Azure App Settings | 中 | 小規模本番 |
| Azure Key Vault | 高 | エンタープライズ |

#### Key Vault使用時の設定

```powershell
# Key Vaultの作成
az keyvault create --name kv-ic-test-eval --resource-group rg-ic-test-evaluation

# シークレットの追加
az keyvault secret set --vault-name kv-ic-test-eval --name "LLM-API-KEY" --value "your-key"

# Function AppにKey Vault参照を設定
az functionapp config appsettings set `
    --name func-ic-test-evaluation `
    --resource-group rg-ic-test-evaluation `
    --settings "AZURE_FOUNDRY_API_KEY=@Microsoft.KeyVault(SecretUri=https://kv-ic-test-eval.vault.azure.net/secrets/LLM-API-KEY/)"
```

### 9.2 データ保護

- エビデンスファイルはBase64エンコードで送信
- HTTPS暗号化通信を使用
- 機密データはメモリ上で処理後速やかに破棄

### 9.3 ネットワークセキュリティ

- VNet統合による通信保護を検討
- IP制限の設定を推奨
- Private Endpointの利用を検討

---

## 10. 技術解説

### 10.1 使用技術スタック

```text
┌─────────────────────────────────────────────────────────────────┐
│                        技術スタック                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  【クライアント層】                                             │
│  ┌──────────────┐  ┌──────────────┐                            │
│  │  Excel VBA   │  │  PowerShell  │                            │
│  │  (マクロ)     │  │  (スクリプト) │                            │
│  └──────────────┘  └──────────────┘                            │
│                                                                 │
│  【API層】                                                      │
│  ┌──────────────────────────────────────────────────────┐      │
│  │  Azure Functions / GCP Cloud Functions / AWS Lambda  │      │
│  │  ┌────────────────────────────────────────────────┐  │      │
│  │  │  Python 3.11 + async/await                     │  │      │
│  │  └────────────────────────────────────────────────┘  │      │
│  └──────────────────────────────────────────────────────┘      │
│                                                                 │
│  【AIオーケストレーション層】                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  LangChain   │  │  LangGraph   │  │   Factory    │         │
│  │  (AI連携)    │  │  (ワークフロー)│  │  Pattern     │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                 │
│  【LLMプロバイダー層】                                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │  Azure   │ │  Azure   │ │   GCP    │ │   AWS    │          │
│  │  Foundry │ │  OpenAI  │ │  Vertex  │ │  Bedrock │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 10.2 LangChainとは

LangChainは、大規模言語モデル（LLM）を活用したアプリケーション開発のためのフレームワークです。

```text
【LangChainの役割】

従来のアプローチ:
  アプリ ──直接呼び出し──▶ OpenAI API
  アプリ ──直接呼び出し──▶ Azure OpenAI API  ← 個別実装が必要
  アプリ ──直接呼び出し──▶ Vertex AI API

LangChainを使用:
  アプリ ──統一インターフェース──▶ LangChain ──▶ 各種LLM
                                         ├──▶ OpenAI
                                         ├──▶ Azure OpenAI
                                         ├──▶ Vertex AI
                                         └──▶ Bedrock
```

### 10.3 LangGraphとは

LangGraphは、複雑なAIワークフローをグラフ構造で定義・実行するライブラリです。

```text
【LangGraphのワークフロー例】

      ┌──────────────┐
      │    開始      │
      └──────┬───────┘
             ▼
      ┌──────────────┐
      │  プラン作成   │ ← LLMがタスクを分解
      └──────┬───────┘
             ▼
    ┌────────┴────────┐
    ▼                 ▼
┌────────┐      ┌────────┐
│ タスクA1│      │ タスクA5│  ← 並列実行可能
└────┬───┘      └────┬───┘
     └────────┬──────┘
              ▼
      ┌──────────────┐
      │  結果集約     │
      └──────┬───────┘
             ▼
      ┌──────────────┐
      │    終了      │
      └──────────────┘
```

### 10.4 Factory Patternとは

本システムでは「Factory Pattern（ファクトリーパターン）」を使用してLLMインスタンスを生成しています。

```text
【Factory Patternの仕組み】

環境変数: LLM_PROVIDER=AZURE_FOUNDRY

          ┌─────────────────┐
          │  llm_factory.py │
          │                 │
          │  create_llm()   │
          └────────┬────────┘
                   │
    ┌──────────────┼──────────────┐
    ▼              ▼              ▼
┌────────┐    ┌────────┐    ┌────────┐
│ AZURE  │    │  GCP   │    │  AWS   │
│ Foundry│    │ Vertex │    │Bedrock │
└────────┘    └────────┘    └────────┘

メリット:
- コードを変更せずにプロバイダーを切り替え可能
- 新しいプロバイダーの追加が容易
- テスト時にモックへの置き換えが容易
```

---

## 11. 用語集

| 用語 | 読み方 | 説明 |
| ---- | ------ | ---- |
| API | エーピーアイ | Application Programming Interface。システム間の通信規約 |
| Azure Functions | アジュール ファンクションズ | Microsoftのサーバーレスコンピューティングサービス |
| Base64 | ベースろくじゅうよん | バイナリデータをテキストに変換するエンコード方式 |
| Claude | クロード | Anthropic社が開発したAIモデル |
| Endpoint | エンドポイント | APIの接続先URL |
| Factory Pattern | ファクトリーパターン | オブジェクト生成を専用クラスに委譲するデザインパターン |
| Functions Core Tools | ファンクションズ コアツールズ | Azure Functionsのローカル開発ツール |
| Gemini | ジェミニ | Google社が開発したAIモデル |
| GPT | ジーピーティー | OpenAI社が開発したAIモデル |
| JSON | ジェイソン | JavaScript Object Notation。データ交換形式 |
| Key Vault | キーボルト | Azureのシークレット管理サービス |
| LangChain | ラングチェーン | LLMアプリケーション開発フレームワーク |
| LangGraph | ラングラフ | AIワークフロー定義ライブラリ |
| LLM | エルエルエム | Large Language Model。大規模言語モデル |
| OCR | オーシーアール | Optical Character Recognition。光学文字認識 |
| Orchestrator | オーケストレーター | 複数の処理を統括・調整するコンポーネント |
| PowerShell | パワーシェル | Windowsのスクリプト実行環境 |
| Serverless | サーバーレス | サーバー管理不要のクラウドサービス形態 |
| SoD | エスオーディー | Segregation of Duties。職務分掌 |
| VBA | ブイビーエー | Visual Basic for Applications。Officeマクロ言語 |
| Vertex AI | バーテックス エーアイ | Google Cloudの機械学習プラットフォーム |

---

## 12. 更新履歴

| 日付 | バージョン | 変更内容 |
| ---- | ---------- | -------- |
| 2024-01-04 | 1.0 | 初版作成 |
| 2024-01-05 | 2.0 | Azure AI Foundry対応、マルチクラウド対応 |
| 2024-01-06 | 2.1 | バッチ処理実装、タイムアウト対策 |
| 2024-01-07 | 3.0 | 仕様書大幅拡充、技術解説・用語集追加 |
