# -*- coding: utf-8 -*-
"""
================================================================================
test_tasks_execute.py - A1-A8 タスク execute() ロジックのユニットテスト
================================================================================

【テスト対象】
- 各タスクの execute() メソッド（LLMをモック化）
- LLM未設定時の早期リターン
- LLM応答のパース・成功判定ロジック
- エラーハンドリング

================================================================================
"""

import pytest
import base64
import json
from unittest.mock import patch, MagicMock, AsyncMock, Mock

from core.tasks.base_task import (
    TaskType, TaskResult, EvidenceFile, AuditContext, BaseAuditTask
)


# =============================================================================
# ヘルパー
# =============================================================================

def _make_context(item_id="CLC-01", files=None):
    """テスト用AuditContextを作成"""
    if files is None:
        text_content = "承認済み。月次レビュー完了。署名者: 田中太郎"
        b64 = base64.b64encode(text_content.encode()).decode()
        files = [
            EvidenceFile(
                file_name="report.txt",
                extension=".txt",
                mime_type="text/plain",
                base64_content=b64
            )
        ]
    return AuditContext(
        item_id=item_id,
        control_description="月次で売上の承認プロセスが実施されている",
        test_procedure="売上報告書に承認者の署名があることを確認する",
        evidence_link="\\\\server\\evidence\\",
        evidence_files=files
    )


def _make_llm_response(content_dict):
    """LLM応答モックを作成"""
    mock = Mock()
    mock.content = json.dumps(content_dict, ensure_ascii=False)
    return mock


def _make_async_llm(response_dict):
    """非同期LLMモックを作成"""
    mock_llm = MagicMock()
    mock_response = _make_llm_response(response_dict)
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    return mock_llm


def _mock_chain_on_task(task, response_dict):
    """タスクの LangChain チェーン (prompt | llm | parser) をモック化

    task.prompt を差し替えて、chain = self.prompt | self.llm | self.parser の
    結果が mock_chain になるようにする。mock_chain.ainvoke() は response_dict を返す。
    """
    mock_chain = MagicMock()
    mock_chain.ainvoke = AsyncMock(return_value=response_dict)

    mock_intermediate = MagicMock()
    mock_intermediate.__or__ = Mock(return_value=mock_chain)

    task.prompt = MagicMock()
    task.prompt.__or__ = Mock(return_value=mock_intermediate)


# =============================================================================
# BaseAuditTask テスト
# =============================================================================

class TestBaseAuditTask:
    """BaseAuditTask の共通機能テスト"""

    def test_task_type_enum(self):
        """TaskType enum の定義"""
        assert TaskType.A1_SEMANTIC_SEARCH.value == "A1"
        assert TaskType.A8_SOD_DETECTION.value == "A8"
        assert len(TaskType) == 8

    def test_evidence_file(self):
        """EvidenceFile dataclass"""
        ef = EvidenceFile(
            file_name="doc.pdf",
            extension=".pdf",
            mime_type="application/pdf",
            base64_content="dGVzdA=="
        )
        assert ef.file_name == "doc.pdf"
        assert ef.extension == ".pdf"

    def test_audit_context(self):
        """AuditContext dataclass"""
        ctx = _make_context()
        assert ctx.item_id == "CLC-01"
        assert len(ctx.evidence_files) == 1

    def test_task_result_defaults(self):
        """TaskResult デフォルト値"""
        result = TaskResult(
            task_type=TaskType.A1_SEMANTIC_SEARCH,
            task_name="テスト",
            success=True,
            result={},
            reasoning="理由",
            confidence=0.9,
        )
        assert result.evidence_references == []
        assert result.sub_results == []


# =============================================================================
# A1: SemanticSearchTask テスト
# =============================================================================

class TestA1SemanticSearch:
    """A1 意味検索タスクのテスト"""

    @pytest.mark.asyncio
    async def test_no_llm_returns_false(self):
        """LLM未設定で失敗"""
        from core.tasks.a1_semantic_search import SemanticSearchTask
        task = SemanticSearchTask(llm=None)
        result = await task.execute(_make_context())
        assert result.success is False

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """正常実行（高い関連度）"""
        from core.tasks.a1_semantic_search import SemanticSearchTask

        llm_response = {
            "overall_relevance": 0.9,
            "found_matches": [{"matched_text": "承認済み"}],
            "reasoning": "関連テキスト発見"
        }
        mock_llm = MagicMock()
        task = SemanticSearchTask(llm=mock_llm)
        _mock_chain_on_task(task, llm_response)

        with patch("core.document_processor.DocumentProcessor") as MockDP:
            mock_dp = MagicMock()
            mock_dp.extract_text.return_value = "承認済み。月次レビュー完了。"
            MockDP.return_value = mock_dp

            result = await task.execute(_make_context())

        assert result.task_type == TaskType.A1_SEMANTIC_SEARCH
        assert result.success is True
        assert result.confidence > 0

    @pytest.mark.asyncio
    async def test_execute_low_relevance(self):
        """低い関連度で失敗"""
        from core.tasks.a1_semantic_search import SemanticSearchTask

        llm_response = {
            "overall_relevance": 0.2,
            "found_matches": [],
            "reasoning": "関連テキストなし"
        }
        mock_llm = MagicMock()
        task = SemanticSearchTask(llm=mock_llm)
        _mock_chain_on_task(task, llm_response)

        with patch("core.document_processor.DocumentProcessor") as MockDP:
            mock_dp = MagicMock()
            mock_dp.extract_text.return_value = "無関係なテキスト"
            MockDP.return_value = mock_dp

            result = await task.execute(_make_context())

        assert result.success is False


# =============================================================================
# A2: ImageRecognitionTask テスト
# =============================================================================

class TestA2ImageRecognition:
    """A2 画像認識タスクのテスト"""

    @pytest.mark.asyncio
    async def test_no_vision_llm_returns_false(self):
        """Vision LLM未設定で失敗"""
        from core.tasks.a2_image_recognition import ImageRecognitionTask
        task = ImageRecognitionTask(llm=MagicMock(), vision_llm=None)
        result = await task.execute(_make_context())
        assert result.success is False

    @pytest.mark.asyncio
    async def test_no_processable_files(self):
        """画像ファイルがない場合"""
        from core.tasks.a2_image_recognition import ImageRecognitionTask

        ctx = _make_context()  # .txt ファイルのみ
        mock_vision = MagicMock()
        mock_vision.ainvoke = AsyncMock()
        task = ImageRecognitionTask(llm=MagicMock(), vision_llm=mock_vision)

        result = await task.execute(ctx)
        assert result.success is False


# =============================================================================
# A4: StepwiseReasoningTask テスト
# =============================================================================

class TestA4StepwiseReasoning:
    """A4 段階的推論タスクのテスト"""

    @pytest.mark.asyncio
    async def test_no_llm_returns_false(self):
        """LLM未設定で失敗"""
        from core.tasks.a4_stepwise_reasoning import StepwiseReasoningTask
        task = StepwiseReasoningTask(llm=None)
        result = await task.execute(_make_context())
        assert result.success is False

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """正常実行（チェーン全体をモック）"""
        from core.tasks.a4_stepwise_reasoning import StepwiseReasoningTask

        llm_response = {
            "calculation_steps": [
                {"step_number": 1, "description": "合計", "result": "100,000"},
                {"step_number": 2, "description": "差異", "result": "0"}
            ],
            "final_result": {"match": True},
            "integrity_checks": [{"check": "合計一致", "passed": True}],
            "confidence": 0.9,
            "reasoning": "計算結果が一致"
        }

        mock_llm = MagicMock()
        task = StepwiseReasoningTask(llm=mock_llm)
        _mock_chain_on_task(task, llm_response)

        # csv ファイルを用意
        csv_b64 = base64.b64encode(b"amount\n100000").decode()
        ctx = _make_context(files=[
            EvidenceFile("data.csv", ".csv", "text/csv", csv_b64)
        ])

        result = await task.execute(ctx)

        assert result.success is True
        assert result.confidence == 0.9


# =============================================================================
# A5: SemanticReasoningTask テスト
# =============================================================================

class TestA5SemanticReasoning:
    """A5 意味検索+推論タスクのテスト"""

    @pytest.mark.asyncio
    async def test_no_llm_returns_false(self):
        """LLM未設定で失敗"""
        from core.tasks.a5_semantic_reasoning import SemanticReasoningTask
        task = SemanticReasoningTask(llm=None)
        result = await task.execute(_make_context())
        assert result.success is False

    @pytest.mark.asyncio
    async def test_execute_compliant(self):
        """準拠判定"""
        from core.tasks.a5_semantic_reasoning import SemanticReasoningTask

        llm_response = {
            "overall_assessment": {
                "compliance_level": "完全準拠",
                "criteria_met": 5,
                "criteria_total": 5,
                "key_findings": []
            },
            "evidence_evaluation": [
                {"evidence_source": "report.txt"}
            ],
            "confidence": 0.85,
            "reasoning": "テスト手続きを完全に満たしている"
        }
        mock_llm = MagicMock()
        task = SemanticReasoningTask(llm=mock_llm)
        _mock_chain_on_task(task, llm_response)

        with patch("core.document_processor.DocumentProcessor") as MockDP:
            mock_dp = MagicMock()
            mock_dp.extract_text.return_value = "承認済みレポート"
            MockDP.return_value = mock_dp

            result = await task.execute(_make_context())

        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_non_compliant(self):
        """非準拠判定"""
        from core.tasks.a5_semantic_reasoning import SemanticReasoningTask

        llm_response = {
            "overall_assessment": {
                "compliance_level": "非準拠",
                "criteria_met": 0,
                "criteria_total": 5,
                "key_findings": []
            },
            "evidence_evaluation": [],
            "confidence": 0.7,
            "reasoning": "証跡不足"
        }
        mock_llm = MagicMock()
        task = SemanticReasoningTask(llm=mock_llm)
        _mock_chain_on_task(task, llm_response)

        with patch("core.document_processor.DocumentProcessor") as MockDP:
            mock_dp = MagicMock()
            mock_dp.extract_text.return_value = ""
            MockDP.return_value = mock_dp

            result = await task.execute(_make_context())

        assert result.success is False


# =============================================================================
# A3, A6, A7, A8: LLM未設定テスト
# =============================================================================

class TestTasksNoLLM:
    """全タスク共通: LLM未設定テスト"""

    @pytest.mark.asyncio
    async def test_a3_no_llm(self):
        from core.tasks.a3_data_extraction import DataExtractionTask
        task = DataExtractionTask(llm=None)
        result = await task.execute(_make_context())
        assert result.success is False

    @pytest.mark.asyncio
    async def test_a6_no_llm(self):
        from core.tasks.a6_multi_document import MultiDocumentTask
        task = MultiDocumentTask(llm=None)
        result = await task.execute(_make_context())
        assert result.success is False

    @pytest.mark.asyncio
    async def test_a7_no_llm(self):
        from core.tasks.a7_pattern_analysis import PatternAnalysisTask
        task = PatternAnalysisTask(llm=None)
        result = await task.execute(_make_context())
        assert result.success is False

    @pytest.mark.asyncio
    async def test_a8_no_llm(self):
        from core.tasks.a8_sod_detection import SoDDetectionTask
        task = SoDDetectionTask(llm=None)
        result = await task.execute(_make_context())
        assert result.success is False


# =============================================================================
# A6: MultiDocumentTask テスト（証跡不足）
# =============================================================================

class TestA6MultiDocument:
    """A6 複数文書統合テスト"""

    @pytest.mark.asyncio
    async def test_insufficient_evidence(self):
        """証跡ファイルなしで失敗"""
        from core.tasks.a6_multi_document import MultiDocumentTask
        mock_llm = _make_async_llm({})
        task = MultiDocumentTask(llm=mock_llm)
        ctx = _make_context(files=[])  # 空
        result = await task.execute(ctx)
        assert result.success is False
