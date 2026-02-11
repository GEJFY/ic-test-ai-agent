# -*- coding: utf-8 -*-
"""
================================================================================
test_platform_aws.py - AWS Lambda エントリポイントのユニットテスト
================================================================================

【テスト対象】
- platforms/aws/lambda_handler.py のルーティング、ヘルパー関数、各エンドポイント

================================================================================
"""

import pytest
import json
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock

# lambda_handler は dotenv に依存するので先にモック化
# platforms/aws をsys.pathに追加してインポート
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_aws_dir = os.path.join(_project_root, "platforms", "aws")


@pytest.fixture(autouse=True)
def _add_aws_path():
    """AWS Lambda ハンドラーのインポート用にパスを追加"""
    if _aws_dir not in sys.path:
        sys.path.insert(0, _aws_dir)
    yield
    if _aws_dir in sys.path:
        sys.path.remove(_aws_dir)


# =============================================================================
# ヘルパー関数テスト
# =============================================================================

class TestHelperFunctions:
    """lambda_handler のヘルパー関数テスト"""

    def _import_handler(self):
        # キャッシュを避けるため reload する
        if "lambda_handler" in sys.modules:
            del sys.modules["lambda_handler"]
        import lambda_handler
        return lambda_handler

    def test_get_path_v2(self):
        """API Gateway v2 のパス取得"""
        lh = self._import_handler()
        event = {"rawPath": "/evaluate"}
        assert lh.get_path(event) == "/evaluate"

    def test_get_path_v1(self):
        """API Gateway v1 のパス取得"""
        lh = self._import_handler()
        event = {"path": "/health"}
        assert lh.get_path(event) == "/health"

    def test_get_path_alb(self):
        """ALB のパス取得"""
        lh = self._import_handler()
        event = {"requestContext": {"path": "/config"}}
        assert lh.get_path(event) == "/config"

    def test_get_path_default(self):
        """パス情報がない場合のデフォルト"""
        lh = self._import_handler()
        assert lh.get_path({}) == "/"

    def test_get_method_v2(self):
        """API Gateway v2 のHTTPメソッド取得"""
        lh = self._import_handler()
        event = {"requestContext": {"http": {"method": "POST"}}}
        assert lh.get_method(event) == "POST"

    def test_get_method_v1(self):
        """API Gateway v1 のHTTPメソッド取得"""
        lh = self._import_handler()
        event = {"httpMethod": "DELETE"}
        assert lh.get_method(event) == "DELETE"

    def test_get_method_default(self):
        """メソッド情報がない場合のデフォルト"""
        lh = self._import_handler()
        assert lh.get_method({}) == "GET"

    def test_get_body_empty(self):
        """空のボディ"""
        lh = self._import_handler()
        assert lh.get_body({}) == b""

    def test_get_body_string(self):
        """文字列ボディ"""
        lh = self._import_handler()
        event = {"body": '{"key": "value"}', "isBase64Encoded": False}
        assert lh.get_body(event) == b'{"key": "value"}'

    def test_get_body_base64(self):
        """Base64エンコードされたボディ"""
        import base64
        lh = self._import_handler()
        original = b'{"key": "value"}'
        encoded = base64.b64encode(original).decode()
        event = {"body": encoded, "isBase64Encoded": True}
        assert lh.get_body(event) == original

    def test_create_response(self):
        """レスポンス生成"""
        lh = self._import_handler()
        result = lh.create_response({"status": "ok"})
        assert result["statusCode"] == 200
        assert "Content-Type" in result["headers"]
        body = json.loads(result["body"])
        assert body["status"] == "ok"

    def test_create_response_custom_status(self):
        """カスタムステータスコードのレスポンス"""
        lh = self._import_handler()
        result = lh.create_response({"error": True}, 400)
        assert result["statusCode"] == 400

    def test_create_error_response(self):
        """エラーレスポンス生成"""
        lh = self._import_handler()
        result = lh.create_error_response("Test error", 500, "traceback...")
        assert result["statusCode"] == 500
        body = json.loads(result["body"])
        assert body["error"] is True
        assert body["message"] == "Test error"
        assert body["traceback"] == "traceback..."


# =============================================================================
# ルーティングテスト
# =============================================================================

class TestRouting:
    """handler() のルーティングテスト"""

    def _import_handler(self):
        if "lambda_handler" in sys.modules:
            del sys.modules["lambda_handler"]
        import lambda_handler
        return lambda_handler

    def test_options_returns_200(self):
        """OPTIONS (CORS preflight) は 200 を返す"""
        lh = self._import_handler()
        event = {"path": "/evaluate", "httpMethod": "OPTIONS"}
        result = lh.handler(event, None)
        assert result["statusCode"] == 200

    def test_health_endpoint(self):
        """/health エンドポイントのルーティング"""
        lh = self._import_handler()
        with patch("lambda_handler.handle_health_request") as mock_health:
            mock_health.return_value = lh.create_response({"status": "healthy"})
            event = {"path": "/health", "httpMethod": "GET"}
            result = lh.handler(event, None)
            mock_health.assert_called_once()

    def test_config_endpoint(self):
        """/config エンドポイントのルーティング"""
        lh = self._import_handler()
        with patch("lambda_handler.handle_config_request") as mock_config:
            mock_config.return_value = lh.create_response({"config": {}})
            event = {"path": "/config", "httpMethod": "GET"}
            result = lh.handler(event, None)
            mock_config.assert_called_once()

    def test_evaluate_endpoint(self):
        """/evaluate エンドポイントのルーティング"""
        lh = self._import_handler()
        with patch("lambda_handler.handle_evaluate_request") as mock_eval:
            mock_eval.return_value = lh.create_response([])
            event = {"path": "/evaluate", "httpMethod": "POST"}
            result = lh.handler(event, None)
            mock_eval.assert_called_once()

    def test_evaluate_submit_endpoint(self):
        """/evaluate/submit はより具体的なパスが先にマッチ"""
        lh = self._import_handler()
        with patch("lambda_handler.handle_evaluate_submit_request") as mock_submit:
            mock_submit.return_value = lh.create_response({}, 202)
            event = {"path": "/evaluate/submit", "httpMethod": "POST"}
            result = lh.handler(event, None)
            mock_submit.assert_called_once()

    def test_not_found(self):
        """不明なパスは 404"""
        lh = self._import_handler()
        event = {"path": "/unknown", "httpMethod": "GET"}
        result = lh.handler(event, None)
        assert result["statusCode"] == 404


# =============================================================================
# 各エンドポイント詳細テスト
# =============================================================================

class TestEvaluateEndpoint:
    """handle_evaluate_request のテスト"""

    def _import_handler(self):
        if "lambda_handler" in sys.modules:
            del sys.modules["lambda_handler"]
        import lambda_handler
        return lambda_handler

    def test_evaluate_method_not_allowed(self):
        """POSTのみ許可"""
        lh = self._import_handler()
        event = {"path": "/evaluate", "httpMethod": "GET", "body": ""}
        result = lh.handle_evaluate_request(event)
        assert result["statusCode"] == 405

    def test_evaluate_success(self):
        """正常評価"""
        lh = self._import_handler()

        mock_items = [{"ID": "CLC-01"}]
        mock_response = [{"ID": "CLC-01", "evaluationResult": True}]

        with patch("core.handlers.parse_request_body", return_value=(mock_items, None)), \
             patch.object(lh, "run_async", return_value=mock_response):
            event = {
                "path": "/evaluate",
                "httpMethod": "POST",
                "body": json.dumps({"items": mock_items}),
            }
            result = lh.handle_evaluate_request(event)
            assert result["statusCode"] == 200
            body = json.loads(result["body"])
            assert body[0]["evaluationResult"] is True

    def test_evaluate_parse_error(self):
        """リクエスト解析エラー"""
        lh = self._import_handler()

        with patch("core.handlers.parse_request_body", return_value=(None, "Invalid JSON")):
            event = {
                "path": "/evaluate",
                "httpMethod": "POST",
                "body": "invalid",
            }
            result = lh.handle_evaluate_request(event)
            assert result["statusCode"] == 400


class TestHealthEndpoint:
    """handle_health_request のテスト"""

    def _import_handler(self):
        if "lambda_handler" in sys.modules:
            del sys.modules["lambda_handler"]
        import lambda_handler
        return lambda_handler

    def test_health(self):
        """ヘルスチェック"""
        lh = self._import_handler()
        with patch("core.handlers.handle_health", return_value={"status": "healthy"}):
            event = {"path": "/health", "httpMethod": "GET"}
            result = lh.handle_health_request(event)
            assert result["statusCode"] == 200
            body = json.loads(result["body"])
            assert body["platform"] == "AWS Lambda"


class TestStatusEndpoint:
    """handle_evaluate_status_request のテスト"""

    def _import_handler(self):
        if "lambda_handler" in sys.modules:
            del sys.modules["lambda_handler"]
        import lambda_handler
        return lambda_handler

    def test_status_from_path(self):
        """パスからjob_idを取得"""
        lh = self._import_handler()
        with patch("lambda_handler.run_async", return_value={"status": "running", "progress": 50}):
            event = {"path": "/evaluate/status/job-123", "httpMethod": "GET"}
            result = lh.handle_evaluate_status_request(event)
            assert result["statusCode"] == 200

    def test_status_missing_job_id(self):
        """job_id が見つからない場合"""
        lh = self._import_handler()
        event = {"path": "/evaluate/status", "httpMethod": "GET"}
        result = lh.handle_evaluate_status_request(event)
        assert result["statusCode"] == 400

    def test_status_not_found(self):
        """ジョブが存在しない場合"""
        lh = self._import_handler()
        with patch("lambda_handler.run_async", return_value={"status": "not_found"}):
            event = {"path": "/evaluate/status/nonexistent", "httpMethod": "GET"}
            result = lh.handle_evaluate_status_request(event)
            assert result["statusCode"] == 404
