# -*- coding: utf-8 -*-
"""
================================================================================
test_platform_gcp.py - GCP Cloud Functions エントリポイントのユニットテスト
================================================================================

【テスト対象】
- platforms/gcp/main.py のエンドポイント関数

================================================================================
"""

import pytest
import json
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock

_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_gcp_dir = os.path.join(_project_root, "platforms", "gcp")


def _setup_gcp_mocks():
    """GCP依存モジュール (functions_framework, flask) をモック化"""
    mock_ff = MagicMock()
    mock_ff.http = lambda f: f  # デコレーターをパススルー

    mock_flask = MagicMock()
    mock_flask.Request = MagicMock
    mock_flask.make_response = MagicMock(side_effect=lambda body, status: MagicMock(
        data=body, status_code=status, headers={}
    ))

    return {
        "functions_framework": mock_ff,
        "flask": mock_flask,
    }


def _import_gcp_main():
    """GCP main モジュールをインポート（モック付き）"""
    if _gcp_dir not in sys.path:
        sys.path.insert(0, _gcp_dir)
    if "main" in sys.modules:
        del sys.modules["main"]

    mocks = _setup_gcp_mocks()
    with patch.dict("sys.modules", mocks):
        import main
        return main


# =============================================================================
# evaluate エンドポイント
# =============================================================================

class TestGCPEvaluate:
    """GCP evaluate 関数のテスト"""

    def test_evaluate_post_success(self):
        """POST /evaluate 正常系"""
        gcp = _import_gcp_main()

        mock_request = MagicMock()
        mock_request.method = "POST"
        mock_request.get_data.return_value = json.dumps({
            "items": [{"ID": "CLC-01"}]
        }).encode()

        with patch("core.handlers.parse_request_body", return_value=([{"ID": "CLC-01"}], None)), \
             patch.object(gcp, "run_async", return_value=[{"ID": "CLC-01", "evaluationResult": True}]):
            result = gcp.evaluate(mock_request)
            assert result.status_code == 200

    def test_evaluate_method_not_allowed(self):
        """GET /evaluate は 405"""
        gcp = _import_gcp_main()

        mock_request = MagicMock()
        mock_request.method = "GET"

        result = gcp.evaluate(mock_request)
        assert result.status_code == 405

    def test_evaluate_parse_error(self):
        """リクエスト解析エラー"""
        gcp = _import_gcp_main()

        mock_request = MagicMock()
        mock_request.method = "POST"
        mock_request.get_data.return_value = b"invalid"

        with patch("core.handlers.parse_request_body", return_value=(None, "Invalid JSON")):
            result = gcp.evaluate(mock_request)
            assert result.status_code == 400


# =============================================================================
# health エンドポイント
# =============================================================================

class TestGCPHealth:
    """GCP health 関数のテスト"""

    def test_health(self):
        """GET /health"""
        gcp = _import_gcp_main()
        mock_request = MagicMock()

        with patch("core.handlers.handle_health", return_value={"status": "healthy"}):
            result = gcp.health(mock_request)
            assert result.status_code == 200
            body = json.loads(result.data)
            assert body["platform"] == "GCP Cloud Functions"


# =============================================================================
# config エンドポイント
# =============================================================================

class TestGCPConfig:
    """GCP config_status 関数のテスト"""

    def test_config(self):
        """GET /config"""
        gcp = _import_gcp_main()
        mock_request = MagicMock()

        with patch("core.handlers.handle_config", return_value={"llm": "configured"}):
            result = gcp.config_status(mock_request)
            assert result.status_code == 200
            body = json.loads(result.data)
            assert body["platform"]["name"] == "GCP Cloud Functions"


# =============================================================================
# evaluate_submit エンドポイント
# =============================================================================

class TestGCPEvaluateSubmit:
    """GCP evaluate_submit 関数のテスト"""

    def test_submit_success(self):
        """POST /evaluate/submit 正常系"""
        gcp = _import_gcp_main()

        mock_request = MagicMock()
        mock_request.method = "POST"
        mock_request.get_data.return_value = json.dumps({"items": [{"ID": "CLC-01"}]}).encode()
        mock_request.headers = {"X-Tenant-ID": "tenant-a"}

        with patch("core.handlers.parse_request_body", return_value=([{"ID": "CLC-01"}], None)), \
             patch.object(gcp, "run_async", return_value={"job_id": "job-123", "status": "pending"}):
            result = gcp.evaluate_submit(mock_request)
            assert result.status_code == 202

    def test_submit_method_not_allowed(self):
        """GET は 405"""
        gcp = _import_gcp_main()
        mock_request = MagicMock()
        mock_request.method = "GET"

        result = gcp.evaluate_submit(mock_request)
        assert result.status_code == 405


# =============================================================================
# evaluate_status エンドポイント
# =============================================================================

class TestGCPEvaluateStatus:
    """GCP evaluate_status 関数のテスト"""

    def test_status_from_path(self):
        """パスからjob_id取得"""
        gcp = _import_gcp_main()

        mock_request = MagicMock()
        mock_request.path = "/evaluate/status/job-123"
        mock_request.args = {}

        with patch.object(gcp, "run_async", return_value={"status": "running", "progress": 50}):
            result = gcp.evaluate_status(mock_request)
            assert result.status_code == 200

    def test_status_missing_job_id(self):
        """job_id 未指定"""
        gcp = _import_gcp_main()

        mock_request = MagicMock()
        mock_request.path = "/evaluate/status/"
        mock_request.args = MagicMock()
        mock_request.args.get.return_value = None
        # path.split("/")[-1] returns "" when path ends with /
        # and "/status/" is in path => job_id = ""

        result = gcp.evaluate_status(mock_request)
        assert result.status_code == 400


# =============================================================================
# evaluate_results エンドポイント
# =============================================================================

class TestGCPEvaluateResults:
    """GCP evaluate_results 関数のテスト"""

    def test_results_completed(self):
        """完了ジョブの結果取得"""
        gcp = _import_gcp_main()

        mock_request = MagicMock()
        mock_request.path = "/evaluate/results/job-123"
        mock_request.args = {}

        with patch.object(gcp, "run_async", return_value={
            "status": "completed",
            "results": [{"ID": "CLC-01"}]
        }):
            result = gcp.evaluate_results(mock_request)
            assert result.status_code == 200

    def test_results_not_found(self):
        """ジョブ未発見"""
        gcp = _import_gcp_main()

        mock_request = MagicMock()
        mock_request.path = "/evaluate/results/nonexistent"
        mock_request.args = {}

        with patch.object(gcp, "run_async", return_value={"status": "not_found"}):
            result = gcp.evaluate_results(mock_request)
            assert result.status_code == 404
