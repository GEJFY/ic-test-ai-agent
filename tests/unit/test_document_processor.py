# -*- coding: utf-8 -*-
"""
================================================================================
test_document_processor.py - document_processor.pyのユニットテスト
================================================================================

【テスト対象】
- TextElement: テキスト要素データクラス
- TableCell: 表セルデータクラス
- ExtractedTable: 抽出表データクラス
- ExtractedContent: 抽出コンテンツデータクラス
- AzureDocumentIntelligence: Document Intelligenceクライアント
- DocumentProcessor: メイン処理クラス

================================================================================
"""

import pytest
import base64
from unittest.mock import Mock, patch, MagicMock
from core.document_processor import (
    TextElement,
    TableCell,
    ExtractedTable,
    ExtractedContent,
    AzureDocumentIntelligence,
    DocumentProcessor
)


# =============================================================================
# TextElement テスト
# =============================================================================

class TestTextElement:
    """TextElementデータクラスのテスト"""

    def test_create_text_element(self):
        """TextElementの基本作成"""
        elem = TextElement(
            element_id="elem_0",
            text="サンプルテキスト",
            page_number=1,
            bounding_box=[0.5, 1.0, 5.0, 1.5],
            element_type="paragraph"
        )
        assert elem.element_id == "elem_0"
        assert elem.text == "サンプルテキスト"
        assert elem.page_number == 1
        assert elem.element_type == "paragraph"
        assert elem.confidence == 1.0  # デフォルト値

    def test_text_element_with_confidence(self):
        """信頼度付きTextElement"""
        elem = TextElement(
            element_id="elem_1",
            text="OCRテキスト",
            page_number=2,
            bounding_box=[1.0, 2.0, 6.0, 2.5],
            element_type="line",
            confidence=0.95
        )
        assert elem.confidence == 0.95

    def test_text_element_types(self):
        """各要素タイプのTextElement"""
        types = ["paragraph", "table_cell", "line", "word"]
        for t in types:
            elem = TextElement(
                element_id=f"elem_{t}",
                text="test",
                page_number=1,
                bounding_box=[0, 0, 1, 1],
                element_type=t
            )
            assert elem.element_type == t


# =============================================================================
# TableCell テスト
# =============================================================================

class TestTableCell:
    """TableCellデータクラスのテスト"""

    def test_create_table_cell(self):
        """TableCellの基本作成"""
        cell = TableCell(
            row_index=0,
            column_index=0,
            text="ヘッダー",
            bounding_box=[0, 0, 2, 1]
        )
        assert cell.row_index == 0
        assert cell.column_index == 0
        assert cell.text == "ヘッダー"
        assert cell.row_span == 1  # デフォルト
        assert cell.column_span == 1  # デフォルト

    def test_table_cell_with_span(self):
        """結合セルのTableCell"""
        cell = TableCell(
            row_index=1,
            column_index=0,
            text="結合セル",
            bounding_box=[0, 1, 4, 3],
            row_span=2,
            column_span=2
        )
        assert cell.row_span == 2
        assert cell.column_span == 2


# =============================================================================
# ExtractedTable テスト
# =============================================================================

class TestExtractedTable:
    """ExtractedTableデータクラスのテスト"""

    def test_create_extracted_table(self):
        """ExtractedTableの基本作成"""
        cells = [
            TableCell(0, 0, "A1", [0, 0, 1, 1]),
            TableCell(0, 1, "B1", [1, 0, 2, 1]),
            TableCell(1, 0, "A2", [0, 1, 1, 2]),
            TableCell(1, 1, "B2", [1, 1, 2, 2]),
        ]
        table = ExtractedTable(
            table_id="table_0",
            page_number=1,
            row_count=2,
            column_count=2,
            cells=cells,
            bounding_box=[0, 0, 2, 2]
        )
        assert table.table_id == "table_0"
        assert table.row_count == 2
        assert table.column_count == 2
        assert len(table.cells) == 4


# =============================================================================
# ExtractedContent テスト
# =============================================================================

class TestExtractedContent:
    """ExtractedContentデータクラスのテスト"""

    def test_create_extracted_content(self):
        """ExtractedContentの基本作成"""
        content = ExtractedContent(
            file_name="test.pdf",
            file_type="pdf",
            text_content="抽出されたテキスト",
            extraction_method="pypdf"
        )
        assert content.file_name == "test.pdf"
        assert content.file_type == "pdf"
        assert content.text_content == "抽出されたテキスト"
        assert content.extraction_method == "pypdf"
        assert content.page_count is None
        assert content.error is None

    def test_extracted_content_with_error(self):
        """エラー付きExtractedContent"""
        content = ExtractedContent(
            file_name="corrupted.pdf",
            file_type="pdf",
            text_content="[エラー]",
            extraction_method="error",
            error="ファイルが破損しています"
        )
        assert content.error == "ファイルが破損しています"

    def test_extracted_content_with_elements(self):
        """要素付きExtractedContent"""
        elements = [
            TextElement("elem_0", "テキスト1", 1, [0, 0, 1, 1], "line"),
            TextElement("elem_1", "テキスト2", 1, [0, 1, 1, 2], "line"),
        ]
        content = ExtractedContent(
            file_name="doc.pdf",
            file_type="pdf",
            text_content="テキスト1\nテキスト2",
            extraction_method="azure_document_intelligence_layout",
            page_count=1,
            elements=elements
        )
        assert len(content.elements) == 2
        assert content.page_count == 1


# =============================================================================
# AzureDocumentIntelligence テスト
# =============================================================================

class TestAzureDocumentIntelligence:
    """AzureDocumentIntelligenceクライアントのテスト"""

    def test_not_configured_without_env(self, mock_no_env):
        """環境変数なしで未設定状態"""
        with patch.dict('os.environ', {}, clear=True):
            di = AzureDocumentIntelligence()
            assert di.is_configured() is False

    def test_configured_with_env(self):
        """環境変数ありで設定状態"""
        with patch.dict('os.environ', {
            'AZURE_DI_ENDPOINT': 'https://test.cognitiveservices.azure.com/',
            'AZURE_DI_KEY': 'test-key'
        }):
            di = AzureDocumentIntelligence()
            assert di.is_configured() is True

    def test_polygon_to_bbox(self):
        """ポリゴン→バウンディングボックス変換"""
        di = AzureDocumentIntelligence()

        # 通常のポリゴン（8点）
        polygon = [0, 0, 10, 0, 10, 5, 0, 5]
        bbox = di._polygon_to_bbox(polygon)
        assert bbox == [0, 0, 10, 5]

        # 空のポリゴン
        bbox = di._polygon_to_bbox([])
        assert bbox == [0, 0, 0, 0]

        # 不十分な点
        bbox = di._polygon_to_bbox([1, 2])
        assert bbox == [0, 0, 0, 0]

    def test_extract_raises_without_config(self):
        """未設定時にextract_with_layoutがエラーを返す"""
        with patch.dict('os.environ', {}, clear=True):
            di = AzureDocumentIntelligence()
            with pytest.raises(ValueError, match="設定されていません"):
                di.extract_with_layout("test.pdf", "base64content")


# =============================================================================
# DocumentProcessor テスト
# =============================================================================

class TestDocumentProcessor:
    """DocumentProcessorクラスのテスト"""

    def test_supported_formats(self):
        """対応ファイル形式の確認"""
        assert ".txt" in DocumentProcessor.TEXT_TYPES
        assert ".csv" in DocumentProcessor.TEXT_TYPES
        assert ".pdf" in DocumentProcessor.PDF_TYPES
        assert ".xlsx" in DocumentProcessor.EXCEL_TYPES
        assert ".docx" in DocumentProcessor.WORD_TYPES
        assert ".png" in DocumentProcessor.IMAGE_TYPES
        assert ".jpg" in DocumentProcessor.IMAGE_TYPES

    def test_extract_text_from_text_file(self, sample_base64_text):
        """テキストファイルからの抽出"""
        result = DocumentProcessor.extract_text(
            file_name="test.txt",
            extension=".txt",
            base64_content=sample_base64_text,
            use_di=False
        )
        assert result.file_type == "text"
        assert result.extraction_method == "direct_decode"
        assert "テスト用のサンプルテキスト" in result.text_content
        assert result.error is None

    def test_extract_text_from_csv(self, sample_base64_csv):
        """CSVファイルからの抽出"""
        result = DocumentProcessor.extract_text(
            file_name="data.csv",
            extension=".csv",
            base64_content=sample_base64_csv,
            use_di=False
        )
        assert result.file_type == "text"
        assert "売上" in result.text_content
        assert "100000" in result.text_content

    def test_extract_text_from_shift_jis(self):
        """Shift-JISファイルからの抽出"""
        # Shift-JISでエンコードされたテキスト
        text = "日本語テキスト（Shift-JIS）"
        content = base64.b64encode(text.encode('shift-jis')).decode('utf-8')

        result = DocumentProcessor.extract_text(
            file_name="sjis.txt",
            extension=".txt",
            base64_content=content,
            use_di=False
        )
        assert "日本語テキスト" in result.text_content
        assert result.extraction_method == "direct_decode_shiftjis"

    def test_extract_text_unsupported_format(self):
        """未対応ファイル形式の処理"""
        content = base64.b64encode(b"dummy content").decode('utf-8')
        result = DocumentProcessor.extract_text(
            file_name="test.xyz",
            extension=".xyz",
            base64_content=content,
            use_di=False
        )
        assert "未対応" in result.text_content
        assert result.error is not None

    def test_extract_text_image_without_ocr(self):
        """OCRなしで画像ファイルを処理"""
        content = base64.b64encode(b"fake image data").decode('utf-8')

        with patch.object(DocumentProcessor, '_extract_with_ocr', return_value=None):
            result = DocumentProcessor.extract_text(
                file_name="screenshot.png",
                extension=".png",
                base64_content=content,
                use_di=True
            )
        assert "画像ファイル" in result.text_content
        assert result.file_type == "image"

    def test_extract_all(self, sample_evidence_files):
        """複数ファイル一括抽出"""
        from core.tasks.base_task import EvidenceFile

        evidence_objs = [EvidenceFile.from_dict(ef) for ef in sample_evidence_files]

        results = DocumentProcessor.extract_all(evidence_objs, use_di=False)

        assert len(results) == 2
        assert results[0].file_name == "テスト文書.txt"
        assert results[1].file_name == "売上データ.csv"

    def test_format_for_prompt(self):
        """プロンプト用フォーマット"""
        contents = [
            ExtractedContent(
                file_name="doc1.txt",
                file_type="text",
                text_content="内容1",
                extraction_method="direct_decode"
            ),
            ExtractedContent(
                file_name="doc2.pdf",
                file_type="pdf",
                text_content="内容2",
                extraction_method="pypdf",
                page_count=3
            )
        ]
        formatted = DocumentProcessor.format_for_prompt(contents)

        assert "【ファイル: doc1.txt】" in formatted
        assert "【ファイル: doc2.pdf】" in formatted
        assert "(3ページ)" in formatted
        assert "[抽出方法: pypdf]" in formatted

    def test_format_for_prompt_truncation(self):
        """長いテキストの切り詰め"""
        long_text = "あ" * 20000
        contents = [
            ExtractedContent(
                file_name="long.txt",
                file_type="text",
                text_content=long_text,
                extraction_method="direct_decode"
            )
        ]
        formatted = DocumentProcessor.format_for_prompt(contents, max_chars_per_file=1000)

        assert "以下省略" in formatted
        assert len(formatted) < len(long_text)

    def test_format_for_prompt_empty(self):
        """空のコンテンツリスト"""
        formatted = DocumentProcessor.format_for_prompt([])
        assert formatted == "エビデンスデータなし"

    def test_get_element_by_id(self):
        """要素ID検索"""
        elements = [
            TextElement("elem_0", "テキスト0", 1, [0, 0, 1, 1], "line"),
            TextElement("elem_1", "テキスト1", 1, [0, 1, 1, 2], "line"),
        ]
        contents = [
            ExtractedContent(
                file_name="doc.pdf",
                file_type="pdf",
                text_content="",
                extraction_method="ocr",
                elements=elements
            )
        ]

        # 存在する要素
        elem = DocumentProcessor.get_element_by_id(contents, "elem_1")
        assert elem is not None
        assert elem.text == "テキスト1"

        # 存在しない要素
        elem = DocumentProcessor.get_element_by_id(contents, "elem_999")
        assert elem is None

    def test_get_config_status(self):
        """設定状態取得"""
        with patch.dict('os.environ', {}, clear=True):
            status = DocumentProcessor.get_config_status()

            assert "ocr_provider" in status
            assert "supported_formats" in status
            assert "text" in status["supported_formats"]
            assert "pdf" in status["supported_formats"]

    @pytest.mark.integration
    def test_extract_from_pdf_with_text(self):
        """テキスト付きPDFの抽出（実際のpypdfを使用）"""
        # 実際のPDFがない場合はスキップ
        try:
            from pypdf import PdfReader
        except ImportError:
            pytest.skip("pypdf not installed")

        # 簡単なPDFコンテンツ（実際のPDFではないのでエラーになる可能性）
        content = base64.b64encode(b"%PDF-1.4 fake").decode('utf-8')
        result = DocumentProcessor._extract_from_pdf("test.pdf", content)

        # エラーでも結果は返る
        assert result.file_name == "test.pdf"
        assert result.file_type in ["pdf", "pdf_image"]

    @pytest.mark.integration
    def test_extract_from_excel(self):
        """Excelファイルの抽出（実際のopenpyxlを使用）"""
        try:
            from openpyxl import load_workbook
        except ImportError:
            pytest.skip("openpyxl not installed")

        # 無効なExcelデータ（エラーになる）
        content = base64.b64encode(b"fake excel").decode('utf-8')
        result = DocumentProcessor._extract_from_excel("test.xlsx", ".xlsx", content)

        # エラーでも結果は返る
        assert result.file_name == "test.xlsx"


# =============================================================================
# 統合テスト
# =============================================================================

class TestDocumentProcessorIntegration:
    """DocumentProcessorの統合テスト"""

    @pytest.mark.integration
    def test_real_text_extraction(self):
        """実際のテキスト抽出フロー"""
        # 日本語テキストを作成
        test_text = """
内部統制テスト評価報告書

1. 統制の概要
   本統制は、売上承認プロセスが適切に実施されていることを確認します。

2. テスト結果
   テスト期間中、全ての取引について承認印が確認されました。

3. 結論
   統制は有効に機能しています。
"""
        content = base64.b64encode(test_text.encode('utf-8')).decode('utf-8')

        result = DocumentProcessor.extract_text(
            file_name="報告書.txt",
            extension=".txt",
            base64_content=content,
            use_di=False
        )

        assert result.error is None
        assert "内部統制テスト評価報告書" in result.text_content
        assert "承認印" in result.text_content
        assert "有効" in result.text_content

    @pytest.mark.integration
    def test_multiple_file_types(self):
        """複数ファイルタイプの処理"""
        from core.tasks.base_task import EvidenceFile

        files = [
            EvidenceFile(
                file_name="text.txt",
                extension=".txt",
                mime_type="text/plain",
                base64_content=base64.b64encode(b"Text content").decode()
            ),
            EvidenceFile(
                file_name="data.csv",
                extension=".csv",
                mime_type="text/csv",
                base64_content=base64.b64encode(b"a,b,c\n1,2,3").decode()
            ),
        ]

        results = DocumentProcessor.extract_all(files, use_di=False)

        assert len(results) == 2
        assert all(r.error is None for r in results)
