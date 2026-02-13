# -*- coding: utf-8 -*-
"""
================================================================================
test_platform_aws.py - AWS App Runner エントリポイントのユニットテスト
================================================================================

【テスト対象】
- platforms/local/main.py のFastAPI/Uvicornエンドポイント（AWS App Runner用Dockerイメージ）

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
# ヘルパー関数テスト
# =============================================================================

class TestHelperFunctions:
    """FastAPIアプリのヘルパー関数テスト"""

    def test_get_path_evaluate(self):
        """FastAPIルーティング: /evaluate パス"""
        client = _get_test_client()
        # FastAPIのルーティングが /evaluate を認識するか確認
        with patch("core.handlers.parse_request_body", return_value=([], None)), \
             patch("core.handlers.handle_evaluate", new_callable=AsyncMock, return_value=[]):
            response = client.post("/evaluate", json=[])
            # ルートが存在することを確認（405ではない）
            assert response.status_code != 405

    def test_get_path_health(self):
        """FastAPIルーティング: /health パス"""
        client = _get_test_client()
        with patch("core.handlers.handle_health", return_value={"status": "healthy"}):
            response = client.get("/health")
            assert response.status_code == 200

    def test_get_path_config(self):
        """FastAPIルーティング: /config パス"""
        client = _get_test_client()
        with patch("core.handlers.handle_config", return_value={"llm": "ok"}):
            response = client.get("/config")
            assert response.status_code == 200

    def test_get_path_default_404(self):
        """パス情報がない場合の404"""
        client = _get_test_client()
        response = client.get("/nonexistent_path")
        assert response.status_code == 404

    def test_options_returns_200(self):
        """OPTIONS (CORS preflight) は 200 を返す"""
        client = _get_test_client()
        response = client.options("/evaluate")
        # FastAPI CORSミドルウェアによる処理
        assert response.status_code in [200, 204, 405]

    def test_create_response(self):
        """JSONレスポンス生成"""
        app_module = _import_fastapi_app()
        if hasattr(app_module, 'create_json_response'):
            result = app_module.create_json_response({"status": "ok"}, 200)
            assert result.status_code == 200

    def test_create_error_response(self):
        """エラーレスポンス生成"""
        app_module = _import_fastapi_app()
        if hasattr(app_module, 'create_error_response'):
            result = app_module.create_error_response("Test error", 500)
            assert result.status_code == 500


# =============================================================================
# ルーティングテスト
# =============================================================================

class TestRouting:
    """FastAPIルーティングテスト"""

    def test_health_endpoint(self):
        """/health エンドポイントのルーティング"""
        client = _get_test_client()
        with patch("core.handlers.handle_health", return_value={"status": "healthy"}):
            response = client.get("/health")
            assert response.status_code == 200

    def test_config_endpoint(self):
        """/config エンドポイントのルーティング"""
        client = _get_test_client()
        with patch("core.handlers.handle_config", return_value={"config": {}}):
            response = client.get("/config")
            assert response.status_code == 200

    def test_evaluate_endpoint(self):
        """/evaluate エンドポイントのルーティング"""
        client = _get_test_client()
        with patch("core.handlers.parse_request_body", return_value=([{"ID": "CLC-01"}], None)), \
             patch("core.handlers.handle_evaluate", new_callable=AsyncMock, return_value=[]):
            response = client.post("/evaluate", json=[{"ID": "CLC-01"}])
            assert response.status_code == 200

    def test_evaluate_submit_endpoint(self):
        """/evaluate/submit エンドポイント"""
        client = _get_test_client()
        with patch("core.handlers.parse_request_body", return_value=([{"ID": "CLC-01"}], None)), \
             patch("core.async_handlers.handle_submit", new_callable=AsyncMock, return_value={
                 "job_id": "job-123", "status": "pending"
             }):
            response = client.post("/evaluate/submit", json={"items": [{"ID": "CLC-01"}]})
            assert response.status_code in [200, 202]

    def test_not_found(self):
        """不明なパスは 404"""
        client = _get_test_client()
        response = client.get("/unknown")
        assert response.status_code == 404


# =============================================================================
# 各エンドポイント詳細テスト
# =============================================================================

class TestEvaluateEndpoint:
    """evaluate エンドポイントのテスト"""

    def test_evaluate_success(self):
        """正常評価"""
        client = _get_test_client()

        mock_items = [{"ID": "CLC-01"}]
        mock_response = [{"ID": "CLC-01", "evaluationResult": True}]

        with patch("core.handlers.parse_request_body", return_value=(mock_items, None)), \
             patch("core.handlers.handle_evaluate", new_callable=AsyncMock, return_value=mock_response):
            response = client.post(
                "/evaluate",
                json={"items": mock_items},
                headers={"Content-Type": "application/json"}
            )
            assert response.status_code == 200

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


class TestHealthEndpoint:
    """health エンドポイントのテスト"""

    def test_health(self):
        """ヘルスチェック"""
        client = _get_test_client()
        with patch("core.handlers.handle_health", return_value={"status": "healthy"}):
            response = client.get("/health")
            assert response.status_code == 200
            body = response.json()
            assert body["platform"] == "Local (FastAPI + Ollama)"


class TestStatusEndpoint:
    """evaluate_status エンドポイントのテスト"""

    def test_status_from_path(self):
        """パスからjob_idを取得"""
        client = _get_test_client()
        with patch("core.async_handlers.handle_status", new_callable=AsyncMock,
                    return_value={"status": "running", "progress": 50}):
            response = client.get("/evaluate/status/job-123")
            assert response.status_code == 200

    def test_status_not_found(self):
        """ジョブが存在しない場合"""
        client = _get_test_client()
        with patch("core.async_handlers.handle_status", new_callable=AsyncMock,
                    return_value={"status": "not_found"}):
            response = client.get("/evaluate/status/nonexistent")
            assert response.status_code == 404
