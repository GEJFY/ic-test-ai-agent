"""
================================================================================
graph_orchestrator.py - LangGraph ベースの監査オーケストレーター
================================================================================

【概要】
LangGraphを活用したセルフリフレクションパターンを実装した
内部統制テスト評価オーケストレーターです。

【適用デザインパターン】
1. セルフリフレクション (No.9) - 計画・結果の自己レビューで品質向上
2. プロンプト/レスポンス最適化 (No.3) - 専門家視点での出力品質向上
3. シングルパスプランジェネレーター (No.7) - 計画生成の強化
4. エージェント評価者 (No.18) - 計画・結果の品質評価

【LangGraphアーキテクチャ】
```
                    ┌──────────────────────────────────────┐
                    │           AuditGraphState            │
                    │  (context, plan, results, judgment)  │
                    └──────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    ↓                                   │
              ┌──────────┐                              │
              │ 計画作成  │                              │
              │(create_  │                              │
              │  plan)   │                              │
              └────┬─────┘                              │
                   │                                    │
                   ↓                                    │
              ┌──────────┐    改善要求                  │
              │計画レビュー│─────────────────┐          │
              │(review_  │                  │          │
              │  plan)   │                  │          │
              └────┬─────┘                  │          │
                   │ OK                     │          │
                   ↓                        ↓          │
              ┌──────────┐            ┌──────────┐     │
              │タスク実行 │            │計画修正  │     │
              │(execute_ │            │(refine_  │     │
              │  tasks)  │            │  plan)   │     │
              └────┬─────┘            └────┬─────┘     │
                   │                       │           │
                   │                       └───────────┤
                   ↓                                   │
              ┌──────────┐                              │
              │結果統合  │                              │
              │(aggregate│                              │
              │ _results)│                              │
              └────┬─────┘                              │
                   │                                    │
                   ↓                                    │
              ┌──────────┐    修正要求                  │
              │判断レビュー│─────────────────┐          │
              │(review_  │                  │          │
              │judgment) │                  │          │
              └────┬─────┘                  │          │
                   │ OK                     │          │
                   ↓                        ↓          │
              ┌──────────┐            ┌──────────┐     │
              │ 最終出力 │            │判断修正  │     │
              │ (output) │            │(refine_  │     │
              └──────────┘            │judgment) │     │
                                      └────┬─────┘     │
                                           │           │
                                           └───────────┘
```

【使用例】
```python
from core.graph_orchestrator import GraphAuditOrchestrator
from core.tasks.base_task import AuditContext

# オーケストレーターを初期化
orchestrator = GraphAuditOrchestrator(llm=llm, vision_llm=vision_llm)

# 評価を実行
result = await orchestrator.evaluate(context)
```

================================================================================
"""
import asyncio
import logging
from typing import TypedDict, List, Dict, Any, Optional, Literal
from dataclasses import dataclass, field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langgraph.graph import StateGraph, END

from .tasks.base_task import (
    BaseAuditTask, TaskType, TaskResult, AuditContext
)
from .tasks import (
    SemanticSearchTask,
    ImageRecognitionTask,
    DataExtractionTask,
    StepwiseReasoningTask,
    SemanticReasoningTask,
    MultiDocumentTask,
    PatternAnalysisTask,
    SoDDetectionTask,
)

# =============================================================================
# ログ設定
# =============================================================================

logger = logging.getLogger(__name__)

# =============================================================================
# プロンプトテンプレート
# =============================================================================

# テスト計画作成用プロンプト（強化版）
ENHANCED_PLANNER_PROMPT = """あなたは内部統制監査の専門家AIプランナーです。
与えられた統制記述とテスト手続きを分析し、最適な評価タスクの実行計画を立案してください。

【最重要原則】
★ 内部統制テストは「必要最小限のタスク」で効率的に実施します。
★ 原則として1〜2タスクで計画してください。3つ以上は過剰です。
★ 「この証跡で何を確認すれば統制の有効性を判断できるか」だけを考えてください。

【タスク選択の判断基準】
タスクを選ぶ際は、以下の質問に答えてください：

1. 「何を確認するか」 → 確認内容でタスクが決まる
   - 記載内容・出席者の確認 → A1（意味検索）
   - 印影・署名の確認 → A2（画像認識）
   - 数値の突合・計算検証 → A3/A4（データ抽出/段階的推論）
   - 規程との整合性 → A5（意味推論）
   - 複数文書間の整合性 → A6（複数文書統合）
   - 複数期間の継続実施 → A7（パターン分析）
   - 権限の競合・分離 → A8（SoD検出）

2. 「実施頻度は何か」 → 頻度でA7の要否が決まる
   - 複数回/継続的（月次、四半期、毎週等）→ A7が候補
   - 単発/年1回/都度 → A7は不適切、A1またはA5を使用

3. 「承認の形態は何か」 → 形態でA2の要否が決まる
   - 押印・署名による承認 → A2
   - 会議出席による承認（議事録） → A1（出席=承認）
   - システム承認・ワークフロー → A1またはA3

【利用可能なタスクタイプ】
A1: 意味検索 - 証跡内の記載内容を意味的に検索・確認（最も汎用的）
A2: 画像認識 - 印影・署名・日付を画像から抽出
A3: データ抽出 - 表から数値を抽出し突合
A4: 段階的推論 - 複雑な計算をステップごとに検証
A5: 意味推論 - 抽象的な規程要求と実施記録の整合性判定
A6: 複数文書統合 - 複数の証跡を統合してプロセス全体を確認
A7: パターン分析 - 複数期間の継続実施を時系列で確認
A8: SoD検出 - 職務分掌違反・権限競合を検出

【A7（パターン分析）の使用条件】
A7は「複数期間にわたる継続的な実施」を確認するタスクです。
使用条件：以下のすべてを満たす場合のみ
  ✓ 統制が「月次」「四半期」「毎週」など複数回の実施を要求している
  ✓ 複数期間分の証跡が提供されている
  ✓ 「継続的に実施されているか」の確認が目的

使用しない条件：以下のいずれかに該当する場合
  ✗ 実施頻度が「年1回」「年度」「都度」など単発
  ✗ 単一時点の実施記録の確認
  ✗ リストやデータの内容確認（→ A1またはA3を使用）

【統制記述】
{control_description}

【テスト手続き】
{test_procedure}

【エビデンスファイル情報】
{evidence_info}

【出力形式】
以下のJSON形式で実行計画を出力してください：
{{
    "analysis": {{
        "evidence_type": "証跡の種類",
        "confirmation_target": "確認対象（記載内容/印影/数値/整合性等）",
        "frequency": "実施頻度（単発/月次/四半期等）",
        "approval_type": "承認形態（押印/会議出席/システム/なし）"
    }},
    "execution_plan": [
        {{
            "step": 1,
            "task_type": "A1-A8のいずれか",
            "purpose": "このタスクを実行する目的",
            "test_description": "【必須】具体的なテスト内容を文章で記述",
            "check_items": ["確認する項目"]
        }}
    ],
    "reasoning": "この計画を立案した理由（なぜこのタスクを選んだか）"
}}

★★★【test_descriptionの記載ルール】★★★
test_descriptionには、「何を」「どのように」テストするかを具体的な文章で記載してください。

【良い例】
- 「研修実施報告書を閲覧し、研修日時・対象者・実施方法が記載されていることを確認する。」
- 「リスク評価結果一覧より、各リスク項目の発生可能性・影響度の評価が実施されていることを確認する。」
- 「取締役会議事録を閲覧し、リスク評価結果が報告・審議されたことを確認する。」
- 「組織図を閲覧し、職務権限規程に定める権限と実際の組織体制が整合していることを確認する。」

【悪い例（禁止）】
- 「A3: 構造化データ抽出」（タスクタイプ名だけ）
- 「データを確認する」（抽象的すぎる）
- 「証跡を検証」（何をどう検証するか不明）
"""

# テスト計画レビュー用プロンプト（セルフリフレクション）
# 監査マネージャー視点：リスクベースでテスト計画の妥当性を評価
PLAN_REVIEW_PROMPT = """あなたは内部統制監査の監査マネージャー（経験15年以上）です。
担当者が作成したテスト計画をレビューし、監査品質の観点から承認可否を判断してください。

【あなたの役割】
監査マネージャーとして、以下を確認します：
1. テスト計画が統制の目的・リスクに対応しているか
2. 証跡の選定が適切か（統制の有効性を判断するのに十分か）
3. テスト手続きの要求事項を満たしているか

【レビューの視点】

★ 統制目的の理解
- この統制は何のリスクを軽減するためのものか？
- テスト計画はそのリスク軽減を検証できる内容か？

★ 証跡と確認事項の整合性
- 提供された証跡で、テスト手続きの確認事項をカバーできるか？
- 確認すべき項目に漏れはないか？

★ タスク選択の妥当性
- 選択されたタスクタイプは確認対象に適切か？
- 過剰なタスク（同じことを重複確認）はないか？

【タスク選択の判断基準】
| 確認対象 | 適切なタスク | 不適切なタスク |
|---------|-------------|---------------|
| 記載内容・出席者 | A1（意味検索） | A7（継続性不要なら） |
| 印影・署名 | A2（画像認識） | A1（画像読めない） |
| 数値の突合 | A3/A4 | A1（計算必要なら） |
| 規程との整合性 | A5（意味推論） | A3（定性的なら） |
| 複数文書の整合 | A6 | 単独タスクの重複 |
| 継続的実施 | A7（月次等） | A7（年1回なら不要） |
| 権限分掌 | A8 | A1（SoD判定必要なら） |

【統制記述】
{control_description}

【テスト手続き】
{test_procedure}

【エビデンスファイル】
{evidence_info}

【レビュー対象の計画】
{execution_plan}

【レビュー判断基準】

「承認」とする条件：
✓ テスト手続きの確認事項がすべてカバーされている
✓ 選択されたタスクが確認対象に適切である
✓ test_descriptionが具体的で、何を確認するか明確である

「要修正」とする条件：
✗ テスト手続きの確認事項に漏れがある
✗ タスク選択が確認対象と不整合（例：数値確認にA1を使用）
✗ test_descriptionが抽象的（「確認する」「検証する」のみ）
✗ 同じ確認を複数タスクで重複している

【出力形式】
{{
    "review_result": "承認" または "要修正",
    "control_objective_understood": true/false,
    "coverage_score": 1-10,
    "efficiency_score": 1-10,
    "issues": [
        {{
            "type": "網羅性不足/タスク不整合/記述不明確/重複",
            "description": "問題の具体的内容",
            "suggestion": "改善提案（具体的に）"
        }}
    ],
    "missing_checks": ["テスト手続きでカバーされていない確認事項"],
    "redundant_tasks": ["削除すべきタスク（理由付き）"],
    "reasoning": "監査マネージャーとしてのレビュー所見"
}}
"""

# 最終判断用プロンプト（強化版・専門家視点）
ENHANCED_JUDGMENT_PROMPT = """あなたは内部統制監査の実務経験20年以上の専門家です。
金融庁検査官が読んでも問題のない、監査調書品質の評価結果を作成してください。

【最重要原則】証跡が存在すれば「有効」と判断する
内部統制テストの目的は「統制が機能しているか」の確認です。
証跡（議事録、報告書、リスト等）が提供され、内容が確認できれば、基本的に有効と判断します。

【有効と判断する条件】（以下のいずれかを満たせば「有効」）
- 議事録に該当事項の記載があり、出席者が確認できる
- 報告書・申請書に必要事項が記載されている
- リスト・明細に期待されるデータが存在する
- 軽微な例外があっても、フォローアップが確認できる

【不備と判断する条件】（以下のすべてを満たす場合のみ「不備」）
- 証跡が全く存在しない、または重大な欠落がある
- 統制の目的が達成されていないことが明確
- 補完統制やフォローアップも確認できない

【絶対に避けるべき判断パターン】
× 「追加証跡が必要」「フォローアップを前提に」→ 提供された証跡で判断を完結させること
× 「証跡が読み取れない」→ ファイル形式の問題であり統制の問題ではない
× 「完全に確認できなかった」→ 確認できた範囲で明確に判断する
× 「未確定」「保留」→ 必ず「有効」か「不備」のいずれかを結論付ける

【統制記述】
{control_description}

【テスト手続き】
{test_procedure}

【エビデンスファイル】
{evidence_files}

【テスト計画】
{execution_plan}

【各タスクの実行結果】
{task_results}

【出力形式】
以下のJSON形式で出力してください：

{{
    "evaluation_result": true/false,
    "judgment_basis": "判断根拠（詳細な文章形式、300〜500文字程度）",
    "document_quotes": [
        {{
            "file_name": "証跡ファイル名（拡張子含む）",
            "quotes": ["前後の文脈を含む引用文1", "前後の文脈を含む引用文2"],
            "page_or_location": "ページ番号やセクション名"
        }}
    ],
    "confidence": 0.0-1.0,
    "key_findings": ["主要な発見事項"],
    "control_effectiveness": {{
        "design": "整備状況の評価（有効/要改善）",
        "operation": "運用状況の評価（有効/要改善）"
    }}
}}

★★★【judgment_basis：経験豊富な専門家による監査調書】★★★

経験20年以上の内部統制監査専門家として、簡潔かつ的確な判断根拠を記載してください。

【書き方のルール】
1. 確認した事実を直接述べる（前置き不要）
2. 具体的な数値・日付・名称を含める
3. 300〜500文字程度で簡潔にまとめる
4. 結論を明確に述べる

【禁止する書き出しパターン - 以下は絶対に使わないこと】
× 「テスト手続きでは〜」「テスト手続きに基づき〜」
× 「当該統制の有効性を評価するため〜」
× 「内部統制テストの結果〜」
× 「評価の結果〜」「検証の結果〜」
× 「以下の通り確認した〜」
× 「本件について〜」「本統制について〜」

【良い書き出しパターン - 直接事実から始める】
○ 「研修実施報告書および受講者リストを閲覧した。」
○ 「取締役会議事録を閲覧し、〜を確認した。」
○ 「リスク評価結果一覧より、〜が実施されていることを確認した。」
○ 「〇〇年〇月〇日付の承認書により、〜を確認した。」

【良い判断根拠の例】
「研修実施報告書および受講者リストを閲覧した。報告書より、2025年11月18日にeラーニング形式で研修が実施され、理解度テスト（10問、合格基準80%）が併せて実施されていることを確認した。受講者リストより、全対象者60名のうち受講済53名、期限後受講4名、未受講3名であること、未受講者に対しては12月2日および9日に督促が実施されていることを確認した。期限後受講者4名は12月6日までに受講完了。整備面として、年1回の研修実施と受講モニタリング手続きが定められており、人事総務部にて管理されている。運用面として、研修は計画どおり実施され、未受講者への督促も適時に行われている。以上より、本統制は有効に整備・運用されていると判断する。」

【悪い判断根拠の例 - こう書いてはいけない】
「テスト手続きでは、研修の実施状況を確認することとしており、当該統制の有効性を評価するため、研修実施報告書および受講者リストを閲覧した。」← 前置きが冗長

★★★【document_quotes：原文をそのまま幅広に引用】★★★

【引用の目的】
レビュアーが元の証跡ファイルを開かずに判断の妥当性を検証できるよう、
根拠となる記載を前後の文脈を含めて十分な量で引用します。

【引用のルール】
1. **原文をそのままコピー＆ペーストする**
   - 証跡ファイルに記載された文言を一字一句変えずにそのまま転記
   - 自分の言葉での言い換え・要約・省略は【絶対禁止】
   - 誤字脱字があってもそのまま引用する

2. **引用の長さ：100〜400文字程度**
   - 根拠となる記載だけでなく、前後の文脈も含めて幅広に引用
   - セクション見出し、項目名、前後の文も含める
   - 短い引用（50文字未満）は不可
   - 表の場合はヘッダー行と複数の該当行を含める

3. **引用形式：括弧なしでそのまま記載**
   - 「」や『』で囲まない
   - 原文をそのまま記載する

4. **各証跡ファイルから2〜3箇所を引用する**
   - 判断根拠を裏付けるすべての箇所を引用する

【悪い引用の例 - このような引用は禁止】
× 「研修が実施されていることを確認した」← 要約している
× 「受講者名簿に全員の受講記録があった」← 言い換えている
× 「対象：全役職員」← 短すぎる（文脈がない）

【良い引用の例 - 原文をそのまま幅広に】
ファイル: CLC-01_コンプライアンス研修実施報告書_2025年度.pdf
引用箇所: 1ページ「1. 実施概要」セクション
引用文: 1. 実施概要 対象：全役職員（役員・嘱託・派遣を含む） 実施日：2025/11/18（eラーニング配信開始） 実施方法：LMS（社内学習管理システム）にて受講、理解度テスト（10問）を実施 受講期限：2025/11/30、期限後受講は2025/12/10まで認める（特段の事情がある場合）

ファイル: CLC-01_コンプライアンス研修実施報告書_2025年度.pdf
引用箇所: 2ページ「3. 受講状況」セクション
引用文: 3. 受講状況 本研修の受講状況は以下の通りである。受講済：53名（88.3%）、期限後受講：4名（6.7%）、未受講：3名（5.0%）、合計：60名 期限後受講者については、業務都合により期限内の受講が困難であったが、いずれも2025/12/06までに受講を完了している。未受講者3名については、2025/12/02および12/09に督促を実施済みであり、追加研修（12/09予定）にて対応予定。

【引用文の品質チェック】
□ 引用文は100文字以上あるか？（前後の文脈を含めているか）
□ 「」や『』で囲んでいないか？（原文そのまま記載しているか）
□ 自分の言葉で言い換えていないか？
□ 判断根拠の各主張に対応する引用があるか？
"""

# 最終判断レビュー用プロンプト（セルフリフレクション）
# 品質管理パートナー視点：監査調書品質の確保（過度な修正要求を避ける）
JUDGMENT_REVIEW_PROMPT = """あなたは監査法人の品質管理パートナー（内部統制監査経験25年）です。
作成された監査判断をレビューし、重大な問題がある場合のみ修正を指示してください。

【重要な前提】
★ 判断根拠が概ね妥当であれば「承認」としてください
★ 軽微な改善点は「承認」としつつ、reasoningに改善提案を記載してください
★ 「要修正」は、判断に重大な誤りがある場合のみ使用してください

【あなたの役割】
品質管理パートナーとして、以下の観点で最終チェックを行います：
1. 評価結果（有効/不備）と判断根拠の整合性
2. 判断根拠に重大な論理的誤りがないか
3. 禁止フレーズが含まれていないか

【統制記述】
{control_description}

【テスト手続き】
{test_procedure}

【テスト計画】
{execution_plan}

【タスク実行結果】
{task_results}

【レビュー対象の判断】
評価結果: {evaluation_result}
判断根拠: {judgment_basis}
引用文: {document_quotes}
信頼度: {confidence}

【品質チェックリスト】

□ 1. 証跡に基づく事実の記載
   - 判断根拠に具体的な事実（日付、数値、名前）が含まれているか
   - その事実は提供された証跡に実際に記載されているか
   - 証跡に存在しない情報を推測で記載していないか

□ 2. 論理的な判断プロセス
   - 「何を確認し」→「何が確認でき」→「よって有効/不備」の流れがあるか
   - 確認事項と結論の間に論理の飛躍がないか

□ 3. 証跡との紐付け（引用の品質チェック）★重要★
   - document_quotesは証跡の原文をそのまま引用しているか（要約・言い換えは不可）
   - 引用が要約形式（例:「研修が実施されていることを確認」）になっていないか → 原文転記を要求
   - 引用箇所（ページ、セクション、行）が特定されているか
   - 各引用は50文字以上の十分な長さがあるか
   - 判断根拠の各主張に対応する引用があるか

□ 4. 結論の明確性
   - 「有効」または「不備」が明確に結論付けられているか
   - 「追加証跡が必要」「今後の確認を要する」等の曖昧な表現がないか
   - 条件付きの結論（「〜を前提として有効」）になっていないか

【要修正とすべきパターン】

1. **証跡に基づかない記載**
   - 「〜と推測される」「〜と思われる」→ 証跡に基づく事実のみ記載
   - 証跡に存在しない数値や日付 → 証跡から確認できる情報のみ記載

2. **曖昧な結論**
   - 「追加証跡が必要」→ 提供された証跡で結論を出す
   - 「フォローアップを前提に有効」→ 無条件で「有効」または「不備」

3. **証跡との紐付け不足**★引用品質は重要★
   - 要約形式の引用（例:「研修が実施されていた」「適切に運用されている」）→ 原文をそのまま引用
   - 短すぎる引用（50文字未満）→ 前後の文脈を含めて引用
   - 引用箇所の特定なし → ページ番号やセクション名を明記
   - 引用文が1〜2個しかない → 各証跡から3〜5個の引用を要求

4. **過度に保守的な判断**
   - 軽微な例外を理由に「不備」→ 例外対応が確認できれば「有効」
   - 証跡が存在するのに「確認できなかった」→ 確認できた事実を記載

【承認/要修正の判断基準】

★★★「承認」とすべき場合 ★★★
以下のすべてに該当すれば「承認」としてください：
- 証跡から確認できた事実に基づいて結論が導かれている
- 判断根拠に具体的な日付、数値、名称が含まれている
- 結論（有効/不備）が明確に述べられている
- 評価結果と判断根拠の内容が一致している

★★★「要修正」とすべき場合 ★★★
以下のいずれかに該当する場合は「要修正」としてください：

【パターン1】禁止フレーズが含まれている
- 「追加証跡が必要」「追加の証跡を要する」「追加検証が必要」
- 「フォローアップを前提に」「フォローアップ計画の明確化が必要」
- 「結論を更新する」「再評価する」
- 「限定的有効性」「条件付き有効」

【パターン2】評価結果と判断根拠が矛盾している（★最重要★）
評価結果が「有効」なのに、判断根拠に以下の否定的表現がある場合は必ず「要修正」：
- 「不備がある」「不備が認められる」「不備と判断」
- 「不十分である」「十分でない」「欠如している」
- 「問題がある」「課題がある」「懸念がある」
- 「統制が機能していない」「機能不全」
- 「有効性に疑義」「有効とは言えない」「有効と断定できず」
- 「確認できなかった」「確認できていない」（証跡が存在する場合）

評価結果が「不備」なのに、判断根拠に以下の肯定的表現がある場合は必ず「要修正」：
- 「有効に整備・運用されている」「有効と判断する」
- 「適切に実施されている」「問題なく運用されている」
- 「統制は機能している」

【矛盾検出時の修正指示】
矛盾を検出した場合は、revised_judgment_basisに以下を含めて修正案を提示：
1. 矛盾する表現を削除または修正
2. 評価結果と整合する結論文を追記
3. 証跡から確認できた事実に基づく記述に修正

【出力形式】
{{
    "review_result": "承認" または "要修正",
    "coverage_score": 1-10,
    "efficiency_score": 1-10,
    "original_judgment_appropriate": true/false,
    "suggested_evaluation_result": true/false,
    "issues": [
        {{
            "type": "禁止フレーズ/評価結果矛盾/その他",
            "description": "問題の具体的内容",
            "correction": "修正案"
        }}
    ],
    "revised_judgment_basis": "要修正の場合のみ記載：禁止フレーズを除去した判断根拠",
    "reasoning": "レビュー所見"
}}
"""


# =============================================================================
# LangGraph State定義
# =============================================================================

class AuditGraphState(TypedDict):
    """
    LangGraphの状態定義

    グラフ実行中に保持される状態情報です。
    各ノードが状態を読み取り・更新します。
    """
    # 入力データ
    context: Dict[str, Any]           # 監査コンテキスト情報

    # 計画関連
    execution_plan: Optional[Dict]    # 実行計画
    plan_review: Optional[Dict]       # 計画レビュー結果
    plan_revision_count: int          # 計画修正回数

    # タスク実行関連
    task_results: List[Dict]          # タスク実行結果

    # 判断関連
    judgment: Optional[Dict]          # 最終判断
    judgment_review: Optional[Dict]   # 判断レビュー結果
    judgment_revision_count: int      # 判断修正回数

    # 出力
    final_result: Optional[Dict]      # 最終出力


# =============================================================================
# データクラス定義
# =============================================================================

@dataclass
class ExecutionPlan:
    """実行計画データクラス"""
    analysis: Dict[str, Any]
    steps: List[Dict[str, Any]]
    dependencies: Dict[str, List[str]]
    reasoning: str
    potential_issues: List[str] = field(default_factory=list)


@dataclass
class AuditResult:
    """監査結果データクラス"""
    item_id: str
    evaluation_result: bool
    judgment_basis: str
    document_reference: str
    file_name: str
    evidence_files_info: List[Dict[str, str]] = field(default_factory=list)
    task_results: List[TaskResult] = field(default_factory=list)
    execution_plan: Optional[ExecutionPlan] = None
    confidence: float = 0.0
    plan_review_summary: str = ""
    judgment_review_summary: str = ""

    def to_response_dict(self, include_debug: bool = True) -> dict:
        """API応答形式の辞書に変換"""
        # 実行計画サマリーを生成
        execution_plan_summary = self._format_execution_plan_summary()

        response = {
            "ID": self.item_id,
            "evaluationResult": self.evaluation_result,
            "executionPlanSummary": execution_plan_summary,
            "judgmentBasis": self.judgment_basis,
            "documentReference": self.document_reference,
            "fileName": self.file_name,
            "evidenceFiles": self.evidence_files_info,
        }

        if include_debug:
            response["_debug"] = {
                "confidence": self.confidence,
                "planReviewSummary": self.plan_review_summary,
                "judgmentReviewSummary": self.judgment_review_summary,
                "executionPlan": None,
                "taskResults": []
            }

            if self.execution_plan:
                response["_debug"]["executionPlan"] = {
                    "analysis": self.execution_plan.analysis,
                    "steps": self.execution_plan.steps,
                    "reasoning": self.execution_plan.reasoning,
                    "potentialIssues": self.execution_plan.potential_issues
                }

            for tr in self.task_results:
                response["_debug"]["taskResults"].append({
                    "taskType": tr.task_type.value,
                    "taskName": tr.task_name,
                    "success": tr.success,
                    "confidence": tr.confidence,
                    "reasoning": tr.reasoning,
                    "evidenceReferences": tr.evidence_references
                })

        return response

    def _format_execution_plan_summary(self) -> str:
        """
        実行計画のサマリーを生成（監査調書として適切な文章形式で記述）

        監査専門家が作成したような、具体的なテスト内容を文章形式で出力します。
        箇条書きや記号は使用せず、段落形式で記述します。
        """
        if not self.task_results:
            return "（タスク未実行）"

        # 実行計画のstepsからtest_descriptionとcheck_itemsを取得
        step_descriptions = []
        if self.execution_plan and self.execution_plan.steps:
            for step in self.execution_plan.steps:
                if isinstance(step, dict):
                    test_desc = step.get("test_description", "") or step.get("purpose", "")
                    check_items = step.get("check_items", [])
                    if test_desc:
                        # 確認項目を文章に組み込む
                        if check_items and isinstance(check_items, list) and len(check_items) > 0:
                            items_text = "、".join(check_items[:3])
                            if not test_desc.endswith("。"):
                                test_desc += "。"
                            test_desc = f"{test_desc}具体的には、{items_text}を確認した"
                        step_descriptions.append(test_desc)

        # タスク結果からも情報を補完
        if not step_descriptions:
            for tr in self.task_results:
                if hasattr(tr, 'reasoning'):
                    reasoning = tr.reasoning
                else:
                    reasoning = tr.get("reasoning", "")

                if reasoning:
                    # reasoningから結論部分を抽出
                    # 「結論:」「/ 結論:」の後の文を優先
                    conclusion_text = ""
                    if "/ 結論:" in reasoning:
                        conclusion_text = reasoning.split("/ 結論:")[-1].strip()
                    elif "結論:" in reasoning:
                        conclusion_text = reasoning.split("結論:")[-1].strip()

                    if conclusion_text:
                        # 最初の文だけ取得
                        if "。" in conclusion_text:
                            conclusion_text = conclusion_text.split("。")[0] + "。"
                        step_descriptions.append(conclusion_text)
                    elif reasoning:
                        # 証跡部分を抽出
                        if "/ 証跡:" in reasoning:
                            evidence_part = reasoning.split("/ 証跡:")[1].split("/")[0].strip()
                            if evidence_part and evidence_part != "N/A":
                                step_descriptions.append(evidence_part)

        # 結果をまとめて文章形式で出力
        if step_descriptions:
            # 複数のテスト説明を自然な文章として結合
            combined = ""
            for i, desc in enumerate(step_descriptions):
                if i == 0:
                    combined = desc
                else:
                    # 接続詞を付けて結合
                    if not combined.endswith("。"):
                        combined += "。"
                    combined += f"また、{desc}"

            # 文末を整える
            if combined and not combined.endswith("。"):
                combined += "。"

            # テスト結果の成否を追加
            success_count = sum(1 for tr in self.task_results
                                if (tr.success if hasattr(tr, 'success') else tr.get("success", False)))
            total_count = len(self.task_results)

            if success_count == total_count:
                result_suffix = "上記テストの結果、統制は有効と判断された。"
            elif success_count == 0:
                result_suffix = "上記テストの結果、証跡不足により統制の有効性を確認できなかった。"
            else:
                result_suffix = f"上記テストの結果、{total_count}件中{success_count}件が有効と判断された。"

            return f"{combined}\n\n{result_suffix}"
        else:
            # フォールバック：シンプルな結果サマリー
            success_count = sum(1 for tr in self.task_results
                                if (tr.success if hasattr(tr, 'success') else tr.get("success", False)))
            total_count = len(self.task_results)

            if total_count == 0:
                return "テストは実施されなかった。"

            return f"計{total_count}件のテストを実施し、{success_count}件が有効と判断された。"


# =============================================================================
# メインクラス: GraphAuditOrchestrator
# =============================================================================

class GraphAuditOrchestrator:
    """
    LangGraphベースの監査オーケストレーター

    セルフリフレクションパターンを実装し、
    計画作成→レビュー→実行→判断→レビューの
    品質向上サイクルを実現します。
    """

    # 最大修正回数（無限ループ防止）
    # セルフリフレクションによる品質向上のため1回の修正を許可
    MAX_PLAN_REVISIONS = 1
    MAX_JUDGMENT_REVISIONS = 1

    def __init__(self, llm=None, vision_llm=None):
        """
        オーケストレーターを初期化

        Args:
            llm: テキスト処理用のLangChain ChatModel
            vision_llm: 画像処理用のVision対応ChatModel
        """
        self.llm = llm
        self.vision_llm = vision_llm or llm

        logger.info("[GraphOrchestrator] 初期化開始")

        # タスクハンドラーを初期化
        self.tasks: Dict[TaskType, BaseAuditTask] = {
            TaskType.A1_SEMANTIC_SEARCH: SemanticSearchTask(llm),
            TaskType.A2_IMAGE_RECOGNITION: ImageRecognitionTask(llm, vision_llm),
            TaskType.A3_DATA_EXTRACTION: DataExtractionTask(llm),
            TaskType.A4_STEPWISE_REASONING: StepwiseReasoningTask(llm),
            TaskType.A5_SEMANTIC_REASONING: SemanticReasoningTask(llm),
            TaskType.A6_MULTI_DOCUMENT: MultiDocumentTask(llm),
            TaskType.A7_PATTERN_ANALYSIS: PatternAnalysisTask(llm),
            TaskType.A8_SOD_DETECTION: SoDDetectionTask(llm),
        }

        # JSON出力パーサー
        self.parser = JsonOutputParser()

        # LangGraphを構築
        self.graph = self._build_graph()

        logger.info("[GraphOrchestrator] 初期化完了")

    # =========================================================================
    # LangGraph構築
    # =========================================================================

    def _build_graph(self) -> StateGraph:
        """
        LangGraphを構築

        セルフリフレクション付きフロー:
        create_plan → review_plan → (refine_plan →) execute_tasks
        → aggregate_results → review_judgment → (refine_judgment →) output

        並列API呼び出しにより各項目が独立したAzure Functionsインスタンスで
        処理されるため、5分のタイムアウト制限を有効活用できます。
        """
        # StateGraphを作成
        workflow = StateGraph(AuditGraphState)

        # ノードを追加
        workflow.add_node("create_plan", self._node_create_plan)
        workflow.add_node("review_plan", self._node_review_plan)
        workflow.add_node("refine_plan", self._node_refine_plan)
        workflow.add_node("execute_tasks", self._node_execute_tasks)
        workflow.add_node("aggregate_results", self._node_aggregate_results)
        workflow.add_node("review_judgment", self._node_review_judgment)
        workflow.add_node("refine_judgment", self._node_refine_judgment)
        workflow.add_node("output", self._node_output)

        # エントリーポイント
        workflow.set_entry_point("create_plan")

        # 計画作成 → 計画レビュー
        workflow.add_edge("create_plan", "review_plan")

        # 計画レビュー後の条件分岐
        workflow.add_conditional_edges(
            "review_plan",
            self._should_refine_plan,
            {
                "refine": "refine_plan",
                "execute": "execute_tasks"
            }
        )

        workflow.add_edge("refine_plan", "review_plan")
        workflow.add_edge("execute_tasks", "aggregate_results")
        workflow.add_edge("aggregate_results", "review_judgment")

        # 判断レビュー後の条件分岐
        workflow.add_conditional_edges(
            "review_judgment",
            self._should_refine_judgment,
            {
                "refine": "refine_judgment",
                "output": "output"
            }
        )

        workflow.add_edge("refine_judgment", "review_judgment")
        workflow.add_edge("output", END)

        logger.info("[GraphOrchestrator] セルフリフレクションフロー構築完了")

        # グラフをコンパイル
        return workflow.compile()

    # =========================================================================
    # 条件分岐関数
    # =========================================================================

    def _should_refine_plan(self, state: AuditGraphState) -> Literal["refine", "execute"]:
        """計画を修正すべきか判断"""
        plan_review = state.get("plan_review", {})
        revision_count = state.get("plan_revision_count", 0)

        # 最大修正回数に達した場合は実行へ
        if revision_count >= self.MAX_PLAN_REVISIONS:
            logger.info("[GraphOrchestrator] 計画修正回数上限に達したため実行へ")
            return "execute"

        # レビュー結果が「要修正」の場合は修正へ
        if plan_review.get("review_result") == "要修正":
            logger.info("[GraphOrchestrator] 計画レビュー: 要修正 → 計画修正へ")
            return "refine"

        logger.info("[GraphOrchestrator] 計画レビュー: 承認 → タスク実行へ")
        return "execute"

    def _should_refine_judgment(self, state: AuditGraphState) -> Literal["refine", "output"]:
        """判断を修正すべきか判断"""
        judgment_review = state.get("judgment_review", {})
        revision_count = state.get("judgment_revision_count", 0)

        # 最大修正回数に達した場合は出力へ
        if revision_count >= self.MAX_JUDGMENT_REVISIONS:
            logger.info("[GraphOrchestrator] 判断修正回数上限に達したため出力へ")
            return "output"

        # レビュー結果が「要修正」の場合は修正へ
        if judgment_review.get("review_result") == "要修正":
            logger.info("[GraphOrchestrator] 判断レビュー: 要修正 → 判断修正へ")
            return "refine"

        logger.info("[GraphOrchestrator] 判断レビュー: 承認 → 最終出力へ")
        return "output"

    # =========================================================================
    # ノード実装
    # =========================================================================

    async def _node_create_plan(self, state: AuditGraphState) -> Dict:
        """計画作成ノード"""
        logger.info("[ノード] create_plan: 実行計画を作成中...")

        context = state["context"]

        if not self.llm:
            # LLMがない場合はデフォルト計画
            plan = self._create_default_plan(context)
            return {
                "execution_plan": {
                    "analysis": plan.analysis,
                    "steps": plan.steps,
                    "dependencies": plan.dependencies,
                    "reasoning": plan.reasoning,
                    "potential_issues": plan.potential_issues
                },
                "plan_revision_count": 0
            }

        try:
            # 証跡情報をサマリー化
            evidence_info = self._summarize_evidence(context.get("evidence_files", []))

            # LLMで計画を生成
            prompt = ChatPromptTemplate.from_template(ENHANCED_PLANNER_PROMPT)
            chain = prompt | self.llm | self.parser

            result = await chain.ainvoke({
                "control_description": context.get("control_description", ""),
                "test_procedure": context.get("test_procedure", ""),
                "evidence_info": evidence_info,
            })

            logger.info(f"[ノード] create_plan: 計画作成完了 - {len(result.get('execution_plan', []))}ステップ")

            return {
                "execution_plan": result,
                "plan_revision_count": 0
            }

        except Exception as e:
            logger.error(f"[ノード] create_plan: エラー - {e}")
            plan = self._create_default_plan(context)
            return {
                "execution_plan": {
                    "analysis": plan.analysis,
                    "steps": plan.steps,
                    "dependencies": plan.dependencies,
                    "reasoning": f"デフォルト計画（エラー: {e}）",
                    "potential_issues": []
                },
                "plan_revision_count": 0
            }

    async def _node_review_plan(self, state: AuditGraphState) -> Dict:
        """計画レビューノード（セルフリフレクション）"""
        logger.info("[ノード] review_plan: 計画をレビュー中...")

        context = state["context"]
        execution_plan = state.get("execution_plan", {})

        if not self.llm:
            return {"plan_review": {"review_result": "承認", "reasoning": "LLM未設定のためスキップ"}}

        try:
            evidence_info = self._summarize_evidence(context.get("evidence_files", []))

            prompt = ChatPromptTemplate.from_template(PLAN_REVIEW_PROMPT)
            chain = prompt | self.llm | self.parser

            result = await chain.ainvoke({
                "control_description": context.get("control_description", ""),
                "test_procedure": context.get("test_procedure", ""),
                "evidence_info": evidence_info,
                "execution_plan": str(execution_plan),
            })

            logger.info(f"[ノード] review_plan: レビュー結果 - {result.get('review_result')}")

            return {"plan_review": result}

        except Exception as e:
            logger.error(f"[ノード] review_plan: エラー - {e}")
            return {"plan_review": {"review_result": "承認", "reasoning": f"レビューエラー: {e}"}}

    async def _node_refine_plan(self, state: AuditGraphState) -> Dict:
        """計画修正ノード - LLMを再度呼び出してレビューのフィードバックを反映"""
        logger.info("[ノード] refine_plan: 計画を修正中...")

        context = state["context"]
        execution_plan = state.get("execution_plan", {})
        plan_review = state.get("plan_review", {})
        revision_count = state.get("plan_revision_count", 0)

        if not self.llm:
            # LLMがない場合は単純な修正のみ
            logger.warning("[ノード] refine_plan: LLM未設定のため簡易修正")
            return {
                "execution_plan": execution_plan,
                "plan_revision_count": revision_count + 1
            }

        try:
            # レビュー結果をフィードバックとして計画を再生成
            evidence_info = self._summarize_evidence(context.get("evidence_files", []))
            issues_text = "\n".join([
                f"- {issue.get('type', '不明')}: {issue.get('description', '')} → {issue.get('suggestion', '')}"
                for issue in plan_review.get("issues", [])
                if isinstance(issue, dict)
            ])

            refine_prompt = f"""あなたは内部統制監査の専門家AIプランナーです。
以下のレビューフィードバックを反映して、テスト計画を修正してください。

【統制記述】
{context.get("control_description", "")}

【テスト手続き】
{context.get("test_procedure", "")}

【エビデンスファイル情報】
{evidence_info}

【現在の計画】
{str(execution_plan.get("execution_plan", []))}

【レビューフィードバック】
レビュー結果: {plan_review.get("review_result", "N/A")}
問題点:
{issues_text if issues_text else "（具体的な問題点なし）"}

削除すべきタスク: {plan_review.get("redundant_tasks", [])}
追加すべきタスク: {plan_review.get("missing_tasks", [])}

【修正指示】
上記のフィードバックを反映し、改善した計画を出力してください。
特に以下を必ず改善してください：
1. test_description は具体的な文章で記述（タスクタイプ名だけは禁止）
2. タスク数は最小限に（原則1〜2タスク）
3. 確認対象に適したタスクを選択

【出力形式】
{{
    "execution_plan": [
        {{
            "step": 1,
            "task_type": "A1-A8のいずれか",
            "purpose": "このタスクを実行する目的",
            "test_description": "具体的なテスト内容を文章で記述",
            "check_items": ["確認する項目"]
        }}
    ],
    "reasoning": "修正理由"
}}
"""
            prompt = ChatPromptTemplate.from_template(refine_prompt)
            chain = prompt | self.llm | self.parser

            result = await chain.ainvoke({})

            # 修正された計画で更新
            if result.get("execution_plan"):
                execution_plan["execution_plan"] = result["execution_plan"]
                execution_plan["reasoning"] = result.get("reasoning", "レビューフィードバックに基づく修正")

            logger.info(f"[ノード] refine_plan: LLMによる修正完了 - 修正回数 {revision_count + 1}")

        except Exception as e:
            logger.error(f"[ノード] refine_plan: LLM修正エラー - {e}")
            # エラー時は元の計画を維持

        return {
            "execution_plan": execution_plan,
            "plan_revision_count": revision_count + 1
        }

    async def _node_execute_tasks(self, state: AuditGraphState) -> Dict:
        """タスク実行ノード"""
        logger.info("[ノード] execute_tasks: タスクを実行中...")

        context_dict = state["context"]
        execution_plan = state.get("execution_plan", {})

        # execution_planの構造を正規化
        # LLMの出力形式によって "execution_plan" または直接配列の場合がある
        if isinstance(execution_plan, dict):
            steps = execution_plan.get("execution_plan", [])
            if not isinstance(steps, list):
                steps = []
        else:
            steps = []

        logger.info(f"[ノード] execute_tasks: {len(steps)}ステップを実行予定")

        # AuditContextを再構築
        from .tasks.base_task import AuditContext, EvidenceFile
        evidence_files = []
        for ef_dict in context_dict.get("evidence_files", []):
            evidence_files.append(EvidenceFile(
                file_name=ef_dict.get("file_name", ""),
                mime_type=ef_dict.get("mime_type", ""),
                extension=ef_dict.get("extension", ""),
                base64_content=ef_dict.get("base64_content", "")
            ))

        context = AuditContext(
            item_id=context_dict.get("item_id", ""),
            control_description=context_dict.get("control_description", ""),
            test_procedure=context_dict.get("test_procedure", ""),
            evidence_link=context_dict.get("evidence_link", ""),
            evidence_files=evidence_files
        )

        # タスクを並列実行するための準備
        async def execute_single_task(step_info):
            """単一タスクを実行"""
            task_type_str, task, task_type = step_info
            try:
                logger.info(f"[ノード] execute_tasks: {task_type.value} - {task.task_name}")
                result = await task.execute(context)
                return {
                    "task_type": result.task_type.value,
                    "task_name": result.task_name,
                    "success": result.success,
                    "result": result.result,
                    "reasoning": result.reasoning,
                    "confidence": result.confidence,
                    "evidence_references": result.evidence_references
                }
            except Exception as e:
                logger.error(f"[ノード] execute_tasks: タスクエラー - {e}")
                return {
                    "task_type": task_type.value,
                    "task_name": task.task_name,
                    "success": False,
                    "result": None,
                    "reasoning": f"実行エラー: {e}",
                    "confidence": 0.0,
                    "evidence_references": []
                }

        # 実行可能なタスクを収集
        tasks_to_execute = []
        for step in steps:
            # stepが辞書でない場合はスキップ（LLM出力の形式不整合対応）
            if not isinstance(step, dict):
                logger.warning(f"[ノード] execute_tasks: 不正なstep形式をスキップ: {type(step)}")
                continue

            task_type_str = step.get("task_type", "")
            task_type = self._parse_task_type(task_type_str)

            if not task_type:
                continue

            task = self.tasks.get(task_type)
            if not task:
                continue

            tasks_to_execute.append((task_type_str, task, task_type))

        # タスクを並列実行（asyncio.gatherで同時実行）
        logger.info(f"[ノード] execute_tasks: {len(tasks_to_execute)}タスクを並列実行開始")
        if tasks_to_execute:
            results = await asyncio.gather(
                *[execute_single_task(t) for t in tasks_to_execute],
                return_exceptions=False
            )
            results = list(results)
        else:
            results = []

        logger.info(f"[ノード] execute_tasks: 完了 - {len(results)}タスク実行")

        return {"task_results": results}

    async def _node_aggregate_results(self, state: AuditGraphState) -> Dict:
        """結果統合ノード"""
        logger.info("[ノード] aggregate_results: 結果を統合中...")

        context = state["context"]
        execution_plan = state.get("execution_plan", {})
        task_results = state.get("task_results", [])

        if not self.llm:
            # LLMがない場合は単純集計
            judgment = self._simple_aggregate(task_results)
            return {"judgment": judgment}

        try:
            # タスク結果をフォーマット
            task_results_text = self._format_task_results(task_results)
            evidence_files_text = self._summarize_evidence(context.get("evidence_files", []))

            # LLMで最終判断を生成
            prompt = ChatPromptTemplate.from_template(ENHANCED_JUDGMENT_PROMPT)
            chain = prompt | self.llm | self.parser

            result = await chain.ainvoke({
                "control_description": context.get("control_description", ""),
                "test_procedure": context.get("test_procedure", ""),
                "evidence_files": evidence_files_text,
                "execution_plan": str(execution_plan.get("execution_plan", [])),
                "task_results": task_results_text,
            })

            logger.info(f"[ノード] aggregate_results: 判断生成完了 - "
                       f"{'有効' if result.get('evaluation_result') else '要確認'}")

            return {
                "judgment": result,
                "judgment_revision_count": 0
            }

        except Exception as e:
            logger.error(f"[ノード] aggregate_results: エラー - {e}")
            return {
                "judgment": self._simple_aggregate(task_results),
                "judgment_revision_count": 0
            }

    async def _node_review_judgment(self, state: AuditGraphState) -> Dict:
        """判断レビューノード（セルフリフレクション）"""
        logger.info("[ノード] review_judgment: 判断をレビュー中...")

        context = state["context"]
        execution_plan = state.get("execution_plan", {})
        task_results = state.get("task_results", [])
        judgment = state.get("judgment", {})

        # ★ LLMレビュー前に矛盾を事前検出 ★
        pre_detected_issues = self._detect_judgment_contradictions(
            judgment.get("judgment_basis", ""),
            judgment.get("evaluation_result", False)
        )
        if pre_detected_issues:
            logger.warning(f"[ノード] review_judgment: 事前検出された問題 - {len(pre_detected_issues)}件")

        if not self.llm:
            # LLMがなくても矛盾検出結果は返す
            if pre_detected_issues:
                return {"judgment_review": {
                    "review_result": "要修正",
                    "issues": pre_detected_issues,
                    "reasoning": "LLM未設定だが矛盾を検出"
                }}
            return {"judgment_review": {"review_result": "承認", "reasoning": "LLM未設定のためスキップ"}}

        try:
            prompt = ChatPromptTemplate.from_template(JUDGMENT_REVIEW_PROMPT)
            chain = prompt | self.llm | self.parser

            result = await chain.ainvoke({
                "control_description": context.get("control_description", ""),
                "test_procedure": context.get("test_procedure", ""),
                "execution_plan": str(execution_plan.get("execution_plan", [])),
                "task_results": self._format_task_results(task_results),
                "evaluation_result": judgment.get("evaluation_result", False),
                "judgment_basis": judgment.get("judgment_basis", ""),
                "document_quotes": str(judgment.get("document_quotes", [])),
                "confidence": judgment.get("confidence", 0.0),
            })

            review_result = result.get("review_result", "承認")
            logger.info(f"[ノード] review_judgment: LLMレビュー結果 - {review_result}")

            # ★ 事前検出した問題をLLM結果にマージ ★
            if pre_detected_issues:
                existing_issues = result.get("issues", [])
                merged_issues = existing_issues + pre_detected_issues
                result["issues"] = merged_issues
                # 事前検出で問題があればレビュー結果を「要修正」に強制
                result["review_result"] = "要修正"
                logger.info(f"[ノード] review_judgment: 事前検出の問題をマージ → 要修正")

            # 過度に保守的な判断を検出した場合
            if not result.get("original_judgment_appropriate", True):
                logger.warning("[ノード] review_judgment: 判断の妥当性に問題あり")

            return {"judgment_review": result}

        except Exception as e:
            logger.error(f"[ノード] review_judgment: エラー - {e}")
            return {"judgment_review": {"review_result": "承認", "reasoning": f"レビューエラー: {e}"}}

    async def _node_refine_judgment(self, state: AuditGraphState) -> Dict:
        """判断修正ノード - LLMを再度呼び出してレビューのフィードバックを反映"""
        logger.info("[ノード] refine_judgment: 判断を修正中...")

        context = state["context"]
        execution_plan = state.get("execution_plan", {})
        task_results = state.get("task_results", [])
        judgment = state.get("judgment", {})
        judgment_review = state.get("judgment_review", {})
        revision_count = state.get("judgment_revision_count", 0)

        # レビューで revised_judgment_basis が提供されている場合はそれを使用
        if judgment_review.get("revised_judgment_basis"):
            judgment["judgment_basis"] = judgment_review["revised_judgment_basis"]
            logger.info("[ノード] refine_judgment: レビューの修正案を適用")

        if judgment_review.get("suggested_evaluation_result") is not None:
            judgment["evaluation_result"] = judgment_review["suggested_evaluation_result"]

        # LLMで判断を再生成（レビューフィードバックを反映）
        if self.llm and judgment_review.get("issues"):
            try:
                issues_text = "\n".join([
                    f"- {issue.get('type', '不明')}: {issue.get('description', '')} → {issue.get('correction', '')}"
                    for issue in judgment_review.get("issues", [])
                    if isinstance(issue, dict)
                ])

                task_results_text = self._format_task_results(task_results)
                evidence_files_text = self._summarize_evidence(context.get("evidence_files", []))

                refine_prompt = f"""あなたは内部統制監査の実務経験20年以上の専門家です。
以下のレビューフィードバックを反映して、監査判断を修正してください。

【統制記述】
{context.get("control_description", "")}

【テスト手続き】
{context.get("test_procedure", "")}

【エビデンスファイル】
{evidence_files_text}

【タスク実行結果】
{task_results_text}

【現在の判断】
評価結果: {"有効" if judgment.get("evaluation_result") else "不備"}
判断根拠: {judgment.get("judgment_basis", "")}

【レビューフィードバック】
問題点:
{issues_text}

【修正指示】
上記のフィードバックを反映し、以下の点を改善した判断を出力してください：
1. 判断根拠は300〜500文字で具体的に記述
2. 証跡から確認できた事実（日付、数値、名前等）を明記
3. 「追加証跡が必要」「フォローアップを前提に」等の曖昧な表現は禁止
4. document_quotes は証跡から一字一句そのまま引用（要約禁止）

【出力形式】
{{
    "evaluation_result": true/false,
    "judgment_basis": "修正後の判断根拠（300〜500文字）",
    "document_quotes": [
        {{
            "file_name": "証跡ファイル名",
            "quotes": ["一字一句そのままの引用1", "一字一句そのままの引用2"],
            "page_or_location": "ページ番号やセクション名"
        }}
    ],
    "confidence": 0.0-1.0
}}
"""
                prompt = ChatPromptTemplate.from_template(refine_prompt)
                chain = prompt | self.llm | self.parser

                result = await chain.ainvoke({})

                # 修正された判断で更新
                if result.get("judgment_basis"):
                    judgment["judgment_basis"] = result["judgment_basis"]
                if result.get("evaluation_result") is not None:
                    judgment["evaluation_result"] = result["evaluation_result"]
                if result.get("document_quotes"):
                    judgment["document_quotes"] = result["document_quotes"]
                if result.get("confidence"):
                    judgment["confidence"] = result["confidence"]

                logger.info(f"[ノード] refine_judgment: LLMによる修正完了 - 修正回数 {revision_count + 1}")

            except Exception as e:
                logger.error(f"[ノード] refine_judgment: LLM修正エラー - {e}")
                # エラー時はレビューの修正案を使用（既に適用済み）

        logger.info(f"[ノード] refine_judgment: 修正完了 - 修正回数 {revision_count + 1}")

        return {
            "judgment": judgment,
            "judgment_revision_count": revision_count + 1
        }

    async def _node_output(self, state: AuditGraphState) -> Dict:
        """最終出力ノード"""
        logger.info("[ノード] output: 最終結果を生成中...")

        context = state["context"]
        judgment = state.get("judgment", {})
        plan_review = state.get("plan_review", {})
        judgment_review = state.get("judgment_review", {})

        # レビューサマリーを生成（数値が取得できない場合はタスク数から推定）
        plan_review_summary = ""
        if plan_review:
            coverage = plan_review.get("coverage_score")
            efficiency = plan_review.get("efficiency_score")

            # スコアが取得できない場合、レビュー結果から推定
            if coverage is None or coverage == "N/A" or str(coverage).strip() == "":
                if plan_review.get("review_result") == "承認":
                    coverage = 8  # 承認された場合は高めのスコア
                else:
                    coverage = 6  # 要修正の場合は中程度
            if efficiency is None or efficiency == "N/A" or str(efficiency).strip() == "":
                if plan_review.get("task_count_appropriate", True):
                    efficiency = 8
                else:
                    efficiency = 5

            plan_review_summary = f"網羅性: {coverage}/10, 効率性: {efficiency}/10"

        judgment_review_summary = ""
        if judgment_review:
            # review_resultが空またはN/Aの場合は「承認」をデフォルトとする
            review_result = judgment_review.get("review_result", "承認")
            if not review_result or review_result == "N/A":
                review_result = "承認"
            judgment_review_summary = f"レビュー結果: {review_result}"

        # 判断根拠の後処理（禁止フレーズの検出と修正）
        judgment_basis = self._postprocess_judgment_basis(
            judgment.get("judgment_basis", ""),
            judgment.get("evaluation_result", False)
        )

        final_result = {
            "item_id": context.get("item_id", ""),
            "evaluation_result": judgment.get("evaluation_result", False),
            "judgment_basis": judgment_basis,
            "document_quotes": judgment.get("document_quotes", []),
            "confidence": judgment.get("confidence", 0.0),
            "key_findings": judgment.get("key_findings", []),
            "control_effectiveness": judgment.get("control_effectiveness", {}),
            "plan_review_summary": plan_review_summary,
            "judgment_review_summary": judgment_review_summary,
        }

        logger.info(f"[ノード] output: 最終結果生成完了 - "
                   f"{'有効' if final_result['evaluation_result'] else '要確認'}")

        return {"final_result": final_result}

    # =========================================================================
    # メイン評価処理
    # =========================================================================

    async def evaluate(self, context: AuditContext) -> AuditResult:
        """
        テスト項目を評価

        LangGraphを使用してセルフリフレクション付きの評価を実行します。

        Args:
            context (AuditContext): 監査コンテキスト

        Returns:
            AuditResult: 評価結果
        """
        logger.info("=" * 60)
        logger.info(f"[GraphOrchestrator] 評価開始: {context.item_id}")

        # コンテキストを辞書形式に変換
        context_dict = {
            "item_id": context.item_id,
            "control_description": context.control_description,
            "test_procedure": context.test_procedure,
            "evidence_link": context.evidence_link,
            "evidence_files": [
                {
                    "file_name": ef.file_name,
                    "mime_type": ef.mime_type,
                    "extension": ef.extension,
                    "base64_content": ef.base64_content
                }
                for ef in context.evidence_files
            ]
        }

        # 初期状態を設定
        initial_state: AuditGraphState = {
            "context": context_dict,
            "execution_plan": None,
            "plan_review": None,
            "plan_revision_count": 0,
            "task_results": [],
            "judgment": None,
            "judgment_review": None,
            "judgment_revision_count": 0,
            "final_result": None,
        }

        # グラフを実行
        try:
            final_state = await self.graph.ainvoke(initial_state)
        except Exception as e:
            logger.error(f"[GraphOrchestrator] グラフ実行エラー: {e}", exc_info=True)
            return self._create_fallback_result(context, f"グラフ実行エラー: {e}")

        # 結果を取得
        final_result = final_state.get("final_result", {})
        task_results_raw = final_state.get("task_results", [])
        execution_plan_raw = final_state.get("execution_plan", {})

        # TaskResultオブジェクトに変換
        task_results = []
        for tr in task_results_raw:
            task_results.append(TaskResult(
                task_type=self._parse_task_type(tr.get("task_type", "A5")) or TaskType.A5_SEMANTIC_REASONING,
                task_name=tr.get("task_name", ""),
                success=tr.get("success", False),
                result=tr.get("result"),
                reasoning=tr.get("reasoning", ""),
                confidence=tr.get("confidence", 0.0),
                evidence_references=tr.get("evidence_references", [])
            ))

        # ExecutionPlanオブジェクトに変換
        execution_plan = ExecutionPlan(
            analysis=execution_plan_raw.get("analysis", {}),
            steps=execution_plan_raw.get("execution_plan", []),
            dependencies=execution_plan_raw.get("task_dependencies", {}),
            reasoning=execution_plan_raw.get("reasoning", ""),
            potential_issues=execution_plan_raw.get("potential_issues", [])
        )

        # 証跡ファイル情報を構築
        evidence_files_info = []
        for ef in context.evidence_files:
            evidence_files_info.append({
                "fileName": ef.file_name,
                "filePath": context.evidence_link
            })

        # 証跡からの引用をフォーマット
        document_quotes = final_result.get("document_quotes", [])
        document_reference = self._format_document_quotes(document_quotes)

        # AuditResultを作成
        result = AuditResult(
            item_id=context.item_id,
            evaluation_result=final_result.get("evaluation_result", False),
            judgment_basis=final_result.get("judgment_basis", ""),
            document_reference=document_reference,
            file_name=context.evidence_files[0].file_name if context.evidence_files else "",
            evidence_files_info=evidence_files_info,
            task_results=task_results,
            execution_plan=execution_plan,
            confidence=final_result.get("confidence", 0.0),
            plan_review_summary=final_result.get("plan_review_summary", ""),
            judgment_review_summary=final_result.get("judgment_review_summary", ""),
        )

        logger.info(f"[GraphOrchestrator] 評価完了: {context.item_id} - "
                   f"{'有効' if result.evaluation_result else '要確認'}")
        logger.info("=" * 60)

        return result

    # =========================================================================
    # ユーティリティメソッド
    # =========================================================================

    def _parse_task_type(self, task_type_str: str) -> Optional[TaskType]:
        """タスクタイプ文字列をTaskType列挙型に変換"""
        task_type_map = {
            "A1": TaskType.A1_SEMANTIC_SEARCH,
            "A2": TaskType.A2_IMAGE_RECOGNITION,
            "A3": TaskType.A3_DATA_EXTRACTION,
            "A4": TaskType.A4_STEPWISE_REASONING,
            "A5": TaskType.A5_SEMANTIC_REASONING,
            "A6": TaskType.A6_MULTI_DOCUMENT,
            "A7": TaskType.A7_PATTERN_ANALYSIS,
            "A8": TaskType.A8_SOD_DETECTION,
        }
        return task_type_map.get(task_type_str.upper())

    def _create_default_plan(self, context_dict: Dict) -> ExecutionPlan:
        """デフォルト実行計画を作成"""
        steps = [
            {
                "step": 1,
                "task_type": "A5",
                "purpose": "統制要件と実施記録の整合性を評価",
                "priority": "必須"
            }
        ]

        # 画像/PDFファイルがある場合はA2を追加
        evidence_files = context_dict.get("evidence_files", [])
        has_images = any(
            ef.get("extension", "").lower() in ['.pdf', '.jpg', '.jpeg', '.png']
            for ef in evidence_files
        )
        if has_images:
            steps.append({
                "step": 2,
                "task_type": "A2",
                "purpose": "承認印・日付・署名の確認",
                "priority": "必須"
            })

        if len(evidence_files) > 1:
            steps.append({
                "step": 3,
                "task_type": "A6",
                "purpose": "複数証跡の統合理解",
                "priority": "推奨"
            })

        return ExecutionPlan(
            analysis={"control_type": "未分類"},
            steps=steps,
            dependencies={},
            reasoning="デフォルト実行計画",
            potential_issues=[]
        )

    def _summarize_evidence(self, evidence_files: list) -> str:
        """証跡ファイル情報をサマリー化"""
        if not evidence_files:
            return "エビデンスファイルなし"

        parts = []
        for ef in evidence_files:
            if isinstance(ef, dict):
                parts.append(f"- {ef.get('file_name', 'N/A')} ({ef.get('mime_type', 'N/A')})")
            else:
                parts.append(f"- {ef.file_name} ({ef.mime_type})")

        return "\n".join(parts)

    def _format_task_results(self, task_results: List[Dict]) -> str:
        """タスク結果をフォーマット"""
        parts = []
        for r in task_results:
            status = "成功" if r.get("success") else "要確認"
            evidence_refs = ', '.join(r.get("evidence_references", [])) or 'なし'

            part = f"""
【{r.get('task_type', 'N/A')}: {r.get('task_name', 'N/A')}】
- 結果: {status} (信頼度: {r.get('confidence', 0.0):.2f})
- 分析内容: {r.get('reasoning', 'N/A')}
- 証跡参照: {evidence_refs}
"""
            parts.append(part)

        return "\n".join(parts)

    def _format_document_quotes(self, document_quotes: List[Dict]) -> str:
        """
        証跡からの引用文をフォーマット

        原文をそのまま記載する形式で出力します。
        括弧（「」）は使用せず、前後の文脈を含む幅広い引用を維持します。
        """
        if not document_quotes:
            return "（引用なし）"

        parts = []
        for quote_info in document_quotes:
            file_name = quote_info.get("file_name", "")
            location = quote_info.get("page_or_location", "")
            quotes = quote_info.get("quotes", [])

            if not quotes:
                single_quote = quote_info.get("quote", "")
                if single_quote:
                    quotes = [single_quote]

            if quotes:
                # ファイル名と位置情報をヘッダーとして追加
                header = f"【{file_name}】" if file_name else ""
                if location:
                    header += f" ({location})"

                if header:
                    parts.append(header)

                # 引用文は括弧なしでそのまま記載
                for q in quotes:
                    if q:
                        # 「」や『』で囲まず、原文そのまま記載
                        parts.append(q)

                parts.append("")  # 空行で区切り

        return "\n".join(parts).strip()

    def _simple_aggregate(self, task_results: List[Dict]) -> Dict:
        """単純集計による結果統合"""
        if not task_results:
            return {
                "evaluation_result": False,
                "judgment_basis": "タスク実行結果がありません",
                "document_quotes": [],
                "confidence": 0.0
            }

        successful_tasks = [r for r in task_results if r.get("success")]
        total_confidence = sum(r.get("confidence", 0.0) for r in task_results)
        avg_confidence = total_confidence / len(task_results)

        # 過半数が成功なら有効
        evaluation_result = len(successful_tasks) >= len(task_results) / 2

        # 判断根拠を構築
        judgment_parts = []
        for r in task_results:
            status = "○" if r.get("success") else "×"
            judgment_parts.append(f"{status} {r.get('task_type')}: {r.get('reasoning', 'N/A')[:100]}")

        return {
            "evaluation_result": evaluation_result,
            "judgment_basis": "\n".join(judgment_parts),
            "document_quotes": [],
            "confidence": avg_confidence
        }

    def _detect_judgment_contradictions(self, judgment_basis: str, evaluation_result: bool) -> List[Dict]:
        """
        判断根拠と評価結果の矛盾を検出

        LLMレビュー前に事前検出し、矛盾があれば修正を促す。
        これにより、LLMが見逃した矛盾も確実に検出できる。

        Args:
            judgment_basis: 判断根拠の文字列
            evaluation_result: 評価結果（True=有効, False=不備）

        Returns:
            検出された問題のリスト（issue形式）
        """
        if not judgment_basis:
            return []

        issues = []

        # 禁止フレーズの検出
        forbidden_phrases = [
            "追加証跡が必要", "追加証跡を要する", "追加の証跡が必要",
            "追加検証が必要", "追加で確認する必要がある",
            "フォローアップが必要", "フォローアップを前提に",
            "フォローアップ計画の明確化が必要",
            "結論を更新する", "結論を再評価する", "再評価する",
            "限定的有効性", "限定的有効", "条件付き有効",
            "有効と断定できず", "判断を保留", "未確定",
        ]

        for phrase in forbidden_phrases:
            if phrase in judgment_basis:
                issues.append({
                    "type": "禁止フレーズ",
                    "description": f"禁止フレーズ「{phrase}」が含まれています",
                    "correction": "提供された証跡の範囲で明確な結論を記述してください"
                })
                logger.warning(f"[矛盾検出] 禁止フレーズ検出: '{phrase}'")

        # 評価結果と判断根拠の矛盾検出
        if evaluation_result:  # 評価結果が「有効」の場合
            negative_indicators = [
                ("不備がある", "「不備がある」という記述は「有効」判定と矛盾"),
                ("不備が認められる", "「不備が認められる」という記述は「有効」判定と矛盾"),
                ("不備と判断", "「不備と判断」という記述は「有効」判定と矛盾"),
                ("不十分である", "「不十分である」という記述は「有効」判定と矛盾"),
                ("十分でない", "「十分でない」という記述は「有効」判定と矛盾"),
                ("欠如している", "「欠如している」という記述は「有効」判定と矛盾"),
                ("問題がある", "「問題がある」という記述は「有効」判定と矛盾"),
                ("課題がある", "「課題がある」という記述は「有効」判定と矛盾"),
                ("懸念がある", "「懸念がある」という記述は「有効」判定と矛盾"),
                ("統制が機能していない", "「統制が機能していない」という記述は「有効」判定と矛盾"),
                ("機能不全", "「機能不全」という記述は「有効」判定と矛盾"),
                ("有効性に疑義", "「有効性に疑義」という記述は「有効」判定と矛盾"),
                ("有効とは言えない", "「有効とは言えない」という記述は「有効」判定と矛盾"),
                ("確認できなかった", "「確認できなかった」という記述は「有効」判定と矛盾の可能性あり"),
                ("確認できていない", "「確認できていない」という記述は「有効」判定と矛盾の可能性あり"),
            ]
            for indicator, description in negative_indicators:
                if indicator in judgment_basis:
                    issues.append({
                        "type": "評価結果矛盾",
                        "description": description,
                        "correction": f"評価結果が「有効」なので、「{indicator}」を削除するか、評価結果を「不備」に変更してください"
                    })
                    logger.warning(f"[矛盾検出] 有効判定との矛盾: '{indicator}'")

        else:  # 評価結果が「不備」の場合
            positive_indicators = [
                ("有効に整備・運用されている", "「有効に整備・運用されている」という記述は「不備」判定と矛盾"),
                ("有効と判断する", "「有効と判断する」という記述は「不備」判定と矛盾"),
                ("適切に実施されている", "「適切に実施されている」という記述は「不備」判定と矛盾"),
                ("問題なく運用されている", "「問題なく運用されている」という記述は「不備」判定と矛盾"),
                ("統制は機能している", "「統制は機能している」という記述は「不備」判定と矛盾"),
            ]
            for indicator, description in positive_indicators:
                if indicator in judgment_basis:
                    issues.append({
                        "type": "評価結果矛盾",
                        "description": description,
                        "correction": f"評価結果が「不備」なので、「{indicator}」を削除するか、評価結果を「有効」に変更してください"
                    })
                    logger.warning(f"[矛盾検出] 不備判定との矛盾: '{indicator}'")

        return issues

    def _postprocess_judgment_basis(self, judgment_basis: str, evaluation_result: bool) -> str:
        """
        判断根拠の後処理
        禁止フレーズを検出し、適切な表現に置換する
        """
        if not judgment_basis:
            return judgment_basis

        # 禁止フレーズと置換パターン（出力結果から検出されたパターンを網羅）
        forbidden_patterns = [
            # 「追加証跡が必要」系（長いパターンを先に）
            ("追加の直接証跡（本文確認が可能な議事録、承認決議文、承認サイン等）が必要", "提供された証跡の範囲で確認した"),
            ("追加の直接証跡が必要", "提供された証跡の範囲で確認した"),
            ("追加証跡が必要", "提供された証跡の範囲で確認した"),
            ("追加証跡を要する", "提供された証跡の範囲で確認した"),
            ("追加の証跡が必要", "提供された証跡の範囲で確認した"),
            ("追加の独立証跡", "提供された証跡"),
            ("追加検証が必要", "確認した範囲で"),
            ("追加で確認する必要がある", "確認した範囲で"),
            ("運用証跡が不足している点を補完すれば", "提供された証跡から確認できる範囲で"),
            ("追加証跡の確認を要する", "提供された証跡で確認可能な範囲で"),
            ("追加証跡を取得・検証でき次第", "提供された証跡の範囲で"),

            # 「フォローアップ」系（長いパターンを先に）
            ("全文確認のフォローアップを行うべきである", "提供された証跡の範囲で確認した"),
            ("全文確認のフォローアップを行うべき", "提供された証跡の範囲で確認した"),
            ("次回フォローアップの結果を待つべき", "提供された証跡の範囲で判断した"),
            ("フォローアップによる追加証跡の確認を要する", "提供された証跡の範囲で統制の有効性を確認した"),
            ("フォローアップを行うべきである", "提供された証跡の範囲で確認した"),
            ("フォローアップを行うべき", "提供された証跡の範囲で確認した"),
            ("フォローアップが必要", "確認できた範囲で"),
            ("フォローアップを前提に", "確認できた範囲で"),
            ("フォローアップ計画の明確化が必要", "確認できた範囲で"),

            # 「再評価」「待つべき」系
            ("結論を更新する", "以上の確認結果に基づき判断した"),
            ("結論を再評価する", "以上の確認結果に基づき判断した"),
            ("再評価する", "判断した"),
            ("承認痕跡を追加で確認する必要がある", "提供された証跡の範囲で確認した"),
            ("承認の痕跡を追加で確認する必要がある", "提供された証跡の範囲で確認した"),
            ("最終判断は次回フォローアップの結果を待つべき", "提供された証跡の範囲で判断した"),
            ("結果を待つべき", "提供された証跡の範囲で判断した"),

            # 「根拠不足」系
            ("根拠が不足している", "提供された証跡の範囲で確認した"),
            ("根拠が薄い", "提供された証跡から確認できる範囲で"),
            ("直接的な結論を下す根拠が不足", "提供された証跡の範囲で確認した"),

            # 「限定的」系
            ("限定的有効性", "有効性"),
            ("限定的有効", "有効"),
            ("条件付き有効", "有効"),
            ("現状の結論は限定的有効とする", "以上より統制は有効と判断する"),

            # 「未確定」系
            ("未確定", "確認完了"),
            ("保留", "確認完了"),
            ("判断を保留", "確認した結果"),
            ("有効と断定できず", "有効性を確認した"),

            # 曖昧な表現
            ("完全に確認できなかった", "確認できた範囲で"),
            ("証跡が読み取れない", "証跡の内容を確認した結果"),
            ("証跡の完全性を損なっている", "証跡を確認した結果"),
            ("不備リスクを解消する追加検証が必要", "確認した範囲で統制の運用状況を評価した"),
            ("本文閲覧不可", "証跡を確認した結果"),
            ("ファイル形式制約", ""),
            ("可読性不足により", "証跡を確認した結果"),
            ("取得エラーにより", "証跡を確認した結果"),
            ("未確認である", "確認した範囲で"),
        ]

        result = judgment_basis
        for forbidden, replacement in forbidden_patterns:
            if forbidden in result:
                logger.info(f"[後処理] 禁止フレーズを置換: '{forbidden}' → '{replacement}'")
                result = result.replace(forbidden, replacement)

        # 評価結果が「有効」なのに否定的な表現が残っている場合の修正
        if evaluation_result:
            negative_indicators = [
                "不備がある", "不十分である", "問題がある",
                "統制が機能していない", "有効性に疑義"
            ]
            for indicator in negative_indicators:
                if indicator in result:
                    logger.warning(f"[後処理] 評価結果と矛盾する表現を検出: '{indicator}'")
                    # 矛盾は修正せず、ログに記録のみ（内容の改ざんを避ける）

        return result

    def _create_fallback_result(self, context: AuditContext, reason: str) -> AuditResult:
        """フォールバック結果を作成"""
        evidence_files_info = []
        for ef in context.evidence_files:
            evidence_files_info.append({
                "fileName": ef.file_name,
                "filePath": context.evidence_link
            })

        return AuditResult(
            item_id=context.item_id,
            evaluation_result=False,
            judgment_basis=f"評価失敗: {reason}",
            document_reference="（引用なし）",
            file_name=context.evidence_files[0].file_name if context.evidence_files else "",
            evidence_files_info=evidence_files_info,
            confidence=0.0,
        )
