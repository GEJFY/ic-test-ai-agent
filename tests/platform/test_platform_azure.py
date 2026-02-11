# -*- coding: utf-8 -*-
"""
================================================================================
test_platform_azure.py - Azure Functions エントリポイントのユニットテスト
================================================================================

【テスト対象】
- platforms/azure/function_app.py の各エンドポイント関数

================================================================================
"""

import pytest
import json
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock

_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_azure_dir = os.path.join(_project_root, "platforms", "azure")


class FakeHttpResponse:
    """azure.functions.HttpResponse のフェイク"""
    def __init__(self, body="", mimetype="application/json", status_code=200, **kwargs):
        self.body = body
        self.mimetype = mimetype
        self.status_code = status_code


def _make_mock_azure_module():
    """azure.functions モジュール全体のモック"""
    mock_azure = MagicMock()
    mock_func = MagicMock()

    mock_func.AuthLevel.ANONYMOUS = "anonymous"

    # FunctionApp: route() はデコレーターをパススルー
    mock_app_instance = MagicMock()
    mock_app_instance.route = MagicMock(side_effect=lambda **kwargs: lambda f: f)
    mock_app_instance.queue_trigger = MagicMock(side_effect=lambda **kwargs: lambda f: f)
    mock_func.FunctionApp.return_value = mock_app_instance

    # HttpResponse をフェイクに差し替え
    mock_func.HttpResponse = FakeHttpResponse
    mock_func.HttpRequest = MagicMock
    mock_func.QueueMessage = MagicMock

    mock_azure.functions = mock_func
    return mock_azure, mock_func


def _import_azure_function_app():
    """Azure function_app をインポート"""
    if _azure_dir not in sys.path:
        sys.path.insert(0, _azure_dir)
    if "function_app" in sys.modules:
        del sys.modules["function_app"]

    mock_azure, mock_func = _make_mock_azure_module()

    with patch.dict("sys.modules", {
        "azure": mock_azure,
        "azure.functions": mock_func,
    }):
        import function_app
        return function_app


# =============================================================================
# health エンドポイント
# =============================================================================

class TestAzureHealth:
    """Azure health 関数のテスト"""

    def test_health(self):
        """GET /api/health"""
        fa = _import_azure_function_app()
        mock_req = MagicMock()

        with patch("core.handlers.handle_health", return_value={"status": "healthy"}), \
             patch("core.handlers.create_json_response", return_value={
                 "body": json.dumps({"status": "healthy", "platform": "Azure Functions"}),
                 "content_type": "application/json; charset=utf-8",
                 "status_code": 200
             }):
            result = fa.health(mock_req)
            assert isinstance(result, FakeHttpResponse)
            assert result.status_code == 200


# =============================================================================
# config エンドポイント
# =============================================================================

class TestAzureConfig:
    """Azure config_status 関数のテスト"""

    def test_config(self):
        """GET /api/config"""
        fa = _import_azure_function_app()
        mock_req = MagicMock()

        with patch("core.handlers.handle_config", return_value={"llm": "ok"}), \
             patch("core.handlers.create_json_response", return_value={
                 "body": json.dumps({"llm": "ok"}),
                 "content_type": "application/json; charset=utf-8",
                 "status_code": 200
             }):
            result = fa.config_status(mock_req)
            assert result.status_code == 200


# =============================================================================
# evaluate エンドポイント
# =============================================================================

class TestAzureEvaluate:
    """Azure evaluate 関数のテスト"""

    @pytest.mark.asyncio
    async def test_evaluate_success(self):
        """POST /api/evaluate 正常系"""
        fa = _import_azure_function_app()

        mock_req = MagicMock()
        mock_req.get_body.return_value = json.dumps({"items": [{"ID": "CLC-01"}]}).encode()

        with patch("core.handlers.parse_request_body", return_value=([{"ID": "CLC-01"}], None)), \
             patch("core.handlers.handle_evaluate", new_callable=AsyncMock,
                   return_value=[{"ID": "CLC-01", "evaluationResult": True}]), \
             patch("core.handlers.create_json_response", return_value={
                 "body": json.dumps([{"ID": "CLC-01", "evaluationResult": True}]),
                 "content_type": "application/json; charset=utf-8",
                 "status_code": 200
             }):
            result = await fa.evaluate(mock_req)
            assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_evaluate_parse_error(self):
        """リクエスト解析エラー"""
        fa = _import_azure_function_app()

        mock_req = MagicMock()
        mock_req.get_body.return_value = b"invalid"

        with patch("core.handlers.parse_request_body", return_value=(None, "Invalid JSON")), \
             patch("core.handlers.create_error_response", return_value={
                 "body": json.dumps({"error": True, "message": "Invalid JSON"}),
                 "content_type": "application/json; charset=utf-8",
                 "status_code": 400
             }):
            result = await fa.evaluate(mock_req)
            assert result.status_code == 400

    @pytest.mark.asyncio
    async def test_evaluate_exception(self):
        """予期せぬ例外"""
        fa = _import_azure_function_app()

        mock_req = MagicMock()
        mock_req.get_body.return_value = b"{}"

        with patch("core.handlers.parse_request_body", side_effect=Exception("Unexpected")), \
             patch("core.handlers.create_error_response", return_value={
                 "body": json.dumps({"error": True}),
                 "content_type": "application/json; charset=utf-8",
                 "status_code": 500
             }):
            result = await fa.evaluate(mock_req)
            assert result.status_code == 500


# =============================================================================
# evaluate/submit エンドポイント
# =============================================================================

class TestAzureEvaluateSubmit:
    """Azure evaluate_submit 関数のテスト"""

    @pytest.mark.asyncio
    async def test_submit_success(self):
        """POST /api/evaluate/submit 正常系"""
        fa = _import_azure_function_app()

        mock_req = MagicMock()
        mock_req.get_body.return_value = json.dumps({"items": [{"ID": "CLC-01"}]}).encode()
        mock_req.headers = {"X-Tenant-ID": "tenant-a"}

        with patch("core.handlers.parse_request_body", return_value=([{"ID": "CLC-01"}], None)), \
             patch("core.async_handlers.handle_submit", new_callable=AsyncMock, return_value={
                 "job_id": "job-123", "status": "pending", "estimated_time": 60
             }), \
             patch("core.handlers.create_json_response", return_value={
                 "body": json.dumps({"job_id": "job-123"}),
                 "content_type": "application/json; charset=utf-8",
                 "status_code": 200
             }):
            result = await fa.evaluate_submit(mock_req)
            assert result.status_code == 202

    @pytest.mark.asyncio
    async def test_submit_error_response(self):
        """ジョブ送信エラー"""
        fa = _import_azure_function_app()

        mock_req = MagicMock()
        mock_req.get_body.return_value = json.dumps({"items": [{"ID": "CLC-01"}]}).encode()
        mock_req.headers = {}

        with patch("core.handlers.parse_request_body", return_value=([{"ID": "CLC-01"}], None)), \
             patch("core.async_handlers.handle_submit", new_callable=AsyncMock, return_value={
                 "error": True, "message": "Storage not available"
             }), \
             patch("core.handlers.create_json_response", return_value={
                 "body": json.dumps({"error": True}),
                 "content_type": "application/json; charset=utf-8",
                 "status_code": 200
             }):
            result = await fa.evaluate_submit(mock_req)
            assert result.status_code == 500


# =============================================================================
# evaluate/status エンドポイント
# =============================================================================

class TestAzureEvaluateStatus:
    """Azure evaluate_status 関数のテスト"""

    @pytest.mark.asyncio
    async def test_status_running(self):
        """実行中ジョブのステータス"""
        fa = _import_azure_function_app()

        mock_req = MagicMock()
        mock_req.route_params = {"job_id": "job-123"}

        with patch("core.async_handlers.handle_status", new_callable=AsyncMock, return_value={
                 "job_id": "job-123", "status": "running", "progress": 50
             }), \
             patch("core.handlers.create_json_response", return_value={
                 "body": json.dumps({"status": "running"}),
                 "content_type": "application/json; charset=utf-8",
                 "status_code": 200
             }):
            result = await fa.evaluate_status(mock_req)
            assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_status_not_found(self):
        """ジョブ未発見"""
        fa = _import_azure_function_app()

        mock_req = MagicMock()
        mock_req.route_params = {"job_id": "nonexistent"}

        with patch("core.async_handlers.handle_status", new_callable=AsyncMock, return_value={
                 "status": "not_found"
             }), \
             patch("core.handlers.create_error_response", return_value={
                 "body": json.dumps({"error": True}),
                 "content_type": "application/json; charset=utf-8",
                 "status_code": 404
             }):
            result = await fa.evaluate_status(mock_req)
            assert result.status_code == 404


# =============================================================================
# evaluate/results エンドポイント
# =============================================================================

class TestAzureEvaluateResults:
    """Azure evaluate_results 関数のテスト"""

    @pytest.mark.asyncio
    async def test_results_completed(self):
        """完了ジョブの結果"""
        fa = _import_azure_function_app()

        mock_req = MagicMock()
        mock_req.route_params = {"job_id": "job-123"}

        with patch("core.async_handlers.handle_results", new_callable=AsyncMock, return_value={
                 "job_id": "job-123", "status": "completed", "results": [{"ID": "CLC-01"}]
             }), \
             patch("core.handlers.create_json_response", return_value={
                 "body": json.dumps({"status": "completed"}),
                 "content_type": "application/json; charset=utf-8",
                 "status_code": 200
             }):
            result = await fa.evaluate_results(mock_req)
            assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_results_still_processing(self):
        """未完了ジョブ→ 202"""
        fa = _import_azure_function_app()

        mock_req = MagicMock()
        mock_req.route_params = {"job_id": "job-123"}

        with patch("core.async_handlers.handle_results", new_callable=AsyncMock, return_value={
                 "status": "running"
             }), \
             patch("core.handlers.create_json_response", return_value={
                 "body": json.dumps({"status": "running"}),
                 "content_type": "application/json; charset=utf-8",
                 "status_code": 200
             }):
            result = await fa.evaluate_results(mock_req)
            assert result.status_code == 202

    @pytest.mark.asyncio
    async def test_results_not_found(self):
        """ジョブ未発見→ 404"""
        fa = _import_azure_function_app()

        mock_req = MagicMock()
        mock_req.route_params = {"job_id": "nonexistent"}

        with patch("core.async_handlers.handle_results", new_callable=AsyncMock, return_value={
                 "status": "not_found"
             }), \
             patch("core.handlers.create_error_response", return_value={
                 "body": json.dumps({"error": True}),
                 "content_type": "application/json; charset=utf-8",
                 "status_code": 404
             }):
            result = await fa.evaluate_results(mock_req)
            assert result.status_code == 404
