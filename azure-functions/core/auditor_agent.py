"""
================================================================================
auditor_agent.py - 監査オーケストレーター
================================================================================

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
import logging
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
各評価タスクの実行結果を統合し、実務的な監査判断を下してください。

【統制記述】
{control_description}

【テスト手続き】
{test_procedure}

【エビデンスファイル】
{evidence_files}

【各タスクの実行結果】
{task_results}

【出力形式】
以下の形式で、内部統制テストの判断根拠を作成してください：

{{
    "evaluation_result": true/false,
    "judgment_basis": {{
        "control_objective": "この統制の目的（何を防止・検知するか）",
        "test_summary": "実施したテストの概要",
        "verification_items": [
            {{
                "item": "検証項目",
                "result": "○/×/△",
                "detail": "具体的な確認内容と結果",
                "evidence_reference": "根拠となる証跡の具体的記載"
            }}
        ],
        "conclusion": "総合判定の理由（なぜ有効/不備と判断したか）"
    }},
    "document_reference": "参照した規程・基準",
    "confidence": 0.0-1.0
}}

【重要な指示】
1. 抽象的な記述ではなく、証跡の具体的な内容を引用して記載
2. 「確認した」だけでなく「何を確認して何が分かったか」を明記
3. 不備がある場合は具体的な不備内容を記載
4. テスト手続きで求められている確認事項を漏れなく評価
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
        document_reference (str): 参照文書
        file_name (str): 主要証跡ファイル名
        task_results (List[TaskResult]): 各タスクの実行結果
        execution_plan (Optional[ExecutionPlan]): 実行計画
        confidence (float): 信頼度（0.0-1.0）

    使用例:
        ```python
        result = AuditResult(
            item_id="CLC-01",
            evaluation_result=True,
            judgment_basis="■ 統制目的: ...",
            document_reference="承認フロー規程",
            file_name="approval.pdf",
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
                - documentReference: 参照文書
                - fileName: ファイル名
                - _debug: デバッグ情報（オプション）
        """
        # 基本応答を構築
        response = {
            "ID": self.item_id,
            "evaluationResult": self.evaluation_result,
            "judgmentBasis": self.judgment_basis,
            "documentReference": self.document_reference,
            "fileName": self.file_name,
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
            document_reference = result.get("document_reference", "")
            confidence = result.get("confidence", 0.0)

            logger.info(f"[最終判断] 評価結果: {'有効' if evaluation_result else '要確認'}")
            logger.info(f"[最終判断] 信頼度: {confidence:.2f}")
            logger.debug(f"[最終判断] 参照文書: {document_reference}")

            return AuditResult(
                item_id=context.item_id,
                evaluation_result=evaluation_result,
                judgment_basis=judgment_basis,
                document_reference=document_reference,
                file_name=context.evidence_files[0].file_name if context.evidence_files else "",
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

    def _format_judgment_basis(self, judgment_data: dict) -> str:
        """
        判断根拠データを読みやすいテキストにフォーマット

        LLMが生成した判断根拠データを、ユーザーが理解しやすい
        階層構造のテキストに変換します。

        Args:
            judgment_data (dict): 判断根拠データ
                - control_objective: 統制目的
                - test_summary: テスト概要
                - verification_items: 検証項目リスト
                - conclusion: 結論

        Returns:
            str: フォーマット済みの判断根拠テキスト
        """
        if not judgment_data:
            logger.warning("[最終判断] 判断根拠データが空です")
            return "判断根拠の生成に失敗しました"

        parts = []

        # 統制目的
        if judgment_data.get("control_objective"):
            parts.append(f"■ 統制目的: {judgment_data['control_objective']}")

        # テスト概要
        if judgment_data.get("test_summary"):
            parts.append(f"■ テスト概要: {judgment_data['test_summary']}")

        # 検証項目
        verification_items = judgment_data.get("verification_items", [])
        if verification_items:
            parts.append("■ 検証結果:")

            for item in verification_items:
                result_mark = item.get("result", "－")
                item_name = item.get("item", "")
                detail = item.get("detail", "")
                evidence = item.get("evidence_reference", "")

                parts.append(f"  {result_mark} {item_name}")
                if detail:
                    parts.append(f"    → {detail}")
                if evidence:
                    parts.append(f"    （証跡: {evidence}）")

        # 結論
        if judgment_data.get("conclusion"):
            parts.append(f"■ 結論: {judgment_data['conclusion']}")

        return "\n".join(parts)

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

        # 参照文書を収集
        all_refs = []
        for r in task_results:
            all_refs.extend(r.evidence_references)
        document_reference = "; ".join(all_refs[:5]) if all_refs else "参照文書なし"

        # 最初の証跡ファイル名を取得
        file_name = context.evidence_files[0].file_name if context.evidence_files else ""

        logger.info(f"[結果統合] 単純集計結果: {'有効' if evaluation_result else '要確認'}")

        return AuditResult(
            item_id=context.item_id,
            evaluation_result=evaluation_result,
            judgment_basis=judgment_basis,
            document_reference=document_reference,
            file_name=file_name,
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

        return AuditResult(
            item_id=context.item_id,
            evaluation_result=False,
            judgment_basis=f"評価失敗: {reason}",
            document_reference="",
            file_name=context.evidence_files[0].file_name if context.evidence_files else "",
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
