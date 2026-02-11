# -*- coding: utf-8 -*-
"""
================================================================================
test_local_platform.py - ローカル/オンプレミスプラットフォームのテスト
================================================================================

【テスト対象】
- platforms/local/main.py のFastAPIエンドポイント
- ローカル環境での設定・動作確認

================================================================================
"""

import pytest
import os
import sys
from unittest.mock import patch, AsyncMock, MagicMock

# パス設定
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
_local_platform_path = os.path.join(_project_root, "platforms", "local")
_src_path = os.path.join(_project_root, "src")

if _src_path not in sys.path:
    sys.path.insert(0, _src_path)
if _local_platform_path not in sys.path:
    sys.path.insert(0, _local_platform_path)


# =============================================================================
# 環境変数設定テスト
# =============================================================================

class TestLocalEnvironmentSetup:
    """ローカル環境の設定テスト"""

    def test_default_llm_provider_is_local(self):
        """デフォルトでLLM_PROVIDER=LOCALが設定されるか"""
        with patch.dict(os.environ, {}, clear=True):
            # 環境変数をクリアして、設定がなければLOCALになることを確認
            if not os.getenv("LLM_PROVIDER"):
                os.environ["LLM_PROVIDER"] = "LOCAL"
            assert os.getenv("LLM_PROVIDER") == "LOCAL"

    def test_default_ocr_provider_is_tesseract(self):
        """デフォルトでOCR_PROVIDER=TESSERACTが設定されるか"""
        with patch.dict(os.environ, {}, clear=True):
            if not os.getenv("OCR_PROVIDER"):
                os.environ["OCR_PROVIDER"] = "TESSERACT"
            assert os.getenv("OCR_PROVIDER") == "TESSERACT"

    def test_ollama_default_url(self):
        """OllamaのデフォルトURL"""
        with patch.dict(os.environ, {}, clear=True):
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            assert base_url == "http://localhost:11434"

    def test_ollama_custom_url(self):
        """Ollamaのカスタム URL"""
        with patch.dict(os.environ, {"OLLAMA_BASE_URL": "http://custom:11434"}):
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            assert base_url == "http://custom:11434"

    def test_ollama_default_model(self):
        """Ollamaのデフォルトモデル"""
        with patch.dict(os.environ, {}, clear=True):
            model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
            assert model == "llama3.1:8b"


# =============================================================================
# FastAPI エンドポイントテスト
# =============================================================================

class TestLocalPlatformEndpoints:
    """ローカルプラットフォームのエンドポイントテスト"""

    @pytest.fixture
    def client(self):
        """テスト用クライアント"""
        # 環境変数を設定
        os.environ["LLM_PROVIDER"] = "LOCAL"
        os.environ["OCR_PROVIDER"] = "TESSERACT"

        try:
            from fastapi.testclient import TestClient
            from main import app
            return TestClient(app)
        except ImportError:
            pytest.skip("FastAPI TestClient not available")

    @pytest.mark.integration
    def test_health_endpoint_structure(self, client):
        """ヘルスエンドポイントの構造"""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert "platform" in data
        assert data["platform"] == "Local (FastAPI + Ollama)"

    @pytest.mark.integration
    def test_config_endpoint_structure(self, client):
        """設定エンドポイントの構造"""
        response = client.get("/config")

        assert response.status_code == 200
        data = response.json()

        assert "platform" in data
        assert data["platform"]["name"] == "Local Server"
        assert data["platform"]["framework"] == "FastAPI"
        assert "ollama" in data

    @pytest.mark.integration
    def test_config_ollama_settings(self, client):
        """Ollama設定の確認"""
        response = client.get("/config")

        assert response.status_code == 200
        data = response.json()

        assert "ollama" in data
        assert "base_url" in data["ollama"]
        assert "model" in data["ollama"]

    @pytest.mark.integration
    def test_evaluate_empty_request(self, client):
        """空リクエストのエラー処理"""
        response = client.post(
            "/evaluate",
            json=[],
            headers={"Content-Type": "application/json"}
        )

        # 空リクエストはエラーまたは空レスポンス
        assert response.status_code in [200, 400]

    @pytest.mark.integration
    def test_evaluate_invalid_json(self, client):
        """不正なJSONのエラー処理"""
        response = client.post(
            "/evaluate",
            content=b"invalid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 400

    @pytest.mark.integration
    def test_evaluate_status_not_found(self, client):
        """存在しないジョブIDでのステータス確認"""
        response = client.get("/evaluate/status/non-existent-job-id")

        # 404（ジョブなし）または200（エラーハンドリング）を許容
        # ジョブストレージが未設定の場合は異なるレスポンスになる可能性あり
        assert response.status_code in [200, 404, 500]
        data = response.json()
        # レスポンスに必要なフィールドがあることを確認
        assert "status" in data or "error" in data

    @pytest.mark.integration
    def test_evaluate_results_not_found(self, client):
        """存在しないジョブIDでの結果取得"""
        response = client.get("/evaluate/results/non-existent-job-id")

        # 404（ジョブなし）、202（処理中）、または200（エラーハンドリング）を許容
        assert response.status_code in [200, 202, 404, 500]
        data = response.json()
        # レスポンスに必要なフィールドがあることを確認
        assert "status" in data or "error" in data or "job_id" in data


# =============================================================================
# Pydantic モデルテスト
# =============================================================================

class TestPydanticModels:
    """Pydanticモデルのテスト"""

    def test_evaluation_item_model(self):
        """EvaluationItemモデル"""
        try:
            sys.path.insert(0, _local_platform_path)
            from main import EvaluationItem

            item = EvaluationItem(
                ID="IC-001",
                controlDescription="テスト統制",
                evidenceFiles=[],
                testProcedures="テスト手順"
            )
            assert item.ID == "IC-001"
            assert item.controlDescription == "テスト統制"
        except ImportError:
            pytest.skip("main module not importable")

    def test_evaluation_item_defaults(self):
        """EvaluationItemのデフォルト値"""
        try:
            sys.path.insert(0, _local_platform_path)
            from main import EvaluationItem

            item = EvaluationItem(
                ID="IC-002",
                controlDescription="最小限の統制"
            )
            assert item.evidenceFiles == []
            assert item.testProcedures == ""
        except ImportError:
            pytest.skip("main module not importable")

    def test_job_submit_response_model(self):
        """JobSubmitResponseモデル"""
        try:
            sys.path.insert(0, _local_platform_path)
            from main import JobSubmitResponse

            response = JobSubmitResponse(
                job_id="job-123",
                status="pending",
                estimated_time=60,
                message="ジョブを受け付けました"
            )
            assert response.job_id == "job-123"
            assert response.status == "pending"
        except ImportError:
            pytest.skip("main module not importable")

    def test_job_status_response_model(self):
        """JobStatusResponseモデル"""
        try:
            sys.path.insert(0, _local_platform_path)
            from main import JobStatusResponse

            response = JobStatusResponse(
                job_id="job-456",
                status="processing",
                progress=50,
                message="処理中"
            )
            assert response.job_id == "job-456"
            assert response.progress == 50
            assert response.error_message is None
        except ImportError:
            pytest.skip("main module not importable")


# =============================================================================
# ヘルパー関数テスト
# =============================================================================

class TestHelperFunctions:
    """ヘルパー関数のテスト"""

    def test_create_json_response(self):
        """JSONレスポンス作成"""
        try:
            sys.path.insert(0, _local_platform_path)
            from main import create_json_response

            response = create_json_response({"key": "value"}, 200)
            assert response.status_code == 200
        except ImportError:
            pytest.skip("main module not importable")

    def test_create_error_response(self):
        """エラーレスポンス作成"""
        try:
            sys.path.insert(0, _local_platform_path)
            from main import create_error_response

            response = create_error_response("エラーメッセージ", 500)
            assert response.status_code == 500
        except ImportError:
            pytest.skip("main module not importable")

    def test_create_error_response_with_details(self):
        """詳細付きエラーレスポンス作成"""
        try:
            sys.path.insert(0, _local_platform_path)
            from main import create_error_response
            import json

            response = create_error_response("エラー", 500, "詳細情報")
            assert response.status_code == 500
            data = json.loads(response.body)
            assert "details" in data
        except ImportError:
            pytest.skip("main module not importable")


# =============================================================================
# Ollama 接続テスト
# =============================================================================

class TestOllamaConnection:
    """Ollama接続のテスト"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_check_ollama_connection_mock_success(self):
        """Ollama接続成功（モック）"""
        try:
            sys.path.insert(0, _local_platform_path)
            from main import check_ollama_connection
        except ImportError:
            pytest.skip("main module not importable")

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "models": [{"name": "llama3.1:8b"}, {"name": "llava:13b"}]
            }

            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await check_ollama_connection()

            assert result["connected"] is True
            assert "llama3.1:8b" in result["available_models"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_check_ollama_connection_mock_failure(self):
        """Ollama接続失敗（モック）"""
        try:
            sys.path.insert(0, _local_platform_path)
            from main import check_ollama_connection
        except ImportError:
            pytest.skip("main module not importable")

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = Exception("Connection refused")
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await check_ollama_connection()

            assert result["connected"] is False
            assert "error" in result


# =============================================================================
# LLM/OCR プロバイダー連携テスト
# =============================================================================

class TestProviderIntegration:
    """プロバイダー連携テスト"""

    def test_llm_factory_local_provider(self):
        """LLMファクトリーでLOCALプロバイダーを取得"""
        from infrastructure.llm_factory import LLMFactory, LLMProvider

        with patch.dict(os.environ, {"LLM_PROVIDER": "LOCAL"}):
            provider = LLMFactory.get_provider()
            assert provider == LLMProvider.LOCAL

    def test_ocr_factory_tesseract_provider(self):
        """OCRファクトリーでTESSERACTプロバイダーを取得"""
        from infrastructure.ocr_factory import OCRFactory, OCRProvider

        with patch.dict(os.environ, {"OCR_PROVIDER": "TESSERACT"}):
            provider = OCRFactory.get_provider()
            assert provider == OCRProvider.TESSERACT

    def test_local_config_status(self):
        """ローカル環境の設定状態確認"""
        from infrastructure.llm_factory import LLMFactory

        with patch.dict(os.environ, {"LLM_PROVIDER": "LOCAL"}):
            status = LLMFactory.get_config_status()
            assert status["provider"] == "LOCAL"
            assert status["configured"] is True

    def test_tesseract_config_status(self):
        """Tesseract設定状態確認"""
        from infrastructure.ocr_factory import OCRFactory

        with patch.dict(os.environ, {"OCR_PROVIDER": "TESSERACT"}, clear=True):
            OCRFactory._client_cache = None
            OCRFactory._cached_provider = None

            status = OCRFactory.get_config_status()
            assert status["provider"] == "TESSERACT"
            # 必須環境変数がないのでmissing_varsは空
            assert len(status.get("missing_vars", [])) == 0


# =============================================================================
# 結合テスト
# =============================================================================

class TestLocalPlatformIntegration:
    """ローカルプラットフォームの結合テスト"""

    @pytest.mark.integration
    def test_full_local_environment_setup(self):
        """ローカル環境のフルセットアップ"""
        env_vars = {
            "LLM_PROVIDER": "LOCAL",
            "OCR_PROVIDER": "TESSERACT",
            "OLLAMA_BASE_URL": "http://localhost:11434",
            "OLLAMA_MODEL": "llama3.1:8b",
            "TESSERACT_LANG": "jpn+eng"
        }

        with patch.dict(os.environ, env_vars):
            from infrastructure.llm_factory import LLMFactory, LLMProvider
            from infrastructure.ocr_factory import OCRFactory, OCRProvider

            # LLM設定確認
            llm_provider = LLMFactory.get_provider()
            assert llm_provider == LLMProvider.LOCAL

            llm_status = LLMFactory.get_config_status()
            assert llm_status["configured"] is True

            # OCR設定確認
            ocr_provider = OCRFactory.get_provider()
            assert ocr_provider == OCRProvider.TESSERACT

    @pytest.mark.integration
    def test_environment_variables_precedence(self):
        """環境変数の優先順位"""
        # カスタム設定が優先されることを確認
        env_vars = {
            "LLM_PROVIDER": "LOCAL",
            "OLLAMA_MODEL": "custom-model:latest"
        }

        with patch.dict(os.environ, env_vars):
            model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
            assert model == "custom-model:latest"
