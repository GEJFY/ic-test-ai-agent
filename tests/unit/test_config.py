# -*- coding: utf-8 -*-
"""
================================================================================
test_config.py - 環境変数バリデーション・証憑制限定数のテスト
================================================================================

【テスト対象】
- get_env_int / get_env_bool / get_env_str のバリデーション
- 証憑ファイル制限定数（MAX_EVIDENCE_FILE_SIZE_MB等）のデフォルト値・上書き

================================================================================
"""

import os
import pytest
from unittest.mock import patch

from infrastructure.config import (
    get_env_int, get_env_bool, get_env_str, ConfigError,
)


# =============================================================================
# get_env_int テスト
# =============================================================================

class TestGetEnvInt:
    """get_env_int のテスト"""

    def test_default_when_not_set(self):
        """環境変数未設定でデフォルト値を返す"""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TEST_INT_VAR", None)
            assert get_env_int("TEST_INT_VAR", default=42) == 42

    def test_parse_valid_int(self):
        """正常な整数値をパースする"""
        with patch.dict(os.environ, {"TEST_INT_VAR": "100"}, clear=False):
            assert get_env_int("TEST_INT_VAR", default=0) == 100

    def test_invalid_int_raises_config_error(self):
        """非整数値でConfigErrorを送出"""
        with patch.dict(os.environ, {"TEST_INT_VAR": "abc"}, clear=False):
            with pytest.raises(ConfigError, match="整数ではありません"):
                get_env_int("TEST_INT_VAR", default=0)

    def test_below_min_raises_config_error(self):
        """最小値未満でConfigErrorを送出"""
        with patch.dict(os.environ, {"TEST_INT_VAR": "0"}, clear=False):
            with pytest.raises(ConfigError, match="最小値"):
                get_env_int("TEST_INT_VAR", default=5, min_val=1)

    def test_above_max_raises_config_error(self):
        """最大値超過でConfigErrorを送出"""
        with patch.dict(os.environ, {"TEST_INT_VAR": "200"}, clear=False):
            with pytest.raises(ConfigError, match="最大値"):
                get_env_int("TEST_INT_VAR", default=5, max_val=100)

    def test_exact_min_value_accepted(self):
        """最小値ちょうどは受け入れる"""
        with patch.dict(os.environ, {"TEST_INT_VAR": "1"}, clear=False):
            assert get_env_int("TEST_INT_VAR", default=5, min_val=1) == 1

    def test_exact_max_value_accepted(self):
        """最大値ちょうどは受け入れる"""
        with patch.dict(os.environ, {"TEST_INT_VAR": "50"}, clear=False):
            assert get_env_int("TEST_INT_VAR", default=5, max_val=50) == 50

    def test_negative_value(self):
        """負の整数値をパースする"""
        with patch.dict(os.environ, {"TEST_INT_VAR": "-5"}, clear=False):
            assert get_env_int("TEST_INT_VAR", default=0) == -5

    def test_float_string_raises_config_error(self):
        """浮動小数点文字列でConfigErrorを送出"""
        with patch.dict(os.environ, {"TEST_INT_VAR": "3.14"}, clear=False):
            with pytest.raises(ConfigError):
                get_env_int("TEST_INT_VAR", default=0)

    def test_empty_string_raises_config_error(self):
        """空文字列でConfigErrorを送出"""
        with patch.dict(os.environ, {"TEST_INT_VAR": ""}, clear=False):
            with pytest.raises(ConfigError):
                get_env_int("TEST_INT_VAR", default=0)


# =============================================================================
# get_env_bool テスト
# =============================================================================

class TestGetEnvBool:
    """get_env_bool のテスト"""

    def test_default_when_not_set(self):
        """環境変数未設定でデフォルト値を返す"""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TEST_BOOL_VAR", None)
            assert get_env_bool("TEST_BOOL_VAR", default=True) is True
            assert get_env_bool("TEST_BOOL_VAR", default=False) is False

    @pytest.mark.parametrize("value", ["true", "True", "TRUE", "1", "yes", "on"])
    def test_truthy_values(self, value):
        """真として認識される値"""
        with patch.dict(os.environ, {"TEST_BOOL_VAR": value}, clear=False):
            assert get_env_bool("TEST_BOOL_VAR") is True

    @pytest.mark.parametrize("value", ["false", "False", "FALSE", "0", "no", "off"])
    def test_falsy_values(self, value):
        """偽として認識される値"""
        with patch.dict(os.environ, {"TEST_BOOL_VAR": value}, clear=False):
            assert get_env_bool("TEST_BOOL_VAR") is False

    def test_invalid_bool_raises_config_error(self):
        """不正な値でConfigErrorを送出"""
        with patch.dict(os.environ, {"TEST_BOOL_VAR": "maybe"}, clear=False):
            with pytest.raises(ConfigError, match="真偽値ではありません"):
                get_env_bool("TEST_BOOL_VAR")

    def test_empty_string_raises_config_error(self):
        """空文字列でConfigErrorを送出"""
        with patch.dict(os.environ, {"TEST_BOOL_VAR": ""}, clear=False):
            with pytest.raises(ConfigError):
                get_env_bool("TEST_BOOL_VAR")


# =============================================================================
# get_env_str テスト
# =============================================================================

class TestGetEnvStr:
    """get_env_str のテスト"""

    def test_default_when_not_set(self):
        """環境変数未設定でデフォルト値を返す"""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TEST_STR_VAR", None)
            assert get_env_str("TEST_STR_VAR", default="default") == "default"

    def test_returns_set_value(self):
        """設定済みの値を返す"""
        with patch.dict(os.environ, {"TEST_STR_VAR": "hello"}, clear=False):
            assert get_env_str("TEST_STR_VAR") == "hello"

    def test_allowed_values_accepted(self):
        """許容値リスト内の値は受け入れる"""
        with patch.dict(os.environ, {"TEST_STR_VAR": "AZURE"}, clear=False):
            result = get_env_str(
                "TEST_STR_VAR", allowed_values=["AZURE", "AWS", "GCP"]
            )
            assert result == "AZURE"

    def test_disallowed_value_raises_config_error(self):
        """許容値リスト外の値でConfigErrorを送出"""
        with patch.dict(os.environ, {"TEST_STR_VAR": "INVALID"}, clear=False):
            with pytest.raises(ConfigError, match="許容されない値"):
                get_env_str(
                    "TEST_STR_VAR", allowed_values=["AZURE", "AWS", "GCP"]
                )

    def test_none_default_when_not_set(self):
        """デフォルトNoneで未設定ならNoneを返す"""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TEST_STR_VAR", None)
            assert get_env_str("TEST_STR_VAR") is None


# =============================================================================
# 証憑ファイル制限定数テスト
# =============================================================================

class TestEvidenceConfigConstants:
    """モジュールレベル定数のデフォルト値テスト"""

    def test_default_max_file_size(self):
        """MAX_EVIDENCE_FILE_SIZE_MB のデフォルト値"""
        from infrastructure.config import MAX_EVIDENCE_FILE_SIZE_MB
        assert MAX_EVIDENCE_FILE_SIZE_MB == 10

    def test_default_max_file_count(self):
        """MAX_EVIDENCE_FILE_COUNT のデフォルト値"""
        from infrastructure.config import MAX_EVIDENCE_FILE_COUNT
        assert MAX_EVIDENCE_FILE_COUNT == 20

    def test_default_max_total_size(self):
        """MAX_EVIDENCE_TOTAL_SIZE_MB のデフォルト値"""
        from infrastructure.config import MAX_EVIDENCE_TOTAL_SIZE_MB
        assert MAX_EVIDENCE_TOTAL_SIZE_MB == 50

    def test_default_enable_screening(self):
        """ENABLE_EVIDENCE_SCREENING のデフォルト値"""
        from infrastructure.config import ENABLE_EVIDENCE_SCREENING
        assert ENABLE_EVIDENCE_SCREENING is True

    def test_default_screening_use_llm(self):
        """EVIDENCE_SCREENING_USE_LLM のデフォルト値"""
        from infrastructure.config import EVIDENCE_SCREENING_USE_LLM
        assert EVIDENCE_SCREENING_USE_LLM is False
