"""
エラーハンドリング統一モジュール

本番環境と開発環境で異なるエラーレスポンスを返す統一エラーハンドリング機能を提供します。

本番環境:
- トレースバックを非表示
- ユーザー向けメッセージのみ返却
- 詳細なエラー情報はログに記録

開発環境:
- トレースバックを表示
- 内部エラーメッセージも返却
- デバッグ情報を含む
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional
import traceback
import uuid
import logging
import os

from .correlation import get_correlation_id

logger = logging.getLogger(__name__)


@dataclass
class ErrorResponse:
    """
    統一エラーレスポンス

    Attributes:
        error_id: エラーの一意識別子（ログ追跡用）
        correlation_id: リクエストの相関ID
        error_code: エラーコード（VALIDATION_ERROR, LLM_API_ERROR等）
        message: 内部用詳細エラーメッセージ
        user_message: ユーザー向けメッセージ
        timestamp: エラー発生時刻
        trace: トレースバック情報（開発環境のみ）
    """
    error_id: str
    correlation_id: str
    error_code: str
    message: str
    user_message: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    trace: Optional[str] = None

    def to_dict(self, include_internal: bool = False) -> Dict[str, Any]:
        """
        辞書形式に変換します。

        Args:
            include_internal: 内部情報を含めるか（開発環境用）

        Returns:
            エラーレスポンス辞書

        Examples:
            >>> error = ErrorResponse(
            ...     error_id="ERR-001",
            ...     correlation_id="test-corr-id",
            ...     error_code="VALIDATION_ERROR",
            ...     message="Internal: Invalid field 'items'",
            ...     user_message="リクエストの形式が正しくありません"
            ... )
            >>> response = error.to_dict(include_internal=False)
            >>> "internal_message" in response
            False
            >>> response["message"]
            'リクエストの形式が正しくありません'
        """
        response = {
            "error_id": self.error_id,
            "correlation_id": self.correlation_id,
            "error_code": self.error_code,
            "message": self.user_message,
            "timestamp": self.timestamp
        }

        if include_internal:
            response["internal_message"] = self.message
            if self.trace:
                response["traceback"] = self.trace

        return response


class ErrorHandler:
    """
    エラーハンドラー

    環境に応じた適切なエラーレスポンスを生成します。
    """

    # エラーコードとユーザー向けメッセージのマッピング
    ERROR_MESSAGES = {
        "VALIDATION_ERROR": "リクエストの形式が正しくありません。入力内容を確認してください。",
        "LLM_API_ERROR": "AI処理でエラーが発生しました。しばらく待ってから再試行してください。",
        "OCR_ERROR": "文字認識処理でエラーが発生しました。画像ファイルを確認してください。",
        "SECRET_ERROR": "認証情報の取得に失敗しました。システム管理者に連絡してください。",
        "TIMEOUT_ERROR": "処理がタイムアウトしました。処理量を減らすか、後で再試行してください。",
        "INTERNAL_ERROR": "内部エラーが発生しました。システム管理者に連絡してください。",
        "NOT_FOUND": "指定されたリソースが見つかりません。",
        "UNAUTHORIZED": "認証に失敗しました。APIキーを確認してください。",
        "RATE_LIMIT_EXCEEDED": "リクエスト数の上限を超えました。しばらく待ってから再試行してください。",
    }

    def __init__(self):
        """
        ErrorHandlerを初期化します。

        環境変数 ENVIRONMENT で本番環境（production）か開発環境かを判定します。
        """
        self.is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"

    def create_error_response(
        self,
        error_code: str,
        internal_message: str,
        user_message: Optional[str] = None,
        exception: Optional[Exception] = None
    ) -> ErrorResponse:
        """
        エラーレスポンスを作成します。

        Args:
            error_code: エラーコード
            internal_message: 内部用詳細メッセージ
            user_message: ユーザー向けメッセージ（Noneの場合はデフォルトメッセージ使用）
            exception: 例外オブジェクト（トレースバック取得用）

        Returns:
            ErrorResponse オブジェクト

        Examples:
            >>> handler = ErrorHandler()
            >>> error = handler.create_error_response(
            ...     error_code="VALIDATION_ERROR",
            ...     internal_message="Missing required field: items"
            ... )
            >>> error.error_code
            'VALIDATION_ERROR'
        """
        error_id = str(uuid.uuid4())[:8].upper()  # 短い一意ID
        correlation_id = get_correlation_id() or "unknown"

        # ユーザー向けメッセージのデフォルト設定
        if user_message is None:
            user_message = self.ERROR_MESSAGES.get(
                error_code,
                "エラーが発生しました。システム管理者に連絡してください。"
            )

        # トレースバック取得（開発環境のみ）
        trace = None
        if not self.is_production and exception:
            trace = "".join(traceback.format_exception(
                type(exception), exception, exception.__traceback__
            ))

        # ログに詳細情報を記録
        logger.error(
            f"エラー発生 [ID: {error_id}] [{error_code}]: {internal_message}",
            extra={
                "error_id": error_id,
                "correlation_id": correlation_id,
                "error_code": error_code
            },
            exc_info=exception if not self.is_production else None
        )

        return ErrorResponse(
            error_id=error_id,
            correlation_id=correlation_id,
            error_code=error_code,
            message=internal_message,
            user_message=user_message,
            trace=trace
        )

    def handle_exception(
        self,
        exception: Exception,
        error_code: Optional[str] = None,
        user_message: Optional[str] = None
    ) -> ErrorResponse:
        """
        例外からエラーレスポンスを作成します。

        Args:
            exception: 例外オブジェクト
            error_code: エラーコード（Noneの場合は例外タイプから推測）
            user_message: ユーザー向けメッセージ

        Returns:
            ErrorResponse オブジェクト

        Examples:
            >>> handler = ErrorHandler()
            >>> try:
            ...     raise ValueError("Invalid input")
            ... except ValueError as e:
            ...     error = handler.handle_exception(e, error_code="VALIDATION_ERROR")
            >>> error.error_code
            'VALIDATION_ERROR'
        """
        # エラーコードの推測
        if error_code is None:
            error_code = self._infer_error_code(exception)

        internal_message = f"{type(exception).__name__}: {str(exception)}"

        return self.create_error_response(
            error_code=error_code,
            internal_message=internal_message,
            user_message=user_message,
            exception=exception
        )

    def _infer_error_code(self, exception: Exception) -> str:
        """
        例外タイプからエラーコードを推測します。

        Args:
            exception: 例外オブジェクト

        Returns:
            推測されたエラーコード
        """
        exception_name = type(exception).__name__

        # 例外タイプとエラーコードのマッピング
        mapping = {
            "ValueError": "VALIDATION_ERROR",
            "KeyError": "VALIDATION_ERROR",
            "ValidationError": "VALIDATION_ERROR",
            "TimeoutError": "TIMEOUT_ERROR",
            "ConnectionError": "LLM_API_ERROR",
            "HTTPError": "LLM_API_ERROR",
            "FileNotFoundError": "NOT_FOUND",
            "PermissionError": "UNAUTHORIZED",
        }

        return mapping.get(exception_name, "INTERNAL_ERROR")

    def to_http_response(
        self,
        error_response: ErrorResponse,
        status_code: int = 500
    ) -> tuple[Dict[str, Any], int]:
        """
        HTTPレスポンス形式に変換します。

        Args:
            error_response: ErrorResponseオブジェクト
            status_code: HTTPステータスコード

        Returns:
            (レスポンスボディ辞書, ステータスコード) のタプル

        Examples:
            >>> handler = ErrorHandler()
            >>> error = ErrorResponse(
            ...     error_id="ERR-001",
            ...     correlation_id="test-corr-id",
            ...     error_code="VALIDATION_ERROR",
            ...     message="Internal error",
            ...     user_message="User error"
            ... )
            >>> body, code = handler.to_http_response(error, status_code=400)
            >>> code
            400
        """
        body = error_response.to_dict(include_internal=not self.is_production)
        return body, status_code


# グローバルインスタンス（簡単に使えるように）
_global_handler = ErrorHandler()


def create_error_response(
    error_code: str,
    internal_message: str,
    user_message: Optional[str] = None,
    exception: Optional[Exception] = None
) -> ErrorResponse:
    """
    グローバルハンドラーを使用してエラーレスポンスを作成します。

    使いやすさのためのショートカット関数です。

    Args:
        error_code: エラーコード
        internal_message: 内部用詳細メッセージ
        user_message: ユーザー向けメッセージ
        exception: 例外オブジェクト

    Returns:
        ErrorResponse オブジェクト
    """
    return _global_handler.create_error_response(
        error_code=error_code,
        internal_message=internal_message,
        user_message=user_message,
        exception=exception
    )


def handle_exception(
    exception: Exception,
    error_code: Optional[str] = None,
    user_message: Optional[str] = None
) -> ErrorResponse:
    """
    グローバルハンドラーを使用して例外を処理します。

    使いやすさのためのショートカット関数です。

    Args:
        exception: 例外オブジェクト
        error_code: エラーコード
        user_message: ユーザー向けメッセージ

    Returns:
        ErrorResponse オブジェクト
    """
    return _global_handler.handle_exception(
        exception=exception,
        error_code=error_code,
        user_message=user_message
    )
