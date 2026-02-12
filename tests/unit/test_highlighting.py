import pytest
import os
import sys
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path

# srcをパスに追加してcoreモジュールをインポートできるようにする
sys.path.append(os.path.join(os.path.dirname(__file__), '../../src'))

from core.highlighting_service import HighlightingService, Stem
from core.types import AuditResult, AuditContext, EvidenceFile

class TestHighlightingService:

    @pytest.fixture
    def service(self):
        return HighlightingService(output_dir="test_highlighted")

    @pytest.fixture
    def mock_audit_result(self):
        return AuditResult(
            item_id="TEST-01",
            evaluation_result=True,
            judgment_basis="Valid",
            document_reference="[report.pdf] Page 1：Approved by Manager\n[data.xlsx] Sheet1：Sales 2024",
            file_name="report.pdf",
            evidence_files_info=[]
        )

    @pytest.fixture
    def mock_context(self):
        return AuditContext(
            item_id="TEST-01",
            control_description="Test Control",
            test_procedure="Test Procedure",
            evidence_link="/tmp/evidence",
            evidence_files=[
                EvidenceFile(
                    file_name="report.pdf",
                    extension=".pdf",
                    mime_type="application/pdf",
                    base64_content="ZHVtbXk=" # dummy
                ),
                EvidenceFile(
                    file_name="data.xlsx",
                    extension=".xlsx",
                    mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    base64_content="ZHVtbXk="
                )
            ]
        )

    def test_parse_quotes(self, service):
        doc_ref = """
        [report.pdf] Page 1：Approved by Manager
        [data.xlsx] Row 5：Sales 2024
        [image.png] : Visual evidence
        """
        quotes = service._parse_quotes(doc_ref)

        assert "report.pdf" in quotes
        assert "Approved by Manager" in quotes["report.pdf"]
        assert "data.xlsx" in quotes
        assert "Sales 2024" in quotes["data.xlsx"]
        assert "image.png" in quotes
        assert "Visual evidence" in quotes["image.png"]

    @patch('core.highlighting_service.fitz')
    def test_highlight_pdf(self, mock_fitz, service):
        # モックの設定
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_fitz.open.return_value = mock_doc
        mock_doc.__iter__.return_value = [mock_page]

        # get_text()が文字列を返すように設定（_normalize_textが正常動作するために必要）
        mock_page.get_text.return_value = "This is Evidence text on the page"

        # "Evidence" に対する検索結果を返すようにモック
        mock_page.search_for.return_value = ["quad1"]

        # 実行
        result = service._highlight_pdf("input.pdf", ["Evidence"], "output.pdf")

        # 検証
        assert result is True
        mock_fitz.open.assert_called_with("input.pdf")
        mock_page.search_for.assert_called_with("Evidence")
        mock_page.add_highlight_annot.assert_called()
        mock_doc.save.assert_called_with("output.pdf")

    @patch('core.highlighting_service.openpyxl')
    def test_highlight_excel(self, mock_openpyxl, service):
        # モックの設定
        mock_wb = MagicMock()
        mock_ws = MagicMock()
        mock_cell = MagicMock()

        mock_openpyxl.load_workbook.return_value = mock_wb
        mock_wb.worksheets = [mock_ws]
        mock_ws.iter_rows.return_value = [[mock_cell]]

        mock_cell.value = "This contains Evidence data"

        # 実行
        result = service._highlight_excel("input.xlsx", ["Evidence"], "output.xlsx")

        # 検証
        assert result is True
        mock_openpyxl.load_workbook.assert_called_with("input.xlsx")
        assert mock_cell.fill is not None # スタイルが適用されたか
        mock_wb.save.assert_called_with("output.xlsx")

    @patch('core.highlighting_service.black', MagicMock())
    @patch('core.highlighting_service.yellow', MagicMock())
    @patch('core.highlighting_service.A4', (595.27, 841.89))
    @patch('core.highlighting_service.canvas')
    def test_generate_highlighted_pdf(self, mock_canvas, service):
        # モックの設定
        mock_c = MagicMock()
        mock_canvas.Canvas.return_value = mock_c

        # 実行
        result = service._generate_highlighted_pdf_from_text(
            "This is a text file content.\nIt contains key Evidence.",
            ["Evidence"],
            "output.pdf",
            "original.txt"
        )

        # 検証
        assert result is True
        from unittest.mock import ANY
        mock_canvas.Canvas.assert_called_with("output.pdf", pagesize=ANY)
        mock_c.setFillColor.assert_any_call(ANY)
        mock_c.rect.assert_called()
        mock_c.save.assert_called()

    def test_parse_quotes_multiline(self, service):
        """複数行形式の引用が正しく解析されることを確認（Bug A修正テスト）"""
        doc_ref = "[report.pdf] Page 5：\n承認者による承認があったことを確認した。\n研修は全社員を対象に実施された。"
        quotes = service._parse_quotes(doc_ref)

        assert "report.pdf" in quotes
        assert len(quotes["report.pdf"]) == 2
        assert "承認者による承認があったことを確認した。" in quotes["report.pdf"]
        assert "研修は全社員を対象に実施された。" in quotes["report.pdf"]

    def test_parse_quotes_multiline_no_content_after_colon(self, service):
        """コロンの後に内容がない場合でもdict keyが初期化されることを確認"""
        doc_ref = "[data.xlsx] シート1：\n売上データ 2024年度"
        quotes = service._parse_quotes(doc_ref)

        assert "data.xlsx" in quotes
        assert "売上データ 2024年度" in quotes["data.xlsx"]

    def test_parse_quotes_multiple_files(self, service):
        """複数ファイルの複数行引用"""
        doc_ref = (
            "[file1.pdf] Page 1：\n"
            "First quote text\n"
            "\n"
            "[file2.xlsx] Sheet1：\n"
            "Second quote text\n"
            "Continuation of second"
        )
        quotes = service._parse_quotes(doc_ref)

        assert "file1.pdf" in quotes
        assert "First quote text" in quotes["file1.pdf"]
        assert "file2.xlsx" in quotes
        assert "Second quote text" in quotes["file2.xlsx"]
        assert "Continuation of second" in quotes["file2.xlsx"]

    def test_split_quote_segments(self, service):
        """長い引用のセグメント分割テスト"""
        short = "短い引用"
        assert service._split_quote_segments(short) == [short]

        long_quote = "これは非常に長い引用文です。句読点を含むテキストが、適切に分割されることを確認します。"
        segments = service._split_quote_segments(long_quote, max_len=20)
        assert len(segments) > 1
        for seg in segments:
            assert len(seg) >= 3

    @patch('core.highlighting_service.fitz')
    def test_highlight_pdf_segment_search(self, mock_fitz, service):
        """長い引用がセグメント分割で検索されることを確認"""
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_fitz.open.return_value = mock_doc
        mock_doc.__iter__.return_value = [mock_page]

        # ページテキストに長い引用が含まれる
        long_text = "この文書は承認済みであり、コンプライアンス研修を全社員対象に実施した記録です。"
        mock_page.get_text.return_value = long_text

        # 全体検索は失敗、セグメント検索は成功する設定
        def search_side_effect(text):
            if len(text) > 30:
                return []  # 長い検索は失敗
            if text in long_text:
                return ["quad1"]
            return []

        mock_page.search_for.side_effect = search_side_effect

        result = service._highlight_pdf("input.pdf", [long_text], "output.pdf")
        assert result is True
        mock_page.add_highlight_annot.assert_called()

    def test_parse_quotes_format_from_format_document_quotes(self, service):
        """_format_document_quotesの出力形式が_parse_quotesで正しく解析されることを確認"""
        # _format_document_quotesが生成する実際の形式
        doc_ref = (
            "[承認報告書.pdf] Page 2：\n"
            "取締役会において承認決議がなされた\n"
            "\n"
            "[売上データ.xlsx] Sheet1：\n"
            "2024年度第4四半期 売上合計: 150,000,000円"
        )
        quotes = service._parse_quotes(doc_ref)

        assert "承認報告書.pdf" in quotes
        assert "取締役会において承認決議がなされた" in quotes["承認報告書.pdf"]
        assert "売上データ.xlsx" in quotes
        assert "2024年度第4四半期 売上合計: 150,000,000円" in quotes["売上データ.xlsx"]

    def test_parse_quotes_location_only_no_colon_after(self, service):
        """ロケーション情報のみでコロン後に内容がない場合"""
        doc_ref = "[report.pdf]：\n重要事項が記載されている箇所"
        quotes = service._parse_quotes(doc_ref)

        assert "report.pdf" in quotes
        assert "重要事項が記載されている箇所" in quotes["report.pdf"]

    def test_stem(self):
        assert Stem("file.pdf") == "file"
        assert Stem("archive.tar.gz") == "archive.tar"
        assert Stem("document") == "document"
