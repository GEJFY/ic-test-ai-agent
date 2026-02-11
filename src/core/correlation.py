"""
相関ID管理モジュール

クライアント（VBA/PowerShell）からサーバー、外部API（LLM/OCR）まで
リクエストを追跡するための相関ID管理機能を提供します。

相関IDはContextVarを使用してスレッドセーフに管理されます。
"""

from contextvars import ContextVar
from typing import Dict, Optional
import uuid
import logging

# 相関IDを保持するContextVar（スレッドセーフ）
correlation_id_var: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)

logger = logging.getLogger(__name__)


def get_or_create_correlation_id(headers: Dict[str, str]) -> str:
    """
    HTTPヘッダーから相関IDを取得、存在しない場合は新規生成します。

    Args:
        headers: HTTPリクエストヘッダー辞書

    Returns:
        相関ID文字列

    Examples:
        >>> headers = {"X-Correlation-ID": "20260209_101530_0001"}
        >>> correlation_id = get_or_create_correlation_id(headers)
        >>> print(correlation_id)
        20260209_101530_0001

        >>> # ヘッダーがない場合はUUID生成
        >>> correlation_id = get_or_create_correlation_id({})
        >>> print(len(correlation_id))
        36
    """
    # X-Correlation-IDヘッダーを探す（大文字小文字を区別しない）
    correlation_id = None
    for key, value in headers.items():
        if key.lower() == 'x-correlation-id':
            correlation_id = value
            break

    # ヘッダーに相関IDがない場合はUUID生成
    if not correlation_id:
        correlation_id = str(uuid.uuid4())
        logger.info(
            f"相関IDが見つからないため新規生成しました: {correlation_id}",
            extra={"correlation_id": correlation_id}
        )

    # ContextVarに保存
    correlation_id_var.set(correlation_id)

    return correlation_id


def get_correlation_id() -> Optional[str]:
    """
    現在のコンテキストに設定されている相関IDを取得します。

    Returns:
        相関ID文字列。設定されていない場合はNone

    Examples:
        >>> # 相関IDを設定
        >>> set_correlation_id("test-correlation-id")
        >>> # 取得
        >>> correlation_id = get_correlation_id()
        >>> print(correlation_id)
        test-correlation-id
    """
    return correlation_id_var.get()


def set_correlation_id(correlation_id: str) -> None:
    """
    相関IDを明示的に設定します。

    Args:
        correlation_id: 設定する相関ID

    Examples:
        >>> set_correlation_id("custom-correlation-id")
        >>> print(get_correlation_id())
        custom-correlation-id
    """
    correlation_id_var.set(correlation_id)
    logger.debug(
        f"相関IDを設定しました: {correlation_id}",
        extra={"correlation_id": correlation_id}
    )


def clear_correlation_id() -> None:
    """
    相関IDをクリアします（主にテスト用）。

    Examples:
        >>> set_correlation_id("test-id")
        >>> clear_correlation_id()
        >>> print(get_correlation_id())
        None
    """
    correlation_id_var.set(None)
    logger.debug("相関IDをクリアしました")


def extract_correlation_id_from_dict(data: Dict, key: str = "correlation_id") -> Optional[str]:
    """
    辞書から相関IDを抽出します。

    Args:
        data: 辞書データ
        key: 相関IDのキー名（デフォルト: "correlation_id"）

    Returns:
        相関ID文字列。見つからない場合はNone

    Examples:
        >>> data = {"correlation_id": "test-id", "other": "value"}
        >>> correlation_id = extract_correlation_id_from_dict(data)
        >>> print(correlation_id)
        test-id
    """
    return data.get(key)


def inject_correlation_id_into_dict(data: Dict, key: str = "correlation_id") -> Dict:
    """
    辞書に現在の相関IDを注入します。

    Args:
        data: 辞書データ
        key: 相関IDのキー名（デフォルト: "correlation_id"）

    Returns:
        相関IDが追加された辞書（元の辞書は変更されない）

    Examples:
        >>> set_correlation_id("test-id")
        >>> data = {"message": "hello"}
        >>> result = inject_correlation_id_into_dict(data)
        >>> print(result)
        {'message': 'hello', 'correlation_id': 'test-id'}
    """
    correlation_id = get_correlation_id()
    if correlation_id:
        data_copy = data.copy()
        data_copy[key] = correlation_id
        return data_copy
    return data


def get_correlation_id_for_logging() -> Dict[str, str]:
    """
    ログ出力用の相関ID辞書を取得します。

    Returns:
        {"correlation_id": "xxx"} 形式の辞書。相関IDがない場合は空辞書

    Examples:
        >>> set_correlation_id("test-id")
        >>> extra = get_correlation_id_for_logging()
        >>> print(extra)
        {'correlation_id': 'test-id'}

        >>> # ログ出力時の使用例
        >>> logger.info("処理開始", extra=get_correlation_id_for_logging())
    """
    correlation_id = get_correlation_id()
    if correlation_id:
        return {"correlation_id": correlation_id}
    return {}
