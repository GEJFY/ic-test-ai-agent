"""
================================================================================
auditor_agent.py - 監査オーケストレーター（非推奨）
================================================================================

【非推奨警告】
このモジュールは非推奨です。代わりに graph_orchestrator.py の
GraphAuditOrchestrator を使用してください。
GraphAuditOrchestrator はセルフリフレクション機能を搭載し、
より高品質な評価結果を生成します。

【概要】
内部統制テスト評価の中核コンポーネントです。
統制記述とテスト手続きを分析し、最適なタスク（A1-A8）を選択・実行して
最終的な監査判断を導出します。

【アーキテクチャ】
```
AuditOrchestrator
    ├── 1. プランナー（LLM）
    │       ↓ 統制・テスト手続きを分析
    │       ↓ 必要なタスクを選択
    │
    ├── 2. タスク実行エンジン
    │       ↓ A1-A8を順次実行
    │       ↓ 各タスクの結果を収集
    │
    └── 3. 結果統合（LLM）
            ↓ タスク結果を統合
            ↓ 最終判断を生成
```

【タスク一覧】
- A1: 意味検索（セマンティックサーチ）
- A2: 画像認識 + 情報抽出
- A3: 構造化データ抽出
- A4: 段階的推論 + 計算
- A5: 意味検索 + 推論
- A6: 複数文書統合理解
- A7: パターン分析（時系列）
- A8: 競合検出（SoD/職務分掌）

【使用例】
```python
from core.auditor_agent import AuditOrchestrator
from core.tasks.base_task import AuditContext

# オーケストレーターを初期化
orchestrator = AuditOrchestrator(llm=llm, vision_llm=vision_llm)

# 監査コンテキストを作成
context = AuditContext.from_request(request_data)

# 評価を実行
result = await orchestrator.evaluate(context)

# 結果を取得
print(result.evaluation_result)  # True/False
print(result.judgment_basis)     # 判断根拠
```

================================================================================
"""
import warnings
import logging

# 非推奨警告を発行
warnings.warn(
    "AuditOrchestrator は非推奨です。"
    "代わりに graph_orchestrator.GraphAuditOrchestrator を使用してください。",
    DeprecationWarning,
    stacklevel=2
)
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

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

# 最終判断用プロンプト
# 各タスクの実行結果を統合し、実務的な監査判断を生成する
FINAL_JUDGMENT_PROMPT = """あなたは内部統制監査の専門家です。
内部統制テストの調書を作成してください。

【統制記述】
{control_description}

【テスト手続き】
{test_procedure}

【エビデンスファイル】
{evidence_files}

【各タスクの実行結果】
{task_results}

【出力形式】
以下のJSON形式で出力してください：

{{
    "evaluation_result": true/false,
    "judgment_basis": "判断根拠（文章形式）",
    "document_quotes": [
        {{
            "file_name": "証跡ファイル名（拡張子含む）",
            "quotes": ["引用文1", "引用文2"],
            "page_or_location": "ページ番号やセル位置"
        }}
    ],
    "confidence": 0.0-1.0
}}

【judgment_basisの書き方 - 経験豊富な専門家の文体】
経験20年以上の内部統制監査専門家として、簡潔かつ的確な判断根拠を記載してください（300〜500文字程度）。

【禁止する書き出しパターン - 以下は絶対に使わないこと】
× 「テスト手続きでは〜」「テスト手続きに基づき〜」
× 「当該統制の有効性を評価するため〜」
× 「内部統制テストの結果〜」「評価の結果〜」
× 「以下の通り確認した〜」「本件について〜」

【良い書き出しパターン - 直接事実から始める】
○ 「研修実施報告書および受講者リストを閲覧した。」
○ 「取締役会議事録を閲覧し、〜を確認した。」
○ 「〇〇年〇月〇日付の承認書により、〜を確認した。」

良い例：
「研修実施報告書および受講者リストを閲覧した。報告書より、2025年11月18日にeラーニング形式で研修が実施されたことを確認した。受講者リストより、対象者60名中53名が受講済であり、未受講者3名については12/09に督促が実施されていることを確認した。期限後受講4名は理由書が承認されており、全員の受講が完了している。以上より、本統制は有効に整備・運用されていると判断する。」

【document_quotesの書き方 - 原文をそのまま幅広に引用】
★★★【最重要ルール】★★★
- 証跡ファイルの原文を一字一句変えずにそのまま転記する
- 自分の言葉での言い換え・要約・省略は【絶対禁止】
- 前後の文脈を含めて100〜400文字程度を引用する
- 各証跡ファイルから2〜3箇所を引用する

【悪い引用の例 - このような引用は禁止】
× 「研修が実施されていることを確認した」← 要約している
× 「受講者名簿に全員の記録があった」← 言い換えている
× 「対象：全役職員」← 短すぎる（文脈がない）

【良い引用の例 - 原文をそのまま幅広に】
{{"file_name": "CLC-01_コンプライアンス研修実施報告書_2025年度.pdf", "quotes": ["1. 実施概要 対象：全役職員（役員・嘱託・派遣を含む） 実施日：2025/11/18（eラーニング配信開始） 実施方法：LMS（社内学習管理システム）にて受講、理解度テスト（10問）を実施 受講期限：2025/11/30、期限後受講は2025/12/10まで認める（特段の事情がある場合）", "3. 受講状況 本研修の受講状況は以下の通りである。受講済：53名（88.3%）、期限後受講：4名（6.7%）、未受講：3名（5.0%）、合計：60名 期限後受講者については、業務都合により期限内の受講が困難であったが、いずれも2025/12/06までに受講を完了している。"], "page_or_location": "1-2ページ"}}

その他のルール：
- 同一ファイルからの引用は1つのオブジェクトにまとめる（quotesは配列）
- 引用箇所（ページ、セクション、行）を必ず明記する
"""

# 実行計画立案用プロンプト
# 統制記述とテスト手続きを分析し、必要なタスクを選択する
PLANNER_PROMPT = """あなたは内部統制監査のAIプランナーです。
与えられた統制記述とテスト手続きを分析し、最適な評価タスクの実行計画を立案してください。

【重要】テスト手続きの内容を詳細に分析し、必要なタスクのみを選択してください。
- 承認印や署名の確認が必要な場合 → A2（画像認識）
- 数値の突合・計算検証が必要な場合 → A3（データ抽出）、A4（計算検証）
- 複数文書の整合性確認が必要な場合 → A6（複数文書統合）
- 継続性・定期実施の確認が必要な場合 → A7（パターン分析）
- 職務分掌・権限確認が必要な場合 → A8（SoD検出）
- 規程要件との整合性判定が必要な場合 → A5（意味推論）
- キーワード・記述の検索が必要な場合 → A1（意味検索）

【利用可能なタスクタイプ】
A1: 意味検索（セマンティックサーチ）- キーワード完全一致に頼らない意味的検索
A2: 画像認識 + 情報抽出 - PDFや画像から承認印、日付、氏名を抽出
A3: 構造化データ抽出 - 表から数値抽出、単位・科目名の正規化、突合
A4: 段階的推論 + 計算 - Chain-of-Thoughtで複雑な計算を検証
A5: 意味検索 + 推論 - 抽象的な規程要求と実施記録の整合性判定
A6: 複数文書統合理解 - バラバラな証跡からプロセスを再構成
A7: パターン分析（時系列） - 継続性確認、記録欠落の検出
A8: 競合検出（SoD/職務分掌） - 権限の競合・職務分掌違反の検出

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
        "control_type": "統制の種類（全社統制/業務プロセス統制/IT全般統制）",
        "key_assertions": ["主要なアサーション"],
        "risk_areas": ["リスク領域"]
    }},
    "execution_plan": [
        {{
            "step": 1,
            "task_type": "A1-A8のいずれか",
            "purpose": "このタスクを実行する目的",
            "expected_output": "期待される出力",
            "priority": "必須/推奨/任意"
        }}
    ],
    "task_dependencies": {{
        "task_type": ["依存するタスクタイプのリスト"]
    }},
    "reasoning": "この計画を立案した理由"
}}
"""


# =============================================================================
# データクラス定義
# =============================================================================

@dataclass
class ExecutionPlan:
    """
    実行計画データクラス

    プランナーLLMが生成した評価タスクの実行計画を保持します。

    Attributes:
        analysis (Dict[str, Any]): 統制分析結果
            - control_type: 統制の種類
            - key_assertions: 主要なアサーション
            - risk_areas: リスク領域
        steps (List[Dict[str, Any]]): 実行ステップのリスト
            - step: ステップ番号
            - task_type: タスクタイプ（A1-A8）
            - purpose: 実行目的
            - priority: 優先度（必須/推奨/任意）
        dependencies (Dict[str, List[str]]): タスク間の依存関係
        reasoning (str): 計画立案の理由
    """
    analysis: Dict[str, Any]
    steps: List[Dict[str, Any]]
    dependencies: Dict[str, List[str]]
    reasoning: str


@dataclass
class AuditResult:
    """
    監査結果データクラス

    評価処理の最終結果を保持し、API応答形式への変換機能を提供します。

    Attributes:
        item_id (str): テスト項目ID
        evaluation_result (bool): 評価結果（True=有効、False=要確認）
        judgment_basis (str): 判断根拠（日本語で詳細に記述）
        document_reference (str): 証跡からの引用文（判断根拠となった箇所）
        file_name (str): 主要証跡ファイル名
        evidence_files_info (List[Dict]): 証跡ファイル情報リスト（ファイル名とパス）
        task_results (List[TaskResult]): 各タスクの実行結果
        execution_plan (Optional[ExecutionPlan]): 実行計画
        confidence (float): 信頼度（0.0-1.0）

    使用例:
        ```python
        result = AuditResult(
            item_id="CLC-01",
            evaluation_result=True,
            judgment_basis="■ 統制目的: ...",
            document_reference="「承認者: 山田太郎、承認日: 2025/01/10」",
            file_name="approval.pdf",
            evidence_files_info=[
                {"fileName": "approval.pdf", "filePath": "C:/Evidence/approval.pdf"}
            ],
            confidence=0.85
        )
        response = result.to_response_dict()
        ```
    """
    item_id: str
    evaluation_result: bool
    judgment_basis: str
    document_reference: str
    file_name: str
    evidence_files_info: List[Dict[str, str]] = field(default_factory=list)
    task_results: List[TaskResult] = field(default_factory=list)
    execution_plan: Optional[ExecutionPlan] = None
    confidence: float = 0.0

    def to_response_dict(self, include_debug: bool = True) -> dict:
        """
        API応答形式の辞書に変換

        Excel VBAマクロが期待する形式に結果を変換します。

        Args:
            include_debug (bool): デバッグ情報を含めるか

        Returns:
            dict: API応答形式の辞書
                - ID: テスト項目ID
                - evaluationResult: 評価結果
                - judgmentBasis: 判断根拠
                - documentReference: 証跡からの引用文
                - fileName: 主要ファイル名（後方互換用）
                - evidenceFiles: 証跡ファイル情報配列（ファイル名とパス）
                - _debug: デバッグ情報（オプション）
        """
        # 実行計画サマリーを生成
        execution_plan_summary = self._format_execution_plan_summary()

        # 基本応答を構築
        response = {
            "ID": self.item_id,
            "evaluationResult": self.evaluation_result,
            "executionPlanSummary": execution_plan_summary,  # 実行計画サマリー
            "judgmentBasis": self.judgment_basis,
            "documentReference": self.document_reference,
            "fileName": self.file_name,
            "evidenceFiles": self.evidence_files_info,  # 複数ファイル対応
        }

        # デバッグ情報を追加（開発時のトラブルシューティング用）
        if include_debug:
            response["_debug"] = {
                "confidence": self.confidence,
                "executionPlan": None,
                "taskResults": []
            }

            # 実行計画の詳細を追加
            if self.execution_plan:
                response["_debug"]["executionPlan"] = {
                    "analysis": self.execution_plan.analysis,
                    "steps": self.execution_plan.steps,
                    "reasoning": self.execution_plan.reasoning
                }

            # 各タスクの実行結果を追加
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
        実行計画のサマリーを生成

        タスクタイプ参照と具体的なテスト内容を含む形式で出力します。
        形式: ○ テスト1 [A1:意味検索]: 具体的なテスト内容

        Returns:
            str: 実行計画サマリー
        """
        if not self.task_results:
            return "（タスク未実行）"

        task_summaries = []

        # 実行計画のstepsからtest_descriptionを取得
        step_descriptions = {}
        if self.execution_plan and self.execution_plan.steps:
            for idx, step in enumerate(self.execution_plan.steps):
                if isinstance(step, dict):
                    task_type = step.get("task_type", "")
                    test_desc = step.get("test_description", "") or step.get("purpose", "")
                    if task_type:
                        step_descriptions[task_type.upper()] = test_desc
                    step_descriptions[f"step_{idx}"] = test_desc

        # タスクタイプ別の名称
        task_type_names = {
            "A1": "意味検索",
            "A2": "画像認識",
            "A3": "構造化データ抽出",
            "A4": "段階的推論",
            "A5": "意味推論",
            "A6": "複数文書統合",
            "A7": "パターン分析",
            "A8": "SoD検出",
        }

        # デフォルト説明文
        default_descriptions = {
            "A1": "証跡の記載内容を意味的に検索・確認した",
            "A2": "証跡の印影・署名・日付を画像から確認した",
            "A3": "証跡の表データから数値を抽出・突合した",
            "A4": "計算結果をステップごとに検証した",
            "A5": "規程要求と実施記録の整合性を推論・判定した",
            "A6": "複数の証跡を統合して確認した",
            "A7": "複数期間の実施状況をパターン分析した",
            "A8": "職務分掌・権限分離を検証した",
        }

        for i, tr in enumerate(self.task_results, 1):
            status = "○" if tr.success else "×"
            task_type_short = ""
            task_type_name = ""

            if tr.task_type:
                task_type_short = tr.task_type.value.split("_")[0].upper()
                task_type_name = task_type_names.get(task_type_short, task_type_short)

            # 1. 実行計画のtest_descriptionを優先
            test_desc = step_descriptions.get(task_type_short, "")

            # 2. ステップ順序でのフォールバック
            if not test_desc:
                test_desc = step_descriptions.get(f"step_{i-1}", "")

            # 3. reasoningからの抽出
            if not test_desc and tr.reasoning:
                reasoning_text = tr.reasoning
                for prefix in ["A1_", "A2_", "A3_", "A4_", "A5_", "A6_", "A7_", "A8_"]:
                    if reasoning_text.upper().startswith(prefix):
                        reasoning_text = reasoning_text[len(prefix):].strip()
                        break
                if ":" in reasoning_text[:30]:
                    reasoning_text = reasoning_text.split(":", 1)[1].strip()
                if "。" in reasoning_text:
                    test_desc = reasoning_text.split("。")[0] + "。"
                else:
                    test_desc = reasoning_text[:100]

            # 4. デフォルト説明文（最終フォールバック）
            if not test_desc or (test_desc.startswith("A") and len(test_desc) < 5):
                test_desc = default_descriptions.get(task_type_short, "テストを実施した")

            # タスクタイプ参照 + 具体的なテスト内容を出力
            task_summaries.append(f"{status} テスト{i} [{task_type_short}:{task_type_name}]: {test_desc}")

        return "\n".join(task_summaries)


# =============================================================================
# メインクラス: AuditOrchestrator
# =============================================================================

class AuditOrchestrator:
    """
    監査オーケストレーター

    内部統制テスト評価の全体フローを制御するコアクラスです。
    統制記述とテスト手続きを分析し、適切なタスク（A1-A8）を選択・実行して
    最終的な監査判断を導出します。

    【処理フロー】
    1. プランニング: LLMで統制を分析し、必要なタスクを選択
    2. タスク実行: 選択されたタスクを順次実行
    3. 結果統合: タスク結果を統合し、最終判断を生成

    【タスク一覧】
    - A1: 意味検索（キーワードに頼らない文書検索）
    - A2: 画像認識（承認印・署名の検出）
    - A3: データ抽出（表からの数値抽出）
    - A4: 段階的推論（計算検証）
    - A5: 意味推論（規程要件との整合性判定）
    - A6: 複数文書統合（プロセス再構成）
    - A7: パターン分析（時系列・継続性確認）
    - A8: SoD検出（職務分掌違反の検出）

    Attributes:
        llm: テキスト処理用のLangChain ChatModel
        vision_llm: 画像処理用のVision対応ChatModel
        tasks: タスクハンドラーの辞書（TaskType -> BaseAuditTask）
        planner_prompt: 実行計画立案用のプロンプト
        parser: JSON出力パーサー

    使用例:
        ```python
        # オーケストレーターを初期化
        orchestrator = AuditOrchestrator(llm=llm, vision_llm=vision_llm)

        # 評価を実行
        result = await orchestrator.evaluate(context)
        ```
    """

    def __init__(self, llm=None, vision_llm=None):
        """
        オーケストレーターを初期化

        Args:
            llm: テキスト処理用のLangChain ChatModel
                 Noneの場合はデフォルトプランにフォールバック
            vision_llm: 画像処理用のVision対応ChatModel
                        Noneの場合はllmを使用
        """
        self.llm = llm
        self.vision_llm = vision_llm or llm

        logger.info("[オーケストレーター] 初期化開始")

        # 全タスクハンドラーを初期化
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

        logger.info(f"[オーケストレーター] タスクハンドラー登録完了: {len(self.tasks)}件")

        # プランナーコンポーネントを初期化
        self.planner_prompt = ChatPromptTemplate.from_template(PLANNER_PROMPT)
        self.parser = JsonOutputParser()

        logger.info("[オーケストレーター] 初期化完了")

    # =========================================================================
    # メイン評価処理
    # =========================================================================

    async def evaluate(self, context: AuditContext) -> AuditResult:
        """
        テスト項目を評価

        内部統制テスト項目の評価を実行し、結果を返します。
        処理は3段階で行われます：
        1. 実行計画の作成
        2. タスクの実行
        3. 結果の統合

        Args:
            context (AuditContext): 監査コンテキスト
                - 統制記述
                - テスト手続き
                - 証跡ファイル

        Returns:
            AuditResult: 評価結果
                - evaluation_result: 有効/要確認
                - judgment_basis: 判断根拠
                - document_reference: 参照文書

        Note:
            - 実行計画の作成に失敗した場合はフォールバック結果を返します
            - 各タスクでエラーが発生しても処理を継続します
        """
        logger.info("=" * 60)
        logger.info(f"[評価] 開始: {context.item_id}")
        logger.info(f"[評価] 統制記述: {context.control_description[:80]}...")
        logger.info(f"[評価] テスト手続き: {context.test_procedure[:80]}...")
        logger.info(f"[評価] 証跡ファイル数: {len(context.evidence_files)}")

        # ------------------------------------------------------------------
        # Step 1: 実行計画を作成
        # ------------------------------------------------------------------
        logger.info("[評価] Step 1: 実行計画を作成中...")
        plan = await self._create_plan(context)

        if not plan:
            logger.error(f"[評価] 実行計画の作成に失敗: {context.item_id}")
            return self._create_fallback_result(context, "実行計画の作成に失敗しました")

        # ------------------------------------------------------------------
        # Step 2: タスクを実行
        # ------------------------------------------------------------------
        logger.info("[評価] Step 2: タスクを実行中...")
        task_results = await self._execute_plan(plan, context)

        # ------------------------------------------------------------------
        # Step 3: 結果を統合
        # ------------------------------------------------------------------
        logger.info("[評価] Step 3: 結果を統合中...")
        result = await self._aggregate_results(context, plan, task_results)

        logger.info(f"[評価] 完了: {context.item_id} "
                   f"(結果: {'有効' if result.evaluation_result else '要確認'}, "
                   f"信頼度: {result.confidence:.2f})")
        logger.info("=" * 60)

        return result

    # =========================================================================
    # 実行計画作成
    # =========================================================================

    async def _create_plan(self, context: AuditContext) -> Optional[ExecutionPlan]:
        """
        実行計画を作成

        LLMを使用して統制記述とテスト手続きを分析し、
        最適なタスク実行順序を決定します。

        Args:
            context (AuditContext): 監査コンテキスト

        Returns:
            Optional[ExecutionPlan]: 実行計画
                - 成功時: ExecutionPlanオブジェクト
                - 失敗時: デフォルトプラン（A5, A2, A6）
        """
        # LLMが未設定の場合はデフォルトプランを使用
        if not self.llm:
            logger.warning("[プランナー] LLM未設定のため、デフォルトプランを使用")
            return self._create_default_plan(context)

        try:
            # 証跡情報のサマリーを作成
            evidence_info = self._summarize_evidence(context.evidence_files)

            logger.info(f"[プランナー] 計画作成開始: {context.item_id}")
            logger.debug(f"[プランナー] 統制記述: {context.control_description[:100]}...")
            logger.debug(f"[プランナー] 証跡ファイル数: {len(context.evidence_files)}")

            # LLMチェーンを構築して実行
            chain = self.planner_prompt | self.llm | self.parser

            result = await chain.ainvoke({
                "control_description": context.control_description,
                "test_procedure": context.test_procedure,
                "evidence_info": evidence_info,
            })

            # 結果をExecutionPlanに変換
            plan = ExecutionPlan(
                analysis=result.get("analysis", {}),
                steps=result.get("execution_plan", []),
                dependencies=result.get("task_dependencies", {}),
                reasoning=result.get("reasoning", ""),
            )

            # 作成した計画をログ出力
            logger.info(f"[プランナー] 分析結果: {plan.analysis}")
            logger.info(f"[プランナー] 実行ステップ数: {len(plan.steps)}")

            for i, step in enumerate(plan.steps):
                task_type = step.get('task_type', '不明')
                purpose = step.get('purpose', 'N/A')
                priority = step.get('priority', '未設定')
                logger.info(f"[プランナー] Step {i+1}: {task_type} "
                           f"(目的: {purpose}, 優先度: {priority})")

            logger.info(f"[プランナー] 立案理由: {plan.reasoning[:200]}...")

            return plan

        except Exception as e:
            logger.error(f"[プランナー] 計画作成エラー: {e}", exc_info=True)
            logger.info("[プランナー] デフォルトプランにフォールバック")
            return self._create_default_plan(context)

    def _create_default_plan(self, context: AuditContext) -> ExecutionPlan:
        """
        デフォルト実行計画を作成

        LLMによるプランニングが失敗した場合のフォールバック用です。
        基本的なタスク構成で安全に評価を実行します。

        Args:
            context (AuditContext): 監査コンテキスト

        Returns:
            ExecutionPlan: デフォルトの実行計画

        Note:
            デフォルトプランの構成:
            1. A5（意味推論）: 必ず実行（基本評価）
            2. A2（画像認識）: PDF/画像がある場合に実行
            3. A6（複数文書）: 複数ファイルがある場合に実行
        """
        logger.info("[プランナー] デフォルトプランを作成")

        steps = []

        # A5（意味推論）は必ず実行
        steps.append({
            "step": 1,
            "task_type": "A5",
            "purpose": "統制要件と実施記録の整合性を評価",
            "priority": "必須"
        })

        # 画像/PDFファイルがある場合はA2を追加
        has_images = any(
            ef.extension.lower() in ['.pdf', '.jpg', '.jpeg', '.png']
            for ef in context.evidence_files
        )
        if has_images:
            steps.append({
                "step": 2,
                "task_type": "A2",
                "purpose": "承認印・日付・署名の確認",
                "priority": "必須"
            })
            logger.debug("[プランナー] 画像/PDFファイルを検出 → A2を追加")

        # 複数ファイルがある場合はA6を追加
        if len(context.evidence_files) > 1:
            steps.append({
                "step": 3,
                "task_type": "A6",
                "purpose": "複数証跡の統合理解",
                "priority": "推奨"
            })
            logger.debug("[プランナー] 複数ファイルを検出 → A6を追加")

        logger.info(f"[プランナー] デフォルトプラン作成完了: {len(steps)}ステップ")

        return ExecutionPlan(
            analysis={"control_type": "未分類"},
            steps=steps,
            dependencies={},
            reasoning="デフォルト実行計画を使用",
        )

    # =========================================================================
    # タスク実行
    # =========================================================================

    async def _execute_plan(
        self,
        plan: ExecutionPlan,
        context: AuditContext
    ) -> List[TaskResult]:
        """
        実行計画に従ってタスクを実行

        計画に含まれる各タスクを順次実行し、結果を収集します。
        個々のタスクでエラーが発生しても処理を継続します。

        Args:
            plan (ExecutionPlan): 実行計画
            context (AuditContext): 監査コンテキスト

        Returns:
            List[TaskResult]: タスク実行結果のリスト

        Note:
            - 不明なタスクタイプはスキップされます
            - エラー発生時は失敗を示すTaskResultが追加されます
        """
        results = []
        total_steps = len(plan.steps)

        logger.info(f"[実行エンジン] タスク実行開始: {total_steps}ステップ")

        for idx, step in enumerate(plan.steps):
            step_num = idx + 1
            task_type_str = step.get("task_type", "")

            # タスクタイプを解析
            task_type = self._parse_task_type(task_type_str)
            if not task_type:
                logger.warning(f"[実行エンジン] Step {step_num}: "
                              f"不明なタスクタイプ: {task_type_str}")
                continue

            # タスクハンドラーを取得
            task = self.tasks.get(task_type)
            if not task:
                logger.warning(f"[実行エンジン] Step {step_num}: "
                              f"タスクハンドラーが見つかりません: {task_type}")
                continue

            # タスクを実行
            try:
                purpose = step.get('purpose', 'N/A')
                logger.info(f"[実行エンジン] Step {step_num}/{total_steps}: "
                           f"{task.task_name} ({task_type.value})")
                logger.info(f"[実行エンジン] 目的: {purpose}")

                result = await task.execute(context)
                results.append(result)

                status = "成功" if result.success else "要確認"
                logger.info(f"[実行エンジン] Step {step_num}: 完了 - "
                           f"{status}, 信頼度: {result.confidence:.2f}")
                logger.debug(f"[実行エンジン] Step {step_num}: "
                            f"分析内容: {result.reasoning[:150]}...")

            except Exception as e:
                logger.error(f"[実行エンジン] Step {step_num}: "
                            f"タスク実行エラー: {task_type.value} - {e}",
                            exc_info=True)

                # エラー結果を追加
                results.append(TaskResult(
                    task_type=task_type,
                    task_name=task.task_name,
                    success=False,
                    result=None,
                    reasoning=f"実行エラー: {str(e)}",
                    confidence=0.0
                ))

        logger.info(f"[実行エンジン] タスク実行完了: "
                   f"{len(results)}/{total_steps}件実行")

        return results

    def _parse_task_type(self, task_type_str: str) -> Optional[TaskType]:
        """
        タスクタイプ文字列をTaskType列挙型に変換

        Args:
            task_type_str (str): タスクタイプ文字列（例: "A1", "A2"）

        Returns:
            Optional[TaskType]: 対応するTaskType
                - 成功時: TaskType列挙値
                - 失敗時: None
        """
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

    # =========================================================================
    # 結果統合
    # =========================================================================

    async def _aggregate_results(
        self,
        context: AuditContext,
        plan: ExecutionPlan,
        task_results: List[TaskResult]
    ) -> AuditResult:
        """
        タスク結果を統合して最終判断を生成

        各タスクの実行結果を分析し、最終的な監査判断を導出します。
        LLMによる統合判断を試み、失敗時は単純集計にフォールバックします。

        Args:
            context (AuditContext): 監査コンテキスト
            plan (ExecutionPlan): 実行計画
            task_results (List[TaskResult]): タスク実行結果

        Returns:
            AuditResult: 最終的な監査結果
        """
        logger.info(f"[結果統合] タスク結果統合開始: {len(task_results)}件")

        # 結果がない場合はフォールバック
        if not task_results:
            logger.warning("[結果統合] タスク実行結果がありません")
            return self._create_fallback_result(context, "タスクの実行結果がありません")

        # 統計情報を計算
        successful_tasks = [r for r in task_results if r.success]
        total_confidence = sum(r.confidence for r in task_results)
        avg_confidence = total_confidence / len(task_results) if task_results else 0.0

        logger.info(f"[結果統合] 成功タスク: {len(successful_tasks)}/{len(task_results)}")
        logger.info(f"[結果統合] 平均信頼度: {avg_confidence:.2f}")

        # LLMによる最終判断を試行
        if self.llm:
            try:
                logger.info("[結果統合] LLMによる最終判断を生成中...")
                final_result = await self._generate_final_judgment(context, task_results)

                if final_result:
                    final_result.task_results = task_results
                    final_result.execution_plan = plan
                    logger.info("[結果統合] LLM最終判断の生成完了")
                    return final_result

            except Exception as e:
                logger.warning(f"[結果統合] LLM最終判断の生成に失敗: {e}")

        # フォールバック: 単純集計
        logger.info("[結果統合] 単純集計にフォールバック")
        return self._simple_aggregate(context, plan, task_results, avg_confidence)

    async def _generate_final_judgment(
        self,
        context: AuditContext,
        task_results: List[TaskResult]
    ) -> Optional[AuditResult]:
        """
        LLMで最終判断を生成

        タスク実行結果をLLMに入力し、実務的な監査判断を生成します。
        判断根拠は検証項目ごとに具体的な確認内容と証跡参照を含みます。

        Args:
            context (AuditContext): 監査コンテキスト
            task_results (List[TaskResult]): タスク実行結果

        Returns:
            Optional[AuditResult]: 最終判断結果
                - 成功時: AuditResultオブジェクト
                - 失敗時: None

        Note:
            生成される判断根拠には以下が含まれます:
            - 統制目的
            - テスト概要
            - 検証項目（○/×/△マーク付き）
            - 結論
        """
        logger.info("[最終判断] LLMで判断根拠を生成中...")

        # タスク結果をプロンプト用にフォーマット
        task_results_text = self._format_task_results_for_judgment(task_results)

        # 証跡ファイル一覧をフォーマット
        evidence_files_text = "\n".join([
            f"- {ef.file_name} ({ef.mime_type})"
            for ef in context.evidence_files
        ]) if context.evidence_files else "なし"

        try:
            # LLMチェーンを構築して実行
            prompt = ChatPromptTemplate.from_template(FINAL_JUDGMENT_PROMPT)
            chain = prompt | self.llm | self.parser

            result = await chain.ainvoke({
                "control_description": context.control_description,
                "test_procedure": context.test_procedure,
                "evidence_files": evidence_files_text,
                "task_results": task_results_text,
            })

            # 判断根拠を抽出してフォーマット
            judgment_data = result.get("judgment_basis", {})
            judgment_basis = self._format_judgment_basis(judgment_data)

            evaluation_result = result.get("evaluation_result", False)
            confidence = result.get("confidence", 0.0)

            # 判断根拠の後処理（禁止フレーズを置換）
            judgment_basis = self._postprocess_judgment_basis(judgment_basis, evaluation_result)

            # 証跡からの引用文を抽出
            document_quotes = result.get("document_quotes", [])
            document_reference = self._format_document_quotes(document_quotes)

            # 証跡ファイル情報を構築（ファイル名とパス）
            evidence_files_info = []
            for ef in context.evidence_files:
                evidence_files_info.append({
                    "fileName": ef.file_name,
                    "filePath": context.evidence_link  # 元のフォルダパス
                })

            logger.info(f"[最終判断] 評価結果: {'有効' if evaluation_result else '要確認'}")
            logger.info(f"[最終判断] 信頼度: {confidence:.2f}")
            logger.info(f"[最終判断] 引用文数: {len(document_quotes)}件")
            logger.debug(f"[最終判断] 証跡ファイル数: {len(evidence_files_info)}件")

            return AuditResult(
                item_id=context.item_id,
                evaluation_result=evaluation_result,
                judgment_basis=judgment_basis,
                document_reference=document_reference,
                file_name=context.evidence_files[0].file_name if context.evidence_files else "",
                evidence_files_info=evidence_files_info,
                confidence=confidence,
            )

        except Exception as e:
            logger.error(f"[最終判断] 判断生成エラー: {e}", exc_info=True)
            return None

    def _format_task_results_for_judgment(self, task_results: List[TaskResult]) -> str:
        """
        タスク結果を最終判断プロンプト用にフォーマット

        各タスクの実行結果を読みやすい形式に変換します。

        Args:
            task_results (List[TaskResult]): タスク実行結果

        Returns:
            str: フォーマット済みのタスク結果テキスト
        """
        parts = []

        for r in task_results:
            status = "成功" if r.success else "要確認"
            evidence_refs = ', '.join(r.evidence_references) if r.evidence_references else 'なし'

            part = f"""
【{r.task_type.value}: {r.task_name}】
- 結果: {status} (信頼度: {r.confidence:.2f})
- 分析内容: {r.reasoning}
- 証跡参照: {evidence_refs}
"""
            parts.append(part)

        return "\n".join(parts)

    def _format_judgment_basis(self, judgment_data) -> str:
        """
        判断根拠データを文章形式でフォーマット

        LLMが生成した判断根拠をそのまま返します。
        文字列の場合はそのまま、辞書の場合は旧形式として処理します。

        Args:
            judgment_data: 判断根拠（文字列または辞書）

        Returns:
            str: 判断根拠テキスト
        """
        # 文字列の場合はそのまま返す（新形式）
        if isinstance(judgment_data, str):
            if judgment_data:
                return judgment_data
            else:
                logger.warning("[最終判断] 判断根拠が空です")
                return "判断根拠の生成に失敗しました"

        # 辞書の場合は旧形式として処理（後方互換性）
        if not judgment_data:
            logger.warning("[最終判断] 判断根拠データが空です")
            return "判断根拠の生成に失敗しました"

        # 旧形式: 辞書から文章を組み立て
        parts = []

        if judgment_data.get("control_objective"):
            parts.append(judgment_data['control_objective'])

        if judgment_data.get("test_summary"):
            parts.append(judgment_data['test_summary'])

        if judgment_data.get("conclusion"):
            parts.append(f"■ 結論: {judgment_data['conclusion']}")

        return "\n".join(parts)

    def _postprocess_judgment_basis(self, judgment_basis: str, evaluation_result: bool) -> str:
        """
        判断根拠の後処理

        禁止フレーズを検出し、適切な表現に置換します。
        監査調書として不適切な表現を自動的に修正します。

        Args:
            judgment_basis: 判断根拠の文字列
            evaluation_result: 評価結果（True=有効, False=不備）

        Returns:
            str: 後処理済みの判断根拠
        """
        if not judgment_basis:
            return judgment_basis

        # 禁止フレーズと置換パターン（長いパターンを先に処理）
        forbidden_patterns = [
            # 「追加証跡が必要」系
            ("追加の直接証跡（本文確認が可能な議事録、承認決議文、承認サイン等）が必要", "提供された証跡の範囲で確認した"),
            ("追加の直接証跡が必要", "提供された証跡の範囲で確認した"),
            ("追加証跡が必要", "提供された証跡の範囲で確認した"),
            ("追加証跡を要する", "提供された証跡の範囲で確認した"),
            ("追加の証跡が必要", "提供された証跡の範囲で確認した"),
            ("追加の独立証跡", "提供された証跡"),
            ("追加検証が必要", "確認した範囲で"),
            ("追加で確認する必要がある", "確認した範囲で"),

            # 「フォローアップ」系
            ("全文確認のフォローアップを行うべきである", "提供された証跡の範囲で確認した"),
            ("全文確認のフォローアップを行うべき", "提供された証跡の範囲で確認した"),
            ("次回フォローアップの結果を待つべき", "提供された証跡の範囲で判断した"),
            ("フォローアップを行うべきである", "提供された証跡の範囲で確認した"),
            ("フォローアップを行うべき", "提供された証跡の範囲で確認した"),
            ("フォローアップが必要", "確認できた範囲で"),
            ("フォローアップを前提に", "確認できた範囲で"),

            # 「再評価」「待つべき」系
            ("最終判断は次回フォローアップの結果を待つべき", "提供された証跡の範囲で判断した"),
            ("結果を待つべき", "提供された証跡の範囲で判断した"),
            ("結論を更新する", "以上の確認結果に基づき判断した"),

            # 「根拠不足」系
            ("根拠が不足している", "提供された証跡の範囲で確認した"),
            ("根拠が薄い", "提供された証跡から確認できる範囲で"),
            ("直接的な結論を下す根拠が不足", "提供された証跡の範囲で確認した"),

            # 「限定的」系
            ("限定的有効性", "有効性"),
            ("限定的有効", "有効"),
            ("条件付き有効", "有効"),

            # エラー表現
            ("本文閲覧不可", "証跡を確認した結果"),
            ("ファイル形式制約", ""),
            ("可読性不足により", "証跡を確認した結果"),
            ("取得エラーにより", "証跡を確認した結果"),
        ]

        result = judgment_basis
        for forbidden, replacement in forbidden_patterns:
            if forbidden in result:
                logger.info(f"[後処理] 禁止フレーズを置換: '{forbidden}' → '{replacement}'")
                result = result.replace(forbidden, replacement)

        return result

    def _format_document_quotes(self, document_quotes: List[Dict]) -> str:
        """
        証跡からの引用文をフォーマット

        LLMが抽出した証跡引用情報を、読みやすいテキストに変換します。
        Excelの「該当文書からの引用」列に出力されます。
        原文をそのまま記載する形式で出力します（括弧なし）。

        Args:
            document_quotes (List[Dict]): 引用情報リスト
                - file_name: 証跡ファイル名
                - quotes: 引用文の配列
                - page_or_location: ページ番号やセル位置

        Returns:
            str: フォーマット済みの引用文テキスト

        出力例:
            【CLC-01_コンプライアンス研修.pdf】 (1ページ)
            1. 実施概要 対象：全役職員（役員・嘱託・派遣を含む） 実施日：2025/11/18...
        """
        if not document_quotes:
            logger.warning("[最終判断] 証跡からの引用がありません")
            return "（引用なし）"

        parts = []

        for quote_info in document_quotes:
            file_name = quote_info.get("file_name", "")
            location = quote_info.get("page_or_location", "")

            # 新形式（quotes配列）と旧形式（quote文字列）の両方に対応
            quotes = quote_info.get("quotes", [])
            if not quotes:
                # 旧形式: quote単独
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
                        parts.append(q)

                parts.append("")  # 空行で区切り

        return "\n".join(parts).strip()

    def _simple_aggregate(
        self,
        context: AuditContext,
        plan: ExecutionPlan,
        task_results: List[TaskResult],
        avg_confidence: float
    ) -> AuditResult:
        """
        単純集計による結果統合（フォールバック）

        LLMによる最終判断が失敗した場合のフォールバック処理です。
        タスク結果を単純に集計して評価結果を決定します。

        Args:
            context (AuditContext): 監査コンテキスト
            plan (ExecutionPlan): 実行計画
            task_results (List[TaskResult]): タスク実行結果
            avg_confidence (float): 平均信頼度

        Returns:
            AuditResult: 単純集計による監査結果

        Note:
            評価結果の決定ロジック:
            - 成功タスクが過半数 AND 重み付きスコアが正 → 有効
            - それ以外 → 要確認
        """
        logger.info("[結果統合] 単純集計を実行")

        successful_tasks = [r for r in task_results if r.success]

        # 評価結果を決定（信頼度で重み付けした多数決）
        weighted_success = sum(
            r.confidence if r.success else -r.confidence
            for r in task_results
        )
        evaluation_result = (
            weighted_success > 0 and
            len(successful_tasks) >= len(task_results) / 2
        )

        # 判断根拠を構築
        judgment_parts = []
        for r in task_results:
            status = "有効" if r.success else "要確認"
            judgment_parts.append(
                f"[{r.task_type.value}:{r.task_name}] {status} - {r.reasoning}"
            )
        judgment_basis = "\n".join(judgment_parts)

        # 証跡からの引用を収集（単純集計の場合はタスク結果から）
        all_refs = []
        for r in task_results:
            all_refs.extend(r.evidence_references)
        document_reference = "\n".join(all_refs[:5]) if all_refs else "（引用なし）"

        # 最初の証跡ファイル名を取得
        file_name = context.evidence_files[0].file_name if context.evidence_files else ""

        # 証跡ファイル情報を構築
        evidence_files_info = []
        for ef in context.evidence_files:
            evidence_files_info.append({
                "fileName": ef.file_name,
                "filePath": context.evidence_link
            })

        logger.info(f"[結果統合] 単純集計結果: {'有効' if evaluation_result else '要確認'}")

        return AuditResult(
            item_id=context.item_id,
            evaluation_result=evaluation_result,
            judgment_basis=judgment_basis,
            document_reference=document_reference,
            file_name=file_name,
            evidence_files_info=evidence_files_info,
            task_results=task_results,
            execution_plan=plan,
            confidence=avg_confidence,
        )

    # =========================================================================
    # ユーティリティメソッド
    # =========================================================================

    def _create_fallback_result(self, context: AuditContext, reason: str) -> AuditResult:
        """
        フォールバック結果を作成

        評価処理が失敗した場合のエラー結果を生成します。

        Args:
            context (AuditContext): 監査コンテキスト
            reason (str): 失敗理由

        Returns:
            AuditResult: エラーを示す監査結果
        """
        logger.warning(f"[結果統合] フォールバック結果を作成: {reason}")

        # 証跡ファイル情報を構築
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

    def _summarize_evidence(self, evidence_files: list) -> str:
        """
        証跡ファイル情報をサマリー化

        プランナーLLMに渡すための証跡ファイル一覧を作成します。

        Args:
            evidence_files (list): 証跡ファイルのリスト

        Returns:
            str: サマリーテキスト
        """
        if not evidence_files:
            return "エビデンスファイルなし"

        summary_parts = []
        for ef in evidence_files:
            summary_parts.append(f"- {ef.file_name} ({ef.mime_type})")

        return "\n".join(summary_parts)
