"""
================================================================================
azure_queue.py - Azure Queue Storageジョブキュー実装
================================================================================

【概要】
Azure Queue Storageを使用したジョブキュー実装です。
Azure Functionsのキュートリガーと連携して非同期処理を実現します。

【必要な環境変数】
- AZURE_STORAGE_CONNECTION_STRING: ストレージアカウント接続文字列
  または
- AZURE_STORAGE_ACCOUNT_NAME: ストレージアカウント名
- AZURE_STORAGE_ACCOUNT_KEY: ストレージアカウントキー

【キュー名】
デフォルト: evaluation-jobs
環境変数 JOB_QUEUE_NAME で変更可能

【必要なパッケージ】
pip install azure-storage-queue

================================================================================
"""

import os
import json
import logging
from typing import Optional

from core.async_job_manager import JobQueueBase

logger = logging.getLogger(__name__)

# Azure Queue Storage SDK
try:
    from azure.storage.queue import QueueClient, QueueServiceClient
    from azure.core.exceptions import ResourceExistsError
    AZURE_QUEUE_AVAILABLE = True
except ImportError:
    AZURE_QUEUE_AVAILABLE = False
    logger.warning(
        "[AzureQueueStorage] azure-storage-queue not installed. "
        "Run: pip install azure-storage-queue"
    )


class AzureQueueJobQueue(JobQueueBase):
    """
    Azure Queue Storageジョブキュー

    Azure Queue Storageを使用してジョブ通知を管理します。
    Azure Functionsのキュートリガーと連携します。
    """

    DEFAULT_QUEUE_NAME = "evaluation-jobs"

    def __init__(
        self,
        connection_string: str = None,
        queue_name: str = None
    ):
        """
        Args:
            connection_string: ストレージ接続文字列
            queue_name: キュー名（デフォルト: evaluation-jobs）
        """
        if not AZURE_QUEUE_AVAILABLE:
            raise ImportError(
                "azure-storage-queue is required. "
                "Install it with: pip install azure-storage-queue"
            )

        # 接続情報の取得
        self._connection_string = (
            connection_string or
            os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        )

        if not self._connection_string:
            account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
            account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")

            if account_name and account_key:
                self._connection_string = (
                    f"DefaultEndpointsProtocol=https;"
                    f"AccountName={account_name};"
                    f"AccountKey={account_key};"
                    f"EndpointSuffix=core.windows.net"
                )

        if not self._connection_string:
            raise ValueError(
                "Azure Storage connection string is required. "
                "Set AZURE_STORAGE_CONNECTION_STRING environment variable."
            )

        self._queue_name = (
            queue_name or
            os.getenv("JOB_QUEUE_NAME", self.DEFAULT_QUEUE_NAME)
        )

        # キュークライアントを初期化
        self._queue_client = QueueClient.from_connection_string(
            conn_str=self._connection_string,
            queue_name=self._queue_name
        )

        # キューを作成（存在しない場合）
        self._ensure_queue_exists()

        logger.info(f"[AzureQueueJobQueue] Initialized with queue: {self._queue_name}")

    def _ensure_queue_exists(self):
        """キューが存在することを確認"""
        try:
            self._queue_client.create_queue()
            logger.info(f"[AzureQueueJobQueue] Queue created: {self._queue_name}")
        except ResourceExistsError:
            logger.debug(f"[AzureQueueJobQueue] Queue already exists: {self._queue_name}")

    async def enqueue(self, job_id: str) -> None:
        """
        ジョブをキューに追加

        Args:
            job_id: キューに追加するジョブID
        """
        try:
            # メッセージ内容（JSON形式）
            message = json.dumps({
                "job_id": job_id,
                "action": "process"
            })

            # キューにメッセージを送信
            # visibility_timeout: メッセージが他のワーカーに見えなくなる時間（秒）
            # time_to_live: メッセージの有効期限（秒）、-1で無期限
            self._queue_client.send_message(
                content=message,
                visibility_timeout=0,  # 即座に処理可能
                time_to_live=-1  # 無期限
            )

            logger.info(f"[AzureQueueJobQueue] Job enqueued: {job_id}")

        except Exception as e:
            logger.error(f"[AzureQueueJobQueue] Error enqueuing job {job_id}: {e}")
            raise

    async def dequeue(self) -> Optional[str]:
        """
        キューからジョブIDを取得

        Returns:
            ジョブID（キューが空の場合はNone）

        Note:
            Azure Functionsのキュートリガーを使用する場合、
            この関数は直接呼び出されません。
            キュートリガーが自動的にメッセージを取得します。
        """
        try:
            messages = self._queue_client.receive_messages(
                messages_per_page=1,
                visibility_timeout=300  # 5分間他のワーカーから見えなくする
            )

            for message in messages:
                # メッセージを処理
                content = json.loads(message.content)
                job_id = content.get("job_id")

                # メッセージを削除（処理完了）
                self._queue_client.delete_message(message)

                logger.info(f"[AzureQueueJobQueue] Job dequeued: {job_id}")
                return job_id

            return None

        except Exception as e:
            logger.error(f"[AzureQueueJobQueue] Error dequeuing: {e}")
            return None

    async def get_queue_length(self) -> int:
        """
        キュー内のメッセージ数を取得

        Returns:
            メッセージ数
        """
        try:
            properties = self._queue_client.get_queue_properties()
            count = properties.approximate_message_count
            logger.debug(f"[AzureQueueJobQueue] Queue length: {count}")
            return count
        except Exception as e:
            logger.error(f"[AzureQueueJobQueue] Error getting queue length: {e}")
            return 0

    async def clear(self) -> None:
        """キューをクリア"""
        try:
            self._queue_client.clear_messages()
            logger.info(f"[AzureQueueJobQueue] Queue cleared: {self._queue_name}")
        except Exception as e:
            logger.error(f"[AzureQueueJobQueue] Error clearing queue: {e}")
            raise


def parse_queue_message(message_content: str) -> Optional[str]:
    """
    キューメッセージをパースしてジョブIDを取得

    Azure Functionsのキュートリガーから呼び出されます。

    Args:
        message_content: キューメッセージの内容

    Returns:
        ジョブID
    """
    try:
        data = json.loads(message_content)
        return data.get("job_id")
    except json.JSONDecodeError:
        # JSON形式でない場合、メッセージ自体がジョブIDと仮定
        return message_content
    except Exception as e:
        logger.error(f"[AzureQueueJobQueue] Error parsing message: {e}")
        return None
