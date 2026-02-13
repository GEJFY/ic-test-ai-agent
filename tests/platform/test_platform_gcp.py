# -*- coding: utf-8 -*-
"""
================================================================================
test_platform_gcp.py - GCP Cloud Run エントリポイントのユニットテスト
================================================================================

【テスト対象】
- platforms/local/main.py のFastAPI/Uvicornエンドポイント（GCP Cloud Run用Dockerイメージ）

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
# evaluate エンドポイント
# =============================================================================

class TestGCPEvaluate:
    """GCP Cloud Run evaluate 関数のテスト"""

    def test_evaluate_post_success(self):
        """POST /evaluate 正常系"""
        client = _get_test_client()

        with patch("core.handlers.parse_request_body", return_value=([{"ID": "CLC-01"}], None)), \
             patch("core.handlers.handle_evaluate", new_callable=AsyncMock,
                   return_value=[{"ID": "CLC-01", "evaluationResult": True}]):
            response = client.post(
                "/evaluate",
                json={"items": [{"ID": "CLC-01"}]},
                headers={"Content-Type": "application/json"}
            )
            assert response.status_code == 200

    def test_evaluate_method_not_allowed(self):
        """GET /evaluate は 405"""
        client = _get_test_client()
        response = client.get("/evaluate")
        assert response.status_code == 405

    def test_evaluate_parse_error(self):
        """リクエスト解析エラー"""
        client = _get_test_client()

        with patch("core.handlers.parse_request_body", return_value=(None, "Invalid JSON")):
            response = client.post(
                "/evaluate",
                content=b"invalid",
                headers={"Content-Type": "application/json"}
            )
            assert response.status_code == 400


# =============================================================================
# health エンドポイント
# =============================================================================

class TestGCPHealth:
    """GCP Cloud Run health 関数のテスト"""

    def test_health(self):
        """GET /health"""
        client = _get_test_client()

        with patch("core.handlers.handle_health", return_value={"status": "healthy"}):
            response = client.get("/health")
            assert response.status_code == 200
            body = response.json()
            assert body["platform"] == "Local (FastAPI + Ollama)"


# =============================================================================
# config エンドポイント
# =============================================================================

class TestGCPConfig:
    """GCP Cloud Run config_status 関数のテスト"""

    def test_config(self):
        """GET /config"""
        client = _get_test_client()

        with patch("core.handlers.handle_config", return_value={"llm": "configured"}):
            response = client.get("/config")
            assert response.status_code == 200
            body = response.json()
            assert body["platform"]["name"] == "Local Server"


# =============================================================================
# evaluate_submit エンドポイント
# =============================================================================

class TestGCPEvaluateSubmit:
    """GCP Cloud Run evaluate_submit 関数のテスト"""

    def test_submit_success(self):
        """POST /evaluate/submit 正常系"""
        client = _get_test_client()

        with patch("core.handlers.parse_request_body", return_value=([{"ID": "CLC-01"}], None)), \
             patch("core.async_handlers.handle_submit", new_callable=AsyncMock,
                   return_value={"job_id": "job-123", "status": "pending"}):
            response = client.post(
                "/evaluate/submit",
                json={"items": [{"ID": "CLC-01"}]},
                headers={"Content-Type": "application/json", "X-Tenant-ID": "tenant-a"}
            )
            assert response.status_code == 202

    def test_submit_method_not_allowed(self):
        """GET は 405"""
        client = _get_test_client()
        response = client.get("/evaluate/submit")
        assert response.status_code == 405


# =============================================================================
# evaluate_status エンドポイント
# =============================================================================

class TestGCPEvaluateStatus:
    """GCP Cloud Run evaluate_status 関数のテスト"""

    def test_status_from_path(self):
        """パスからjob_id取得"""
        client = _get_test_client()

        with patch("core.async_handlers.handle_status", new_callable=AsyncMock,
                    return_value={"status": "running", "progress": 50}):
            response = client.get("/evaluate/status/job-123")
            assert response.status_code == 200

    def test_status_missing_job_id(self):
        """job_id 未指定"""
        client = _get_test_client()
        # FastAPIルーティングでは /evaluate/status/ はjob_idパラメータなしで404
        response = client.get("/evaluate/status/")
        assert response.status_code in [400, 404, 422]


# =============================================================================
# evaluate_results エンドポイント
# =============================================================================

class TestGCPEvaluateResults:
    """GCP Cloud Run evaluate_results 関数のテスト"""

    def test_results_completed(self):
        """完了ジョブの結果取得"""
        client = _get_test_client()

        with patch("core.async_handlers.handle_results", new_callable=AsyncMock,
                    return_value={"status": "completed", "results": [{"ID": "CLC-01"}]}):
            response = client.get("/evaluate/results/job-123")
            assert response.status_code == 200

    def test_results_not_found(self):
        """ジョブ未発見"""
        client = _get_test_client()

        with patch("core.async_handlers.handle_results", new_callable=AsyncMock,
                    return_value={"status": "not_found"}):
            response = client.get("/evaluate/results/nonexistent")
            assert response.status_code == 404
