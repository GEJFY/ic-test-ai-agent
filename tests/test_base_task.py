# -*- coding: utf-8 -*-
"""
================================================================================
test_base_task.py - base_task.pyのユニットテスト
================================================================================

【テスト対象】
- TaskType: タスクタイプ列挙型
- TaskResult: タスク結果データクラス
- EvidenceFile: 証跡ファイルデータクラス
- AuditContext: 監査コンテキストデータクラス
- BaseAuditTask: 抽象基底クラス

================================================================================
"""

import pytest
import base64
from core.tasks.base_task import (
    TaskType,
    TaskResult,
    EvidenceFile,
    AuditContext,
    BaseAuditTask
)


# =============================================================================
# TaskType テスト
# =============================================================================

class TestTaskType:
    """TaskType列挙型のテスト"""

    def test_all_task_types_exist(self):
        """全タスクタイプ（A1-A8）が定義されているか"""
        expected_types = [
            "A1_SEMANTIC_SEARCH",
            "A2_IMAGE_RECOGNITION",
            "A3_DATA_EXTRACTION",
            "A4_STEPWISE_REASONING",
            "A5_SEMANTIC_REASONING",
            "A6_MULTI_DOCUMENT",
            "A7_PATTERN_ANALYSIS",
            "A8_SOD_DETECTION"
        ]
        for type_name in expected_types:
            assert hasattr(TaskType, type_name), f"TaskType.{type_name} が存在しない"

    def test_task_type_values(self):
        """タスクタイプの値が正しいか"""
        assert TaskType.A1_SEMANTIC_SEARCH.value == "A1"
        assert TaskType.A2_IMAGE_RECOGNITION.value == "A2"
        assert TaskType.A3_DATA_EXTRACTION.value == "A3"
        assert TaskType.A4_STEPWISE_REASONING.value == "A4"
        assert TaskType.A5_SEMANTIC_REASONING.value == "A5"
        assert TaskType.A6_MULTI_DOCUMENT.value == "A6"
        assert TaskType.A7_PATTERN_ANALYSIS.value == "A7"
        assert TaskType.A8_SOD_DETECTION.value == "A8"

    def test_task_type_count(self):
        """タスクタイプが8種類あるか"""
        assert len(TaskType) == 8


# =============================================================================
# TaskResult テスト
# =============================================================================

class TestTaskResult:
    """TaskResultデータクラスのテスト"""

    def test_create_task_result(self):
        """TaskResultの基本作成"""
        result = TaskResult(
            task_type=TaskType.A1_SEMANTIC_SEARCH,
            task_name="意味検索",
            success=True,
            result={"matches": ["test1", "test2"]},
            reasoning="テスト理由",
            confidence=0.85,
            evidence_references=["file1.pdf"]
        )
        assert result.task_type == TaskType.A1_SEMANTIC_SEARCH
        assert result.task_name == "意味検索"
        assert result.success is True
        assert result.confidence == 0.85
        assert len(result.evidence_references) == 1

    def test_task_result_default_values(self):
        """TaskResultのデフォルト値"""
        result = TaskResult(
            task_type=TaskType.A1_SEMANTIC_SEARCH,
            task_name="意味検索",
            success=False,
            result=None,
            reasoning="失敗理由"
        )
        assert result.confidence == 0.0
        assert result.evidence_references == []
        assert result.sub_results == []

    def test_task_result_to_dict(self):
        """TaskResult.to_dict()のテスト"""
        result = TaskResult(
            task_type=TaskType.A2_IMAGE_RECOGNITION,
            task_name="画像認識",
            success=True,
            result={"signature": "found"},
            reasoning="署名を検出",
            confidence=0.95,
            evidence_references=["doc.pdf", "image.png"]
        )
        d = result.to_dict()

        assert d["taskType"] == "A2"
        assert d["taskName"] == "画像認識"
        assert d["success"] is True
        assert d["confidence"] == 0.95
        assert d["reasoning"] == "署名を検出"
        assert d["evidenceReferences"] == ["doc.pdf", "image.png"]

    def test_task_result_with_sub_results(self):
        """サブ結果を持つTaskResult"""
        sub_result = TaskResult(
            task_type=TaskType.A1_SEMANTIC_SEARCH,
            task_name="意味検索",
            success=True,
            result={},
            reasoning="サブタスク完了"
        )
        main_result = TaskResult(
            task_type=TaskType.A6_MULTI_DOCUMENT,
            task_name="複数文書統合",
            success=True,
            result={},
            reasoning="メインタスク完了",
            sub_results=[sub_result]
        )
        assert len(main_result.sub_results) == 1
        assert main_result.sub_results[0].task_type == TaskType.A1_SEMANTIC_SEARCH


# =============================================================================
# EvidenceFile テスト
# =============================================================================

class TestEvidenceFile:
    """EvidenceFileデータクラスのテスト"""

    def test_create_evidence_file(self):
        """EvidenceFileの基本作成"""
        content = base64.b64encode(b"test content").decode('utf-8')
        ef = EvidenceFile(
            file_name="test.pdf",
            extension=".pdf",
            mime_type="application/pdf",
            base64_content=content
        )
        assert ef.file_name == "test.pdf"
        assert ef.extension == ".pdf"
        assert ef.mime_type == "application/pdf"
        assert ef.base64_content == content

    def test_evidence_file_from_dict(self):
        """EvidenceFile.from_dict()のテスト"""
        content = base64.b64encode(b"test content").decode('utf-8')
        data = {
            "fileName": "report.xlsx",
            "extension": ".xlsx",
            "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "base64": content
        }
        ef = EvidenceFile.from_dict(data)

        assert ef.file_name == "report.xlsx"
        assert ef.extension == ".xlsx"
        assert ef.mime_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert ef.base64_content == content

    def test_evidence_file_from_dict_missing_fields(self):
        """不完全なデータからのEvidenceFile作成"""
        data = {"fileName": "test.txt"}
        ef = EvidenceFile.from_dict(data)

        assert ef.file_name == "test.txt"
        assert ef.extension == ""
        assert ef.mime_type == ""
        assert ef.base64_content == ""

    def test_evidence_file_japanese_filename(self):
        """日本語ファイル名のEvidenceFile"""
        content = base64.b64encode("テスト内容".encode('utf-8')).decode('utf-8')
        ef = EvidenceFile(
            file_name="売上報告書_2025年度.pdf",
            extension=".pdf",
            mime_type="application/pdf",
            base64_content=content
        )
        assert ef.file_name == "売上報告書_2025年度.pdf"


# =============================================================================
# AuditContext テスト
# =============================================================================

class TestAuditContext:
    """AuditContextデータクラスのテスト"""

    def test_create_audit_context(self, sample_evidence_file):
        """AuditContextの基本作成"""
        context = AuditContext(
            item_id="CLC-01",
            control_description="月次売上承認",
            test_procedure="承認印を確認",
            evidence_link="\\\\server\\evidence\\",
            evidence_files=[sample_evidence_file]
        )
        assert context.item_id == "CLC-01"
        assert context.control_description == "月次売上承認"
        assert context.test_procedure == "承認印を確認"
        assert len(context.evidence_files) == 1
        assert context.additional_context == {}

    def test_audit_context_from_request(self, sample_request_item):
        """AuditContext.from_request()のテスト"""
        context = AuditContext.from_request(sample_request_item)

        assert context.item_id == "CLC-01"
        assert "承認プロセス" in context.control_description
        assert "署名" in context.test_procedure
        assert len(context.evidence_files) == 2

    def test_audit_context_from_request_empty(self):
        """空のリクエストからAuditContext作成"""
        context = AuditContext.from_request({})

        assert context.item_id == "unknown"
        assert context.control_description == ""
        assert context.test_procedure == ""
        assert context.evidence_files == []

    def test_audit_context_with_additional_context(self, sample_evidence_file):
        """追加コンテキスト付きAuditContext"""
        context = AuditContext(
            item_id="CLC-02",
            control_description="四半期レビュー",
            test_procedure="レビュー記録を確認",
            evidence_link="",
            evidence_files=[sample_evidence_file],
            additional_context={
                "fiscal_year": "2025",
                "department": "経理部"
            }
        )
        assert context.additional_context["fiscal_year"] == "2025"
        assert context.additional_context["department"] == "経理部"


# =============================================================================
# BaseAuditTask テスト
# =============================================================================

class TestBaseAuditTask:
    """BaseAuditTask抽象基底クラスのテスト"""

    def test_cannot_instantiate_base_class(self):
        """BaseAuditTaskを直接インスタンス化できないことを確認"""
        with pytest.raises(TypeError):
            BaseAuditTask()

    def test_concrete_task_implementation(self, sample_audit_context):
        """具体的なタスク実装のテスト"""
        # 具体的な実装クラスを作成
        class ConcreteTask(BaseAuditTask):
            task_type = TaskType.A1_SEMANTIC_SEARCH
            task_name = "テストタスク"
            description = "テスト用の具体的タスク"

            async def execute(self, context: AuditContext) -> TaskResult:
                return self._create_result(
                    success=True,
                    result={"test": "data"},
                    reasoning="テスト完了",
                    confidence=0.9
                )

        task = ConcreteTask(llm=None)
        assert task.task_type == TaskType.A1_SEMANTIC_SEARCH
        assert task.task_name == "テストタスク"

    def test_get_task_info(self):
        """get_task_info()のテスト"""
        class ConcreteTask(BaseAuditTask):
            task_type = TaskType.A3_DATA_EXTRACTION
            task_name = "データ抽出"
            description = "表からデータを抽出"

            async def execute(self, context):
                pass

        task = ConcreteTask()
        info = task.get_task_info()

        assert info["type"] == "A3"
        assert info["name"] == "データ抽出"
        assert info["description"] == "表からデータを抽出"

    def test_create_result_helper(self):
        """_create_result()ヘルパーメソッドのテスト"""
        class ConcreteTask(BaseAuditTask):
            task_type = TaskType.A5_SEMANTIC_REASONING
            task_name = "意味推論"
            description = "意味推論タスク"

            async def execute(self, context):
                pass

        task = ConcreteTask()
        result = task._create_result(
            success=True,
            result={"key": "value"},
            reasoning="推論完了",
            confidence=0.88,
            evidence_refs=["doc1.pdf", "doc2.xlsx"]
        )

        assert result.task_type == TaskType.A5_SEMANTIC_REASONING
        assert result.task_name == "意味推論"
        assert result.success is True
        assert result.confidence == 0.88
        assert len(result.evidence_references) == 2

    @pytest.mark.asyncio
    async def test_async_execute(self, sample_audit_context):
        """非同期execute()のテスト"""
        class AsyncTask(BaseAuditTask):
            task_type = TaskType.A7_PATTERN_ANALYSIS
            task_name = "パターン分析"
            description = "パターン分析タスク"

            async def execute(self, context: AuditContext) -> TaskResult:
                # 非同期処理をシミュレート
                return self._create_result(
                    success=True,
                    result={"patterns": ["pattern1", "pattern2"]},
                    reasoning="2つのパターンを検出",
                    confidence=0.75
                )

        task = AsyncTask()
        result = await task.execute(sample_audit_context)

        assert result.success is True
        assert result.result["patterns"] == ["pattern1", "pattern2"]

    def test_task_with_llm(self, mock_llm):
        """LLM付きタスクの初期化テスト"""
        class LLMTask(BaseAuditTask):
            task_type = TaskType.A1_SEMANTIC_SEARCH
            task_name = "LLMタスク"
            description = "LLMを使用するタスク"

            async def execute(self, context):
                pass

        task = LLMTask(llm=mock_llm)
        assert task.llm is not None
        assert task.llm == mock_llm
