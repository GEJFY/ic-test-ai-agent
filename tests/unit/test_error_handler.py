"""
エラーハンドリング機能のユニットテスト

error_handler.pyの機能をテストします。
"""
import pytest
import os
from datetime import datetime

# テスト対象のモジュールをインポート
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.error_handler import (
    ErrorResponse,
    handle_exception,
    create_error_response
)
from core.correlation import set_correlation_id


class TestErrorResponse:
    """ErrorResponseクラスのテストクラス"""

    def test_error_response_basic(self):
        """
        基本的なエラーレスポンス生成をテスト
        """
        error = ErrorResponse(
            error_id="ERR-001",
            correlation_id="test-correlation-id",
            error_code="VALIDATION_ERROR",
            message="Internal: Invalid field 'items'",
            user_message="リクエストの形式が正しくありません"
        )

        assert error.error_id == "ERR-001"
        assert error.correlation_id == "test-correlation-id"
        assert error.error_code == "VALIDATION_ERROR"
        assert error.message == "Internal: Invalid field 'items'"
        assert error.user_message == "リクエストの形式が正しくありません"

    def test_error_response_to_dict_production_mode(self):
        """
        本番環境モード（include_internal=False）でトレースバックが非表示になることを確認
        """
        error = ErrorResponse(
            error_id="ERR-002",
            correlation_id="test-corr-id",
            error_code="VALIDATION_ERROR",
            message="Internal: Invalid field 'items'",
            user_message="リクエストの形式が正しくありません",
            trace="Traceback (most recent call last):\n  File \"test.py\", line 10, in <module>"
        )

        response = error.to_dict(include_internal=False)

        # 本番モードではinternal_messageとtracebackが含まれない
        assert "internal_message" not in response
        assert "traceback" not in response

        # ユーザー向け情報のみ含まれる
        assert response["error_id"] == "ERR-002"
        assert response["correlation_id"] == "test-corr-id"
        assert response["error_code"] == "VALIDATION_ERROR"
        assert response["message"] == "リクエストの形式が正しくありません"
        assert "timestamp" in response

    def test_error_response_to_dict_development_mode(self):
        """
        開発環境モード（include_internal=True）で詳細情報が表示されることを確認
        """
        error = ErrorResponse(
            error_id="ERR-003",
            correlation_id="test-corr-id",
            error_code="INTERNAL_ERROR",
            message="Internal: Database connection failed",
            user_message="システムエラーが発生しました",
            trace="Traceback (most recent call last):\n  File \"db.py\", line 42"
        )

        response = error.to_dict(include_internal=True)

        # 開発モードでは全情報が含まれる
        assert response["internal_message"] == "Internal: Database connection failed"
        assert response["traceback"] == "Traceback (most recent call last):\n  File \"db.py\", line 42"
        assert response["error_id"] == "ERR-003"
        assert response["message"] == "システムエラーが発生しました"

    def test_error_response_timestamp_format(self):
        """
        タイムスタンプがISO 8601形式であることを確認
        """
        error = ErrorResponse(
            error_id="ERR-004",
            correlation_id="test",
            error_code="TEST_ERROR",
            message="Test",
            user_message="Test"
        )

        response = error.to_dict()

        # タイムスタンプがISO 8601形式でパース可能
        timestamp = response["timestamp"]
        try:
            datetime.fromisoformat(timestamp)
        except ValueError:
            pytest.fail(f"Invalid timestamp format: {timestamp}")

    def test_error_response_without_trace(self):
        """
        トレースバックなしのエラーレスポンスをテスト
        """
        error = ErrorResponse(
            error_id="ERR-005",
            correlation_id="test",
            error_code="SIMPLE_ERROR",
            message="Simple error",
            user_message="エラーが発生しました"
        )

        response_dev = error.to_dict(include_internal=True)
        response_prod = error.to_dict(include_internal=False)

        # 開発モードでもtracebackが含まれない（Noneなので）
        assert "traceback" not in response_dev or response_dev.get("traceback") is None
        assert "traceback" not in response_prod


class TestHandleException:
    """handle_exception関数のテストクラス"""

    def setup_method(self):
        """各テストの前に相関IDを設定"""
        set_correlation_id("test-correlation-id")

    def test_handle_exception_basic(self):
        """
        基本的な例外ハンドリングをテスト
        """
        try:
            raise ValueError("Test error message")
        except Exception as e:
            error_response = handle_exception(
                e,
                error_code="TEST_ERROR",
                user_message="テストエラーが発生しました"
            )

        assert error_response.error_code == "TEST_ERROR"
        assert error_response.user_message == "テストエラーが発生しました"
        assert error_response.correlation_id == "test-correlation-id"
        assert "ValueError" in error_response.message or "Test error message" in error_response.message

    def test_handle_exception_with_correlation_id(self):
        """
        相関IDが正しくエラーレスポンスに含まれることを確認
        """
        set_correlation_id("custom-correlation-id-123")

        try:
            raise RuntimeError("Runtime error")
        except Exception as e:
            error_response = handle_exception(
                e,
                error_code="RUNTIME_ERROR",
                user_message="実行時エラー"
            )

        assert error_response.correlation_id == "custom-correlation-id-123"

    def test_handle_exception_includes_traceback(self):
        """
        トレースバックが含まれることを確認
        """
        try:
            # スタックトレースを作るために関数呼び出し
            def inner_function():
                raise ValueError("Inner error")

            inner_function()
        except Exception as e:
            error_response = handle_exception(
                e,
                error_code="NESTED_ERROR",
                user_message="ネストされたエラー"
            )

        # トレースバックに関数名が含まれることを確認
        assert error_response.trace is not None
        assert "inner_function" in error_response.trace
        assert "ValueError" in error_response.trace

    def test_handle_exception_without_correlation_id(self):
        """
        相関IDが設定されていない場合、"unknown"が設定されることを確認
        """
        set_correlation_id(None)

        try:
            raise Exception("No correlation ID")
        except Exception as e:
            error_response = handle_exception(
                e,
                error_code="NO_CORR_ID_ERROR",
                user_message="相関IDなしエラー"
            )

        # 相関IDがない場合は"unknown"が設定される
        assert error_response.correlation_id == "unknown"


class TestCreateErrorResponse:
    """create_error_response関数のテストクラス"""

    def setup_method(self):
        """各テストの前に相関IDを設定"""
        set_correlation_id("test-correlation-id")

    def test_create_error_response_production(self):
        """
        本番環境用エラーレスポンス生成をテスト
        """
        error_response = create_error_response(
            error_code="API_ERROR",
            internal_message="Internal: API connection failed",
            user_message="APIエラーが発生しました"
        )

        # production環境（include_internal=False）でdictに変換
        response = error_response.to_dict(include_internal=False)

        assert response["error_code"] == "API_ERROR"
        assert response["message"] == "APIエラーが発生しました"
        assert response["correlation_id"] == "test-correlation-id"
        assert "internal_message" not in response  # 本番環境では内部メッセージは含まれない

    def test_create_error_response_development(self):
        """
        開発環境用エラーレスポンス生成をテスト
        """
        error_response = create_error_response(
            error_code="API_ERROR",
            internal_message="Internal: Connection timeout",
            user_message="APIエラーが発生しました"
        )

        # 開発環境（include_internal=True）でdictに変換
        response = error_response.to_dict(include_internal=True)

        assert response["internal_message"] == "Internal: Connection timeout"
        assert response["error_code"] == "API_ERROR"
        assert response["message"] == "APIエラーが発生しました"

    def test_create_error_response_with_trace(self):
        """
        トレースバック付きエラーレスポンス生成をテスト
        """
        try:
            raise ValueError("Test exception for trace")
        except Exception as e:
            error_response = create_error_response(
                error_code="TRACED_ERROR",
                internal_message="Internal: Test exception occurred",
                user_message="トレース付きエラー",
                exception=e
            )

            # 開発環境（include_internal=True）でdictに変換
            response = error_response.to_dict(include_internal=True)

            # トレースバックが含まれることを確認
            assert "traceback" in response
            assert "ValueError: Test exception for trace" in response["traceback"]

    def test_create_error_response_without_correlation_id(self):
        """
        相関IDなしでエラーレスポンス生成をテスト
        """
        set_correlation_id(None)

        error_response = create_error_response(
            error_code="NO_CORR_ERROR",
            internal_message="Internal: No correlation ID",
            user_message="相関IDなし"
        )

        response = error_response.to_dict(include_internal=False)

        # 相関IDがない場合は"unknown"が設定される
        assert response["correlation_id"] == "unknown"

    def test_create_error_response_auto_error_id(self):
        """
        エラーIDが自動生成されることを確認
        """
        error_response = create_error_response(
            error_code="AUTO_ID_ERROR",
            internal_message="Internal: Auto ID test",
            user_message="自動ID生成"
        )

        response = error_response.to_dict(include_internal=False)

        # error_idが存在し、形式が正しい（8文字の16進数）
        assert "error_id" in response
        assert len(response["error_id"]) == 8
        # 16進数文字のみで構成されていることを確認
        int(response["error_id"], 16)  # 例外が発生しなければOK


class TestErrorHandlingIntegration:
    """エラーハンドリング統合テスト"""

    def test_full_error_flow_production(self):
        """
        実際のエラー発生から本番環境レスポンス生成までのフロー
        """
        set_correlation_id("integration-test-id")

        try:
            # 意図的にエラーを発生させる
            raise ValueError("Production test error")
        except Exception as e:
            error_response = handle_exception(
                e,
                error_code="INTEGRATION_ERROR",
                user_message="統合テストエラー"
            )
            response_dict = error_response.to_dict(include_internal=False)

        # 本番環境では内部情報が含まれない
        assert "internal_message" not in response_dict
        assert "traceback" not in response_dict
        assert response_dict["message"] == "統合テストエラー"
        assert response_dict["correlation_id"] == "integration-test-id"

    def test_full_error_flow_development(self):
        """
        実際のエラー発生から開発環境レスポンス生成までのフロー
        """
        set_correlation_id("dev-test-id")

        try:
            raise RuntimeError("Development test error")
        except Exception as e:
            error_response = handle_exception(
                e,
                error_code="DEV_ERROR",
                user_message="開発テストエラー"
            )
            response_dict = error_response.to_dict(include_internal=True)

        # 開発環境では内部情報が含まれる
        assert "internal_message" in response_dict
        assert "traceback" in response_dict
        assert "RuntimeError" in response_dict["internal_message"]
        assert response_dict["correlation_id"] == "dev-test-id"


# pytest実行時のエントリポイント
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
