# -*- coding: utf-8 -*-
"""
================================================================================
test_graph_orchestrator.py - graph_orchestrator.pyのユニットテスト
================================================================================

【テスト対象】
- AuditGraphState: LangGraph状態定義
- ExecutionPlan: 実行計画データクラス
- AuditResult: 監査結果データクラス
- GraphAuditOrchestrator: LangGraphベースのオーケストレーター

================================================================================
"""

import pytest
import os
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from dataclasses import fields

from core.graph_orchestrator import (
    AuditGraphState,
    ExecutionPlan,
    AuditResult,
    GraphAuditOrchestrator,
)
from core.tasks.base_task import TaskType, TaskResult, AuditContext, EvidenceFile


# =============================================================================
# ExecutionPlan テスト
# =============================================================================

class TestExecutionPlan:
    """ExecutionPlanデータクラスのテスト"""

    def test_basic_creation(self):
        """基本的なインスタンス作成"""
        plan = ExecutionPlan(
            analysis={"control_type": "承認統制"},
            steps=[{"step": 1, "task_type": "A5"}],
            dependencies={},
            reasoning="テスト計画",
        )
        assert plan.analysis == {"control_type": "承認統制"}
        assert len(plan.steps) == 1
        assert plan.reasoning == "テスト計画"
        assert plan.potential_issues == []

    def test_potential_issues_default(self):
        """potential_issuesのデフォルト値"""
        plan = ExecutionPlan(
            analysis={}, steps=[], dependencies={}, reasoning=""
        )
        assert plan.potential_issues == []

    def test_potential_issues_custom(self):
        """potential_issuesのカスタム値"""
        plan = ExecutionPlan(
            analysis={}, steps=[], dependencies={}, reasoning="",
            potential_issues=["証跡不足", "OCR精度"]
        )
        assert len(plan.potential_issues) == 2
        assert "証跡不足" in plan.potential_issues


# =============================================================================
# AuditResult テスト
# =============================================================================

class TestAuditResult:
    """AuditResultデータクラスのテスト"""

    def _create_result(self, **kwargs):
        """テスト用AuditResult作成ヘルパー"""
        defaults = {
            "item_id": "CLC-01",
            "evaluation_result": True,
            "judgment_basis": "統制は有効である",
            "document_reference": "[test.pdf]",
            "file_name": "test.pdf",
        }
        defaults.update(kwargs)
        return AuditResult(**defaults)

    def test_basic_creation(self):
        """基本的なインスタンス作成"""
        result = self._create_result()
        assert result.item_id == "CLC-01"
        assert result.evaluation_result is True
        assert result.confidence == 0.0

    def test_defaults(self):
        """デフォルト値の確認"""
        result = self._create_result()
        assert result.evidence_files_info == []
        assert result.task_results == []
        assert result.execution_plan is None
        assert result.confidence == 0.0
        assert result.plan_review_summary == ""
        assert result.judgment_review_summary == ""

    def test_to_response_dict_basic(self):
        """to_response_dict: 基本レスポンス"""
        result = self._create_result()
        response = result.to_response_dict(include_debug=False)

        assert response["ID"] == "CLC-01"
        assert response["evaluationResult"] is True
        assert response["judgmentBasis"] == "統制は有効である"
        assert response["fileName"] == "test.pdf"
        assert "_debug" not in response

    def test_to_response_dict_with_debug(self):
        """to_response_dict: デバッグ情報付き"""
        result = self._create_result(confidence=0.85)
        response = result.to_response_dict(include_debug=True)

        assert "_debug" in response
        assert response["_debug"]["confidence"] == 0.85
        assert response["_debug"]["taskResults"] == []

    def test_to_response_dict_with_task_results(self):
        """to_response_dict: タスク結果付き"""
        tr = TaskResult(
            task_type=TaskType.A5_SEMANTIC_REASONING,
            task_name="意味的推論",
            success=True,
            result=None,
            reasoning="テスト",
            confidence=0.9,
            evidence_references=["test.pdf"]
        )
        result = self._create_result(task_results=[tr])
        response = result.to_response_dict(include_debug=True)

        assert len(response["_debug"]["taskResults"]) == 1
        assert response["_debug"]["taskResults"][0]["taskType"] == "A5"
        assert response["_debug"]["taskResults"][0]["success"] is True

    def test_to_response_dict_with_execution_plan(self):
        """to_response_dict: 実行計画付き"""
        plan = ExecutionPlan(
            analysis={"type": "test"},
            steps=[{"step": 1}],
            dependencies={},
            reasoning="計画理由",
            potential_issues=["issue1"]
        )
        result = self._create_result(execution_plan=plan)
        response = result.to_response_dict(include_debug=True)

        assert response["_debug"]["executionPlan"] is not None
        assert response["_debug"]["executionPlan"]["reasoning"] == "計画理由"

    def test_get_task_type_label(self):
        """タスクタイプラベルの取得"""
        result = self._create_result()
        assert result._get_task_type_label("A5") == "【A5:意味的推論】"
        assert result._get_task_type_label("A1") == "【A1:意味検索】"
        assert result._get_task_type_label("A8") == "【A8:職務分離検出】"
        assert result._get_task_type_label("") == ""
        assert result._get_task_type_label("X9") == "【X9】"

    def test_format_execution_plan_summary_no_plan(self):
        """計画サマリー: 計画なし"""
        result = self._create_result()
        summary = result._format_execution_plan_summary()
        assert "計画未作成" in summary

    def test_format_execution_plan_summary_with_steps(self):
        """計画サマリー: ステップあり"""
        plan = ExecutionPlan(
            analysis={},
            steps=[
                {"step": 1, "task_type": "A5", "purpose": "整合性確認", "test_description": "テスト手続きの確認"},
                {"step": 2, "task_type": "A2", "purpose": "画像確認"},
            ],
            dependencies={},
            reasoning=""
        )
        result = self._create_result(execution_plan=plan)
        summary = result._format_execution_plan_summary()
        assert "A5" in summary
        assert "A2" in summary
        assert "整合性確認" in summary

    def test_format_execution_plan_summary_with_check_items(self):
        """計画サマリー: 確認項目付き"""
        plan = ExecutionPlan(
            analysis={},
            steps=[{
                "step": 1,
                "task_type": "A3",
                "purpose": "データ確認",
                "test_description": "金額を確認",
                "check_items": ["日付", "金額", "承認者"]
            }],
            dependencies={},
            reasoning=""
        )
        result = self._create_result(execution_plan=plan)
        summary = result._format_execution_plan_summary()
        assert "日付" in summary
        assert "金額" in summary

    def test_format_execution_plan_summary_fallback_to_task_results(self):
        """計画サマリー: タスク結果からのフォールバック"""
        tr = TaskResult(
            task_type=TaskType.A5_SEMANTIC_REASONING,
            task_name="意味的推論テスト",
            success=True, result=None,
            reasoning="", confidence=0.8, evidence_references=[]
        )
        result = self._create_result(task_results=[tr])
        summary = result._format_execution_plan_summary()
        assert "A5" in summary
        assert "意味的推論テスト" in summary


# =============================================================================
# GraphAuditOrchestrator 設定テスト
# =============================================================================

class TestGraphOrchestratorConfig:
    """GraphAuditOrchestrator設定のテスト"""

    @patch("core.graph_orchestrator.StateGraph")
    def test_default_config(self, mock_state_graph):
        """デフォルト設定"""
        mock_state_graph.return_value = MagicMock()
        mock_state_graph.return_value.compile.return_value = MagicMock()

        with patch.dict(os.environ, {}, clear=True):
            orch = GraphAuditOrchestrator(llm=None, vision_llm=None)
            assert orch.MAX_PLAN_REVISIONS == 1
            assert orch.MAX_JUDGMENT_REVISIONS == 1
            assert orch.SKIP_PLAN_CREATION is False

    @patch("core.graph_orchestrator.StateGraph")
    def test_custom_config(self, mock_state_graph):
        """カスタム設定"""
        mock_state_graph.return_value = MagicMock()
        mock_state_graph.return_value.compile.return_value = MagicMock()

        env = {
            "MAX_PLAN_REVISIONS": "3",
            "MAX_JUDGMENT_REVISIONS": "2",
            "SKIP_PLAN_CREATION": "true",
        }
        with patch.dict(os.environ, env, clear=True):
            orch = GraphAuditOrchestrator(llm=None, vision_llm=None)
            assert orch.MAX_PLAN_REVISIONS == 3
            assert orch.MAX_JUDGMENT_REVISIONS == 2
            assert orch.SKIP_PLAN_CREATION is True

    @patch("core.graph_orchestrator.StateGraph")
    def test_invalid_revision_config(self, mock_state_graph):
        """不正な設定値はConfigErrorを発生させる"""
        mock_state_graph.return_value = MagicMock()
        mock_state_graph.return_value.compile.return_value = MagicMock()

        from infrastructure.config import ConfigError

        env = {"MAX_PLAN_REVISIONS": "invalid", "MAX_JUDGMENT_REVISIONS": "abc"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigError):
                GraphAuditOrchestrator(llm=None, vision_llm=None)

    @patch("core.graph_orchestrator.StateGraph")
    def test_zero_revisions(self, mock_state_graph):
        """レビュースキップ設定"""
        mock_state_graph.return_value = MagicMock()
        mock_state_graph.return_value.compile.return_value = MagicMock()

        env = {"MAX_PLAN_REVISIONS": "0", "MAX_JUDGMENT_REVISIONS": "0"}
        with patch.dict(os.environ, env, clear=True):
            orch = GraphAuditOrchestrator(llm=None, vision_llm=None)
            assert orch.MAX_PLAN_REVISIONS == 0
            assert orch.MAX_JUDGMENT_REVISIONS == 0

    @patch("core.graph_orchestrator.StateGraph")
    def test_tasks_initialized(self, mock_state_graph):
        """タスクハンドラーの初期化"""
        mock_state_graph.return_value = MagicMock()
        mock_state_graph.return_value.compile.return_value = MagicMock()

        orch = GraphAuditOrchestrator(llm=None, vision_llm=None)
        assert len(orch.tasks) == 8
        assert TaskType.A1_SEMANTIC_SEARCH in orch.tasks
        assert TaskType.A8_SOD_DETECTION in orch.tasks

    @patch("core.graph_orchestrator.StateGraph")
    def test_vision_llm_fallback(self, mock_state_graph):
        """vision_llm未指定時のフォールバック"""
        mock_state_graph.return_value = MagicMock()
        mock_state_graph.return_value.compile.return_value = MagicMock()

        mock_llm = MagicMock()
        orch = GraphAuditOrchestrator(llm=mock_llm, vision_llm=None)
        assert orch.vision_llm is mock_llm


# =============================================================================
# ユーティリティメソッドテスト
# =============================================================================

class TestOrchestratorUtilities:
    """GraphAuditOrchestratorユーティリティメソッドのテスト"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """各テストの前にオーケストレーターを初期化"""
        with patch("core.graph_orchestrator.StateGraph") as mock_sg:
            mock_sg.return_value = MagicMock()
            mock_sg.return_value.compile.return_value = MagicMock()
            self.orch = GraphAuditOrchestrator(llm=None, vision_llm=None)

    def test_parse_task_type_valid(self):
        """タスクタイプ解析: 有効な値"""
        assert self.orch._parse_task_type("A1") == TaskType.A1_SEMANTIC_SEARCH
        assert self.orch._parse_task_type("A5") == TaskType.A5_SEMANTIC_REASONING
        assert self.orch._parse_task_type("A8") == TaskType.A8_SOD_DETECTION

    def test_parse_task_type_case_insensitive(self):
        """タスクタイプ解析: 大文字小文字"""
        assert self.orch._parse_task_type("a5") == TaskType.A5_SEMANTIC_REASONING

    def test_parse_task_type_invalid(self):
        """タスクタイプ解析: 無効な値"""
        assert self.orch._parse_task_type("A9") is None
        assert self.orch._parse_task_type("") is None
        assert self.orch._parse_task_type("invalid") is None

    def test_create_default_plan_basic(self):
        """デフォルト計画: 基本（テキストのみ）"""
        context = {"evidence_files": [{"file_name": "test.txt", "extension": ".txt"}]}
        plan = self.orch._create_default_plan(context)

        assert isinstance(plan, ExecutionPlan)
        assert len(plan.steps) == 1
        assert plan.steps[0]["task_type"] == "A5"
        assert plan.reasoning == "デフォルト実行計画"

    def test_create_default_plan_with_images(self):
        """デフォルト計画: 画像ファイル含む"""
        context = {"evidence_files": [
            {"file_name": "doc.pdf", "extension": ".pdf"},
        ]}
        plan = self.orch._create_default_plan(context)

        task_types = [s["task_type"] for s in plan.steps]
        assert "A5" in task_types
        assert "A2" in task_types

    def test_create_default_plan_multiple_files(self):
        """デフォルト計画: 複数ファイル"""
        context = {"evidence_files": [
            {"file_name": "a.txt", "extension": ".txt"},
            {"file_name": "b.txt", "extension": ".txt"},
        ]}
        plan = self.orch._create_default_plan(context)

        task_types = [s["task_type"] for s in plan.steps]
        assert "A6" in task_types

    def test_summarize_evidence_empty(self):
        """証跡サマリー: 空"""
        assert self.orch._summarize_evidence([]) == "エビデンスファイルなし"

    def test_summarize_evidence_dicts(self):
        """証跡サマリー: 辞書形式"""
        files = [
            {"file_name": "a.pdf", "mime_type": "application/pdf"},
            {"file_name": "b.xlsx", "mime_type": "application/vnd.openxmlformats"},
        ]
        result = self.orch._summarize_evidence(files)
        assert "a.pdf" in result
        assert "b.xlsx" in result

    def test_format_task_results(self):
        """タスク結果フォーマット"""
        results = [{
            "task_type": "A5",
            "task_name": "意味的推論",
            "success": True,
            "reasoning": "確認完了",
            "confidence": 0.85,
            "evidence_references": ["test.pdf"]
        }]
        formatted = self.orch._format_task_results(results)
        assert "A5" in formatted
        assert "成功" in formatted
        assert "0.85" in formatted

    def test_format_document_quotes_empty(self):
        """引用フォーマット: 空"""
        assert self.orch._format_document_quotes([]) == "（引用なし）"

    def test_format_document_quotes_basic(self):
        """引用フォーマット: 基本"""
        quotes = [{
            "file_name": "test.pdf",
            "page_or_location": "P.3",
            "quotes": ["承認日: 2025年1月15日"]
        }]
        result = self.orch._format_document_quotes(quotes)
        assert "[test.pdf]" in result
        assert "P.3" in result
        assert "承認日" in result

    def test_format_document_quotes_single_quote_field(self):
        """引用フォーマット: quoteフィールド（単数形）"""
        quotes = [{"file_name": "a.pdf", "quote": "テスト引用文"}]
        result = self.orch._format_document_quotes(quotes)
        assert "テスト引用文" in result

    def test_simple_aggregate_empty(self):
        """単純集計: 空"""
        result = self.orch._simple_aggregate([])
        assert result["evaluation_result"] is False
        assert "タスク実行結果がありません" in result["judgment_basis"]

    def test_simple_aggregate_all_success(self):
        """単純集計: 全成功"""
        results = [
            {"success": True, "confidence": 0.9, "task_type": "A5", "reasoning": "OK"},
            {"success": True, "confidence": 0.8, "task_type": "A2", "reasoning": "確認済"},
        ]
        result = self.orch._simple_aggregate(results)
        assert result["evaluation_result"] is True
        assert abs(result["confidence"] - 0.85) < 1e-9

    def test_simple_aggregate_majority_fail(self):
        """単純集計: 過半数失敗"""
        results = [
            {"success": False, "confidence": 0.3, "task_type": "A5", "reasoning": "NG"},
            {"success": False, "confidence": 0.2, "task_type": "A2", "reasoning": "NG"},
            {"success": True, "confidence": 0.9, "task_type": "A3", "reasoning": "OK"},
        ]
        result = self.orch._simple_aggregate(results)
        assert result["evaluation_result"] is False


# =============================================================================
# 条件分岐関数テスト
# =============================================================================

class TestConditionalEdges:
    """条件分岐関数のテスト"""

    @pytest.fixture(autouse=True)
    def setup(self):
        with patch("core.graph_orchestrator.StateGraph") as mock_sg:
            mock_sg.return_value = MagicMock()
            mock_sg.return_value.compile.return_value = MagicMock()
            self.orch = GraphAuditOrchestrator(llm=None, vision_llm=None)

    def test_should_refine_plan_approved(self):
        """計画レビュー: 承認"""
        state = {"plan_review": {"review_result": "承認"}, "plan_revision_count": 0}
        assert self.orch._should_refine_plan(state) == "execute"

    def test_should_refine_plan_needs_revision(self):
        """計画レビュー: 要修正"""
        state = {"plan_review": {"review_result": "要修正"}, "plan_revision_count": 0}
        assert self.orch._should_refine_plan(state) == "refine"

    def test_should_refine_plan_max_reached(self):
        """計画レビュー: 最大回数到達"""
        state = {"plan_review": {"review_result": "要修正"}, "plan_revision_count": 1}
        assert self.orch._should_refine_plan(state) == "execute"

    def test_should_refine_judgment_approved(self):
        """判断レビュー: 承認"""
        state = {"judgment_review": {"review_result": "承認"}, "judgment_revision_count": 0}
        assert self.orch._should_refine_judgment(state) == "output"

    def test_should_refine_judgment_needs_revision(self):
        """判断レビュー: 要修正"""
        state = {"judgment_review": {"review_result": "要修正"}, "judgment_revision_count": 0}
        assert self.orch._should_refine_judgment(state) == "refine"

    def test_should_refine_judgment_max_reached(self):
        """判断レビュー: 最大回数到達"""
        state = {"judgment_review": {"review_result": "要修正"}, "judgment_revision_count": 1}
        assert self.orch._should_refine_judgment(state) == "output"


# =============================================================================
# 矛盾検出テスト
# =============================================================================

class TestContradictionDetection:
    """_detect_judgment_contradictions のテスト"""

    @pytest.fixture(autouse=True)
    def setup(self):
        with patch("core.graph_orchestrator.StateGraph") as mock_sg:
            mock_sg.return_value = MagicMock()
            mock_sg.return_value.compile.return_value = MagicMock()
            self.orch = GraphAuditOrchestrator(llm=None, vision_llm=None)

    def test_no_contradictions(self):
        """矛盾なし"""
        issues = self.orch._detect_judgment_contradictions(
            "統制は有効に機能している。よって本統制は有効である。",
            True
        )
        assert len(issues) == 0

    def test_empty_basis(self):
        """空の判断根拠"""
        issues = self.orch._detect_judgment_contradictions("", True)
        assert len(issues) == 0

    def test_forbidden_phrase_detected(self):
        """禁止フレーズ検出"""
        issues = self.orch._detect_judgment_contradictions(
            "追加証跡が必要であるため確認できない", True
        )
        assert any(i["type"] == "禁止フレーズ" for i in issues)

    def test_positive_negative_contradiction(self):
        """有効判定と否定表現の矛盾"""
        issues = self.orch._detect_judgment_contradictions(
            "統制に不備があるが、全体として有効である", True
        )
        assert any(i["type"] == "評価結果矛盾" for i in issues)

    def test_negative_positive_contradiction(self):
        """不備判定と肯定表現の矛盾"""
        issues = self.orch._detect_judgment_contradictions(
            "統制は有効に整備・運用されている", False
        )
        assert any(i["type"] == "評価結果矛盾" for i in issues)

    def test_multiple_issues(self):
        """複数の問題検出"""
        issues = self.orch._detect_judgment_contradictions(
            "追加証跡が必要で、不備がある部分もあるが有効と判断する", True
        )
        assert len(issues) >= 2


# =============================================================================
# 後処理テスト
# =============================================================================

class TestPostProcessing:
    """_postprocess_judgment_basis, _clean_judgment_basis_prefix のテスト"""

    @pytest.fixture(autouse=True)
    def setup(self):
        with patch("core.graph_orchestrator.StateGraph") as mock_sg:
            mock_sg.return_value = MagicMock()
            mock_sg.return_value.compile.return_value = MagicMock()
            self.orch = GraphAuditOrchestrator(llm=None, vision_llm=None)

    def test_clean_prefix_no_change(self):
        """プレフィックス除去: 変更なし"""
        text = "統制は有効である。"
        assert self.orch._clean_judgment_basis_prefix(text) == text

    def test_clean_prefix_removes_modification_prefix(self):
        """プレフィックス除去: 修正案プレフィックス"""
        text = "修正案：統制は有効である。"
        result = self.orch._clean_judgment_basis_prefix(text)
        assert "統制は有効である" in result
        assert "修正案" not in result

    def test_clean_prefix_empty(self):
        """プレフィックス除去: 空文字列"""
        assert self.orch._clean_judgment_basis_prefix("") == ""

    def test_postprocess_empty(self):
        """後処理: 空文字列"""
        assert self.orch._postprocess_judgment_basis("", True) == ""

    def test_postprocess_removes_meta_explanation(self):
        """後処理: メタ説明の除去"""
        text = "修正案として以下を提示する。統制は有効に機能している。"
        result = self.orch._postprocess_judgment_basis(text, True)
        assert "修正案" not in result

    def test_postprocess_replaces_uncertain_expressions(self):
        """後処理: 曖昧表現の置換"""
        text = "統制は有効と考えられる。"
        result = self.orch._postprocess_judgment_basis(text, True)
        assert "考えられる" not in result
        assert "である" in result

    def test_postprocess_replaces_limited_effectiveness(self):
        """後処理: 限定的有効の修正"""
        text = "限定的有効と判断する。"
        result = self.orch._postprocess_judgment_basis(text, True)
        assert "限定的有効" not in result

    def test_postprocess_cleans_invalid_characters(self):
        """後処理: 不正文字の除去"""
        # 韓国語文字を含むテスト
        text = "統制は有効\ud55cである"
        result = self.orch._postprocess_judgment_basis(text, True)
        assert "\ud55c" not in result


# =============================================================================
# 引用テキストクリーニングテスト
# =============================================================================

class TestCleanQuoteText:
    """_clean_quote_text のテスト"""

    @pytest.fixture(autouse=True)
    def setup(self):
        with patch("core.graph_orchestrator.StateGraph") as mock_sg:
            mock_sg.return_value = MagicMock()
            mock_sg.return_value.compile.return_value = MagicMock()
            self.orch = GraphAuditOrchestrator(llm=None, vision_llm=None)

    def test_clean_quote_no_change(self):
        """変更不要のテキスト"""
        text = "承認日: 2025年1月15日"
        assert self.orch._clean_quote_text(text) == text

    def test_clean_quote_empty(self):
        """空文字列"""
        assert self.orch._clean_quote_text("") == ""

    def test_clean_quote_removes_duplicates(self):
        """重複文の除去"""
        text = "承認日は1月15日。承認日は1月15日。追加情報あり。"
        result = self.orch._clean_quote_text(text)
        # 重複が除去されているか
        assert result.count("承認日は1月15日") == 1


# =============================================================================
# エラーメッセージ変換テスト
# =============================================================================

class TestErrorConversion:
    """_convert_to_user_friendly_error のテスト"""

    @pytest.fixture(autouse=True)
    def setup(self):
        with patch("core.graph_orchestrator.StateGraph") as mock_sg:
            mock_sg.return_value = MagicMock()
            mock_sg.return_value.compile.return_value = MagicMock()
            self.orch = GraphAuditOrchestrator(llm=None, vision_llm=None)

    def test_graph_error(self):
        """グラフ実行エラー"""
        result = self.orch._convert_to_user_friendly_error("グラフ実行エラー: xxx")
        assert "評価未完了" in result
        assert "再度実行" in result

    def test_timeout_error(self):
        """タイムアウトエラー"""
        result = self.orch._convert_to_user_friendly_error("Request timeout exceeded")
        assert "タイムアウト" in result

    def test_rate_limit_error(self):
        """レート制限エラー"""
        result = self.orch._convert_to_user_friendly_error("API rate limit reached")
        assert "API制限" in result

    def test_connection_error(self):
        """接続エラー"""
        result = self.orch._convert_to_user_friendly_error("Connection refused")
        assert "接続エラー" in result

    def test_unknown_error(self):
        """不明なエラー"""
        result = self.orch._convert_to_user_friendly_error("Some unknown error")
        assert "評価未完了" in result


# =============================================================================
# フォールバック結果テスト
# =============================================================================

class TestFallbackResult:
    """_create_fallback_result のテスト"""

    @pytest.fixture(autouse=True)
    def setup(self):
        with patch("core.graph_orchestrator.StateGraph") as mock_sg:
            mock_sg.return_value = MagicMock()
            mock_sg.return_value.compile.return_value = MagicMock()
            self.orch = GraphAuditOrchestrator(llm=None, vision_llm=None)

    def test_fallback_basic(self):
        """フォールバック結果の基本"""
        ef = EvidenceFile(
            file_name="test.pdf", mime_type="application/pdf",
            extension=".pdf", base64_content=""
        )
        context = AuditContext(
            item_id="CLC-01",
            control_description="テスト",
            test_procedure="テスト手続き",
            evidence_link="//server/path/",
            evidence_files=[ef]
        )
        result = self.orch._create_fallback_result(context, "グラフ実行エラー: test")

        assert isinstance(result, AuditResult)
        assert result.item_id == "CLC-01"
        assert result.evaluation_result is False
        assert result.confidence == 0.0
        assert result.file_name == "test.pdf"
        assert "評価未完了" in result.judgment_basis

    def test_fallback_no_evidence(self):
        """フォールバック結果: 証跡なし"""
        context = AuditContext(
            item_id="CLC-02",
            control_description="テスト",
            test_procedure="テスト手続き",
            evidence_link="",
            evidence_files=[]
        )
        result = self.orch._create_fallback_result(context, "error")
        assert result.file_name == ""


# =============================================================================
# ノード実装テスト（非同期）
# =============================================================================

class TestNodes:
    """LangGraphノードのテスト"""

    @pytest.fixture(autouse=True)
    def setup(self):
        with patch("core.graph_orchestrator.StateGraph") as mock_sg:
            mock_sg.return_value = MagicMock()
            mock_sg.return_value.compile.return_value = MagicMock()
            self.orch = GraphAuditOrchestrator(llm=None, vision_llm=None)

    @pytest.mark.asyncio
    async def test_node_create_plan_no_llm(self):
        """計画作成ノード: LLMなし"""
        state = {"context": {
            "control_description": "テスト",
            "test_procedure": "手続き",
            "evidence_files": []
        }}
        result = await self.orch._node_create_plan(state)

        assert "execution_plan" in result
        assert result["plan_revision_count"] == 0

    @pytest.mark.asyncio
    async def test_node_review_plan_no_llm(self):
        """計画レビューノード: LLMなし"""
        state = {
            "context": {"evidence_files": []},
            "execution_plan": {"execution_plan": []}
        }
        result = await self.orch._node_review_plan(state)

        assert result["plan_review"]["review_result"] == "承認"

    @pytest.mark.asyncio
    async def test_node_refine_plan_no_llm(self):
        """計画修正ノード: LLMなし"""
        state = {
            "context": {},
            "execution_plan": {"execution_plan": []},
            "plan_review": {},
            "plan_revision_count": 0
        }
        result = await self.orch._node_refine_plan(state)

        assert result["plan_revision_count"] == 1

    @pytest.mark.asyncio
    async def test_node_aggregate_results_no_llm(self):
        """結果統合ノード: LLMなし"""
        state = {
            "context": {},
            "execution_plan": {},
            "task_results": [
                {"success": True, "confidence": 0.9, "task_type": "A5", "reasoning": "OK"}
            ]
        }
        result = await self.orch._node_aggregate_results(state)

        assert "judgment" in result
        assert result["judgment"]["evaluation_result"] is True

    @pytest.mark.asyncio
    async def test_node_review_judgment_no_llm(self):
        """判断レビューノード: LLMなし"""
        state = {
            "context": {},
            "execution_plan": {},
            "task_results": [],
            "judgment": {"judgment_basis": "統制は有効である", "evaluation_result": True}
        }
        result = await self.orch._node_review_judgment(state)

        assert result["judgment_review"]["review_result"] == "承認"

    @pytest.mark.asyncio
    async def test_node_review_judgment_detects_contradiction(self):
        """判断レビューノード: 矛盾検出"""
        state = {
            "context": {},
            "execution_plan": {},
            "task_results": [],
            "judgment": {
                "judgment_basis": "統制に不備がある。よって有効と判断する。",
                "evaluation_result": True
            }
        }
        result = await self.orch._node_review_judgment(state)

        assert result["judgment_review"]["review_result"] == "要修正"
        assert len(result["judgment_review"]["issues"]) > 0

    @pytest.mark.asyncio
    async def test_node_output(self):
        """最終出力ノード"""
        state = {
            "context": {"item_id": "CLC-01"},
            "judgment": {
                "evaluation_result": True,
                "judgment_basis": "統制は有効である",
                "document_quotes": [],
                "confidence": 0.85,
            },
            "plan_review": {"review_result": "承認", "coverage_score": 8, "efficiency_score": 7},
            "judgment_review": {"review_result": "承認"},
        }
        result = await self.orch._node_output(state)

        assert "final_result" in result
        assert result["final_result"]["item_id"] == "CLC-01"
        assert result["final_result"]["evaluation_result"] is True
        assert result["final_result"]["confidence"] == 0.85
        assert "8/10" in result["final_result"]["plan_review_summary"]

    @pytest.mark.asyncio
    async def test_node_output_na_scores(self):
        """最終出力ノード: N/Aスコア処理"""
        state = {
            "context": {"item_id": "CLC-02"},
            "judgment": {"evaluation_result": False, "judgment_basis": "不備あり"},
            "plan_review": {"review_result": "承認", "coverage_score": "N/A", "efficiency_score": None},
            "judgment_review": {"review_result": "N/A"},
        }
        result = await self.orch._node_output(state)

        # N/Aの場合はデフォルト値で補完される
        assert "plan_review_summary" in result["final_result"]
        assert result["final_result"]["judgment_review_summary"] == "レビュー結果: 承認"


# =============================================================================
# タスク実行ノードテスト
# =============================================================================

class TestExecuteTasksNode:
    """execute_tasksノードのテスト"""

    @pytest.fixture(autouse=True)
    def setup(self):
        with patch("core.graph_orchestrator.StateGraph") as mock_sg:
            mock_sg.return_value = MagicMock()
            mock_sg.return_value.compile.return_value = MagicMock()
            self.orch = GraphAuditOrchestrator(llm=None, vision_llm=None)

    @pytest.mark.asyncio
    async def test_execute_tasks_empty_plan(self):
        """タスク実行: 空の計画"""
        state = {
            "context": {
                "item_id": "CLC-01",
                "control_description": "テスト",
                "test_procedure": "手続き",
                "evidence_link": "",
                "evidence_files": []
            },
            "execution_plan": {"execution_plan": []}
        }
        result = await self.orch._node_execute_tasks(state)
        assert result["task_results"] == []

    @pytest.mark.asyncio
    async def test_execute_tasks_with_mock_task(self):
        """タスク実行: モックタスク"""
        mock_task = AsyncMock()
        mock_task.task_name = "テストタスク"
        mock_task.execute.return_value = TaskResult(
            task_type=TaskType.A5_SEMANTIC_REASONING,
            task_name="テストタスク",
            success=True,
            result={"test": True},
            reasoning="テスト実行完了",
            confidence=0.9,
            evidence_references=["test.pdf"]
        )
        self.orch.tasks[TaskType.A5_SEMANTIC_REASONING] = mock_task

        state = {
            "context": {
                "item_id": "CLC-01",
                "control_description": "テスト",
                "test_procedure": "手続き",
                "evidence_link": "",
                "evidence_files": []
            },
            "execution_plan": {
                "execution_plan": [{"step": 1, "task_type": "A5"}]
            }
        }
        result = await self.orch._node_execute_tasks(state)

        assert len(result["task_results"]) == 1
        assert result["task_results"][0]["success"] is True
        assert result["task_results"][0]["task_type"] == "A5"

    @pytest.mark.asyncio
    async def test_execute_tasks_invalid_step_skipped(self):
        """タスク実行: 不正なstep形式はスキップ"""
        state = {
            "context": {
                "item_id": "CLC-01",
                "control_description": "テスト",
                "test_procedure": "手続き",
                "evidence_link": "",
                "evidence_files": []
            },
            "execution_plan": {
                "execution_plan": ["invalid_step", 123, None]
            }
        }
        result = await self.orch._node_execute_tasks(state)
        assert result["task_results"] == []


# =============================================================================
# 証憑バリデーション（Layer 0）テスト
# =============================================================================

class TestEvidenceValidation:
    """_validate_evidence_files メソッドのテスト"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """各テストの前にオーケストレーターを初期化"""
        with patch("core.graph_orchestrator.StateGraph") as mock_sg:
            mock_sg.return_value = MagicMock()
            mock_sg.return_value.compile.return_value = MagicMock()
            self.orch = GraphAuditOrchestrator(llm=None, vision_llm=None)

    def _make_evidence_file(self, name, size_mb=1.0):
        """テスト用EvidenceFileを作成（指定MBのBase64コンテンツ付き）"""
        # Base64は4文字→3バイトなので、n MBに必要な文字数を計算
        byte_count = int(size_mb * 1024 * 1024)
        b64_char_count = (byte_count * 4) // 3
        return EvidenceFile(
            file_name=name,
            extension=".pdf",
            mime_type="application/pdf",
            base64_content="A" * b64_char_count,
        )

    def test_all_files_accepted(self):
        """全ファイルが制限内"""
        files = [self._make_evidence_file("a.pdf", 1.0)]
        accepted, result = self.orch._validate_evidence_files(files)
        assert len(accepted) == 1
        assert result["skipped_count"] == 0

    def test_oversized_file_skipped(self):
        """個別ファイルサイズ超過"""
        files = [
            self._make_evidence_file("small.pdf", 1.0),
            self._make_evidence_file("big.pdf", 15.0),  # 10MB上限超過
        ]
        accepted, result = self.orch._validate_evidence_files(files)
        assert len(accepted) == 1
        assert accepted[0].file_name == "small.pdf"
        assert result["skipped_count"] == 1
        assert result["skipped_files"][0]["file_name"] == "big.pdf"

    def test_file_count_limit(self):
        """ファイル件数超過"""
        # 21件作成（上限20件）
        files = [self._make_evidence_file(f"file_{i}.pdf", 0.1) for i in range(21)]
        accepted, result = self.orch._validate_evidence_files(files)
        assert len(accepted) == 20
        assert result["skipped_count"] == 1

    def test_empty_files(self):
        """空のファイルリスト"""
        accepted, result = self.orch._validate_evidence_files([])
        assert len(accepted) == 0
        assert result["skipped_count"] == 0

    def test_validation_result_structure(self):
        """バリデーション結果の構造"""
        files = [self._make_evidence_file("a.pdf", 1.0)]
        _, result = self.orch._validate_evidence_files(files)
        assert "original_count" in result
        assert "accepted_count" in result
        assert "skipped_count" in result
        assert "skipped_files" in result
        assert "total_size_mb" in result
        assert "warnings" in result

    def test_exact_boundary_file_accepted(self):
        """個別ファイルサイズがちょうど上限の場合は受理"""
        files = [self._make_evidence_file("exact.pdf", 10.0)]  # 10MB = 上限
        accepted, result = self.orch._validate_evidence_files(files)
        assert len(accepted) == 1
        assert result["skipped_count"] == 0

    def test_total_size_limit(self):
        """合計サイズ超過で後半ファイルが除外される"""
        # 各9MB × 6 = 54MB > 50MB上限
        files = [self._make_evidence_file(f"f{i}.pdf", 9.0) for i in range(6)]
        accepted, result = self.orch._validate_evidence_files(files)
        # 9MB × 5 = 45MB < 50MB OK、6番目で54MB > 50MBとなり除外
        assert len(accepted) == 5
        assert result["skipped_count"] == 1
        assert "合計サイズ超過" in result["skipped_files"][0]["reason"]

    def test_mixed_validation_failures(self):
        """サイズ超過 + 件数超過が混在するケース"""
        files = [
            self._make_evidence_file("big.pdf", 15.0),  # サイズ超過
        ] + [
            self._make_evidence_file(f"f{i}.pdf", 0.1) for i in range(21)  # 件数超過
        ]
        accepted, result = self.orch._validate_evidence_files(files)
        # big.pdf=スキップ, f0-f19=受理(20件), f20=件数超過
        assert len(accepted) == 20
        assert result["skipped_count"] == 2

    def test_empty_base64_content(self):
        """base64_contentが空文字のファイルは受理される（サイズ0）"""
        ef = EvidenceFile(
            file_name="empty.txt",
            extension=".txt",
            mime_type="text/plain",
            base64_content="",
        )
        accepted, result = self.orch._validate_evidence_files([ef])
        assert len(accepted) == 1


# =============================================================================
# Evidence Screeningテスト
# =============================================================================

class TestEvidenceScreening:
    """_node_screen_evidence および関連メソッドのテスト"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """各テストの前にオーケストレーターを初期化"""
        with patch("core.graph_orchestrator.StateGraph") as mock_sg:
            mock_sg.return_value = MagicMock()
            mock_sg.return_value.compile.return_value = MagicMock()
            self.orch = GraphAuditOrchestrator(llm=None, vision_llm=None)

    def test_extract_screening_keywords(self):
        """キーワード抽出"""
        keywords = self.orch._extract_screening_keywords(
            "月次の取締役会議事録を作成",
            "議事録を閲覧し、承認印を確認する"
        )
        # 句読点・スペース・記号で分割されるため、助詞「の」「を」では分割されない
        # 分割結果: ["月次の取締役会議事録を作成", "議事録を閲覧し", "承認印を確認する"]
        assert len(keywords) >= 1
        # ストップワード「する」は単独トークンでないと除去されない
        # キーワードが空でないことを確認
        assert all(len(kw) >= 2 for kw in keywords)

    def test_calculate_relevance_score_matching(self):
        """関連性スコア: ファイル名にキーワードが含まれる"""
        score = self.orch._calculate_relevance_score(
            file_name="取締役会議事録_2025Q4.pdf",
            text_preview="取締役会議事録 2025年第4四半期",
            keywords=["取締役会議事録", "承認印", "2025"],
            test_procedure="取締役会議事録を閲覧し、承認印を確認する",
        )
        assert score > 0.3  # 高い関連性

    def test_calculate_relevance_score_unrelated(self):
        """関連性スコア: 無関係なファイル"""
        score = self.orch._calculate_relevance_score(
            file_name="会社案内パンフレット.pdf",
            text_preview="",
            keywords=["取締役会議事録", "承認印"],
            test_procedure="取締役会議事録を閲覧する",
        )
        assert score < 0.2  # 低い関連性

    def test_calculate_relevance_score_approval_bonus(self):
        """関連性スコア: 承認系テストで画像にボーナス"""
        score = self.orch._calculate_relevance_score(
            file_name="document.pdf",
            text_preview="",
            keywords=[],
            test_procedure="承認印を確認する",
        )
        # 承認系テスト + PDF形式のボーナスが付与される
        assert score >= 0.15

    @pytest.mark.asyncio
    async def test_screen_evidence_few_files_pass_all(self):
        """スクリーニング: 3件以下は全通過"""
        state = {
            "context": {
                "control_description": "テスト",
                "test_procedure": "手続き",
                "evidence_files": [
                    {"file_name": "a.pdf", "extension": ".pdf",
                     "mime_type": "application/pdf", "base64_content": ""},
                ],
            }
        }
        with patch.object(self.orch, "_extract_text_preview", return_value=""):
            result = await self.orch._node_screen_evidence(state)
        assert result["screening_summary"]["screened"] == 1
        assert result["screening_summary"]["excluded"] == 0

    @pytest.mark.asyncio
    async def test_screen_evidence_empty(self):
        """スクリーニング: 証憑なし"""
        state = {
            "context": {
                "control_description": "テスト",
                "test_procedure": "手続き",
                "evidence_files": [],
            }
        }
        result = await self.orch._node_screen_evidence(state)
        assert result["screening_summary"]["screened"] == 0

    @pytest.mark.asyncio
    async def test_screen_evidence_excludes_unrelated(self):
        """スクリーニング: 無関係ファイルが除外される"""
        state = {
            "context": {
                "control_description": "月次の取締役会議事録を作成",
                "test_procedure": "議事録を閲覧し、承認印を確認する",
                "evidence_files": [
                    {"file_name": "取締役会議事録_2025Q4.pdf", "extension": ".pdf",
                     "mime_type": "application/pdf", "base64_content": ""},
                    {"file_name": "社内旅行写真.jpg", "extension": ".jpg",
                     "mime_type": "image/jpeg", "base64_content": ""},
                    {"file_name": "会社案内パンフレット.pdf", "extension": ".pdf",
                     "mime_type": "application/pdf", "base64_content": ""},
                    {"file_name": "月次レポート承認済.pdf", "extension": ".pdf",
                     "mime_type": "application/pdf", "base64_content": ""},
                ],
            }
        }
        with patch.object(self.orch, "_extract_text_preview", return_value=""):
            result = await self.orch._node_screen_evidence(state)

        summary = result["screening_summary"]
        # 議事録とレポートは通過、写真とパンフレットは除外（スコア依存）
        assert summary["screened"] + summary["excluded"] == 4
        assert summary["excluded"] >= 1  # 少なくとも1件は除外

    def test_calculate_relevance_score_capped_at_one(self):
        """関連性スコアが1.0を超えない"""
        # ファイル名 + テキスト + 承認ボーナスを全て最大にする
        score = self.orch._calculate_relevance_score(
            file_name="取締役会議事録_承認_月次_レビュー_売上.pdf",
            text_preview="取締役会議事録 承認 月次 レビュー 売上 " * 20,
            keywords=["取締役会議事録", "承認", "月次", "レビュー", "売上"],
            test_procedure="承認印を確認する",
        )
        assert score <= 1.0

    def test_calculate_relevance_score_empty_keywords(self):
        """キーワードが空のケース"""
        score = self.orch._calculate_relevance_score(
            file_name="report.pdf",
            text_preview="何かのテキスト内容",
            keywords=[],
            test_procedure="手続き",
        )
        # キーワードマッチ0 + テキストあり0.1 = 0.1
        assert score >= 0.0
        assert score <= 1.0

    def test_extract_screening_keywords_empty_input(self):
        """空文字列からのキーワード抽出"""
        keywords = self.orch._extract_screening_keywords("", "")
        assert isinstance(keywords, list)
        assert len(keywords) == 0

    def test_extract_screening_keywords_deduplication(self):
        """同一キーワードが重複しない"""
        keywords = self.orch._extract_screening_keywords(
            "売上報告書の売上確認", "売上報告書を閲覧"
        )
        # "売上報告書" は1回のみ
        assert keywords.count("売上報告書") <= 1


# =============================================================================
# _summarize_evidence 強化テスト
# =============================================================================

class TestSummarizeEvidence:
    """_summarize_evidence の強化テスト"""

    @pytest.fixture(autouse=True)
    def setup(self):
        with patch("core.graph_orchestrator.StateGraph") as mock_sg:
            mock_sg.return_value = MagicMock()
            mock_sg.return_value.compile.return_value = MagicMock()
            self.orch = GraphAuditOrchestrator(llm=None, vision_llm=None)

    def test_empty_evidence(self):
        """証拠なしでメッセージを返す"""
        result = self.orch._summarize_evidence([])
        assert "なし" in result

    def test_dict_with_preview(self):
        """dict形式でtext_previewとrelevance_scoreを含む"""
        files = [
            {
                "file_name": "report.pdf",
                "mime_type": "application/pdf",
                "text_preview": "月次売上報告書の承認済みコピー",
                "relevance_score": 0.85,
            }
        ]
        result = self.orch._summarize_evidence(files)
        assert "report.pdf" in result
        assert "関連性: 0.85" in result
        assert "月次売上報告書" in result

    def test_dict_without_preview(self):
        """dict形式でtext_previewがない場合"""
        files = [
            {"file_name": "data.csv", "mime_type": "text/csv"}
        ]
        result = self.orch._summarize_evidence(files)
        assert "data.csv" in result
        assert "内容概要" not in result

    def test_evidence_file_object(self):
        """EvidenceFileオブジェクト形式"""
        ef = EvidenceFile(
            file_name="doc.pdf",
            extension=".pdf",
            mime_type="application/pdf",
            base64_content="dGVzdA==",
        )
        result = self.orch._summarize_evidence([ef])
        assert "doc.pdf" in result

    def test_preview_truncated_to_200_chars(self):
        """テキストプレビューが200文字に制限される"""
        long_text = "あ" * 300
        files = [
            {
                "file_name": "long.pdf",
                "mime_type": "application/pdf",
                "text_preview": long_text,
            }
        ]
        result = self.orch._summarize_evidence(files)
        # "内容概要: " + 200文字以内
        assert "あ" * 201 not in result


# =============================================================================
# テスト範囲の透明性テスト
# =============================================================================

class TestTestCoverage:
    """_build_test_coverage メソッドのテスト"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """各テストの前にオーケストレーターを初期化"""
        with patch("core.graph_orchestrator.StateGraph") as mock_sg:
            mock_sg.return_value = MagicMock()
            mock_sg.return_value.compile.return_value = MagicMock()
            self.orch = GraphAuditOrchestrator(llm=None, vision_llm=None)

    def test_coverage_no_issues(self):
        """テスト範囲: 問題なし"""
        state = {
            "evidence_validation": {
                "original_count": 3,
                "accepted_count": 3,
                "skipped_files": [],
            },
            "screening_summary": {
                "screened": 3,
                "excluded": 0,
                "excluded_files": [],
            },
            "context": {
                "evidence_files": [
                    {"file_name": "a.pdf"},
                    {"file_name": "b.pdf"},
                    {"file_name": "c.pdf"},
                ],
            },
            "task_results": [],
        }
        coverage = self.orch._build_test_coverage(state)
        assert coverage["files_received"] == 3
        assert coverage["files_processed"] == 3
        assert coverage["coverage_warning"] is None

    def test_coverage_with_exclusions(self):
        """テスト範囲: 除外あり"""
        state = {
            "evidence_validation": {
                "original_count": 5,
                "accepted_count": 4,
                "skipped_files": [{"file_name": "big.pdf", "reason": "サイズ超過"}],
            },
            "screening_summary": {
                "screened": 2,
                "excluded": 2,
                "excluded_files": [
                    {"file_name": "unrelated.pdf", "reason": "関連性低"}
                ],
            },
            "context": {
                "evidence_files": [
                    {"file_name": "a.pdf"},
                    {"file_name": "b.pdf"},
                ],
            },
            "task_results": [],
        }
        coverage = self.orch._build_test_coverage(state)
        assert coverage["files_received"] == 5
        assert coverage["files_after_validation"] == 4
        assert coverage["files_after_screening"] == 2
        assert coverage["files_processed"] == 2
        assert coverage["coverage_warning"] is not None
        assert "サイズ" in coverage["coverage_warning"]
        assert "スクリーニング" in coverage["coverage_warning"]

    def test_coverage_empty_state(self):
        """テスト範囲: 空のstate"""
        state = {
            "evidence_validation": None,
            "screening_summary": None,
            "context": {"evidence_files": []},
            "task_results": [],
        }
        coverage = self.orch._build_test_coverage(state)
        assert coverage["files_received"] == 0
        assert coverage["files_processed"] == 0


# =============================================================================
# フィードバック再評価テスト
# =============================================================================

class TestFeedbackReeval:
    """フィードバック再評価関連のテスト"""

    def setup_method(self):
        """テスト用オーケストレーター作成"""
        self.orch = GraphAuditOrchestrator(llm=None, vision_llm=None)

    # --- _build_feedback_section テスト ---

    def test_build_feedback_section_no_feedback(self):
        """フィードバックなしで空文字を返す"""
        result = self.orch._build_feedback_section(None, None)
        assert result == ""

    def test_build_feedback_section_empty_string(self):
        """空文字列フィードバックで空文字を返す"""
        result = self.orch._build_feedback_section("", None)
        assert result == ""

    def test_build_feedback_section_with_feedback_only(self):
        """フィードバックのみ（前回結果なし）"""
        result = self.orch._build_feedback_section(
            "署名を確認してください", None
        )
        assert "署名を確認してください" in result
        assert "ユーザーからのフィードバック" in result
        assert "前回の評価結果" not in result

    def test_build_feedback_section_with_previous_result(self):
        """フィードバック＋前回結果あり"""
        prev = {
            "evaluationResult": True,
            "judgmentBasis": "統制は有効である",
            "executionPlanSummary": "【A5:意味的推論】",
        }
        result = self.orch._build_feedback_section(
            "根拠を修正してください", prev
        )
        assert "根拠を修正してください" in result
        assert "前回の評価結果" in result
        assert "有効" in result
        assert "統制は有効である" in result

    def test_build_feedback_section_truncates_long_basis(self):
        """長い判断根拠は500文字で切り詰められる"""
        prev = {
            "evaluationResult": False,
            "judgmentBasis": "A" * 800,
            "executionPlanSummary": "",
        }
        result = self.orch._build_feedback_section("test", prev)
        assert "..." in result
        # 500文字 + "..." が含まれているはず
        assert "A" * 500 in result

    # --- AuditResult フィードバックフィールド テスト ---

    def test_audit_result_feedback_defaults(self):
        """AuditResult: フィードバックフィールドのデフォルト値"""
        result = AuditResult(
            item_id="CLC-01",
            evaluation_result=True,
            judgment_basis="test",
            document_reference="",
            file_name="test.pdf",
        )
        assert result.feedback_applied is False
        assert result.reevaluation_round == 0
        assert result.result_changed is False

    def test_audit_result_feedback_fields_in_response(self):
        """AuditResult: to_response_dictにフィードバック情報が含まれる"""
        result = AuditResult(
            item_id="CLC-01",
            evaluation_result=False,
            judgment_basis="再評価結果",
            document_reference="",
            file_name="test.pdf",
            feedback_applied=True,
            reevaluation_round=2,
            result_changed=True,
        )
        response = result.to_response_dict(include_debug=False)
        assert response["feedbackApplied"] is True
        assert response["reevaluationRound"] == 2
        assert response["resultChanged"] is True

    def test_audit_result_no_feedback_in_response(self):
        """AuditResult: 初回評価時のレスポンス"""
        result = AuditResult(
            item_id="CLC-01",
            evaluation_result=True,
            judgment_basis="test",
            document_reference="",
            file_name="test.pdf",
        )
        response = result.to_response_dict(include_debug=False)
        assert response["feedbackApplied"] is False
        assert response["reevaluationRound"] == 0
        assert response["resultChanged"] is False

    # --- AuditGraphState フィードバックフィールド テスト ---

    def test_state_has_feedback_fields(self):
        """AuditGraphStateにフィードバックフィールドが存在する"""
        assert "user_feedback" in AuditGraphState.__annotations__
        assert "previous_result" in AuditGraphState.__annotations__
        assert "reevaluation_mode" in AuditGraphState.__annotations__


# =============================================================================
# evaluate() フィードバックルーティングテスト
# =============================================================================

class TestEvaluateFeedbackRouting:
    """evaluate() メソッドのフィードバックルーティングテスト"""

    @pytest.fixture(autouse=True)
    def setup(self):
        with patch("core.graph_orchestrator.StateGraph") as mock_sg:
            mock_sg.return_value = MagicMock()
            mock_sg.return_value.compile.return_value = AsyncMock()
            self.orch = GraphAuditOrchestrator(llm=None, vision_llm=None)

    def _make_context(self):
        """テスト用AuditContextを作成"""
        return AuditContext(
            item_id="CLC-01",
            control_description="テスト統制",
            test_procedure="テスト手続き",
            evidence_link="",
            evidence_files=[]
        )

    @pytest.mark.asyncio
    async def test_evaluate_no_feedback_calls_graph(self):
        """フィードバックなしで通常のグラフ実行を呼ぶ"""
        mock_final_state = {
            "final_result": {
                "item_id": "CLC-01",
                "evaluation_result": True,
                "judgment_basis": "有効",
                "document_quotes": [],
                "confidence": 0.8,
                "key_findings": [],
                "control_effectiveness": {},
                "plan_review_summary": "",
                "judgment_review_summary": "",
                "test_coverage": {},
            },
            "task_results": [],
            "execution_plan": {"analysis": {}, "execution_plan": [], "task_dependencies": {}, "reasoning": ""},
        }
        self.orch.graph.ainvoke = AsyncMock(return_value=mock_final_state)

        with patch.object(self.orch.highlighting_service, "highlight_evidence", new_callable=AsyncMock, return_value=[]):
            result = await self.orch.evaluate(self._make_context())

        assert isinstance(result, AuditResult)
        assert result.feedback_applied is False
        assert result.reevaluation_round == 0
        self.orch.graph.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_with_feedback_full_calls_graph(self):
        """fullモードフィードバックでグラフ実行を呼ぶ"""
        mock_final_state = {
            "final_result": {
                "item_id": "CLC-01",
                "evaluation_result": False,
                "judgment_basis": "再評価結果",
                "document_quotes": [],
                "confidence": 0.7,
                "key_findings": [],
                "control_effectiveness": {},
                "plan_review_summary": "",
                "judgment_review_summary": "",
                "test_coverage": {},
            },
            "task_results": [],
            "execution_plan": {"analysis": {}, "execution_plan": [], "task_dependencies": {}, "reasoning": ""},
        }
        self.orch.graph.ainvoke = AsyncMock(return_value=mock_final_state)

        prev = {"evaluationResult": True, "reevaluationRound": 0}

        with patch.object(self.orch.highlighting_service, "highlight_evidence", new_callable=AsyncMock, return_value=[]):
            result = await self.orch.evaluate(
                self._make_context(),
                user_feedback="根拠を見直してください",
                reevaluation_mode="full",
                previous_result=prev,
            )

        assert result.feedback_applied is True
        assert result.reevaluation_round == 1
        assert result.result_changed is True
        # fullモードではグラフを呼ぶ
        self.orch.graph.ainvoke.assert_called_once()
        # initial_stateにフィードバックが注入されている
        call_args = self.orch.graph.ainvoke.call_args[0][0]
        assert call_args["user_feedback"] != ""
        assert call_args["reevaluation_mode"] == "full"

    @pytest.mark.asyncio
    async def test_evaluate_judgment_only_skips_graph(self):
        """judgment_onlyモードではグラフを呼ばず_evaluate_judgment_onlyへ"""
        prev = {
            "evaluationResult": True,
            "judgmentBasis": "前回根拠",
            "executionPlanSummary": "前回計画",
            "taskResults": [],
            "reevaluationRound": 0,
        }

        with patch.object(
            self.orch, "_evaluate_judgment_only", new_callable=AsyncMock
        ) as mock_jo:
            mock_jo.return_value = AuditResult(
                item_id="CLC-01",
                evaluation_result=False,
                judgment_basis="再評価済み",
                document_reference="",
                file_name="",
                feedback_applied=True,
                reevaluation_round=1,
                result_changed=True,
            )

            result = await self.orch.evaluate(
                self._make_context(),
                user_feedback="テスト",
                reevaluation_mode="judgment_only",
                previous_result=prev,
            )

        mock_jo.assert_called_once()
        assert result.feedback_applied is True
        # グラフは呼ばれない
        self.orch.graph.ainvoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_evaluate_graph_error_returns_fallback(self):
        """グラフ実行エラー時にフォールバック結果を返す"""
        self.orch.graph.ainvoke = AsyncMock(side_effect=Exception("テストエラー"))

        result = await self.orch.evaluate(self._make_context())

        assert isinstance(result, AuditResult)
        assert result.evaluation_result is False
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_evaluate_reevaluation_round_increments(self):
        """再評価ラウンドが前回+1になる"""
        mock_final_state = {
            "final_result": {
                "item_id": "CLC-01",
                "evaluation_result": True,
                "judgment_basis": "再評価済み",
                "document_quotes": [],
                "confidence": 0.9,
                "key_findings": [],
                "control_effectiveness": {},
                "plan_review_summary": "",
                "judgment_review_summary": "",
                "test_coverage": {},
            },
            "task_results": [],
            "execution_plan": {"analysis": {}, "execution_plan": [], "task_dependencies": {}, "reasoning": ""},
        }
        self.orch.graph.ainvoke = AsyncMock(return_value=mock_final_state)

        prev = {"evaluationResult": True, "reevaluationRound": 3}

        with patch.object(self.orch.highlighting_service, "highlight_evidence", new_callable=AsyncMock, return_value=[]):
            result = await self.orch.evaluate(
                self._make_context(),
                user_feedback="確認お願いします",
                reevaluation_mode="full",
                previous_result=prev,
            )

        assert result.reevaluation_round == 4

    @pytest.mark.asyncio
    async def test_evaluate_result_changed_false_when_same(self):
        """前回と同じ結果のときresult_changed=False"""
        mock_final_state = {
            "final_result": {
                "item_id": "CLC-01",
                "evaluation_result": True,
                "judgment_basis": "有効",
                "document_quotes": [],
                "confidence": 0.8,
                "key_findings": [],
                "control_effectiveness": {},
                "plan_review_summary": "",
                "judgment_review_summary": "",
                "test_coverage": {},
            },
            "task_results": [],
            "execution_plan": {"analysis": {}, "execution_plan": [], "task_dependencies": {}, "reasoning": ""},
        }
        self.orch.graph.ainvoke = AsyncMock(return_value=mock_final_state)

        prev = {"evaluationResult": True, "reevaluationRound": 0}

        with patch.object(self.orch.highlighting_service, "highlight_evidence", new_callable=AsyncMock, return_value=[]):
            result = await self.orch.evaluate(
                self._make_context(),
                user_feedback="確認",
                reevaluation_mode="full",
                previous_result=prev,
            )

        assert result.result_changed is False


# =============================================================================
# _evaluate_judgment_only テスト
# =============================================================================

class TestEvaluateJudgmentOnly:
    """_evaluate_judgment_only メソッドのテスト"""

    @pytest.fixture(autouse=True)
    def setup(self):
        with patch("core.graph_orchestrator.StateGraph") as mock_sg:
            mock_sg.return_value = MagicMock()
            mock_sg.return_value.compile.return_value = MagicMock()
            # LLMを設定
            self.mock_llm = MagicMock()
            self.orch = GraphAuditOrchestrator(
                llm=self.mock_llm, vision_llm=None
            )

    def _make_context(self, with_files=False):
        files = []
        if with_files:
            files = [EvidenceFile(
                file_name="test.pdf", mime_type="application/pdf",
                extension=".pdf", base64_content="dGVzdA=="
            )]
        return AuditContext(
            item_id="CLC-01",
            control_description="テスト統制",
            test_procedure="テスト手続き",
            evidence_link="//server/path/",
            evidence_files=files,
        )

    @pytest.mark.asyncio
    async def test_judgment_only_calls_llm_with_feedback(self):
        """judgment_onlyモードでLLMにフィードバック付きのプロンプトを渡す"""
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = {
            "evaluation_result": False,
            "judgment_basis": "再評価済み根拠",
            "document_quotes": [],
            "confidence": 0.85,
        }

        with patch("core.graph_orchestrator.ChatPromptTemplate") as mock_pt:
            mock_pt.from_template.return_value.__or__ = MagicMock(
                return_value=MagicMock(__or__=MagicMock(return_value=mock_chain))
            )
            with patch.object(self.orch.highlighting_service, "highlight_evidence", new_callable=AsyncMock, return_value=[]):
                result = await self.orch._evaluate_judgment_only(
                    context=self._make_context(),
                    user_feedback="署名日を確認してください",
                    previous_result={
                        "evaluationResult": True,
                        "judgmentBasis": "前回根拠",
                        "executionPlanSummary": "前回計画",
                        "taskResults": [],
                        "reevaluationRound": 0,
                    },
                )

        assert isinstance(result, AuditResult)
        assert result.feedback_applied is True
        assert result.reevaluation_round == 1
        assert result.result_changed is True  # True→False
        assert result.evaluation_result is False

    @pytest.mark.asyncio
    async def test_judgment_only_error_returns_fallback(self):
        """judgment_onlyでLLMエラー時にフォールバック結果を返す"""
        mock_chain = AsyncMock()
        mock_chain.ainvoke.side_effect = Exception("LLMエラー")

        with patch("core.graph_orchestrator.ChatPromptTemplate") as mock_pt:
            mock_pt.from_template.return_value.__or__ = MagicMock(
                return_value=MagicMock(__or__=MagicMock(return_value=mock_chain))
            )
            result = await self.orch._evaluate_judgment_only(
                context=self._make_context(),
                user_feedback="テスト",
                previous_result={
                    "evaluationResult": True,
                    "reevaluationRound": 0,
                },
            )

        assert isinstance(result, AuditResult)
        assert result.evaluation_result is False
        assert "エラー" in result.judgment_basis

    @pytest.mark.asyncio
    async def test_judgment_only_uses_previous_task_results(self):
        """judgment_onlyが前回のタスク結果をプロンプトに含める"""
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = {
            "evaluation_result": True,
            "judgment_basis": "有効",
            "document_quotes": [],
            "confidence": 0.9,
        }

        prev_results = {
            "evaluationResult": True,
            "judgmentBasis": "前回根拠",
            "executionPlanSummary": "【A5:意味的推論】",
            "taskResults": [
                {
                    "taskType": "A5",
                    "taskName": "意味的推論",
                    "success": True,
                    "confidence": 0.9,
                    "reasoning": "確認完了",
                }
            ],
            "reevaluationRound": 1,
        }

        with patch("core.graph_orchestrator.ChatPromptTemplate") as mock_pt:
            mock_pt.from_template.return_value.__or__ = MagicMock(
                return_value=MagicMock(__or__=MagicMock(return_value=mock_chain))
            )
            with patch.object(self.orch.highlighting_service, "highlight_evidence", new_callable=AsyncMock, return_value=[]):
                result = await self.orch._evaluate_judgment_only(
                    context=self._make_context(with_files=True),
                    user_feedback="再確認",
                    previous_result=prev_results,
                )

        # LLM呼び出し時の引数を確認
        call_kwargs = mock_chain.ainvoke.call_args[0][0]
        assert "A5" in call_kwargs["task_results"]
        assert "意味的推論" in call_kwargs["task_results"]
        assert result.reevaluation_round == 2

    @pytest.mark.asyncio
    async def test_judgment_only_no_previous_tasks(self):
        """前回タスク結果がない場合でもエラーにならない"""
        mock_chain = AsyncMock()
        mock_chain.ainvoke.return_value = {
            "evaluation_result": True,
            "judgment_basis": "有効",
            "document_quotes": [],
            "confidence": 0.8,
        }

        with patch("core.graph_orchestrator.ChatPromptTemplate") as mock_pt:
            mock_pt.from_template.return_value.__or__ = MagicMock(
                return_value=MagicMock(__or__=MagicMock(return_value=mock_chain))
            )
            with patch.object(self.orch.highlighting_service, "highlight_evidence", new_callable=AsyncMock, return_value=[]):
                result = await self.orch._evaluate_judgment_only(
                    context=self._make_context(),
                    user_feedback="確認",
                    previous_result={
                        "evaluationResult": True,
                        "reevaluationRound": 0,
                    },
                )

        assert isinstance(result, AuditResult)
        call_kwargs = mock_chain.ainvoke.call_args[0][0]
        assert "タスク結果情報なし" in call_kwargs["task_results"]
