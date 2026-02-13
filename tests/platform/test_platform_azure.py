# -*- coding: utf-8 -*-
"""
================================================================================
test_platform_azure.py - Azure Container Apps エントリポイントのユニットテスト
================================================================================

【テスト対象】
- platforms/local/main.py のFastAPI/Uvicornエンドポイント（Azure Container Apps用Dockerイメージ）

================================================================================
"""

import pytest
import json
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock

_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_local_dir = os.path.join(_project_root, "platforms", "local")


def _import_fastapi_app():
    """FastAPIアプリ（Docker共通イメージ）をインポート"""
    if _local_dir not in sys.path:
        sys.path.insert(0, _local_dir)
    if "main" in sys.modules:
        del sys.modules["main"]

    import main
    return main


def _get_test_client():
    """FastAPI TestClientを取得"""
    from fastapi.testclient import TestClient
    app_module = _import_fastapi_app()
    return TestClient(app_module.app)


# =============================================================================
# health エンドポイント
# =============================================================================

class TestAzureHealth:
    """Azure Container Apps health 関数のテスト"""

    def test_health(self):
        """GET /health"""
        client = _get_test_client()

        with patch("core.handlers.handle_health", return_value={"status": "healthy"}), \
             patch("core.handlers.create_json_response", return_value={
                 "body": json.dumps({"status": "healthy", "platform": "Azure Container Apps"}),
                 "content_type": "application/json; charset=utf-8",
                 "status_code": 200
             }):
            response = client.get("/health")
            assert response.status_code == 200


# =============================================================================
# config エンドポイント
# =============================================================================

class TestAzureConfig:
    """Azure Container Apps config_status 関数のテスト"""

    def test_config(self):
        """GET /config"""
        client = _get_test_client()

        with patch("core.handlers.handle_config", return_value={"llm": "ok"}), \
             patch("core.handlers.create_json_response", return_value={
                 "body": json.dumps({"llm": "ok"}),
                 "content_type": "application/json; charset=utf-8",
                 "status_code": 200
             }):
            response = client.get("/config")
            assert response.status_code == 200


# =============================================================================
# evaluate エンドポイント
# =============================================================================

class TestAzureEvaluate:
    """Azure Container Apps evaluate 関数のテスト"""

    @pytest.mark.asyncio
    async def test_evaluate_success(self):
        """POST /evaluate 正常系"""
        client = _get_test_client()

        with patch("core.handlers.parse_request_body", return_value=([{"ID": "CLC-01"}], None)), \
             patch("core.handlers.handle_evaluate", new_callable=AsyncMock,
                   return_value=[{"ID": "CLC-01", "evaluationResult": True}]), \
             patch("core.handlers.create_json_response", return_value={
                 "body": json.dumps([{"ID": "CLC-01", "evaluationResult": True}]),
                 "content_type": "application/json; charset=utf-8",
                 "status_code": 200
             }):
            response = client.post(
                "/evaluate",
                json={"items": [{"ID": "CLC-01"}]},
                headers={"Content-Type": "application/json"}
            )
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_evaluate_parse_error(self):
        """リクエスト解析エラー"""
        client = _get_test_client()

        with patch("core.handlers.parse_request_body", return_value=(None, "Invalid JSON")), \
             patch("core.handlers.create_error_response", return_value={
                 "body": json.dumps({"error": True, "message": "Invalid JSON"}),
                 "content_type": "application/json; charset=utf-8",
                 "status_code": 400
             }):
            response = client.post(
                "/evaluate",
                content=b"invalid",
                headers={"Content-Type": "application/json"}
            )
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_evaluate_exception(self):
        """予期せぬ例外"""
        client = _get_test_client()

        with patch("core.handlers.parse_request_body", side_effect=Exception("Unexpected")), \
             patch("core.handlers.create_error_response", return_value={
                 "body": json.dumps({"error": True}),
                 "content_type": "application/json; charset=utf-8",
                 "status_code": 500
             }):
            response = client.post(
                "/evaluate",
                content=b"{}",
                headers={"Content-Type": "application/json"}
            )
            assert response.status_code == 500


# =============================================================================
# evaluate/submit エンドポイント
# =============================================================================

class TestAzureEvaluateSubmit:
    """Azure Container Apps evaluate_submit 関数のテスト"""

    @pytest.mark.asyncio
    async def test_submit_success(self):
        """POST /evaluate/submit 正常系"""
        client = _get_test_client()

        with patch("core.handlers.parse_request_body", return_value=([{"ID": "CLC-01"}], None)), \
             patch("core.async_handlers.handle_submit", new_callable=AsyncMock, return_value={
                 "job_id": "job-123", "status": "pending", "estimated_time": 60
             }), \
             patch("core.handlers.create_json_response", return_value={
                 "body": json.dumps({"job_id": "job-123"}),
                 "content_type": "application/json; charset=utf-8",
                 "status_code": 200
             }):
            response = client.post(
                "/evaluate/submit",
                json={"items": [{"ID": "CLC-01"}]},
                headers={"Content-Type": "application/json", "X-Tenant-ID": "tenant-a"}
            )
            assert response.status_code == 202

    @pytest.mark.asyncio
    async def test_submit_error_response(self):
        """ジョブ送信エラー"""
        client = _get_test_client()

        with patch("core.handlers.parse_request_body", return_value=([{"ID": "CLC-01"}], None)), \
             patch("core.async_handlers.handle_submit", new_callable=AsyncMock, return_value={
                 "error": True, "message": "Storage not available"
             }), \
             patch("core.handlers.create_json_response", return_value={
                 "body": json.dumps({"error": True}),
                 "content_type": "application/json; charset=utf-8",
                 "status_code": 200
             }):
            response = client.post(
                "/evaluate/submit",
                json={"items": [{"ID": "CLC-01"}]},
                headers={"Content-Type": "application/json"}
            )
            assert response.status_code == 500


# =============================================================================
# evaluate/status エンドポイント
# =============================================================================

class TestAzureEvaluateStatus:
    """Azure Container Apps evaluate_status 関数のテスト"""

    @pytest.mark.asyncio
    async def test_status_running(self):
        """実行中ジョブのステータス"""
        client = _get_test_client()

        with patch("core.async_handlers.handle_status", new_callable=AsyncMock, return_value={
                 "job_id": "job-123", "status": "running", "progress": 50
             }), \
             patch("core.handlers.create_json_response", return_value={
                 "body": json.dumps({"status": "running"}),
                 "content_type": "application/json; charset=utf-8",
                 "status_code": 200
             }):
            response = client.get("/evaluate/status/job-123")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_status_not_found(self):
        """ジョブ未発見"""
        client = _get_test_client()

        with patch("core.async_handlers.handle_status", new_callable=AsyncMock, return_value={
                 "status": "not_found"
             }), \
             patch("core.handlers.create_error_response", return_value={
                 "body": json.dumps({"error": True}),
                 "content_type": "application/json; charset=utf-8",
                 "status_code": 404
             }):
            response = client.get("/evaluate/status/nonexistent")
            assert response.status_code == 404


# =============================================================================
# evaluate/results エンドポイント
# =============================================================================

class TestAzureEvaluateResults:
    """Azure Container Apps evaluate_results 関数のテスト"""

    @pytest.mark.asyncio
    async def test_results_completed(self):
        """完了ジョブの結果"""
        client = _get_test_client()

        with patch("core.async_handlers.handle_results", new_callable=AsyncMock, return_value={
                 "job_id": "job-123", "status": "completed", "results": [{"ID": "CLC-01"}]
             }), \
             patch("core.handlers.create_json_response", return_value={
                 "body": json.dumps({"status": "completed"}),
                 "content_type": "application/json; charset=utf-8",
                 "status_code": 200
             }):
            response = client.get("/evaluate/results/job-123")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_results_still_processing(self):
        """未完了ジョブ→ 202"""
        client = _get_test_client()

        with patch("core.async_handlers.handle_results", new_callable=AsyncMock, return_value={
                 "status": "running"
             }), \
             patch("core.handlers.create_json_response", return_value={
                 "body": json.dumps({"status": "running"}),
                 "content_type": "application/json; charset=utf-8",
                 "status_code": 200
             }):
            response = client.get("/evaluate/results/job-123")
            assert response.status_code == 202

    @pytest.mark.asyncio
    async def test_results_not_found(self):
        """ジョブ未発見→ 404"""
        client = _get_test_client()

        with patch("core.async_handlers.handle_results", new_callable=AsyncMock, return_value={
                 "status": "not_found"
             }), \
             patch("core.handlers.create_error_response", return_value={
                 "body": json.dumps({"error": True}),
                 "content_type": "application/json; charset=utf-8",
                 "status_code": 404
             }):
            response = client.get("/evaluate/results/nonexistent")
            assert response.status_code == 404
