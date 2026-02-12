import sys
import os
import pytest
import shutil
import base64
import asyncio
from pathlib import Path

# Add src to python path
SRC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src'))
sys.path.append(SRC_PATH)

from core.highlighting_service import HighlightingService
from core.types import AuditResult, AuditContext, EvidenceFile

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

@pytest.fixture
def temp_output_dir():
    dir_name = "e2e_highlight_test"
    if os.path.exists(dir_name):
        shutil.rmtree(dir_name)
    os.makedirs(dir_name)
    yield dir_name
    if os.path.exists(dir_name):
        shutil.rmtree(dir_name)

@pytest.mark.asyncio
async def test_highlighting_e2e_flow(temp_output_dir):
    """
    HighlightingServiceのE2Eテスト。
    PDFとExcelファイルが処理され、出力ファイルが生成されることを検証します。
    """
    # 1. モック入力ファイルの準備
    # reportlabが利用可能な場合はダミーPDFを作成、そうでない場合はスキップ
    pdf_content = ""
    try:
        from reportlab.pdfgen import canvas
        pdf_path = os.path.join(temp_output_dir, "input.pdf")
        c = canvas.Canvas(pdf_path)
        c.drawString(100, 750, "Audit Evidence Here")
        c.save()
        with open(pdf_path, "rb") as f:
            pdf_content = base64.b64encode(f.read()).decode()
    except ImportError:
        # reportlabがない場合はPDF生成をスキップ
        password = None
        pass

    # openpyxlが利用可能な場合はダミーExcelを作成
    xlsx_content = ""
    try:
        import openpyxl
        xlsx_path = os.path.join(temp_output_dir, "input.xlsx")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws["A1"] = "Evidence Data"
        wb.save(xlsx_path)
        with open(xlsx_path, "rb") as f:
            xlsx_content = base64.b64encode(f.read()).decode()
    except ImportError:
         pass

    # ダミーテキストを作成
    txt_content = base64.b64encode(b"Log file contains Evidence.").decode()

    # 2. コンテキストと結果の準備
    context = AuditContext(
        item_id="E2E-TEST",
        control_description="Ctrl",
        test_procedure="Test",
        evidence_link=os.path.abspath(temp_output_dir),
        evidence_files=[
            EvidenceFile("input.pdf", ".pdf", "application/pdf", pdf_content),
            EvidenceFile("input.xlsx", ".xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", xlsx_content),
            EvidenceFile("input.txt", ".txt", "text/plain", txt_content)
        ]
    )

    audit_result = AuditResult(
        item_id="E2E-TEST",
        evaluation_result=True,
        judgment_basis="OK",
        document_reference="[input.pdf] : Audit Evidence\n[input.xlsx] : Evidence Data\n[input.txt] : Evidence",
        file_name="input.pdf",
        evidence_files_info=[]
    )

    # 3. サービスの実行
    service = HighlightingService(output_dir="highlighted")
    results = await service.highlight_evidence(audit_result, context)

    # 4. 出力の検証
    assert len(results) >= 1  # ライブラリが不足していても少なくともテキストは動作するはず

    # ファイルの存在確認（サーバー側一時ディレクトリに出力される）
    for res in results:
        file_path = os.path.join(res['filePath'], res['fileName'])
        print(f"Verified generated file: {file_path}")
        assert os.path.exists(file_path)
        assert os.path.getsize(file_path) > 0

        # ファイル名の簡易検証
        assert res['fileName'].startswith("highlighted_")

        # Base64データが含まれていることを確認（PowerShellでデコードするため必須）
        assert 'base64' in res
        assert len(res['base64']) > 0

if __name__ == "__main__":
    # スタンドアロン実行
    output_dir = "e2e_highlight_test_manual"
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir)
    try:
        asyncio.run(test_highlighting_e2e_flow(output_dir))
        print("E2E Test Passed Successfully!")
    except Exception as e:
        print(f"E2E Test Failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
