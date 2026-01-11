# 内部統制テスト評価AIシステム 仕様書

## 1. システム概要

### 1.1 目的
内部統制監査におけるテスト手続きの評価を、AI（大規模言語モデル）を活用して自動化・効率化するシステム。

### 1.2 主要機能
- Excelシートからテストデータを読み込み
- エビデンスファイル（PDF、画像、テキスト等）を自動収集・Base64変換
- クラウドAPIを通じてAIによる評価を実行
- 評価結果をExcelシートに書き戻し

### 1.3 対応クラウドプロバイダー
| プロバイダー | 環境変数 | 説明 |
|------------|---------|------|
| Azure AI Foundry | `AZURE_FOUNDRY` | Microsoft統合AIプラットフォーム（推奨） |
| Azure OpenAI | `AZURE` | Azure OpenAI Service |
| GCP Vertex AI | `GCP` | Google Cloud Gemini |
| AWS Bedrock | `AWS` | Amazon Claude/Titan |

---

## 2. システムアーキテクチャ

### 2.1 全体構成図

```
┌─────────────────────────────────────────────────────────────────┐
│                      クライアント側（Excel VBA）                   │
├─────────────────────────────────────────────────────────────────┤
│  Excel VBA (ExcelToJson.bas)                                    │
│    ├── setting.json 読み込み                                     │
│    ├── Excelデータ → JSON変換                                    │
│    ├── バッチ処理（batchSize件ずつ）                              │
│    └── PowerShellスクリプト呼び出し                               │
│                                                                  │
│  PowerShell (CallCloudApi.ps1)                                   │
│    ├── EvidenceLinkフォルダからファイル収集                        │
│    ├── ファイル → Base64変換                                      │
│    └── Azure Functions API呼び出し                               │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTPS POST
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    サーバー側（Azure Functions）                  │
├─────────────────────────────────────────────────────────────────┤
│  function_app.py (エントリポイント)                               │
│    ├── /api/evaluate - 評価エンドポイント                         │
│    ├── /api/health - ヘルスチェック                               │
│    └── /api/config - 設定状態確認                                │
│                                                                  │
│  infrastructure/llm_factory.py                                   │
│    └── マルチクラウドLLMインスタンス生成                           │
│                                                                  │
│  core/auditor_agent.py (AuditOrchestrator)                       │
│    ├── タスク分解プランナー                                       │
│    ├── A1-A8タスク実行制御                                        │
│    └── 結果集約・最終判定                                         │
│                                                                  │
│  core/tasks/ (監査タスク A1-A8)                                   │
│    ├── a1_semantic_search.py    - 意味検索                        │
│    ├── a2_image_recognition.py  - 画像認識                        │
│    ├── a3_data_extraction.py    - データ抽出                      │
│    ├── a4_stepwise_reasoning.py - 段階的推論                      │
│    ├── a5_semantic_reasoning.py - 意味推論                        │
│    ├── a6_multi_document.py     - 複数文書統合                    │
│    ├── a7_pattern_analysis.py   - パターン分析                    │
│    └── a8_sod_detection.py      - 職務分掌検出                    │
└───────────────────────────┬─────────────────────────────────────┘
                            │ LangChain
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                       LLM プロバイダー                            │
│  Azure AI Foundry / Azure OpenAI / GCP Vertex AI / AWS Bedrock  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 データフロー

```
1. Excel → VBA変換
   ┌──────────────┐     ┌─────────────────┐
   │ Excelシート   │ ──▶ │ JSON配列        │
   │ (テストデータ) │     │ (複数アイテム)   │
   └──────────────┘     └─────────────────┘

2. エビデンス収集 (PowerShell)
   ┌──────────────┐     ┌─────────────────┐
   │ EvidenceLink  │ ──▶ │ EvidenceFiles[] │
   │ (フォルダパス) │     │ (Base64配列)    │
   └──────────────┘     └─────────────────┘

3. API呼び出し・評価
   ┌──────────────┐     ┌─────────────────┐
   │ リクエストJSON │ ──▶ │ レスポンスJSON   │
   │ (エビデンス含)  │     │ (評価結果)       │
   └──────────────┘     └─────────────────┘

4. Excel書き戻し
   ┌──────────────┐     ┌─────────────────┐
   │ レスポンスJSON │ ──▶ │ Excelシート     │
   │ (評価結果)     │     │ (結果列更新)    │
   └──────────────┘     └─────────────────┘
```

---

## 3. ファイル構成

```
ic-test-ai-agent/
├── ExcelToJson.bas          # Excel VBAモジュール（クライアント）
├── CallCloudApi.ps1         # PowerShellスクリプト（API呼び出し）
├── setting.json             # 設定ファイル
├── setting.sample.json      # 設定ファイルサンプル
├── test_api.ps1             # APIテストスクリプト
│
├── azure-functions/         # Azure Functions（サーバー）
│   ├── function_app.py      # メインエントリポイント
│   ├── host.json            # Functions設定
│   ├── requirements.txt     # Python依存関係
│   ├── local.settings.json  # ローカル環境変数
│   │
│   ├── infrastructure/
│   │   └── llm_factory.py   # LLMインスタンスファクトリ
│   │
│   └── core/
│       ├── auditor_agent.py # 監査オーケストレーター
│       └── tasks/
│           ├── base_task.py           # 基底クラス
│           ├── a1_semantic_search.py  # A1: 意味検索
│           ├── a2_image_recognition.py# A2: 画像認識
│           ├── a3_data_extraction.py  # A3: データ抽出
│           ├── a4_stepwise_reasoning.py# A4: 段階的推論
│           ├── a5_semantic_reasoning.py# A5: 意味推論
│           ├── a6_multi_document.py   # A6: 複数文書統合
│           ├── a7_pattern_analysis.py # A7: パターン分析
│           └── a8_sod_detection.py    # A8: 職務分掌検出
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

- Python 3.11
- Azure Functions Core Tools
- PowerShell 5.1以上
- Excel（VBA有効）

### 6.2 ローカル環境セットアップ

```powershell
# 1. 仮想環境作成
cd azure-functions
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. 依存関係インストール
pip install -r requirements.txt

# 3. 環境変数設定（local.settings.json）
{
    "Values": {
        "LLM_PROVIDER": "AZURE_FOUNDRY",
        "AZURE_FOUNDRY_ENDPOINT": "https://...",
        "AZURE_FOUNDRY_API_KEY": "...",
        "AZURE_FOUNDRY_MODEL": "gpt-4o"
    }
}

# 4. ローカル実行
func start
```

### 6.3 Azureデプロイ

```powershell
# デプロイ
func azure functionapp publish func-ic-test-evaluation

# 環境変数設定
az functionapp config appsettings set `
    --name func-ic-test-evaluation `
    --resource-group rg-ic-test-evaluation `
    --settings LLM_PROVIDER=AZURE_FOUNDRY ...
```

---

## 7. 使用方法

### 7.1 Excelシート準備

1. テストデータシートを作成（列構成はsetting.jsonで定義）
2. EvidenceLink列にエビデンスフォルダパスを入力
3. 各フォルダにエビデンスファイルを配置

### 7.2 VBA実行

1. Excelブックを開く
2. `ExcelToJson.bas`をインポート
3. `ProcessWithApi`マクロを実行
4. 結果列（F〜I列）に評価結果が書き込まれる

### 7.3 バッチサイズ調整

タイムアウトが発生する場合:
- `setting.json`の`batchSize`を減らす（例: 3→1）
- サーバー側の`functionTimeout`を延長

---

## 8. トラブルシューティング

### 8.1 504 Gateway Timeout

**原因**: APIの処理時間がAzure Functionsのタイムアウトを超過

**対策**:
1. `setting.json`の`batchSize`を減らす
2. `host.json`の`functionTimeout`を延長（最大10分）
3. エビデンスファイルのサイズを削減

### 8.2 Temperature parameter error

**原因**: 一部モデル（gpt-5-nano, o1シリーズ）はtemperatureをサポートしない

**対策**: `llm_factory.py`の`MODELS_WITHOUT_TEMPERATURE`リストで自動対応済み

### 8.3 LLM not configured

**原因**: 環境変数が未設定

**対策**: `/api/config`エンドポイントで`missing_vars`を確認して設定

---

## 9. セキュリティ考慮事項

1. **APIキー管理**: Azure Key Vaultの使用を推奨
2. **エビデンスデータ**: Base64変換後もメモリ上に残るため、機密文書の取り扱いに注意
3. **ログ出力**: 本番環境ではデバッグ情報（`_debug`）の出力を検討
4. **ネットワーク**: Azure VNet統合による通信の保護を検討

---

## 10. 更新履歴

| 日付 | バージョン | 変更内容 |
|------|-----------|---------|
| 2024-01-04 | 1.0 | 初版作成 |
| 2024-01-05 | 2.0 | Azure AI Foundry対応、マルチクラウド対応 |
| 2024-01-06 | 2.1 | バッチ処理実装、タイムアウト対策 |
