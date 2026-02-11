# -*- coding: utf-8 -*-
"""
================================================================================
test_job_storage_aws_gcp.py - AWS/GCP ジョブストレージ・キューのユニットテスト
================================================================================

【テスト対象】
- AWSDynamoDBJobStorage (aws_dynamodb.py)
- AWSSQSJobQueue (aws_sqs.py) + ユーティリティ関数
- GCPFirestoreJobStorage (gcp_firestore.py)
- GCPCloudTasksJobQueue (gcp_tasks.py) + ユーティリティ関数

================================================================================
"""

import pytest
import json
import sys
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch, MagicMock, PropertyMock


# =============================================================================
# AWS DynamoDB テスト
# =============================================================================

class TestAWSDynamoDB:
    """AWSDynamoDBJobStorage のテスト"""

    def _make_storage(self):
        """モック付きストレージを作成"""
        mock_boto3 = MagicMock()
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session

        mock_dynamodb = MagicMock()
        mock_table = MagicMock()
        mock_table.load.return_value = None  # テーブル存在
        mock_dynamodb.Table.return_value = mock_table
        mock_session.resource.return_value = mock_dynamodb

        # botocore.exceptions.ClientError もモック
        mock_botocore = MagicMock()
        mock_client_error = type("ClientError", (Exception,), {})
        mock_botocore.exceptions.ClientError = mock_client_error

        with patch.dict("sys.modules", {
            "boto3": mock_boto3,
            "botocore": mock_botocore,
            "botocore.exceptions": mock_botocore.exceptions,
        }):
            # モジュールをリロード
            if "infrastructure.job_storage.aws_dynamodb" in sys.modules:
                del sys.modules["infrastructure.job_storage.aws_dynamodb"]
            from infrastructure.job_storage.aws_dynamodb import AWSDynamoDBJobStorage
            storage = AWSDynamoDBJobStorage(region="us-east-1", table_name="TestJobs")

        return storage, mock_table

    def test_init(self):
        """初期化"""
        storage, mock_table = self._make_storage()
        assert storage._region == "us-east-1"
        assert storage._table_name == "TestJobs"
        mock_table.load.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_job(self):
        """ジョブ作成"""
        storage, mock_table = self._make_storage()
        job = await storage.create_job("tenant-a", [{"ID": "CLC-01"}])
        assert job.tenant_id == "tenant-a"
        assert len(job.items) == 1
        mock_table.put_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_job_found(self):
        """ジョブ取得（存在する）"""
        storage, mock_table = self._make_storage()
        mock_table.query.return_value = {
            "Items": [{
                "job_id": "job-123",
                "tenant_id": "default",
                "status": "pending",
                "items": json.dumps([{"ID": "CLC-01"}]),
                "results": "",
                "progress": 0,
                "message": "",
                "created_at": "2026-01-01T00:00:00",
                "started_at": "",
                "completed_at": "",
                "error_message": "",
                "metadata": "{}"
            }]
        }
        job = await storage.get_job("job-123")
        assert job is not None
        assert job.job_id == "job-123"

    @pytest.mark.asyncio
    async def test_get_job_not_found(self):
        """ジョブ取得（存在しない）"""
        storage, mock_table = self._make_storage()
        mock_table.query.return_value = {"Items": []}
        job = await storage.get_job("nonexistent")
        assert job is None

    @pytest.mark.asyncio
    async def test_update_job(self):
        """ジョブ更新"""
        storage, mock_table = self._make_storage()
        from core.async_job_manager import EvaluationJob, JobStatus
        job = EvaluationJob(
            job_id="job-123", tenant_id="default",
            status=JobStatus.RUNNING, items=[], progress=50
        )
        await storage.update_job(job)
        mock_table.put_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_job(self):
        """ジョブ削除"""
        storage, mock_table = self._make_storage()
        # get_job が job を返すよう設定
        mock_table.query.return_value = {
            "Items": [{
                "job_id": "job-123",
                "tenant_id": "default",
                "status": "pending",
                "items": "[]",
                "results": "",
                "progress": 0,
                "message": "",
                "created_at": "2026-01-01T00:00:00",
                "started_at": "",
                "completed_at": "",
                "error_message": "",
                "metadata": "{}"
            }]
        }
        result = await storage.delete_job("job-123")
        assert result is True
        mock_table.delete_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_pending_jobs(self):
        """待機中ジョブ取得"""
        storage, mock_table = self._make_storage()
        mock_table.query.return_value = {"Items": []}
        jobs = await storage.get_pending_jobs(limit=5)
        assert jobs == []

    def test_decimal_conversion(self):
        """Decimal→int変換"""
        if "infrastructure.job_storage.aws_dynamodb" in sys.modules:
            del sys.modules["infrastructure.job_storage.aws_dynamodb"]

        mock_boto3 = MagicMock()
        mock_botocore = MagicMock()
        mock_botocore.exceptions.ClientError = type("ClientError", (Exception,), {})

        with patch.dict("sys.modules", {
            "boto3": mock_boto3,
            "botocore": mock_botocore,
            "botocore.exceptions": mock_botocore.exceptions,
        }):
            from infrastructure.job_storage.aws_dynamodb import decimal_to_int
            assert decimal_to_int(Decimal("5")) == 5
            assert decimal_to_int(Decimal("3.14")) == 3.14
            assert decimal_to_int({"count": Decimal("10")}) == {"count": 10}
            assert decimal_to_int([Decimal("1"), Decimal("2")]) == [1, 2]
            assert decimal_to_int("text") == "text"


# =============================================================================
# AWS SQS テスト
# =============================================================================

class TestAWSSQS:
    """AWSSQSJobQueue のテスト"""

    def _make_queue(self):
        """モック付きキューを作成"""
        mock_boto3 = MagicMock()
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session

        mock_sqs = MagicMock()
        mock_sqs.get_queue_url.return_value = {"QueueUrl": "https://sqs.us-east-1/queue"}
        mock_session.client.return_value = mock_sqs

        mock_botocore = MagicMock()
        mock_botocore.exceptions.ClientError = type("ClientError", (Exception,), {})

        with patch.dict("sys.modules", {
            "boto3": mock_boto3,
            "botocore": mock_botocore,
            "botocore.exceptions": mock_botocore.exceptions,
        }):
            if "infrastructure.job_storage.aws_sqs" in sys.modules:
                del sys.modules["infrastructure.job_storage.aws_sqs"]
            from infrastructure.job_storage.aws_sqs import AWSSQSJobQueue
            queue = AWSSQSJobQueue(region="us-east-1", queue_name="test-queue")

        return queue, mock_sqs

    def test_init(self):
        """初期化"""
        queue, mock_sqs = self._make_queue()
        assert queue._queue_url == "https://sqs.us-east-1/queue"

    @pytest.mark.asyncio
    async def test_enqueue(self):
        """エンキュー"""
        queue, mock_sqs = self._make_queue()
        mock_sqs.send_message.return_value = {"MessageId": "msg-001"}
        await queue.enqueue("job-123")
        mock_sqs.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_dequeue_with_message(self):
        """デキュー（メッセージあり）"""
        queue, mock_sqs = self._make_queue()
        mock_sqs.receive_message.return_value = {
            "Messages": [{
                "Body": json.dumps({"job_id": "job-123", "action": "process"}),
                "ReceiptHandle": "receipt-001"
            }]
        }
        result = await queue.dequeue()
        assert result == "job-123"
        mock_sqs.delete_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_dequeue_empty(self):
        """デキュー（空キュー）"""
        queue, mock_sqs = self._make_queue()
        mock_sqs.receive_message.return_value = {"Messages": []}
        result = await queue.dequeue()
        assert result is None


class TestAWSSQSParsers:
    """SQSイベント/レコードパーサーのテスト"""

    def _import_module(self):
        mock_boto3 = MagicMock()
        mock_botocore = MagicMock()
        mock_botocore.exceptions.ClientError = type("ClientError", (Exception,), {})
        with patch.dict("sys.modules", {
            "boto3": mock_boto3,
            "botocore": mock_botocore,
            "botocore.exceptions": mock_botocore.exceptions,
        }):
            if "infrastructure.job_storage.aws_sqs" in sys.modules:
                del sys.modules["infrastructure.job_storage.aws_sqs"]
            from infrastructure.job_storage import aws_sqs
            return aws_sqs

    def test_parse_sqs_event(self):
        """SQSイベントからjob_id取得"""
        mod = self._import_module()
        event = {"Records": [{"body": json.dumps({"job_id": "job-123"})}]}
        assert mod.parse_sqs_event(event) == "job-123"

    def test_parse_sqs_event_empty(self):
        """空のSQSイベント"""
        mod = self._import_module()
        assert mod.parse_sqs_event({"Records": []}) is None

    def test_parse_sqs_record(self):
        """SQSレコードからjob_id取得"""
        mod = self._import_module()
        record = {"body": json.dumps({"job_id": "job-456"})}
        assert mod.parse_sqs_record(record) == "job-456"

    def test_parse_sqs_record_plain_text(self):
        """JSON形式でないレコード（plain text）"""
        mod = self._import_module()
        record = {"body": "plain-job-id"}
        assert mod.parse_sqs_record(record) == "plain-job-id"


# =============================================================================
# GCP Firestore テスト
# =============================================================================

class TestGCPFirestore:
    """GCPFirestoreJobStorage のテスト"""

    def _make_storage(self):
        """モック付きストレージを作成"""
        mock_firestore = MagicMock()
        mock_firestore.Client.return_value = MagicMock()
        mock_field_filter = MagicMock()

        mock_google = MagicMock()
        mock_google.cloud.firestore = mock_firestore
        mock_google.cloud.firestore_v1 = MagicMock()
        mock_google.cloud.firestore_v1.base_query.FieldFilter = mock_field_filter

        with patch.dict("sys.modules", {
            "google": mock_google,
            "google.cloud": mock_google.cloud,
            "google.cloud.firestore": mock_firestore,
            "google.cloud.firestore_v1": mock_google.cloud.firestore_v1,
            "google.cloud.firestore_v1.base_query": mock_google.cloud.firestore_v1.base_query,
        }):
            if "infrastructure.job_storage.gcp_firestore" in sys.modules:
                del sys.modules["infrastructure.job_storage.gcp_firestore"]
            from infrastructure.job_storage.gcp_firestore import GCPFirestoreJobStorage
            storage = GCPFirestoreJobStorage(
                project_id="test-project",
                collection_name="test_jobs"
            )

        mock_client = mock_firestore.Client.return_value
        mock_collection = mock_client.collection.return_value
        return storage, mock_collection

    def test_init(self):
        """初期化"""
        storage, _ = self._make_storage()
        assert storage._project_id == "test-project"
        assert storage._collection_name == "test_jobs"

    @pytest.mark.asyncio
    async def test_create_job(self):
        """ジョブ作成"""
        storage, mock_collection = self._make_storage()
        job = await storage.create_job("tenant-a", [{"ID": "CLC-01"}])
        assert job.tenant_id == "tenant-a"
        mock_collection.document.return_value.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_job_found(self):
        """ジョブ取得（存在する）"""
        storage, mock_collection = self._make_storage()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "job_id": "job-123",
            "tenant_id": "default",
            "status": "pending",
            "items": [{"ID": "CLC-01"}],
            "progress": 0,
            "message": "",
            "created_at": datetime(2026, 1, 1),
        }
        mock_collection.document.return_value.get.return_value = mock_doc

        job = await storage.get_job("job-123")
        assert job is not None
        assert job.job_id == "job-123"

    @pytest.mark.asyncio
    async def test_get_job_not_found(self):
        """ジョブ取得（存在しない）"""
        storage, mock_collection = self._make_storage()
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_collection.document.return_value.get.return_value = mock_doc

        job = await storage.get_job("nonexistent")
        assert job is None

    @pytest.mark.asyncio
    async def test_update_job(self):
        """ジョブ更新"""
        storage, mock_collection = self._make_storage()
        from core.async_job_manager import EvaluationJob, JobStatus
        job = EvaluationJob(
            job_id="job-123", tenant_id="default",
            status=JobStatus.RUNNING, items=[], progress=50
        )
        await storage.update_job(job)
        mock_collection.document.return_value.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_job_found(self):
        """ジョブ削除（存在する）"""
        storage, mock_collection = self._make_storage()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_collection.document.return_value.get.return_value = mock_doc

        result = await storage.delete_job("job-123")
        assert result is True
        mock_collection.document.return_value.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_job_not_found(self):
        """ジョブ削除（存在しない）"""
        storage, mock_collection = self._make_storage()
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_collection.document.return_value.get.return_value = mock_doc

        result = await storage.delete_job("nonexistent")
        assert result is False


# =============================================================================
# GCP Cloud Tasks テスト
# =============================================================================

class TestGCPCloudTasks:
    """GCPCloudTasksJobQueue のテスト"""

    def _make_queue(self):
        """モック付きキューを作成"""
        mock_tasks = MagicMock()
        mock_client = MagicMock()
        mock_client.queue_path.return_value = "projects/test/locations/asia/queues/jobs"
        mock_tasks.CloudTasksClient.return_value = mock_client
        mock_tasks.HttpMethod.POST = "POST"

        mock_google = MagicMock()
        mock_google.cloud.tasks_v2 = mock_tasks

        with patch.dict("sys.modules", {
            "google": mock_google,
            "google.cloud": mock_google.cloud,
            "google.cloud.tasks_v2": mock_tasks,
        }):
            if "infrastructure.job_storage.gcp_tasks" in sys.modules:
                del sys.modules["infrastructure.job_storage.gcp_tasks"]
            from infrastructure.job_storage.gcp_tasks import GCPCloudTasksJobQueue
            queue = GCPCloudTasksJobQueue(
                project_id="test-project",
                location="asia-northeast1",
                queue_name="test-queue",
                target_url="https://example.com/process"
            )

        return queue, mock_client

    def test_init(self):
        """初期化"""
        queue, _ = self._make_queue()
        assert queue._project_id == "test-project"

    @pytest.mark.asyncio
    async def test_enqueue(self):
        """エンキュー"""
        queue, mock_client = self._make_queue()
        mock_client.create_task.return_value = MagicMock(name="task-001")
        await queue.enqueue("job-123")
        mock_client.create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_dequeue_returns_none(self):
        """Cloud Tasksはプッシュ型なのでdequeueはNone"""
        queue, _ = self._make_queue()
        result = await queue.dequeue()
        assert result is None


class TestGCPCloudTasksParsers:
    """Cloud Tasks パーサーのテスト"""

    def _import_module(self):
        mock_tasks = MagicMock()
        mock_google = MagicMock()
        mock_google.cloud.tasks_v2 = mock_tasks
        with patch.dict("sys.modules", {
            "google": mock_google,
            "google.cloud": mock_google.cloud,
            "google.cloud.tasks_v2": mock_tasks,
        }):
            if "infrastructure.job_storage.gcp_tasks" in sys.modules:
                del sys.modules["infrastructure.job_storage.gcp_tasks"]
            from infrastructure.job_storage import gcp_tasks
            return gcp_tasks

    def test_parse_cloud_task_request(self):
        """リクエストボディからjob_id取得"""
        mod = self._import_module()
        body = json.dumps({"job_id": "job-123"}).encode()
        assert mod.parse_cloud_task_request(body) == "job-123"

    def test_parse_cloud_task_request_invalid(self):
        """無効なJSONリクエスト"""
        mod = self._import_module()
        assert mod.parse_cloud_task_request(b"not-json") is None

    def test_is_cloud_task_request(self):
        """Cloud Tasks リクエスト判定"""
        mod = self._import_module()
        headers = {
            "X-CloudTasks-TaskName": "task-001",
            "X-CloudTasks-QueueName": "queue-001"
        }
        assert mod.is_cloud_task_request(headers) is True

    def test_is_not_cloud_task_request(self):
        """通常のリクエスト"""
        mod = self._import_module()
        assert mod.is_cloud_task_request({}) is False
