    # 内部統制テスト評価AIシステム 仕様書

    ================================================================================
    **バージョン**: 1.2.0
    **最終更新日**: 2026年2月8日
    **対象読者**: システム管理者、開発者、内部監査担当者
    ================================================================================

    ## 目次

    1. [システム概要](#1-システム概要)
    2. [システムアーキテクチャ](#2-システムアーキテクチャ)
    3. [ファイル構成](#3-ファイル構成)
    4. [コンポーネント詳細](#4-コンポーネント詳細)
    5. [監査タスク詳細 (A1-A8)](#5-監査タスク詳細-a1-a8)
    6. [処理モード](#6-処理モード)
    7. [環境構築](#7-環境構築)
    8. [使用方法](#8-使用方法)
    9. [トラブルシューティング](#9-トラブルシューティング)
    10. [セキュリティ考慮事項](#10-セキュリティ考慮事項)
    11. [テスト](#11-テスト)
    12. [クラウドリソース詳細](#12-クラウドリソース詳細)
    13. [技術解説](#13-技術解説)
    14. [用語集](#14-用語集)
    15. [更新履歴](#15-更新履歴)

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
    | **Azure AI Foundry** | `AZURE_FOUNDRY` | Microsoft統合AIプラットフォーム | **推奨** - GPT-5.2 / GPT-5-nano利用 |
    | Azure OpenAI | `AZURE` | Azure OpenAI Service | GPT-4o利用（レガシー） |
    | GCP Vertex AI | `GCP` | Google Cloud Gemini | Gemini 2.5 Pro / 3 Pro利用 |
    | AWS Bedrock | `AWS` | Amazon Bedrock | Claude Sonnet 4.5 / Opus 4.6利用 |

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
    ├── CallCloudApi.ps1         # PowerShellスクリプト（同期API呼び出し）
    ├── CallCloudApiAsync.ps1    # PowerShellスクリプト（非同期API呼び出し）
    ├── setting.json             # 設定ファイル（APIキー含む、Git除外）
    ├── setting.json.example     # 設定ファイルサンプル
    ├── .env                     # 環境変数（Git除外）
    ├── .env.example             # 環境変数サンプル
    │
    ├── src/                     # 共通コード（全プラットフォーム共有）
    │   ├── core/                # ビジネスロジック
    │   │   ├── handlers.py          # プラットフォーム非依存ハンドラー
    │   │   ├── async_handlers.py    # 非同期API用ハンドラー
    │   │   ├── async_job_manager.py # 非同期ジョブ管理
    │   │   ├── auditor_agent.py     # 監査オーケストレーター（レガシー）
    │   │   ├── graph_orchestrator.py# LangGraphオーケストレーター
    │   │   ├── document_processor.py# ドキュメント処理
    │   │   ├── prompts.py           # プロンプトテンプレート
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
    │       ├── ocr_factory.py       # マルチOCR対応ファクトリー
    │       ├── logging_config.py    # ロギング設定
    │       └── job_storage/         # 非同期ジョブストレージ
    │           ├── __init__.py          # ファクトリー・インターフェース
    │           ├── memory.py            # インメモリ実装（開発用）
    │           ├── azure_table.py       # Azure Table Storage
    │           ├── azure_blob.py        # Azure Blob Storage
    │           ├── azure_queue.py       # Azure Queue Storage
    │           ├── aws_dynamodb.py      # AWS DynamoDB
    │           ├── aws_sqs.py           # AWS SQS
    │           ├── gcp_firestore.py     # GCP Firestore
    │           └── gcp_tasks.py         # GCP Cloud Tasks
    │
    ├── platforms/               # プラットフォーム別エントリーポイント
    │   ├── README.md            # プラットフォーム選択ガイド
    │   ├── azure/               # Azure Functions
    │   │   ├── function_app.py      # エントリーポイント
    │   │   ├── host.json            # Functions設定
    │   │   ├── requirements.txt     # Azure用依存関係
    │   │   ├── deploy.ps1           # デプロイスクリプト
    │   │   ├── local.settings.json  # ローカル開発設定（Git除外）
    │   │   ├── .funcignore          # デプロイ除外設定
    │   │   └── README.md            # Azure固有の手順書
    │   ├── gcp/                 # GCP Cloud Functions
    │   │   ├── main.py              # エントリーポイント
    │   │   ├── requirements.txt     # GCP用依存関係
    │   │   ├── deploy.ps1           # デプロイスクリプト
    │   │   ├── .gcloudignore        # デプロイ除外設定
    │   │   └── README.md            # GCP固有の手順書
    │   └── aws/                 # AWS Lambda
    │       ├── lambda_handler.py    # エントリーポイント
    │       ├── requirements.txt     # AWS用依存関係
    │       ├── deploy.ps1           # デプロイスクリプト
    │       ├── .lambdaignore        # デプロイ除外設定
    │       └── README.md            # AWS固有の手順書
    │
    ├── scripts/                 # ユーティリティスクリプト
    │   ├── setup-azure-ad-auth.ps1  # Azure AD認証設定
    │   ├── setup-gcp-iap-auth.ps1   # GCP IAM認証設定
    │   ├── setup-aws-cognito-auth.ps1 # AWS Cognito認証設定
    │   └── test-azure-ad-auth.ps1   # Azure AD認証テスト
    │
    ├── web/                     # Webフロントエンド（EXPORTモード用）
    │   ├── index.html               # メインHTML
    │   ├── styles.css               # スタイルシート
    │   ├── app.js                   # JavaScript
    │   └── staticwebapp.config.json # Azure Static Web Apps設定
    │
    ├── docs/                    # ドキュメント
    │   ├── README.md                # ドキュメント目次
    │   └── AZURE_COST_ESTIMATION.md # コスト見積書
    │
    ├── tests/                   # テストスイート
    │   ├── conftest.py              # テスト設定・フィクスチャ
    │   ├── test_base_task.py        # タスク基底クラステスト
    │   ├── test_document_processor.py# ドキュメント処理テスト
    │   └── ...                      # その他テスト
    │
    ├── requirements.txt         # 共通依存関係
    ├── requirements-dev.txt     # 開発用依存関係
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
        BatchSize As Long           ' バッチサイズ（デフォルト10、推奨5-20）
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
        "batchSize": 10,
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
    | `batchSize` | 1回のAPI呼び出しで処理する件数（5-20推奨） | 10 |
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

    ### 4.7 HighlightingService (証跡ハイライト)

    #### 概要
    証跡ハイライト機能は、AI監査人が特定した引用箇所に基づき、証跡ファイルの該当部分を自動的にハイライトします。これにより、ユーザー（監査人やクライアント）は監査判断の根拠を迅速に確認できます。

    #### 対応形式と動作

    | ファイルタイプ | 拡張子 | ハイライト方法 | 出力形式 |
    | :--- | :--- | :--- | :--- |
    | **PDF** | `.pdf` | テキストハイライト（黄色背景） | `.pdf` |
    | **Excel** | `.xlsx` | セル背景色変更（黄色） | `.xlsx` |
    | **Word** | `.docx`, `.doc` | テキストを抽出し、ハイライト付きでPDF化 | `.pdf` |
    | **テキスト/コード** | `.txt`, `.csv`, `.json`, `.xml`, `.log`, `.md` | テキストを抽出し、ハイライト付きでPDF化 | `.pdf` |
    | **画像** | `.jpg`, `.png`, etc. | OCRテキストを抽出し、ハイライト付きでPDF化（予定） | `.pdf` |

    **PDF/Excel以外の形式に関する注意点**:

    ネイティブなハイライトをサポートしていない形式や、専用ソフトウェアなしでの編集が困難な形式（Word、メールなど）の場合、システムは抽出されたテキストを含む**新しいPDFを生成**します。
    この生成されたPDF内で該当箇所がハイライトされます。これにより、ユーザーが特定のアプリケーション（Wordなど）をインストールしていなくても、一貫したレビュー体験が可能になります。

    #### 出力場所
    ハイライトされたファイルは、証跡フォルダ内の `highlighted_evidence` ディレクトリ（証跡フォルダが読み取り専用の場合は一時ディレクトリ）に保存されます。
    Excelの監査レポートには、元の証跡ファイルの代わりに、これらのハイライト済みファイルへのリンクが含まれます。

    #### 依存ライブラリ
    この機能には以下のPythonライブラリが必要です（requirements.txtに含まれています）：
    - `pymupdf` (PDF処理用)
    - `openpyxl` (Excel処理用)
    - `reportlab` (PDF生成用)

    #### トラブルシューティング
    - **PDFでハイライトが表示されない**: PDFが選択可能なテキストを含んでいるか確認してください（スキャン画像のみでないこと）。スキャンされたPDFの場合、ハイライトが失敗するか、位置がずれる可能性があります。
    - **Excelのリンク切れ**: `highlighted_evidence` フォルダがExcelレポートから相対的にアクセス可能な位置にあるか確認してください。

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

    ## 6. 処理モード

    本システムは、用途に応じて複数の処理モードを提供しています。

    ### 6.1 同期モードと非同期モード

    Azure Functions等のサーバーレス環境では、230秒のタイムアウト制限があります。
    複数のテスト項目を評価する場合、この制限を超える可能性があるため、非同期モードを推奨します。

    ```text
    【同期モード（asyncMode: false）】
    Excel ──POST /api/evaluate──▶ API ──待機──▶ 結果
            └────────最大230秒で504タイムアウトの可能性────────┘

    【非同期モード（asyncMode: true、推奨）】
    Excel ──POST /api/evaluate/submit──▶ API ──即座に──▶ job_id返却
                                            │
                                            ▼ バックグラウンド処理
                                        ┌─────────────────┐
                                        │ 評価処理を実行  │
                                        └─────────────────┘
                                            │
    Excel ◀──GET /api/evaluate/status────────┤ ポーリング
    Excel ◀──GET /api/evaluate/results───────┘ 結果取得
    ```

    #### 設定方法（setting.json）

    ```json
    {
        "asyncMode": true,
        "pollingIntervalSec": 5
    }
    ```

    | 設定項目 | 説明 | デフォルト |
    |---------|------|-----------|
    | `asyncMode` | 非同期モードの有効/無効 | `true`（推奨） |
    | `pollingIntervalSec` | ポーリング間隔（秒） | `5` |

    ### 6.2 APIクライアント方式

    2つのAPI呼び出し方式を選択可能です：

    | 方式 | 設定値 | 特徴 | 推奨 |
    |------|--------|------|------|
    | PowerShell | `POWERSHELL` | 大容量ファイル対応、安定性高 | **推奨** |
    | VBA Native | `VBA` | PowerShell不可環境用、COM経由HTTP通信 | 特殊環境用 |
    | Export/Import | `EXPORT` | PowerShell/VBA両方禁止環境用、Webブラウザ経由 | 最終手段 |

    #### 設定方法（setting.json）

    ```json
    {
        "apiClient": "POWERSHELL"
    }
    ```

    #### EXPORTモード（Webフロントエンド連携）

    PowerShellとVBA COMの両方が禁止されている環境向けの代替手段です。

    ```text
    【ワークフロー】

    ┌─────────────────────────────────────────────────────────────────┐
    │ Excel                                                           │
    │  1. ProcessForExport マクロ実行                                 │
    │     → export_YYYYMMDD_HHMMSS.json が生成される                 │
    └─────────────────────────────────────────────────────────────────┘
                                  ↓
    ┌─────────────────────────────────────────────────────────────────┐
    │ Webブラウザ (web/index.html)                                    │
    │  2. JSONファイルをドラッグ&ドロップでアップロード               │
    │  3. APIエンドポイントとキーを入力                               │
    │  4. 「AI評価を開始」をクリック                                  │
    │  5. 処理完了後、結果JSONをダウンロード                          │
    └─────────────────────────────────────────────────────────────────┘
                                  ↓
    ┌─────────────────────────────────────────────────────────────────┐
    │ Excel                                                           │
    │  6. ImportResults マクロ実行                                    │
    │  7. ダウンロードしたJSONファイルを選択                          │
    │  8. 評価結果がExcelに反映される                                 │
    └─────────────────────────────────────────────────────────────────┘
    ```

    **VBAマクロ**:

    | マクロ名 | 機能 |
    |----------|------|
    | `ProcessForExport` | 評価用JSONをエクスポート |
    | `ImportResults` | 評価結果JSONをインポート |

    **Webフロントエンド**:

    - 場所: `web/index.html`
    - 対応ブラウザ: Chrome 80+, Firefox 75+, Safari 13+, Edge 80+
    - デプロイ: ローカル使用 または Azure Static Web Apps

    ### 6.3 セルフリフレクション機能

    AI評価の品質向上のため、評価結果を自動的にレビュー・修正する機能です。

    ```text
    【処理フロー】
    1. execute_task: 初期評価を実行
        ↓
    2. review_judgment: 評価結果をレビュー
        ↓
    3. refine_judgment: フィードバックに基づき修正
        ↓
    4. finalize: 最終結果を出力
    ```

    #### 出力フィールド

    | フィールド | 説明 |
    |-----------|------|
    | `evaluationResult` | 評価結果（true=有効, false=非有効） |
    | `executionPlanSummary` | 実行計画の概要 |
    | `judgmentBasis` | 判断根拠（詳細説明） |
    | `documentReference` | 参照文書（引用情報） |
    | `evidenceFileNames` | 証跡ファイル名リスト |

    ### 6.4 大容量証跡ファイル対応

    Azure Table Storageの64KB制限を回避するため、**全ての証跡ファイル**をBlob Storageに自動分離します。

    > **重要**: Azure Table Storageは1エンティティあたり64KBの制限があります。
    > 複数の小さな証跡ファイル（例: 10KB × 10ファイル = 100KB）でも合計で制限を超える
    > 可能性があるため、サイズに関わらず全ての証跡ファイルをBlob Storageに保存します。

    ```text
    【処理フロー】
    送信時: 全ての証跡ファイル ──▶ Blob Storage保存 ──▶ 参照情報に置換
                                                        │
                                                        ▼
                                              Table Storageに参照のみ保存
                                              （64KB制限を確実に回避）

    取得時: 参照 ──▶ Blob Storageから復元 ──▶ 評価処理
    ```

    #### Blobストレージ構造

    ```text
    evidence-files/                          # Blobコンテナ
    └── {job_id}/                            # ジョブ別フォルダ
        └── {item_id}/                       # アイテム別フォルダ
            ├── 0_議事録.pdf                 # 証跡ファイル（Base64）
            ├── 1_承認書.xlsx
            └── 2_スクリーンショット.png
    ```

    #### 必要な環境変数

    ```ini
    AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
    ```

    ---

    ## 7. 環境構築

    ### 7.1 前提条件

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

    ### 7.2 ローカル環境セットアップ（詳細手順）

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

    ### 7.3 Azureへのデプロイ（詳細手順）

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

    ## 8. 使用方法

    ### 8.1 Excelシートの準備（詳細）

    #### 8.1.1 シートの列構成

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

    #### 8.1.2 エビデンスフォルダの準備

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

    #### 8.1.3 対応ファイル形式

    | カテゴリ | 拡張子 | 処理方法 |
    | -------- | ------ | -------- |
    | PDF | .pdf | テキスト抽出 + OCR（必要時） |
    | Word | .doc, .docx | テキスト抽出 |
    | Excel | .xls, .xlsx, .xlsm, .csv | セルデータ抽出 |
    | 画像 | .jpg, .jpeg, .png, .gif, .bmp, .webp, .tiff | OCR + 画像認識 |
    | テキスト | .txt, .log, .json, .xml | 直接読み込み |
    | メール | .msg, .eml | 本文・添付抽出 |

    ### 8.2 VBAマクロの実行

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
        "batchSize": 10,
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

    ### 8.3 バッチサイズの調整

    バッチサイズは1回のAPI呼び出しで処理するテスト項目数です。非同期モードでは大きな値も安全に使用できます。

    | バッチサイズ | 処理速度 | タイムアウトリスク | 推奨ケース |
    | ------------ | -------- | ------------------ | ---------- |
    | 5 | 中程度 | 低い | 大きなエビデンスファイル |
    | 10 | 速い | 中程度 | 標準的な使用（推奨） |
    | 20 | 非常に速い | 高い | 小さなファイルのみ・非同期モード |

    ---

    ## 9. トラブルシューティング

    ### 9.1 エラー別対処法

    #### 9.1.1 504 Gateway Timeout

    ```text
    【症状】
    API呼び出しが「504 Gateway Timeout」でエラー終了する

    【原因】
    処理時間がタイムアウト設定（デフォルト5分）を超過

    【対策】
    1. setting.json の batchSize を減らす（10 → 5）
    2. host.json の functionTimeout を延長:
    {
        "functionTimeout": "00:10:00"  // 10分に延長
    }
    3. エビデンスファイルを軽量化（PDFの最適化等）
    ```

    #### 9.1.2 401 Unauthorized

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

    #### 9.1.3 LLM not configured

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

    #### 9.1.4 Temperature parameter error

    ```text
    【症状】
    「Temperature parameter not supported」

    【原因】
    o1シリーズなど一部モデルはtemperatureパラメータ非対応

    【対策】
    自動対応済み。llm_factory.py で自動スキップ。
    手動対応が必要な場合は MODELS_WITHOUT_TEMPERATURE に追加。
    ```

    ### 9.2 ログの確認方法

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

    ## 10. セキュリティ考慮事項

    ### 10.1 APIキーの管理

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

    ### 10.2 データ保護

    - エビデンスファイルはBase64エンコードで送信
    - HTTPS暗号化通信を使用
    - 機密データはメモリ上で処理後速やかに破棄

    ### 10.3 ネットワークセキュリティ

    - VNet統合による通信保護を検討
    - IP制限の設定を推奨
    - Private Endpointの利用を検討

    ### 10.4 Azure AD認証によるアクセス制御（推奨・本番環境必須）

    本システムでは、**Azure AD認証のみ**によるセキュアなアクセス制御を推奨しています。
    Functions Keyは使用せず、Azure ADで認証・認可を一元管理します。

    #### 10.4.1 認証方式の比較

    | 認証方式 | セキュリティ | 管理性 | 推奨環境 |
    | -------- | ----------- | ------ | -------- |
    | Functions Key のみ | 低 | 簡単 | ローカル開発のみ |
    | **Azure AD のみ** | **高** | **中程度** | **本番環境（推奨）** |
    | Azure AD + Functions Key | 中 | 複雑 | 非推奨（Key流出リスク） |

    > **重要**: Functions Keyは設定ファイルに記載するため、流出リスクがあります。
    > 本番環境では必ずAzure AD認証を使用してください。

    #### 10.4.2 Azure AD認証の仕組み

    ```text
    【認証フロー（ブラウザ認証 + トークンキャッシュ）】

    本システムでは、Authorization Code Flow with PKCE を使用したブラウザベース認証を採用しています。
    これにより、デバイスコードを手動入力する必要がなく、ブラウザが自動で開いて認証が完了します。

    ┌─────────────────────────────────────────────────────────────────┐
    │                         初回認証                                 │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                  │
    │  ユーザー（Excel）                                               │
    │      │                                                          │
    │      ▼                                                          │
    │  ① PowerShell起動                                               │
    │      │                                                          │
    │      ├── まずサイレント認証を試行（prompt=none）                │
    │      │   └── 成功: ブラウザ操作なしでトークン取得 ──────▶ ④へ  │
    │      │                                                          │
    │      └── サイレント認証失敗の場合:                              │
    │          ▼                                                      │
    │  ② ブラウザが自動で開く（Azure ADログインページ）               │
    │      │                                                          │
    │      ▼                                                          │
    │  ③ ユーザーがログイン（初回のみ権限承認）                       │
    │      │                                                          │
    │      ├── 認証成功 → localhost:8400-8499 にリダイレクト          │
    │      │             （PowerShellがHTTPリスナーで待機）            │
    │      │                                                          │
    │      ▼                                                          │
    │  ④ アクセストークン + リフレッシュトークン取得                   │
    │      │                                                          │
    │      ├──▶ トークンをローカルにキャッシュ保存                    │
    │      │    （%TEMP%\ic-test-azure-ad-token.json）                 │
    │      │                                                          │
    │      ▼                                                          │
    │  ⑤ API呼び出し（Authorization: Bearer {token}）                 │
    │      │                                                          │
    │      ▼                                                          │
    │  Azure Functions（AuthLevel.ANONYMOUS）                         │
    │      │                                                          │
    │      ├── ⑥ Azure ADプラットフォーム認証でトークン検証           │
    │      │                                                          │
    │      ├── ⑦ グループメンバーシップ確認                           │
    │      │       └── 許可グループに所属？ → Yes: 処理続行           │
    │      │                                  → No: 403 Forbidden     │
    │      │                                                          │
    │      ▼                                                          │
    │  評価処理実行                                                    │
    │                                                                  │
    └─────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────┐
    │                     2回目以降（キャッシュ利用）                   │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                  │
    │  ユーザー（Excel）                                               │
    │      │                                                          │
    │      ▼                                                          │
    │  ① キャッシュからトークン読み込み                               │
    │      │                                                          │
    │      ├── 有効期限内？ → Yes: そのまま使用                       │
    │      │                                                          │
    │      └── 期限切れ？ → リフレッシュトークンで自動更新            │
    │                        （ユーザー操作不要）                      │
    │      │                                                          │
    │      ▼                                                          │
    │  ② API呼び出し（ブラウザ操作なし）                              │
    │                                                                  │
    │  ※ リフレッシュトークンが無効（90日以上経過）の場合は           │
    │    サイレント認証を試行し、失敗時のみブラウザ認証               │
    │                                                                  │
    └─────────────────────────────────────────────────────────────────┘
    ```

    #### 10.4.3 トークンキャッシュ機能

    毎回の認証操作を避けるため、トークンキャッシュ機能を実装しています。

    | 項目 | 説明 |
    | ---- | ---- |
    | キャッシュ場所 | `%TEMP%\ic-test-azure-ad-token.json` |
    | 保存内容 | access_token, refresh_token, expires_at, client_id |
    | 有効期間 | アクセストークン: 約1時間 / リフレッシュトークン: 90日 |
    | 自動更新 | 期限切れ時にリフレッシュトークンで自動取得 |

    ```text
    【トークンキャッシュの動作】

    API呼び出し時:
    ┌──────────────────┐
    │ キャッシュ確認   │
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐     Yes     ┌──────────────────┐
    │ 有効なトークン？  │────────────▶│ そのまま使用     │
    └────────┬─────────┘             └──────────────────┘
             │ No
             ▼
    ┌──────────────────┐     Yes     ┌──────────────────┐
    │ リフレッシュ可？  │────────────▶│ 自動でトークン   │
    │ (refresh_token)  │             │ 更新             │
    └────────┬─────────┘             └──────────────────┘
             │ No
             ▼
    ┌──────────────────┐     Yes     ┌──────────────────┐
    │ サイレント認証   │────────────▶│ トークン取得     │
    │ (prompt=none)    │             │ ブラウザ操作なし │
    └────────┬─────────┘             └──────────────────┘
             │ No（未ログインの場合）
             ▼
    ┌──────────────────┐
    │ ブラウザ認証     │ ← 初回または90日以上経過時
    │ （自動でブラウザ │   ブラウザが自動で開く
    │   が開く）       │   ユーザーがログインして完了
    └──────────────────┘
    ```

    #### 10.4.4 Azureセットアップ手順（手動）

    以下の手順でAzure AD認証を設定します。

    **ステップ1: App Registrationの作成**

    ```text
    Azure Portal → Microsoft Entra ID → アプリの登録 → 新規登録

    名前: func-ic-test-evaluation-auth（任意）
    サポートされているアカウントの種類: この組織ディレクトリのみ
    リダイレクトURI: （空欄のまま）
    ```

    **ステップ2: API識別子URIとスコープの設定**

    ```text
    作成したApp Registration → APIの公開

    1. アプリケーションID URIの設定:
       「設定」→ api://{clientId} の形式で自動生成

    2. スコープの追加:
       「スコープの追加」をクリック
       スコープ名: user_impersonation
       同意できるのは: 管理者とユーザー
       管理者の同意の表示名: IC Test Evaluation API へのアクセス
       管理者の同意の説明: 内部統制テスト評価APIへのアクセスを許可します
       状態: 有効
    ```

    **ステップ3: リダイレクトURIとパブリッククライアントフローの設定**

    ```text
    App Registration → 認証

    1. リダイレクトURIの追加（ブラウザ認証に必要）:
       「プラットフォームを追加」→「モバイル アプリケーションとデスクトップ アプリケーション」
       カスタム リダイレクトURI:
         - http://localhost:8400/callback
         - http://localhost:8401/callback
         - http://localhost:8402/callback
         - ... （8400-8499の範囲で必要な分だけ追加）

       ※ 複数ポートを登録しておくと、ポート競合時に自動的に別ポートを使用

    2. 詳細設定:
       「パブリック クライアント フローを許可する」: はい

       ※ Device Code Flow（フォールバック用）に必要な設定
    ```

    **ステップ4: Azure ADグループの作成**

    ```text
    Azure Portal → Microsoft Entra ID → グループ → 新しいグループ

    グループの種類: セキュリティ
    グループ名: IC-Test-Users
    グループの説明: 内部統制テストツール利用者
    メンバー: 許可するユーザーを追加
    ```

    **ステップ5: Service Principal（Enterprise Application）の設定**

    ```text
    Azure Portal → Microsoft Entra ID → エンタープライズアプリケーション
    → 作成したアプリ名を検索 → プロパティ

    1. ユーザーの割り当てが必要ですか？: はい

    2. ユーザーとグループ → 追加
       → IC-Test-Users グループを選択
    ```

    **ステップ6: Function Appの認証設定**

    ```text
    Azure Portal → Function App → 認証 → IDプロバイダーの追加

    IDプロバイダー: Microsoft
    アプリの登録の種類: 既存のアプリの登録の詳細を指定する
    アプリケーション（クライアント）ID: {App RegistrationのクライアントID}
    クライアントシークレット: （空欄）
    発行者のURL: https://login.microsoftonline.com/{tenantId}/v2.0
    許可されるトークン対象ユーザー:
      - api://{clientId}
      - {clientId}
    認証されていない要求: HTTP 401 Unauthorized
    トークンストア: 有効
    ```

    **ステップ7: Function Appコードの設定**

    `platforms/azure/function_app.py` で `AuthLevel.ANONYMOUS` を設定：

    ```python
    # Azure ADによるプラットフォームレベル認証を使用
    # Functions Keyは不要（AuthLevel.ANONYMOUS）
    app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)
    ```

    #### 10.4.5 Azureセットアップ手順（自動スクリプト）

    `scripts/setup-azure-ad-auth.ps1` を使用して自動セットアップできます。

    **前提条件**

    - Azure CLI (`az`) がインストール済み
    - Function App が既にデプロイ済み
    - 適切な権限（Application Administrator または Global Administrator）

    **実行方法**

    ```powershell
    # プロジェクトディレクトリに移動
    cd c:\path\to\ic-test-ai-agent

    # スクリプトを実行
    .\scripts\setup-azure-ad-auth.ps1 `
        -FunctionAppName "func-ic-test-evaluation" `
        -ResourceGroup "rg-ic-test" `
        -GroupName "IC-Test-Users"
    ```

    **スクリプトが行う処理**

    1. Azure CLIログイン確認
    2. Function App存在確認
    3. App Registration作成（または既存を使用）
    4. API識別子URIとスコープ設定
    5. **リダイレクトURI設定（localhost:8400-8409）**
    6. パブリッククライアントフロー有効化
    7. Service Principal作成
    8. ユーザー割り当て必須設定
    9. Azure ADグループ作成（または既存を使用）
    10. 現在のユーザーをグループに追加
    11. グループをアプリに割り当て
    12. Function App認証設定
    13. 設定情報の出力

    **出力例**

    ```text
    ============================================================
    セットアップ完了！
    ============================================================

    以下の設定を setting.json に追加してください:

    {
        "api": {
            "provider": "AZURE",
            "authType": "azureAd",
            "endpoint": "https://func-ic-test-evaluation.azurewebsites.net/api/evaluate"
        },
        "azureAd": {
            "tenantId": "1f6ccb61-70c2-46fa-bab8-55e19b2fcc9b",
            "clientId": "262cd06b-dcd2-4237-9eb3-4c0536a665b1",
            "scope": "api://262cd06b-dcd2-4237-9eb3-4c0536a665b1/user_impersonation openid offline_access"
        }
    }
    ```

    #### 10.4.6 クライアント設定（setting.json）

    ```json
    {
        "apiClient": "POWERSHELL",
        "asyncMode": true,
        "pollingIntervalSec": 5,
        "api": {
            "provider": "AZURE",
            "endpoint": "https://func-ic-test-evaluation.azurewebsites.net/api/evaluate",
            "authType": "azureAd"
        },
        "azureAd": {
            "tenantId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            "clientId": "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy",
            "scope": "api://yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy/user_impersonation openid offline_access"
        }
    }
    ```

    **設定項目の説明**

    | 項目 | 説明 | 確認場所 |
    | ---- | ---- | -------- |
    | `authType` | 認証方式。`azureAd` を指定 | - |
    | `tenantId` | Azure ADテナントID | Azure Portal → Entra ID → 概要 |
    | `clientId` | App RegistrationのクライアントID | App Registration → 概要 |
    | `scope` | APIスコープ。`user_impersonation` を含める | App Registration → APIの公開 |

    > **スコープの形式**: `api://{clientId}/user_impersonation openid offline_access`
    > - `user_impersonation`: APIアクセス権限
    > - `openid`: ユーザー情報取得
    > - `offline_access`: リフレッシュトークン取得（キャッシュに必要）

    #### 10.4.7 初回認証の流れ

    初回実行時、以下のフローで認証が行われます：

    ```text
    ┌─────────────────────────────────────────────────────────┐
    │  ブラウザ認証フロー（Authorization Code Flow + PKCE）   │
    ├─────────────────────────────────────────────────────────┤
    │                                                         │
    │  1. Excel VBAからPowerShell起動                         │
    │     ↓                                                   │
    │  2. サイレント認証を試行（prompt=none）                  │
    │     ├── 成功: トークン取得 → API呼び出しへ             │
    │     └── 失敗: ブラウザ認証へ                           │
    │     ↓                                                   │
    │  3. ブラウザが自動で開く                                │
    │     ┌───────────────────────────────────────────────┐   │
    │     │  Azure ADログインページ                        │   │
    │     │                                                │   │
    │     │  会社アカウントでサインイン                    │   │
    │     │  ┌──────────────────────────┐                 │   │
    │     │  │ user@company.com         │                 │   │
    │     │  └──────────────────────────┘                 │   │
    │     │                                                │   │
    │     │  初回は権限承認ダイアログも表示                │   │
    │     │  「IC Test Evaluation APIへのアクセス」       │   │
    │     │  [承諾] [キャンセル]                           │   │
    │     └───────────────────────────────────────────────┘   │
    │     ↓                                                   │
    │  4. 認証成功 → ブラウザに「認証成功」と表示            │
    │     ↓                                                   │
    │  5. トークン取得 → API呼び出し実行                     │
    │                                                         │
    └─────────────────────────────────────────────────────────┘

    ユーザーの操作:
    1. Excelマクロを実行
    2. ブラウザが自動で開く（既にログイン済みならスキップ）
    3. 会社アカウントでサインイン
    4. 権限の承認（初回のみ）
    5. ブラウザに「認証が完了しました」と表示されれば完了
       （ブラウザを閉じてOK）

    ※ 2回目以降はキャッシュされたトークンを使用するため、
      ブラウザは開きません（約90日間有効）
    ※ ブラウザでAzure ADに既にログイン済みの場合は、
      サイレント認証で自動的にトークンが取得されます
    ```

    **Device Code Flow（フォールバック）**

    ブラウザ認証が失敗した場合（ファイアウォール等でlocalhostへのリダイレクトが
    ブロックされる環境）、Device Code Flowにフォールバックします：

    ```text
    ┌─────────────────────────────────────────────────────────┐
    │  PowerShellウィンドウに表示されるメッセージ              │
    ├─────────────────────────────────────────────────────────┤
    │                                                         │
    │  ========================================                │
    │  Azure AD 認証（Device Code）                            │
    │  ========================================                │
    │                                                         │
    │  URL: https://microsoft.com/devicelogin                 │
    │  Code: ABC123DEF                                        │
    │                                                         │
    │  上記URLにアクセスしてコードを入力してください           │
    │                                                         │
    └─────────────────────────────────────────────────────────┘
    ```

    #### 10.4.8 認証テスト

    `scripts/test-azure-ad-auth.ps1` で認証をテストできます：

    ```powershell
    .\scripts\test-azure-ad-auth.ps1 `
        -TenantId "1f6ccb61-70c2-46fa-bab8-55e19b2fcc9b" `
        -ClientId "262cd06b-dcd2-4237-9eb3-4c0536a665b1" `
        -FunctionUrl "https://func-ic-test-evaluation.azurewebsites.net/api/health" `
        -Scope "api://262cd06b-dcd2-4237-9eb3-4c0536a665b1/user_impersonation openid offline_access"
    ```

    **成功時の出力**

    ```text
    ============================================================
    テスト成功！
    ============================================================

    レスポンス:
    {
        "status": "healthy",
        "llm_configured": true,
        ...
    }
    ```

    #### 10.4.9 トラブルシューティング

    | エラー | 原因 | 対策 |
    | ------ | ---- | ---- |
    | AADSTS7000218 | Public Client Flow未有効 | App Registration → 認証 → パブリッククライアントフロー: はい |
    | AADSTS90009 | スコープ形式エラー | `api://{clientId}/user_impersonation` 形式を使用 |
    | 401 Unauthorized | トークン対象不一致 | Function App認証の許可されるトークン対象ユーザーに `api://{clientId}` と `{clientId}` の両方を追加 |
    | 403 Forbidden | グループ未割り当て | Enterprise App → ユーザーとグループ でグループを割り当て |

    #### 10.4.10 セキュリティのベストプラクティス

    ```text
    【推奨構成】

    ┌────────────────────────────────────────────────────────────┐
    │  Azure Functions                                           │
    │                                                            │
    │  function_app.py:                                          │
    │    AuthLevel.ANONYMOUS  ← Functions Keyを使用しない        │
    │                                                            │
    │  認証設定:                                                  │
    │    ・Azure ADプラットフォーム認証: 有効                    │
    │    ・認証されていない要求: HTTP 401                        │
    │    ・許可されるトークン対象: api://{clientId}, {clientId} │
    │                                                            │
    │  Enterprise Application:                                   │
    │    ・ユーザー割り当て必須: はい                            │
    │    ・許可グループ: IC-Test-Users                          │
    │                                                            │
    └────────────────────────────────────────────────────────────┘

    【セキュリティメリット】

    1. 認証情報の流出リスク低減
       - Functions Keyを設定ファイルに記載不要
       - トークンは一時的（1時間）で自動失効

    2. アクセス制御の一元管理
       - Azure ADグループでユーザー管理
       - 退職者は即座にアクセス無効化可能

    3. 監査ログ
       - Azure ADでアクセスログを自動記録
       - 誰がいつアクセスしたか追跡可能
    ```

    ---

    ## 11. テスト

    ### 11.1 テスト構成概要

    本システムは、以下のテスト構成を採用しています。

    ```text
    ┌─────────────────────────────────────────────────────────────────┐
    │                      テスト構成                                  │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                  │
    │  【Pythonバックエンド】                                          │
    │  ┌──────────────────────────────────────────────────────────┐   │
    │  │  pytest フレームワーク（カバレッジ: 62%）                   │   │
    │  │  ├── ユニットテスト（約500件 - 外部依存なし、高速実行）    │   │
    │  │  ├── E2Eテスト（26件 - ハンドラー全体フロー）             │   │
    │  │  └── 統合テスト（約10件 - Azure/クラウド接続が必要）      │   │
    │  └──────────────────────────────────────────────────────────┘   │
    │                                                                  │
    │  【品質ゲート】                                                  │
    │  ┌──────────────────────────────────────────────────────────┐   │
    │  │  pre-commit hooks（コミット前自動チェック）                  │   │
    │  │  ├── flake8 (構文エラー検出)                                │   │
    │  │  ├── bandit (セキュリティスキャン)                          │   │
    │  │  ├── detect-secrets (シークレット検出)                      │   │
    │  │  └── trailing-whitespace, check-yaml, check-json 等         │   │
    │  └──────────────────────────────────────────────────────────┘   │
    │                                                                  │
    │  【CI/CD (GitHub Actions)】                                      │
    │  ┌──────────────────────────────────────────────────────────┐   │
    │  │  ├── flake8 リンティング                                   │   │
    │  │  ├── bandit セキュリティスキャン                            │   │
    │  │  ├── pytest + coverage (閾値: 40%)                         │   │
    │  │  ├── Codecov カバレッジレポート                             │   │
    │  │  ├── Docker ビルド + ヘルスチェック                         │   │
    │  │  └── Dependabot (依存パッケージ自動更新)                   │   │
    │  └──────────────────────────────────────────────────────────┘   │
    │                                                                  │
    │  【PowerShell / VBA】                                            │
    │  ┌──────────────────────────────────────────────────────────┐   │
    │  │  手動テスト                                                │   │
    │  │  ├── scripts/test-azure-ad-auth.ps1 (Azure AD認証)        │   │
    │  │  └── Excel上での統合動作確認 (SampleData使用)              │   │
    │  └──────────────────────────────────────────────────────────┘   │
    │                                                                  │
    └─────────────────────────────────────────────────────────────────┘
    ```

    ### 11.2 Pythonテストの実行

    #### 11.2.1 前提条件

    ```powershell
    # 仮想環境を有効化
    .\.venv\Scripts\Activate.ps1

    # テスト依存パッケージをインストール
    pip install -r requirements.txt -r requirements-dev.txt
    ```

    #### 11.2.2 テスト実行コマンド

    | コマンド | 説明 |
    | -------- | ---- |
    | `python -m pytest tests/ -v` | 全テスト実行（530+件） |
    | `python -m pytest tests/ -v -m "unit"` | ユニットテストのみ |
    | `python -m pytest tests/ -v -m "integration"` | 統合テストのみ（クラウド接続必要） |
    | `python -m pytest tests/ -v --cov=src --cov-report=term-missing` | カバレッジ付き実行 |
    | `python -m pytest tests/ -v -m "not integration"` | 統合テスト除外（CI用） |
    | `python -m pytest tests/test_e2e.py -v` | E2Eテストのみ |

    #### 11.2.3 テストファイル構成

    ```text
    tests/
    ├── conftest.py                 # 共通フィクスチャ（.env自動読み込み）
    │
    │  # --- コアモジュール UT ---
    ├── test_base_task.py           # 基底クラス・データ構造テスト
    ├── test_tasks.py               # A1-A8タスク属性・基本動作
    ├── test_tasks_execute.py       # A1-A8タスク execute() ロジック
    ├── test_document_processor.py  # ドキュメント処理
    ├── test_handlers.py            # ハンドラー UT
    ├── test_graph_orchestrator.py  # GraphOrchestrator UT（76件）
    ├── test_async_handlers.py      # 非同期ハンドラー UT（38件）
    ├── test_prompts.py             # プロンプト管理 UT
    │
    │  # --- インフラストラクチャ UT ---
    ├── test_llm_factory.py         # LLMファクトリー
    ├── test_ocr_factory.py         # OCRファクトリー
    ├── test_job_storage.py         # ジョブストレージ（Memory/Azure）
    ├── test_job_storage_aws_gcp.py # ジョブストレージ（AWS/GCP）
    │
    │  # --- プラットフォーム UT ---
    ├── test_platform_azure.py      # Azure Functions エントリポイント
    ├── test_platform_aws.py        # AWS Lambda エントリポイント
    ├── test_platform_gcp.py        # GCP Cloud Functions エントリポイント
    ├── test_local_platform.py      # ローカルサーバー
    │
    │  # --- E2E / 統合テスト ---
    ├── test_e2e.py                 # E2Eテスト（ハンドラー全体フロー）
    ├── test_integration_local.py   # ローカル統合テスト
    ├── test_integration_cloud.py   # クラウド統合テスト
    └── test_integration_models.py  # LLMモデル統合テスト
    ```

    **合計: 530+件**（うち統合テストはクラウド接続が必要）
    **コードカバレッジ: 62%**

    ### 11.3 テスト対象モジュール

    | モジュール | テストファイル | カバー内容 |
    | ---------- | -------------- | ---------- |
    | `core/tasks/base_task.py` | test_base_task.py | TaskType, TaskResult, EvidenceFile, AuditContext |
    | `core/tasks/a1-a8` | test_tasks.py, test_tasks_execute.py | 属性・基本動作 + execute()ロジック |
    | `core/document_processor.py` | test_document_processor.py | テキスト/PDF/Excel抽出 |
    | `core/handlers.py` | test_handlers.py, test_e2e.py | ハンドラーUT + E2Eフロー |
    | `core/graph_orchestrator.py` | test_graph_orchestrator.py | データクラス, 条件分岐, ノード, 後処理 |
    | `core/async_handlers.py` | test_async_handlers.py | submit/status/results/cancel, シングルトン |
    | `core/prompts.py` | test_prompts.py | PromptManager, フィードバック注入 |
    | `infrastructure/llm_factory.py` | test_llm_factory.py | LLMProvider, LLMFactory |
    | `infrastructure/ocr_factory.py` | test_ocr_factory.py | OCRProvider, OCRFactory |
    | `infrastructure/job_storage/` | test_job_storage.py, test_job_storage_aws_gcp.py | Memory/Azure/AWS/GCPストレージ・キュー |
    | `platforms/azure/` | test_platform_azure.py | Azure Functions エントリポイント |
    | `platforms/aws/` | test_platform_aws.py | Lambda ヘルパー・ルーティング・エンドポイント |
    | `platforms/gcp/` | test_platform_gcp.py | Cloud Functions エントリポイント |

    ### 11.4 テストマーカー

    pytest.iniで以下のマーカーを定義しています:

    ```ini
    [pytest]
    markers =
        unit: Unit tests (fast, no external dependencies)
        integration: Integration tests (may require external services)
        slow: Slow tests (skip with -m "not slow")
        azure: Tests requiring Azure services
        aws: Tests requiring AWS services
        gcp: Tests requiring GCP services
        local: Tests for local/on-premise environment (Ollama, Tesseract)
        llm: Tests requiring LLM API
        ocr: Tests requiring OCR services
    ```

    | マーカー | 説明 | 実行タイミング |
    | -------- | ---- | -------------- |
    | `@pytest.mark.unit` | 外部依存なしの高速テスト | 開発中常時 |
    | `@pytest.mark.integration` | クラウド接続が必要なテスト | CI/CD、デプロイ前 |
    | `@pytest.mark.azure` | Azureサービス固有テスト | Azure環境でのみ |
    | `@pytest.mark.aws` | AWSサービス固有テスト | AWS環境でのみ |
    | `@pytest.mark.gcp` | GCPサービス固有テスト | GCP環境でのみ |
    | `@pytest.mark.llm` | LLM API接続が必要なテスト | API Key設定時 |
    | `@pytest.mark.ocr` | OCRサービスが必要なテスト | OCR設定時 |
    | `@pytest.mark.slow` | 実行が遅いテスト | `-m "not slow"` で除外可 |
    | `@pytest.mark.asyncio` | 非同期テスト | pytest-asyncioが自動検出 |

    ### 11.5 Azure統合テスト

    Azure Blob Storage / Queue Storageの実接続テストです。

    #### 11.5.1 前提条件

    ```bash
    # .envファイルに接続文字列を設定
    AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...
    ```

    #### 11.5.2 テスト対象

    | テスト名 | 対象 | 操作 |
    | -------- | ---- | ---- |
    | `test_store_and_restore_evidence_files_real` | Blob Storage | ファイル保存・復元・削除 |
    | `test_enqueue_dequeue_real` | Queue Storage | メッセージ追加・取得・クリア |

    #### 11.5.3 実行方法

    ```bash
    # Azure統合テストのみ実行
    python -m pytest tests/test_job_storage.py -v -m "integration and azure"

    # 全テスト実行（Azure統合テスト含む）
    python -m pytest tests/ -v
    ```

    #### 11.5.4 テスト分離

    統合テストは以下の方法で本番環境から分離されています：
    - Blobテスト: 一意のジョブID（`test-job-{uuid}`）を使用し、テスト後に削除
    - Queueテスト: テスト専用キュー名（`test-evaluation-jobs`）を使用し、テスト後にクリア

    ### 11.6 共通フィクスチャ（conftest.py）

    テスト間で共有するモックとサンプルデータを定義しています。

    | フィクスチャ名 | 説明 |
    | -------------- | ---- |
    | `sample_base64_text` | テスト用Base64エンコードテキスト |
    | `sample_evidence_dict` | 証跡ファイル辞書形式 |
    | `sample_request_item` | APIリクエストアイテム形式 |
    | `sample_audit_context` | AuditContextオブジェクト |
    | `mock_llm` | LLMクライアントモック |
    | `mock_ocr_client` | OCRクライアントモック |
    | `mock_job_storage` | ジョブストレージモック |
    | `mock_azure_env` | Azure環境変数モック |

    **注意**: conftest.pyは`.env`ファイルを自動的に読み込みます（統合テスト用）。

    ### 11.7 PowerShellテスト

    #### 11.7.1 Azure AD認証テスト

    `scripts/test-azure-ad-auth.ps1` を使用して認証フローをテストします。

    ```powershell
    .\scripts\test-azure-ad-auth.ps1 `
        -TenantId "your-tenant-id" `
        -ClientId "your-client-id" `
        -FunctionUrl "https://your-function.azurewebsites.net/api/health"
    ```

    **テスト内容**:
    - Azure ADトークン取得
    - Function AppへのAPI呼び出し
    - 認証エラーの診断

    ### 11.8 VBA/Excelテスト

    VBAコードの自動テストフレームワークは未実装です。以下の手動テストを実施してください。

    #### 11.8.1 手動テスト手順

    1. **テストデータ準備**
       - `SampleData/` フォルダに証跡ファイルを配置
       - Excelテストシートを作成（ID, ControlDescription, TestProcedure, EvidenceLink列）

    2. **VBAモジュール動作確認**
       - `LoadSettings()`: setting.json読み込み確認
       - `GenerateJsonForBatch()`: JSON生成確認
       - `WriteResponseToExcel()`: 結果書き戻し確認

    3. **統合動作確認**
       - `ProcessWithApi()` をローカルAPIで実行
       - 評価結果がExcelに正しく書き込まれることを確認

    ### 11.9 CI/CD パイプライン

    `.github/workflows/ci.yml` で以下のパイプラインが実行されます:

    ```text
    ┌──────────────────────────────────────────────────────────┐
    │  CI Pipeline (main/develop ブランチ push & PR)            │
    ├──────────────────────────────────────────────────────────┤
    │                                                            │
    │  [Test Job]                                                │
    │  ├── Python 3.11 セットアップ                              │
    │  ├── pip install (requirements.txt + requirements-dev.txt) │
    │  ├── flake8 リンティング (E9,F63,F7,F82)                  │
    │  ├── bandit セキュリティスキャン (--severity-level=high)   │
    │  ├── pytest + coverage (閾値: 40%, Codecovアップロード)    │
    │  └── bandit-report.json アーティファクト保存               │
    │                                                            │
    │  [Docker Build Job] (Test成功後)                           │
    │  ├── Docker Buildx ビルド                                  │
    │  └── コンテナ起動 + /health ヘルスチェック                 │
    │                                                            │
    │  [Docker Push Job] (mainブランチpushのみ)                  │
    │  ├── Azure Container Registry                              │
    │  ├── GCP Artifact Registry                                 │
    │  └── AWS ECR                                               │
    │                                                            │
    └──────────────────────────────────────────────────────────┘
    ```

    ### 11.10 pre-commit hooks

    `.pre-commit-config.yaml` で、コミット前に以下のチェックが自動実行されます:

    | フック | 説明 |
    | ------ | ---- |
    | trailing-whitespace | 末尾空白の除去 |
    | end-of-file-fixer | ファイル末尾改行の統一 |
    | check-yaml / check-json | YAML/JSON構文チェック |
    | check-merge-conflict | マージコンフリクトマーカー検出 |
    | check-added-large-files | 500KB超ファイルの検出 |
    | debug-statements | デバッグ文 (pdb等) の検出 |
    | flake8 | Python構文エラー検出 (src/のみ) |
    | bandit | セキュリティ脆弱性検出 (src/のみ) |
    | detect-secrets | シークレット（APIキー等）の検出 |

    ```powershell
    # インストール
    pip install pre-commit
    pre-commit install

    # 手動実行
    pre-commit run --all-files
    ```

    ### 11.11 Dependabot

    `.github/dependabot.yml` で以下の依存パッケージが週次で自動更新されます:

    | エコシステム | 対象 | 更新頻度 |
    | ------------ | ---- | -------- |
    | pip | Python パッケージ (requirements.txt) | 毎週月曜 |
    | github-actions | GitHub Actions バージョン | 毎週月曜 |
    | docker | Docker ベースイメージ | 毎月 |

    ---

    ## 12. クラウドリソース詳細

    本セクションでは、このシステムで使用されるすべてのクラウドリソースについて、
    初心者の方でも理解できるよう詳細に解説します。

    ### 12.1 マルチクラウドアーキテクチャの全体像

    本システムは「マルチクラウド対応」を設計の柱としており、
    Azure、AWS、GCPのいずれでも同じソースコードで動作します。

    ```text
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                    マルチクラウドアーキテクチャ                          │
    ├─────────────────────────────────────────────────────────────────────────┤
    │                                                                         │
    │  ┌─────────────────────────────────────────────────────────────────┐   │
    │  │                     共通ソースコード (src/)                       │   │
    │  │  ┌──────────────┐  ┌───────────────┐  ┌──────────────────────┐ │   │
    │  │  │  handlers.py │  │ llm_factory.py│  │  job_storage/*.py    │ │   │
    │  │  │  (APIハンドラ) │  │  (LLM抽象化)   │  │  (ストレージ抽象化)    │ │   │
    │  │  └──────────────┘  └───────────────┘  └──────────────────────┘ │   │
    │  └─────────────────────────────────────────────────────────────────┘   │
    │                                    │                                    │
    │                ┌───────────────────┼───────────────────┐                │
    │                ▼                   ▼                   ▼                │
    │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐      │
    │  │      Azure       │  │       GCP        │  │       AWS        │      │
    │  ├──────────────────┤  ├──────────────────┤  ├──────────────────┤      │
    │  │ 【計算リソース】   │  │ 【計算リソース】   │  │ 【計算リソース】   │      │
    │  │  Azure Functions │  │  Cloud Functions │  │   AWS Lambda    │      │
    │  │                  │  │                  │  │  + API Gateway  │      │
    │  ├──────────────────┤  ├──────────────────┤  ├──────────────────┤      │
    │  │ 【AIサービス】    │  │ 【AIサービス】    │  │ 【AIサービス】    │      │
    │  │  Azure AI Foundry│  │   Vertex AI      │  │  Amazon Bedrock │      │
    │  │  (GPT-5, Claude) │  │  (Gemini 2.5/3)  │  │  (Claude Opus)  │      │
    │  ├──────────────────┤  ├──────────────────┤  ├──────────────────┤      │
    │  │ 【ストレージ】    │  │ 【ストレージ】    │  │ 【ストレージ】    │      │
    │  │  Table Storage   │  │   Firestore     │  │   DynamoDB      │      │
    │  │  Blob Storage    │  │  Cloud Storage  │  │      S3         │      │
    │  │  Queue Storage   │  │  Cloud Tasks    │  │      SQS        │      │
    │  └──────────────────┘  └──────────────────┘  └──────────────────┘      │
    │                                                                         │
    └─────────────────────────────────────────────────────────────────────────┘
    ```

    ### 12.2 Azure クラウドリソース

    #### 12.2.1 Azure AI Foundry（旧 Azure AI Studio）

    **Azure AI Foundryとは？**

    Azure AI Foundryは、MicrosoftがAzure上で提供する統合AIプラットフォームです。
    OpenAIのGPTシリーズだけでなく、Anthropic Claude、Meta Llama、Mistralなど
    複数のAIモデルを統一されたAPIで利用できます。

    ```text
    【Azure AI Foundry の概念図】

    ┌─────────────────────────────────────────────────────────────────┐
    │                    Azure AI Foundry                             │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                 │
    │  ┌───────────────────────────────────────────────────────────┐ │
    │  │                    Model Catalog（モデルカタログ）           │ │
    │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │ │
    │  │  │  GPT-5  │ │ Claude  │ │  Llama  │ │ Mistral │        │ │
    │  │  │  Nano   │ │ Opus 4.6│ │   3.x   │ │   7B    │        │ │
    │  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘        │ │
    │  └───────────────────────────────────────────────────────────┘ │
    │                                                                 │
    │  【メリット】                                                   │
    │  - 複数モデルを単一エンドポイントで利用                          │
    │  - モデル切り替えが環境変数の変更だけで完了                       │
    │  - Azure ADによるエンタープライズ認証                            │
    │  - SLA（サービスレベル保証）付き                                 │
    │                                                                 │
    └─────────────────────────────────────────────────────────────────┘
    ```

    **利用可能なモデル（2026年2月時点・動作確認済み）**

    | モデル | 説明 | 推奨用途 |
    |--------|------|---------|
    | `gpt-5.2` | 最新フラッグシップ、企業エージェント向け | 複雑な推論 |
    | `gpt-5-nano` | 高速・低コスト、推論系モデル | **本システム推奨** |
    | `claude-opus-4-6` | Anthropic最高性能、1Mトークン対応 | 大規模文書処理 |
    | `claude-sonnet-4-5` | バランス型 | 汎用処理 |

    **環境変数設定**

    ```ini
    # .envファイル
    LLM_PROVIDER=AZURE_FOUNDRY
    AZURE_FOUNDRY_ENDPOINT=https://your-project.region.models.ai.azure.com
    AZURE_FOUNDRY_API_KEY=your-api-key
    AZURE_FOUNDRY_MODEL=gpt-5-nano
    AZURE_FOUNDRY_API_VERSION=2025-01-01-preview
    ```

    #### 12.2.2 Azure Functions

    **Azure Functionsとは？**

    Azure Functionsは、サーバーレスコンピューティングサービスです。
    「サーバーレス」とは、サーバーの管理が不要という意味で、
    コードを書くだけで自動的にスケールする環境を提供します。

    ```text
    【従来のサーバー vs サーバーレス】

    従来のサーバー:
    ┌─────────────────────────────────────────────────────────────────┐
    │  あなたの責任範囲                                                │
    │  ┌─────────────────────────────────────────────────────────┐   │
    │  │  OS更新 │ セキュリティパッチ │ スケーリング │ 監視 │ 冗長化 │   │
    │  └─────────────────────────────────────────────────────────┘   │
    │  + コード開発                                                   │
    └─────────────────────────────────────────────────────────────────┘

    サーバーレス (Azure Functions):
    ┌─────────────────────────────────────────────────────────────────┐
    │  Azureが管理（あなたは気にしなくてOK）                            │
    │  ┌─────────────────────────────────────────────────────────┐   │
    │  │  OS更新 │ セキュリティパッチ │ スケーリング │ 監視 │ 冗長化 │   │
    │  └─────────────────────────────────────────────────────────┘   │
    ├─────────────────────────────────────────────────────────────────┤
    │  あなたの責任範囲: コード開発のみ！                              │
    └─────────────────────────────────────────────────────────────────┘
    ```

    **本システムでの使用**

    | リソース名 | 説明 | 設定値 |
    |-----------|------|--------|
    | Function App | アプリケーションホスト | `func-ic-test-evaluation` |
    | ランタイム | 実行環境 | Python 3.11 |
    | プラン | 課金モデル | 従量課金（Consumption） |
    | タイムアウト | 最大実行時間 | 10分 |

    **エンドポイント一覧**

    | パス | メソッド | 説明 | モード |
    |------|---------|------|--------|
    | `/api/evaluate` | POST | 同期評価 | asyncMode: false |
    | `/api/evaluate/submit` | POST | 非同期ジョブ送信 | asyncMode: true |
    | `/api/evaluate/status/{job_id}` | GET | ステータス確認 | asyncMode: true |
    | `/api/evaluate/results/{job_id}` | GET | 結果取得 | asyncMode: true |
    | `/api/health` | GET | ヘルスチェック | 共通 |
    | `/api/config` | GET | 設定確認 | 共通 |

    #### 12.2.3 Azure Storage（ストレージサービス群）

    Azure Storageは、クラウド上のデータ保存サービスです。
    本システムでは3種類のストレージを使用します。

    ```text
    【Azure Storageの種類と用途】

    ┌─────────────────────────────────────────────────────────────────┐
    │                    Azure Storage Account                        │
    │                   (ストレージアカウント)                          │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                 │
    │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
    │  │  Table Storage  │  │  Blob Storage   │  │  Queue Storage  │ │
    │  │  (テーブル)      │  │  (ファイル)      │  │  (メッセージ)    │ │
    │  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤ │
    │  │ ジョブ状態管理   │  │  証跡ファイル    │  │  ジョブ通知     │ │
    │  │                 │  │  (Base64保存)   │  │  (キュートリガー)│ │
    │  │ EvaluationJobs  │  │ evidence-files │  │ evaluation-jobs │ │
    │  │ テーブル        │  │ コンテナ        │  │ キュー          │ │
    │  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
    │                                                                 │
    └─────────────────────────────────────────────────────────────────┘
    ```

    **Table Storage（テーブルストレージ）**

    NoSQLデータベースの一種で、構造化データを保存します。
    Excelのスプレッドシートに似たイメージで理解できます。

    | 概念 | 説明 | 本システムでの例 |
    |------|------|-----------------|
    | テーブル | データの入れ物 | `EvaluationJobs` |
    | PartitionKey | グループ分けキー | `tenant_id`（テナントID） |
    | RowKey | 一意識別子 | `job_id`（ジョブID） |
    | プロパティ | 列（データ項目） | `status`, `progress`, `results` |

    **Blob Storage（ブロブストレージ）**

    ファイルを保存するためのストレージです。
    「Blob」は「Binary Large Object」の略で、大きなファイルを意味します。

    ```text
    【64KB制限対策】

    Azure Table Storageは1行あたり64KBまでの制限があります。
    証跡ファイル（PDF等）はこれを超えることがあるため、
    Blob Storageに分離して保存します。

    ジョブ送信時:
    ┌────────────┐     ┌────────────────┐
    │ 証跡ファイル │ ──▶ │ Blob Storage   │ ──▶ 参照情報のみをTable Storageに保存
    │ (10MB PDF) │     │ (制限なし)      │
    └────────────┘     └────────────────┘

    ジョブ処理時:
    ┌────────────────┐     ┌────────────┐
    │ Table Storage  │ ──▶ │ 参照から復元 │ ──▶ 評価処理
    │ (参照情報のみ)  │     │            │
    └────────────────┘     └────────────┘
    ```

    **Queue Storage（キューストレージ）**

    メッセージキューサービスです。
    「キュー」は「待ち行列」を意味し、処理待ちのタスクを順番に管理します。

    ```text
    【非同期処理のフロー】

    1. APIがジョブを受信
    2. ジョブIDをQueueに追加 ──▶ [job-001] [job-002] [job-003] ...
    3. 即座にジョブIDを返却      │
                                ▼ キュートリガーが自動起動
    4. Azure Functionsワーカーがメッセージを取得
    5. ジョブを処理
    6. 結果をTable Storageに保存
    ```

    **環境変数設定**

    ```ini
    # 接続文字列（すべてのStorageサービスで共通）
    AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=stictestevaluation;AccountKey=xxx;EndpointSuffix=core.windows.net
    ```

    ### 12.3 AWS クラウドリソース

    #### 12.3.1 Amazon Bedrock

    **Amazon Bedrockとは？**

    Amazon Bedrockは、AWSが提供する基盤モデル（Foundation Model）サービスです。
    Anthropic Claude、Meta Llama、Amazon Titanなど複数のAIモデルを利用できます。

    ```text
    【Amazon Bedrockの概念図】

    ┌─────────────────────────────────────────────────────────────────┐
    │                      Amazon Bedrock                             │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                 │
    │  ┌───────────────────────────────────────────────────────────┐ │
    │  │                Foundation Models（基盤モデル）              │ │
    │  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │ │
    │  │  │ Claude  │ │  Titan  │ │  Llama  │ │ Mistral │        │ │
    │  │  │ Opus 4.6│ │ Premier │ │   3.2   │ │  Large  │        │ │
    │  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘        │ │
    │  └───────────────────────────────────────────────────────────┘ │
    │                                                                 │
    │  【特徴】                                                       │
    │  - IAMによる認証（AWSの標準認証）                               │
    │  - Lambda等AWSサービスとのシームレスな連携                       │
    │  - Inference Profile（推論プロファイル）によるリージョン最適化   │
    │                                                                 │
    └─────────────────────────────────────────────────────────────────┘
    ```

    **重要: Inference Profile ID（推論プロファイルID）**

    AWS Bedrockでは、オンデマンドスループットを使用する場合、
    モデルIDではなく「Inference Profile ID」を指定する必要があります。

    ```text
    【正しいモデルID形式】

    ✗ 直接モデルID（エラーになる）:
    anthropic.claude-opus-4-6-v1

    ✓ Inference Profile ID（正しい）:
    global.anthropic.claude-opus-4-6-v1      ← グローバル推論
    jp.anthropic.claude-sonnet-4-5-20250929-v1:0  ← 日本リージョン推論
    ```

    **利用可能なモデル（2026年2月時点・動作確認済み）**

    | モデルID | 説明 | レイテンシ |
    |----------|------|-----------|
    | `global.anthropic.claude-opus-4-6-v1` | 最高性能、グローバル推論 | 約9秒 |
    | `global.anthropic.claude-opus-4-5-20251101-v1:0` | 高性能モデル | 約7秒 |
    | `jp.anthropic.claude-sonnet-4-5-20250929-v1:0` | 日本リージョン、バランス型 | 約1.6秒 |
    | `anthropic.claude-3-haiku-20240307-v1:0` | 高速・低コスト | 約0.5秒 |

    **環境変数設定**

    ```ini
    LLM_PROVIDER=AWS
    AWS_REGION=ap-northeast-1
    # AWS_PROFILE=default  # SSO使用時
    AWS_BEDROCK_MODEL_ID=jp.anthropic.claude-sonnet-4-5-20250929-v1:0
    ```

    #### 12.3.2 AWS Lambda

    **AWS Lambdaとは？**

    AWS Lambdaは、AWSのサーバーレスコンピューティングサービスです。
    Azure Functionsと同様、コードを書くだけで自動スケールする環境を提供します。

    **API Gateway連携**

    LambdaはHTTPリクエストを直接受け取れないため、
    API Gatewayと組み合わせて使用します。

    ```text
    【AWS Lambda + API Gateway 構成】

    クライアント
        │
        ▼ HTTPS
    ┌──────────────────┐
    │   API Gateway    │ ← HTTPリクエストを受信、認証、ルーティング
    └────────┬─────────┘
             │
             ▼
    ┌──────────────────┐
    │   AWS Lambda     │ ← 実際の処理を実行
    │ lambda_handler.py│
    └──────────────────┘
    ```

    **本システムでの設定**

    | 設定項目 | 値 | 説明 |
    |---------|-----|------|
    | ランタイム | Python 3.11 | 実行環境 |
    | メモリ | 1024 MB | 割り当てメモリ |
    | タイムアウト | 300秒 | 最大実行時間 |
    | ハンドラー | `lambda_handler.handler` | エントリポイント |

    #### 12.3.3 AWS DynamoDB

    **DynamoDBとは？**

    Amazon DynamoDBは、フルマネージドのNoSQLデータベースです。
    Azure Table Storageと同様の用途で、ジョブの状態管理に使用します。

    ```text
    【DynamoDBテーブル設計】

    テーブル名: EvaluationJobs

    ┌─────────────┬─────────────┬─────────┬──────────┬──────────┐
    │ tenant_id   │ job_id      │ status  │ progress │ results  │
    │ (Partition) │ (Sort Key)  │         │          │ (JSON)   │
    ├─────────────┼─────────────┼─────────┼──────────┼──────────┤
    │ default     │ uuid-001    │ pending │ 0        │ null     │
    │ default     │ uuid-002    │ running │ 50       │ null     │
    │ tenant-a    │ uuid-003    │ completed│ 100     │ [{...}]  │
    └─────────────┴─────────────┴─────────┴──────────┴──────────┘

    GSI（グローバルセカンダリインデックス）:
    - status-created_at-index: ステータス別検索用
    - job_id-index: ジョブID単独検索用
    ```

    #### 12.3.4 Amazon SQS

    **SQSとは？**

    Amazon Simple Queue Service (SQS) は、メッセージキューサービスです。
    Azure Queue Storageと同様の用途で、非同期ジョブの通知に使用します。

    **環境変数設定**

    ```ini
    JOB_STORAGE_PROVIDER=AWS
    JOB_QUEUE_PROVIDER=AWS
    AWS_DYNAMODB_TABLE_NAME=EvaluationJobs
    AWS_SQS_QUEUE_URL=https://sqs.ap-northeast-1.amazonaws.com/123456789/evaluation-jobs
    ```

    ### 12.4 GCP クラウドリソース

    #### 12.4.1 Google Cloud Vertex AI

    **Vertex AIとは？**

    Vertex AIは、Google Cloudの機械学習プラットフォームです。
    GoogleのGeminiモデルを利用できます。

    ```text
    【Vertex AI の概念図】

    ┌─────────────────────────────────────────────────────────────────┐
    │                      Vertex AI                                  │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                 │
    │  ┌───────────────────────────────────────────────────────────┐ │
    │  │                  Gemini モデルファミリー                    │ │
    │  │  ┌───────────────────┐  ┌───────────────────┐            │ │
    │  │  │   Gemini 3.x      │  │   Gemini 2.x      │            │ │
    │  │  │  (Preview)        │  │  (GA - 安定版)     │            │ │
    │  │  │  - 3-pro-preview  │  │  - 2.5-pro        │            │ │
    │  │  │  - 3-flash-preview│  │  - 2.5-flash      │            │ │
    │  │  │                   │  │  - 2.5-flash-lite │            │ │
    │  │  └───────────────────┘  └───────────────────┘            │ │
    │  └───────────────────────────────────────────────────────────┘ │
    │                                                                 │
    │  【重要】リージョン設定                                         │
    │  - Gemini 3.x: globalリージョン必須                            │
    │  - Gemini 2.x: us-central1等のリージョンも利用可能              │
    │                                                                 │
    └─────────────────────────────────────────────────────────────────┘
    ```

    **重要: Gemini 3.x のリージョン設定**

    Gemini 3 Previewモデルは、**globalリージョン**でのみ利用可能です。
    `us-central1`等の従来リージョンでは404エラーになります。

    ```text
    【リージョン設定の違い】

    ✗ 従来リージョン設定（Gemini 3.xでエラー）:
    GCP_LOCATION=us-central1

    ✓ globalリージョン設定（Gemini 3.x対応）:
    GCP_LOCATION=global

    注意: Gemini 2.x はどちらでも動作します
    ```

    **利用可能なモデル（2026年2月時点・動作確認済み）**

    | モデル | 説明 | リージョン | レイテンシ |
    |--------|------|-----------|-----------|
    | `gemini-3-pro-preview` | 最高性能（Preview） | global必須 | 約30秒 |
    | `gemini-3-flash-preview` | 高速・マルチモーダル | global必須 | 約5秒 |
    | `gemini-2.5-pro` | GA版、高度な推論 | 任意 | 約4秒 |
    | `gemini-2.5-flash` | GA版、コスト効率 | 任意 | 約3秒 |
    | `gemini-2.5-flash-lite` | 超軽量 | 任意 | 約1秒 |

    > **注意**: Gemini 2.0は2026年3月31日に廃止予定です。

    **環境変数設定**

    ```ini
    LLM_PROVIDER=GCP
    GCP_PROJECT_ID=your-project-id
    GCP_LOCATION=global                    # Gemini 3.x用
    GCP_MODEL_NAME=gemini-3-pro-preview
    ```

    #### 12.4.2 GCP Cloud Functions

    **Cloud Functionsとは？**

    Cloud Functionsは、GCPのサーバーレスコンピューティングサービスです。
    Azure Functions、AWS Lambdaと同様の役割を果たします。

    **本システムでの使用**

    | 設定項目 | 値 | 説明 |
    |---------|-----|------|
    | ランタイム | Python 3.11 | 実行環境 |
    | メモリ | 1024 MB | 割り当てメモリ |
    | タイムアウト | 540秒 | 最大実行時間 |
    | フレームワーク | functions-framework | HTTPトリガー |

    #### 12.4.3 GCP Firestore

    **Firestoreとは？**

    Cloud Firestoreは、GCPのNoSQLデータベースです。
    リアルタイム同期機能があり、スマートフォンアプリなどでも人気のサービスです。

    ```text
    【Firestoreのデータ構造】

    コレクション: evaluation_jobs
    └── ドキュメント: {job_id}
        ├── tenant_id: "default"
        ├── status: "pending" | "running" | "completed" | "failed"
        ├── items: [ {...}, {...} ]
        ├── results: [ {...}, {...} ]
        ├── progress: 0-100
        ├── created_at: Timestamp
        └── completed_at: Timestamp
    ```

    #### 12.4.4 GCP Cloud Tasks

    **Cloud Tasksとは？**

    Cloud Tasksは、非同期タスク実行サービスです。
    Azure Queue Storage、Amazon SQSと同様の用途で使用します。

    **環境変数設定**

    ```ini
    JOB_STORAGE_PROVIDER=GCP
    JOB_QUEUE_PROVIDER=GCP
    GCP_FIRESTORE_COLLECTION=evaluation_jobs
    GCP_TASKS_QUEUE_PATH=projects/your-project/locations/us-central1/queues/evaluation-jobs
    ```

    ### 12.5 プロバイダー比較表

    #### 12.5.1 サーバーレスコンピューティング

    | 機能 | Azure Functions | AWS Lambda | GCP Cloud Functions |
    |------|-----------------|------------|---------------------|
    | 最大タイムアウト | 10分（Premium: 無制限） | 15分 | 9分（Gen2: 60分） |
    | メモリ範囲 | 128MB - 14GB | 128MB - 10GB | 128MB - 32GB |
    | 課金単位 | 100ms | 1ms | 100ms |
    | コールドスタート | 約1-3秒 | 約0.5-2秒 | 約0.5-2秒 |
    | ローカル開発ツール | Azure Functions Core Tools | SAM / localstack | functions-framework |

    #### 12.5.2 NoSQLデータベース

    | 機能 | Azure Table Storage | AWS DynamoDB | GCP Firestore |
    |------|---------------------|--------------|---------------|
    | データモデル | Key-Value | Key-Value | ドキュメント |
    | 制限 | 64KB/エンティティ | 400KB/アイテム | 1MB/ドキュメント |
    | クエリ機能 | 限定的 | GSI対応 | 複合クエリ対応 |
    | リアルタイム | なし | Streams | ネイティブ対応 |
    | 料金モデル | 従量課金 | オンデマンド/プロビジョニング | 従量課金 |

    #### 12.5.3 メッセージキュー

    | 機能 | Azure Queue Storage | Amazon SQS | GCP Cloud Tasks |
    |------|---------------------|------------|-----------------|
    | 最大メッセージサイズ | 64KB | 256KB | 100KB |
    | 保持期間 | 7日 | 14日 | 31日 |
    | ファンクショントリガー | ネイティブ対応 | Lambda統合 | HTTP呼び出し |
    | FIFO対応 | なし | オプション | なし |

    #### 12.5.4 AIモデルサービス

    | 項目 | Azure AI Foundry | AWS Bedrock | GCP Vertex AI |
    |------|------------------|-------------|---------------|
    | 主力モデル | GPT-5.2, Claude | Claude Opus 4.6 | Gemini 3 Pro |
    | 推奨モデル（本システム） | gpt-5-nano | jp.anthropic.claude-sonnet-4-5 | gemini-3-pro-preview |
    | 認証方式 | API Key / Azure AD | IAM Role / Keys | サービスアカウント |
    | リージョン | 東日本/西日本 | 東京 | global |
    | SLA | 99.9% | 99.9% | 99.9% |

    #### 12.5.5 OCRプロバイダー

    本システムでは、ドキュメント（PDF、画像）からテキストを抽出するためにOCRサービスを使用します。

    | プロバイダー | 説明 | 日本語 | タイ語 | オランダ語 | 設定値 |
    |-------------|------|:------:|:------:|:----------:|--------|
    | Azure Document Intelligence | 高精度OCR、レイアウト解析対応 | ◎ | ○ | ○ | `AZURE` |
    | AWS Textract | 表抽出・フォーム解析に強い | × | × | × | `AWS` |
    | GCP Document AI | 多言語対応、カスタムモデル可 | ○ | △ | ○ | `GCP` |
    | Tesseract | OSS、Docker/Lambda実行可 | ○ | ◎ | ◎ | `TESSERACT` |
    | YomiToku-Pro | 日本語特化、AWS Marketplace | ◎ | × | × | `YOMITOKU` |

    **凡例**: ◎ 高精度対応 / ○ 対応 / △ 限定対応 / × 非対応

    **言語別推奨プロバイダー**:
    - **日本語ドキュメント**: Azure Document Intelligence または YomiToku-Pro（高精度）
    - **英語ドキュメント**: Azure / AWS / GCP いずれも高精度
    - **タイ語ドキュメント**: Tesseract（AWS Textract/GCPは非対応）
    - **オランダ語ドキュメント**: Tesseract（安定した精度）

    **YomiToku-Pro（AWS Marketplace版）について**:
    ```text
    YomiToku-Proは、日本語OCRに特化したAWS Marketplace製品です。
    SageMaker Endpointとしてデプロイし、invoke_endpointで呼び出します。

    【設定例】
    OCR_PROVIDER=YOMITOKU
    YOMITOKU_ENDPOINT_NAME=yomitoku-pro-endpoint
    AWS_REGION=ap-northeast-1

    【特徴】
    - 手書き文字認識に対応
    - 複雑なレイアウト（帳票、申請書等）に強い
    - 日本語と英語の混在文書に対応
    ```

    **Tesseract（Docker版）について**:
    ```text
    AWS Lambda上でTesseractを使用する場合、Dockerコンテナでデプロイします。
    platforms/aws/Dockerfile に設定例があります。

    【対応言語】
    - jpn: 日本語
    - eng: 英語
    - tha: タイ語
    - nld: オランダ語

    【設定例】
    OCR_PROVIDER=TESSERACT
    TESSERACT_LANG=jpn+eng+tha+nld
    TESSERACT_CMD=/usr/bin/tesseract
    ```

    ### 12.6 クラウドリソースのセットアップ手順

    #### 12.6.1 Azure セットアップ

    **ステップ1: リソースグループの作成**

    ```powershell
    # Azure CLIにログイン
    az login

    # リソースグループを作成（リソースをまとめる入れ物）
    az group create `
        --name rg-ic-test-evaluation `
        --location japaneast

    # 確認
    az group show --name rg-ic-test-evaluation
    ```

    **ステップ2: ストレージアカウントの作成**

    ```powershell
    # ストレージアカウント作成
    az storage account create `
        --name stictestevaluation `
        --resource-group rg-ic-test-evaluation `
        --location japaneast `
        --sku Standard_LRS

    # 接続文字列を取得
    az storage account show-connection-string `
        --name stictestevaluation `
        --resource-group rg-ic-test-evaluation
    ```

    **ステップ3: Function Appの作成**

    ```powershell
    # Function App作成
    az functionapp create `
        --name func-ic-test-evaluation `
        --resource-group rg-ic-test-evaluation `
        --storage-account stictestevaluation `
        --consumption-plan-location japaneast `
        --runtime python `
        --runtime-version 3.11 `
        --functions-version 4

    # 環境変数設定
    az functionapp config appsettings set `
        --name func-ic-test-evaluation `
        --resource-group rg-ic-test-evaluation `
        --settings `
            LLM_PROVIDER=AZURE_FOUNDRY `
            AZURE_FOUNDRY_ENDPOINT=https://your-project.openai.azure.com/ `
            AZURE_FOUNDRY_API_KEY=your-api-key `
            AZURE_FOUNDRY_MODEL=gpt-5-nano
    ```

    **ステップ4: Azure AI Foundryの設定**

    1. [Azure AI Foundry](https://ai.azure.com) にアクセス
    2. 新しいプロジェクトを作成
    3. Model Catalogからモデルをデプロイ（gpt-5-nano推奨）
    4. エンドポイントとAPIキーを取得
    5. .envまたはFunction App設定に反映

    #### 12.6.2 AWS セットアップ

    **ステップ1: Bedrockモデルアクセス申請**

    1. AWS Consoleにログイン
    2. Amazon Bedrock サービスを開く
    3. 「Model access」でClaudeモデルへのアクセスをリクエスト
    4. 承認を待つ（通常は数分〜数時間）

    **ステップ2: Lambda関数の作成**

    ```powershell
    # 依存パッケージをインストール
    cd platforms/aws
    mkdir package
    pip install -r requirements.txt -t package/

    # ソースコードをコピー
    Copy-Item -Recurse ..\..\src\* package\
    Copy-Item lambda_handler.py package\

    # ZIPファイル作成
    Compress-Archive -Path package\* -DestinationPath deployment.zip

    # Lambda関数作成（AWS CLI）
    aws lambda create-function `
        --function-name ic-test-evaluate `
        --runtime python3.11 `
        --handler lambda_handler.handler `
        --zip-file fileb://deployment.zip `
        --role arn:aws:iam::123456789:role/lambda-bedrock-role `
        --timeout 300 `
        --memory-size 1024 `
        --environment Variables='{
            "LLM_PROVIDER":"AWS",
            "AWS_REGION":"ap-northeast-1",
            "AWS_BEDROCK_MODEL_ID":"jp.anthropic.claude-sonnet-4-5-20250929-v1:0"
        }'
    ```

    **ステップ3: API Gatewayの設定**

    1. AWS ConsoleでAPI Gatewayを開く
    2. HTTP APIを作成
    3. Lambda統合を追加
    4. ルートを設定（/evaluate, /health等）
    5. ステージをデプロイしてエンドポイントURLを取得

    #### 12.6.3 GCP セットアップ

    **ステップ1: プロジェクト設定**

    ```bash
    # GCPにログイン
    gcloud auth login

    # プロジェクト作成
    gcloud projects create ic-test-ai-agent

    # プロジェクトを設定
    gcloud config set project ic-test-ai-agent

    # Vertex AI APIを有効化
    gcloud services enable aiplatform.googleapis.com
    ```

    **ステップ2: 認証設定**

    ```bash
    # アプリケーションデフォルト認証（開発用）
    gcloud auth application-default login

    # サービスアカウント作成（本番用）
    gcloud iam service-accounts create ic-test-sa `
        --display-name="IC Test Service Account"

    # 権限付与
    gcloud projects add-iam-policy-binding ic-test-ai-agent `
        --member="serviceAccount:ic-test-sa@ic-test-ai-agent.iam.gserviceaccount.com" `
        --role="roles/aiplatform.user"

    # キーファイル作成
    gcloud iam service-accounts keys create key.json `
        --iam-account=ic-test-sa@ic-test-ai-agent.iam.gserviceaccount.com
    ```

    **ステップ3: Cloud Functionsのデプロイ**

    ```bash
    cd platforms/gcp

    # src/をコピー
    cp -r ../../src .

    # デプロイ
    gcloud functions deploy evaluate `
        --runtime python311 `
        --trigger-http `
        --allow-unauthenticated `
        --entry-point evaluate `
        --timeout 540 `
        --memory 1024MB `
        --set-env-vars "LLM_PROVIDER=GCP,GCP_PROJECT_ID=ic-test-ai-agent,GCP_LOCATION=global,GCP_MODEL_NAME=gemini-3-pro-preview"
    ```

    ---

    ## 13. 技術解説

    ### 13.1 使用技術スタック

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

    ### 13.2 LangChainとは

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

    ### 13.3 LangGraphとは

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

    ### 13.4 Factory Patternとは

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

    ## 14. 用語集

    | 用語 | 読み方 | 説明 |
    | ---- | ------ | ---- |
    | Amazon Bedrock | アマゾン ベッドロック | AWSの基盤モデルサービス。Claude、Titan等を提供 |
    | API | エーピーアイ | Application Programming Interface。システム間の通信規約 |
    | API Gateway | エーピーアイ ゲートウェイ | APIリクエストのルーティング・認証を行うサービス |
    | Azure AI Foundry | アジュール エーアイ ファウンドリー | Microsoft統合AIプラットフォーム。複数モデルを統一APIで利用可能 |
    | Azure Functions | アジュール ファンクションズ | Microsoftのサーバーレスコンピューティングサービス |
    | Base64 | ベースろくじゅうよん | バイナリデータをテキストに変換するエンコード方式 |
    | Blob Storage | ブロブ ストレージ | ファイルを保存するためのクラウドストレージ |
    | Claude | クロード | Anthropic社が開発したAIモデル。Opus、Sonnet、Haiku等 |
    | Cloud Functions | クラウド ファンクションズ | GCPのサーバーレスコンピューティングサービス |
    | Cloud Tasks | クラウド タスクス | GCPの非同期タスク実行サービス |
    | DynamoDB | ダイナモディービー | AWSのNoSQLデータベース |
    | Endpoint | エンドポイント | APIの接続先URL |
    | Factory Pattern | ファクトリーパターン | オブジェクト生成を専用クラスに委譲するデザインパターン |
    | Firestore | ファイアストア | GCPのNoSQLデータベース。リアルタイム同期対応 |
    | Functions Core Tools | ファンクションズ コアツールズ | Azure Functionsのローカル開発ツール |
    | Gemini | ジェミニ | Google社が開発したAIモデル。3.x、2.5シリーズ等 |
    | GPT | ジーピーティー | OpenAI社が開発したAIモデル。GPT-5シリーズ等 |
    | IAM | アイアム | Identity and Access Management。AWSの認証・認可サービス |
    | Inference Profile | インファレンス プロファイル | AWS Bedrockの推論設定。リージョン最適化に使用 |
    | JSON | ジェイソン | JavaScript Object Notation。データ交換形式 |
    | Key Vault | キーボルト | Azureのシークレット管理サービス |
    | Lambda | ラムダ | AWSのサーバーレスコンピューティングサービス |
    | LangChain | ラングチェーン | LLMアプリケーション開発フレームワーク |
    | LangGraph | ラングラフ | AIワークフロー定義ライブラリ |
    | LLM | エルエルエム | Large Language Model。大規模言語モデル |
    | NoSQL | ノーエスキューエル | 非リレーショナルデータベース。柔軟なスキーマが特徴 |
    | OCR | オーシーアール | Optical Character Recognition。光学文字認識 |
    | Orchestrator | オーケストレーター | 複数の処理を統括・調整するコンポーネント |
    | PowerShell | パワーシェル | Windowsのスクリプト実行環境 |
    | Queue Storage | キュー ストレージ | メッセージキューサービス。非同期処理に使用 |
    | Serverless | サーバーレス | サーバー管理不要のクラウドサービス形態 |
    | SoD | エスオーディー | Segregation of Duties。職務分掌 |
    | SQS | エスキューエス | Amazon Simple Queue Service。AWSのメッセージキュー |
    | Table Storage | テーブル ストレージ | AzureのNoSQLデータベース |
    | VBA | ブイビーエー | Visual Basic for Applications。Officeマクロ言語 |
    | Vertex AI | バーテックス エーアイ | Google Cloudの機械学習プラットフォーム |

    ---

    ## 15. 更新履歴

    | 日付 | バージョン | 変更内容 |
    | ---- | ---------- | -------- |
    | 2026-02-09 | 1.3.0 | テストスイート大幅拡充（156件→530+件、カバレッジ62%）、E2Eテスト追加、pre-commit hooks導入（flake8/bandit/detect-secrets）、CI/CDにbanditセキュリティスキャン・Codecovカバレッジ追加、Dependabot設定追加、テストドキュメント全面更新 |
    | 2026-02-08 | 1.2.0 | クラウドリソース詳細ドキュメント追加（セクション12）、マルチクラウドアーキテクチャ図解、各プロバイダー（Azure/AWS/GCP）のリソース詳細解説、最新モデル情報更新（Gemini 3 global設定、AWS Inference Profile ID、GPT-5 Nano等）、初心者向け学習コンテンツ追加 |
    | 2026-01-30 | 1.1.2 | pytestベースのユニットテスト・統合テストスイート追加（156件）、Azure Blob/Queue統合テスト追加、テストドキュメント整備 |
    | 2026-01-30 | 1.1.1 | Azure Table Storage 64KB制限対策を強化（全証跡ファイルをBlob Storageに保存） |
    | 2026-01-30 | 1.1.0 | Azure AD認証のみ方式に変更（Functions Key廃止）、トークンキャッシュ機能追加、セットアップスクリプト整備 |
    | 2026-01-29 | 1.0.0 | 初版リリース |
