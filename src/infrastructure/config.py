"""
環境変数の型安全な取得・バリデーションヘルパー

起動時に不正値を検出し、実行時エラーを防止します。
"""

import os
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)


class ConfigError(ValueError):
    """設定値が不正な場合の例外"""
    pass


def get_env_int(
    name: str,
    default: int,
    min_val: Optional[int] = None,
    max_val: Optional[int] = None,
) -> int:
    """
    環境変数を整数として安全に取得する。

    Args:
        name: 環境変数名
        default: デフォルト値
        min_val: 最小値（Noneで制限なし）
        max_val: 最大値（Noneで制限なし）

    Returns:
        整数値

    Raises:
        ConfigError: 値が不正な場合
    """
    value_str = os.environ.get(name)
    if value_str is None:
        return default

    try:
        value = int(value_str)
    except ValueError:
        raise ConfigError(
            f"環境変数 {name}='{value_str}' は整数ではありません"
        )

    if min_val is not None and value < min_val:
        raise ConfigError(
            f"環境変数 {name}={value} は最小値 {min_val} を下回っています"
        )

    if max_val is not None and value > max_val:
        raise ConfigError(
            f"環境変数 {name}={value} は最大値 {max_val} を超えています"
        )

    return value


def get_env_bool(name: str, default: bool = False) -> bool:
    """
    環境変数を真偽値として安全に取得する。

    Args:
        name: 環境変数名
        default: デフォルト値

    Returns:
        真偽値

    Raises:
        ConfigError: 値が不正な場合
    """
    value_str = os.environ.get(name)
    if value_str is None:
        return default

    if value_str.lower() in ("true", "1", "yes", "on"):
        return True
    elif value_str.lower() in ("false", "0", "no", "off"):
        return False
    else:
        raise ConfigError(
            f"環境変数 {name}='{value_str}' は真偽値ではありません "
            f"(true/false/1/0 を指定してください)"
        )


def get_env_str(
    name: str,
    default: Optional[str] = None,
    allowed_values: Optional[List[str]] = None,
) -> Optional[str]:
    """
    環境変数を文字列として安全に取得する。

    Args:
        name: 環境変数名
        default: デフォルト値
        allowed_values: 許容される値のリスト（Noneで制限なし）

    Returns:
        文字列値

    Raises:
        ConfigError: 値が不正な場合
    """
    value = os.environ.get(name, default)

    if value is not None and allowed_values and value not in allowed_values:
        raise ConfigError(
            f"環境変数 {name}='{value}' は許容されない値です。"
            f"許容値: {allowed_values}"
        )

    return value
