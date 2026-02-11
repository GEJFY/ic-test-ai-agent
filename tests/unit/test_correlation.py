"""
相関ID管理機能のユニットテスト

correlation.pyの機能をテストします。
"""
import pytest
import uuid
from contextvars import ContextVar

# テスト対象のモジュールをインポート
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.correlation import (
    get_or_create_correlation_id,
    get_correlation_id,
    set_correlation_id,
    correlation_id_var
)


class TestCorrelationID:
    """相関ID管理のテストクラス"""

    def setup_method(self):
        """各テストの前にContextVarをクリア"""
        correlation_id_var.set(None)

    def test_get_or_create_correlation_id_from_header(self):
        """
        ヘッダーから相関IDを取得できることを確認
        """
        # X-Correlation-IDヘッダーが存在する場合
        headers = {"X-Correlation-ID": "test-correlation-id-123"}
        correlation_id = get_or_create_correlation_id(headers)

        assert correlation_id == "test-correlation-id-123"
        assert get_correlation_id() == "test-correlation-id-123"

    def test_get_or_create_correlation_id_case_insensitive(self):
        """
        ヘッダー名が小文字でも相関IDを取得できることを確認
        """
        # 小文字のヘッダー名
        headers = {"x-correlation-id": "test-correlation-id-456"}
        correlation_id = get_or_create_correlation_id(headers)

        assert correlation_id == "test-correlation-id-456"
        assert get_correlation_id() == "test-correlation-id-456"

    def test_get_or_create_correlation_id_generate(self):
        """
        ヘッダーに相関IDがない場合、新規生成されることを確認
        """
        headers = {}
        correlation_id = get_or_create_correlation_id(headers)

        # UUID形式であることを確認
        assert correlation_id is not None
        assert len(correlation_id) == 36  # UUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        assert "-" in correlation_id

        # ContextVarに設定されていることを確認
        assert get_correlation_id() == correlation_id

    def test_get_or_create_correlation_id_empty_header_value(self):
        """
        ヘッダーに空の相関IDがある場合、新規生成されることを確認
        """
        headers = {"X-Correlation-ID": ""}
        correlation_id = get_or_create_correlation_id(headers)

        # 空文字列の場合は新規生成される
        assert correlation_id is not None
        assert len(correlation_id) == 36
        assert correlation_id != ""

    def test_get_correlation_id_when_not_set(self):
        """
        相関IDが設定されていない場合、Noneが返されることを確認
        """
        # ContextVarをクリア
        correlation_id_var.set(None)

        correlation_id = get_correlation_id()
        assert correlation_id is None

    def test_get_correlation_id_when_set(self):
        """
        相関IDが設定されている場合、正しく取得できることを確認
        """
        test_id = "manual-test-id-789"
        set_correlation_id(test_id)

        correlation_id = get_correlation_id()
        assert correlation_id == test_id

    def test_set_correlation_id(self):
        """
        set_correlation_idで相関IDを明示的に設定できることを確認
        """
        test_id = str(uuid.uuid4())
        set_correlation_id(test_id)

        assert get_correlation_id() == test_id

    def test_correlation_id_isolation_between_contexts(self):
        """
        ContextVarによりコンテキスト間で相関IDが分離されることを確認

        Note: この簡易テストでは単一コンテキストのみテスト
        実際のマルチスレッド環境では自動的に分離される
        """
        # 最初の相関ID設定
        correlation_id_1 = "context-1-id"
        set_correlation_id(correlation_id_1)
        assert get_correlation_id() == correlation_id_1

        # 別の相関IDに上書き
        correlation_id_2 = "context-2-id"
        set_correlation_id(correlation_id_2)
        assert get_correlation_id() == correlation_id_2

    def test_multiple_header_formats(self):
        """
        様々なヘッダー形式で相関IDを取得できることを確認
        """
        # 大文字
        headers1 = {"X-CORRELATION-ID": "uppercase-id"}
        correlation_id_var.set(None)
        assert get_or_create_correlation_id(headers1) == "uppercase-id"

        # 小文字
        headers2 = {"x-correlation-id": "lowercase-id"}
        correlation_id_var.set(None)
        assert get_or_create_correlation_id(headers2) == "lowercase-id"

        # 混合
        headers3 = {"X-Correlation-Id": "mixedcase-id"}
        correlation_id_var.set(None)
        assert get_or_create_correlation_id(headers3) == "mixedcase-id"

    def test_get_or_create_correlation_id_preserves_existing(self):
        """
        既に設定されている相関IDがあっても、ヘッダーの値を優先することを確認
        """
        # まず相関IDを設定
        set_correlation_id("existing-id")

        # ヘッダーに別の相関IDがある場合、それが優先される
        headers = {"X-Correlation-ID": "new-id-from-header"}
        correlation_id = get_or_create_correlation_id(headers)

        assert correlation_id == "new-id-from-header"
        assert get_correlation_id() == "new-id-from-header"

    def test_correlation_id_format_validation(self):
        """
        生成される相関IDの形式が正しいことを確認
        """
        headers = {}
        correlation_id = get_or_create_correlation_id(headers)

        # UUIDとしてパースできることを確認
        try:
            parsed_uuid = uuid.UUID(correlation_id)
            assert str(parsed_uuid) == correlation_id
        except ValueError:
            pytest.fail(f"Generated correlation ID is not a valid UUID: {correlation_id}")

    def test_get_or_create_with_special_characters(self):
        """
        特殊文字を含む相関IDも正しく処理できることを確認
        """
        special_id = "test_id-2024@01:01"
        headers = {"X-Correlation-ID": special_id}
        correlation_id = get_or_create_correlation_id(headers)

        assert correlation_id == special_id
        assert get_correlation_id() == special_id

    def test_correlation_id_consistency_across_calls(self):
        """
        同じコンテキスト内で相関IDが一貫していることを確認
        """
        headers = {"X-Correlation-ID": "consistent-id"}
        correlation_id_1 = get_or_create_correlation_id(headers)
        correlation_id_2 = get_correlation_id()
        correlation_id_3 = get_correlation_id()

        assert correlation_id_1 == correlation_id_2 == correlation_id_3


# pytest実行時のエントリポイント
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
