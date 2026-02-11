# -*- coding: utf-8 -*-
"""
================================================================================
test_tasks.py - A1-A8タスクのユニットテスト
================================================================================

【テスト対象】
- A1: SemanticSearchTask（意味検索）
- A2: ImageRecognitionTask（画像認識）
- A3: DataExtractionTask（データ抽出）
- A4: StepwiseReasoningTask（段階的推論）
- A5: SemanticReasoningTask（意味推論）
- A6: MultiDocumentTask（複数文書統合）
- A7: PatternAnalysisTask（パターン分析）
- A8: SoDDetectionTask（SoD検出）

================================================================================
"""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import base64

from core.tasks.base_task import (
    TaskType, TaskResult, AuditContext, EvidenceFile
)


# =============================================================================
# タスククラスのインポートとインスタンス化テスト
# =============================================================================

class TestTaskImports:
    """タスクのインポートテスト"""

    def test_import_a1_semantic_search(self):
        """A1タスクのインポート"""
        from core.tasks.a1_semantic_search import SemanticSearchTask
        task = SemanticSearchTask(llm=None)
        assert task.task_type == TaskType.A1_SEMANTIC_SEARCH

    def test_import_a2_image_recognition(self):
        """A2タスクのインポート"""
        from core.tasks.a2_image_recognition import ImageRecognitionTask
        task = ImageRecognitionTask(llm=None)
        assert task.task_type == TaskType.A2_IMAGE_RECOGNITION

    def test_import_a3_data_extraction(self):
        """A3タスクのインポート"""
        from core.tasks.a3_data_extraction import DataExtractionTask
        task = DataExtractionTask(llm=None)
        assert task.task_type == TaskType.A3_DATA_EXTRACTION

    def test_import_a4_stepwise_reasoning(self):
        """A4タスクのインポート"""
        from core.tasks.a4_stepwise_reasoning import StepwiseReasoningTask
        task = StepwiseReasoningTask(llm=None)
        assert task.task_type == TaskType.A4_STEPWISE_REASONING

    def test_import_a5_semantic_reasoning(self):
        """A5タスクのインポート"""
        from core.tasks.a5_semantic_reasoning import SemanticReasoningTask
        task = SemanticReasoningTask(llm=None)
        assert task.task_type == TaskType.A5_SEMANTIC_REASONING

    def test_import_a6_multi_document(self):
        """A6タスクのインポート"""
        from core.tasks.a6_multi_document import MultiDocumentTask
        task = MultiDocumentTask(llm=None)
        assert task.task_type == TaskType.A6_MULTI_DOCUMENT

    def test_import_a7_pattern_analysis(self):
        """A7タスクのインポート"""
        from core.tasks.a7_pattern_analysis import PatternAnalysisTask
        task = PatternAnalysisTask(llm=None)
        assert task.task_type == TaskType.A7_PATTERN_ANALYSIS

    def test_import_a8_sod_detection(self):
        """A8タスクのインポート"""
        from core.tasks.a8_sod_detection import SoDDetectionTask
        task = SoDDetectionTask(llm=None)
        assert task.task_type == TaskType.A8_SOD_DETECTION


# =============================================================================
# タスク情報テスト
# =============================================================================

class TestTaskInfo:
    """get_task_info()のテスト"""

    def test_all_tasks_have_info(self):
        """全タスクがタスク情報を持つ"""
        from core.tasks.a1_semantic_search import SemanticSearchTask
        from core.tasks.a2_image_recognition import ImageRecognitionTask
        from core.tasks.a3_data_extraction import DataExtractionTask
        from core.tasks.a4_stepwise_reasoning import StepwiseReasoningTask
        from core.tasks.a5_semantic_reasoning import SemanticReasoningTask
        from core.tasks.a6_multi_document import MultiDocumentTask
        from core.tasks.a7_pattern_analysis import PatternAnalysisTask
        from core.tasks.a8_sod_detection import SoDDetectionTask

        tasks = [
            SemanticSearchTask(),
            ImageRecognitionTask(),
            DataExtractionTask(),
            StepwiseReasoningTask(),
            SemanticReasoningTask(),
            MultiDocumentTask(),
            PatternAnalysisTask(),
            SoDDetectionTask(),
        ]

        for task in tasks:
            info = task.get_task_info()
            assert "type" in info
            assert "name" in info
            assert "description" in info
            expected_types = [
                "A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8"
            ]
            assert info["type"] in expected_types


# =============================================================================
# A1: SemanticSearchTask テスト
# =============================================================================

class TestSemanticSearchTask:
    """A1: SemanticSearchTaskのテスト"""

    @pytest.fixture
    def mock_llm(self):
        """LLMモック"""
        mock = MagicMock()
        mock_response = Mock()
        mock_response.content = json.dumps({
            "matches": [
                {"text": "関連テキスト1", "relevance": 0.9},
                {"text": "関連テキスト2", "relevance": 0.8}
            ],
            "overall_relevance": 0.85,
            "reasoning": "統制記述に関連する記述を発見"
        })
        mock.invoke.return_value = mock_response
        mock.__or__ = Mock(return_value=mock)
        return mock

    @pytest.fixture
    def sample_context(self):
        """サンプルコンテキスト"""
        return AuditContext(
            item_id="CLC-01",
            control_description="コンプライアンス研修が実施されている",
            test_procedure="研修記録に参加者の署名があることを確認",
            evidence_link="",
            evidence_files=[
                EvidenceFile(
                    file_name="研修記録.txt",
                    extension=".txt",
                    mime_type="text/plain",
                    base64_content=base64.b64encode(
                        "研修参加者リスト\n山田太郎 署名済\n鈴木花子 署名済".encode()
                    ).decode()
                )
            ]
        )

    def test_task_attributes(self):
        """タスク属性の確認"""
        from core.tasks.a1_semantic_search import SemanticSearchTask
        task = SemanticSearchTask()
        assert task.task_type == TaskType.A1_SEMANTIC_SEARCH
        assert "意味検索" in task.task_name

    @pytest.mark.asyncio
    async def test_execute_without_llm(self, sample_context):
        """LLMなしでの実行"""
        from core.tasks.a1_semantic_search import SemanticSearchTask
        task = SemanticSearchTask(llm=None)

        result = await task.execute(sample_context)

        assert isinstance(result, TaskResult)
        assert result.task_type == TaskType.A1_SEMANTIC_SEARCH


# =============================================================================
# A2: ImageRecognitionTask テスト
# =============================================================================

class TestImageRecognitionTask:
    """A2: ImageRecognitionTaskのテスト"""

    def test_task_attributes(self):
        """タスク属性の確認"""
        from core.tasks.a2_image_recognition import ImageRecognitionTask
        task = ImageRecognitionTask()
        assert task.task_type == TaskType.A2_IMAGE_RECOGNITION
        assert "画像認識" in task.task_name

    @pytest.fixture
    def sample_image_context(self):
        """画像を含むサンプルコンテキスト"""
        return AuditContext(
            item_id="CLC-02",
            control_description="承認印が押印されている",
            test_procedure="承認書に承認印があることを確認",
            evidence_link="",
            evidence_files=[
                EvidenceFile(
                    file_name="承認書.png",
                    extension=".png",
                    mime_type="image/png",
                    base64_content=base64.b64encode(
                        b"fake image data"
                    ).decode()
                )
            ]
        )


# =============================================================================
# A3: DataExtractionTask テスト
# =============================================================================

class TestDataExtractionTask:
    """A3: DataExtractionTaskのテスト"""

    def test_task_attributes(self):
        """タスク属性の確認"""
        from core.tasks.a3_data_extraction import DataExtractionTask
        task = DataExtractionTask()
        assert task.task_type == TaskType.A3_DATA_EXTRACTION
        assert "データ抽出" in task.task_name or "抽出" in task.task_name


# =============================================================================
# A4: StepwiseReasoningTask テスト
# =============================================================================

class TestStepwiseReasoningTask:
    """A4: StepwiseReasoningTaskのテスト"""

    def test_task_attributes(self):
        """タスク属性の確認"""
        from core.tasks.a4_stepwise_reasoning import StepwiseReasoningTask
        task = StepwiseReasoningTask()
        assert task.task_type == TaskType.A4_STEPWISE_REASONING
        assert "推論" in task.task_name or "段階" in task.task_name


# =============================================================================
# A5: SemanticReasoningTask テスト
# =============================================================================

class TestSemanticReasoningTask:
    """A5: SemanticReasoningTaskのテスト"""

    def test_task_attributes(self):
        """タスク属性の確認"""
        from core.tasks.a5_semantic_reasoning import SemanticReasoningTask
        task = SemanticReasoningTask()
        assert task.task_type == TaskType.A5_SEMANTIC_REASONING
        assert "意味" in task.task_name or "推論" in task.task_name


# =============================================================================
# A6: MultiDocumentTask テスト
# =============================================================================

class TestMultiDocumentTask:
    """A6: MultiDocumentTaskのテスト"""

    def test_task_attributes(self):
        """タスク属性の確認"""
        from core.tasks.a6_multi_document import MultiDocumentTask
        task = MultiDocumentTask()
        assert task.task_type == TaskType.A6_MULTI_DOCUMENT
        assert "複数" in task.task_name or "文書" in task.task_name

    @pytest.fixture
    def multi_doc_context(self):
        """複数文書のコンテキスト"""
        return AuditContext(
            item_id="CLC-06",
            control_description="承認フローが遵守されている",
            test_procedure="申請書と承認書の整合性を確認",
            evidence_link="",
            evidence_files=[
                EvidenceFile("申請書.txt", ".txt", "text/plain",
                            base64.b64encode(b"application").decode()),
                EvidenceFile("承認書.txt", ".txt", "text/plain",
                            base64.b64encode(b"approval").decode()),
            ]
        )


# =============================================================================
# A7: PatternAnalysisTask テスト
# =============================================================================

class TestPatternAnalysisTask:
    """A7: PatternAnalysisTaskのテスト"""

    def test_task_attributes(self):
        """タスク属性の確認"""
        from core.tasks.a7_pattern_analysis import PatternAnalysisTask
        task = PatternAnalysisTask()
        assert task.task_type == TaskType.A7_PATTERN_ANALYSIS
        assert "パターン" in task.task_name or "分析" in task.task_name


# =============================================================================
# A8: SoDDetectionTask テスト
# =============================================================================

class TestSoDDetectionTask:
    """A8: SoDDetectionTaskのテスト"""

    def test_task_attributes(self):
        """タスク属性の確認"""
        from core.tasks.a8_sod_detection import SoDDetectionTask
        task = SoDDetectionTask()
        assert task.task_type == TaskType.A8_SOD_DETECTION
        assert "SoD" in task.task_name or "職務分掌" in task.task_name


# =============================================================================
# タスク結果生成テスト
# =============================================================================

class TestTaskResultCreation:
    """_create_result()ヘルパーのテスト"""

    def test_create_success_result(self):
        """成功結果の生成"""
        from core.tasks.a1_semantic_search import SemanticSearchTask
        task = SemanticSearchTask()

        result = task._create_result(
            success=True,
            result={"matches": ["test1", "test2"]},
            reasoning="テスト成功",
            confidence=0.9,
            evidence_refs=["doc1.pdf"]
        )

        assert result.success is True
        assert result.confidence == 0.9
        assert result.task_type == TaskType.A1_SEMANTIC_SEARCH

    def test_create_failure_result(self):
        """失敗結果の生成"""
        from core.tasks.a2_image_recognition import ImageRecognitionTask
        task = ImageRecognitionTask()

        result = task._create_result(
            success=False,
            result={"error": "画像が見つかりません"},
            reasoning="画像ファイルが含まれていません",
            confidence=0.0
        )

        assert result.success is False
        assert result.confidence == 0.0


# =============================================================================
# 統合テスト
# =============================================================================

class TestTasksIntegration:
    """タスクの統合テスト"""

    def test_all_task_types_covered(self):
        """全タスクタイプがカバーされているか"""
        from core.tasks.a1_semantic_search import SemanticSearchTask
        from core.tasks.a2_image_recognition import ImageRecognitionTask
        from core.tasks.a3_data_extraction import DataExtractionTask
        from core.tasks.a4_stepwise_reasoning import StepwiseReasoningTask
        from core.tasks.a5_semantic_reasoning import SemanticReasoningTask
        from core.tasks.a6_multi_document import MultiDocumentTask
        from core.tasks.a7_pattern_analysis import PatternAnalysisTask
        from core.tasks.a8_sod_detection import SoDDetectionTask

        task_types_from_classes = {
            SemanticSearchTask().task_type,
            ImageRecognitionTask().task_type,
            DataExtractionTask().task_type,
            StepwiseReasoningTask().task_type,
            SemanticReasoningTask().task_type,
            MultiDocumentTask().task_type,
            PatternAnalysisTask().task_type,
            SoDDetectionTask().task_type,
        }

        all_task_types = set(TaskType)

        assert task_types_from_classes == all_task_types

    def test_tasks_have_llm_property(self):
        """全タスクがLLMプロパティを持つ"""
        from core.tasks.a1_semantic_search import SemanticSearchTask
        from core.tasks.a2_image_recognition import ImageRecognitionTask

        mock_llm = Mock()

        task1 = SemanticSearchTask(llm=mock_llm)
        assert task1.llm == mock_llm

        task2 = ImageRecognitionTask(llm=mock_llm)
        assert task2.llm == mock_llm

    @pytest.mark.asyncio
    async def test_tasks_return_task_result(self, sample_audit_context):
        """全タスクがTaskResultを返す"""
        from core.tasks.a1_semantic_search import SemanticSearchTask

        task = SemanticSearchTask(llm=None)

        # LLMなしでも結果は返る（エラー結果として）
        result = await task.execute(sample_audit_context)

        assert isinstance(result, TaskResult)
        assert result.task_type is not None
        assert result.task_name is not None
