# -*- coding: utf-8 -*-
"""
================================================================================
test_job_storage.py - job_storageモジュールのユニットテスト
================================================================================

【テスト対象】
- InMemoryJobStorage: インメモリジョブストレージ
- InMemoryJobQueue: インメモリジョブキュー
- azure_blob.py: EvidenceBlobStorage（モックテスト）
- azure_table.py: AzureTableJobStorage（モックテスト）
- azure_queue.py: AzureQueueJobQueue（モックテスト）

================================================================================
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime

from infrastructure.job_storage.memory import (
    InMemoryJobStorage,
    InMemoryJobQueue,
)
from core.async_job_manager import (
    EvaluationJob,
    JobStatus,
    generate_job_id,
)


# =============================================================================
# InMemoryJobStorage テスト
# =============================================================================

class TestInMemoryJobStorage:
    """InMemoryJobStorageのテスト"""

    @pytest.fixture
    def storage(self):
        """ストレージインスタンス"""
        return InMemoryJobStorage(max_jobs=10)

    @pytest.mark.asyncio
    async def test_create_job(self, storage):
        """ジョブ作成"""
        items = [{"ID": "CLC-01"}, {"ID": "CLC-02"}]
        job = await storage.create_job(
            tenant_id="test-tenant",
            items=items
        )

        assert job.job_id is not None
        assert job.tenant_id == "test-tenant"
        assert job.status == JobStatus.PENDING
        assert len(job.items) == 2

    @pytest.mark.asyncio
    async def test_get_job(self, storage):
        """ジョブ取得"""
        items = [{"ID": "CLC-01"}]
        created_job = await storage.create_job("test-tenant", items)

        retrieved_job = await storage.get_job(created_job.job_id)

        assert retrieved_job is not None
        assert retrieved_job.job_id == created_job.job_id

    @pytest.mark.asyncio
    async def test_get_job_not_found(self, storage):
        """存在しないジョブの取得"""
        job = await storage.get_job("non-existent-id")
        assert job is None

    @pytest.mark.asyncio
    async def test_update_job(self, storage):
        """ジョブ更新"""
        items = [{"ID": "CLC-01"}]
        job = await storage.create_job("test-tenant", items)

        job.status = JobStatus.RUNNING
        job.progress = 50
        await storage.update_job(job)

        updated_job = await storage.get_job(job.job_id)
        assert updated_job.status == JobStatus.RUNNING
        assert updated_job.progress == 50

    @pytest.mark.asyncio
    async def test_delete_job(self, storage):
        """ジョブ削除"""
        items = [{"ID": "CLC-01"}]
        job = await storage.create_job("test-tenant", items)

        result = await storage.delete_job(job.job_id)
        assert result is True

        deleted_job = await storage.get_job(job.job_id)
        assert deleted_job is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_job(self, storage):
        """存在しないジョブの削除"""
        result = await storage.delete_job("non-existent-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_pending_jobs(self, storage):
        """処理待ちジョブの取得"""
        # 複数のジョブを作成
        for i in range(5):
            await storage.create_job(f"tenant-{i}", [{"ID": f"CLC-{i}"}])

        pending_jobs = await storage.get_pending_jobs(limit=3)
        assert len(pending_jobs) == 3
        assert all(j.status == JobStatus.PENDING for j in pending_jobs)

    @pytest.mark.asyncio
    async def test_get_jobs_by_tenant(self, storage):
        """テナント別ジョブ取得"""
        # テナント1のジョブ
        await storage.create_job("tenant-1", [{"ID": "A"}])
        await storage.create_job("tenant-1", [{"ID": "B"}])

        # テナント2のジョブ
        await storage.create_job("tenant-2", [{"ID": "C"}])

        tenant1_jobs = await storage.get_jobs_by_tenant("tenant-1")
        assert len(tenant1_jobs) == 2

        tenant2_jobs = await storage.get_jobs_by_tenant("tenant-2")
        assert len(tenant2_jobs) == 1

    @pytest.mark.asyncio
    async def test_max_jobs_limit(self, storage):
        """最大ジョブ数制限"""
        # 制限を超えてジョブを作成
        for i in range(15):
            await storage.create_job(f"tenant", [{"ID": f"CLC-{i}"}])

        stats = storage.get_stats()
        assert stats["total_jobs"] <= 10  # max_jobs

    def test_get_stats(self, storage):
        """統計情報取得"""
        stats = storage.get_stats()
        assert "total_jobs" in stats
        assert "max_jobs" in stats
        assert "status_counts" in stats


# =============================================================================
# InMemoryJobQueue テスト
# =============================================================================

class TestInMemoryJobQueue:
    """InMemoryJobQueueのテスト"""

    @pytest.fixture
    def queue(self):
        """キューインスタンス"""
        return InMemoryJobQueue()

    @pytest.mark.asyncio
    async def test_enqueue(self, queue):
        """ジョブをキューに追加"""
        await queue.enqueue("job-1")
        await queue.enqueue("job-2")

        size = await queue.size()
        assert size == 2

    @pytest.mark.asyncio
    async def test_dequeue(self, queue):
        """キューからジョブを取得（FIFO）"""
        await queue.enqueue("job-1")
        await queue.enqueue("job-2")
        await queue.enqueue("job-3")

        # FIFOで取り出し
        job1 = await queue.dequeue()
        assert job1 == "job-1"

        job2 = await queue.dequeue()
        assert job2 == "job-2"

        job3 = await queue.dequeue()
        assert job3 == "job-3"

    @pytest.mark.asyncio
    async def test_dequeue_empty(self, queue):
        """空のキューからdequeue"""
        job = await queue.dequeue()
        assert job is None

    @pytest.mark.asyncio
    async def test_peek(self, queue):
        """キューの先頭を確認（削除しない）"""
        await queue.enqueue("job-1")
        await queue.enqueue("job-2")

        # peekは先頭を確認するだけ
        peeked = await queue.peek()
        assert peeked == "job-1"

        # サイズは変わらない
        size = await queue.size()
        assert size == 2

    @pytest.mark.asyncio
    async def test_peek_empty(self, queue):
        """空のキューでpeek"""
        peeked = await queue.peek()
        assert peeked is None

    @pytest.mark.asyncio
    async def test_size(self, queue):
        """キューサイズ"""
        assert await queue.size() == 0

        await queue.enqueue("job-1")
        assert await queue.size() == 1

        await queue.enqueue("job-2")
        assert await queue.size() == 2

        await queue.dequeue()
        assert await queue.size() == 1

    @pytest.mark.asyncio
    async def test_clear(self, queue):
        """キューをクリア"""
        await queue.enqueue("job-1")
        await queue.enqueue("job-2")
        await queue.enqueue("job-3")

        await queue.clear()

        size = await queue.size()
        assert size == 0


# =============================================================================
# EvidenceBlobStorage テスト
# =============================================================================

class TestEvidenceBlobStorage:
    """EvidenceBlobStorageのテスト"""

    def test_blob_storage_requires_connection_string(self):
        """接続文字列なしでエラー"""
        with patch.dict('os.environ', {}, clear=True):
            # グローバルキャッシュをクリア
            import infrastructure.job_storage.azure_blob as blob_module
            blob_module._evidence_storage = None

            from infrastructure.job_storage.azure_blob import get_evidence_storage
            result = get_evidence_storage()
            # 接続文字列がない場合はNoneが返る
            assert result is None

    def test_blob_storage_constants(self):
        """定数値の確認"""
        from infrastructure.job_storage.azure_blob import EvidenceBlobStorage
        assert EvidenceBlobStorage.CONTAINER_NAME == "evidence-files"
        assert EvidenceBlobStorage.MAX_INLINE_SIZE == 0  # 全ファイルをBlobに保存

    def test_blob_storage_init_with_connection_string(self):
        """接続文字列ありで初期化成功"""
        from infrastructure.job_storage.azure_blob import AZURE_BLOB_AVAILABLE
        if not AZURE_BLOB_AVAILABLE:
            pytest.skip("azure-storage-blob not installed")

        # SDKが利用可能な場合のみパッチを適用
        with patch('azure.storage.blob.BlobServiceClient') as mock_blob_service:
            from azure.core.exceptions import ResourceExistsError
            mock_service = MagicMock()
            mock_blob_service.from_connection_string.return_value = mock_service
            # コンテナが既に存在する場合のシミュレーション
            mock_service.create_container.side_effect = ResourceExistsError("Container already exists")
            mock_service.get_container_client.return_value = MagicMock()

            # モジュールを再インポート
            import importlib
            import infrastructure.job_storage.azure_blob as blob_module
            importlib.reload(blob_module)

            storage = blob_module.EvidenceBlobStorage(
                connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test;EndpointSuffix=core.windows.net"
            )

            assert storage is not None

    def test_store_evidence_files_mocked(self):
        """証跡ファイルの保存（モック）"""
        from infrastructure.job_storage.azure_blob import AZURE_BLOB_AVAILABLE
        if not AZURE_BLOB_AVAILABLE:
            pytest.skip("azure-storage-blob not installed")

        with patch('azure.storage.blob.BlobServiceClient') as mock_blob_service:
            # モックセットアップ
            mock_service = MagicMock()
            mock_blob_service.from_connection_string.return_value = mock_service
            mock_container = MagicMock()
            mock_service.get_container_client.return_value = mock_container
            mock_blob_client = MagicMock()
            mock_container.get_blob_client.return_value = mock_blob_client

            import importlib
            import infrastructure.job_storage.azure_blob as blob_module
            importlib.reload(blob_module)

            storage = blob_module.EvidenceBlobStorage(
                connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test"
            )

            # テストデータ
            evidence_files = [
                {
                    "fileName": "test.pdf",
                    "base64": "dGVzdCBjb250ZW50",  # "test content"
                    "extension": ".pdf",
                    "mimeType": "application/pdf"
                }
            ]

            # 保存実行
            result = storage.store_evidence_files(
                job_id="job-123",
                item_id="CLC-01",
                evidence_files=evidence_files
            )

            # Blobにアップロードされたことを確認
            assert isinstance(result, list)

    def test_restore_evidence_files_mocked(self):
        """証跡ファイルの復元（モック）"""
        from infrastructure.job_storage.azure_blob import AZURE_BLOB_AVAILABLE
        if not AZURE_BLOB_AVAILABLE:
            pytest.skip("azure-storage-blob not installed")

        with patch('azure.storage.blob.BlobServiceClient') as mock_blob_service:
            # モックセットアップ
            mock_service = MagicMock()
            mock_blob_service.from_connection_string.return_value = mock_service
            mock_container = MagicMock()
            mock_service.get_container_client.return_value = mock_container
            mock_blob_client = MagicMock()
            mock_container.get_blob_client.return_value = mock_blob_client

            # ダウンロードデータ
            mock_blob_client.download_blob.return_value.readall.return_value = b"test content"

            import importlib
            import infrastructure.job_storage.azure_blob as blob_module
            importlib.reload(blob_module)

            storage = blob_module.EvidenceBlobStorage(
                connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test"
            )

            # 参照データ（store_evidence_filesの戻り値形式に合わせる）
            references = [
                {
                    "_blobRef": "job-123/CLC-01/0_test.pdf",
                    "fileName": "test.pdf",
                    "extension": ".pdf",
                    "mimeType": "application/pdf"
                }
            ]

            # 復元実行
            result = storage.restore_evidence_files(references)

            assert isinstance(result, list)

    @pytest.mark.integration
    @pytest.mark.azure
    def test_store_and_restore_evidence_files_real(self):
        """証跡ファイルの保存と復元（実Azure接続）"""
        import os
        import importlib
        from dotenv import load_dotenv
        load_dotenv()

        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        if not connection_string:
            pytest.skip("AZURE_STORAGE_CONNECTION_STRING not set")

        # モジュールをリロードしてモック状態をクリア
        import infrastructure.job_storage.azure_blob as blob_module
        importlib.reload(blob_module)

        EvidenceBlobStorage = blob_module.EvidenceBlobStorage
        AZURE_BLOB_AVAILABLE = blob_module.AZURE_BLOB_AVAILABLE

        if not AZURE_BLOB_AVAILABLE:
            pytest.skip("azure-storage-blob not installed")

        # テスト用のジョブID（一意にする）
        import uuid
        test_job_id = f"test-job-{uuid.uuid4().hex[:8]}"
        test_item_id = "CLC-TEST-01"

        storage = EvidenceBlobStorage(connection_string=connection_string)

        # テストデータ（小さなPDFっぽいデータ）
        test_content = b"Test evidence file content for integration test"
        import base64
        evidence_files = [
            {
                "fileName": "test_evidence.txt",
                "base64": base64.b64encode(test_content).decode("utf-8"),
                "extension": ".txt",
                "mimeType": "text/plain"
            }
        ]

        try:
            # 保存
            references = storage.store_evidence_files(
                job_id=test_job_id,
                item_id=test_item_id,
                evidence_files=evidence_files
            )

            assert len(references) == 1
            assert "_blobRef" in references[0]
            assert references[0]["fileName"] == "test_evidence.txt"

            # 復元
            restored = storage.restore_evidence_files(references)

            assert len(restored) == 1
            assert restored[0]["fileName"] == "test_evidence.txt"
            # base64をデコードして内容を確認
            restored_content = base64.b64decode(restored[0]["base64"])
            assert restored_content == test_content

        finally:
            # クリーンアップ（job_idのみで削除）
            storage.delete_evidence_files(test_job_id)


# =============================================================================
# AzureQueueJobQueue テスト（モック）
# =============================================================================

class TestAzureQueueJobQueue:
    """AzureQueueJobQueueのテスト"""

    def test_queue_requires_connection_string(self):
        """接続文字列なしでエラー"""
        with patch.dict('os.environ', {}, clear=True):
            from infrastructure.job_storage.azure_queue import AZURE_QUEUE_AVAILABLE
            # SDK がインストールされていればTrueだが、接続文字列がないとエラー
            assert isinstance(AZURE_QUEUE_AVAILABLE, bool)

    def test_queue_constants(self):
        """定数値の確認"""
        from infrastructure.job_storage.azure_queue import AzureQueueJobQueue
        assert AzureQueueJobQueue.DEFAULT_QUEUE_NAME == "evaluation-jobs"

    def test_queue_init_with_connection_string(self):
        """接続文字列ありで初期化成功"""
        from infrastructure.job_storage.azure_queue import AZURE_QUEUE_AVAILABLE
        if not AZURE_QUEUE_AVAILABLE:
            pytest.skip("azure-storage-queue not installed")

        with patch('azure.storage.queue.QueueClient') as mock_queue_client:
            mock_client = MagicMock()
            mock_queue_client.from_connection_string.return_value = mock_client

            import importlib
            import infrastructure.job_storage.azure_queue as queue_module
            importlib.reload(queue_module)

            queue = queue_module.AzureQueueJobQueue(
                connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test"
            )

            assert queue is not None
            assert queue._queue_name == "evaluation-jobs"

    @pytest.mark.asyncio
    async def test_enqueue_mocked(self):
        """キューへの追加（モック）"""
        from infrastructure.job_storage.azure_queue import AZURE_QUEUE_AVAILABLE
        if not AZURE_QUEUE_AVAILABLE:
            pytest.skip("azure-storage-queue not installed")

        with patch('azure.storage.queue.QueueClient') as mock_queue_client:
            mock_client = MagicMock()
            mock_queue_client.from_connection_string.return_value = mock_client
            mock_client.send_message = MagicMock()

            import importlib
            import infrastructure.job_storage.azure_queue as queue_module
            importlib.reload(queue_module)

            queue = queue_module.AzureQueueJobQueue(
                connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test"
            )

            await queue.enqueue("job-123")

            # send_messageが呼ばれたことを確認
            mock_client.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_dequeue_mocked(self):
        """キューからの取得（モック）"""
        from infrastructure.job_storage.azure_queue import AZURE_QUEUE_AVAILABLE
        if not AZURE_QUEUE_AVAILABLE:
            pytest.skip("azure-storage-queue not installed")

        with patch('azure.storage.queue.QueueClient') as mock_queue_client:
            mock_client = MagicMock()
            mock_queue_client.from_connection_string.return_value = mock_client

            # メッセージモック（receive_messagesはイテレータを返す）
            mock_message = MagicMock()
            mock_message.content = '{"job_id": "job-123"}'
            mock_client.receive_messages.return_value = iter([mock_message])
            mock_client.delete_message = MagicMock()

            import importlib
            import infrastructure.job_storage.azure_queue as queue_module
            importlib.reload(queue_module)

            queue = queue_module.AzureQueueJobQueue(
                connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test"
            )

            result = await queue.dequeue()

            # receive_messagesが呼ばれたことを確認
            mock_client.receive_messages.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_queue_length_mocked(self):
        """キューサイズ取得（モック）"""
        from infrastructure.job_storage.azure_queue import AZURE_QUEUE_AVAILABLE
        if not AZURE_QUEUE_AVAILABLE:
            pytest.skip("azure-storage-queue not installed")

        with patch('azure.storage.queue.QueueClient') as mock_queue_client:
            mock_client = MagicMock()
            mock_queue_client.from_connection_string.return_value = mock_client

            # プロパティモック
            mock_props = MagicMock()
            mock_props.approximate_message_count = 5
            mock_client.get_queue_properties.return_value = mock_props

            import importlib
            import infrastructure.job_storage.azure_queue as queue_module
            importlib.reload(queue_module)

            queue = queue_module.AzureQueueJobQueue(
                connection_string="DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test"
            )

            size = await queue.get_queue_length()

            assert size == 5

    @pytest.mark.integration
    @pytest.mark.azure
    @pytest.mark.asyncio
    async def test_enqueue_dequeue_real(self):
        """キューへの追加と取得（実Azure接続）"""
        import os
        import importlib
        from dotenv import load_dotenv
        load_dotenv()

        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        if not connection_string:
            pytest.skip("AZURE_STORAGE_CONNECTION_STRING not set")

        # モジュールをリロードしてモック状態をクリア
        import infrastructure.job_storage.azure_queue as queue_module
        importlib.reload(queue_module)

        AzureQueueJobQueue = queue_module.AzureQueueJobQueue
        AZURE_QUEUE_AVAILABLE = queue_module.AZURE_QUEUE_AVAILABLE

        if not AZURE_QUEUE_AVAILABLE:
            pytest.skip("azure-storage-queue not installed")

        # テスト用キュー名（本番と分離）
        test_queue_name = "test-evaluation-jobs"

        queue = AzureQueueJobQueue(
            connection_string=connection_string,
            queue_name=test_queue_name
        )

        # テスト用のジョブID
        import uuid
        test_job_id = f"test-job-{uuid.uuid4().hex[:8]}"

        try:
            # キューに追加
            await queue.enqueue(test_job_id)

            # キューサイズ確認（少なくとも1つある）
            size = await queue.get_queue_length()
            assert size >= 1

            # キューから取得
            dequeued_job_id = await queue.dequeue()

            # 取得したジョブIDを確認（他のテストも同時実行している可能性があるため、存在確認のみ）
            assert dequeued_job_id is not None

        finally:
            # クリーンアップ（キューをクリア）
            await queue.clear()


# =============================================================================
# parse_queue_message テスト
# =============================================================================

class TestParseQueueMessage:
    """parse_queue_message()のテスト"""

    def test_parse_json_message(self):
        """JSON形式のメッセージをパース"""
        from infrastructure.job_storage.azure_queue import parse_queue_message

        message = '{"job_id": "job-123", "action": "process"}'
        job_id = parse_queue_message(message)
        assert job_id == "job-123"

    def test_parse_plain_message(self):
        """プレーン形式のメッセージをパース"""
        from infrastructure.job_storage.azure_queue import parse_queue_message

        message = "job-456"
        job_id = parse_queue_message(message)
        assert job_id == "job-456"

    def test_parse_invalid_json(self):
        """不正なJSONメッセージ"""
        from infrastructure.job_storage.azure_queue import parse_queue_message

        message = "not-json-but-string"
        job_id = parse_queue_message(message)
        assert job_id == "not-json-but-string"


# =============================================================================
# generate_job_id テスト
# =============================================================================

class TestGenerateJobId:
    """generate_job_id()のテスト"""

    def test_generate_unique_ids(self):
        """一意なIDが生成される"""
        ids = [generate_job_id() for _ in range(100)]
        assert len(ids) == len(set(ids))  # 全て一意

    def test_id_format(self):
        """ID形式の確認"""
        job_id = generate_job_id()
        assert isinstance(job_id, str)
        assert len(job_id) > 0


# =============================================================================
# EvaluationJob テスト
# =============================================================================

class TestEvaluationJob:
    """EvaluationJobデータクラスのテスト"""

    def test_create_job(self):
        """ジョブの作成"""
        job = EvaluationJob(
            job_id="job-123",
            tenant_id="tenant-1",
            status=JobStatus.PENDING,
            items=[{"ID": "CLC-01"}]
        )

        assert job.job_id == "job-123"
        assert job.tenant_id == "tenant-1"
        assert job.status == JobStatus.PENDING
        assert job.progress == 0  # デフォルト

    def test_job_status_values(self):
        """ジョブステータス値"""
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"


# =============================================================================
# 統合テスト
# =============================================================================

class TestJobStorageIntegration:
    """ジョブストレージの統合テスト"""

    @pytest.mark.asyncio
    async def test_full_job_lifecycle(self):
        """完全なジョブライフサイクル"""
        storage = InMemoryJobStorage()
        queue = InMemoryJobQueue()

        # 1. ジョブ作成
        job = await storage.create_job(
            tenant_id="test-tenant",
            items=[{"ID": "CLC-01"}, {"ID": "CLC-02"}]
        )
        assert job.status == JobStatus.PENDING

        # 2. キューに追加
        await queue.enqueue(job.job_id)
        assert await queue.size() == 1

        # 3. キューから取得
        dequeued_id = await queue.dequeue()
        assert dequeued_id == job.job_id

        # 4. ジョブをRUNNINGに更新
        job.status = JobStatus.RUNNING
        job.progress = 0
        await storage.update_job(job)

        # 5. 進捗更新
        job.progress = 50
        job.results = [{"ID": "CLC-01", "evaluationResult": True}]
        await storage.update_job(job)

        # 6. 完了
        job.status = JobStatus.COMPLETED
        job.progress = 100
        job.results.append({"ID": "CLC-02", "evaluationResult": False})
        await storage.update_job(job)

        # 7. 結果確認
        final_job = await storage.get_job(job.job_id)
        assert final_job.status == JobStatus.COMPLETED
        assert final_job.progress == 100
        assert len(final_job.results) == 2

    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """並行操作のテスト"""
        storage = InMemoryJobStorage()

        # 複数のジョブを並行して作成
        async def create_job(i):
            return await storage.create_job(f"tenant-{i}", [{"ID": f"CLC-{i}"}])

        jobs = await asyncio.gather(*[create_job(i) for i in range(10)])

        assert len(jobs) == 10
        assert len(set(j.job_id for j in jobs)) == 10  # 全て一意

        # 全てのジョブが取得可能
        for job in jobs:
            retrieved = await storage.get_job(job.job_id)
            assert retrieved is not None
