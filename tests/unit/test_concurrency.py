"""
並行処理のスレッドセーフ性テスト

グローバルシングルトンの初期化がスレッドセーフであることを検証します。
"""

import threading
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestJobManagerThreadSafety:
    """get_job_manager() のスレッドセーフ性テスト"""

    def test_singleton_returns_same_instance(self):
        """同一インスタンスが返されることを確認"""
        import core.async_handlers as module

        mock_manager = MagicMock()
        module._job_manager = mock_manager

        try:
            result1 = module.get_job_manager()
            result2 = module.get_job_manager()
            assert result1 is result2
        finally:
            module._job_manager = None

    def test_concurrent_initialization_creates_single_instance(self):
        """並行呼び出しでもインスタンスが1つだけ作成されることを確認"""
        import core.async_handlers as module
        module._job_manager = None

        init_count = {"count": 0}
        instances = []
        errors = []

        mock_storage = MagicMock()
        mock_queue = MagicMock()

        original_init = module.AsyncJobManager.__init__

        def counting_init(self, storage, queue=None):
            init_count["count"] += 1
            original_init(self, storage, queue)

        def call_get_manager():
            try:
                mgr = module.get_job_manager()
                instances.append(mgr)
            except Exception as e:
                errors.append(e)

        with patch("core.async_handlers.AsyncJobManager.__init__", counting_init):
            with patch("infrastructure.job_storage.get_job_storage", return_value=mock_storage):
                with patch("infrastructure.job_storage.get_job_queue", return_value=mock_queue):
                    threads = [threading.Thread(target=call_get_manager) for _ in range(20)]
                    for t in threads:
                        t.start()
                    for t in threads:
                        t.join()

        try:
            assert len(errors) == 0, f"Errors during init: {errors}"
            assert len(instances) == 20
            # 全スレッドが同一インスタンスを取得
            assert all(inst is instances[0] for inst in instances)
            # __init__は1回だけ呼ばれる
            assert init_count["count"] == 1
        finally:
            module._job_manager = None


class TestSecretProviderThreadSafety:
    """get_default_provider() のスレッドセーフ性テスト"""

    def test_concurrent_initialization_creates_single_provider(self):
        """並行呼び出しでもプロバイダーが1つだけ作成されることを確認"""
        from infrastructure.secrets.secrets_provider import (
            get_default_provider,
            EnvironmentSecretProvider,
        )
        import infrastructure.secrets.secrets_provider as module

        module._global_provider = None

        providers = []
        errors = []

        def call_get_provider():
            try:
                p = get_default_provider()
                providers.append(p)
            except Exception as e:
                errors.append(e)

        with patch.dict("os.environ", {"SECRET_PROVIDER": "env"}):  # pragma: allowlist secret
            threads = [threading.Thread(target=call_get_provider) for _ in range(20)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        try:
            assert len(errors) == 0, f"Errors: {errors}"
            assert len(providers) == 20
            assert all(p is providers[0] for p in providers)
            assert isinstance(providers[0], EnvironmentSecretProvider)
        finally:
            module._global_provider = None


class TestJobSubmissionValidation:
    """submit_job() の入力バリデーションテスト"""

    @pytest.fixture
    def manager(self):
        from core.async_job_manager import AsyncJobManager
        storage = AsyncMock()
        return AsyncJobManager(storage=storage)

    @pytest.mark.asyncio
    async def test_empty_items_rejected(self, manager):
        """空のitemsリストは拒否される"""
        with pytest.raises(ValueError, match="空にできません"):
            await manager.submit_job("tenant-1", [])

    @pytest.mark.asyncio
    async def test_non_list_items_rejected(self, manager):
        """リスト以外のitemsは拒否される"""
        with pytest.raises(ValueError, match="リストで指定"):
            await manager.submit_job("tenant-1", "not-a-list")

    @pytest.mark.asyncio
    async def test_empty_tenant_id_rejected(self, manager):
        """空のtenant_idは拒否される"""
        with pytest.raises(ValueError, match="tenant_id"):
            await manager.submit_job("", [{"ID": "1"}])

    @pytest.mark.asyncio
    async def test_too_long_tenant_id_rejected(self, manager):
        """長すぎるtenant_idは拒否される"""
        with pytest.raises(ValueError, match="tenant_id"):
            await manager.submit_job("x" * 256, [{"ID": "1"}])

    @pytest.mark.asyncio
    async def test_non_dict_item_rejected(self, manager):
        """辞書でないitemは拒否される"""
        with pytest.raises(ValueError, match="辞書で指定"):
            await manager.submit_job("tenant-1", ["not-a-dict"])

    @pytest.mark.asyncio
    async def test_too_many_items_rejected(self, manager):
        """アイテム数上限超過は拒否される"""
        items = [{"ID": str(i)} for i in range(1001)]
        with pytest.raises(ValueError, match="上限を超えています"):
            await manager.submit_job("tenant-1", items)

    @pytest.mark.asyncio
    async def test_valid_submission_passes(self, manager):
        """正常な入力はバリデーションを通過する"""
        from core.async_job_manager import EvaluationJob, JobStatus

        mock_job = EvaluationJob(
            job_id="test-id",
            tenant_id="tenant-1",
            status=JobStatus.PENDING,
            items=[{"ID": "1"}]
        )
        manager.storage.create_job = AsyncMock(return_value=mock_job)

        response = await manager.submit_job("tenant-1", [{"ID": "1"}])
        assert response.job_id == "test-id"
        assert response.status == "pending"


class TestConfigValidation:
    """環境変数バリデーションヘルパーのテスト"""

    def test_get_env_int_valid(self):
        from infrastructure.config import get_env_int
        with patch.dict("os.environ", {"TEST_INT": "42"}):
            assert get_env_int("TEST_INT", default=0) == 42

    def test_get_env_int_default(self):
        from infrastructure.config import get_env_int
        with patch.dict("os.environ", {}, clear=True):
            assert get_env_int("MISSING_INT", default=10) == 10

    def test_get_env_int_invalid_raises(self):
        from infrastructure.config import get_env_int, ConfigError
        with patch.dict("os.environ", {"TEST_INT": "abc"}):
            with pytest.raises(ConfigError, match="整数ではありません"):
                get_env_int("TEST_INT", default=0)

    def test_get_env_int_below_min_raises(self):
        from infrastructure.config import get_env_int, ConfigError
        with patch.dict("os.environ", {"TEST_INT": "-1"}):
            with pytest.raises(ConfigError, match="最小値"):
                get_env_int("TEST_INT", default=0, min_val=0)

    def test_get_env_int_above_max_raises(self):
        from infrastructure.config import get_env_int, ConfigError
        with patch.dict("os.environ", {"TEST_INT": "100"}):
            with pytest.raises(ConfigError, match="最大値"):
                get_env_int("TEST_INT", default=0, max_val=50)

    def test_get_env_bool_true_values(self):
        from infrastructure.config import get_env_bool
        for val in ["true", "1", "yes", "on", "True", "YES"]:
            with patch.dict("os.environ", {"TEST_BOOL": val}):
                assert get_env_bool("TEST_BOOL") is True

    def test_get_env_bool_false_values(self):
        from infrastructure.config import get_env_bool
        for val in ["false", "0", "no", "off", "False", "NO"]:
            with patch.dict("os.environ", {"TEST_BOOL": val}):
                assert get_env_bool("TEST_BOOL") is False

    def test_get_env_bool_invalid_raises(self):
        from infrastructure.config import get_env_bool, ConfigError
        with patch.dict("os.environ", {"TEST_BOOL": "maybe"}):
            with pytest.raises(ConfigError, match="真偽値ではありません"):
                get_env_bool("TEST_BOOL")

    def test_get_env_str_allowed_values(self):
        from infrastructure.config import get_env_str, ConfigError
        with patch.dict("os.environ", {"TEST_STR": "invalid"}):
            with pytest.raises(ConfigError, match="許容されない値"):
                get_env_str("TEST_STR", allowed_values=["a", "b"])
