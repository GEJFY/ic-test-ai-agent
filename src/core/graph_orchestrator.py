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
import os
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
from .prompts import (
    PLANNER_PROMPT,
    PLAN_REVIEW_PROMPT,
    JUDGMENT_PROMPT,
    JUDGMENT_REVIEW_PROMPT,
    PLAN_REFINE_PROMPT,
    JUDGMENT_REFINE_PROMPT,
)
from .highlighting_service import HighlightingService
from infrastructure.config import (
    MAX_EVIDENCE_FILE_SIZE_MB,
    MAX_EVIDENCE_FILE_COUNT,
    MAX_EVIDENCE_TOTAL_SIZE_MB,
    ENABLE_EVIDENCE_SCREENING,
    EVIDENCE_SCREENING_USE_LLM,
)

# =============================================================================
# ログ設定
# =============================================================================

logger = logging.getLogger(__name__)

# =============================================================================
# プロンプトテンプレート
# =============================================================================
# プロンプトは src/core/prompts.py で一元管理されています。
# 詳細は prompts.py を参照してください。
#
# インポート済み:
# - PLANNER_PROMPT: テスト計画作成用
# - PLAN_REVIEW_PROMPT: 計画レビュー用
# - JUDGMENT_PROMPT: 最終判断作成用
# - JUDGMENT_REVIEW_PROMPT: 判断レビュー用
# - PLAN_REFINE_PROMPT: 計画修正用
# - JUDGMENT_REFINE_PROMPT: 判断修正用
# =============================================================================


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

    # 証憑バリデーション・スクリーニング
    evidence_validation: Optional[Dict]   # 入力制御の結果（P1）
    screening_summary: Optional[Dict]     # スクリーニング結果（P2）

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

    # フィードバック再評価関連
    user_feedback: Optional[str]      # ユーザーフィードバック
    previous_result: Optional[Dict]   # 前回の評価結果
    reevaluation_mode: Optional[str]  # 再評価モード（judgment_only/full）

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
    # フィードバック再評価関連
    feedback_applied: bool = False
    reevaluation_round: int = 0
    result_changed: bool = False

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
            "feedbackApplied": self.feedback_applied,
            "reevaluationRound": self.reevaluation_round,
            "resultChanged": self.result_changed,
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

    # タスクタイプの説明マップ
    TASK_TYPE_DESCRIPTIONS = {
        "A1": "意味検索",
        "A2": "画像認識",
        "A3": "データ抽出",
        "A4": "段階的推論",
        "A5": "意味的推論",
        "A6": "複数文書統合",
        "A7": "パターン分析",
        "A8": "職務分離検出",
    }

    def _get_task_type_label(self, task_type: str) -> str:
        """タスクタイプのラベルを取得（例: A5 → 【A5:意味的推論】）"""
        if not task_type:
            return ""
        desc = self.TASK_TYPE_DESCRIPTIONS.get(task_type, "")
        if desc:
            return f"【{task_type}:{desc}】"
        return f"【{task_type}】"

    def _format_execution_plan_summary(self) -> str:
        """
        実行計画のサマリーを生成（監査調書として適切な文章形式で記述）

        レビュー後の計画に基づき、タスク番号・タスク名とテスト方法を明記した計画を出力します。
        これは「計画」であるため、結果判断は含めません。
        """
        if not self.execution_plan or not self.execution_plan.steps:
            # タスク結果からタスクタイプを取得してフォールバック
            if self.task_results:
                parts = []
                for i, tr in enumerate(self.task_results, 1):
                    task_type = tr.task_type.value
                    task_name = tr.task_name
                    label = self._get_task_type_label(task_type)
                    parts.append(f"{label}\n{task_name}を実施する。")
                return "\n\n".join(parts)
            return "（計画未作成）"

        # 実行計画のstepsからタスク番号・目的・テスト内容を取得
        parts = []
        for step in self.execution_plan.steps:
            if not isinstance(step, dict):
                continue

            step_num = step.get("step", len(parts) + 1)
            task_type = step.get("task_type", "")
            purpose = step.get("purpose", "")
            test_desc = step.get("test_description", "")
            check_items = step.get("check_items", [])

            # タスク番号とタスク名を含むヘッダー
            if task_type:
                header = self._get_task_type_label(task_type)
            else:
                header = f"【ステップ{step_num}】"

            # テスト方法の説明を構築
            description_parts = []

            # 目的がある場合は追加
            if purpose:
                description_parts.append(purpose)

            # テスト説明を追加
            if test_desc:
                description_parts.append(test_desc)

            # 確認項目を文章に組み込む
            if check_items and isinstance(check_items, list) and len(check_items) > 0:
                items_text = "、".join(check_items[:5])  # 最大5項目まで表示
                description_parts.append(f"具体的には、{items_text}を確認する")

            # 説明を結合
            if description_parts:
                full_desc = "。".join(d.rstrip("。") for d in description_parts if d) + "。"
                parts.append(f"{header}\n{full_desc}")
            elif task_type:
                # 最低限タスクタイプだけは記載
                parts.append(f"{header}\n当該タスクにより証跡を確認する。")

        if parts:
            return "\n\n".join(parts)
        else:
            return "（計画詳細なし）"


# =============================================================================
# メインクラス: GraphAuditOrchestrator
# =============================================================================

class GraphAuditOrchestrator:
    """
    LangGraphベースの監査オーケストレーター

    セルフリフレクションパターンを実装し、
    計画作成→レビュー→実行→判断→レビューの
    品質向上サイクルを実現します。

    【環境変数による設定】
    - MAX_PLAN_REVISIONS: 計画レビューの最大修正回数（デフォルト: 1, 0でスキップ）
    - MAX_JUDGMENT_REVISIONS: 判断レビューの最大修正回数（デフォルト: 1, 0でスキップ）
    - SKIP_PLAN_CREATION: 計画作成を省略するか（デフォルト: false）
    """

    def __init__(self, llm=None, vision_llm=None):
        """
        オーケストレーターを初期化

        Args:
            llm: テキスト処理用のLangChain ChatModel
            vision_llm: 画像処理用のVision対応ChatModel
        """
        self.llm = llm
        self.vision_llm = vision_llm or llm

        # 環境変数から設定を読み込み
        self._load_config()

        logger.info("[GraphOrchestrator] 初期化開始")
        logger.info(f"[GraphOrchestrator] 設定: MAX_PLAN_REVISIONS={self.MAX_PLAN_REVISIONS}, "
                    f"MAX_JUDGMENT_REVISIONS={self.MAX_JUDGMENT_REVISIONS}, "
                    f"SKIP_PLAN_CREATION={self.SKIP_PLAN_CREATION}")

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

        # ハイライトサービス
        self.highlighting_service = HighlightingService()

        # LangGraphを構築
        self.graph = self._build_graph()

        logger.info("[GraphOrchestrator] 初期化完了")

    def _load_config(self):
        """
        環境変数から設定を読み込む（型安全・範囲チェック付き）

        【設定項目】
        - MAX_PLAN_REVISIONS: 計画レビューの最大修正回数（0でレビュースキップ、最大5）
        - MAX_JUDGMENT_REVISIONS: 判断レビューの最大修正回数（0でレビュースキップ、最大5）
        - SKIP_PLAN_CREATION: 計画作成を省略（true/false）
        """
        from infrastructure.config import get_env_int, get_env_bool

        self.MAX_PLAN_REVISIONS = get_env_int(
            "MAX_PLAN_REVISIONS", default=1, min_val=0, max_val=5
        )
        self.MAX_JUDGMENT_REVISIONS = get_env_int(
            "MAX_JUDGMENT_REVISIONS", default=1, min_val=0, max_val=5
        )
        self.SKIP_PLAN_CREATION = get_env_bool("SKIP_PLAN_CREATION", default=False)

    # =========================================================================
    # LangGraph構築
    # =========================================================================

    def _build_graph(self) -> StateGraph:
        """
        LangGraphを構築

        設定に応じてフローを動的に構築:
        - SKIP_PLAN_CREATION=true: 計画作成をスキップ
        - MAX_PLAN_REVISIONS=0: 計画レビューをスキップ
        - MAX_JUDGMENT_REVISIONS=0: 判断レビューをスキップ

        【フルモード】(デフォルト)
        create_plan → review_plan → (refine_plan →) execute_tasks
        → aggregate_results → review_judgment → (refine_judgment →) output

        【高速モード】(SKIP_PLAN_CREATION=true, MAX_*_REVISIONS=0)
        execute_tasks → aggregate_results → output
        """
        # StateGraphを作成
        workflow = StateGraph(AuditGraphState)

        # Evidence Screeningノード（有効時のみ）
        use_screening = ENABLE_EVIDENCE_SCREENING
        if use_screening:
            workflow.add_node("screen_evidence", self._node_screen_evidence)

        # ノードを追加（使用するノードのみ）
        if not self.SKIP_PLAN_CREATION:
            workflow.add_node("create_plan", self._node_create_plan)
            if self.MAX_PLAN_REVISIONS > 0:
                workflow.add_node("review_plan", self._node_review_plan)
                workflow.add_node("refine_plan", self._node_refine_plan)

        workflow.add_node("execute_tasks", self._node_execute_tasks)
        workflow.add_node("aggregate_results", self._node_aggregate_results)

        if self.MAX_JUDGMENT_REVISIONS > 0:
            workflow.add_node("review_judgment", self._node_review_judgment)
            workflow.add_node("refine_judgment", self._node_refine_judgment)

        workflow.add_node("output", self._node_output)

        # フローを構築
        if self.SKIP_PLAN_CREATION:
            if use_screening:
                workflow.set_entry_point("screen_evidence")
                workflow.add_edge("screen_evidence", "execute_tasks")
                logger.info("[GraphOrchestrator] 高速モード + スクリーニング有効")
            else:
                logger.info("[GraphOrchestrator] 高速モード: 計画作成をスキップ")
                workflow.set_entry_point("execute_tasks")
        else:
            if use_screening:
                # スクリーニング → 計画作成
                workflow.set_entry_point("screen_evidence")
                workflow.add_edge("screen_evidence", "create_plan")
            else:
                workflow.set_entry_point("create_plan")

            if self.MAX_PLAN_REVISIONS > 0:
                # 計画レビューあり
                workflow.add_edge("create_plan", "review_plan")
            else:
                # 計画レビューなし: 直接 execute_tasks へ
                logger.info("[GraphOrchestrator] 高速モード: 計画レビューをスキップ")
                workflow.add_edge("create_plan", "execute_tasks")

        # 計画レビュー後の条件分岐（レビューが有効な場合のみ）
        if self.MAX_PLAN_REVISIONS > 0 and not self.SKIP_PLAN_CREATION:
            workflow.add_conditional_edges(
                "review_plan",
                self._should_refine_plan,
                {
                    "refine": "refine_plan",
                    "execute": "execute_tasks"
                }
            )
            workflow.add_edge("refine_plan", "review_plan")

        # タスク実行 → 結果集約
        workflow.add_edge("execute_tasks", "aggregate_results")

        # 判断レビューの設定に応じた分岐
        if self.MAX_JUDGMENT_REVISIONS > 0:
            # 判断レビューあり
            workflow.add_edge("aggregate_results", "review_judgment")

            workflow.add_conditional_edges(
                "review_judgment",
                self._should_refine_judgment,
                {
                    "refine": "refine_judgment",
                    "output": "output"
                }
            )
            workflow.add_edge("refine_judgment", "review_judgment")
        else:
            # 判断レビューなし: 直接 output へ
            logger.info("[GraphOrchestrator] 高速モード: 判断レビューをスキップ")
            workflow.add_edge("aggregate_results", "output")

        workflow.add_edge("output", END)

        # モード情報をログ出力
        mode_desc = []
        if self.SKIP_PLAN_CREATION:
            mode_desc.append("計画作成スキップ")
        if self.MAX_PLAN_REVISIONS == 0:
            mode_desc.append("計画レビュースキップ")
        if self.MAX_JUDGMENT_REVISIONS == 0:
            mode_desc.append("判断レビュースキップ")

        if mode_desc:
            logger.info(f"[GraphOrchestrator] 高速モード有効: {', '.join(mode_desc)}")
        else:
            logger.info("[GraphOrchestrator] フルモード: セルフリフレクション有効")

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

    async def _node_screen_evidence(self, state: AuditGraphState) -> Dict:
        """
        証憑スクリーニングノード（Layer 3）

        統制記述・テスト手続きとの関連性に基づいて証憑ファイルをフィルタリング。
        Stage 1: ローカルテキスト抽出 + キーワードマッチ（LLMコスト0）
        Stage 2: LLMによる精密判定（オプション、環境変数で制御）
        """
        logger.info("[ノード] screen_evidence: 証憑スクリーニング開始...")

        context = state["context"]
        evidence_files = context.get("evidence_files", [])
        control_desc = context.get("control_description", "")
        test_procedure = context.get("test_procedure", "")

        if not evidence_files:
            logger.info("[ノード] screen_evidence: 証憑ファイルなし、スキップ")
            return {"screening_summary": {"screened": 0, "excluded": 0}}

        # ファイルが少数なら全通過（スクリーニング不要）
        if len(evidence_files) <= 3:
            logger.info(
                f"[ノード] screen_evidence: ファイル数{len(evidence_files)}件、"
                "スクリーニング省略（全件処理）"
            )
            # テキストプレビューのみ付与
            for ef in evidence_files:
                ef["text_preview"] = self._extract_text_preview(ef)
            return {
                "screening_summary": {
                    "screened": len(evidence_files),
                    "excluded": 0,
                    "excluded_files": [],
                    "skipped_screening": True,
                }
            }

        # キーワードを抽出（統制記述 + テスト手続きから）
        keywords = self._extract_screening_keywords(control_desc, test_procedure)
        logger.debug(f"[ノード] screen_evidence: キーワード = {keywords[:10]}")

        screened = []
        excluded = []

        for ef in evidence_files:
            # Stage 1: ローカルテキスト抽出 + キーワードマッチ
            text_preview = self._extract_text_preview(ef)
            ef["text_preview"] = text_preview

            score = self._calculate_relevance_score(
                ef.get("file_name", ""),
                text_preview,
                keywords,
                test_procedure,
            )
            ef["relevance_score"] = score

            if score >= 0.2:
                screened.append(ef)
            else:
                excluded.append(ef)

        # 除外ファイルの記録
        excluded_info = [
            {
                "file_name": ef.get("file_name", ""),
                "relevance_score": ef.get("relevance_score", 0),
                "reason": "関連性スコアが閾値未満",
            }
            for ef in excluded
        ]

        logger.info(
            f"[ノード] screen_evidence: "
            f"{len(screened)}件を処理対象、{len(excluded)}件を除外"
        )

        # コンテキストを更新（スクリーニング済みファイルのみ残す）
        context["evidence_files"] = screened

        return {
            "context": context,
            "screening_summary": {
                "screened": len(screened),
                "excluded": len(excluded),
                "excluded_files": excluded_info,
                "keywords_used": keywords[:20],
            },
        }

    def _extract_text_preview(self, ef_dict: dict, max_chars: int = 500) -> str:
        """
        証憑ファイルからテキストプレビューをローカル抽出する（LLMコスト0）

        Args:
            ef_dict: evidence_fileの辞書
            max_chars: プレビューの最大文字数

        Returns:
            先頭max_chars文字のテキストプレビュー
        """
        try:
            from .document_processor import DocumentProcessor

            result = DocumentProcessor.extract_text(
                file_name=ef_dict.get("file_name", ""),
                extension=ef_dict.get("extension", ""),
                base64_content=ef_dict.get("base64_content", ""),
                mime_type=ef_dict.get("mime_type"),
                use_di=False,  # ローカル抽出のみ（OCRサービス非使用）
            )
            text = result.text_content if result else ""
            return text[:max_chars]
        except Exception as e:
            logger.debug(f"[screen_evidence] テキスト抽出失敗: {ef_dict.get('file_name')} - {e}")
            return ""

    def _extract_screening_keywords(
        self, control_desc: str, test_procedure: str
    ) -> list:
        """
        統制記述・テスト手続きからスクリーニング用キーワードを抽出する

        日本語テキストから重要な名詞・固有名詞をキーワード化。
        """
        text = f"{control_desc} {test_procedure}"

        # 不要語を除去してキーワード候補を抽出
        stop_words = {
            "する", "こと", "ため", "おり", "また", "および", "より",
            "なお", "いる", "ある", "れる", "られる", "について",
            "において", "による", "に対して", "として", "の", "は",
            "を", "に", "が", "で", "と", "から", "まで", "へ",
            "確認", "実施", "テスト", "手続き", "以下", "上記",
        }

        # 文字列をトークン化（簡易的に助詞・句読点で分割）
        import re
        tokens = re.split(r'[、。\s・（）()「」\[\]【】,./]', text)
        keywords = []
        for token in tokens:
            token = token.strip()
            if len(token) >= 2 and token not in stop_words:
                keywords.append(token.lower())

        # 重複除去しつつ順序保持
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)

        return unique_keywords

    def _calculate_relevance_score(
        self,
        file_name: str,
        text_preview: str,
        keywords: list,
        test_procedure: str,
    ) -> float:
        """
        証憑ファイルの関連性スコアを計算する（0.0〜1.0）

        Args:
            file_name: ファイル名
            text_preview: テキストプレビュー
            keywords: 統制・手続き由来のキーワード
            test_procedure: テスト手続き全文

        Returns:
            関連性スコア（0.0=無関係、1.0=高関連）
        """
        score = 0.0
        name_lower = file_name.lower()
        text_lower = text_preview.lower() if text_preview else ""

        # 1. ファイル名のキーワードマッチ（重み高）
        name_matches = sum(1 for kw in keywords if kw in name_lower)
        score += min(0.4, name_matches * 0.15)

        # 2. テキスト内容のキーワードマッチ
        if text_lower:
            text_matches = sum(1 for kw in keywords if kw in text_lower)
            score += min(0.4, text_matches * 0.08)

        # 3. テキストが空でなければ最低限のスコアを付与
        #    （テキスト抽出できた＝何かしらの文書）
        if text_preview and len(text_preview) > 50:
            score += 0.1

        # 4. 承認系テストで画像/PDFなら追加スコア
        approval_keywords = ["承認", "押印", "署名", "決裁", "印影"]
        if any(kw in test_procedure for kw in approval_keywords):
            img_exts = (".pdf", ".png", ".jpg", ".jpeg")
            if any(name_lower.endswith(ext) for ext in img_exts):
                score += 0.15

        return min(1.0, score)

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
            prompt = ChatPromptTemplate.from_template(PLANNER_PROMPT)
            chain = prompt | self.llm | self.parser

            result = await chain.ainvoke({
                "control_description": context.get("control_description", ""),
                "test_procedure": context.get("test_procedure", ""),
                "evidence_info": evidence_info,
                "user_feedback_section": state.get("user_feedback") or "",
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
                "user_feedback_section": state.get("user_feedback") or "",
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

        # 計画作成スキップモードの場合、デフォルト計画を生成
        if not steps and self.SKIP_PLAN_CREATION:
            logger.info("[ノード] execute_tasks: 計画作成スキップモード - デフォルト計画を使用")
            default_plan = self._create_default_plan(context_dict)
            steps = default_plan.steps
            # 状態にも保存（後続のノードで参照される場合のため）
            execution_plan = {
                "analysis": default_plan.analysis,
                "execution_plan": steps,
                "dependencies": default_plan.dependencies,
                "reasoning": "高速モード: デフォルト計画を使用"
            }

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
            prompt = ChatPromptTemplate.from_template(JUDGMENT_PROMPT)
            chain = prompt | self.llm | self.parser

            result = await chain.ainvoke({
                "control_description": context.get("control_description", ""),
                "test_procedure": context.get("test_procedure", ""),
                "evidence_files": evidence_files_text,
                "execution_plan": str(execution_plan.get("execution_plan", [])),
                "task_results": task_results_text,
                "user_feedback_section": state.get("user_feedback") or "",
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
                "user_feedback_section": state.get("user_feedback") or "",
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
        # ただしプレースホルダーパターンは除外
        revised_basis = judgment_review.get("revised_judgment_basis", "")
        placeholder_patterns = [
            "要修正の場合のみ記載",
            "禁止フレーズを除去した",
            "承認の場合は空文字列",
            "ここに記載",
            "引用文を原文のまま厳密に転記",
            "例示表現を排し",
            "ファイル名・頁・行番号を特定",
        ]
        is_placeholder = any(p in revised_basis for p in placeholder_patterns) if revised_basis else True

        if revised_basis and not is_placeholder:
            judgment["judgment_basis"] = revised_basis
            logger.info("[ノード] refine_judgment: レビューの修正案を適用")
        elif is_placeholder and revised_basis:
            logger.warning(f"[ノード] refine_judgment: プレースホルダーパターン検出 - 無視: {revised_basis[:50]}...")

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

                # 元のdocument_quotesを保持（refine後に空なら復元用）
                original_quotes = judgment.get("document_quotes", [])

                refine_prompt = f"""★★★ 絶対厳守：JSON以外の文字を一切出力しないでください ★★★

以下の出力は全て禁止です（出力すると不合格）：
× 「修正案として」「以下の修正方針」「修正後の判断根拠」
× 「以下のJSONを出力します」「JSONは以下の通り」
× 説明文、前置き、後書き、コメント
× ```json ``` のようなコードブロック記法

最初の文字は必ず {{ で始め、最後の文字は }} で終わること。

【3つの原則】

■ 原則1: 判断根拠は「監査調書」として完結する
- 確認した証跡名、確認した事実（日付・数値・名称）、結論を含める
- 他の資料を参照しなくても内容が理解できる独立した文章にする
- 末尾は必ず「よって本統制は有効である」または「よって本統制には不備がある」で締める

■ 原則2: 引用は「証跡の複製」である
- 引用文＝証跡ファイルに存在する文字列のコピー
- あなたの言葉、解釈、要約、説明は一切含めない

■ 原則3: 結論は「確定的」である
- 「有効」または「不備」を明確に述べる
- 条件付き、暫定的、追加確認を要する表現は禁止

【修正すべき問題点】
{issues_text}

【証跡から確認できた事実】
{task_results_text}

★★★ 出力は以下のJSONのみ（説明文なし）★★★
{{
    "evaluation_result": true,
    "judgment_basis": "証跡名を閲覧した。具体的事実を確認した。整備状況として〜。運用状況として〜。よって本統制は有効である。",
    "document_quotes": [
        {{
            "file_name": "ファイル名.xlsx",
            "quotes": ["証跡から直接コピーした原文"],
            "page_or_location": "シート名"
        }}
    ],
    "confidence": 0.85
}}
"""
                prompt = ChatPromptTemplate.from_template(refine_prompt)
                chain = prompt | self.llm | self.parser

                result = await chain.ainvoke({})

                # 修正された判断で更新
                if result.get("judgment_basis"):
                    # judgment_basisから「修正案」等のプレフィックスを除去
                    clean_basis = self._clean_judgment_basis_prefix(result["judgment_basis"])
                    judgment["judgment_basis"] = clean_basis
                if result.get("evaluation_result") is not None:
                    judgment["evaluation_result"] = result["evaluation_result"]
                # document_quotesの更新（空の場合は元の引用を保持）
                new_quotes = result.get("document_quotes", [])
                if new_quotes and len(new_quotes) > 0:
                    judgment["document_quotes"] = new_quotes
                elif original_quotes:
                    # 新しい引用が空なら元の引用を保持
                    logger.info("[ノード] refine_judgment: 新規引用が空のため元の引用を保持")
                    judgment["document_quotes"] = original_quotes
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

        # テスト範囲の透明性情報を構築
        test_coverage = self._build_test_coverage(state)

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
            "test_coverage": test_coverage,
        }

        logger.info(f"[ノード] output: 最終結果生成完了 - "
                   f"{'有効' if final_result['evaluation_result'] else '要確認'}")

        return {"final_result": final_result}

    # =========================================================================
    # メイン評価処理
    # =========================================================================

    async def evaluate(
        self,
        context: AuditContext,
        user_feedback: Optional[str] = None,
        reevaluation_mode: Optional[str] = None,
        previous_result: Optional[Dict] = None,
    ) -> AuditResult:
        """
        テスト項目を評価

        LangGraphを使用してセルフリフレクション付きの評価を実行します。
        フィードバック再評価にも対応しています。

        Args:
            context (AuditContext): 監査コンテキスト
            user_feedback: ユーザーフィードバック（再評価時）
            reevaluation_mode: 再評価モード（"judgment_only" or "full"）
            previous_result: 前回の評価結果（judgment_only時に使用）

        Returns:
            AuditResult: 評価結果
        """
        is_feedback = bool(user_feedback)
        logger.info("=" * 60)
        if is_feedback:
            logger.info(
                f"[GraphOrchestrator] フィードバック再評価開始: {context.item_id} "
                f"(モード: {reevaluation_mode})"
            )
        else:
            logger.info(f"[GraphOrchestrator] 評価開始: {context.item_id}")

        # judgment_onlyモード: タスク結果を前回から引き継いでグラフを再構築
        if is_feedback and reevaluation_mode == "judgment_only" and previous_result:
            return await self._evaluate_judgment_only(
                context, user_feedback, previous_result
            )

        # 証憑ファイルのバリデーション（Layer 0: 入力制御）
        validated_files, validation_result = self._validate_evidence_files(
            context.evidence_files
        )
        if validation_result.get("warnings"):
            for w in validation_result["warnings"]:
                logger.warning(f"[GraphOrchestrator] 証憑バリデーション: {w}")

        # コンテキストを辞書形式に変換（検証済みファイルのみ使用）
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
                for ef in validated_files
            ]
        }

        # フィードバックセクションの構築
        feedback_section = self._build_feedback_section(
            user_feedback, previous_result
        )

        # 初期状態を設定
        initial_state: AuditGraphState = {
            "context": context_dict,
            "evidence_validation": validation_result,
            "screening_summary": None,
            "execution_plan": None,
            "plan_review": None,
            "plan_revision_count": 0,
            "task_results": [],
            "judgment": None,
            "judgment_review": None,
            "judgment_revision_count": 0,
            "user_feedback": feedback_section,
            "previous_result": previous_result,
            "reevaluation_mode": reevaluation_mode,
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

        # 証跡からの引用をフォーマット
        document_quotes = final_result.get("document_quotes", [])
        document_reference = self._format_document_quotes(document_quotes)

        # ハイライト処理
        try:
            temp_result = AuditResult(
                item_id=context.item_id,
                evaluation_result=final_result.get("evaluation_result", False),
                judgment_basis=final_result.get("judgment_basis", ""),
                document_reference=document_reference,
                file_name=context.evidence_files[0].file_name if context.evidence_files else "",
                confidence=final_result.get("confidence", 0.0),
            )

            evidence_files_info = await self.highlighting_service.highlight_evidence(
                temp_result,
                context
            )
            logger.info(f"[最終判断] ハイライト処理完了: {len(evidence_files_info)}件")

        except Exception as e:
            logger.error(f"[最終判断] ハイライト処理エラー: {e}", exc_info=True)
            # エラー時は元のファイルをBase64で返す（クライアント側でローカル保存するため）
            evidence_files_info = []
            for ef in context.evidence_files:
                evidence_files_info.append({
                    "fileName": ef.file_name,
                    "originalFileName": ef.file_name,
                    "filePath": context.evidence_link,
                    "base64": ef.base64_content if ef.base64_content else ""
                })

        # フィードバック再評価の情報を付与
        prev_eval = previous_result.get("evaluationResult") if previous_result else None
        current_eval = final_result.get("evaluation_result", False)

        # AuditResultを作成
        result = AuditResult(
            item_id=context.item_id,
            evaluation_result=current_eval,
            judgment_basis=final_result.get("judgment_basis", ""),
            document_reference=document_reference,
            file_name=context.evidence_files[0].file_name if context.evidence_files else "",
            evidence_files_info=evidence_files_info,
            feedback_applied=is_feedback,
            reevaluation_round=(
                (previous_result.get("reevaluationRound", 0) + 1)
                if is_feedback and previous_result else 0
            ),
            result_changed=(
                prev_eval is not None and prev_eval != current_eval
            ),
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
    # フィードバック再評価ヘルパー
    # =========================================================================

    def _build_feedback_section(
        self,
        user_feedback: Optional[str],
        previous_result: Optional[Dict],
    ) -> str:
        """
        ユーザーフィードバックセクションを構築

        LLMプロンプトの {user_feedback_section} に注入するテキストを生成。

        Args:
            user_feedback: ユーザーからのフィードバックテキスト
            previous_result: 前回の評価結果

        Returns:
            フォーマットされたフィードバックセクション（なければ空文字列）
        """
        if not user_feedback:
            return ""

        parts = []
        parts.append("\n【ユーザーからのフィードバック・追加指示】")
        parts.append("★ 以下のフィードバックを十分に考慮して再評価を行ってください ★")
        parts.append(user_feedback.strip())

        if previous_result:
            prev_eval = previous_result.get("evaluationResult")
            prev_basis = previous_result.get("judgmentBasis", "")
            prev_plan = previous_result.get("executionPlanSummary", "")

            parts.append("")
            parts.append("【前回の評価結果（参考）】")
            parts.append(f"- 評価結果: {'有効' if prev_eval else '非有効'}")
            if prev_basis:
                # 根拠は長いので先頭500文字まで
                basis_preview = prev_basis[:500]
                if len(prev_basis) > 500:
                    basis_preview += "..."
                parts.append(f"- 判断根拠: {basis_preview}")
            if prev_plan:
                parts.append(f"- 実行計画: {prev_plan[:200]}")

        return "\n".join(parts)

    async def _evaluate_judgment_only(
        self,
        context: AuditContext,
        user_feedback: str,
        previous_result: Dict,
    ) -> AuditResult:
        """
        判断のみ再評価（judgment_only モード）

        タスク実行をスキップし、前回の結果をベースに
        判断・根拠のみをフィードバックを踏まえて再生成する。

        Args:
            context: 監査コンテキスト
            user_feedback: ユーザーフィードバック
            previous_result: 前回の評価結果

        Returns:
            AuditResult: 再評価結果
        """
        logger.info(
            f"[GraphOrchestrator] judgment_only再評価: {context.item_id}"
        )

        # フィードバックセクションを構築
        feedback_section = self._build_feedback_section(
            user_feedback, previous_result
        )

        # 前回のタスク結果をフォーマット（_debugから取得）
        prev_task_results = previous_result.get("taskResults", [])
        task_results_text = ""
        if prev_task_results:
            for tr in prev_task_results:
                task_results_text += (
                    f"- {tr.get('taskType', 'N/A')}: {tr.get('taskName', '')}\n"
                    f"  成功: {tr.get('success', False)}, "
                    f"信頼度: {tr.get('confidence', 0.0)}\n"
                    f"  根拠: {tr.get('reasoning', '')}\n\n"
                )
        else:
            task_results_text = "（前回のタスク結果情報なし）"

        # 証憑ファイルの情報を取得
        evidence_files_text = self._summarize_evidence(
            [{"file_name": ef.file_name, "mime_type": ef.mime_type}
             for ef in context.evidence_files]
        )

        # 前回の実行計画サマリー
        prev_plan_summary = previous_result.get("executionPlanSummary", "")

        try:
            # LLMで判断を再生成（フィードバック付き）
            prompt = ChatPromptTemplate.from_template(JUDGMENT_PROMPT)
            chain = prompt | self.llm | self.parser

            result = await chain.ainvoke({
                "control_description": context.control_description,
                "test_procedure": context.test_procedure,
                "evidence_files": evidence_files_text,
                "execution_plan": prev_plan_summary,
                "task_results": task_results_text,
                "user_feedback_section": feedback_section,
            })

            logger.info(
                f"[GraphOrchestrator] judgment_only再評価完了: "
                f"{'有効' if result.get('evaluation_result') else '要確認'}"
            )

        except Exception as e:
            logger.error(
                f"[GraphOrchestrator] judgment_only再評価エラー: {e}",
                exc_info=True
            )
            return self._create_fallback_result(
                context, f"フィードバック再評価エラー: {e}"
            )

        # 判断の後処理
        judgment_basis = self._postprocess_judgment_basis(
            result.get("judgment_basis", ""),
            result.get("evaluation_result", False)
        )

        # 引用をフォーマット
        document_quotes = result.get("document_quotes", [])
        document_reference = self._format_document_quotes(document_quotes)

        # ハイライト処理
        try:
            temp_result = AuditResult(
                item_id=context.item_id,
                evaluation_result=result.get("evaluation_result", False),
                judgment_basis=judgment_basis,
                document_reference=document_reference,
                file_name=(
                    context.evidence_files[0].file_name
                    if context.evidence_files else ""
                ),
                confidence=result.get("confidence", 0.0),
            )
            evidence_files_info = await self.highlighting_service.highlight_evidence(
                temp_result, context
            )
        except Exception as e:
            logger.error(f"[judgment_only] ハイライトエラー: {e}", exc_info=True)
            evidence_files_info = [
                {
                    "fileName": ef.file_name,
                    "originalFileName": ef.file_name,
                    "filePath": context.evidence_link,
                    "base64": ef.base64_content or ""
                }
                for ef in context.evidence_files
            ]

        # 前回の評価結果と比較
        prev_eval = previous_result.get("evaluationResult")
        current_eval = result.get("evaluation_result", False)
        reeval_round = previous_result.get("reevaluationRound", 0) + 1

        return AuditResult(
            item_id=context.item_id,
            evaluation_result=current_eval,
            judgment_basis=judgment_basis,
            document_reference=document_reference,
            file_name=(
                context.evidence_files[0].file_name
                if context.evidence_files else ""
            ),
            evidence_files_info=evidence_files_info,
            confidence=result.get("confidence", 0.0),
            feedback_applied=True,
            reevaluation_round=reeval_round,
            result_changed=(prev_eval is not None and prev_eval != current_eval),
        )

    # =========================================================================
    # 証憑バリデーション（Layer 0: 入力制御）
    # =========================================================================

    def _validate_evidence_files(
        self, evidence_files: list
    ) -> tuple:
        """
        証憑ファイルのサイズ・件数バリデーション

        超過ファイルを除外し、警告リストを返す。

        Args:
            evidence_files: EvidenceFileオブジェクトのリスト

        Returns:
            (検証済みファイルリスト, バリデーション結果dict)
        """
        max_file_bytes = MAX_EVIDENCE_FILE_SIZE_MB * 1024 * 1024
        max_total_bytes = MAX_EVIDENCE_TOTAL_SIZE_MB * 1024 * 1024

        accepted = []
        warnings = []
        skipped_files = []
        total_bytes = 0
        original_count = len(evidence_files)

        for ef in evidence_files:
            # Base64 → バイナリサイズの概算
            b64_len = len(ef.base64_content) if ef.base64_content else 0
            file_bytes = (b64_len * 3) // 4

            # 個別ファイルサイズチェック
            if file_bytes > max_file_bytes:
                size_mb = file_bytes / (1024 * 1024)
                msg = (
                    f"ファイルサイズ超過: {ef.file_name} "
                    f"({size_mb:.1f}MB > {MAX_EVIDENCE_FILE_SIZE_MB}MB)"
                )
                warnings.append(msg)
                skipped_files.append({
                    "file_name": ef.file_name,
                    "reason": f"サイズ超過 ({size_mb:.1f}MB)",
                    "size_mb": round(size_mb, 1),
                })
                logger.warning(f"[Evidence Validation] {msg}")
                continue

            # 合計サイズチェック
            if total_bytes + file_bytes > max_total_bytes:
                size_mb = file_bytes / (1024 * 1024)
                msg = (
                    f"合計サイズ超過のため除外: {ef.file_name} "
                    f"(累計が{MAX_EVIDENCE_TOTAL_SIZE_MB}MB超)"
                )
                warnings.append(msg)
                skipped_files.append({
                    "file_name": ef.file_name,
                    "reason": f"合計サイズ超過",
                    "size_mb": round(size_mb, 1),
                })
                logger.warning(f"[Evidence Validation] {msg}")
                continue

            # 件数チェック
            if len(accepted) >= MAX_EVIDENCE_FILE_COUNT:
                msg = (
                    f"ファイル件数超過のため除外: {ef.file_name} "
                    f"(上限{MAX_EVIDENCE_FILE_COUNT}件)"
                )
                warnings.append(msg)
                skipped_files.append({
                    "file_name": ef.file_name,
                    "reason": f"件数上限超過",
                })
                logger.warning(f"[Evidence Validation] {msg}")
                continue

            accepted.append(ef)
            total_bytes += file_bytes

        validation_result = {
            "original_count": original_count,
            "accepted_count": len(accepted),
            "skipped_count": len(skipped_files),
            "skipped_files": skipped_files,
            "total_size_mb": round(total_bytes / (1024 * 1024), 1),
            "warnings": warnings,
        }

        if skipped_files:
            logger.info(
                f"[Evidence Validation] {original_count}件中{len(accepted)}件を処理対象、"
                f"{len(skipped_files)}件をスキップ"
            )

        return accepted, validation_result

    # =========================================================================
    # テスト範囲の透明性
    # =========================================================================

    def _build_test_coverage(self, state: AuditGraphState) -> dict:
        """
        テスト範囲の透明性情報を構築する

        バリデーション・スクリーニング・タスク実行の結果を統合し、
        何を検査し、何を検査しなかったかを明確にする。
        """
        evidence_validation = state.get("evidence_validation") or {}
        screening_summary = state.get("screening_summary") or {}
        context = state.get("context", {})
        task_results = state.get("task_results", [])

        # 受信ファイル数（バリデーション前の元の件数）
        original_count = evidence_validation.get("original_count", 0)
        # バリデーション後の件数
        validated_count = evidence_validation.get("accepted_count", original_count)
        # スクリーニング後の処理件数
        screened_count = screening_summary.get("screened", validated_count)
        # 現在のコンテキスト内の件数
        current_files = context.get("evidence_files", [])

        # 除外ファイル情報を統合
        files_skipped_validation = evidence_validation.get("skipped_files", [])
        files_excluded_screening = screening_summary.get("excluded_files", [])

        # 警告メッセージの構築
        warnings = []
        if files_skipped_validation:
            warnings.append(
                f"{len(files_skipped_validation)}件のファイルがサイズ/件数制限により除外されました"
            )
        if files_excluded_screening:
            warnings.append(
                f"{len(files_excluded_screening)}件のファイルが関連性スクリーニングにより除外されました"
            )

        coverage_warning = "。".join(warnings) if warnings else None

        return {
            "files_received": original_count,
            "files_after_validation": validated_count,
            "files_after_screening": screened_count,
            "files_processed": len(current_files),
            "files_skipped_validation": files_skipped_validation,
            "files_excluded_screening": files_excluded_screening,
            "coverage_warning": coverage_warning,
        }

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
        """
        証跡ファイル情報をサマリー化

        text_previewがある場合（スクリーニング済み）はプレビューを含める。
        プランナーがファイル内容を理解した上でタスク選択できるようにする。
        """
        if not evidence_files:
            return "エビデンスファイルなし"

        parts = []
        for ef in evidence_files:
            if isinstance(ef, dict):
                name = ef.get('file_name', 'N/A')
                mime = ef.get('mime_type', 'N/A')
                preview = ef.get('text_preview', '')
                score = ef.get('relevance_score')

                line = f"- {name} ({mime})"
                if score is not None:
                    line += f" [関連性: {score:.2f}]"
                if preview:
                    # プレビューは先頭200文字に制限
                    truncated = preview[:200].replace('\n', ' ')
                    line += f"\n  内容概要: {truncated}"
                parts.append(line)
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
        証跡からの引用文をフォーマット（原則ベースの品質チェック付き）

        原則: 引用文は「証跡の複製」であり、評価者の解釈を含まない

        形式: [ファイル名] 引用箇所：
        原文（証跡からそのままコピーした文字列）
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
                for q in quotes:
                    if q:
                        # 引用文の品質チェック（原則ベース）
                        clean_quote = self._clean_quote_text(q)

                        # 形式: [ファイル名] 引用箇所：原文
                        source_info = ""
                        if file_name:
                            source_info = f"[{file_name}]"
                        if location:
                            source_info += f" {location}："
                        elif file_name:
                            source_info += "："

                        if source_info:
                            parts.append(f"{source_info}\n{clean_quote}")
                        else:
                            parts.append(clean_quote)

        # 引用が全て空だった場合のフォールバック
        if not parts:
            return "（引用なし）"

        # 各引用を空行で区切る
        return "\n\n".join(parts)

    def _clean_quote_text(self, quote: str) -> str:
        """
        引用文の品質チェックとクリーニング（原則ベース）

        原則: 引用は証跡の複製であり、評価者の視点・解釈を含まない

        検出パターン:
        - 「〜であること」「〜が確認できる」等の評価者視点の表現
        - 「例：」「抜粋：」等の前置き
        - 重複した内容
        """
        if not quote:
            return quote

        result = quote.strip()

        # 評価者視点の表現を検出してログ出力（除去はしない、警告のみ）
        # 原則: 内容を勝手に改変しない。ただし問題があることは記録する
        evaluator_patterns = [
            "であること",
            "が確認できる",
            "が示されている",
            "が指摘されている",
            "と記載されている",
            "を確認した",
            "が存在する",
            "であることがわかる",
        ]

        for pattern in evaluator_patterns:
            if pattern in result:
                logger.warning(f"[引用品質] 評価者視点の表現を検出: '{pattern}' in '{result[:50]}...'")

        # 重複する内容の検出（同じ文が2回出現）
        sentences = result.split("。")
        seen = set()
        unique_sentences = []
        for s in sentences:
            s_clean = s.strip()
            if s_clean and s_clean not in seen:
                seen.add(s_clean)
                unique_sentences.append(s_clean)
            elif s_clean in seen:
                logger.info(f"[引用品質] 重複文を除去: '{s_clean[:30]}...'")

        if len(unique_sentences) < len([s for s in sentences if s.strip()]):
            result = "。".join(unique_sentences)
            if result and not result.endswith("。"):
                result += "。"

        return result

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

    def _clean_judgment_basis_prefix(self, text: str) -> str:
        """
        判断根拠から「修正案」等のプレフィックスを除去（refine時に使用）

        LLMが「修正案として〜」「以下のJSONを〜」等の前置きを出力した場合、
        それを除去して本文のみを返す。
        """
        if not text:
            return text

        import re

        result = text.strip()

        # よくあるパターンを除去
        removal_patterns = [
            r'^修正案[：:]\s*',
            r'^【修正案】\s*',
            r'^修正案として[、,]?\s*',
            r'^以下の修正方針に沿って[、,]?[^。]*。\s*',
            r'^以下のJSONを出力[^。]*。\s*',
            r'^JSONは以下の通り[^。]*。\s*',
            r'^修正後の判断根拠[：:]\s*',
            r'^\d+[\)）]\s*',  # 番号付きリスト
        ]

        for pattern in removal_patterns:
            result = re.sub(pattern, '', result, flags=re.MULTILINE)

        # 先頭の空白・改行を除去
        result = result.lstrip()

        if result != text:
            logger.info(f"[refine_judgment] プレフィックス除去: '{text[:30]}...' → '{result[:30]}...'")

        return result

    def _postprocess_judgment_basis(self, judgment_basis: str, evaluation_result: bool) -> str:
        """
        判断根拠の後処理（原則ベース）

        3つの原則に基づいて判断根拠を検証・修正:
        1. 監査調書として完結している（事実と結論を含む）
        2. 確定的な結論を述べている（曖昧表現がない）
        3. メタ的な説明を含まない（方針説明ではなく本文のみ）
        """
        if not judgment_basis:
            return judgment_basis

        result = judgment_basis

        # =========================================
        # 原則1: メタ的な説明の除去
        # 「修正方針の説明」「以下の〜」などLLMが出力しがちな前置きを除去
        # =========================================
        meta_prefixes = [
            # 修正案系パターン
            "修正案",
            "修正案：",
            "修正案:",
            "【修正案】",
            "以下の修正方針に沿って",
            "修正案として",
            "以下は修正後の",
            "修正後の判断根拠",
            "以下の判断",
            "以下のとおり修正",
            "レビューフィードバックを反映し",
            "以下の点を改善した",
            "以下のJSONを出力",
            "JSONは以下の通り",
            # プレースホルダーパターン
            "要修正の場合のみ記載",
            "禁止フレーズを除去した",
            "引用文を原文のまま厳密に転記",
            "例示表現を排し",
            "ファイル名・頁・行番号を特定",
            "結論の根拠を証跡に即して再確認",
            "最終判断を再表現",
        ]

        for prefix in meta_prefixes:
            if prefix in result:
                # 該当する文を探して除去（文末の「。」まで）
                start_idx = result.find(prefix)
                if start_idx != -1:
                    # この文の終わりを探す
                    end_idx = result.find("。", start_idx)
                    if end_idx != -1:
                        removed_part = result[start_idx:end_idx + 1]
                        result = result[:start_idx] + result[end_idx + 1:]
                        logger.info(f"[後処理] メタ説明を除去: '{removed_part[:50]}...'")

        # 先頭の番号付きリスト形式を除去（「1) 〜 2) 〜」など）
        import re
        result = re.sub(r'^[\s]*\d+[\)）]\s*[^\n]+[\n\s]*', '', result)

        # =========================================
        # 原則2: 確定的でない表現の修正
        # 曖昧な結論を確定的な表現に置換
        # =========================================
        uncertain_to_certain = [
            # 追加確認系 → 確認完了として表現
            ("追加証跡が必要", "提供された証跡の範囲で確認した"),
            ("追加で確認する必要", "確認した"),
            ("フォローアップを要する", "確認した範囲で判断した"),
            ("フォローアップが必要", "確認した範囲で判断した"),
            ("再評価が必要", "確認した結果"),
            ("結果を待つべき", "確認した範囲で判断した"),

            # 限定・条件付き系 → 確定表現に
            ("限定的有効", "有効"),
            ("条件付き有効", "有効"),
            ("暫定的に有効", "有効"),

            # 推測系 → 事実表現に
            ("と考えられる", "である"),
            ("と思われる", "である"),
            ("と推測される", "と確認した"),
        ]

        for uncertain, certain in uncertain_to_certain:
            if uncertain in result:
                logger.info(f"[後処理] 曖昧表現を修正: '{uncertain}' → '{certain}'")
                result = result.replace(uncertain, certain)

        # =========================================
        # 原則3: 非ASCII文字の混入チェック
        # 韓国語などの不正な文字が混入していないか確認
        # =========================================
        # 許可する文字: 日本語（ひらがな、カタカナ、漢字）、ASCII、記号
        cleaned_chars = []
        for char in result:
            code = ord(char)
            # ASCII (0-127), 日本語ひらがな (3040-309F), カタカナ (30A0-30FF),
            # CJK統合漢字 (4E00-9FFF), 全角記号 (3000-303F), 半角カナ (FF00-FFEF)
            if (code < 128 or
                0x3040 <= code <= 0x309F or  # ひらがな
                0x30A0 <= code <= 0x30FF or  # カタカナ
                0x4E00 <= code <= 0x9FFF or  # 漢字
                0x3000 <= code <= 0x303F or  # 全角記号
                0xFF00 <= code <= 0xFFEF):   # 半角カナ・全角英数
                cleaned_chars.append(char)
            else:
                # 不正な文字はスペースに置換
                logger.warning(f"[後処理] 不正な文字を検出・除去: U+{code:04X}")
                cleaned_chars.append(' ')

        result = ''.join(cleaned_chars)

        # 連続するスペースを1つに
        result = re.sub(r' +', ' ', result)

        # 先頭・末尾の空白を除去
        result = result.strip()

        # =========================================
        # 評価結果との整合性チェック（ログのみ）
        # =========================================
        if evaluation_result:
            negative_indicators = ["不備がある", "不十分である", "問題がある", "有効性に疑義"]
            for indicator in negative_indicators:
                if indicator in result:
                    logger.warning(f"[後処理] 評価結果(有効)と矛盾する表現を検出: '{indicator}'")

        return result

    def _create_fallback_result(self, context: AuditContext, reason: str) -> AuditResult:
        """フォールバック結果を作成"""
        evidence_files_info = []
        for ef in context.evidence_files:
            evidence_files_info.append({
                "fileName": ef.file_name,
                "originalFileName": ef.file_name,
                "filePath": context.evidence_link,
                "base64": ef.base64_content if ef.base64_content else ""
            })

        # ユーザーフレンドリーなエラーメッセージに変換
        user_message = self._convert_to_user_friendly_error(reason)

        return AuditResult(
            item_id=context.item_id,
            evaluation_result=False,
            judgment_basis=user_message,
            document_reference="（引用なし）",
            file_name=context.evidence_files[0].file_name if context.evidence_files else "",
            evidence_files_info=evidence_files_info,
            confidence=0.0,
        )

    def _convert_to_user_friendly_error(self, reason: str) -> str:
        """技術的なエラーメッセージをユーザーフレンドリーな形式に変換"""
        # エラーパターンと対応するメッセージ
        error_patterns = [
            ("グラフ実行エラー", "システム処理中にエラーが発生しました。再度実行してください。"),
            ("timeout", "処理がタイムアウトしました。証跡ファイルのサイズを確認してください。"),
            ("rate limit", "API制限に達しました。しばらく待ってから再実行してください。"),
            ("connection", "接続エラーが発生しました。ネットワーク接続を確認してください。"),
            ("parse", "証跡ファイルの読み取りに失敗しました。ファイル形式を確認してください。"),
            ("認証", "API認証に失敗しました。設定を確認してください。"),
        ]

        reason_lower = reason.lower()
        for pattern, message in error_patterns:
            if pattern.lower() in reason_lower:
                return f"【評価未完了】{message}\n（技術詳細: {reason[:100]}）"

        # マッチしない場合は汎用メッセージ
        return f"【評価未完了】処理中にエラーが発生しました。\n（詳細: {reason[:150]}）"
