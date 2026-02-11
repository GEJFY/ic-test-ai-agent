# -*- coding: utf-8 -*-
"""
================================================================================
conftest.py - pytest共通フィクスチャ
================================================================================

【概要】
全テストで共有するフィクスチャとモックを定義します。

【フィクスチャ一覧】
- sample_evidence_file: サンプル証跡ファイル
- sample_audit_context: サンプル監査コンテキスト
- mock_llm: LLMモック
- mock_ocr_client: OCRクライアントモック

================================================================================
"""

import pytest
import base64
import json
import os
import sys
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from typing import Dict, Any, List

# srcディレクトリをパスに追加
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_src_path = os.path.join(_project_root, "src")
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

# .envファイルを読み込み（統合テスト用）
from dotenv import load_dotenv
_env_path = os.path.join(_project_root, ".env")
if os.path.exists(_env_path):
    load_dotenv(_env_path)


# =============================================================================
# 基本データフィクスチャ
# =============================================================================

@pytest.fixture
def sample_base64_text():
    """サンプルテキストのBase64エンコード"""
    text = "これはテスト用のサンプルテキストです。\n内部統制テスト評価に使用されます。"
    return base64.b64encode(text.encode('utf-8')).decode('utf-8')


@pytest.fixture
def sample_base64_csv():
    """サンプルCSVのBase64エンコード"""
    csv_content = "日付,項目,金額\n2025-01-01,売上,100000\n2025-01-02,経費,50000"
    return base64.b64encode(csv_content.encode('utf-8')).decode('utf-8')


@pytest.fixture
def sample_evidence_dict(sample_base64_text):
    """サンプル証跡ファイル辞書"""
    return {
        "fileName": "test_document.txt",
        "extension": ".txt",
        "mimeType": "text/plain",
        "base64": sample_base64_text
    }


@pytest.fixture
def sample_evidence_files(sample_base64_text, sample_base64_csv):
    """複数のサンプル証跡ファイル"""
    return [
        {
            "fileName": "テスト文書.txt",
            "extension": ".txt",
            "mimeType": "text/plain",
            "base64": sample_base64_text
        },
        {
            "fileName": "売上データ.csv",
            "extension": ".csv",
            "mimeType": "text/csv",
            "base64": sample_base64_csv
        }
    ]


@pytest.fixture
def sample_request_item(sample_evidence_files):
    """サンプルAPIリクエストアイテム"""
    return {
        "ID": "CLC-01",
        "ControlDescription": "月次で売上の承認プロセスが実施されている",
        "TestProcedure": "売上報告書に承認者の署名があることを確認する",
        "EvidenceLink": "\\\\server\\evidence\\CLC-01\\",
        "EvidenceFiles": sample_evidence_files
    }


@pytest.fixture
def sample_api_request(sample_request_item):
    """サンプルAPIリクエスト全体"""
    return {
        "items": [sample_request_item],
        "options": {
            "maxConcurrentEvaluations": 3,
            "timeoutSeconds": 300
        }
    }


# =============================================================================
# Core モジュールフィクスチャ
# =============================================================================

@pytest.fixture
def sample_evidence_file():
    """EvidenceFileオブジェクト"""
    from core.tasks.base_task import EvidenceFile
    return EvidenceFile(
        file_name="test_report.pdf",
        extension=".pdf",
        mime_type="application/pdf",
        base64_content=base64.b64encode(b"dummy pdf content").decode('utf-8')
    )


@pytest.fixture
def sample_audit_context(sample_evidence_file):
    """AuditContextオブジェクト"""
    from core.tasks.base_task import AuditContext
    return AuditContext(
        item_id="CLC-01",
        control_description="月次で売上の承認プロセスが実施されている",
        test_procedure="売上報告書に承認者の署名があることを確認する",
        evidence_link="\\\\server\\evidence\\CLC-01\\",
        evidence_files=[sample_evidence_file]
    )


@pytest.fixture
def sample_task_result():
    """TaskResultオブジェクト"""
    from core.tasks.base_task import TaskResult, TaskType
    return TaskResult(
        task_type=TaskType.A1_SEMANTIC_SEARCH,
        task_name="意味検索",
        success=True,
        result={"matches": ["承認済み", "署名あり"]},
        reasoning="関連する記述を証跡から発見しました",
        confidence=0.85,
        evidence_references=["test_report.pdf"]
    )


# =============================================================================
# LLM モックフィクスチャ
# =============================================================================

@pytest.fixture
def mock_llm_response():
    """LLM応答のモック"""
    mock_response = Mock()
    mock_response.content = json.dumps({
        "evaluation": True,
        "reasoning": "テスト手続きに基づき、統制が有効に機能していることを確認しました。",
        "confidence": 0.9
    })
    return mock_response


@pytest.fixture
def mock_llm(mock_llm_response):
    """LLMクライアントモック"""
    mock = Mock()
    mock.invoke = Mock(return_value=mock_llm_response)
    mock.ainvoke = AsyncMock(return_value=mock_llm_response)
    return mock


@pytest.fixture
def mock_chat_model(mock_llm_response):
    """ChatModelモック（LangChain形式）"""
    mock = MagicMock()
    mock.invoke.return_value = mock_llm_response
    mock.__or__ = Mock(return_value=mock)
    return mock


# =============================================================================
# OCR モックフィクスチャ
# =============================================================================

@pytest.fixture
def mock_ocr_result():
    """OCR抽出結果モック"""
    return {
        "text_content": "これはOCRで抽出されたテキストです。\n承認日: 2025年1月15日\n承認者: 山田太郎",
        "page_count": 1,
        "elements": [],
        "tables": [],
        "error": None
    }


@pytest.fixture
def mock_ocr_client(mock_ocr_result):
    """OCRクライアントモック"""
    mock = Mock()
    mock.is_configured.return_value = True
    mock.provider_name = "MockOCR"
    mock.extract_text.return_value = Mock(**mock_ocr_result)
    return mock


# =============================================================================
# Storage モックフィクスチャ
# =============================================================================

@pytest.fixture
def mock_job_storage():
    """ジョブストレージモック"""
    mock = Mock()
    mock.save_job = AsyncMock(return_value=True)
    mock.get_job = AsyncMock(return_value={
        "job_id": "test-job-123",
        "status": "running",
        "progress": 50,
        "total_items": 10,
        "results": []
    })
    mock.update_job = AsyncMock(return_value=True)
    mock.delete_job = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_job_queue():
    """ジョブキューモック"""
    mock = Mock()
    mock.enqueue = AsyncMock(return_value=None)
    mock.dequeue = AsyncMock(return_value="test-job-123")
    mock.get_queue_length = AsyncMock(return_value=5)
    return mock


# =============================================================================
# 環境変数モック
# =============================================================================

@pytest.fixture
def mock_azure_env():
    """Azure環境変数モック"""
    env_vars = {
        "LLM_PROVIDER": "AZURE_FOUNDRY",
        "AZURE_FOUNDRY_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_FOUNDRY_MODEL": "gpt-4o-mini",
        "AZURE_FOUNDRY_API_KEY": "test-api-key",
        "AZURE_FOUNDRY_API_VERSION": "2024-02-01",
        "OCR_PROVIDER": "AZURE",
        "AZURE_DI_ENDPOINT": "https://test.cognitiveservices.azure.com/",
        "AZURE_DI_KEY": "test-di-key",
        "AZURE_STORAGE_CONNECTION_STRING": "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test;EndpointSuffix=core.windows.net"
    }
    with patch.dict(os.environ, env_vars, clear=False):
        yield env_vars


@pytest.fixture
def mock_no_env():
    """環境変数なしモック"""
    env_vars_to_remove = [
        "LLM_PROVIDER", "AZURE_FOUNDRY_ENDPOINT", "AZURE_FOUNDRY_MODEL",
        "OCR_PROVIDER", "AZURE_DI_ENDPOINT", "AZURE_DI_KEY",
        "AZURE_STORAGE_CONNECTION_STRING"
    ]
    with patch.dict(os.environ, {}, clear=False):
        for var in env_vars_to_remove:
            os.environ.pop(var, None)
        yield


# =============================================================================
# ヘルパー関数
# =============================================================================

def create_mock_graph_state(item_id: str = "CLC-01") -> Dict[str, Any]:
    """GraphOrchestratorの状態モック"""
    return {
        "item_id": item_id,
        "control_description": "テスト統制記述",
        "test_procedure": "テスト手続き",
        "evidence_files": [],
        "extracted_texts": [],
        "task_plan": [],
        "task_results": [],
        "evaluation_result": None,
        "judgment_basis": "",
        "document_reference": "",
        "error": None,
        "iteration_count": 0,
        "max_iterations": 3
    }


@pytest.fixture
def mock_graph_state():
    """GraphOrchestrator状態フィクスチャ"""
    return create_mock_graph_state()


# =============================================================================
# 統合テストスキップ設定
# =============================================================================

def pytest_addoption(parser):
    """pytestコマンドラインオプション追加"""
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Run integration tests (requires cloud access)"
    )


def pytest_collection_modifyitems(config, items):
    """統合テストマーカーを処理"""
    if config.getoption("--integration"):
        return

    skip_integration = pytest.mark.skip(reason="need --integration option to run")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
